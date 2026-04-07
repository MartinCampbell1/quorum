"""Regression coverage for checkpoint-safe pause/resume control."""

import asyncio
import json
from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import patch

from langchain_gateway import GatewayInvocationError
import orchestrator.modes.base as mode_base
import orchestrator.modes.creator_critic as creator_critic
import orchestrator.modes.democracy as democracy
import orchestrator.modes.debate as debate
import orchestrator.modes.tournament as tournament
import orchestrator.generation.moa as moa_mode
from orchestrator.engine import (
    SessionRunner,
    CHECKPOINT_SAVERS,
    has_checkpoint_runtime,
    fork_from_checkpoint,
    inject_instruction,
    request_pause,
    request_resume,
    run,
)
from orchestrator.models import AgentConfig, store


async def _wait_for_status(session_id: str, expected: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = store.get(session_id)
        if session and session["status"] == expected:
            return session
        await asyncio.sleep(0.02)
    session = store.get(session_id)
    raise AssertionError(f"Session {session_id} did not reach status '{expected}'. Last session: {session}")


def test_creator_critic_supports_pause_resume_and_instruction_injection(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        prompts.append((agent["role"], prompt))
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Review the BTC trading plan",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        assert request_pause(session_id) is True

        paused = await _wait_for_status(session_id, "paused")
        assert paused["current_checkpoint_id"] == "cp_1"
        assert paused["checkpoints"][0]["next_node"] == "critic_evaluates"

        queued = inject_instruction(session_id, "Pay extra attention to recent Bitcoin news and volatility.")
        assert queued == 1
        assert store.get(session_id)["pending_instructions"] == 1

        assert request_resume(session_id) is True

        completed = await _wait_for_status(session_id, "completed")
        assert completed["pending_instructions"] == 0
        assert len(completed["checkpoints"]) >= 2
        assert any(message["agent_id"] == "user" for message in completed["messages"])
        assert any(event["type"] == "run_started" for event in completed["events"])
        assert any(event["type"] == "checkpoint_created" for event in completed["events"])
        assert any(event["type"] == "agent_message" for event in completed["events"])
        assert any(event["type"] == "run_completed" for event in completed["events"])
        assert "Pay extra attention to recent Bitcoin news and volatility." in prompts[-1][1]

    asyncio.run(scenario())


def test_creator_critic_persists_protocol_blueprint_and_trace(monkeypatch):
    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Refine the execution brief handoff.",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        completed = await _wait_for_status(session_id, "completed")

        assert completed["protocol_blueprint"]["entry_node_id"] == "creator_produces"
        assert completed["protocol_shadow_validation"]["validated_transitions"] >= 2
        assert completed["protocol_shadow_validation"]["invalid_transitions"] == 0
        assert any(step["from_node_id"] == "creator_produces" for step in completed["protocol_trace"])
        assert completed["protocol_trace"][-1]["to_node_id"] == "__end__"
        assert completed["config"]["topology_state"]["selected_template"]
        assert completed["protocol_blueprint"]["planner_hints"]["topology"]["selected_template"]
        assert any(event["type"] == "topology_optimized" for event in completed["events"])
        assert any(event["type"] == "topology_runtime_plan" for event in completed["events"])

    asyncio.run(scenario())


def test_moa_persists_generation_trace_and_protocol_trace(monkeypatch):
    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        role = agent["role"]
        if "judge pack" in prompt.lower():
            return (
                '{"winner_candidate_id":"aggregate_1","summary":"aggregate_1 wins",'
                '"scores":['
                '{"candidate_id":"aggregate_1","overall_score":8.8,"criteria":{"buildability":9},"rationale":"stronger"},'
                '{"candidate_id":"aggregate_2","overall_score":6.9,"criteria":{"buildability":7},"rationale":"weaker"}'
                "]}"
            )
        if role.startswith("proposer"):
            return f"{role} proposal"
        if role.startswith("aggregator"):
            return f"{role} aggregate"
        if role == "final_synthesizer":
            return "Final MoA synthesis"
        raise AssertionError(f"Unexpected agent call: {role}")

    monkeypatch.setattr(moa_mode, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="moa",
            task="Generate founder-fit startup directions before debate.",
            agents=[
                AgentConfig(role="proposer_market", provider="claude", tools=[]),
                AgentConfig(role="proposer_builder", provider="codex", tools=[]),
                AgentConfig(role="aggregator_operator", provider="gemini", tools=[]),
                AgentConfig(role="aggregator_editor", provider="claude", tools=[]),
                AgentConfig(role="final_synthesizer", provider="codex", tools=[]),
            ],
            config={"aggregator_count": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        generation_trace = completed["config"]["generation_trace"]

        assert completed["protocol_blueprint"]["entry_node_id"] == "generate_layer_one"
        assert completed["protocol_shadow_validation"]["validated_transitions"] >= 4
        assert completed["protocol_shadow_validation"]["invalid_transitions"] == 0
        assert completed["protocol_trace"][-1]["to_node_id"] == "__end__"
        assert generation_trace["selected_candidate_id"] == "aggregate_1"
        assert len(generation_trace["layer2_outputs"]) == 2
        assert generation_trace["final_artifact"]["layer"] == "final"
        assert any(event["type"] == "generation_candidate_created" for event in completed["events"])
        assert any(event["type"] == "generation_candidate_scored" for event in completed["events"])

    asyncio.run(scenario())


def test_fork_from_checkpoint_creates_independent_branch(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        prompts.append((agent["role"], prompt))
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Review the BTC trading plan",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        assert request_pause(session_id) is True
        paused = await _wait_for_status(session_id, "paused")

        new_session_id = fork_from_checkpoint(
            session_id,
            checkpoint_id=paused["current_checkpoint_id"],
            content="Branch and focus on downside risk.",
        )
        assert new_session_id
        assert new_session_id != session_id

        branched = await _wait_for_status(new_session_id, "completed")
        assert branched["forked_from"] == session_id
        assert branched["forked_checkpoint_id"] == paused["current_checkpoint_id"]
        assert any(event["type"] == "branch_started" for event in branched["events"])
        assert any("Branch and focus on downside risk." in prompt for _, prompt in prompts)

        original = store.get(session_id)
        assert original["status"] == "paused"

    asyncio.run(scenario())


def test_fork_from_checkpoint_works_after_in_memory_saver_is_evicted(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        prompts.append((agent["role"], prompt))
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Branch from persisted checkpoint runtime",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        assert request_pause(session_id) is True
        paused = await _wait_for_status(session_id, "paused")
        assert store.checkpoint_runtime_path(session_id).exists() is True

        CHECKPOINT_SAVERS.pop(session_id, None)
        assert has_checkpoint_runtime(session_id) is True

        new_session_id = fork_from_checkpoint(
            session_id,
            checkpoint_id=paused["current_checkpoint_id"],
            content="Branch from disk-backed checkpoint state.",
        )

        assert new_session_id
        branched = await _wait_for_status(new_session_id, "completed")
        assert branched["forked_from"] == session_id
        assert any("Branch from disk-backed checkpoint state." in prompt for _, prompt in prompts)

    asyncio.run(scenario())


def test_fork_from_terminal_checkpoint_uses_latest_resumable_checkpoint(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        prompts.append((agent["role"], prompt))
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Continue the completed discussion",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert len(completed["checkpoints"]) >= 2
        terminal_checkpoint = completed["current_checkpoint_id"]
        resumable_checkpoint = completed["checkpoints"][-2]["id"]

        new_session_id = fork_from_checkpoint(
            session_id,
            checkpoint_id=terminal_checkpoint,
            content="Continue and focus on operational risk.",
        )

        assert new_session_id
        branched = await _wait_for_status(new_session_id, "completed")
        assert branched["forked_from"] == session_id
        assert branched["forked_checkpoint_id"] == resumable_checkpoint
        assert any("Continue and focus on operational risk." in prompt for _, prompt in prompts)

    asyncio.run(scenario())


def test_fork_from_tournament_checkpoint_retargets_session_state(monkeypatch):
    captured_states: list[dict] = []

    async def fake_run_parallel_stage(state: dict) -> dict:
        captured_states.append(
            {
                "session_id": state.get("session_id"),
                "agent_session_ids": [agent.get("session_id") for agent in state.get("agents", [])],
                "submission_session_ids": [entry.get("session_id") for entry in state.get("submissions", [])],
            }
        )
        winner = dict((state.get("submissions") or [state["agents"][0]])[0])
        return {
            "winners": [winner],
            "match_history": [],
            "parallel_stage_children": [],
            "parallel_stage_group_id": "pg_test",
            "advance_target": "crown_champion",
            "result": "Parallel stage finished",
        }

    monkeypatch.setattr(tournament, "run_parallel_stage", fake_run_parallel_stage)

    async def scenario() -> None:
        session_id = await run(
            mode="tournament",
            task="Pick the best project to prioritize first.",
            agents=[
                AgentConfig(role="contestant_1", provider="claude", tools=[]),
                AgentConfig(role="contestant_2", provider="codex", tools=[]),
                AgentConfig(role="judge", provider="gemini", tools=[]),
            ],
            config={"execution_mode": "parallel", "max_rounds": 1},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert len(completed["checkpoints"]) >= 3
        parallel_checkpoint = next(
            checkpoint["id"]
            for checkpoint in completed["checkpoints"]
            if checkpoint.get("next_node") == "run_parallel_stage"
        )

        new_session_id = fork_from_checkpoint(session_id, checkpoint_id=parallel_checkpoint)
        assert new_session_id

        branched = await _wait_for_status(new_session_id, "completed")
        assert branched["forked_from"] == session_id
        assert len(captured_states) >= 2
        assert captured_states[0]["session_id"] == session_id
        assert captured_states[-1]["session_id"] == new_session_id
        assert set(captured_states[-1]["agent_session_ids"]) == {new_session_id}
        assert set(captured_states[-1]["submission_session_ids"]) == {new_session_id}

    asyncio.run(scenario())


def test_democracy_emits_vote_and_round_events(monkeypatch):
    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        return f'{{"position": "Ship the strategy", "reasoning": "{agent["role"]} agrees"}}'

    monkeypatch.setattr(democracy, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="democracy",
            task="Decide whether to ship the strategy report",
            agents=[
                AgentConfig(role="voter_1", provider="claude", tools=[]),
                AgentConfig(role="voter_2", provider="claude", tools=[]),
                AgentConfig(role="voter_3", provider="claude", tools=[]),
            ],
            config={"max_rounds": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        event_types = [event["type"] for event in completed["events"]]
        assert event_types.count("vote_recorded") == 3
        assert "round_started" in event_types
        assert "round_completed" in event_types
        assert completed["result"] == "Ship the strategy"

    asyncio.run(scenario())


def test_creator_critic_fails_when_critic_returns_empty_output(monkeypatch):
    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        if agent["role"] == "creator":
            return "Draft analysis"
        return ""

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Waiting state probe",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="codex", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        failed = await _wait_for_status(session_id, "failed")
        assert any(event["type"] == "agent_failed" for event in failed["events"])
        assert any(event["type"] == "run_failed" for event in failed["events"])
        assert "empty response" in failed["result"]

    asyncio.run(scenario())


def test_debate_fails_when_judge_returns_empty_verdict(monkeypatch):
    calls = {"count": 0}

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        if agent["role"] == "proponent":
            return "Pro argument"
        if agent["role"] == "opponent":
            return "Con argument"
        calls["count"] += 1
        return ""

    monkeypatch.setattr(debate, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="debate",
            task="Should we ship the rewrite?",
            agents=[
                AgentConfig(role="proponent", provider="claude", tools=[]),
                AgentConfig(role="opponent", provider="codex", tools=[]),
                AgentConfig(role="judge", provider="gemini", tools=[]),
            ],
            config={"max_rounds": 2},
        )

        failed = await _wait_for_status(session_id, "failed")
        assert calls["count"] == 1
        assert any(event["type"] == "agent_failed" and event.get("agent_id") == "judge" for event in failed["events"])
        assert not any(message["phase"] == "verdict" for message in failed["messages"])
        assert "empty response" in failed["result"]

    asyncio.run(scenario())


def test_creator_critic_recovers_when_critic_provider_falls_back(monkeypatch):
    attempts: list[tuple[str, str | None]] = []

    def fake_call_agent(
        provider: str,
        prompt: str,
        system_prompt: str = "",
        tools=None,
        workdir=None,
        workspace_paths=None,
        session_id=None,
        agent_role=None,
    ) -> str:
        attempts.append((provider, agent_role))
        if agent_role == "creator":
            return "Draft analysis"
        if provider == "claude":
            raise GatewayInvocationError(
                provider=provider,
                agent_role=agent_role,
                profile_used="acc1",
                retries=0,
                gateway_error="claude returned tool scaffolding without a usable text response.",
            )
        return "APPROVED: ready to ship"

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Fallback path for critic",
            agents=[
                AgentConfig(role="creator", provider="codex", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert completed["result"] == "Draft analysis"
        assert any(message["agent_id"] == "critic" and "APPROVED" in message["content"] for message in completed["messages"])
        assert ("claude", "critic") in attempts
        assert ("codex", "critic") in attempts
        assert not any(event["type"] == "run_failed" for event in completed["events"])

    asyncio.run(scenario())


def test_debate_recovers_when_judge_provider_falls_back(monkeypatch):
    attempts: list[tuple[str, str | None]] = []

    def fake_call_agent(
        provider: str,
        prompt: str,
        system_prompt: str = "",
        tools=None,
        workdir=None,
        workspace_paths=None,
        session_id=None,
        agent_role=None,
    ) -> str:
        attempts.append((provider, agent_role))
        if agent_role == "proponent":
            return "Pro argument"
        if agent_role == "opponent":
            return "Con argument"
        if provider == "gemini":
            raise GatewayInvocationError(
                provider=provider,
                agent_role=agent_role,
                profile_used="acc2",
                retries=0,
                gateway_error="gemini returned no usable text output.",
            )
        return "FINAL_VERDICT Verdict: proponent wins because the argument is more specific."

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    async def scenario() -> None:
        session_id = await run(
            mode="debate",
            task="Should we ship the rewrite?",
            agents=[
                AgentConfig(role="proponent", provider="claude", tools=[]),
                AgentConfig(role="opponent", provider="codex", tools=[]),
                AgentConfig(role="judge", provider="gemini", tools=[]),
            ],
            config={"max_rounds": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert "Verdict:" in completed["result"]
        assert any(message["phase"] == "verdict" and "Verdict:" in message["content"] for message in completed["messages"])
        assert ("gemini", "judge") in attempts
        assert any(provider != "gemini" and role == "judge" for provider, role in attempts)
        assert not any(event["type"] == "run_failed" for event in completed["events"])

    asyncio.run(scenario())


def test_debate_uses_configured_round_budget_by_default(monkeypatch):
    call_counts = {"proponent": 0, "opponent": 0, "judge": 0}

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        role = agent["role"]
        call_counts[role] += 1
        if role == "proponent":
            return f"Pro argument round {call_counts[role]}"
        if role == "opponent":
            return f"Con argument round {call_counts[role]}"
        if call_counts[role] == 1:
            return "Interim assessment: both sides should sharpen their evidence."
        return "Final verdict: proponent wins on specificity."

    monkeypatch.setattr(debate, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="debate",
            task="Should we continue the project?",
            agents=[
                AgentConfig(role="proponent", provider="gemini", tools=[]),
                AgentConfig(role="opponent", provider="codex", tools=[]),
                AgentConfig(role="judge", provider="gemini", tools=[]),
            ],
            config={"max_rounds": 2},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert call_counts == {"proponent": 2, "opponent": 2, "judge": 2}
        assert "Final verdict" in completed["result"]
        assert len([message for message in completed["messages"] if message["agent_id"] == "proponent"]) == 2
        assert len([message for message in completed["messages"] if message["agent_id"] == "opponent"]) == 2
        round_events = [event for event in completed["events"] if event["type"] == "round_completed"]
        assert len(round_events) == 2

    asyncio.run(scenario())


def test_debate_allows_judge_to_finish_early_with_explicit_marker(monkeypatch):
    call_counts = {"proponent": 0, "opponent": 0, "judge": 0}

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        role = agent["role"]
        call_counts[role] += 1
        if role == "proponent":
            return "Pro opening argument"
        if role == "opponent":
            return "Con opening argument"
        return "FINAL_VERDICT Clear winner after one round."

    monkeypatch.setattr(debate, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="debate",
            task="Should we ship this now?",
            agents=[
                AgentConfig(role="proponent", provider="gemini", tools=[]),
                AgentConfig(role="opponent", provider="codex", tools=[]),
                AgentConfig(role="judge", provider="codex", tools=[]),
            ],
            config={"max_rounds": 5},
        )

        completed = await _wait_for_status(session_id, "completed")
        assert call_counts == {"proponent": 1, "opponent": 1, "judge": 1}
        assert "Clear winner" in completed["result"]
        assert "FINAL_VERDICT" not in completed["result"]
        round_events = [event for event in completed["events"] if event["type"] == "round_completed"]
        assert len(round_events) == 1

    asyncio.run(scenario())


def test_store_ingests_bridge_tool_events_from_runtime_file():
    session_id = store.create(
        mode="creator_critic",
        task="Bridge tool event ingestion",
        agents=[
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        config={},
    )

    runtime_dir = Path.home() / ".multi-agent" / "runtime_events"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / f"{session_id}.jsonl"
    runtime_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "tool_call_started",
                        "title": "Tool call started",
                        "detail": "stitch_mcp__search",
                        "agent_id": "creator",
                        "tool_name": "stitch_mcp__search",
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_call_finished",
                        "title": "Tool call finished",
                        "detail": "ok",
                        "agent_id": "creator",
                        "tool_name": "stitch_mcp__search",
                        "success": True,
                    }
                ),
            ]
        )
        + "\n"
    )

    events = store.list_events(session_id)
    event_types = [event["type"] for event in events]
    assert "tool_call_started" in event_types
    assert "tool_call_finished" in event_types

    session = store.get(session_id)
    assert any(event["type"] == "tool_call_finished" for event in session["events"])
    assert runtime_file.exists() is False


def test_session_runner_eagerly_ingests_runtime_tool_events():
    session_id = store.create(
        mode="creator_critic",
        task="Eager tool event ingestion",
        agents=[
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        config={},
    )

    runtime_dir = Path.home() / ".multi-agent" / "runtime_events"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / f"{session_id}.jsonl"
    runtime_file.write_text(
        json.dumps(
            {
                "type": "tool_call_started",
                "title": "Tool call started",
                "detail": "market_api",
                "agent_id": "creator",
                "tool_name": "market_api",
            }
        )
        + "\n"
    )

    runner = SessionRunner(
        session_id=session_id,
        mode="creator_critic",
        graph=None,
        graph_config={},
        initial_state=None,
        checkpointer=None,
    )
    snapshot = SimpleNamespace(
        values={"messages": [], "result": ""},
        next=[],
        config={"configurable": {"checkpoint_id": "graph_cp_1"}},
    )

    with patch.object(store, "ingest_runtime_events", wraps=store.ingest_runtime_events) as mock_ingest:
        asyncio.run(runner._sync_from_snapshot(snapshot))

    mock_ingest.assert_called_once_with(session_id)
    session = store.get(session_id)
    assert any(event["type"] == "tool_call_started" for event in session["events"])
    assert runtime_file.exists() is False
