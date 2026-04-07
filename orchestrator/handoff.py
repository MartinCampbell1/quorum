"""Typed discovery -> Autopilot handoff packet builder."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.discovery_models import (
    DossierTimelineEventCreateRequest,
    EvidenceBundleCandidate,
    EvidenceItemRecord,
    ExecutionBriefCandidate,
    ExecutionBriefCandidateUpsertRequest,
    IdeaCandidate,
    IdeaDecisionCreateRequest,
    IdeaDossier,
    IdeaUpdateRequest,
    IdeaValidationReport,
    MarketSimulationReport,
    RiskItemRecord,
    SimulationFeedbackReport,
    StoryDecompositionSeedRecord,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.shared_contracts import (
    Confidence,
    EffortEstimate,
    EvidenceBundle,
    EvidenceItem,
    ExecutionBrief,
    RiskItem,
    Urgency,
    BudgetTier,
    StoryDecompositionSeed,
    to_jsonable,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _clip(value: str | None, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _repo_dna_snapshot(dossier: IdeaDossier) -> dict[str, Any]:
    idea = dossier.idea
    candidates = [
        idea.provenance.get("repo_dna_profile"),
        idea.provenance.get("repo_dna"),
        idea.provenance.get("repo_profile"),
    ]
    if dossier.execution_brief_candidate and dossier.execution_brief_candidate.repo_dna_snapshot:
        candidates.append(dossier.execution_brief_candidate.repo_dna_snapshot)
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate
    return {}


class DiscoveryHandoffReadinessCheck(BaseModel):
    code: str
    passed: bool
    detail: str


class DiscoveryHandoffPacket(BaseModel):
    idea: IdeaCandidate
    brief: dict[str, Any]
    critic_evidence: dict[str, Any] | None = None
    readiness_checks: list[DiscoveryHandoffReadinessCheck] = Field(default_factory=list)
    handoff_summary: str = ""
    generated_at: datetime = Field(default_factory=_utcnow)


class DiscoveryHandoffExportRequest(BaseModel):
    persist_candidate: bool = True


class DiscoveryHandoffService:
    """Build execution-ready handoff packets from discovery dossiers."""

    def __init__(self, discovery_store: DiscoveryStore):
        self._store = discovery_store

    def _default_prd_summary(self, dossier: IdeaDossier) -> str:
        parts = [
            dossier.idea.summary,
            dossier.idea.thesis,
            dossier.execution_brief_candidate.prd_summary if dossier.execution_brief_candidate else None,
        ]
        if dossier.market_simulation_report is not None:
            parts.append(dossier.market_simulation_report.executive_summary)
        elif dossier.simulation_report is not None:
            parts.append(dossier.simulation_report.summary_headline)
        if dossier.validation_reports:
            parts.append(dossier.validation_reports[-1].summary)
        return _clip(next((part for part in parts if part), dossier.idea.title), 420)

    def _default_acceptance_criteria(self, dossier: IdeaDossier) -> list[str]:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.acceptance_criteria:
            return dossier.execution_brief_candidate.acceptance_criteria[:6]
        criteria: list[str] = []
        if dossier.market_simulation_report is not None:
            criteria.extend(
                _clip(action, 140)
                for action in dossier.market_simulation_report.recommended_actions[:3]
            )
        if dossier.simulation_report is not None:
            criteria.extend(
                _clip(action, 140)
                for action in dossier.simulation_report.recommended_actions[:3]
            )
        if dossier.validation_reports:
            criteria.extend(
                f"Address validation point: {_clip(point, 120)}"
                for point in dossier.validation_reports[-1].findings[:3]
            )
        if not criteria:
            criteria = [
                f"Ship an MVP for {_clip(dossier.idea.title, 120)}.",
                "Preserve evidence and founder-facing rationale in the product surface.",
                "Keep execution scoped tightly enough for an autonomous first sprint.",
            ]
        return list(dict.fromkeys(criteria))[:6]

    def _default_risks(self, dossier: IdeaDossier) -> list[RiskItemRecord]:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.risks:
            return dossier.execution_brief_candidate.risks[:6]
        risks: list[RiskItemRecord] = []
        if dossier.validation_reports:
            report = dossier.validation_reports[-1]
            for finding in report.findings[:3]:
                risks.append(
                    RiskItemRecord(
                        category="validation",
                        description=_clip(finding, 180),
                        level="medium",
                        mitigation="Resolve the validation finding before broadening build scope.",
                    )
                )
        if dossier.market_simulation_report is not None:
            for objection in dossier.market_simulation_report.key_objections[:2]:
                risks.append(
                    RiskItemRecord(
                        category="market",
                        description=_clip(objection, 180),
                        level="medium",
                        mitigation="Use the simulation objection as a critic test before implementation.",
                    )
                )
        elif dossier.simulation_report is not None:
            for objection in dossier.simulation_report.objections[:2]:
                risks.append(
                    RiskItemRecord(
                        category="persona",
                        description=_clip(objection, 180),
                        level="medium",
                        mitigation="Address the objection in scope, messaging, or onboarding.",
                    )
                )
        if not risks:
            risks.append(
                RiskItemRecord(
                    category="execution",
                    description="The current dossier is light on explicit failure cases.",
                    level="low",
                    mitigation="Keep the first story narrow and preserve evidence capture from day one.",
                )
            )
        return risks[:6]

    def _default_tech_stack(self, dossier: IdeaDossier) -> list[str]:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.recommended_tech_stack:
            return dossier.execution_brief_candidate.recommended_tech_stack[:8]
        snapshot = _repo_dna_snapshot(dossier)
        stack: list[str] = []
        for key in ("tech_stack", "languages", "frameworks"):
            value = snapshot.get(key)
            if isinstance(value, dict):
                stack.extend(str(item) for item in value.keys())
            elif isinstance(value, list):
                stack.extend(str(item) for item in value)
        if not stack:
            stack = ["FastAPI", "SQLite", "Next.js"]
        return list(dict.fromkeys(item for item in stack if item))[:8]

    def _default_first_stories(
        self,
        dossier: IdeaDossier,
        acceptance_criteria: list[str],
    ) -> list[StoryDecompositionSeedRecord]:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.first_stories:
            return dossier.execution_brief_candidate.first_stories[:4]
        stories: list[StoryDecompositionSeedRecord] = []
        for index, criterion in enumerate(acceptance_criteria[:3], start=1):
            stories.append(
                StoryDecompositionSeedRecord(
                    title=f"Story {index}: {_clip(criterion, 72)}",
                    description=_clip(
                        f"Implement the smallest slice needed to satisfy: {criterion}",
                        220,
                    ),
                    acceptance_criteria=[criterion],
                    effort=EffortEstimate.SMALL,
                )
            )
        if not stories:
            stories.append(
                StoryDecompositionSeedRecord(
                    title="Story 1: Handoff-ready MVP shell",
                    description="Create the first thin slice that turns the dossier into a working product artifact.",
                    acceptance_criteria=["A single founder-facing workflow exists end-to-end."],
                    effort=EffortEstimate.SMALL,
                )
            )
        return stories[:4]

    def _default_judge_summary(self, dossier: IdeaDossier) -> str | None:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.judge_summary:
            return dossier.execution_brief_candidate.judge_summary
        if dossier.validation_reports:
            latest = dossier.validation_reports[-1]
            verdict = str(latest.verdict.value if hasattr(latest.verdict, "value") else latest.verdict)
            return _clip(f"{verdict.upper()}: {latest.summary}", 240)
        if dossier.explainability_context and dossier.explainability_context.judge_summary:
            return _clip(dossier.explainability_context.judge_summary, 240)
        return None

    def _default_simulation_summary(self, dossier: IdeaDossier) -> str | None:
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.simulation_summary:
            return dossier.execution_brief_candidate.simulation_summary
        if dossier.market_simulation_report is not None:
            return _clip(dossier.market_simulation_report.executive_summary, 240)
        if dossier.simulation_report is not None:
            return _clip(dossier.simulation_report.summary_headline, 240)
        return None

    def _hydrate_candidate(self, dossier: IdeaDossier) -> ExecutionBriefCandidate:
        current = dossier.execution_brief_candidate or ExecutionBriefCandidate(
            idea_id=dossier.idea.idea_id,
            title=dossier.idea.title,
        )
        acceptance_criteria = (
            current.acceptance_criteria[:] if current.acceptance_criteria else self._default_acceptance_criteria(dossier)
        )
        risks = current.risks[:] if current.risks else self._default_risks(dossier)
        first_stories = current.first_stories[:] if current.first_stories else self._default_first_stories(dossier, acceptance_criteria)
        repo_snapshot = current.repo_dna_snapshot or _repo_dna_snapshot(dossier) or None
        return current.model_copy(
            update={
                "title": current.title or dossier.idea.title,
                "prd_summary": current.prd_summary or self._default_prd_summary(dossier),
                "acceptance_criteria": acceptance_criteria,
                "risks": risks,
                "recommended_tech_stack": (
                    current.recommended_tech_stack[:] if current.recommended_tech_stack else self._default_tech_stack(dossier)
                ),
                "first_stories": first_stories,
                "repo_dna_snapshot": repo_snapshot,
                "judge_summary": current.judge_summary or self._default_judge_summary(dossier),
                "simulation_summary": current.simulation_summary or self._default_simulation_summary(dossier),
                "evidence_bundle_id": (
                    current.evidence_bundle_id
                    or (dossier.evidence_bundle.bundle_id if dossier.evidence_bundle is not None else None)
                ),
                "confidence": current.confidence or Confidence.MEDIUM,
                "effort": current.effort or EffortEstimate.MEDIUM,
                "urgency": current.urgency or Urgency.BACKLOG,
                "budget_tier": current.budget_tier or BudgetTier.MEDIUM,
            }
        )

    def _persist_candidate(self, idea_id: str, candidate: ExecutionBriefCandidate) -> ExecutionBriefCandidate:
        return self._store.upsert_execution_brief_candidate(
            idea_id,
            ExecutionBriefCandidateUpsertRequest(
                title=candidate.title,
                prd_summary=candidate.prd_summary,
                acceptance_criteria=candidate.acceptance_criteria,
                risks=candidate.risks,
                recommended_tech_stack=candidate.recommended_tech_stack,
                first_stories=candidate.first_stories,
                repo_dna_snapshot=candidate.repo_dna_snapshot,
                judge_summary=candidate.judge_summary,
                simulation_summary=candidate.simulation_summary,
                evidence_bundle_id=candidate.evidence_bundle_id,
                confidence=candidate.confidence,
                effort=candidate.effort,
                urgency=candidate.urgency,
                budget_tier=candidate.budget_tier,
                founder_approval_required=candidate.founder_approval_required,
            ),
        )

    def _ensure_critic_evidence(self, dossier: IdeaDossier) -> EvidenceBundle:
        bundle = dossier.evidence_bundle
        if bundle is None or not bundle.items:
            items: list[EvidenceItem] = []
            for observation in dossier.observations[-4:]:
                items.append(
                    EvidenceItem(
                        evidence_id=observation.observation_id,
                        kind="source_observation",
                        summary=_clip(observation.raw_text, 200),
                        raw_content=observation.raw_text,
                        source=observation.source,
                        confidence=observation.evidence_confidence,
                        created_at=observation.captured_at,
                        tags=observation.topic_tags,
                    )
                )
            for report in dossier.validation_reports[-2:]:
                items.append(self._validation_evidence_item(report))
            if dossier.market_simulation_report is not None:
                items.append(self._market_simulation_evidence_item(dossier.market_simulation_report))
            elif dossier.simulation_report is not None:
                items.append(self._simulation_evidence_item(dossier.simulation_report))
            if not items:
                items.append(
                    EvidenceItem(
                        evidence_id=f"evidence_{dossier.idea.idea_id}",
                        kind="idea_summary",
                        summary=_clip(dossier.idea.summary or dossier.idea.title, 200),
                        raw_content=dossier.idea.description or dossier.idea.thesis or dossier.idea.summary,
                        source=dossier.idea.source,
                        confidence=Confidence.UNKNOWN,
                        tags=dossier.idea.topic_tags,
                    )
                )
            return EvidenceBundle(
                bundle_id=f"bundle_{dossier.idea.idea_id}",
                parent_id=dossier.idea.idea_id,
                items=items,
                overall_confidence=self._bundle_confidence(items),
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        return EvidenceBundle(
            bundle_id=bundle.bundle_id,
            parent_id=bundle.parent_id,
            items=[self._evidence_item_from_record(item) for item in bundle.items],
            overall_confidence=bundle.overall_confidence,
            created_at=bundle.created_at,
            updated_at=bundle.updated_at,
        )

    def _evidence_item_from_record(self, item: EvidenceItemRecord) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=item.evidence_id,
            kind=item.kind,
            summary=item.summary,
            raw_content=item.raw_content,
            artifact_path=item.artifact_path,
            source=item.source,
            confidence=item.confidence,
            created_at=item.created_at,
            tags=item.tags,
        )

    def _validation_evidence_item(self, report: IdeaValidationReport) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=report.report_id,
            kind="validation_report",
            summary=_clip(report.summary, 200),
            raw_content="\n".join(report.findings),
            source="validation",
            confidence=report.confidence,
            created_at=report.updated_at,
            tags=[str(report.verdict.value if hasattr(report.verdict, "value") else report.verdict)],
        )

    def _simulation_evidence_item(self, report: SimulationFeedbackReport) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=report.report_id,
            kind="simulation_report",
            summary=_clip(report.summary_headline, 200),
            raw_content="\n".join([*report.positive_signals[:3], *report.objections[:3], *report.recommended_actions[:3]]),
            source="simulation",
            confidence=Confidence.MEDIUM,
            created_at=report.created_at,
            tags=[report.verdict, *report.strongest_segments[:3]],
        )

    def _market_simulation_evidence_item(self, report: MarketSimulationReport) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=report.report_id,
            kind="market_simulation_report",
            summary=_clip(report.executive_summary, 200),
            raw_content="\n".join([*report.channel_findings[:3], *report.key_objections[:3], *report.recommended_actions[:3]]),
            source="market_simulation",
            confidence=Confidence.MEDIUM,
            created_at=report.created_at,
            tags=[report.verdict, *report.strongest_segments[:3]],
        )

    def _bundle_confidence(self, items: list[EvidenceItem]) -> Confidence:
        levels = {item.confidence for item in items}
        if Confidence.HIGH in levels:
            return Confidence.HIGH
        if Confidence.MEDIUM in levels:
            return Confidence.MEDIUM
        if Confidence.LOW in levels:
            return Confidence.LOW
        return Confidence.UNKNOWN

    def _shared_brief_from_candidate(
        self,
        dossier: IdeaDossier,
        candidate: ExecutionBriefCandidate,
        evidence: EvidenceBundle,
    ) -> ExecutionBrief:
        return ExecutionBrief(
            brief_id=candidate.brief_id,
            idea_id=dossier.idea.idea_id,
            title=candidate.title,
            prd_summary=candidate.prd_summary,
            acceptance_criteria=candidate.acceptance_criteria,
            risks=[
                RiskItem(
                    category=item.category,
                    description=item.description,
                    level=item.level,
                    mitigation=item.mitigation,
                )
                for item in candidate.risks
            ],
            recommended_tech_stack=candidate.recommended_tech_stack,
            first_stories=[
                StoryDecompositionSeed(
                    title=item.title,
                    description=item.description,
                    acceptance_criteria=item.acceptance_criteria,
                    effort=item.effort,
                )
                for item in candidate.first_stories
            ],
            repo_dna_snapshot=candidate.repo_dna_snapshot,
            judge_summary=candidate.judge_summary,
            simulation_summary=candidate.simulation_summary,
            evidence=evidence,
            confidence=candidate.confidence,
            effort=candidate.effort,
            urgency=candidate.urgency,
            budget_tier=candidate.budget_tier,
        )

    def _readiness_checks(
        self,
        candidate: ExecutionBriefCandidate,
        evidence: EvidenceBundle,
    ) -> list[DiscoveryHandoffReadinessCheck]:
        checks = [
            DiscoveryHandoffReadinessCheck(
                code="prd_summary",
                passed=bool(candidate.prd_summary.strip()),
                detail="PRD summary is populated for the execution brief.",
            ),
            DiscoveryHandoffReadinessCheck(
                code="acceptance_criteria",
                passed=bool(candidate.acceptance_criteria),
                detail=f"{len(candidate.acceptance_criteria)} acceptance criteria attached.",
            ),
            DiscoveryHandoffReadinessCheck(
                code="risk_list",
                passed=bool(candidate.risks),
                detail=f"{len(candidate.risks)} explicit risks attached.",
            ),
            DiscoveryHandoffReadinessCheck(
                code="starter_stories",
                passed=bool(candidate.first_stories),
                detail=f"{len(candidate.first_stories)} first-story seeds attached.",
            ),
            DiscoveryHandoffReadinessCheck(
                code="critic_evidence",
                passed=bool(evidence.items),
                detail=f"{len(evidence.items)} evidence items prepared for the Autopilot critic.",
            ),
            DiscoveryHandoffReadinessCheck(
                code="repo_context",
                passed=bool(candidate.repo_dna_snapshot),
                detail="RepoDNA context attached." if candidate.repo_dna_snapshot else "No RepoDNA snapshot attached.",
            ),
        ]
        return checks

    def build_packet(
        self,
        idea_id: str,
        *,
        persist_candidate: bool = True,
    ) -> DiscoveryHandoffPacket:
        dossier = self._store.get_dossier(idea_id)
        if dossier is None:
            raise KeyError(f"Unknown idea id: {idea_id}")
        candidate = self._hydrate_candidate(dossier)
        if persist_candidate:
            candidate = self._persist_candidate(idea_id, candidate)
            dossier = self._store.get_dossier(idea_id) or dossier
        evidence = self._ensure_critic_evidence(dossier)
        shared_brief = self._shared_brief_from_candidate(dossier, candidate, evidence)
        checks = self._readiness_checks(candidate, evidence)
        summary = (
            f"Handoff packet ready with {len(candidate.acceptance_criteria)} acceptance criteria, "
            f"{len(candidate.first_stories)} starter stories, and {len(evidence.items)} critic evidence items."
        )
        return DiscoveryHandoffPacket(
            idea=dossier.idea,
            brief=to_jsonable(shared_brief),
            critic_evidence=to_jsonable(evidence),
            readiness_checks=checks,
            handoff_summary=summary,
        )

    def mark_sent_to_autopilot(
        self,
        idea_id: str,
        *,
        project_name: str | None,
        autopilot_payload: dict[str, Any],
    ) -> None:
        dossier = self._store.get_dossier(idea_id)
        if dossier is not None:
            project_payload = dict(autopilot_payload.get("project") or {})
            provenance = dict(dossier.idea.provenance or {})
            autopilot_meta = dict(provenance.get("autopilot") or {})
            project_id = (
                str(autopilot_payload.get("project_id") or "").strip()
                or str(project_payload.get("project_id") or "").strip()
                or str(project_payload.get("id") or "").strip()
            )
            effective_name = (
                str(project_name or "").strip()
                or str(autopilot_payload.get("project_name") or "").strip()
                or str(project_payload.get("name") or "").strip()
            )
            project_path = (
                str(autopilot_payload.get("project_path") or "").strip()
                or str(project_payload.get("path") or "").strip()
            )
            if project_id:
                autopilot_meta["project_id"] = project_id
            if effective_name:
                autopilot_meta["project_name"] = effective_name
            if project_path:
                autopilot_meta["project_path"] = project_path
            autopilot_api_base = str(autopilot_payload.get("autopilot_api_base") or "").strip()
            if autopilot_api_base:
                autopilot_meta["autopilot_api_base"] = autopilot_api_base
            if dossier.execution_brief_candidate is not None:
                autopilot_meta["brief_id"] = dossier.execution_brief_candidate.brief_id
            if autopilot_payload:
                autopilot_meta["latest_payload"] = autopilot_payload
            provenance["autopilot"] = autopilot_meta
            self._store.update_idea(idea_id, IdeaUpdateRequest(provenance=provenance))

        detail = _clip(
            f"Sent to Autopilot as {project_name or autopilot_payload.get('project_name') or autopilot_payload.get('project_id') or 'new project'}."
        )
        self._store.add_decision(
            idea_id,
            IdeaDecisionCreateRequest(
                decision_type="handoff_sent_to_autopilot",
                rationale=detail,
                actor="autopilot_bridge",
                metadata=autopilot_payload,
            ),
        )
        self._store.add_timeline_event(
            idea_id,
            DossierTimelineEventCreateRequest(
                stage="handed_off",
                title="Handoff sent to Autopilot",
                detail=detail,
                metadata={
                    "project_name": project_name,
                    **autopilot_payload,
                },
            ),
        )


_HANDOFF_CACHE: dict[str, DiscoveryHandoffService] = {}


def get_handoff_service(db_path: str, discovery_store: DiscoveryStore) -> DiscoveryHandoffService:
    key = str(Path(db_path).expanduser().resolve())
    service = _HANDOFF_CACHE.get(key)
    if service is None:
        service = DiscoveryHandoffService(discovery_store)
        _HANDOFF_CACHE[key] = service
    return service


def clear_handoff_service_cache() -> None:
    _HANDOFF_CACHE.clear()
