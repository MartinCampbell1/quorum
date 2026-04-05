"""Regression coverage for the remediation pass.

This file locks in the removal of hidden minimax arbitration and the parallel
chunk-processing contract for map_reduce.
"""

import asyncio
import time

import orchestrator.engine as engine
import orchestrator.modes.board as board
import orchestrator.modes.base as mode_base
import orchestrator.modes.debate as debate
import orchestrator.modes.democracy as democracy
import orchestrator.modes.map_reduce as map_reduce
import orchestrator.modes.tournament as tournament

from langchain_gateway import GatewayInvocationError


def _forbidden(*args, **kwargs):
    raise AssertionError("hidden arbiter should not be called")


def test_democracy_tally_votes_uses_majority_without_hidden_arbiter(monkeypatch):
    monkeypatch.setattr(democracy, "call_agent", _forbidden, raising=False)

    state = {
        "task": "Pick a database",
        "agents": [],
        "messages": [],
        "votes": [
            {"agent_id": "claude", "position": "Use Postgres", "reasoning": "scale"},
            {"agent_id": "gemini", "position": "Use Postgres", "reasoning": "reliable"},
            {"agent_id": "codex", "position": "Use SQLite", "reasoning": "simple"},
        ],
        "round": 1,
        "max_rounds": 3,
        "majority_position": "",
        "result": "",
    }

    result = democracy.tally_votes(state)

    assert result["majority_position"] == "Use Postgres"
    assert result["result"] == "Use Postgres"
    assert result["messages"][0]["phase"] == "tally_round_1"


def test_democracy_force_decision_is_deterministic(monkeypatch):
    monkeypatch.setattr(democracy, "call_agent", _forbidden, raising=False)

    state = {
        "task": "Choose a storage engine",
        "agents": [],
        "messages": [],
        "votes": [
            {"agent_id": "claude", "position": "Use Postgres", "reasoning": ""},
            {"agent_id": "gemini", "position": "Use SQLite", "reasoning": ""},
            {"agent_id": "codex", "position": "Use Postgres", "reasoning": ""},
            {"agent_id": "minimax", "position": "Use SQLite", "reasoning": ""},
        ],
        "round": 3,
        "max_rounds": 3,
        "majority_position": "",
        "result": "",
    }

    result = democracy.force_decision(state)

    assert result["majority_position"] == "Use Postgres"
    assert result["result"] == "Use Postgres"
    assert "Deterministic fallback" in result["messages"][0]["content"]


def test_board_check_consensus_is_deterministic(monkeypatch):
    monkeypatch.setattr(board, "call_agent", _forbidden, raising=False)

    state = {
        "task": "Agree on a deployment plan",
        "agents": [
            {"role": "chair", "provider": "claude", "system_prompt": "", "tools": []},
            {"role": "dir_2", "provider": "gemini", "system_prompt": "", "tools": []},
            {"role": "dir_3", "provider": "codex", "system_prompt": "", "tools": []},
        ],
        "messages": [],
        "positions": [
            {"director": "chair", "position": "Deploy on Monday", "reasoning": "safer", "action_items": []},
            {"director": "dir_2", "position": "Deploy on Monday", "reasoning": "ready", "action_items": []},
            {"director": "dir_3", "position": "Deploy on Monday", "reasoning": "aligned", "action_items": []},
        ],
        "vote_round": 1,
        "max_rounds": 2,
        "consensus_reached": False,
        "decision": "",
        "worker_results": [],
        "result": "",
    }

    result = board.check_consensus(state)

    assert result["consensus_reached"] is False
    assert result["scrutiny_requested"] is True
    assert result["messages"][0]["phase"] == "consensus_check"
    scrutiny = board.scrutinize_consensus({**state, **result})
    assert scrutiny["consensus_reached"] is True
    assert scrutiny["decision"] == "Deploy on Monday"
    assert scrutiny["messages"][0]["phase"] == "consensus_scrutiny"


