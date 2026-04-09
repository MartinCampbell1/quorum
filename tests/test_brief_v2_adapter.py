"""Tests for the Quorum → ExecutionBriefV2 lossless adapter."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orchestrator.brief_v2_adapter import shared_brief_to_v2
from orchestrator.shared_contracts import (
    BudgetTier,
    Confidence,
    EffortEstimate,
    EvidenceBundle,
    EvidenceItem,
    ExecutionBrief,
    RiskItem,
    RiskLevel,
    StoryDecompositionSeed,
    Urgency,
)


def _make_full_brief() -> ExecutionBrief:
    """Build a fully-populated ExecutionBrief for testing."""
    evidence_item = EvidenceItem(
        evidence_id="ei-001",
        kind="market_research",
        summary="Strong PMF signals in SMB segment",
        raw_content="Full raw text here",
        artifact_path="/artifacts/research.md",
        source="primary_research",
        confidence=Confidence.HIGH,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        tags=["smb", "pmf"],
    )
    evidence_bundle = EvidenceBundle(
        bundle_id="eb-001",
        parent_id="idea-42",
        items=[evidence_item],
        overall_confidence=Confidence.MEDIUM,
    )
    story = StoryDecompositionSeed(
        title="User can log in",
        description="As a user I want to log in so I can access my dashboard",
        acceptance_criteria=["Login form appears", "Valid credentials grant access"],
        effort=EffortEstimate.SMALL,
    )
    risk = RiskItem(
        category="technical",
        description="Database scaling risk at 10k users",
        level=RiskLevel.HIGH,
        mitigation="Shard early",
    )
    return ExecutionBrief(
        brief_id="brief-001",
        idea_id="idea-42",
        title="Founder OS MVP",
        prd_summary="Build a lean MVP for solo founders",
        acceptance_criteria=["Onboarding < 5 min", "Core loop works end-to-end"],
        risks=[risk],
        recommended_tech_stack=["Python", "FastAPI", "React"],
        first_stories=[story],
        repo_dna_snapshot={"language": "python", "framework": "fastapi"},
        judge_summary="Option A wins on velocity",
        simulation_summary="Market sim shows 12% TAM capture in 18 months",
        evidence=evidence_bundle,
        confidence=Confidence.HIGH,
        effort=EffortEstimate.LARGE,
        urgency=Urgency.THIS_WEEK,
        budget_tier=BudgetTier.LOW,
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )


def test_shared_brief_to_v2_preserves_all_fields() -> None:
    """Every field from the source brief should appear correctly in the V2 output."""
    brief = _make_full_brief()
    v2 = shared_brief_to_v2(
        brief, initiative_id="init-99", option_id="opt-1", decision_id="dec-7"
    )

    assert v2.schema_version == "2.0"
    assert v2.brief_id == "brief-001"
    assert v2.revision_id.startswith("rev-")
    assert len(v2.revision_id) == len("rev-") + 8

    # Lineage
    assert v2.initiative_id == "init-99"
    assert v2.option_id == "opt-1"
    assert v2.decision_id == "dec-7"

    # Content
    assert v2.title == "Founder OS MVP"
    assert v2.initiative_summary == "Build a lean MVP for solo founders"
    assert v2.winner_rationale == "Option A wins on velocity"
    assert v2.research_summary == "Market sim shows 12% TAM capture in 18 months"

    # Requirements
    assert v2.success_criteria == ["Onboarding < 5 min", "Core loop works end-to-end"]

    # Budget
    assert v2.budget_policy.tier == "low"
    assert v2.approval_policy.founder_approval_required is True

    # Technical
    assert v2.recommended_tech_stack == ["Python", "FastAPI", "React"]
    assert v2.repo_dna_snapshot == {"language": "python", "framework": "fastapi"}

    # Timestamps
    assert v2.created_at == datetime(2024, 6, 1, tzinfo=timezone.utc)
    assert v2.updated_at is not None

    # New fields should be derived from existing evidence when available
    assert len(v2.citations) == 1
    assert v2.citations[0].citation_id == "ei-001"
    assert v2.citations[0].title == "Strong PMF signals in SMB segment"
    assert v2.source_pack_ref == "eb-001"
    assert v2.repo_instruction_refs == []
    assert v2.brief_approval_status == "pending"


def test_shared_brief_to_v2_does_not_lose_stories() -> None:
    """Regression: story description, acceptance_criteria, and effort must all survive conversion."""
    brief = _make_full_brief()
    v2 = shared_brief_to_v2(brief, initiative_id="init-1")

    assert len(v2.story_breakdown) == 1
    story = v2.story_breakdown[0]

    assert story.title == "User can log in"
    assert (
        story.description == "As a user I want to log in so I can access my dashboard"
    )
    assert story.acceptance_criteria == [
        "Login form appears",
        "Valid credentials grant access",
    ]
    assert story.effort == "small"


def test_shared_brief_to_v2_converts_evidence() -> None:
    """Evidence bundle items must be converted; Confidence enum → float."""
    brief = _make_full_brief()
    v2 = shared_brief_to_v2(brief, initiative_id="init-1")

    assert v2.evidence is not None
    assert v2.evidence.bundle_id == "eb-001"
    assert v2.evidence.parent_id == "idea-42"
    assert v2.evidence.overall_confidence == 0.5  # MEDIUM → 0.5

    assert len(v2.evidence.items) == 1
    item = v2.evidence.items[0]

    assert item.evidence_id == "ei-001"
    assert item.kind == "market_research"
    assert item.summary == "Strong PMF signals in SMB segment"
    assert item.raw_content == "Full raw text here"
    assert item.artifact_path == "/artifacts/research.md"
    assert item.source == "primary_research"
    assert item.confidence == 0.9  # HIGH → 0.9
    assert item.tags == ["smb", "pmf"]

    assert len(v2.citations) == 1
    citation = v2.citations[0]
    assert citation.citation_id == "ei-001"
    assert citation.source_type == "market_research"
    assert citation.url == ""
    assert citation.quoted_text == "Full raw text here"
    assert "source=primary_research" in citation.note
    assert "artifact=/artifacts/research.md" in citation.note


def test_shared_brief_to_v2_handles_none_evidence() -> None:
    """A brief with evidence=None must produce a V2 with evidence=None."""
    brief = _make_full_brief()
    brief.evidence = None

    v2 = shared_brief_to_v2(brief, initiative_id="init-1")

    assert v2.evidence is None


def test_shared_brief_to_v2_preserves_risks() -> None:
    """Risk items including enum level values must be preserved."""
    brief = _make_full_brief()
    v2 = shared_brief_to_v2(brief, initiative_id="init-1")

    assert len(v2.risks) == 1
    risk = v2.risks[0]

    assert risk.category == "technical"
    assert risk.description == "Database scaling risk at 10k users"
    assert risk.level == "high"
    assert risk.mitigation == "Shard early"


def test_shared_brief_to_v2_optional_params_default_to_none() -> None:
    """option_id and decision_id are optional and default to None."""
    brief = _make_full_brief()
    v2 = shared_brief_to_v2(brief, initiative_id="init-1")

    assert v2.option_id is None
    assert v2.decision_id is None


def test_shared_brief_to_v2_confidence_enum_all_values() -> None:
    """All Confidence enum values are converted to the correct float."""
    from orchestrator.brief_v2_adapter import _confidence_enum_to_float

    assert _confidence_enum_to_float(Confidence.HIGH) == 0.9
    assert _confidence_enum_to_float(Confidence.MEDIUM) == 0.5
    assert _confidence_enum_to_float(Confidence.LOW) == 0.2
    assert _confidence_enum_to_float(Confidence.UNKNOWN) == 0.0


def test_shared_brief_to_v2_preserves_explicit_revision_and_approval_fields() -> None:
    brief = _make_full_brief()
    approved_at = datetime(2026, 4, 5, tzinfo=timezone.utc)

    v2 = shared_brief_to_v2(
        brief,
        initiative_id="init-1",
        revision_id="brief_rev_123",
        founder_approval_required=True,
        brief_approval_status="approved",
        approved_at=approved_at,
        approved_by="founder",
    )

    assert v2.revision_id == "brief_rev_123"
    assert v2.brief_approval_status == "approved"
    assert v2.approved_at == approved_at
    assert v2.approved_by == "founder"
