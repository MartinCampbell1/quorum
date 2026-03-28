"""Regression coverage for the remediation pass.

This file locks in the removal of hidden minimax arbitration and the parallel
chunk-processing contract for map_reduce.
"""

import asyncio
import time

import orchestrator.modes.board as board
import orchestrator.modes.base as mode_base
import orchestrator.modes.democracy as democracy
import orchestrator.modes.map_reduce as map_reduce
import pytest

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

    assert result["consensus_reached"] is True
    assert result["decision"] == "Deploy on Monday"
    assert result["messages"][0]["phase"] == "consensus_check"


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
    assert [provider for provider, _, _ in attempts] == ["claude", "gemini"]
    assert "FINAL RESPONSE CONTRACT" in attempts[0][2]


def test_call_agent_cfg_does_not_retry_noncritical_roles(monkeypatch):
    attempts: list[str] = []

    def fake_call_agent(provider, prompt, system_prompt="", tools=None, **kwargs):
        attempts.append(provider)
        raise GatewayInvocationError(
            provider=provider,
            agent_role=kwargs.get("agent_role"),
            profile_used="acc1",
            retries=0,
            gateway_error="provider failed",
        )

    monkeypatch.setattr(mode_base, "call_agent", fake_call_agent)

    with pytest.raises(GatewayInvocationError):
        mode_base.call_agent_cfg(
            {
                "role": "planner",
                "provider": "claude",
                "system_prompt": "",
                "tools": [],
            },
            "Plan the work.",
        )

    assert attempts == ["claude"]
