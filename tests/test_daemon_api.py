"""Regression coverage for discovery daemon routines and daily digest surfaces."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.daemon import clear_discovery_daemon_cache
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.models import SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_daemon_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_discovery_daemon_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_daemon_cache()
    clear_discovery_store_cache()


def _create_idea(title: str, rank_score: float, belief_score: float, *, swipe_state: str = "unseen") -> dict:
    response = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": title,
            "summary": f"{title} summary",
            "topic_tags": ["daemon", "discovery"],
            "latest_scorecard": {"rank_score": rank_score, "belief_score": belief_score},
        },
    )
    assert response.status_code == 200
    idea = response.json()
    patch = client.patch(
        f"/orchestrate/discovery/ideas/{idea['idea_id']}",
        json={"swipe_state": swipe_state},
    )
    assert patch.status_code == 200
    return patch.json()


def test_daily_digest_routine_writes_digest_inbox_and_dossier_timeline():
    first = _create_idea("Founder repo daemon", 0.86, 0.74, swipe_state="yes")
    _create_idea("Async ICP refresh loop", 0.78, 0.63)

    response = client.post(
        "/orchestrate/discovery/daemon/control",
        json={"action": "run_routine", "routine_kind": "daily_digest"},
    )
    assert response.status_code == 200
    assert response.json()["recent_runs"][0]["routine_kind"] == "daily_digest"

    digests = client.get("/orchestrate/discovery/daemon/digests?limit=5")
    assert digests.status_code == 200
    payload = digests.json()["items"]
    assert payload
    assert payload[0]["headline"].startswith("Daily discovery digest")
    assert any(item["title"] == "Founder repo daemon" for item in payload[0]["top_ideas"])

    inbox = client.get("/orchestrate/discovery/inbox?limit=10&status=open")
    assert inbox.status_code == 200
    assert any(item["kind"] == "daily_digest" for item in inbox.json()["items"])

    dossier = client.get(f"/orchestrate/discovery/ideas/{first['idea_id']}/dossier")
    assert dossier.status_code == 200
    assert any(event["title"] == "Included in daily digest" for event in dossier.json()["timeline"])


def test_hourly_refresh_updates_freshness_and_creates_review_inbox_item():
    idea = _create_idea("Stale discovery thread", 0.69, 0.58, swipe_state="maybe")
    old_refresh = (datetime.now(UTC) - timedelta(hours=18)).isoformat()
    patch = client.patch(
        f"/orchestrate/discovery/ideas/{idea['idea_id']}",
        json={"last_evidence_refresh_at": old_refresh},
    )
    assert patch.status_code == 200

    response = client.post(
        "/orchestrate/discovery/daemon/control",
        json={"action": "run_routine", "routine_kind": "hourly_refresh"},
    )
    assert response.status_code == 200

    updated = client.get(f"/orchestrate/discovery/ideas/{idea['idea_id']}")
    assert updated.status_code == 200
    assert updated.json()["last_evidence_refresh_at"] != old_refresh

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea['idea_id']}/dossier").json()
    assert any(event["title"] == "Daemon hourly refresh" for event in dossier["timeline"])

    inbox = client.get("/orchestrate/discovery/inbox?limit=20&status=open").json()["items"]
    assert any(item["kind"] == "refresh_review" and item["idea_id"] == idea["idea_id"] for item in inbox)


def test_overnight_queue_respects_budget_and_persists_checkpoints():
    _create_idea("Queue alpha", 0.81, 0.71, swipe_state="yes")
    _create_idea("Queue beta", 0.77, 0.67)
    _create_idea("Queue gamma", 0.73, 0.64)

    response = client.post(
        "/orchestrate/discovery/daemon/control",
        json={"action": "run_routine", "routine_kind": "overnight_queue"},
    )
    assert response.status_code == 200

    status = client.get("/orchestrate/discovery/daemon/status")
    assert status.status_code == 200
    overnight_run = next(item for item in status.json()["recent_runs"] if item["routine_kind"] == "overnight_queue")
    assert overnight_run["budget_used_usd"] <= 1.8
    assert len(overnight_run["checkpoints"]) >= 1

    inbox = client.get("/orchestrate/discovery/inbox?limit=20&status=open").json()["items"]
    assert any(item["kind"] == "overnight_queue" for item in inbox)


def test_daemon_status_emits_stale_worker_alert():
    service = orchestrator_api._daemon_service()
    state = service._load_state()
    state.mode = "running"
    state.worker_heartbeat_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=12)
    service._db.save_state(state)

    response = client.get("/orchestrate/discovery/daemon/status")
    assert response.status_code == 200
    assert any(item["code"] == "stale_worker" for item in response.json()["alerts"])
