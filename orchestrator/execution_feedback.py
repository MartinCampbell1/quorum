"""Execution feedback loop from Autopilot back into discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import threading
from typing import Any

from orchestrator.discovery_models import (
    DossierTimelineEventCreateRequest,
    EvidenceBundleCandidate,
    EvidenceItemRecord,
    ExecutionOutcomeRecord,
    FounderPreferenceProfile,
    IdeaCandidate,
    IdeaDecisionCreateRequest,
    IdeaDossier,
    IdeaReasonSnapshot,
    IdeaScoreSnapshot,
    IdeaUpdateRequest,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.preference_model import PreferenceModelService
from orchestrator.shared_contracts import (
    BudgetTier,
    Confidence,
    EffortEstimate,
    EvidenceBundle,
    ExecutionOutcomeBundle,
    IdeaOutcomeStatus,
    VerdictStatus,
)


_SERVICE_CACHE: dict[str, "ExecutionFeedbackService"] = {}
_SERVICE_CACHE_LOCK = threading.Lock()

_BUDGET_BASELINES_USD: dict[BudgetTier, float] = {
    BudgetTier.MICRO: 500.0,
    BudgetTier.LOW: 2_000.0,
    BudgetTier.MEDIUM: 10_000.0,
    BudgetTier.HIGH: 40_000.0,
    BudgetTier.UNLIMITED: 100_000.0,
}
_EFFORT_BASELINES_SEC: dict[EffortEstimate, float] = {
    EffortEstimate.TRIVIAL: 2 * 86_400.0,
    EffortEstimate.SMALL: 5 * 86_400.0,
    EffortEstimate.MEDIUM: 14 * 86_400.0,
    EffortEstimate.LARGE: 30 * 86_400.0,
    EffortEstimate.EPIC: 60 * 86_400.0,
}
_STATUS_BASE: dict[IdeaOutcomeStatus, float] = {
    IdeaOutcomeStatus.VALIDATED: 0.32,
    IdeaOutcomeStatus.FOLLOW_ON_OPPORTUNITY: 0.24,
    IdeaOutcomeStatus.PIVOT_CANDIDATE: 0.06,
    IdeaOutcomeStatus.IN_PROGRESS: 0.04,
    IdeaOutcomeStatus.STALLED: -0.12,
    IdeaOutcomeStatus.EXECUTION_TRAP: -0.24,
    IdeaOutcomeStatus.COST_TRAP: -0.22,
    IdeaOutcomeStatus.INVALIDATED: -0.28,
}
_STATUS_TO_VALIDATION = {
    IdeaOutcomeStatus.VALIDATED: "validated",
    IdeaOutcomeStatus.INVALIDATED: "invalidated",
    IdeaOutcomeStatus.PIVOT_CANDIDATE: "pivot_candidate",
    IdeaOutcomeStatus.EXECUTION_TRAP: "execution_trap",
    IdeaOutcomeStatus.COST_TRAP: "cost_trap",
    IdeaOutcomeStatus.FOLLOW_ON_OPPORTUNITY: "follow_on_opportunity",
    IdeaOutcomeStatus.IN_PROGRESS: "in_progress",
    IdeaOutcomeStatus.STALLED: "stalled",
}
_VERDICT_BONUS: dict[VerdictStatus, float] = {
    VerdictStatus.PASS: 0.07,
    VerdictStatus.PARTIAL: 0.0,
    VerdictStatus.FAIL: -0.08,
    VerdictStatus.SKIP: -0.02,
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _clip(value: str, limit: int = 220) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


@dataclass(slots=True)
class ExecutionFeedbackApplyResult:
    outcome: ExecutionOutcomeRecord
    idea: IdeaCandidate
    dossier: IdeaDossier
    preference_profile: FounderPreferenceProfile
    learning_summary: str


class ExecutionFeedbackService:
    def __init__(self, discovery_store: DiscoveryStore):
        self._store = discovery_store
        self._preferences = PreferenceModelService(discovery_store)

    def ingest_outcome_bundle(
        self,
        idea_id: str,
        outcome: ExecutionOutcomeBundle,
        *,
        actor: str = "autopilot",
        autopilot_project_id: str | None = None,
        autopilot_project_name: str | None = None,
        approvals_count: int | None = None,
        shipped_experiment_count: int | None = None,
        autopilot_payload: dict[str, Any] | None = None,
    ) -> ExecutionFeedbackApplyResult:
        dossier = self._store.get_dossier(idea_id)
        if dossier is None:
            raise KeyError(f"Unknown idea id: {idea_id}")
        if outcome.idea_id != idea_id:
            raise ValueError(f"Execution outcome idea_id mismatch: expected {idea_id}, got {outcome.idea_id}")
        if (
            dossier.execution_brief_candidate is not None
            and outcome.brief_id.strip()
            and outcome.brief_id != dossier.execution_brief_candidate.brief_id
        ):
            raise ValueError(
                "Execution outcome brief_id does not match the current discovery handoff candidate."
            )

        payload = dict(autopilot_payload or {})
        record = self._build_record(
            outcome,
            autopilot_project_id=autopilot_project_id,
            autopilot_project_name=autopilot_project_name,
            approvals_count=approvals_count,
            shipped_experiment_count=shipped_experiment_count,
            autopilot_payload=payload,
        )
        scorecard = self._score_execution(dossier, record)
        profile, preference_delta = self._apply_outcome_to_preferences(dossier, record)

        self._store.record_execution_outcome(idea_id, record)
        self._store.update_idea(idea_id, self._build_idea_patch(dossier, record, scorecard))
        profile.updated_at = record.ingested_at
        self._store.save_preference_profile(profile)

        learning_summary = self._learning_summary(record)
        self._store.add_decision(
            idea_id,
            IdeaDecisionCreateRequest(
                decision_type=f"execution_feedback_{record.status.value}",
                rationale=learning_summary,
                actor=actor,
                metadata={
                    "outcome_id": record.outcome_id,
                    "brief_id": record.brief_id,
                    "status": record.status.value,
                    "verdict": record.verdict.value,
                    "autopilot_project_id": record.autopilot_project_id,
                    "approvals_count": record.approvals_count,
                    "shipped_experiment_count": record.shipped_experiment_count,
                    "preference_delta": preference_delta,
                },
            ),
        )
        self._store.add_timeline_event(
            idea_id,
            DossierTimelineEventCreateRequest(
                stage="executed",
                title=f"Execution outcome: {record.status.value}",
                detail=learning_summary,
                metadata={
                    "outcome_id": record.outcome_id,
                    "project_id": record.autopilot_project_id,
                    "verdict": record.verdict.value,
                    "stories_attempted": record.stories_attempted,
                    "stories_passed": record.stories_passed,
                    "stories_failed": record.stories_failed,
                    "bugs_found": record.bugs_found,
                    "total_cost_usd": round(record.total_cost_usd, 4),
                    "total_duration_seconds": round(record.total_duration_seconds, 2),
                    "approvals_count": record.approvals_count,
                    "shipped_experiment_count": record.shipped_experiment_count,
                },
            ),
        )

        updated_idea = self._store.get_idea(idea_id) or dossier.idea
        updated_dossier = self._store.get_dossier(idea_id) or dossier
        return ExecutionFeedbackApplyResult(
            outcome=record,
            idea=updated_idea,
            dossier=updated_dossier,
            preference_profile=profile,
            learning_summary=learning_summary,
        )

    def list_outcomes(self, idea_id: str, limit: int = 20) -> list[ExecutionOutcomeRecord]:
        return self._store.list_execution_outcomes(idea_id, limit=limit)

    def _build_record(
        self,
        outcome: ExecutionOutcomeBundle,
        *,
        autopilot_project_id: str | None,
        autopilot_project_name: str | None,
        approvals_count: int | None,
        shipped_experiment_count: int | None,
        autopilot_payload: dict[str, Any],
    ) -> ExecutionOutcomeRecord:
        project_id = autopilot_project_id or self._string_from_payload(
            autopilot_payload,
            "project_id",
            "project.project_id",
            "project.id",
        )
        project_name = autopilot_project_name or self._string_from_payload(
            autopilot_payload,
            "project_name",
            "project.project_name",
            "project.name",
        )
        approval_total = approvals_count
        if approval_total is None:
            approval_total = self._int_from_payload(
                autopilot_payload,
                "approvals_count",
                "approval_count",
                "project.approvals_count",
            )
        experiment_total = shipped_experiment_count
        if experiment_total is None:
            experiment_total = self._int_from_payload(
                autopilot_payload,
                "shipped_experiment_count",
                "experiment_count",
                "project.shipped_experiment_count",
            )
            experiment_total = max(experiment_total or 0, len(outcome.shipped_artifacts))
        return ExecutionOutcomeRecord(
            outcome_id=outcome.outcome_id,
            brief_id=outcome.brief_id,
            idea_id=outcome.idea_id,
            status=outcome.status,
            verdict=outcome.verdict,
            total_cost_usd=float(outcome.total_cost_usd),
            total_duration_seconds=float(outcome.total_duration_seconds),
            stories_attempted=int(outcome.stories_attempted),
            stories_passed=int(outcome.stories_passed),
            stories_failed=int(outcome.stories_failed),
            bugs_found=int(outcome.bugs_found),
            critic_pass_rate=_clamp(float(outcome.critic_pass_rate), 0.0, 1.0),
            approvals_count=max(int(approval_total or 0), 0),
            shipped_experiment_count=max(int(experiment_total or 0), 0),
            shipped_artifacts=list(outcome.shipped_artifacts),
            failure_modes=list(outcome.failure_modes),
            lessons_learned=list(outcome.lessons_learned),
            evidence_bundle=self._bundle_candidate(outcome.evidence, outcome.idea_id),
            autopilot_project_id=project_id,
            autopilot_project_name=project_name,
            autopilot_payload=autopilot_payload,
            created_at=outcome.created_at,
            ingested_at=_utcnow(),
        )

    def _score_execution(self, dossier: IdeaDossier, record: ExecutionOutcomeRecord) -> dict[str, float]:
        idea = dossier.idea
        budget_tier = (
            dossier.execution_brief_candidate.budget_tier
            if dossier.execution_brief_candidate is not None
            else BudgetTier.MEDIUM
        )
        effort = (
            dossier.execution_brief_candidate.effort
            if dossier.execution_brief_candidate is not None
            else EffortEstimate.MEDIUM
        )
        budget_baseline = _BUDGET_BASELINES_USD.get(budget_tier, _BUDGET_BASELINES_USD[BudgetTier.MEDIUM])
        duration_baseline = _EFFORT_BASELINES_SEC.get(effort, _EFFORT_BASELINES_SEC[EffortEstimate.MEDIUM])
        attempted = max(record.stories_attempted, 1)
        success_ratio = _clamp(record.stories_passed / attempted, 0.0, 1.0)
        ship_signal = _clamp(
            (len(record.shipped_artifacts) + (record.shipped_experiment_count * 0.5)) / attempted,
            0.0,
            1.0,
        )
        approval_signal = _clamp(record.approvals_count / attempted, 0.0, 1.0)
        bug_pressure = _clamp(record.bugs_found / attempted, 0.0, 1.5)
        cost_pressure = max(record.total_cost_usd / max(budget_baseline, 1.0), 0.0)
        duration_pressure = max(record.total_duration_seconds / max(duration_baseline, 1.0), 0.0)
        believability_target = _clamp(
            0.48
            + _STATUS_BASE.get(record.status, 0.0)
            + ((success_ratio - 0.5) * 0.24)
            + _VERDICT_BONUS.get(record.verdict, 0.0)
            + ((record.critic_pass_rate - 0.5) * 0.18)
            + (ship_signal * 0.12)
            + (approval_signal * 0.05)
            - (bug_pressure * 0.14)
            - (max(0.0, cost_pressure - 1.0) * 0.12)
            - (max(0.0, duration_pressure - 1.0) * 0.08),
            0.0,
            1.0,
        )
        rank_target = _clamp(
            0.45
            + (_STATUS_BASE.get(record.status, 0.0) * 0.7)
            + (success_ratio * 0.2)
            + (ship_signal * 0.1)
            - (bug_pressure * 0.1)
            - (max(0.0, cost_pressure - 1.0) * 0.1),
            0.0,
            1.0,
        )
        new_belief = round(_clamp((idea.belief_score * 0.55) + (believability_target * 0.45), 0.0, 1.0), 4)
        new_rank = round(_clamp((idea.rank_score * 0.6) + (rank_target * 0.4), 0.0, 1.0), 4)
        return {
            "belief_score": new_belief,
            "rank_score": new_rank,
            "belief_delta": round(new_belief - float(idea.belief_score), 4),
            "rank_delta": round(new_rank - float(idea.rank_score), 4),
            "execution_success_ratio": round(success_ratio, 4),
            "execution_shipping_score": round(ship_signal, 4),
            "execution_approval_score": round(approval_signal, 4),
            "execution_bug_pressure": round(bug_pressure, 4),
            "execution_cost_pressure": round(cost_pressure, 4),
            "execution_duration_pressure": round(duration_pressure, 4),
            "execution_critic_pass_rate": round(record.critic_pass_rate, 4),
        }

    def _apply_outcome_to_preferences(
        self,
        dossier: IdeaDossier,
        record: ExecutionOutcomeRecord,
    ) -> tuple[FounderPreferenceProfile, dict[str, float]]:
        profile = self._store.get_preference_profile().model_copy(deep=True)
        features = self._preferences._extract_features(dossier)
        weight = _STATUS_BASE.get(record.status, 0.0)
        delivery_multiplier = (
            0.65
            + (record.critic_pass_rate * 0.15)
            + (_clamp(record.stories_passed / max(record.stories_attempted, 1), 0.0, 1.0) * 0.15)
            - (_clamp(record.bugs_found / max(record.stories_attempted, 1), 0.0, 1.0) * 0.08)
        )
        signed = weight * _clamp(delivery_multiplier, 0.2, 1.0)
        delta: dict[str, float] = {}

        for domain in features.domains:
            previous = float(profile.domain_weights.get(domain, 0.0))
            profile.domain_weights[domain] = round(_clamp(previous + (0.14 * signed), -2.0, 2.0), 4)
            delta[f"domain:{domain}"] = round(profile.domain_weights[domain] - previous, 4)
        for market in features.markets:
            previous = float(profile.market_weights.get(market, 0.0))
            profile.market_weights[market] = round(_clamp(previous + (0.1 * signed), -2.0, 2.0), 4)
            delta[f"market:{market}"] = round(profile.market_weights[market] - previous, 4)
        if features.buyer in {"b2b", "b2c"}:
            previous = float(profile.buyer_preferences.get(features.buyer, 0.0))
            profile.buyer_preferences[features.buyer] = round(_clamp(previous + (0.1 * signed), -2.0, 2.0), 4)
            delta[f"buyer:{features.buyer}"] = round(profile.buyer_preferences[features.buyer] - previous, 4)

        complexity_before = float(profile.preferred_complexity)
        complexity_target = features.complexity if signed >= 0 else 1.0 - features.complexity
        profile.preferred_complexity = round(
            _clamp(complexity_before + ((complexity_target - complexity_before) * (0.18 if signed >= 0 else 0.12)), 0.0, 1.0),
            4,
        )
        delta["preferred_complexity"] = round(profile.preferred_complexity - complexity_before, 4)

        ai_before = float(profile.ai_necessity_preference)
        ai_target = features.ai_necessity if signed >= 0 else 1.0 - features.ai_necessity
        profile.ai_necessity_preference = round(
            _clamp(ai_before + ((ai_target - ai_before) * (0.2 if signed >= 0 else 0.11)), 0.0, 1.0),
            4,
        )
        delta["ai_necessity_preference"] = round(profile.ai_necessity_preference - ai_before, 4)
        return profile, delta

    def _build_idea_patch(
        self,
        dossier: IdeaDossier,
        record: ExecutionOutcomeRecord,
        scorecard: dict[str, float],
    ) -> IdeaUpdateRequest:
        idea = dossier.idea
        latest_scorecard = {
            **idea.latest_scorecard,
            "execution_total_cost_usd": round(record.total_cost_usd, 4),
            "execution_total_duration_seconds": round(record.total_duration_seconds, 2),
            "execution_stories_attempted": float(record.stories_attempted),
            "execution_stories_passed": float(record.stories_passed),
            "execution_stories_failed": float(record.stories_failed),
            "execution_bugs_found": float(record.bugs_found),
            "execution_approvals_count": float(record.approvals_count),
            "execution_shipped_experiment_count": float(record.shipped_experiment_count),
            **scorecard,
        }
        score_snapshots = [
            *idea.score_snapshots,
            IdeaScoreSnapshot(
                label=f"execution_feedback:{record.status.value}",
                value=scorecard["belief_score"],
                reason=self._learning_summary(record),
                created_at=record.ingested_at,
            ),
        ][-24:]
        reason_snapshots = [
            *idea.reason_snapshots,
            IdeaReasonSnapshot(
                category="execution_feedback",
                summary=_clip(
                    f"{record.status.value} via shipping feedback for {idea.title}.",
                    160,
                ),
                detail=_clip(
                    "; ".join([*record.lessons_learned[:2], *record.failure_modes[:2], *record.shipped_artifacts[:2]])
                    or self._learning_summary(record),
                    220,
                ),
                created_at=record.ingested_at,
            ),
        ][-24:]
        provenance = dict(idea.provenance or {})
        autopilot_meta = dict(provenance.get("autopilot") or {})
        if record.autopilot_project_id:
            autopilot_meta["project_id"] = record.autopilot_project_id
        if record.autopilot_project_name:
            autopilot_meta["project_name"] = record.autopilot_project_name
        if record.autopilot_payload:
            autopilot_meta["latest_payload"] = record.autopilot_payload
        if dossier.execution_brief_candidate is not None:
            autopilot_meta["brief_id"] = dossier.execution_brief_candidate.brief_id
        if autopilot_meta:
            provenance["autopilot"] = autopilot_meta
        provenance["execution_feedback"] = {
            "outcome_id": record.outcome_id,
            "brief_id": record.brief_id,
            "status": record.status.value,
            "verdict": record.verdict.value,
            "project_id": record.autopilot_project_id,
            "project_name": record.autopilot_project_name,
            "approvals_count": record.approvals_count,
            "shipped_experiment_count": record.shipped_experiment_count,
            "total_cost_usd": round(record.total_cost_usd, 4),
            "total_duration_seconds": round(record.total_duration_seconds, 2),
            "stories_attempted": record.stories_attempted,
            "stories_passed": record.stories_passed,
            "stories_failed": record.stories_failed,
            "bugs_found": record.bugs_found,
            "critic_pass_rate": round(record.critic_pass_rate, 4),
            "shipped_artifacts": record.shipped_artifacts,
            "failure_modes": record.failure_modes,
            "lessons_learned": record.lessons_learned,
        }
        return IdeaUpdateRequest(
            belief_score=scorecard["belief_score"],
            rank_score=scorecard["rank_score"],
            validation_state=_STATUS_TO_VALIDATION[record.status],
            latest_stage="executed",
            latest_scorecard=latest_scorecard,
            score_snapshots=score_snapshots,
            reason_snapshots=reason_snapshots,
            provenance=provenance,
        )

    def _learning_summary(self, record: ExecutionOutcomeRecord) -> str:
        attempted = max(record.stories_attempted, 1)
        pass_rate = round((record.stories_passed / attempted) * 100)
        learning = record.lessons_learned[:2] or record.failure_modes[:2] or record.shipped_artifacts[:2]
        suffix = f" Key learning: {'; '.join(_clip(item, 90) for item in learning)}." if learning else ""
        return _clip(
            (
                f"{record.status.value} with {record.stories_passed}/{record.stories_attempted} stories passing, "
                f"{pass_rate}% delivery pass rate, critic pass {round(record.critic_pass_rate * 100)}%, "
                f"{record.bugs_found} bugs, and ${record.total_cost_usd:.2f} spend.{suffix}"
            ),
            240,
        )

    def _bundle_candidate(self, evidence: EvidenceBundle | None, idea_id: str) -> EvidenceBundleCandidate | None:
        if evidence is None:
            return None
        return EvidenceBundleCandidate(
            bundle_id=evidence.bundle_id,
            parent_id=evidence.parent_id or idea_id,
            items=[
                EvidenceItemRecord(
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
                for item in evidence.items
            ],
            overall_confidence=evidence.overall_confidence,
            created_at=evidence.created_at,
            updated_at=evidence.updated_at,
        )

    def _string_from_payload(self, payload: dict[str, Any], *paths: str) -> str | None:
        for path in paths:
            value = payload
            for segment in path.split("."):
                if not isinstance(value, dict):
                    value = None
                    break
                value = value.get(segment)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _int_from_payload(self, payload: dict[str, Any], *paths: str) -> int:
        for path in paths:
            value: Any = payload
            for segment in path.split("."):
                if not isinstance(value, dict):
                    value = None
                    break
                value = value.get(segment)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, list):
                return len(value)
        return 0


def get_execution_feedback_service(db_path: str, discovery_store: DiscoveryStore) -> ExecutionFeedbackService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(normalized)
        if service is None:
            service = ExecutionFeedbackService(discovery_store)
            _SERVICE_CACHE[normalized] = service
        return service


def clear_execution_feedback_service_cache() -> None:
    with _SERVICE_CACHE_LOCK:
        _SERVICE_CACHE.clear()
