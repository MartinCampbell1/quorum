"""Integration tests for the discovery → Autopilot handoff seam.

Validates that _infer_brief_kind correctly identifies brief contracts and
that _send_brief_to_autopilot routes to the appropriate endpoint.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from orchestrator.handoff_models import SendExecutionBriefRequest
from orchestrator.handoff_bridge import _infer_brief_kind, _send_brief_to_autopilot


# ---------------------------------------------------------------------------
# Fixture payloads
# ---------------------------------------------------------------------------

SHARED_BRIEF_PAYLOAD = {
    "brief_id": "brief_abc123",
    "idea_id": "idea_xyz",
    "title": "Repo signal monitor",
    "prd_summary": "Turn founder repo patterns into execution-ready product briefs.",
    "acceptance_criteria": ["Must ingest repo DNA", "Must emit typed brief"],
    "risks": [
        {
            "category": "technical",
            "description": "API rate limits",
            "level": "medium",
            "mitigation": "Add retry and caching",
        }
    ],
    "recommended_tech_stack": ["FastAPI", "Next.js"],
    "first_stories": [
        {
            "title": "Story 1",
            "description": "As a founder, I want ...",
            "acceptance_criteria": ["Shared brief survives conversion"],
            "effort": "small",
        }
    ],
    "repo_dna_snapshot": {"tech_stack": ["FastAPI"]},
    "judge_summary": "PASS: solid opportunity",
    "simulation_summary": "8/10 personas engaged",
    "evidence": {"bundle_id": "bundle_1", "parent_id": "idea_xyz", "items": []},
    "confidence": "high",
    "effort": "medium",
    "urgency": "this_week",
    "budget_tier": "low",
    "created_at": "2026-04-05T00:00:00Z",
}

INTERNAL_BRIEF_PAYLOAD = {
    "version": "1.0",
    "title": "My Startup",
    "thesis": "The world needs better tooling for founders.",
    "summary": "A founder productivity suite.",
    "tags": ["founder", "tooling"],
    "founder": {},
    "market": {},
    "execution": {},
    "monetization": {},
    "evaluation": {},
    "provenance": {},
}


# ---------------------------------------------------------------------------
# _infer_brief_kind tests
# ---------------------------------------------------------------------------


def test_shared_brief_routes_to_shared_ingest_endpoint():
    """_infer_brief_kind returns 'shared' for a shared cross-plane brief payload."""
    result = _infer_brief_kind(SHARED_BRIEF_PAYLOAD)
    assert result == "shared"


def test_internal_brief_routes_to_internal_endpoint():
    """_infer_brief_kind returns 'internal' for an internal brief payload."""
    result = _infer_brief_kind(INTERNAL_BRIEF_PAYLOAD)
    assert result == "internal"


def test_infer_brief_kind_raises_on_unknown_payload():
    """_infer_brief_kind raises ValueError for a payload matching neither contract."""
    garbage = {"foo": "bar", "baz": 42}
    with pytest.raises(ValueError, match="Unknown execution brief contract"):
        _infer_brief_kind(garbage)


# ---------------------------------------------------------------------------
# _send_brief_to_autopilot URL routing tests
# ---------------------------------------------------------------------------


def _make_request(
    autopilot_url: str = "http://autopilot:8001",
    *,
    launch: bool = False,
) -> SendExecutionBriefRequest:
    return SendExecutionBriefRequest(
        autopilot_url=autopilot_url,
        project_name="test-project",
        project_path="/tmp/test",
        priority="normal",
        launch=launch,
        launch_profile=None,
    )


def test_shared_brief_never_hits_internal_route():
    """_send_brief_to_autopilot sends shared briefs through the canonical V2 endpoint."""
    import asyncio

    captured_url: list[str] = []
    captured_payloads: list[dict] = []

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"project_id": "proj_1"}

    async def fake_post(url: str, **kwargs):
        captured_url.append(url)
        captured_payloads.append(kwargs.get("json") or {})
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    discovery_store = SimpleNamespace(
        get_dossier=lambda idea_id: SimpleNamespace(
            execution_brief_candidate=SimpleNamespace(
                brief_id="brief_abc123",
                revision_id="brief_rev_001",
                founder_approval_required=True,
                brief_approval_status="approved",
                approved_by="founder",
                approved_at="2026-04-05T00:00:00Z",
            )
        )
    )

    async def run():
        with patch("orchestrator.handoff_bridge.httpx.AsyncClient", return_value=mock_client):
            return await _send_brief_to_autopilot(
                SHARED_BRIEF_PAYLOAD,
                _make_request(),
                discovery_store=discovery_store,
            )

    result = asyncio.run(run())

    assert len(captured_url) == 1
    assert captured_url[0] == "http://autopilot:8001/projects/from-brief-v2"
    assert captured_payloads[0]["brief"]["brief_approval_status"] == "approved"
    assert captured_payloads[0]["brief"]["approved_by"] == "founder"
    assert captured_payloads[0]["brief"]["revision_id"] == "brief_rev_001"
    assert result == {"project_id": "proj_1"}


def test_shared_brief_launch_blocks_without_candidate_approval():
    """Shared brief launch cannot bypass the persisted Quorum approval state."""
    import asyncio

    discovery_store = SimpleNamespace(
        get_dossier=lambda idea_id: SimpleNamespace(
            execution_brief_candidate=SimpleNamespace(
                brief_id="brief_abc123",
                founder_approval_required=True,
                brief_approval_status="pending",
                approved_by=None,
                approved_at=None,
            )
        )
    )

    async def run():
        return await _send_brief_to_autopilot(
            SHARED_BRIEF_PAYLOAD,
            _make_request(launch=True),
            discovery_store=discovery_store,
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 409
    assert "approved" in str(exc_info.value.detail).lower()


@pytest.mark.parametrize("status_code", [409, 422, 503])
def test_upstream_business_errors_pass_through(status_code: int):
    """Bridge preserves expected Autopilot business status codes instead of rewriting them to 502."""
    import asyncio

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = {"detail": f"upstream-{status_code}"}

    async def fake_post(url: str, **kwargs):
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    async def run():
        with patch("orchestrator.handoff_bridge.httpx.AsyncClient", return_value=mock_client):
            return await _send_brief_to_autopilot(SHARED_BRIEF_PAYLOAD, _make_request())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == f"upstream-{status_code}"