def test_board_check_consensus_uses_structured_decision_key(monkeypatch):
    monkeypatch.setattr(board, "call_agent", _forbidden, raising=False)

    state = {
        "task": "Pick which project to strengthen first",
        "agents": [
            {"role": "chair", "provider": "codex", "system_prompt": "", "tools": []},
            {"role": "dir_2", "provider": "gemini", "system_prompt": "", "tools": []},
            {"role": "dir_3", "provider": "codex", "system_prompt": "", "tools": []},
        ],
        "messages": [],
        "positions": [
            {
                "director": "chair",
                "position": "Strengthen GraphRAG first as a paid service.",
                "reasoning": "Closest to cash.",
                "action_items": [],
                "decision_key": "GRAPH_RAG_SERVICE_FIRST",
            },
            {
                "director": "dir_2",
                "position": "GraphRAG should go first because it is the fastest path to revenue.",
                "reasoning": "Shorter time to money.",
                "action_items": [],
                "decision_key": "GRAPH_RAG_SERVICE_FIRST",
            },
            {
                "director": "dir_3",
                "position": "Do not pivot. Sell GraphRAG as a service-led intelligence layer first.",
                "reasoning": "Autopilot can stay internal for now.",
                "action_items": [],
                "decision_key": "GRAPH_RAG_SERVICE_FIRST",
            },
        ],
        "vote_round": 1,
        "max_rounds": 2,
        "consensus_reached": False,
        "decision": "",
        "worker_results": [],
        "result": "",
    }

    result = board.check_consensus(state)

    assert result["consensus_reached"] is False
    assert result["scrutiny_requested"] is True
    scrutiny = board.scrutinize_consensus({**state, **result})
    assert scrutiny["consensus_reached"] is True
    assert scrutiny["decision"] == "Strengthen GraphRAG first as a paid service."


def test_board_directors_analyze_retries_meta_reply_with_next_provider(monkeypatch):
    events: list[tuple[str, str, str]] = []

    class FakeStore:
        def append_event(self, session_id, event_type, title, detail="", **extra):
            events.append((event_type, title, detail))

    calls: list[str] = []

    def fake_call_agent_cfg(agent, prompt):
        calls.append(agent["provider"])
        if agent["provider"] == "claude":
            return '{"position":"I need search tool permissions to do proper market research.","reasoning":"","action_items":[]}'
        return (
            '{"decision_key":"GRAPH_RAG_SERVICE_FIRST","position":"Sell GraphRAG as a paid diagnostic first.",'
            '"reasoning":"Fastest path to cash.","action_items":["Define the pilot offer"]}'
        )

    monkeypatch.setattr(board, "store", FakeStore())
    monkeypatch.setattr(board, "call_agent_cfg", fake_call_agent_cfg)
    monkeypatch.setattr(board, "BOARD_PROGRESS_HEARTBEAT_SEC", 999)
    monkeypatch.setattr(board, "BOARD_MAX_INVALID_ATTEMPTS", 2)

    state = {
        "task": "Strengthen the GraphRAG project",
        "agents": [
            {
                "role": "product_strengthener",
                "provider": "claude",
                "system_prompt": "",
                "tools": [],
                "session_id": "sess_test",
                "session_provider_pool": ["claude", "codex", "gemini"],
            },
            {
                "role": "growth_operator",
                "provider": "gemini",
                "system_prompt": "",
                "tools": [],
                "session_id": "sess_test",
                "session_provider_pool": ["claude", "codex", "gemini"],
            },
            {
                "role": "execution_critic",
                "provider": "codex",
                "system_prompt": "",
                "tools": [],
                "session_id": "sess_test",
                "session_provider_pool": ["claude", "codex", "gemini"],
            },
        ],
        "messages": [],
        "user_messages": [],
        "positions": [],
        "vote_round": 0,
        "max_rounds": 3,
        "consensus_reached": False,
        "decision": "",
        "worker_results": [],
        "result": "",
    }

    result = board.directors_analyze(state)

    assert result["positions"][0]["decision_key"] == "GRAPH_RAG_SERVICE_FIRST"
    assert "Reasoning: Fastest path to cash." in result["messages"][0]["content"]
    assert "Decision key: GRAPH_RAG_SERVICE_FIRST" in result["messages"][0]["content"]
    assert calls[:2] == ["claude", "codex"]
    assert any(event_type == "director_invalid" for event_type, _, _ in events)
    assert any(event_type == "director_started" for event_type, _, _ in events)
    assert any(event_type == "director_completed" for event_type, _, _ in events)


