"""Regression coverage for backend restart recovery of in-memory runtime state."""

import time

from orchestrator.engine import CHECKPOINT_SAVERS, _prune_checkpoint_savers, reconcile_orphaned_sessions
from orchestrator.models import AgentConfig, store


def test_reconcile_orphaned_sessions_marks_transient_runs_terminal():
    running_id = store.create(
        "dictator",
        "Running before restart",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    cancelling_id = store.create(
        "dictator",
        "Cancelling before restart",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    paused_id = store.create(
        "creator_critic",
        "Paused checkpoint session",
        [
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        {},
    )

    store.update(running_id, status="running")
    store.update(cancelling_id, status="cancel_requested")
    store.update(paused_id, status="paused")

    recovered = reconcile_orphaned_sessions()

    assert recovered >= 2

    running = store.get(running_id)
    cancelling = store.get(cancelling_id)
    paused = store.get(paused_id)

    assert running["status"] == "failed"
    assert "backend restart" in (running["result"] or "").lower()
    assert any(event["type"] == "runtime_recovered" for event in running["events"])

    assert cancelling["status"] == "cancelled"
    assert any(event["type"] == "runtime_recovered" for event in cancelling["events"])

    assert paused["status"] == "paused"


def test_checkpoint_runtime_cache_prunes_stale_sessions():
    snapshot = dict(CHECKPOINT_SAVERS)
    CHECKPOINT_SAVERS.clear()
    try:
        first_id = store.create(
            "dictator",
            "Older checkpoint cache",
            [
                AgentConfig(role="director", provider="claude", tools=[]),
                AgentConfig(role="worker", provider="codex", tools=[]),
            ],
            {},
        )
        time.sleep(0.01)
        second_id = store.create(
            "dictator",
            "Middle checkpoint cache",
            [
                AgentConfig(role="director", provider="claude", tools=[]),
                AgentConfig(role="worker", provider="codex", tools=[]),
            ],
            {},
        )
        time.sleep(0.01)
        third_id = store.create(
            "dictator",
            "Newest checkpoint cache",
            [
                AgentConfig(role="director", provider="claude", tools=[]),
                AgentConfig(role="worker", provider="codex", tools=[]),
            ],
            {},
        )

        CHECKPOINT_SAVERS[first_id] = object()
        CHECKPOINT_SAVERS[second_id] = object()
        CHECKPOINT_SAVERS[third_id] = object()

        _prune_checkpoint_savers(limit=2)

        assert first_id not in CHECKPOINT_SAVERS
        assert second_id in CHECKPOINT_SAVERS
        assert third_id in CHECKPOINT_SAVERS
    finally:
        CHECKPOINT_SAVERS.clear()
        CHECKPOINT_SAVERS.update(snapshot)
