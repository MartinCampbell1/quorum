"""Regression coverage for swipe queue and preference learning routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.models import SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_preference_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()


def test_swipe_queue_learns_preferences_and_rechecks_maybe_items():
    core_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Approval workflow copilot",
            "summary": "Turn repo evidence into approval-routing opportunities.",
            "source": "github",
            "topic_tags": ["workflow-automation", "developer-tools", "b2b", "ai"],
            "provenance": {
                "repo_dna_profile": {
                    "domain_clusters": ["workflow-automation", "developer-tools"],
                    "preferred_complexity": "high",
                    "idea_generation_context": "Repo history keeps circling back to approval flows.",
                }
            },
            "latest_scorecard": {"rank_score": 0.82, "belief_score": 0.74},
        },
    ).json()
    secondary_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Consumer pantry planner",
            "summary": "A lighter B2C planning idea for recipe discovery.",
            "source": "manual",
            "topic_tags": ["consumer", "b2c"],
            "latest_scorecard": {"rank_score": 0.35, "belief_score": 0.31},
        },
    ).json()

    observation_response = client.post(
        f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/example/approval-workflows",
            "raw_text": "Approval queue failures and agent handoff latency show up repeatedly in this repo history.",
            "topic_tags": ["workflow", "approval"],
            "pain_score": 0.77,
            "trend_score": 0.71,
            "evidence_confidence": "high",
        },
    )
    assert observation_response.status_code == 200

    queue_response = client.get("/orchestrate/discovery/swipe-queue?limit=10")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    queue_ids = {item["idea"]["idea_id"] for item in queue_payload["items"]}
    assert core_idea["idea_id"] in queue_ids
    assert secondary_idea["idea_id"] in queue_ids
    assert queue_payload["preference_profile"]["swipe_count"] == 0

    swipe_response = client.post(
        f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/swipe",
        json={
            "action": "maybe",
            "rationale": "Hold for follow-up evidence before promoting it.",
            "actor": "founder",
            "revisit_after_hours": 999,
        },
    )
    assert swipe_response.status_code == 200
    swipe_payload = swipe_response.json()
    assert swipe_payload["decision"]["decision_type"] == "maybe"
    assert swipe_payload["maybe_entry"]["idea_id"] == core_idea["idea_id"]
    assert swipe_payload["preference_profile"]["domain_weights"]["workflow-automation"] > 0
    assert swipe_payload["preference_profile"]["buyer_preferences"]["b2b"] > 0

    maybe_queue = client.get("/orchestrate/discovery/maybe-queue?limit=10")
    assert maybe_queue.status_code == 200
    maybe_payload = maybe_queue.json()
    assert maybe_payload["summary"]["total_count"] == 1
    assert maybe_payload["summary"]["ready_count"] == 0
    assert maybe_payload["summary"]["waiting_count"] == 1

    followup_observation = client.post(
        f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/observations",
        json={
            "source": "reddit",
            "entity": "thread",
            "url": "https://reddit.com/r/startups/example",
            "raw_text": "Founders keep saying approval handoffs are still a painful dead-end in existing stacks.",
            "topic_tags": ["handoff", "approval"],
            "pain_score": 0.82,
            "trend_score": 0.66,
            "evidence_confidence": "medium",
        },
    )
    assert followup_observation.status_code == 200

    maybe_queue_after = client.get("/orchestrate/discovery/maybe-queue?limit=10")
    assert maybe_queue_after.status_code == 200
    maybe_after_payload = maybe_queue_after.json()
    assert maybe_after_payload["summary"]["ready_count"] == 1
    assert maybe_after_payload["items"][0]["has_new_evidence"] is True
    assert maybe_after_payload["items"][0]["recheck_status"] == "ready"

    changes_response = client.get(f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/changes")
    assert changes_response.status_code == 200
    changes_payload = changes_response.json()
    assert any("new evidence" in item.lower() for item in changes_payload["summary_points"])
    assert len(changes_payload["new_observations"]) == 1

    revived_queue = client.get("/orchestrate/discovery/swipe-queue?limit=10")
    assert revived_queue.status_code == 200
    revived_ids = {item["idea"]["idea_id"] for item in revived_queue.json()["items"]}
    assert core_idea["idea_id"] in revived_ids

    preferences = client.get("/orchestrate/discovery/preferences")
    assert preferences.status_code == 200
    profile_payload = preferences.json()
    assert profile_payload["swipe_count"] == 1
    assert profile_payload["action_counts"]["maybe"] == 1
    assert profile_payload["ai_necessity_preference"] > 0.5

    decisive_swipe = client.post(
        f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/swipe",
        json={"action": "yes", "rationale": "The new evidence is enough to promote it."},
    )
    assert decisive_swipe.status_code == 200

    maybe_queue_cleared = client.get("/orchestrate/discovery/maybe-queue?limit=10")
    assert maybe_queue_cleared.status_code == 200
    assert maybe_queue_cleared.json()["summary"]["total_count"] == 0

    dossier = client.get(f"/orchestrate/discovery/ideas/{core_idea['idea_id']}/dossier").json()
    assert dossier["idea"]["swipe_state"] == "yes"
    assert len(dossier["decisions"]) == 2
