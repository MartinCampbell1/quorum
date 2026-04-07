"""Persistent discovery daemon with fresh-cycle routines and health checks."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from orchestrator.discovery_models import (
    DossierTimelineEventCreateRequest,
    DiscoveryDaemonAlert,
    DiscoveryDaemonControlRequest,
    DiscoveryDaemonRun,
    DiscoveryDaemonStatus,
    DiscoveryDailyDigest,
    DiscoveryInboxActionRequest,
    DiscoveryInboxActionKind,
    DiscoveryInboxAgingBucket,
    DiscoveryInboxCompareOption,
    DiscoveryInboxDossierPreview,
    DiscoveryInboxEvidencePreview,
    DiscoveryInboxItem,
    DiscoveryInboxResponse,
    DiscoveryInboxResolveRequest,
    DiscoveryInboxSubjectKind,
    DiscoveryInterruptActionRequest,
    DiscoveryInterruptConfig,
    DiscoveryInterruptPayload,
    DiscoveryReviewEvent,
    DiscoveryRoutineState,
    ExecutionBriefCandidateUpsertRequest,
    IdeaDecisionCreateRequest,
    IdeaUpdateRequest,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.models import SessionStore
from orchestrator.scheduler import DiscoveryRoutineScheduler, compute_next_due, default_routine_states


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _clip(value: str | None, limit: int = 180) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _age_minutes(created_at: datetime, *, now: datetime) -> int:
    delta = max(now - created_at, timedelta())
    return int(delta.total_seconds() // 60)


def _aging_bucket(age_minutes: int) -> DiscoveryInboxAgingBucket:
    if age_minutes >= 24 * 60:
        return "stale"
    if age_minutes >= 8 * 60:
        return "aging"
    return "fresh"


class DiscoveryDaemonPersistence:
    """SQLite-backed persistence for daemon state, runs, digests, and inbox items."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daemon_state (
                    daemon_id TEXT PRIMARY KEY,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daemon_runs (
                    run_id TEXT PRIMARY KEY,
                    routine_kind TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daemon_runs_started ON daemon_runs(started_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daemon_digests (
                    digest_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daemon_digests_created ON daemon_digests(created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daemon_inbox (
                    item_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daemon_inbox_created ON daemon_inbox(created_at DESC)"
            )

    def _encode(self, value: Any) -> str:
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump(mode="json"), ensure_ascii=False)
        return json.dumps(value, ensure_ascii=False)

    def _decode(self, raw: str, cls):
        return cls.model_validate_json(raw)

    def load_state(self) -> DiscoveryDaemonStatus | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM daemon_state WHERE daemon_id = ?", ("discovery_daemon",)).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], DiscoveryDaemonStatus)

    def save_state(self, state: DiscoveryDaemonStatus) -> DiscoveryDaemonStatus:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daemon_state (daemon_id, updated_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    state.daemon_id,
                    time.time(),
                    self._encode(state),
                ),
            )
        return state

    def save_run(self, run: DiscoveryDaemonRun) -> DiscoveryDaemonRun:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daemon_runs (run_id, routine_kind, started_at, status, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.routine_kind,
                    run.started_at.timestamp(),
                    run.status,
                    self._encode(run),
                ),
            )
        return run

    def list_runs(self, limit: int = 20) -> list[DiscoveryDaemonRun]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM daemon_runs ORDER BY started_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode(row["payload_json"], DiscoveryDaemonRun) for row in rows]

    def list_active_runs(self) -> list[DiscoveryDaemonRun]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM daemon_runs WHERE status = 'running' ORDER BY started_at DESC"
            ).fetchall()
        return [self._decode(row["payload_json"], DiscoveryDaemonRun) for row in rows]

    def save_digest(self, digest: DiscoveryDailyDigest) -> DiscoveryDailyDigest:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daemon_digests (digest_id, created_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    digest.digest_id,
                    digest.created_at.timestamp(),
                    self._encode(digest),
                ),
            )
        return digest

    def list_digests(self, limit: int = 14) -> list[DiscoveryDailyDigest]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM daemon_digests ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 90)),),
            ).fetchall()
        return [self._decode(row["payload_json"], DiscoveryDailyDigest) for row in rows]

    def save_inbox_item(self, item: DiscoveryInboxItem) -> DiscoveryInboxItem:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daemon_inbox (item_id, created_at, status, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    item.item_id,
                    item.created_at.timestamp(),
                    item.status,
                    self._encode(item),
                ),
            )
        return item

    def list_inbox(self, *, limit: int = 50, status: str | None = "open") -> list[DiscoveryInboxItem]:
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT payload_json FROM daemon_inbox WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, max(1, min(limit, 500))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM daemon_inbox ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 500)),),
                ).fetchall()
        return [self._decode(row["payload_json"], DiscoveryInboxItem) for row in rows]

    def get_inbox_item(self, item_id: str) -> DiscoveryInboxItem | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM daemon_inbox WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], DiscoveryInboxItem)

    def resolve_inbox_item(self, item_id: str, request: DiscoveryInboxResolveRequest | None = None) -> DiscoveryInboxItem | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM daemon_inbox WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                return None
            item = self._decode(row["payload_json"], DiscoveryInboxItem)
            item.status = request.status if request else "resolved"
            conn.execute(
                "UPDATE daemon_inbox SET status = ?, payload_json = ? WHERE item_id = ?",
                (item.status, self._encode(item), item_id),
            )
        return item


