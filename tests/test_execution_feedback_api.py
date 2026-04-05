"""Regression coverage for execution feedback flowing back from Autopilot."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.execution_feedback import clear_execution_feedback_service_cache
from orchestrator.handoff import clear_handoff_service_cache
from orchestrator.memory_graph import clear_memory_graph_service_cache
from orchestrator.models import SessionStore
from orchestrator.shared_contracts import (
    ExecutionOutcomeBundle,
    IdeaOutcomeStatus,
    VerdictStatus,
    to_jsonable,
)


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_discovery_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_handoff_service_cache()
    clear_execution_feedback_service_cache()
    clear_memory_graph_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_memory_graph_service_cache()
    clear_execution_feedback_service_cache()
    clear_handoff_service_cache()
    clear_discovery_store_cache()


def _seed_handoff_ready_idea() -> dict[str, str]:
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Repo execution scorekeeper",
            "summary": "Carry real shipping outcomes back into the founder discovery loop.",
            "source": "github",
            "topic_tags": ["repo", "execution", "workflow", "ops"],
        },
    ).json()
    idea_id = idea["idea_id"]

    client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/validation-reports",
        json={
            "summary": "The execution loop is concrete enough to ship and measure.",
            "verdict": "pass",
            "findings": ["Autopilot must return execution verdicts to discovery."],
            "confidence": "high",
        },
    )
    brief = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Repo execution scorekeeper MVP",
            "prd_summary": "Ingest shipped outcomes, costs, and lessons into discovery dossiers.",
            "acceptance_criteria": ["Store execution outcomes", "Re-score belief from shipping"],
            "recommended_tech_stack": ["FastAPI", "SQLite"],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    ).json()
    return {"idea_id": idea_id, "brief_id": brief["brief_id"]}


def test_execution_feedback_updates_dossier_scores_and_autopilot_linkage():
    seeded = _seed_handoff_ready_idea()
    idea_id = seeded["idea_id"]
    brief_id = seeded["brief_id"]

    schema = client.get("/orchestrate/discovery/execution-feedback/schema")
    assert schema.status_code == 200
    assert schema.json()["title"] == "ExecutionOutcomeBundle"

    with patch(
        "orchestrator.api._send_brief_to_autopilot",
        new=AsyncMock(
            return_value={
                "status": "ok",
                "project_id": "proj_exec_123",
                "project_name": "Repo execution scorekeeper MVP",
                "project_path": "/tmp/autopilot/repo-exec-scorekeeper",
                "launched": True,
            }
        ),
    ):
        sent = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
            json={"launch": True, "priority": "high"},
        )
    assert sent.status_code == 200

    outcome = ExecutionOutcomeBundle(
        outcome_id="outcome_exec_123",
        brief_id=brief_id,
        idea_id=idea_id,
        status=IdeaOutcomeStatus.VALIDATED,
        verdict=VerdictStatus.PASS,
        total_cost_usd=1840.0,
        total_duration_seconds=4 * 86_400.0,
        stories_attempted=4,
        stories_passed=3,
        stories_failed=1,
        bugs_found=1,
        critic_pass_rate=0.76,
        shipped_artifacts=["/dashboard/scoreboard", "/api/discovery/execution-feedback"],
        failure_modes=["Approval loop slowed the first deploy"],
        lessons_learned=["Keep the first execution slice narrow and instrumented"],
    )
    response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-feedback",
        json={
            "outcome": to_jsonable(outcome),
            "actor": "autopilot",
            "approvals_count": 2,
            "shipped_experiment_count": 1,
            "autopilot_payload": {
                "project_id": "proj_exec_123",
                "project_name": "Repo execution scorekeeper MVP",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["outcome"]["status"] == "validated"
    assert payload["idea"]["latest_stage"] == "executed"
    assert payload["idea"]["validation_state"] == "validated"
    assert payload["idea"]["belief_score"] > 0.0
    assert payload["preference_profile"]["domain_weights"]["execution"] > 0.0

    listed = client.get(f"/orchestrate/discovery/ideas/{idea_id}/execution-feedback?limit=5")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["outcome_id"] == "outcome_exec_123"

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert dossier["idea"]["provenance"]["autopilot"]["project_id"] == "proj_exec_123"
    assert dossier["idea"]["provenance"]["execution_feedback"]["status"] == "validated"
    assert len(dossier["execution_outcomes"]) == 1
    assert dossier["execution_outcomes"][0]["approvals_count"] == 2
    assert dossier["execution_outcomes"][0]["shipped_experiment_count"] == 1
    assert dossier["idea"]["latest_scorecard"]["execution_total_cost_usd"] == pytest.approx(1840.0)
    assert dossier["idea"]["latest_scorecard"]["execution_approval_score"] > 0.0
    assert any(decision["decision_type"] == "execution_feedback_validated" for decision in dossier["decisions"])
    assert any(event["title"] == "Execution outcome: validated" for event in dossier["timeline"])


def test_execution_feedback_pushes_shipping_lessons_into_memory_queries():
    seeded = _seed_handoff_ready_idea()
    idea_id = seeded["idea_id"]
    brief_id = seeded["brief_id"]

    outcome = ExecutionOutcomeBundle(
        outcome_id="outcome_exec_mem",
        brief_id=brief_id,
        idea_id=idea_id,
        status=IdeaOutcomeStatus.COST_TRAP,
        verdict=VerdictStatus.PARTIAL,
        total_cost_usd=6400.0,
        total_duration_seconds=12 * 86_400.0,
        stories_attempted=3,
        stories_passed=1,
        stories_failed=2,
        bugs_found=3,
        critic_pass_rate=0.34,
        shipped_artifacts=["/prototype/insights"],
        failure_modes=["Approval loop blocked deployment", "Scope creep broke the first release"],
        lessons_learned=["Constrain approval surfaces before scaling execution"],
    )
    feedback = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-feedback",
        json={
            "outcome": to_jsonable(outcome),
            "approvals_count": 4,
            "shipped_experiment_count": 1,
            "autopilot_payload": {"project_id": "proj_cost_1"},
        },
    )
    assert feedback.status_code == 200

    rebuilt = client.post("/orchestrate/discovery/memory/rebuild")
    assert rebuilt.status_code == 200
    memory = rebuilt.json()
    assert any(episode["kind"] == "execution_feedback" for episode in memory["episodes"])

    query = client.post(
        "/orchestrate/discovery/memory/query",
        json={"query": "approval loop scope creep execution", "limit": 6},
    )
    assert query.status_code == 200
    query_payload = query.json()
    assert idea_id in query_payload["related_idea_ids"]
    assert any(match["kind"] == "episode" for match in query_payload["matches"])

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier")
    assert dossier.status_code == 200
    assert dossier.json()["memory_context"]["related_episode_ids"]
