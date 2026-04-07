"""Regression coverage for discovery-store API routes."""

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


def test_discovery_idea_round_trip_and_dossier_view():
    create_response = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Founder repo signal miner",
            "summary": "Build structured opportunity dossiers from a founder's repos.",
            "source": "github",
            "topic_tags": ["repo", "founder", "discovery"],
            "latest_scorecard": {"rank_score": 0.74, "belief_score": 0.68},
        },
    )

    assert create_response.status_code == 200
    idea = create_response.json()
    assert idea["idea_id"].startswith("idea_")
    assert idea["rank_score"] == pytest.approx(0.74)
    assert idea["belief_score"] == pytest.approx(0.68)

    list_response = client.get("/orchestrate/discovery/ideas")
    assert list_response.status_code == 200
    listed = list_response.json()["ideas"]
    assert len(listed) == 1
    assert listed[0]["idea_id"] == idea["idea_id"]

    dossier_response = client.get(f"/orchestrate/discovery/ideas/{idea['idea_id']}/dossier")
    assert dossier_response.status_code == 200
    dossier = dossier_response.json()
    assert dossier["idea"]["idea_id"] == idea["idea_id"]
    assert dossier["timeline"][0]["stage"] == "sourced"


def test_discovery_supports_observations_reports_decisions_and_brief_candidates():
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={"title": "Typed startup thesis store"},
    ).json()
    idea_id = idea["idea_id"]

    observation_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/cyclotruc/gitingest",
            "raw_text": "Repository packaging flows and compact repo digestion are highly reusable here.",
            "topic_tags": ["digest", "repo"],
            "pain_score": 0.61,
            "trend_score": 0.72,
            "evidence_confidence": "high",
        },
    )
    assert observation_response.status_code == 200

    report_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/validation-reports",
        json={
            "summary": "The founder workflow is concrete enough for a typed dossier MVP.",
            "verdict": "pass",
            "findings": ["Stable IDs are required.", "Need provenance for every observation."],
            "confidence": "high",
        },
    )
    assert report_response.status_code == 200

    decision_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/decisions",
        json={
            "decision_type": "yes",
            "rationale": "The evidence density justifies keeping this in the active queue.",
            "actor": "founder",
        },
    )
    assert decision_response.status_code == 200

    evidence_response = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/evidence-bundle",
        json={
            "items": [
                {
                    "kind": "source_observation",
                    "summary": "GitHub donor confirms compact repo digest pattern.",
                    "source": "github",
                    "confidence": "high",
                    "tags": ["repo", "digest"],
                }
            ],
            "overall_confidence": "high",
        },
    )
    assert evidence_response.status_code == 200

    brief_response = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Discovery store MVP",
            "prd_summary": "Persist ideas, evidence, lineage, and a typed handoff candidate.",
            "acceptance_criteria": ["List ideas", "Read dossier", "Archive ideas"],
            "risks": [
                {
                    "category": "technical",
                    "description": "Discovery store drifts from shared contract fields.",
                    "level": "medium",
                    "mitigation": "Keep shared contracts in a dedicated module.",
                }
            ],
            "recommended_tech_stack": ["FastAPI", "SQLite", "Next.js"],
            "first_stories": [
                {
                    "title": "Discovery tables",
                    "description": "Persist ideas and related evidence.",
                    "acceptance_criteria": ["SQLite tables exist", "Routes return typed JSON"],
                    "effort": "small",
                }
            ],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    )
    assert brief_response.status_code == 200

    archive_response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/archive",
        json={"reason": "Merged into a broader discovery-portfolio epic."},
    )
    assert archive_response.status_code == 200

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert len(dossier["observations"]) == 1
    assert len(dossier["validation_reports"]) == 1
    assert len(dossier["decisions"]) == 1
    assert len(dossier["archive_entries"]) == 1
    assert dossier["evidence_bundle"]["overall_confidence"] == "high"
    assert dossier["execution_brief_candidate"]["title"] == "Discovery store MVP"
    assert dossier["execution_brief_candidate"]["brief_approval_status"] == "pending"
    assert dossier["execution_brief_candidate"]["revision_id"].startswith("brief_rev_")
    assert dossier["idea"]["validation_state"] == "archived"
    assert dossier["idea"]["swipe_state"] == "yes"
    assert any(event["title"] == "Execution brief drafted" for event in dossier["timeline"])


def test_material_brief_candidate_edit_resets_approval_and_bumps_revision():
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={"title": "Approval reset regression"},
    ).json()
    idea_id = idea["idea_id"]

    create = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={"title": "Approval reset regression brief"},
    )
    assert create.status_code == 200
    created = create.json()

    export = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/export",
        json={"persist_candidate": True},
    )
    assert export.status_code == 200
    created = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()["execution_brief_candidate"]

    approve = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate/approval",
        json={
            "status": "approved",
            "actor": "founder",
            "expected_brief_id": created["brief_id"],
            "expected_revision_id": created["revision_id"],
        },
    )
    assert approve.status_code == 200

    edited = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Approval reset regression brief v2",
            "prd_summary": "The brief changed after approval.",
        },
    )
    assert edited.status_code == 200
    edited_payload = edited.json()
    assert edited_payload["brief_approval_status"] == "pending"
    assert edited_payload["approved_by"] is None
    assert edited_payload["approved_at"] is None
    assert edited_payload["revision_id"] != created["revision_id"]


def test_discovery_dossiers_summary_mode_returns_compact_authoring_payload():
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={"title": "Compact dossier summary"},
    ).json()
    idea_id = idea["idea_id"]

    observation = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://example.com/repo",
            "raw_text": "Very long raw observation body that should not be shipped in dossier summary mode.",
            "topic_tags": ["summary"],
            "evidence_confidence": "high",
        },
    )
    assert observation.status_code == 200

    evidence = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/evidence-bundle",
        json={
            "items": [
                {
                    "kind": "source_observation",
                    "summary": "Evidence item for compact payload checks.",
                    "raw_content": "Verbose evidence payload should stay out of the summary response.",
                    "confidence": "high",
                }
            ],
            "overall_confidence": "high",
        },
    )
    assert evidence.status_code == 200

    summary_response = client.get("/orchestrate/discovery/dossiers?summary=true")

    assert summary_response.status_code == 200
    dossier = next(
        item for item in summary_response.json()["dossiers"] if item["idea"]["idea_id"] == idea_id
    )
    assert dossier["authoring_summary"]["observation_count"] == 1
    assert dossier["authoring_summary"]["evidence_item_count"] == 1
    assert dossier["authoring_summary"]["overall_confidence"] == "high"
    assert "observations" not in dossier
    assert "evidence_bundle" not in dossier
