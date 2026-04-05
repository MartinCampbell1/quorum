"""Regression coverage for the HITL inbox and review queue surfaces."""

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
def isolated_discovery_runtime(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_daemon_cache()
    clear_discovery_store_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_daemon_cache()
    clear_discovery_store_cache()


def _create_idea(title: str, summary: str, *, score: float = 0.82) -> dict:
    response = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": title,
            "summary": summary,
            "topic_tags": ["repo", "workflow", "founder"],
            "latest_scorecard": {"rank_score": score, "belief_score": max(0.55, score - 0.08)},
        },
    )
    assert response.status_code == 200
    return response.json()


def _seed_review_ready_idea(title: str) -> dict:
    idea = _create_idea(
        title,
        "A founder-facing workflow to turn repo and evidence signals into execution-ready opportunities.",
    )
    idea_id = idea["idea_id"]

    observation = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/langchain-ai/agent-inbox",
            "raw_text": "Founders need an approval inbox that shows evidence before the raw trace.",
            "topic_tags": ["inbox", "evidence", "workflow"],
            "pain_score": 0.71,
            "trend_score": 0.69,
            "evidence_confidence": "high",
        },
    )
    assert observation.status_code == 200

    report = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/validation-reports",
        json={
            "summary": "Debate verdict says the inbox-first flow is specific enough to ship.",
            "verdict": "pass",
            "findings": ["Need typed actions.", "Need dossier preview in the queue."],
            "confidence": "high",
        },
    )
    assert report.status_code == 200

    brief = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": f"{title} brief",
            "prd_summary": "Package the discovery approval queue as an inbox-first founder surface.",
            "acceptance_criteria": ["Queue review items", "Accept and edit actions", "Preview evidence"],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    )
    assert brief.status_code == 200

    simulation = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation",
        json={"persona_count": 12, "max_rounds": 3},
    )
    assert simulation.status_code == 200

    return client.get(f"/orchestrate/discovery/ideas/{idea_id}").json()


def test_inbox_feed_materializes_structured_review_queue():
    _seed_review_ready_idea("Inbox-native founder review")
    sibling = _create_idea(
        "Inbox-native founder review companion",
        "A related workflow for comparing approval candidates and evidence packs.",
        score=0.79,
    )
    client.post(
        f"/orchestrate/discovery/ideas/{sibling['idea_id']}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/paperclipai/paperclip",
            "raw_text": "Paperclip mixes approvals into a dashboard-first inbox feed.",
            "topic_tags": ["inbox", "workflow", "dashboard"],
            "pain_score": 0.68,
            "trend_score": 0.64,
            "evidence_confidence": "medium",
        },
    )

    response = client.get("/orchestrate/discovery/inbox?limit=20&status=open")
    assert response.status_code == 200
    payload = response.json()

    kinds = {item["kind"] for item in payload["items"]}
    assert {"idea_review", "debate_review", "simulation_review", "handoff_review"}.issubset(kinds)
    assert payload["summary"]["open_count"] >= 4
    assert payload["summary"]["action_required_count"] >= 4

    handoff_item = next(item for item in payload["items"] if item["kind"] == "handoff_review")
    assert handoff_item["subject_kind"] == "handoff"
    assert handoff_item["interrupt"]["config"]["allow_accept"] is True
    assert handoff_item["interrupt"]["config"]["allow_edit"] is True
    assert handoff_item["dossier_preview"]["evidence"]["observations"]
    assert handoff_item["dossier_preview"]["compare_options"]


def test_inbox_actions_record_history_and_dossier_events():
    primary = _seed_review_ready_idea("Approval queue for founder OS")
    compare_target = _create_idea(
        "Approval queue for founder OS companion",
        "A companion idea to compare queue posture and evidence density.",
        score=0.77,
    )
    client.post(
        f"/orchestrate/discovery/ideas/{compare_target['idea_id']}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/4regab/TaskSync",
            "raw_text": "TaskSync keeps queued prompts editable instead of dropping them on interrupt.",
            "topic_tags": ["workflow", "queue", "founder"],
            "pain_score": 0.63,
            "trend_score": 0.58,
            "evidence_confidence": "medium",
        },
    )

    feed = client.get("/orchestrate/discovery/inbox?limit=20&status=open").json()
    handoff_item = next(item for item in feed["items"] if item["kind"] == "handoff_review" and item["idea_id"] == primary["idea_id"])

    compare_response = client.post(
        f"/orchestrate/discovery/inbox/{handoff_item['item_id']}/act",
        json={
            "action": "compare",
            "actor": "founder",
            "note": "Compare against the companion queue idea before approving.",
            "compare_target_idea_id": compare_target["idea_id"],
        },
    )
    assert compare_response.status_code == 200
    assert compare_response.json()["status"] == "open"
    assert compare_response.json()["review_history"][-1]["action"] == "compare"

    accept_response = client.post(
        f"/orchestrate/discovery/inbox/{handoff_item['item_id']}/act",
        json={
            "action": "accept",
            "actor": "founder",
            "note": "Ship this execution brief next.",
        },
    )
    assert accept_response.status_code == 200
    accepted = accept_response.json()
    assert accepted["status"] == "resolved"
    assert accepted["resolution"]["action"] == "accept"

    dossier = client.get(f"/orchestrate/discovery/ideas/{primary['idea_id']}/dossier").json()
    assert any(decision["decision_type"] == "inbox_compare" for decision in dossier["decisions"])
    assert any(decision["decision_type"] == "inbox_accept" for decision in dossier["decisions"])
    assert any(event["title"] == "Inbox review accepted" for event in dossier["timeline"])


def test_inbox_edit_and_respond_actions_apply_changes():
    idea = _seed_review_ready_idea("Editable founder brief lane")
    feed = client.get("/orchestrate/discovery/inbox?limit=20&status=open").json()
    idea_item = next(item for item in feed["items"] if item["kind"] == "idea_review" and item["idea_id"] == idea["idea_id"])

    edit_response = client.post(
        f"/orchestrate/discovery/inbox/{idea_item['item_id']}/act",
        json={
            "action": "edit",
            "actor": "founder",
            "note": "Tighten the queue summary before review.",
            "edited_fields": {"summary": "FounderOS now surfaces a typed review inbox with evidence preview first."},
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["status"] == "resolved"

    updated_idea = client.get(f"/orchestrate/discovery/ideas/{idea['idea_id']}").json()
    assert updated_idea["summary"] == "FounderOS now surfaces a typed review inbox with evidence preview first."

    feed = client.get("/orchestrate/discovery/inbox?limit=20&status=open").json()
    debate_item = next(item for item in feed["items"] if item["kind"] == "debate_review" and item["idea_id"] == idea["idea_id"])
    respond_response = client.post(
        f"/orchestrate/discovery/inbox/{debate_item['item_id']}/act",
        json={
            "action": "respond",
            "actor": "founder",
            "note": "Keep the dissent path visible in the final UI.",
            "response_text": "Keep the dissent path visible in the final UI.",
        },
    )
    assert respond_response.status_code == 200
    assert respond_response.json()["resolution"]["action"] == "respond"

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea['idea_id']}/dossier").json()
    assert any(decision["decision_type"] == "inbox_edit" for decision in dossier["decisions"])
    assert any(decision["decision_type"] == "inbox_respond" for decision in dossier["decisions"])
