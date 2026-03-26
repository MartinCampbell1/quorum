"""Regression coverage for the remediation pass.

This file locks in the removal of hidden minimax arbitration and the parallel
chunk-processing contract for map_reduce.
"""

import asyncio
import time

import orchestrator.modes.board as board
import orchestrator.modes.democracy as democracy
import orchestrator.modes.map_reduce as map_reduce


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
