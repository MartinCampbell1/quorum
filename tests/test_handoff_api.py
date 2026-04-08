"""Regression coverage for discovery -> Autopilot handoff routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.handoff import clear_handoff_service_cache
from orchestrator.models import SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_discovery_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_handoff_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_handoff_service_cache()
    clear_discovery_store_cache()


def _seed_discovery_idea(*, with_simulation: bool) -> dict:
    idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Founder repo signal monitor",
            "summary": "Turn founder repo patterns into execution-ready product briefs.",
            "source": "github",
            "topic_tags": ["repo", "founder", "handoff"],
            "provenance": {
                "repo_dna_profile": {
                    "tech_stack": ["FastAPI", "Next.js"],
                    "frameworks": ["FastAPI", "Next.js"],
                    "languages": ["Python", "TypeScript"],
                    "readme_claims": ["Execution-ready founder workflow"],
                }
            },
        },
    ).json()
    idea_id = idea["idea_id"]

    client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/cyclotruc/gitingest",
            "raw_text": "Founder workflows need a typed bridge from repo signals into launch-ready execution briefs.",
            "topic_tags": ["repo", "handoff"],
            "pain_score": 0.71,
            "trend_score": 0.63,
            "evidence_confidence": "high",
        },
    )

    client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/validation-reports",
        json={
            "summary": "The opportunity is concrete enough to hand off directly into an MVP build.",
            "verdict": "pass",
            "findings": [
                "Execution brief needs explicit acceptance criteria.",
                "Autopilot critic should receive the evidence pack, not just a prose summary.",
            ],
            "confidence": "high",
        },
    )

    client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={"title": "Repo signal monitor MVP"},
    )

    simulation_payload = None
    if with_simulation:
        simulation_response = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/simulation",
            json={"persona_count": 10, "max_rounds": 2},
        )
        assert simulation_response.status_code == 200
        simulation_payload = simulation_response.json()

    return {"idea_id": idea_id, "simulation": simulation_payload}


def test_discovery_handoff_schema_route_exposes_shared_execution_contract():
    response = client.get("/orchestrate/discovery/handoff/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "ExecutionBrief"
    assert "properties" in payload
    assert "prd_summary" in payload["properties"]
    assert "evidence" in payload["properties"]


def test_discovery_handoff_export_synthesizes_and_persists_packet():
    seeded = _seed_discovery_idea(with_simulation=True)
    idea_id = seeded["idea_id"]
    simulation_summary = seeded["simulation"]["report"]["summary_headline"]

    response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/export",
        json={"persist_candidate": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"

    handoff = payload["handoff"]
    brief = handoff["brief"]
    assert handoff["idea"]["idea_id"] == idea_id
    assert brief["brief_id"].startswith("brief_")
    assert brief["idea_id"] == idea_id
    assert brief["title"] == "Repo signal monitor MVP"
    assert brief["prd_summary"]
    assert len(brief["acceptance_criteria"]) >= 2
    assert len(brief["risks"]) >= 1
    assert len(brief["recommended_tech_stack"]) >= 2
    assert brief["repo_dna_snapshot"]["tech_stack"] == ["FastAPI", "Next.js"]
    assert len(brief["first_stories"]) >= 1
    assert brief["judge_summary"].startswith("PASS:")
    assert brief["simulation_summary"] == simulation_summary
    assert brief["evidence"]["bundle_id"].startswith("bundle_")
    assert len(brief["evidence"]["items"]) >= 3
    assert handoff["critic_evidence"]["bundle_id"] == brief["evidence"]["bundle_id"]
    assert any(check["code"] == "repo_context" and check["passed"] for check in handoff["readiness_checks"])

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert dossier["execution_brief_candidate"]["brief_id"] == brief["brief_id"]
    assert dossier["execution_brief_candidate"]["prd_summary"] == brief["prd_summary"]
    assert dossier["idea"]["latest_stage"] == "handed_off"


def test_discovery_handoff_send_to_autopilot_records_decision_and_timeline():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    with patch(
        "orchestrator.api._send_brief_to_autopilot",
        new=AsyncMock(return_value={"project_id": "proj_123", "status": "ok", "launched": False}),
    ) as mock_send:
        response = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
            json={
                "project_path": "/workspace/autopilot/projects/repo-signal-monitor",
                "priority": "high",
                "launch": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["autopilot"]["project_id"] == "proj_123"
    assert payload["handoff"]["brief"]["title"] == "Repo signal monitor MVP"
    assert mock_send.await_count == 1
    sent_brief, sent_request = mock_send.await_args.args
    assert sent_brief["title"] == "Repo signal monitor MVP"
    assert sent_request.project_name == "Repo signal monitor MVP"
    assert mock_send.await_args.kwargs["discovery_store"] is not None

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert any(decision["decision_type"] == "handoff_sent_to_autopilot" for decision in dossier["decisions"])
    assert any(event["title"] == "Handoff sent to Autopilot" for event in dossier["timeline"])


def test_execution_brief_approval_route_updates_candidate_and_rejects_stale_revision():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    export = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/export",
        json={"persist_candidate": True},
    )
    assert export.status_code == 200
    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    candidate = dossier["execution_brief_candidate"]
    revision_id = candidate["revision_id"]

    approve = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate/approval",
        json={
            "status": "approved",
            "actor": "founder",
            "expected_brief_id": candidate["brief_id"],
            "expected_revision_id": revision_id,
        },
    )

    assert approve.status_code == 200, approve.text
    approved = approve.json()
    assert approved["brief_approval_status"] == "approved"
    assert approved["approved_by"] == "founder"
    assert approved["approved_at"]
    assert approved["revision_id"] == revision_id

    edit = client.put(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate",
        json={
            "title": "Repo signal monitor MVP v2",
            "prd_summary": "Updated after approval.",
        },
    )
    assert edit.status_code == 200, edit.text
    edited = edit.json()
    assert edited["brief_approval_status"] == "pending"
    assert edited["approved_by"] is None
    assert edited["revision_id"] != revision_id

    stale = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate/approval",
        json={
            "status": "approved",
            "actor": "founder",
            "expected_brief_id": candidate["brief_id"],
            "expected_revision_id": revision_id,
        },
    )
    assert stale.status_code == 409
    assert "changed before approval" in stale.json()["detail"].lower()


def test_founder_approval_alias_rejects_stale_brief_and_revision():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    export = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/export",
        json={"persist_candidate": True},
    )
    assert export.status_code == 200
    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    candidate = dossier["execution_brief_candidate"]

    stale_brief = client.post(
        f"/orchestrate/founder/approval/{idea_id}/approve",
        json={"expected_brief_id": "wrong-brief-id"},
    )
    assert stale_brief.status_code == 409
    assert "brief changed" in stale_brief.json()["detail"].lower()

    stale_revision = client.post(
        f"/orchestrate/founder/approval/{idea_id}/reject",
        json={
            "expected_brief_id": candidate["brief_id"],
            "expected_revision_id": "wrong-revision-id",
        },
    )
    assert stale_revision.status_code == 409
    assert "changed before approval" in stale_revision.json()["detail"].lower()


def test_discovery_handoff_launch_blocks_when_candidate_is_pending():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    response = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
        json={
            "project_path": "/tmp/repo-signal-monitor",
            "priority": "high",
            "launch": True,
        },
    )

    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()


def test_discovery_handoff_launch_sends_approved_candidate_as_v2():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    export = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/handoff/export",
        json={"persist_candidate": True},
    )
    assert export.status_code == 200
    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    candidate = dossier["execution_brief_candidate"]
    approve = client.post(
        f"/orchestrate/discovery/ideas/{idea_id}/execution-brief-candidate/approval",
        json={
            "status": "approved",
            "actor": "founder",
            "expected_brief_id": candidate["brief_id"],
            "expected_revision_id": candidate["revision_id"],
        },
    )
    assert approve.status_code == 200, approve.text
    approved = approve.json()

    captured: dict[str, object] = {}
    mock_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"project_id": "proj-approved", "status": "ok", "launched": True},
        text="",
    )

    async def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs.get("json")
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("orchestrator.handoff_bridge.httpx.AsyncClient", return_value=mock_client):
        response = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
            json={
                "project_path": "/tmp/repo-signal-monitor",
                "priority": "high",
                "launch": True,
            },
        )

    assert response.status_code == 200, response.text
    assert captured["url"] == "http://127.0.0.1:8420/api/projects/from-brief-v2"
    payload = captured["payload"]
    assert payload["brief"]["brief_approval_status"] == "approved"
    assert payload["brief"]["approved_by"] == "founder"
    assert payload["brief"]["revision_id"] == approved["revision_id"]
    assert response.json()["autopilot"]["project_id"] == "proj-approved"


def test_founder_approval_alias_syncs_existing_autopilot_project():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    with patch(
        "orchestrator.api._send_brief_to_autopilot",
        new=AsyncMock(return_value={"project_id": "proj_123", "status": "ok", "launched": False}),
    ):
        send = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
            json={
                "autopilot_url": "http://autopilot:8001/api",
                "project_path": "/tmp/repo-signal-monitor",
                "priority": "high",
                "launch": False,
            },
        )
    assert send.status_code == 200, send.text

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    candidate = dossier["execution_brief_candidate"]
    assert dossier["idea"]["provenance"]["autopilot"]["autopilot_api_base"] == "http://autopilot:8001/api"

    captured: dict[str, object] = {}
    mock_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"status": "ok"},
        text="",
    )

    async def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs.get("json")
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("orchestrator.api.httpx.AsyncClient", return_value=mock_client):
        approve = client.post(
            f"/orchestrate/founder/approval/{idea_id}/approve",
            json={
                "actor": "founder",
                "expected_brief_id": candidate["brief_id"],
                "expected_revision_id": candidate["revision_id"],
            },
        )

    assert approve.status_code == 200, approve.text
    assert approve.json()["brief"]["brief_approval_status"] == "approved"
    assert approve.json()["autopilot_sync"]["status"] == "ok"
    assert captured["url"] == f"http://autopilot:8001/api/projects/briefs/{candidate['brief_id']}/sync-v2"
    payload = captured["payload"]
    assert payload["brief"]["brief_approval_status"] == "approved"
    assert payload["brief"]["approved_by"] == "founder"
    assert payload["brief"]["revision_id"] == candidate["revision_id"]


def test_founder_approval_alias_rolls_back_local_approval_when_autopilot_sync_fails():
    seeded = _seed_discovery_idea(with_simulation=False)
    idea_id = seeded["idea_id"]

    with patch(
        "orchestrator.api._send_brief_to_autopilot",
        new=AsyncMock(return_value={"project_id": "proj_123", "status": "ok", "launched": False}),
    ):
        send = client.post(
            f"/orchestrate/discovery/ideas/{idea_id}/handoff/send-to-autopilot",
            json={
                "autopilot_url": "http://autopilot:8001/api",
                "project_path": "/tmp/repo-signal-monitor",
                "priority": "high",
                "launch": False,
            },
        )
    assert send.status_code == 200, send.text

    dossier = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    candidate = dossier["execution_brief_candidate"]

    with patch(
        "orchestrator.api._sync_existing_autopilot_brief_if_present",
        new=AsyncMock(side_effect=HTTPException(502, "Failed to reach Autopilot sync bridge: timeout")),
    ):
        approve = client.post(
            f"/orchestrate/founder/approval/{idea_id}/approve",
            json={
                "actor": "founder",
                "expected_brief_id": candidate["brief_id"],
                "expected_revision_id": candidate["revision_id"],
            },
        )

    assert approve.status_code == 502, approve.text
    payload = approve.json()
    assert "rolled back" in payload["detail"]
    assert "Autopilot sync bridge" in payload["detail"]

    refreshed = client.get(f"/orchestrate/discovery/ideas/{idea_id}/dossier").json()
    assert refreshed["execution_brief_candidate"]["brief_approval_status"] == "pending"
    assert refreshed["execution_brief_candidate"]["approved_by"] is None
    assert not any(
        decision["decision_type"] == "execution_brief_approved"
        for decision in refreshed["decisions"]
    )
    assert any(event["title"] == "Execution brief approval rolled back" for event in refreshed["timeline"])
    assert not any(event["title"] == "Execution brief approved" for event in refreshed["timeline"])
