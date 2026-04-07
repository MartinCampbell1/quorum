"""Recurring discovery routines and fresh-cycle scheduling heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from orchestrator.discovery_models import (
    DiscoveryDailyDigest,
    DiscoveryDailyDigestIdea,
    DiscoveryDailyDigestRoutineSummary,
    DiscoveryDaemonAlert,
    DiscoveryDaemonCheckpoint,
    DiscoveryInboxItem,
    DiscoveryRoutineState,
    DossierTimelineEventCreateRequest,
    IdeaDossier,
    IdeaUpdateRequest,
)
from orchestrator.discovery_store import DiscoveryStore


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def compute_next_due(last_run_at: datetime | None, cadence_minutes: int, *, now: datetime | None = None) -> datetime:
    anchor = _normalize_dt(last_run_at) or now or _utcnow()
    return anchor + timedelta(minutes=max(1, cadence_minutes))


def default_routine_states(now: datetime | None = None) -> list[DiscoveryRoutineState]:
    current = now or _utcnow()
    return [
        DiscoveryRoutineState(
            routine_kind="hourly_refresh",
            label="Hourly refresh",
            cadence_minutes=60,
            max_ideas=6,
            stale_after_minutes=8 * 60,
            budget_limit_usd=0.6,
            next_due_at=current,
        ),
        DiscoveryRoutineState(
            routine_kind="daily_digest",
            label="Daily digest",
            cadence_minutes=24 * 60,
            max_ideas=5,
            stale_after_minutes=24 * 60,
            budget_limit_usd=0.9,
            next_due_at=current,
        ),
        DiscoveryRoutineState(
            routine_kind="overnight_queue",
            label="Overnight queue",
            cadence_minutes=8 * 60,
            max_ideas=8,
            stale_after_minutes=18 * 60,
            budget_limit_usd=1.8,
            next_due_at=current,
        ),
    ]


@dataclass
class RoutineExecutionResult:
    summary: str
    touched_idea_ids: list[str] = field(default_factory=list)
    checkpoints: list[DiscoveryDaemonCheckpoint] = field(default_factory=list)
    inbox_items: list[DiscoveryInboxItem] = field(default_factory=list)
    alerts: list[DiscoveryDaemonAlert] = field(default_factory=list)
    digest: DiscoveryDailyDigest | None = None
    budget_used_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def _dossier_priority(dossier: IdeaDossier) -> float:
    idea = dossier.idea
    recency_bonus = 0.0
    updated_at = _normalize_dt(idea.updated_at)
    if updated_at:
        age_hours = max(0.0, (_utcnow() - updated_at).total_seconds() / 3600)
        recency_bonus = max(0.0, 0.22 - min(0.22, age_hours / 240))
    evidence_bonus = min(0.12, len(dossier.observations) * 0.015)
    brief_bonus = 0.08 if dossier.execution_brief_candidate else 0.0
    simulation_bonus = 0.05 if dossier.simulation_report or dossier.market_simulation_report else 0.0
    return float(idea.rank_score) + (0.55 * float(idea.belief_score)) + recency_bonus + evidence_bonus + brief_bonus + simulation_bonus


def _idea_reason(dossier: IdeaDossier) -> str:
    parts: list[str] = []
    if dossier.idea.rank_score:
        parts.append(f"rank {dossier.idea.rank_score:.2f}")
    if dossier.idea.belief_score:
        parts.append(f"belief {dossier.idea.belief_score:.2f}")
    if dossier.observations:
        parts.append(f"{len(dossier.observations)} observations")
    if dossier.execution_brief_candidate:
        parts.append("brief candidate ready")
    if dossier.idea.swipe_state in {"yes", "now"}:
        parts.append(f"founder={dossier.idea.swipe_state}")
    return ", ".join(parts) or "active discovery candidate"


def _digest_idea(dossier: IdeaDossier, reason: str | None = None) -> DiscoveryDailyDigestIdea:
    return DiscoveryDailyDigestIdea(
        idea_id=dossier.idea.idea_id,
        title=dossier.idea.title,
        latest_stage=dossier.idea.latest_stage,
        rank_score=dossier.idea.rank_score,
        belief_score=dossier.idea.belief_score,
        reason=reason or _idea_reason(dossier),
        tags=list(dossier.idea.topic_tags[:5]),
    )


def _staleness_reason(dossier: IdeaDossier, now: datetime, stale_after_minutes: int) -> str:
    refreshed_at = _normalize_dt(dossier.idea.last_evidence_refresh_at) or _normalize_dt(dossier.idea.updated_at)
    if refreshed_at is None:
        return "No evidence refresh recorded yet."
    age_minutes = max(0.0, (now - refreshed_at).total_seconds() / 60)
    if age_minutes >= stale_after_minutes:
        return f"Evidence refresh is {int(age_minutes // 60)}h old."
    if dossier.idea.swipe_state == "maybe":
        return "Maybe queue idea should be revisited with fresh context."
    return "Top discovery candidate checked for freshness."


def _estimate_overnight_cost(dossier: IdeaDossier) -> float:
    cost = 0.14
    cost += min(0.18, len(dossier.observations) * 0.025)
    cost += 0.08 if dossier.execution_brief_candidate is None else 0.03
    cost += 0.1 if dossier.market_simulation_report is None else 0.02
    if dossier.idea.swipe_state == "now":
        cost += 0.06
    return round(cost, 2)


class DiscoveryRoutineScheduler:
    """Deterministic routine runner for the discovery daemon."""

    def __init__(self, discovery_store: DiscoveryStore):
        self._store = discovery_store

    def run_routine(
        self,
        routine: DiscoveryRoutineState,
        *,
        cycle_id: str,
        fresh_session_id: str,
        now: datetime | None = None,
    ) -> RoutineExecutionResult:
        current = now or _utcnow()
        if routine.routine_kind == "hourly_refresh":
            return self._run_hourly_refresh(routine, cycle_id=cycle_id, fresh_session_id=fresh_session_id, now=current)
        if routine.routine_kind == "daily_digest":
            return self._run_daily_digest(routine, cycle_id=cycle_id, fresh_session_id=fresh_session_id, now=current)
        return self._run_overnight_queue(routine, cycle_id=cycle_id, fresh_session_id=fresh_session_id, now=current)

    def _active_dossiers(self, limit: int = 64) -> list[IdeaDossier]:
        dossiers = self._store.list_dossiers(limit=limit, include_archived=False)
        return sorted(dossiers, key=_dossier_priority, reverse=True)

    def _stale_candidates(self, routine: DiscoveryRoutineState, now: datetime) -> list[IdeaDossier]:
        stale: list[IdeaDossier] = []
        for dossier in self._active_dossiers(limit=max(24, routine.max_ideas * 4)):
            refreshed_at = _normalize_dt(dossier.idea.last_evidence_refresh_at) or _normalize_dt(dossier.idea.updated_at)
            if refreshed_at is None:
                stale.append(dossier)
                continue
            age_minutes = max(0.0, (now - refreshed_at).total_seconds() / 60)
            if age_minutes >= routine.stale_after_minutes or dossier.idea.swipe_state == "maybe":
                stale.append(dossier)
        return stale

    def _select_overnight_queue(self, routine: DiscoveryRoutineState) -> tuple[list[tuple[IdeaDossier, float]], float]:
        budget_used = 0.0
        picked: list[tuple[IdeaDossier, float]] = []
        for dossier in self._active_dossiers(limit=40):
            if dossier.idea.validation_state == "archived":
                continue
            if dossier.idea.swipe_state == "pass":
                continue
            estimated_cost = _estimate_overnight_cost(dossier)
            if picked and budget_used + estimated_cost > routine.budget_limit_usd:
                continue
            budget_used += estimated_cost
            picked.append((dossier, estimated_cost))
            if len(picked) >= routine.max_ideas or budget_used >= routine.budget_limit_usd:
                break
        return picked, round(budget_used, 2)

    def _run_hourly_refresh(
        self,
        routine: DiscoveryRoutineState,
        *,
        cycle_id: str,
        fresh_session_id: str,
        now: datetime,
    ) -> RoutineExecutionResult:
        candidates = self._stale_candidates(routine, now)[: routine.max_ideas]
        touched: list[str] = []
        checkpoints: list[DiscoveryDaemonCheckpoint] = [
            DiscoveryDaemonCheckpoint(
                label="Fresh cycle started",
                detail="Hourly daemon refresh opened a brand-new context window.",
                metadata={"cycle_id": cycle_id, "fresh_session_id": fresh_session_id},
            )
        ]
        inbox_items: list[DiscoveryInboxItem] = []
        for dossier in candidates:
            reason = _staleness_reason(dossier, now, routine.stale_after_minutes)
            touched.append(dossier.idea.idea_id)
            provenance = dict(dossier.idea.provenance or {})
            daemon_meta = dict(provenance.get("daemon") or {})
            daemon_meta["last_hourly_refresh_cycle"] = cycle_id
            daemon_meta["last_hourly_refresh_at"] = now.isoformat()
            provenance["daemon"] = daemon_meta
            self._store.update_idea(
                dossier.idea.idea_id,
                IdeaUpdateRequest(
                    provenance=provenance,
                    last_evidence_refresh_at=now,
                ),
            )
            self._store.add_timeline_event(
                dossier.idea.idea_id,
                DossierTimelineEventCreateRequest(
                    stage=dossier.idea.latest_stage,
                    title="Daemon hourly refresh",
                    detail=reason,
                    metadata={
                        "routine_kind": routine.routine_kind,
                        "cycle_id": cycle_id,
                        "fresh_session_id": fresh_session_id,
                    },
                ),
            )
            inbox_items.append(
                DiscoveryInboxItem(
                    kind="refresh_review",
                    title=f"Review refreshed idea: {dossier.idea.title}",
                    detail=reason,
                    idea_id=dossier.idea.idea_id,
                    metadata={
                        "routine_kind": routine.routine_kind,
                        "cycle_id": cycle_id,
                    },
                )
            )
            checkpoints.append(
                DiscoveryDaemonCheckpoint(
                    label=dossier.idea.title,
                    detail=reason,
                    metadata={"idea_id": dossier.idea.idea_id},
                )
            )
        summary = (
            f"Refreshed {len(touched)} stale or maybe-queue ideas with fresh context."
            if touched
            else "No stale discovery ideas needed an hourly refresh."
        )
        return RoutineExecutionResult(
            summary=summary,
            touched_idea_ids=touched,
            checkpoints=checkpoints,
            inbox_items=inbox_items,
            metadata={"fresh_session_policy": "new_cycle_per_run"},
        )

    def _run_daily_digest(
        self,
        routine: DiscoveryRoutineState,
        *,
        cycle_id: str,
        fresh_session_id: str,
        now: datetime,
    ) -> RoutineExecutionResult:
        dossiers = self._active_dossiers(limit=max(12, routine.max_ideas * 3))
        top = dossiers[: routine.max_ideas]
        stale_count = len(self._stale_candidates(routine, now))
        overnight_preview, overnight_budget = self._select_overnight_queue(
            DiscoveryRoutineState(
                routine_kind="overnight_queue",
                label="Overnight queue",
                max_ideas=min(4, routine.max_ideas),
                cadence_minutes=8 * 60,
                stale_after_minutes=18 * 60,
                budget_limit_usd=max(0.8, routine.budget_limit_usd),
            )
        )
        highlights = [
            f"{len(top)} high-signal ideas are still active in discovery.",
            f"{stale_count} ideas crossed the freshness threshold and should be revisited soon.",
            f"Overnight queue preview fits inside ~${overnight_budget:.2f} of budgeted refresh work.",
        ]
        alerts = []
        if stale_count >= max(3, routine.max_ideas):
            alerts.append("Freshness debt is building up across the active queue.")
        digest = DiscoveryDailyDigest(
            digest_date=now.date().isoformat(),
            headline=f"Daily discovery digest for {now.date().isoformat()}",
            highlights=highlights,
            alerts=alerts,
            top_ideas=[_digest_idea(dossier) for dossier in top],
            overnight_queue=[_digest_idea(dossier, reason=f"overnight est. ${cost:.2f}") for dossier, cost in overnight_preview],
            routine_summaries=[
                DiscoveryDailyDigestRoutineSummary(
                    routine_kind="daily_digest",
                    headline="Compiled a founder-facing digest from fresh portfolio state.",
                    touched_count=len(top),
                    inbox_count=1,
                    checkpoint_count=2,
                ),
                DiscoveryDailyDigestRoutineSummary(
                    routine_kind="overnight_queue",
                    headline="Prepared an overnight refresh queue preview.",
                    touched_count=len(overnight_preview),
                    budget_used_usd=overnight_budget,
                ),
                DiscoveryDailyDigestRoutineSummary(
                    routine_kind="hourly_refresh",
                    headline=f"{stale_count} ideas are currently freshness candidates.",
                    touched_count=stale_count,
                ),
            ],
            metadata={
                "cycle_id": cycle_id,
                "fresh_session_id": fresh_session_id,
            },
        )
        inbox_item = DiscoveryInboxItem(
            kind="daily_digest",
            title="Daily discovery digest ready",
            detail=digest.headline,
            digest_id=digest.digest_id,
            metadata={"cycle_id": cycle_id},
        )
        digest.inbox_item_ids.append(inbox_item.item_id)
        checkpoints = [
            DiscoveryDaemonCheckpoint(
                label="Digest started",
                detail="Compiled a daily founder digest from fresh portfolio state.",
                metadata={"cycle_id": cycle_id},
            ),
            DiscoveryDaemonCheckpoint(
                label="Digest completed",
                detail=digest.headline,
                metadata={"digest_id": digest.digest_id},
            ),
        ]
        for dossier in top[:3]:
            self._store.add_timeline_event(
                dossier.idea.idea_id,
                DossierTimelineEventCreateRequest(
                    stage=dossier.idea.latest_stage,
                    title="Included in daily digest",
                    detail=digest.headline,
                    metadata={"digest_id": digest.digest_id, "cycle_id": cycle_id},
                ),
            )
        return RoutineExecutionResult(
            summary=digest.headline,
            touched_idea_ids=[dossier.idea.idea_id for dossier in top[:3]],
            checkpoints=checkpoints,
            inbox_items=[inbox_item],
            digest=digest,
            alerts=[
                DiscoveryDaemonAlert(
                    severity="warning",
                    code="freshness_debt",
                    title="Freshness debt building",
                    detail=alerts[0],
                    metadata={"stale_count": stale_count},
                )
            ]
            if alerts
            else [],
            metadata={"fresh_session_policy": "new_cycle_per_run"},
        )

    def _run_overnight_queue(
        self,
        routine: DiscoveryRoutineState,
        *,
        cycle_id: str,
        fresh_session_id: str,
        now: datetime,
    ) -> RoutineExecutionResult:
        picked, budget_used = self._select_overnight_queue(routine)
        checkpoints = [
            DiscoveryDaemonCheckpoint(
                label="Overnight queue started",
                detail="Selected a budget-bounded queue using fresh portfolio state.",
                metadata={"cycle_id": cycle_id, "budget_limit_usd": routine.budget_limit_usd},
            )
        ]
        touched: list[str] = []
        queue_lines: list[str] = []
        for dossier, estimated_cost in picked:
            touched.append(dossier.idea.idea_id)
            queue_lines.append(f"{dossier.idea.title} (~${estimated_cost:.2f})")
            self._store.add_timeline_event(
                dossier.idea.idea_id,
                DossierTimelineEventCreateRequest(
                    stage=dossier.idea.latest_stage,
                    title="Queued for overnight daemon cycle",
                    detail=f"Budgeted for an offline refresh slot (~${estimated_cost:.2f}).",
                    metadata={
                        "routine_kind": routine.routine_kind,
                        "cycle_id": cycle_id,
                        "fresh_session_id": fresh_session_id,
                        "estimated_cost_usd": estimated_cost,
                    },
                ),
            )
            checkpoints.append(
                DiscoveryDaemonCheckpoint(
                    label=dossier.idea.title,
                    detail=f"Reserved overnight slot (~${estimated_cost:.2f}).",
                    metadata={"idea_id": dossier.idea.idea_id, "estimated_cost_usd": estimated_cost},
                )
            )
        inbox_item = DiscoveryInboxItem(
            kind="overnight_queue",
            title="Overnight queue refreshed",
            detail="; ".join(queue_lines[:4]) or "No ideas were selected for the overnight queue.",
            metadata={
                "cycle_id": cycle_id,
                "budget_used_usd": budget_used,
                "idea_ids": touched,
            },
        )
        summary = (
            f"Prepared {len(touched)} offline refresh candidates inside a ${budget_used:.2f} budget."
            if touched
            else "No overnight queue candidates cleared the current budget heuristics."
        )
        return RoutineExecutionResult(
            summary=summary,
            touched_idea_ids=touched,
            checkpoints=checkpoints,
            inbox_items=[inbox_item],
            budget_used_usd=budget_used,
            metadata={"fresh_session_policy": "new_cycle_per_run"},
        )