def test_map_reduce_process_chunks_runs_concurrently(monkeypatch):
    def slow_call(agent, prompt):
        time.sleep(0.2)
        return f"{agent['role']}: {prompt.splitlines()[0]}"

    monkeypatch.setattr(map_reduce, "call_agent_cfg", slow_call)

    state = {
        "task": "Summarize the repository",
        "agents": [
            {"role": "planner", "provider": "claude", "system_prompt": "", "tools": []},
            {"role": "worker_1", "provider": "codex", "system_prompt": "", "tools": []},
            {"role": "worker_2", "provider": "gemini", "system_prompt": "", "tools": []},
            {"role": "synth", "provider": "claude", "system_prompt": "", "tools": []},
        ],
        "messages": [],
        "chunks": ["alpha", "beta", "gamma"],
        "chunk_results": [],
        "synthesis": "",
        "result": "",
    }

    started = time.perf_counter()
    result = asyncio.run(map_reduce.process_chunks(state))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
    assert [item["worker"] for item in result["chunk_results"]] == ["worker_1", "worker_2", "worker_1"]
    assert len(result["messages"]) == 3


def test_call_agent_cfg_retries_critical_roles_with_provider_fallback(monkeypatch):
    attempts: list[tuple[str, str | None, str]] = []

    def fake_call_agent(provider, prompt, system_prompt="", tools=None, **kwargs):
        attempts.append((provider, kwargs.get("agent_role"), prompt))
        if provider == "claude":
            raise GatewayInvocationError(
                provider=provider,
                agent_role=kwargs.get("agent_role"),
                profile_used="acc1",
                retries=0,
                gateway_error="claude returned tool scaffolding without a usable text response.",
            )
        return "APPROVED: concise critique"

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    response = mode_base.call_agent_cfg(
        {
            "role": "critic",
            "provider": "claude",
            "system_prompt": "",
            "tools": [],
        },
        "Review the draft and decide if it is ready.",
    )

    assert response == "APPROVED: concise critique"
    assert [provider for provider, _, _ in attempts] == ["claude", "codex"]
    assert "FINAL RESPONSE CONTRACT" in attempts[0][2]


def test_call_agent_cfg_retries_noncritical_roles_on_gateway_failure(monkeypatch):
    attempts: list[tuple[str, str]] = []

    def fake_call_agent(provider, prompt, system_prompt="", tools=None, **kwargs):
        attempts.append((provider, prompt))
        if provider == "claude":
            raise GatewayInvocationError(
                provider=provider,
                agent_role=kwargs.get("agent_role"),
                profile_used="acc1",
                retries=0,
                gateway_error="provider failed",
            )
        return "Plan: keep launch health checks lightweight."

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    response = mode_base.call_agent_cfg(
        {
            "role": "planner",
            "provider": "claude",
            "system_prompt": "",
            "tools": [],
        },
        "Plan the work.",
    )

    assert response == "Plan: keep launch health checks lightweight."
    assert [provider for provider, _ in attempts] == ["claude", "codex"]
    assert "FINAL RESPONSE CONTRACT" not in attempts[0][1]


def test_call_agent_cfg_stays_with_session_provider_pool(monkeypatch):
    attempts: list[str] = []

    def fake_call_agent(provider, prompt, system_prompt="", tools=None, **kwargs):
        attempts.append(provider)
        if provider == "gemini":
            raise GatewayInvocationError(
                provider=provider,
                agent_role=kwargs.get("agent_role"),
                profile_used="acc1",
                retries=0,
                gateway_error="gemini failed",
            )
        if provider == "codex":
            return "Counterpoint: shipping unchanged is risky."
        raise AssertionError(f"unexpected provider fallback: {provider}")

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    response = mode_base.call_agent_cfg(
        {
            "role": "proponent",
            "provider": "gemini",
            "system_prompt": "",
            "tools": [],
            "session_provider_pool": ["gemini", "codex"],
        },
        "Debate the project outlook.",
    )

    assert response == "Counterpoint: shipping unchanged is risky."
    assert attempts == ["gemini", "codex"]