class DiscoveryDaemonService:
    """Fresh-cycle daemon runner for discovery routines."""

    def __init__(self, db_path: str | Path, discovery_store: DiscoveryStore, session_store: SessionStore):
        self._db = DiscoveryDaemonPersistence(db_path)
        self._discovery_store = discovery_store
        self._session_store = session_store
        self._scheduler = DiscoveryRoutineScheduler(discovery_store)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _initial_state(self) -> DiscoveryDaemonStatus:
        state = DiscoveryDaemonStatus()
        state.routines = default_routine_states()
        state.inbox_pending_count = len(self._db.list_inbox(limit=500, status="open"))
        digests = self._db.list_digests(limit=1)
        state.latest_digest_id = digests[0].digest_id if digests else None
        state.recent_runs = self._db.list_runs(limit=8)
        return state

    def _load_state(self) -> DiscoveryDaemonStatus:
        state = self._db.load_state()
        if state is None:
            state = self._initial_state()
            self._db.save_state(state)
        if not state.routines:
            state.routines = default_routine_states()
        return state

    def _save_state(self, state: DiscoveryDaemonStatus) -> DiscoveryDaemonStatus:
        state.inbox_pending_count = len(self._db.list_inbox(limit=500, status="open"))
        digests = self._db.list_digests(limit=1)
        state.latest_digest_id = digests[0].digest_id if digests else None
        state.recent_runs = self._db.list_runs(limit=8)
        state.alerts = self._build_alerts(state)
        return self._db.save_state(state)

    def _build_alerts(self, state: DiscoveryDaemonStatus, *, now: datetime | None = None) -> list[DiscoveryDaemonAlert]:
        current = now or _utcnow()
        alerts: list[DiscoveryDaemonAlert] = []
        if state.mode == "running":
            if not state.worker_heartbeat_at or (current - state.worker_heartbeat_at) > timedelta(seconds=max(120, state.loop_interval_sec * 3)):
                alerts.append(
                    DiscoveryDaemonAlert(
                        severity="critical",
                        code="stale_worker",
                        title="Daemon worker heartbeat is stale",
                        detail="The background loop has not reported a heartbeat recently.",
                    )
                )
        for routine in state.routines:
            if not routine.enabled or routine.next_due_at is None:
                continue
            if current > routine.next_due_at + timedelta(minutes=max(30, routine.cadence_minutes // 2)):
                alerts.append(
                    DiscoveryDaemonAlert(
                        severity="warning",
                        code="missed_scan",
                        title=f"Missed {routine.label.lower()} window",
                        detail=f"{routine.label} was due at {routine.next_due_at.isoformat()} and has not completed yet.",
                        metadata={"routine_kind": routine.routine_kind},
                    )
                )
        for run in self._db.list_active_runs():
            if (current - run.started_at) > timedelta(minutes=20):
                alerts.append(
                    DiscoveryDaemonAlert(
                        severity="warning",
                        code="stale_run",
                        title="Daemon run looks stale",
                        detail=f"{run.routine_kind} has been running since {run.started_at.isoformat()}.",
                        metadata={"run_id": run.run_id, "routine_kind": run.routine_kind},
                    )
                )
        return alerts[:8]

    @staticmethod
    def _subject_kind_for_item(item: DiscoveryInboxItem) -> DiscoveryInboxSubjectKind:
        if item.subject_kind != "daemon":
            return item.subject_kind
        if item.kind in {"refresh_review", "overnight_queue", "idea_review"}:
            return "idea"
        if item.kind == "debate_review":
            return "debate"
        if item.kind == "simulation_review":
            return "simulation"
        if item.kind == "handoff_review":
            return "handoff"
        if item.kind == "daily_digest":
            return "digest"
        return "daemon"

    def _build_compare_options(self, idea_id: str, topic_tags: list[str]) -> list[DiscoveryInboxCompareOption]:
        base_tags = set(tag for tag in topic_tags if tag)
        candidates: list[tuple[int, DiscoveryInboxCompareOption]] = []
        for candidate in self._discovery_store.list_ideas(limit=40):
            if candidate.idea_id == idea_id:
                continue
            overlap = sorted(base_tags.intersection(candidate.topic_tags))
            lineage = sorted(
                set(candidate.lineage_parent_ids).intersection({idea_id})
                | set(candidate.evolved_from).intersection({idea_id})
            )
            score = len(overlap) * 3 + len(lineage) * 4
            if score <= 0:
                continue
            reasons: list[str] = []
            if overlap:
                reasons.append(f"Shared tags: {', '.join(overlap[:2])}")
            if lineage:
                reasons.append("Linked through lineage")
            candidates.append(
                (
                    score,
                    DiscoveryInboxCompareOption(
                        idea_id=candidate.idea_id,
                        title=candidate.title,
                        latest_stage=candidate.latest_stage,
                        reason="; ".join(reasons),
                    ),
                )
            )
        candidates.sort(key=lambda item: (-item[0], item[1].title.lower()))
        return [item for _, item in candidates[:3]]

    def _build_dossier_preview(self, idea_id: str) -> DiscoveryInboxDossierPreview | None:
        dossier = self._discovery_store.get_dossier(idea_id)
        if dossier is None:
            return None
        latest_validation = dossier.validation_reports[-1] if dossier.validation_reports else None
        simulation_summary = None
        if dossier.market_simulation_report is not None:
            simulation_summary = _clip(dossier.market_simulation_report.executive_summary)
        elif dossier.simulation_report is not None:
            simulation_summary = _clip(dossier.simulation_report.summary_headline)
        elif dossier.execution_brief_candidate and dossier.execution_brief_candidate.simulation_summary:
            simulation_summary = _clip(dossier.execution_brief_candidate.simulation_summary)
        handoff_summary = None
        if dossier.execution_brief_candidate is not None:
            handoff_summary = _clip(
                dossier.execution_brief_candidate.prd_summary or dossier.execution_brief_candidate.title
            )
        debate_summary = None
        if latest_validation is not None:
            debate_summary = _clip(latest_validation.summary)
        elif dossier.explainability_context and dossier.explainability_context.judge_summary:
            debate_summary = _clip(dossier.explainability_context.judge_summary)
        return DiscoveryInboxDossierPreview(
            headline=dossier.idea.title,
            idea_summary=_clip(dossier.idea.summary or dossier.idea.thesis or dossier.idea.description),
            latest_stage=dossier.idea.latest_stage,
            rank_score=float(dossier.idea.rank_score or 0.0),
            belief_score=float(dossier.idea.belief_score or 0.0),
            evidence=DiscoveryInboxEvidencePreview(
                observations=[
                    _clip(observation.raw_text, 140)
                    for observation in reversed(dossier.observations[-3:])
                ],
                validations=[
                    _clip(report.summary, 120)
                    for report in reversed(dossier.validation_reports[-2:])
                ],
                timeline=[
                    _clip(
                        f"{event.title}: {event.detail}"
                        if event.detail
                        else event.title,
                        120,
                    )
                    for event in reversed(dossier.timeline[-3:])
                ],
            ),
            debate_summary=debate_summary,
            simulation_summary=simulation_summary,
            handoff_summary=handoff_summary,
            compare_options=self._build_compare_options(dossier.idea.idea_id, dossier.idea.topic_tags),
            raw_trace={
                "timeline_event_ids": [event.event_id for event in dossier.timeline[-3:]],
                "validation_report_ids": [report.report_id for report in dossier.validation_reports[-2:]],
                "simulation_report_id": (
                    dossier.simulation_report.report_id
                    if dossier.simulation_report is not None
                    else None
                ),
                "market_simulation_report_id": (
                    dossier.market_simulation_report.report_id
                    if dossier.market_simulation_report is not None
                    else None
                ),
                "execution_brief_id": (
                    dossier.execution_brief_candidate.brief_id
                    if dossier.execution_brief_candidate is not None
                    else None
                ),
            },
        )

    def _build_interrupt_payload(self, item: DiscoveryInboxItem) -> DiscoveryInterruptPayload:
        preview = item.dossier_preview
        action_label = {
            "idea": "Review idea next step",
            "debate": "Review debate verdict",
            "simulation": "Review simulation outcome",
            "handoff": "Approve execution handoff",
            "digest": "Acknowledge discovery digest",
            "daemon": item.title,
        }.get(item.subject_kind, item.title)
        summary = _clip(item.detail or (preview.idea_summary if preview else item.title), 180)
        description_parts = [part for part in [item.detail, preview.idea_summary if preview else None] if part]
        if item.subject_kind == "debate" and preview and preview.debate_summary:
            description_parts.append(f"Debate summary: {preview.debate_summary}")
        if item.subject_kind == "simulation" and preview and preview.simulation_summary:
            description_parts.append(f"Simulation summary: {preview.simulation_summary}")
        if item.subject_kind == "handoff" and preview and preview.handoff_summary:
            description_parts.append(f"Handoff brief: {preview.handoff_summary}")
        if preview and preview.evidence.observations:
            description_parts.append(f"Evidence preview: {preview.evidence.observations[0]}")
        return DiscoveryInterruptPayload(
            action_request=DiscoveryInterruptActionRequest(
                action=action_label,
                args={
                    "item_id": item.item_id,
                    "kind": item.kind,
                    "subject_kind": item.subject_kind,
                    "idea_id": item.idea_id,
                    "digest_id": item.digest_id,
                    "run_id": item.run_id,
                    "priority_score": item.priority_score,
                },
            ),
            config=DiscoveryInterruptConfig(
                allow_ignore=True,
                allow_respond=True,
                allow_edit=item.subject_kind in {"idea", "debate", "simulation", "handoff"},
                allow_accept=True,
                allow_compare=bool(preview and preview.compare_options),
            ),
            description="\n\n".join(_clip(part, 240) for part in description_parts[:4]),
            summary=summary,
        )

    def _hydrate_inbox_item(self, item: DiscoveryInboxItem, *, now: datetime | None = None) -> DiscoveryInboxItem:
        current = now or _utcnow()
        hydrated = item.model_copy(deep=True)
        hydrated.subject_kind = self._subject_kind_for_item(hydrated)
        hydrated.age_minutes = _age_minutes(hydrated.created_at, now=current)
        hydrated.aging_bucket = _aging_bucket(hydrated.age_minutes)
        if hydrated.idea_id:
            hydrated.dossier_preview = self._build_dossier_preview(hydrated.idea_id)
        if hydrated.priority_score <= 0 and hydrated.dossier_preview is not None:
            hydrated.priority_score = round(
                hydrated.dossier_preview.rank_score * 0.55
                + hydrated.dossier_preview.belief_score * 0.45,
                4,
            )
        hydrated.interrupt = self._build_interrupt_payload(hydrated)
        return hydrated

    def _build_inbox_summary(self, items: list[DiscoveryInboxItem]) -> DiscoveryInboxResponse:
        response = DiscoveryInboxResponse(items=items)
        for item in items:
            if item.status == "open":
                response.summary.open_count += 1
            else:
                response.summary.resolved_count += 1
            if item.aging_bucket == "stale":
                response.summary.stale_count += 1
            if (
                item.status == "open"
                and item.interrupt is not None
                and (
                    item.interrupt.config.allow_accept
                    or item.interrupt.config.allow_edit
                    or item.interrupt.config.allow_respond
                    or item.interrupt.config.allow_compare
                )
            ):
                response.summary.action_required_count += 1
            response.summary.kinds[item.kind] = response.summary.kinds.get(item.kind, 0) + 1
            response.summary.subject_kinds[item.subject_kind] = (
                response.summary.subject_kinds.get(item.subject_kind, 0) + 1
            )
        return response

    def _find_item_by_review_signature(
        self,
        review_key: str,
        review_revision: str,
    ) -> DiscoveryInboxItem | None:
        for existing in self._db.list_inbox(limit=500, status=None):
            if (
                str(existing.metadata.get("review_key") or "") == review_key
                and str(existing.metadata.get("review_revision") or "") == review_revision
            ):
                return existing
        return None

    def _has_open_subject_item(self, subject_kind: DiscoveryInboxSubjectKind, idea_id: str) -> bool:
        for existing in self._db.list_inbox(limit=500, status="open"):
            hydrated = self._hydrate_inbox_item(existing)
            if hydrated.idea_id == idea_id and hydrated.subject_kind == subject_kind:
                return True
        return False

    def _save_derived_review_item(
        self,
        dossier,
        *,
        subject_kind: DiscoveryInboxSubjectKind,
        kind: str,
        review_revision: str,
        title: str,
        detail: str,
        priority_score: float,
    ) -> DiscoveryInboxItem | None:
        review_key = f"{subject_kind}:{dossier.idea.idea_id}"
        if self._find_item_by_review_signature(review_key, review_revision) is not None:
            return None
        item = DiscoveryInboxItem(
            kind=kind,
            subject_kind=subject_kind,
            title=title,
            detail=detail,
            idea_id=dossier.idea.idea_id,
            priority_score=priority_score,
            due_at=_utcnow() + timedelta(hours=12),
            metadata={
                "source": "derived_review_queue",
                "review_key": review_key,
                "review_revision": review_revision,
            },
        )
        hydrated = self._hydrate_inbox_item(item)
        self._db.save_inbox_item(hydrated)
        return hydrated

    def _sync_review_queue(self) -> None:
        for dossier in self._discovery_store.list_dossiers(limit=120, include_archived=False):
            idea = dossier.idea
            if idea.validation_state == "archived":
                continue
            if dossier.execution_brief_candidate is not None and not self._has_open_subject_item("handoff", idea.idea_id):
                brief = dossier.execution_brief_candidate
                self._save_derived_review_item(
                    dossier,
                    subject_kind="handoff",
                    kind="handoff_review",
                    review_revision=brief.brief_id,
                    title=f"Approve handoff brief: {idea.title}",
                    detail=_clip(brief.prd_summary or brief.title),
                    priority_score=0.92 + min(0.06, idea.rank_score * 0.04),
                )
            if (
                dossier.simulation_report is not None or dossier.market_simulation_report is not None
            ) and not self._has_open_subject_item("simulation", idea.idea_id):
                report_id = (
                    dossier.market_simulation_report.report_id
                    if dossier.market_simulation_report is not None
                    else dossier.simulation_report.report_id
                )
                detail = (
                    dossier.market_simulation_report.executive_summary
                    if dossier.market_simulation_report is not None
                    else dossier.simulation_report.summary_headline
                )
                self._save_derived_review_item(
                    dossier,
                    subject_kind="simulation",
                    kind="simulation_review",
                    review_revision=report_id,
                    title=f"Review simulation outcome: {idea.title}",
                    detail=_clip(detail),
                    priority_score=0.86 + min(0.04, idea.belief_score * 0.04),
                )
            if dossier.validation_reports and not self._has_open_subject_item("debate", idea.idea_id):
                latest_report = dossier.validation_reports[-1]
                self._save_derived_review_item(
                    dossier,
                    subject_kind="debate",
                    kind="debate_review",
                    review_revision=latest_report.report_id,
                    title=f"Review debate verdict: {idea.title}",
                    detail=_clip(latest_report.summary),
                    priority_score=0.8 + min(0.05, idea.belief_score * 0.05),
                )
            if (
                not self._has_open_subject_item("idea", idea.idea_id)
                and (idea.rank_score >= 0.72 or idea.belief_score >= 0.62 or idea.swipe_state in {"yes", "now"})
            ):
                self._save_derived_review_item(
                    dossier,
                    subject_kind="idea",
                    kind="idea_review",
                    review_revision=idea.idea_id,
                    title=f"Review next move: {idea.title}",
                    detail=_clip(idea.summary or idea.thesis or idea.description or "High-signal idea waiting for founder review."),
                    priority_score=0.74 + min(0.08, idea.rank_score * 0.05 + idea.belief_score * 0.03),
                )

    def _edit_brief_from_inbox(self, idea_id: str, edited_fields: dict[str, str]) -> None:
        if not edited_fields:
            return
        dossier = self._discovery_store.get_dossier(idea_id)
        if dossier is None or dossier.execution_brief_candidate is None:
            return
        brief = dossier.execution_brief_candidate
        prd_summary = edited_fields.get("prd_summary") or edited_fields.get("summary") or brief.prd_summary
        title = edited_fields.get("title") or brief.title
        simulation_summary = edited_fields.get("simulation_summary") or brief.simulation_summary
        judge_summary = edited_fields.get("judge_summary") or brief.judge_summary
        request = ExecutionBriefCandidateUpsertRequest(
            title=title,
            prd_summary=prd_summary,
            acceptance_criteria=brief.acceptance_criteria,
            risks=brief.risks,
            recommended_tech_stack=brief.recommended_tech_stack,
            first_stories=brief.first_stories,
            repo_dna_snapshot=brief.repo_dna_snapshot,
            judge_summary=judge_summary,
            simulation_summary=simulation_summary,
            evidence_bundle_id=brief.evidence_bundle_id,
            confidence=brief.confidence,
            effort=brief.effort,
            urgency=brief.urgency,
            budget_tier=brief.budget_tier,
        )
        self._discovery_store.upsert_execution_brief_candidate(idea_id, request)

    def _apply_inbox_edits(self, item: DiscoveryInboxItem, request: DiscoveryInboxActionRequest) -> None:
        if not item.idea_id or not request.edited_fields:
            return
        if item.subject_kind in {"idea", "debate", "simulation"}:
            patch = {
                key: value
                for key, value in request.edited_fields.items()
                if key in {"title", "summary", "thesis", "description"}
            }
            if patch:
                self._discovery_store.update_idea(item.idea_id, IdeaUpdateRequest(**patch))
        elif item.subject_kind == "handoff":
            self._edit_brief_from_inbox(item.idea_id, request.edited_fields)

    def _record_inbox_action(
        self,
        item: DiscoveryInboxItem,
        event: DiscoveryReviewEvent,
        request: DiscoveryInboxActionRequest,
    ) -> None:
        if not item.idea_id:
            return
        detail_parts = [segment for segment in [request.note, request.response_text] if segment]
        if request.compare_target_idea_id:
            detail_parts.append(f"Compared against {request.compare_target_idea_id}")
        if request.edited_fields:
            detail_parts.append(
                "Edits: " + ", ".join(f"{key}={_clip(value, 60)}" for key, value in request.edited_fields.items())
            )
        title = {
            "accept": "Inbox review accepted",
            "ignore": "Inbox review ignored",
            "edit": "Inbox review edited",
            "compare": "Inbox review compared",
            "respond": "Inbox review responded",
            "resolve": "Inbox review resolved",
        }[request.action]
        self._discovery_store.add_decision(
            item.idea_id,
            IdeaDecisionCreateRequest(
                decision_type=f"inbox_{request.action}",
                rationale=_clip(" ".join(detail_parts) or item.title),
                actor=request.actor,
                metadata={
                    "item_id": item.item_id,
                    "kind": item.kind,
                    "subject_kind": item.subject_kind,
                    "response_text": request.response_text,
                    "edited_fields": request.edited_fields,
                    "compare_target_idea_id": request.compare_target_idea_id,
                    **request.metadata,
                },
            ),
        )
        self._discovery_store.add_timeline_event(
            item.idea_id,
            DossierTimelineEventCreateRequest(
                stage="handed_off" if item.subject_kind == "handoff" else self._discovery_store.get_idea(item.idea_id).latest_stage,
                title=title,
                detail=_clip(" ".join(detail_parts) or item.detail or item.title, 200),
                metadata={
                    "item_id": item.item_id,
                    "action": request.action,
                    "actor": request.actor,
                    "subject_kind": item.subject_kind,
                    "review_event_id": event.event_id,
                },
            ),
        )

    def act_on_inbox_item(
        self,
        item_id: str,
        request: DiscoveryInboxActionRequest,
    ) -> DiscoveryInboxItem | None:
        with self._lock:
            self._sync_review_queue()
            stored = self._db.get_inbox_item(item_id)
            if stored is None:
                return None
            item = self._hydrate_inbox_item(stored)
            if request.action == "edit":
                self._apply_inbox_edits(item, request)
                item = self._hydrate_inbox_item(self._db.get_inbox_item(item_id) or item)
            event = DiscoveryReviewEvent(
                action=request.action,
                actor=request.actor,
                note=_clip(request.note, 240),
                metadata={
                    "response_text": request.response_text,
                    "edited_fields": request.edited_fields,
                    "compare_target_idea_id": request.compare_target_idea_id,
                    **request.metadata,
                },
            )
            item.review_history.append(event)
            if request.action == "compare" and not bool(request.resolve):
                item.status = "open"
            else:
                item.status = "resolved"
                item.resolution = event
            self._record_inbox_action(item, event, request)
            saved = self._db.save_inbox_item(self._hydrate_inbox_item(item))
            self._save_state(self._load_state())
            return self._hydrate_inbox_item(saved)

    def _ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="discovery-daemon", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(1.0):
            with self._lock:
                state = self._load_state()
                if state.mode != "running":
                    continue
                now = _utcnow()
                state.worker_heartbeat_at = now
                state.last_tick_at = now
                state.next_tick_at = now + timedelta(seconds=state.loop_interval_sec)
                self._db.save_state(state)
            self.run_due_routines(now=now)

    def get_status(self) -> DiscoveryDaemonStatus:
        with self._lock:
            self._sync_review_queue()
            return self._save_state(self._load_state())

    def list_digests(self, limit: int = 14) -> list[DiscoveryDailyDigest]:
        return self._db.list_digests(limit=limit)

    def list_runs(self, limit: int = 20) -> list[DiscoveryDaemonRun]:
        return self._db.list_runs(limit=limit)

    def list_inbox(self, *, limit: int = 50, status: str | None = "open") -> list[DiscoveryInboxItem]:
        return self.get_inbox_feed(limit=limit, status=status).items

    def get_inbox_feed(self, *, limit: int = 50, status: str | None = "open") -> DiscoveryInboxResponse:
        with self._lock:
            self._sync_review_queue()
            current = _utcnow()
            visible = [
                self._hydrate_inbox_item(item, now=current)
                for item in self._db.list_inbox(limit=limit, status=status)
            ]
            all_items = [
                self._hydrate_inbox_item(item, now=current)
                for item in self._db.list_inbox(limit=500, status=None)
            ]
            self._save_state(self._load_state())
            response = self._build_inbox_summary(all_items)
            response.items = visible
            return response

    def get_inbox_item(self, item_id: str) -> DiscoveryInboxItem | None:
        with self._lock:
            self._sync_review_queue()
            item = self._db.get_inbox_item(item_id)
            if item is None:
                return None
            return self._hydrate_inbox_item(item)

    def resolve_inbox_item(self, item_id: str, request: DiscoveryInboxResolveRequest | None = None) -> DiscoveryInboxItem | None:
        with self._lock:
            self._sync_review_queue()
            item = self._db.resolve_inbox_item(item_id, request)
            if item is None:
                return None
            if item.status == "resolved":
                event = DiscoveryReviewEvent(
                    action="resolve",
                    actor="system",
                    note="Legacy resolve endpoint applied.",
                )
                item.review_history.append(event)
                item.resolution = event
                item = self._db.save_inbox_item(self._hydrate_inbox_item(item))
            self._save_state(self._load_state())
            return self._hydrate_inbox_item(item)

    def start(self) -> DiscoveryDaemonStatus:
        with self._lock:
            state = self._load_state()
            now = _utcnow()
            state.mode = "running"
            state.started_at = state.started_at or now
            state.worker_heartbeat_at = now
            state.last_tick_at = now
            state.next_tick_at = now + timedelta(seconds=state.loop_interval_sec)
            for routine in state.routines:
                if routine.next_due_at is None:
                    routine.next_due_at = now
            self._ensure_thread()
            return self._save_state(state)

    def pause(self) -> DiscoveryDaemonStatus:
        with self._lock:
            state = self._load_state()
            state.mode = "paused"
            state.next_tick_at = None
            return self._save_state(state)

    def resume(self) -> DiscoveryDaemonStatus:
        with self._lock:
            state = self._load_state()
            state.mode = "running"
            now = _utcnow()
            state.worker_heartbeat_at = now
            state.last_tick_at = now
            state.next_tick_at = now + timedelta(seconds=state.loop_interval_sec)
            self._ensure_thread()
            return self._save_state(state)

    def stop(self) -> DiscoveryDaemonStatus:
        with self._lock:
            state = self._load_state()
            state.mode = "stopped"
            state.next_tick_at = None
            self._save_state(state)
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        return self.get_status()

    def run_due_routines(self, *, now: datetime | None = None) -> DiscoveryDaemonStatus:
        current = now or _utcnow()
        with self._lock:
            state = self._load_state()
            for routine in state.routines:
                if not routine.enabled:
                    continue
                if routine.next_due_at and routine.next_due_at > current:
                    continue
                self._run_single_routine(state, routine.routine_kind, triggered_by="timer", now=current)
                state = self._load_state()
            state.worker_heartbeat_at = current
            state.last_tick_at = current
            state.next_tick_at = current + timedelta(seconds=state.loop_interval_sec) if state.mode == "running" else None
            return self._save_state(state)

    def tick(self) -> DiscoveryDaemonStatus:
        return self.run_due_routines(now=_utcnow())

    def run_routine(self, routine_kind: str) -> DiscoveryDaemonStatus:
        with self._lock:
            state = self._load_state()
            self._run_single_routine(state, routine_kind, triggered_by="manual", now=_utcnow())
            return self.get_status()

    def _run_single_routine(
        self,
        state: DiscoveryDaemonStatus,
        routine_kind: str,
        *,
        triggered_by: str,
        now: datetime,
    ) -> None:
        routine = next((item for item in state.routines if item.routine_kind == routine_kind), None)
        if routine is None:
            raise KeyError(routine_kind)
        run = DiscoveryDaemonRun(
            routine_kind=routine.routine_kind,
            status="running",
            triggered_by=triggered_by,
            started_at=now,
        )
        self._db.save_run(run)
        try:
            result = self._scheduler.run_routine(
                routine,
                cycle_id=run.cycle_id,
                fresh_session_id=run.fresh_session_id,
                now=now,
            )
            for item in result.inbox_items:
                item.run_id = run.run_id
                self._db.save_inbox_item(self._hydrate_inbox_item(item, now=now))
            if result.digest is not None:
                self._db.save_digest(result.digest)
            run.status = "completed"
            run.finished_at = _utcnow()
            run.summary = result.summary
            run.touched_idea_ids = result.touched_idea_ids
            run.digest_id = result.digest.digest_id if result.digest else None
            run.inbox_item_ids = [item.item_id for item in result.inbox_items]
            run.budget_used_usd = result.budget_used_usd
            run.checkpoints = result.checkpoints
            run.alerts = result.alerts
            run.metadata = {
                **result.metadata,
                "checkpoint_count": len(result.checkpoints),
            }
            routine.last_run_at = run.finished_at
            routine.last_status = run.status
            routine.last_run_id = run.run_id
            routine.summary = run.summary
            routine.next_due_at = compute_next_due(run.finished_at, routine.cadence_minutes, now=now)
            state.worker_heartbeat_at = run.finished_at
            state.last_tick_at = run.finished_at
            state.next_tick_at = run.finished_at + timedelta(seconds=state.loop_interval_sec) if state.mode == "running" else None
            self._db.save_run(run)
            self._save_state(state)
        except Exception as exc:
            run.status = "failed"
            run.finished_at = _utcnow()
            run.summary = f"{routine.label} failed: {type(exc).__name__}: {exc}"
            run.alerts = [
                DiscoveryDaemonAlert(
                    severity="critical",
                    code="routine_failed",
                    title=f"{routine.label} failed",
                    detail=str(exc),
                    metadata={"routine_kind": routine.routine_kind},
                )
            ]
            routine.last_run_at = run.finished_at
            routine.last_status = run.status
            routine.last_run_id = run.run_id
            routine.summary = run.summary
            routine.next_due_at = compute_next_due(run.finished_at, routine.cadence_minutes, now=now)
            self._db.save_run(run)
            self._save_state(state)
            raise


_DAEMON_CACHE: dict[str, DiscoveryDaemonService] = {}


def get_discovery_daemon_service(
    db_path: str | Path,
    discovery_store: DiscoveryStore,
    session_store: SessionStore,
) -> DiscoveryDaemonService:
    key = str(Path(db_path).resolve())
    service = _DAEMON_CACHE.get(key)
    if service is None:
        service = DiscoveryDaemonService(key, discovery_store, session_store)
        _DAEMON_CACHE[key] = service
    return service


def clear_discovery_daemon_cache() -> None:
    for service in list(_DAEMON_CACHE.values()):
        service.stop()
    _DAEMON_CACHE.clear()
