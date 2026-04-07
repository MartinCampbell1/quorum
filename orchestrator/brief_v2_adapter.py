"""Lossless adapter: converts Quorum ExecutionBrief (dataclass) → ExecutionBriefV2 (Pydantic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from founderos_contracts.brief_v2 import (
    ApprovalPolicy,
    BudgetPolicy,
    EvidenceBundle,
    EvidenceItem,
    ExecutionBriefV2,
    RiskItem,
    StoryDecompositionSeed,
)

from .shared_contracts import Confidence
from .shared_contracts import ExecutionBrief
from .shared_contracts import EvidenceBundle as SharedEvidenceBundle

_CONFIDENCE_TO_FLOAT: dict[str, float] = {
    Confidence.HIGH.value: 0.9,
    Confidence.MEDIUM.value: 0.5,
    Confidence.LOW.value: 0.2,
    Confidence.UNKNOWN.value: 0.0,
}


def _confidence_enum_to_float(confidence: Confidence) -> float:
    return _CONFIDENCE_TO_FLOAT.get(confidence.value, 0.0)


def _convert_evidence_bundle(bundle: SharedEvidenceBundle) -> EvidenceBundle:
    items = [
        EvidenceItem(
            evidence_id=item.evidence_id,
            kind=item.kind,
            summary=item.summary,
            raw_content=item.raw_content or "",
            artifact_path=item.artifact_path or "",
            source=item.source or "",
            confidence=_confidence_enum_to_float(item.confidence),
            tags=list(item.tags),
        )
        for item in bundle.items
    ]
    return EvidenceBundle(
        bundle_id=bundle.bundle_id,
        parent_id=bundle.parent_id,
        items=items,
        overall_confidence=_confidence_enum_to_float(bundle.overall_confidence),
    )


def shared_brief_to_v2(
    brief: ExecutionBrief,
    *,
    initiative_id: str,
    revision_id: str | None = None,
    option_id: str | None = None,
    decision_id: str | None = None,
    founder_approval_required: bool = True,
    brief_approval_status: str = "pending",
    approved_at: datetime | None = None,
    approved_by: str | None = None,
) -> ExecutionBriefV2:
    """Convert a shared ExecutionBrief dataclass to a canonical ExecutionBriefV2 Pydantic model.

    All fields are preserved; enum values are extracted with .value; Confidence enums
    are converted to floats (HIGH=0.9, MEDIUM=0.5, LOW=0.2, UNKNOWN=0.0).
    """
    story_breakdown = [
        StoryDecompositionSeed(
            title=story.title,
            description=story.description,
            acceptance_criteria=list(story.acceptance_criteria),
            effort=story.effort.value,
        )
        for story in brief.first_stories
    ]

    risks = [
        RiskItem(
            category=risk.category,
            description=risk.description,
            level=risk.level.value,
            mitigation=risk.mitigation or "",
        )
        for risk in brief.risks
    ]

    evidence = (
        _convert_evidence_bundle(brief.evidence) if brief.evidence is not None else None
    )

    return ExecutionBriefV2(
        schema_version="2.0",
        brief_id=brief.brief_id,
        revision_id=revision_id or f"rev-{uuid.uuid4().hex[:8]}",
        initiative_id=initiative_id,
        option_id=option_id,
        decision_id=decision_id,
        title=brief.title,
        initiative_summary=brief.prd_summary,
        winner_rationale=brief.judge_summary or "",
        research_summary=brief.simulation_summary or "",
        success_criteria=list(brief.acceptance_criteria),
        budget_policy=BudgetPolicy(tier=brief.budget_tier.value),
        approval_policy=ApprovalPolicy(founder_approval_required=founder_approval_required),
        recommended_tech_stack=list(brief.recommended_tech_stack),
        story_breakdown=story_breakdown,
        risks=risks,
        repo_dna_snapshot=brief.repo_dna_snapshot,
        evidence=evidence,
        citations=[],
        source_pack_ref=None,
        repo_instruction_refs=[],
        brief_approval_status=brief_approval_status,
        approved_at=approved_at,
        approved_by=approved_by,
        created_at=brief.created_at,
        updated_at=datetime.now(timezone.utc),
    )
