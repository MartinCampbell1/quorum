"""Regression coverage for the MVP virtual-user simulation lane."""

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
def isolated_discovery_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()


def test_virtual_user_simulation_run_is_persisted_and_reused():
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Repo-aware founder workflow monitor",
            "summary": "Turn founder repo activity into ranked product opportunities and launch briefs.",
            "topic_tags": ["repo", "workflow", "ranking", "evidence"],
            "latest_scorecard": {"rank_score": 0.81, "belief_score": 0.72},
        },
    ).json()
    idea_id = idea["idea_id"]

    client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/microsoft/TinyTroupe",
            "raw_text": "Operators want a cheaper way to pressure-test workflow pain before building.",
            "topic_tags": ["simulation", "operators"],
            "pain_score": 0.66,
            "trend_score": 0.61,
            "evidence_confidence": "high",
        },
    )

    client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Workflow monitor MVP",
            "prd_summary": "Validate repo-driven founder opportunities before handoff.",
            "acceptance_criteria": ["Run simulation", "Store verdict"],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    )

    run_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation",
        json={"persona_count": 12, "max_rounds": 3},
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["cached"] is False
    assert payload["idea"]["simulation_state"] == "complete"
    assert payload["idea"]["latest_stage"] == "simulated"
    assert payload["report"]["run"]["persona_count"] == 12
    assert payload["report"]["run"]["estimated_cost_usd"] > 0
    assert len(payload["report"]["personas"]) == 12
    assert len(payload["report"]["run"]["rounds"]) == 3
    assert payload["report"]["verdict"] in {"watch", "pilot", "advance", "reject"}

    fetch_response = client.get(f"/orchestrate/discovery/ideas/{idea_id}/simulation")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["report_id"] == payload["report"]["report_id"]

    cached_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation",
        json={"persona_count": 12, "max_rounds": 3},
    )
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True
    assert cached_response.json()["report"]["report_id"] == payload["report"]["report_id"]

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert dossier["simulation_report"]["report_id"] == payload["report"]["report_id"]
    assert dossier["execution_brief_candidate"]["simulation_summary"] == payload["report"]["summary_headline"]
    assert any(event["title"] == "Virtual focus group completed" for event in dossier["timeline"])