def test_call_agent_cfg_uses_single_workspace_as_default_workdir(monkeypatch):
    captured: dict[str, object] = {}

    def fake_call_agent(provider, prompt, system_prompt="", tools=None, **kwargs):
        captured["provider"] = provider
        captured["workdir"] = kwargs.get("workdir")
        captured["workspace_paths"] = kwargs.get("workspace_paths")
        return "Opened the attached project."

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    response = mode_base.call_agent_cfg(
        {
            "role": "proponent",
            "provider": "claude",
            "system_prompt": "",
            "tools": [],
            "workspace_paths": ["/tmp/attached-project"],
        },
        "Inspect the repository.",
    )

    assert response == "Opened the attached project."
    assert captured["workdir"] == "/tmp/attached-project"
    assert captured["workspace_paths"] == ["/tmp/attached-project"]


def test_debate_prompts_include_workspace_context(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent, prompt):
        prompts.append((agent["role"], prompt))
        if agent["role"] == "judge":
            return f"{debate.CONTINUE_MARKER} Need one more round."
        return f"response from {agent['role']}"

    monkeypatch.setattr(debate, "call_agent_cfg", fake_call_agent_cfg)

    state = {
        "task": "Should we invest in the attached repo?",
        "agents": [
            {"role": "proponent", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/project"]},
            {"role": "opponent", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/project"]},
            {"role": "judge", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/project"]},
        ],
        "messages": [],
        "user_messages": [],
        "rounds": [],
        "current_round": 0,
        "max_rounds": 3,
        "verdict": "",
        "judge_action": "",
        "result": "",
    }

    pro_result = debate.proponent_argues(state)
    opp_state = {**state, "rounds": pro_result["rounds"], "messages": pro_result["messages"]}
    opp_result = debate.opponent_argues(opp_state)
    judge_state = {**opp_state, "rounds": opp_result["rounds"], "messages": [*pro_result["messages"], *opp_result["messages"]], "current_round": opp_result["current_round"]}
    debate.judge_decides(judge_state)

    assert [role for role, _ in prompts] == ["proponent", "opponent", "judge"]
    for _, prompt in prompts:
        assert "Your accessible project roots are:" in prompt
        assert "- /tmp/project" in prompt
        assert "resolve them relative to this root: /tmp/project" in prompt


def test_tournament_start_round_supports_byes():
    state = {
        "task": "Pick the strongest repo",
        "agents": [],
        "messages": [],
        "user_messages": [],
        "submissions": [
            {"role": "contestant_1", "provider": "claude", "workspace_paths": ["/tmp/a"], "project_label": "a"},
            {"role": "contestant_2", "provider": "codex", "workspace_paths": ["/tmp/b"], "project_label": "b"},
            {"role": "contestant_3", "provider": "gemini", "workspace_paths": ["/tmp/c"], "project_label": "c"},
        ],
        "bracket": [],
        "current_round": 0,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 5,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
    }

    result = tournament.start_round(state)

    assert result["current_round"] == 1
    assert len(result["bracket"]) == 1
    assert len(result["bracket"][0]) == 1
    assert result["winners"][0]["role"] == "contestant_3"
    assert result["current_match"]["a"]["role"] == "contestant_1"
    assert result["current_match"]["b"]["role"] == "contestant_2"


def test_tournament_start_round_supports_adaptive_pairing_and_repeat_avoidance():
    state = {
        "task": "Pick the strongest repo",
        "agents": [],
        "messages": [],
        "user_messages": [],
        "submissions": [
            {"role": "contestant_1", "provider": "claude", "workspace_paths": ["/tmp/a"], "project_label": "a"},
            {"role": "contestant_2", "provider": "codex", "workspace_paths": ["/tmp/b"], "project_label": "b"},
            {"role": "contestant_3", "provider": "gemini", "workspace_paths": ["/tmp/c"], "project_label": "c"},
            {"role": "contestant_4", "provider": "gemini", "workspace_paths": ["/tmp/d"], "project_label": "d"},
            {"role": "contestant_5", "provider": "codex", "workspace_paths": ["/tmp/e"], "project_label": "e"},
        ],
        "bracket": [],
        "config": {
            "pairing_strategy": "adaptive",
            "pairing_priors": {"a": 0.92, "b": 0.86, "c": 0.52, "d": 0.5, "e": 0.15},
        },
        "current_round": 0,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 5,
        "winners": [],
        "champion": {},
        "match_history": [
            {
                "a": {"project_label": "c", "workspace_paths": ["/tmp/c"]},
                "b": {"project_label": "d", "workspace_paths": ["/tmp/d"]},
            }
        ],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
    }

    result = tournament.start_round(state)

    assert result["current_round"] == 1
    assert result["winners"][0]["project_label"] == "a"
    assert len(result["bracket"]) == 1
    assert len(result["bracket"][0]) == 2
    first_pair = {
        result["current_match"]["a"]["project_label"],
        result["current_match"]["b"]["project_label"],
    }
    assert first_pair == {"b", "c"}
    second_pair = {
        result["bracket"][0][1]["a"]["project_label"],
        result["bracket"][0][1]["b"]["project_label"],
    }
    assert second_pair == {"d", "e"}


def test_tournament_start_round_uses_archive_cells_to_preserve_diversity():
    state = {
        "task": "Pick the strongest repo",
        "agents": [],
        "messages": [],
        "user_messages": [],
        "submissions": [
            {"role": "contestant_1", "provider": "claude", "workspace_paths": ["/tmp/a"], "project_label": "a"},
            {"role": "contestant_2", "provider": "codex", "workspace_paths": ["/tmp/b"], "project_label": "b"},
            {"role": "contestant_3", "provider": "gemini", "workspace_paths": ["/tmp/c"], "project_label": "c"},
            {"role": "contestant_4", "provider": "gemini", "workspace_paths": ["/tmp/d"], "project_label": "d"},
        ],
        "bracket": [],
        "config": {
            "pairing_strategy": "adaptive",
            "pairing_priors": {"a": 0.91, "b": 0.9, "c": 0.89, "d": 0.12},
            "pairing_archive_cells": {"a": "developer|low", "b": "developer|low", "c": "security|medium", "d": "ops|high"},
        },
        "current_round": 0,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 5,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
    }

    result = tournament.start_round(state)

    first_pair = {
        result["current_match"]["a"]["project_label"],
        result["current_match"]["b"]["project_label"],
    }
    assert first_pair == {"b", "c"}


def test_tournament_match_uses_multi_round_debate_and_judge_control(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent, prompt):
        prompts.append((agent["role"], prompt))
        if agent["role"] == "contestant_1":
            return "Project A wins on leverage."
        if agent["role"] == "contestant_2":
            return "Project B wins on risk control."
        if len([role for role, _ in prompts if role == "judge"]) == 1:
            return f"{tournament.NEED_MORE_ROUNDS_MARKER}\nBoth sides need one more concrete comparison."
        return f"{tournament.ADVANCE_MATCH_MARKER}: B\nWinner: B because the comparison stayed more concrete."

    monkeypatch.setattr(tournament, "call_agent_cfg", fake_call_agent_cfg)

    agents = [
        {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"]},
        {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"]},
        {"role": "judge", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": []},
    ]
    state = {
        "task": "Pick the strongest repo",
        "agents": agents,
        "messages": [],
        "user_messages": [],
        "submissions": [],
        "bracket": [],
        "current_round": 0,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 2,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
    }

    seeded = tournament.seed_contestants(state)
    round_state = {**state, "submissions": seeded["submissions"]}
    started = tournament.start_round(round_state)

    a1 = tournament.contestant_a_argues({**round_state, **started})
    b1_state = {**round_state, **started, **a1}
    b1 = tournament.contestant_b_argues(b1_state)
    j1_state = {**round_state, **started, **a1, **b1}
    j1 = tournament.judge_match(j1_state)

    assert j1["judge_action"] == "continue"
    assert "Both sides need one more concrete comparison." in j1["current_match"]["rounds"][-1]["judge_note"]

    a2_state = {**j1_state, **j1}
    a2 = tournament.contestant_a_argues(a2_state)
    b2_state = {**a2_state, **a2}
    b2 = tournament.contestant_b_argues(b2_state)
    j2_state = {**b2_state, **b2}
    j2 = tournament.judge_match(j2_state)
    advanced = tournament.advance_match({**j2_state, **j2})

    assert j2["judge_action"] == "advance"
    assert j2["match_winner"] == "B"
    assert advanced["winners"][0]["role"] == "contestant_2"
    assert advanced["advance_target"] == "crown_champion"
    assert any(role == "judge" and "Your accessible project roots are:" in prompt and "- /tmp/a" in prompt and "- /tmp/b" in prompt for role, prompt in prompts)


def test_tournament_judge_accepts_backticked_control_markers(monkeypatch):
    def fake_call_agent_cfg(agent, prompt):
        if agent["role"] == "contestant_1":
            return "Project A opening."
        if agent["role"] == "contestant_2":
            return "Project B opening."
        return "`ADVANCE_MATCH: B`\n\nWinner: B because the evidence is stronger."

    monkeypatch.setattr(tournament, "call_agent_cfg", fake_call_agent_cfg)

    state = {
        "task": "Pick the strongest repo",
        "agents": [
            {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"]},
            {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"]},
            {"role": "judge", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": []},
        ],
        "messages": [],
        "user_messages": [],
        "submissions": [],
        "bracket": [[{
            "a": {"role": "contestant_1", "provider": "claude", "workspace_paths": ["/tmp/a"], "project_label": "a"},
            "b": {"role": "contestant_2", "provider": "codex", "workspace_paths": ["/tmp/b"], "project_label": "b"},
        }]],
        "current_round": 1,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {
            "a": {"role": "contestant_1", "provider": "claude", "workspace_paths": ["/tmp/a"], "project_label": "a"},
            "b": {"role": "contestant_2", "provider": "codex", "workspace_paths": ["/tmp/b"], "project_label": "b"},
            "rounds": [],
            "winner": "",
            "verdict": "",
        },
        "max_rounds": 5,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
    }

    a1 = tournament.contestant_a_argues(state)
    b1 = tournament.contestant_b_argues({**state, **a1})
    judged = tournament.judge_match({**state, **a1, **b1})

    assert judged["judge_action"] == "advance"
    assert judged["match_winner"] == "B"
    assert judged["match_verdict"].startswith("Winner: B because the evidence is stronger.")


def test_tournament_parallel_stage_spawns_child_sessions_and_aggregates(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.sessions = {
                "sess_parent": {
                    "id": "sess_parent",
                    "status": "running",
                }
            }
            self.updates: list[tuple[str, dict]] = []

        def update(self, sid: str, **kwargs):
            self.updates.append((sid, kwargs))
            current = self.sessions.setdefault(sid, {"id": sid})
            current.update(kwargs)

        def get(self, sid: str):
            return self.sessions.get(sid)

    fake_store = FakeStore()
    spawn_calls: list[dict] = []

    async def fake_run(**kwargs):
        child_id = f"sess_child_{len(spawn_calls) + 1}"
        spawn_calls.append({"id": child_id, **kwargs})
        winner_token = "A" if len(spawn_calls) == 1 else "B"
        fake_store.sessions[child_id] = {
            "id": child_id,
            "status": "completed",
            "result": f"Winner: {winner_token}",
            "config": {
                "match_result": {
                    "winner_token": winner_token,
                    "verdict": f"Winner: {winner_token}",
                }
            },
            "parallel_label": kwargs.get("parallel_label"),
        }
        return child_id

    monkeypatch.setattr(engine, "run", fake_run)
    monkeypatch.setattr(engine, "request_cancel", lambda session_id: True)
    monkeypatch.setattr(tournament, "store", fake_store)

    state = {
        "session_id": "sess_parent",
        "mode": "tournament",
        "task": "Pick the strongest project",
        "agents": [
            {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"]},
            {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"]},
            {"role": "contestant_3", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/c"]},
            {"role": "contestant_4", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/d"]},
            {"role": "judge", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": []},
        ],
        "messages": [],
        "user_messages": [],
        "config": {"execution_mode": "parallel", "max_rounds": 3, "parallelism_limit": 2},
        "workspace_paths": [],
        "attached_tool_ids": [],
        "submissions": [],
        "bracket": [[
            {
                "a": {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"], "project_label": "a"},
                "b": {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"], "project_label": "b"},
            },
            {
                "a": {"role": "contestant_3", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/c"], "project_label": "c"},
                "b": {"role": "contestant_4", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/d"], "project_label": "d"},
            },
        ]],
        "current_round": 1,
        "current_stage_label": "QF",
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 3,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
        "parallel_stage_children": [],
        "parallel_stage_group_id": "",
    }

    result = asyncio.run(tournament.run_parallel_stage(state))

    assert [call["mode"] for call in spawn_calls] == ["tournament_match", "tournament_match"]
    assert all(call["parallel_parent_id"] == "sess_parent" for call in spawn_calls)
    assert result["advance_target"] == "start_round"
    assert [winner["role"] for winner in result["winners"]] == ["contestant_1", "contestant_4"]
    assert len(result["match_history"]) == 2
    assert fake_store.updates[-1][1]["parallel_progress"]["completed"] == 2


def test_tournament_parallel_stage_respects_parallelism_limit(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.sessions = {
                "sess_parent": {
                    "id": "sess_parent",
                    "status": "running",
                }
            }
            self.updates: list[tuple[str, dict]] = []

        def update(self, sid: str, **kwargs):
            self.updates.append((sid, kwargs))
            current = self.sessions.setdefault(sid, {"id": sid})
            current.update(kwargs)

        def get(self, sid: str):
            current = self.sessions.get(sid)
            if current and sid.startswith("sess_child_") and current.get("status") == "running":
                current["status"] = "completed"
                current["result"] = "Winner: A"
                current["config"] = {
                    "match_result": {
                        "winner_token": "A",
                        "verdict": "Winner: A",
                    }
                }
            return current

    fake_store = FakeStore()
    spawn_calls: list[dict] = []
    max_running_at_spawn = 0

    async def fake_run(**kwargs):
        nonlocal max_running_at_spawn
        child_id = f"sess_child_{len(spawn_calls) + 1}"
        running_now = sum(
            1
            for session_id, session in fake_store.sessions.items()
            if session_id.startswith("sess_child_") and session.get("status") == "running"
        )
        fake_store.sessions[child_id] = {
            "id": child_id,
            "status": "running",
            "parallel_label": kwargs.get("parallel_label"),
        }
        max_running_at_spawn = max(max_running_at_spawn, running_now + 1)
        spawn_calls.append({"id": child_id, **kwargs})
        return child_id

    monkeypatch.setattr(engine, "run", fake_run)
    monkeypatch.setattr(engine, "request_cancel", lambda session_id: True)
    monkeypatch.setattr(tournament, "store", fake_store)

    state = {
        "session_id": "sess_parent",
        "mode": "tournament",
        "task": "Pick the strongest project",
        "agents": [
            {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"]},
            {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"]},
            {"role": "contestant_3", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/c"]},
            {"role": "contestant_4", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/d"]},
            {"role": "contestant_5", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/e"]},
            {"role": "contestant_6", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/f"]},
            {"role": "judge", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": []},
        ],
        "messages": [],
        "user_messages": [],
        "config": {"execution_mode": "parallel", "max_rounds": 3, "parallelism_limit": 1},
        "workspace_paths": [],
        "attached_tool_ids": [],
        "submissions": [],
        "bracket": [[
            {
                "a": {"role": "contestant_1", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/a"], "project_label": "a"},
                "b": {"role": "contestant_2", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/b"], "project_label": "b"},
            },
            {
                "a": {"role": "contestant_3", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/c"], "project_label": "c"},
                "b": {"role": "contestant_4", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/d"], "project_label": "d"},
            },
            {
                "a": {"role": "contestant_5", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/e"], "project_label": "e"},
                "b": {"role": "contestant_6", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": ["/tmp/f"], "project_label": "f"},
            },
        ]],
        "current_round": 1,
        "current_stage_label": "QF",
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "max_rounds": 3,
        "winners": [],
        "champion": {},
        "match_history": [],
        "match_verdict": "",
        "judge_action": "",
        "match_winner": "",
        "advance_target": "",
        "result": "",
        "parallel_stage_children": [],
        "parallel_stage_group_id": "",
    }

    result = asyncio.run(tournament.run_parallel_stage(state))

    assert len(spawn_calls) == 3
    assert max_running_at_spawn == 1
    assert result["advance_target"] == "start_round"
    assert len(result["match_history"]) == 3
