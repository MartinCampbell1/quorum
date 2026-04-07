"""Regression coverage for the full market-sandbox simulation lab."""

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


def test_market_simulation_run_persists_report_and_updates_scorecard():
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Operator-grade repo signal monitor",
            "summary": "Convert founder repo activity into ranked product signals and execution briefs.",
            "description": "An ops-heavy workflow tool that shortens triage and prioritization loops.",
            "topic_tags": ["repo", "ops", "workflow", "automation"],
            "latest_scorecard": {"rank_score": 0.63, "belief_score": 0.58},
        },
    ).json()
    idea_id = idea["idea_id"]

    client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/google-deepmind/concordia",
            "raw_text": "Ops leads want a bounded environment to validate adoption before build approval.",
            "topic_tags": ["simulation", "ops"],
            "pain_score": 0.71,
            "trend_score": 0.63,
            "evidence_confidence": "high",
        },
    )
    client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Operator-grade repo signal monitor",
            "prd_summary": "Validate demand and adoption before build approval.",
            "acceptance_criteria": ["Store dossier", "Store simulation report"],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    )

    focus_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation",
        json={"persona_count": 12, "max_rounds": 3},
    )
    assert focus_response.status_code == 200

    run_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation/lab",
        json={"population_size": 60, "round_count": 4, "competition_pressure": 0.39, "network_density": 0.44},
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["cached"] is False
    assert payload["idea"]["latest_stage"] == "simulated"
    assert payload["report"]["parameters"]["population_size"] == 60
    assert payload["report"]["run_state"]["status"] == "completed"
    assert len(payload["report"]["run_state"]["round_summaries"]) == 4
    assert payload["report"]["market_fit_score"] >= 0
    assert payload["report"]["build_priority_score"] >= 0
    assert "rank_score_delta" in payload["report"]["ranking_delta"]
    assert "belief_score_delta" in payload["report"]["ranking_delta"]

    get_response = client.get(f"/orchestrate/discovery/ideas/{idea_id}/simulation/lab")
    assert get_response.status_code == 200
    assert get_response.json()["report_id"] == payload["report"]["report_id"]

    cached_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/simulation/lab",
        json={"population_size": 60, "round_count": 4},
    )
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert dossier["market_simulation_report"]["report_id"] == payload["report"]["report_id"]
    assert dossier["execution_brief_candidate"]["simulation_summary"] == payload["report"]["executive_summary"]
    assert dossier["idea"]["latest_scorecard"]["simulation_build_priority_score"] == payload["report"]["build_priority_score"]
    assert dossier["idea"]["rank_score"] != pytest.approx(0.63)
    assert dossier["idea"]["belief_score"] != pytest.approx(0.58)
    assert any(event["title"] == "Market sandbox completed" for event in dossier["timeline"])
