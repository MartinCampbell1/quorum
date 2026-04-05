"""Tests for Quorum-side founder approval workflow (P1.3).

Validates that approval state changes route through discovery_store
(the single source of truth) so the launch gate in handoff_bridge
correctly reads the approved/rejected status.
"""
from __future__ import annotations

import pytest

from orchestrator.discovery_models import (
    ExecutionBriefApprovalUpdateRequest,
    ExecutionBriefCandidateUpsertRequest,
    IdeaCreateRequest,
)
from orchestrator.discovery_store import DiscoveryStore


@pytest.fixture()
def ds(tmp_path):
    """Create an isolated DiscoveryStore."""
    return DiscoveryStore(db_path=str(tmp_path / "test-approval.db"))


def _seed_idea_with_pending_brief(ds: DiscoveryStore) -> str:
    """Create an idea with a pending execution brief candidate. Returns idea_id."""
    idea = ds.create_idea(IdeaCreateRequest(title="Test Idea", summary="Test summary"))
    ds.upsert_execution_brief_candidate(
        idea.idea_id,
        ExecutionBriefCandidateUpsertRequest(
            brief_id="brief-001",
            title="Test Brief",
            prd_summary="Test PRD",
            acceptance_criteria=["works"],
            recommended_tech_stack=["python"],
            first_stories=[],
            founder_approval_required=True,
            brief_approval_status="pending",
        ),
    )
    return idea.idea_id


def test_approve_via_discovery_store(ds):
    """Approving through discovery_store sets status visible to the launch gate."""
    idea_id = _seed_idea_with_pending_brief(ds)

    brief = ds.update_execution_brief_candidate_approval(
        idea_id,
        ExecutionBriefApprovalUpdateRequest(status="approved", actor="martin"),
    )

    assert brief.brief_approval_status == "approved"
    assert brief.approved_by == "martin"
    assert brief.approved_at is not None

    # Verify the launch gate will now see approved status
    dossier = ds.get_dossier(idea_id)
    assert dossier.execution_brief_candidate.brief_approval_status == "approved"


def test_reject_via_discovery_store(ds):
    """Rejecting through discovery_store sets status visible to the launch gate."""
    idea_id = _seed_idea_with_pending_brief(ds)

    brief = ds.update_execution_brief_candidate_approval(
        idea_id,
        ExecutionBriefApprovalUpdateRequest(status="rejected", actor="martin", note="Needs more research"),
    )

    assert brief.brief_approval_status == "rejected"

    dossier = ds.get_dossier(idea_id)
    assert dossier.execution_brief_candidate.brief_approval_status == "rejected"


def test_approve_nonexistent_raises(ds):
    """Approving a brief for an unknown idea raises KeyError."""
    with pytest.raises(KeyError):
        ds.update_execution_brief_candidate_approval(
            "nonexistent",
            ExecutionBriefApprovalUpdateRequest(status="approved", actor="founder"),
        )


def test_approval_state_visible_through_dossier(ds):
    """The handoff bridge reads from dossier.execution_brief_candidate — verify it works."""
    idea_id = _seed_idea_with_pending_brief(ds)

    # Before approval — pending
    dossier = ds.get_dossier(idea_id)
    candidate = dossier.execution_brief_candidate
    assert candidate.brief_approval_status == "pending"
    assert candidate.founder_approval_required is True

    # After approval — approved
    ds.update_execution_brief_candidate_approval(
        idea_id,
        ExecutionBriefApprovalUpdateRequest(status="approved", actor="founder"),
    )
    dossier = ds.get_dossier(idea_id)
    candidate = dossier.execution_brief_candidate
    assert candidate.brief_approval_status == "approved"
    assert candidate.approved_by == "founder"


def test_approval_with_wrong_brief_id_raises(ds):
    """Approval request with mismatched brief_id raises ValueError (stale UI)."""
    idea_id = _seed_idea_with_pending_brief(ds)

    with pytest.raises(ValueError, match="brief changed"):
        ds.update_execution_brief_candidate_approval(
            idea_id,
            ExecutionBriefApprovalUpdateRequest(
                status="approved",
                actor="founder",
                expected_brief_id="wrong-brief-id",
            ),
        )
