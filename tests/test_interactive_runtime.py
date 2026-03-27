"""Regression coverage for checkpoint-safe pause/resume control."""

import asyncio
import time

import orchestrator.modes.creator_critic as creator_critic
import orchestrator.modes.democracy as democracy
from orchestrator.engine import (
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
