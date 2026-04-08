"""SQLite-backed discovery store for ideas, dossiers, and evidence."""

from __future__ import annotations

from collections import defaultdict
import json
import sqlite3
import threading
from uuid import uuid4
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from orchestrator.discovery_models import (
    DossierTimelineEvent,
    DossierTimelineEventCreateRequest,
    EvidenceBundleCandidate,
    EvidenceBundleUpsertRequest,
    ExecutionBriefApprovalUpdateRequest,
    ExecutionBriefCandidate,
    ExecutionBriefCandidateUpsertRequest,
    ExecutionOutcomeRecord,
    FounderPreferenceProfile,
    IdeaArchiveEntry,
    IdeaArchiveRequest,
    IdeaCandidate,
    IdeaCreateRequest,
    IdeaDecision,
    IdeaDecisionCreateRequest,
    IdeaDossier,
    IdeaReasonSnapshot,
    IdeaScoreSnapshot,
    MaybeQueueEntry,
    MarketSimulationReport,
    SimulationFeedbackReport,
    SwipeEventRecord,
    IdeaUpdateRequest,
    IdeaValidationReport,
    IdeaValidationReportCreateRequest,
    SourceObservation,
    SourceObservationCreateRequest,
)


T = TypeVar("T")

_STORE_CACHE: dict[str, "DiscoveryStore"] = {}
_STORE_CACHE_LOCK = threading.Lock()


class DiscoveryStore:
    """Persistent portfolio storage for discovery entities."""

    def __init__(self, db_path: str):
        self._db_path = Path(db_path).expanduser().resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_ideas (
                    idea_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    latest_stage TEXT NOT NULL,
                    swipe_state TEXT NOT NULL,
                    validation_state TEXT NOT NULL,
                    simulation_state TEXT NOT NULL,
                    rank_score REAL NOT NULL,
                    belief_score REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_observations (
                    observation_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_validation_reports (
                    report_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_decisions (
                    decision_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_archive_entries (
                    archive_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_timeline (
                    event_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_evidence_bundles (
                    bundle_id TEXT PRIMARY KEY,
                    parent_id TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_execution_briefs (
                    brief_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL UNIQUE,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_execution_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_simulation_reports (
                    idea_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_market_simulation_reports (
                    idea_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_swipe_events (
                    event_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_preference_profiles (
                    profile_key TEXT PRIMARY KEY,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_maybe_queue (
                    idea_id TEXT PRIMARY KEY,
                    due_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_ideas_updated_at ON discovery_ideas(updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_observations_idea_id ON discovery_observations(idea_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_validation_reports_idea_id ON discovery_validation_reports(idea_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_decisions_idea_id ON discovery_decisions(idea_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_timeline_idea_id ON discovery_timeline(idea_id, created_at ASC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_simulation_reports_updated_at ON discovery_simulation_reports(updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_market_simulation_reports_updated_at ON discovery_market_simulation_reports(updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_execution_outcomes_idea_id ON discovery_execution_outcomes(idea_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_swipe_events_idea_id ON discovery_swipe_events(idea_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_maybe_queue_due_at ON discovery_maybe_queue(due_at ASC)"
            )

    @staticmethod
    def _encode(model: T) -> str:
        if hasattr(model, "model_dump_json"):
            return model.model_dump_json()
        return json.dumps(model, ensure_ascii=False)

    @staticmethod
    def _decode(payload: str, cls: type[T]) -> T:
        return cls.model_validate_json(payload)

    @staticmethod
    def _timestamp(value) -> float:
        return value.timestamp()

    def _require_idea_conn(self, conn: sqlite3.Connection, idea_id: str) -> IdeaCandidate:
        row = conn.execute(
            "SELECT payload_json FROM discovery_ideas WHERE idea_id = ?",
            (idea_id,),
        ).fetchone()
        if not row:
            raise KeyError(f"Unknown idea id: {idea_id}")
        return self._decode(row["payload_json"], IdeaCandidate)

    def _save_idea_conn(self, conn: sqlite3.Connection, idea: IdeaCandidate) -> IdeaCandidate:
        idea.updated_at = idea.updated_at or idea.created_at
        conn.execute(
            """
            INSERT OR REPLACE INTO discovery_ideas (
                idea_id, title, latest_stage, swipe_state, validation_state, simulation_state,
                rank_score, belief_score, created_at, updated_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea.idea_id,
                idea.title,
                idea.latest_stage,
                idea.swipe_state,
                idea.validation_state,
                idea.simulation_state,
                float(idea.rank_score),
                float(idea.belief_score),
                self._timestamp(idea.created_at),
                self._timestamp(idea.updated_at),
                self._encode(idea),
            ),
        )
        return idea

    def _append_timeline_conn(
        self,
        conn: sqlite3.Connection,
        idea_id: str,
        request: DossierTimelineEventCreateRequest,
    ) -> DossierTimelineEvent:
        event = DossierTimelineEvent(
            stage=request.stage,
            title=request.title,
            detail=request.detail,
            metadata=request.metadata,
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO discovery_timeline (
                event_id, idea_id, stage, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                idea_id,
                event.stage,
                self._timestamp(event.created_at),
                self._encode(event),
            ),
        )
        return event

    def save_preference_profile(
        self,
        profile: FounderPreferenceProfile,
        profile_key: str = "founder_default",
    ) -> FounderPreferenceProfile:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_preference_profiles (
                    profile_key, updated_at, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    profile_key,
                    self._timestamp(profile.updated_at),
                    self._encode(profile),
                ),
            )
        return profile

    def _persist_execution_brief_candidate_conn(
        self,
        conn: sqlite3.Connection,
        idea_id: str,
        brief: ExecutionBriefCandidate,
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO discovery_execution_briefs (
                brief_id, idea_id, updated_at, payload_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                brief.brief_id,
                idea_id,
                self._timestamp(brief.updated_at),
                self._encode(brief),
            ),
        )

    def _save_execution_brief_candidate_conn(
        self,
        conn: sqlite3.Connection,
        idea: IdeaCandidate,
        brief: ExecutionBriefCandidate,
    ) -> None:
        self._persist_execution_brief_candidate_conn(conn, brief.idea_id, brief)
        idea.updated_at = brief.updated_at
        self._save_idea_conn(conn, idea)

    def _build_execution_brief_approval_timeline_request(
        self,
        brief: ExecutionBriefCandidate,
        request: ExecutionBriefApprovalUpdateRequest,
    ) -> DossierTimelineEventCreateRequest:
        title_by_status = {
            "approved": "Execution brief approved",
            "rejected": "Execution brief rejected",
            "editing": "Execution brief sent back for revision",
            "pending": "Execution brief marked pending",
        }
        detail = request.note.strip() or (
            f"{request.actor.strip() or 'founder'} set brief {brief.brief_id} to {request.status}."
        )
        return DossierTimelineEventCreateRequest(
            stage="handed_off",
            title=title_by_status.get(request.status, "Execution brief approval updated"),
            detail=detail,
            metadata={
                "brief_id": brief.brief_id,
                "revision_id": brief.revision_id,
                "status": request.status,
                "actor": request.actor,
            },
        )

    def get_preference_profile(self, profile_key: str = "founder_default") -> FounderPreferenceProfile:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM discovery_preference_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
        if not row:
            return FounderPreferenceProfile()
        return self._decode(row["payload_json"], FounderPreferenceProfile)

    def add_swipe_event(self, record: SwipeEventRecord) -> SwipeEventRecord:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_swipe_events (
                    event_id, idea_id, action, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.idea_id,
                    record.action,
                    self._timestamp(record.created_at),
                    self._encode(record),
                ),
            )
        return record

    def get_last_swipe_event(self, idea_id: str) -> SwipeEventRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM discovery_swipe_events
                WHERE idea_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (idea_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], SwipeEventRecord)

    def list_swipe_events(self, idea_id: str | None = None, limit: int = 200) -> list[SwipeEventRecord]:
        bounded_limit = max(1, min(limit, 500))
        with self._lock, self._connect() as conn:
            if idea_id:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM discovery_swipe_events
                    WHERE idea_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (idea_id, bounded_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM discovery_swipe_events
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (bounded_limit,),
                ).fetchall()
        return [self._decode(row["payload_json"], SwipeEventRecord) for row in rows]

    def upsert_maybe_queue_entry(self, entry: MaybeQueueEntry) -> MaybeQueueEntry:
        updated_at = entry.last_rechecked_at or entry.last_seen_at or entry.queued_at
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_maybe_queue (
                    idea_id, due_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    entry.idea_id,
                    self._timestamp(entry.due_at),
                    self._timestamp(updated_at),
                    self._encode(entry),
                ),
            )
        return entry

    def remove_maybe_queue_entry(self, idea_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM discovery_maybe_queue WHERE idea_id = ?", (idea_id,))

    def get_maybe_queue_entry(self, idea_id: str) -> MaybeQueueEntry | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM discovery_maybe_queue WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], MaybeQueueEntry)

    def list_maybe_queue_entries(self, limit: int = 200) -> list[MaybeQueueEntry]:
        bounded_limit = max(1, min(limit, 500))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM discovery_maybe_queue
                ORDER BY due_at ASC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [self._decode(row["payload_json"], MaybeQueueEntry) for row in rows]

    def _list_related_conn(self, conn: sqlite3.Connection, table: str, idea_id: str, cls: type[T]) -> list[T]:
        rows = conn.execute(
            f"SELECT payload_json FROM {table} WHERE idea_id = ? ORDER BY created_at ASC",
            (idea_id,),
        ).fetchall()
        return [self._decode(row["payload_json"], cls) for row in rows]

    def _portfolio_cache_token_conn(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM discovery_ideas) AS idea_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_ideas) AS idea_updated_at,
                (SELECT COUNT(*) FROM discovery_observations) AS observation_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_observations) AS observation_created_at,
                (SELECT COUNT(*) FROM discovery_validation_reports) AS validation_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_validation_reports) AS validation_created_at,
                (SELECT COUNT(*) FROM discovery_decisions) AS decision_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_decisions) AS decision_created_at,
                (SELECT COUNT(*) FROM discovery_archive_entries) AS archive_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_archive_entries) AS archive_created_at,
                (SELECT COUNT(*) FROM discovery_timeline) AS timeline_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_timeline) AS timeline_created_at,
                (SELECT COUNT(*) FROM discovery_evidence_bundles) AS evidence_bundle_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_evidence_bundles) AS evidence_bundle_updated_at,
                (SELECT COUNT(*) FROM discovery_execution_briefs) AS execution_brief_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_execution_briefs) AS execution_brief_updated_at,
                (SELECT COUNT(*) FROM discovery_execution_outcomes) AS execution_outcome_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_execution_outcomes) AS execution_outcome_created_at,
                (SELECT COUNT(*) FROM discovery_simulation_reports) AS simulation_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_simulation_reports) AS simulation_updated_at,
                (SELECT COUNT(*) FROM discovery_market_simulation_reports) AS market_simulation_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_market_simulation_reports) AS market_simulation_updated_at,
                (SELECT COUNT(*) FROM discovery_swipe_events) AS swipe_count,
                (SELECT COALESCE(MAX(created_at), 0) FROM discovery_swipe_events) AS swipe_created_at,
                (SELECT COUNT(*) FROM discovery_preference_profiles) AS preference_count,
                (SELECT COALESCE(MAX(updated_at), 0) FROM discovery_preference_profiles) AS preference_updated_at
            """
        ).fetchone()
        if row is None:
            return "discovery:v1:empty"
        return "|".join(
            [
                "discovery:v1",
                str(row["idea_count"]),
                str(row["idea_updated_at"]),
                str(row["observation_count"]),
                str(row["observation_created_at"]),
                str(row["validation_count"]),
                str(row["validation_created_at"]),
                str(row["decision_count"]),
                str(row["decision_created_at"]),
                str(row["archive_count"]),
                str(row["archive_created_at"]),
                str(row["timeline_count"]),
                str(row["timeline_created_at"]),
                str(row["evidence_bundle_count"]),
                str(row["evidence_bundle_updated_at"]),
                str(row["execution_brief_count"]),
                str(row["execution_brief_updated_at"]),
                str(row["execution_outcome_count"]),
                str(row["execution_outcome_created_at"]),
                str(row["simulation_count"]),
                str(row["simulation_updated_at"]),
                str(row["market_simulation_count"]),
                str(row["market_simulation_updated_at"]),
                str(row["swipe_count"]),
                str(row["swipe_created_at"]),
                str(row["preference_count"]),
                str(row["preference_updated_at"]),
            ]
        )

    def portfolio_cache_token(self) -> str:
        with self._lock, self._connect() as conn:
            return self._portfolio_cache_token_conn(conn)

    def _list_dossiers_conn(
        self,
        conn: sqlite3.Connection,
        *,
        limit: int | None = None,
        include_archived: bool = True,
        idea_ids: list[str] | None = None,
    ) -> list[IdeaDossier]:
        idea_rows: list[sqlite3.Row]
        ordered_idea_ids: list[str]

        if idea_ids is not None:
            ordered_idea_ids = [
                idea_id
                for idea_id in dict.fromkeys(str(value or "").strip() for value in idea_ids)
                if idea_id
            ]
            if not ordered_idea_ids:
                return []
            placeholders = ", ".join("?" for _ in ordered_idea_ids)
            params: list[object] = list(ordered_idea_ids)
            query = (
                "SELECT idea_id, payload_json FROM discovery_ideas "
                f"WHERE idea_id IN ({placeholders})"
            )
            if not include_archived:
                query += " AND validation_state != ?"
                params.append("archived")
            idea_rows = conn.execute(query, tuple(params)).fetchall()
        else:
            query = "SELECT idea_id, payload_json FROM discovery_ideas"
            params = []
            if not include_archived:
                query += " WHERE validation_state != ?"
                params.append("archived")
            query += " ORDER BY updated_at DESC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(max(1, min(limit, 5000)))
            idea_rows = conn.execute(query, tuple(params)).fetchall()
            ordered_idea_ids = [str(row["idea_id"]) for row in idea_rows]

        if not idea_rows:
            return []

        if idea_ids is not None:
            row_by_id = {str(row["idea_id"]): row for row in idea_rows}
            idea_rows = [row_by_id[idea_id] for idea_id in ordered_idea_ids if idea_id in row_by_id]
        else:
            ordered_idea_ids = [str(row["idea_id"]) for row in idea_rows]

        if not ordered_idea_ids:
            return []

        placeholders = ", ".join("?" for _ in ordered_idea_ids)
        related_params = tuple(ordered_idea_ids)

        evidence_rows = conn.execute(
            f"""
            SELECT parent_id, payload_json
            FROM discovery_evidence_bundles
            WHERE parent_id IN ({placeholders})
            """,
            related_params,
        ).fetchall()
        brief_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_execution_briefs
            WHERE idea_id IN ({placeholders})
            """,
            related_params,
        ).fetchall()
        simulation_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_simulation_reports
            WHERE idea_id IN ({placeholders})
            """,
            related_params,
        ).fetchall()
        market_simulation_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_market_simulation_reports
            WHERE idea_id IN ({placeholders})
            """,
            related_params,
        ).fetchall()
        observation_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_observations
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()
        validation_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_validation_reports
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()
        decision_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_decisions
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()
        archive_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_archive_entries
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()
        timeline_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_timeline
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()
        execution_outcome_rows = conn.execute(
            f"""
            SELECT idea_id, payload_json
            FROM discovery_execution_outcomes
            WHERE idea_id IN ({placeholders})
            ORDER BY idea_id ASC, created_at ASC
            """,
            related_params,
        ).fetchall()

        observations_by_idea: dict[str, list[SourceObservation]] = defaultdict(list)
        for row in observation_rows:
            observations_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], SourceObservation)
            )

        validations_by_idea: dict[str, list[IdeaValidationReport]] = defaultdict(list)
        for row in validation_rows:
            validations_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], IdeaValidationReport)
            )

        decisions_by_idea: dict[str, list[IdeaDecision]] = defaultdict(list)
        for row in decision_rows:
            decisions_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], IdeaDecision)
            )

        archive_by_idea: dict[str, list[IdeaArchiveEntry]] = defaultdict(list)
        for row in archive_rows:
            archive_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], IdeaArchiveEntry)
            )

        timeline_by_idea: dict[str, list[DossierTimelineEvent]] = defaultdict(list)
        for row in timeline_rows:
            timeline_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], DossierTimelineEvent)
            )

        execution_outcomes_by_idea: dict[str, list[ExecutionOutcomeRecord]] = defaultdict(list)
        for row in execution_outcome_rows:
            execution_outcomes_by_idea[str(row["idea_id"])].append(
                self._decode(row["payload_json"], ExecutionOutcomeRecord)
            )

        evidence_by_idea = {
            str(row["parent_id"]): self._decode(row["payload_json"], EvidenceBundleCandidate)
            for row in evidence_rows
        }
        briefs_by_idea = {
            str(row["idea_id"]): self._decode(row["payload_json"], ExecutionBriefCandidate)
            for row in brief_rows
        }
        simulation_by_idea = {
            str(row["idea_id"]): self._decode(row["payload_json"], SimulationFeedbackReport)
            for row in simulation_rows
        }
        market_simulation_by_idea = {
            str(row["idea_id"]): self._decode(row["payload_json"], MarketSimulationReport)
            for row in market_simulation_rows
        }

        dossiers: list[IdeaDossier] = []
        for row in idea_rows:
            idea_id = str(row["idea_id"])
            idea = self._decode(row["payload_json"], IdeaCandidate)
            dossiers.append(
                IdeaDossier(
                    idea=idea,
                    evidence_bundle=evidence_by_idea.get(idea_id),
                    observations=observations_by_idea.get(idea_id, []),
                    validation_reports=validations_by_idea.get(idea_id, []),
                    decisions=decisions_by_idea.get(idea_id, []),
                    archive_entries=archive_by_idea.get(idea_id, []),
                    timeline=timeline_by_idea.get(idea_id, []),
                    execution_brief_candidate=briefs_by_idea.get(idea_id),
                    execution_outcomes=execution_outcomes_by_idea.get(idea_id, []),
                    simulation_report=simulation_by_idea.get(idea_id),
                    market_simulation_report=market_simulation_by_idea.get(idea_id),
                )
            )
        return dossiers

    def list_ideas(self, limit: int = 100) -> list[IdeaCandidate]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM discovery_ideas
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._decode(row["payload_json"], IdeaCandidate) for row in rows]

    def list_dossiers(self, limit: int | None = None, include_archived: bool = True) -> list[IdeaDossier]:
        with self._lock, self._connect() as conn:
            return self._list_dossiers_conn(
                conn,
                limit=limit,
                include_archived=include_archived,
            )

    def create_idea(self, request: IdeaCreateRequest) -> IdeaCandidate:
        idea = IdeaCandidate(
            title=request.title,
            thesis=request.thesis,
            summary=request.summary,
            description=request.description,
            source=request.source,
            source_urls=request.source_urls,
            topic_tags=request.topic_tags,
            provenance=request.provenance or {"source": request.source},
            lineage_parent_ids=request.lineage_parent_ids,
            evolved_from=request.evolved_from,
            latest_scorecard=request.latest_scorecard,
        )
        if idea.latest_scorecard:
            idea.rank_score = float(idea.latest_scorecard.get("rank_score", idea.rank_score))
            idea.belief_score = float(idea.latest_scorecard.get("belief_score", idea.belief_score))
        with self._lock, self._connect() as conn:
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea.idea_id,
                DossierTimelineEventCreateRequest(
                    stage="sourced",
                    title="Idea sourced",
                    detail="The idea was added to the discovery portfolio.",
                    metadata={"source": idea.source},
                ),
            )
        return idea

    def get_idea(self, idea_id: str) -> IdeaCandidate | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM discovery_ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            return self._decode(row["payload_json"], IdeaCandidate)

    def update_idea(self, idea_id: str, request: IdeaUpdateRequest) -> IdeaCandidate:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            patch = {
                field_name: getattr(request, field_name)
                for field_name in request.model_fields_set
            }
            if not patch:
                return idea
            previous_stage = idea.latest_stage
            for key, value in patch.items():
                setattr(idea, key, value)
            if "last_evidence_refresh_at" in patch and patch["last_evidence_refresh_at"] is not None:
                idea.updated_at = patch["last_evidence_refresh_at"]
            elif "last_debate_refresh_at" in patch and patch["last_debate_refresh_at"] is not None:
                idea.updated_at = patch["last_debate_refresh_at"]
            else:
                idea.updated_at = datetime.now(UTC).replace(tzinfo=None)
            if "latest_scorecard" in patch and patch["latest_scorecard"]:
                idea.rank_score = float(patch["latest_scorecard"].get("rank_score", idea.rank_score))
                idea.belief_score = float(patch["latest_scorecard"].get("belief_score", idea.belief_score))
            self._save_idea_conn(conn, idea)
            if idea.latest_stage != previous_stage:
                self._append_timeline_conn(
                    conn,
                    idea_id,
                    DossierTimelineEventCreateRequest(
                        stage=idea.latest_stage,
                        title=f"Stage changed to {idea.latest_stage}",
                        detail="The idea advanced in the dossier workflow.",
                    ),
                )
            return idea

    def add_observation(self, idea_id: str, request: SourceObservationCreateRequest) -> SourceObservation:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            observation = SourceObservation(
                idea_id=idea_id,
                source=request.source,
                entity=request.entity,
                url=request.url,
                raw_text=request.raw_text,
                topic_tags=request.topic_tags,
                pain_score=request.pain_score,
                trend_score=request.trend_score,
                evidence_confidence=request.evidence_confidence,
                freshness_deadline=request.freshness_deadline,
                metadata=request.metadata,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_observations (
                    observation_id, idea_id, source, entity, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.observation_id,
                    idea_id,
                    observation.source,
                    observation.entity,
                    self._timestamp(observation.captured_at),
                    self._encode(observation),
                ),
            )
            idea.last_evidence_refresh_at = observation.captured_at
            idea.updated_at = observation.captured_at
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage=idea.latest_stage,
                    title="Evidence refreshed",
                    detail=observation.raw_text[:160] if observation.raw_text else observation.url,
                    metadata={"source": observation.source, "url": observation.url},
                ),
            )
            return observation

    def add_validation_report(
        self,
        idea_id: str,
        request: IdeaValidationReportCreateRequest,
    ) -> IdeaValidationReport:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            report = IdeaValidationReport(
                idea_id=idea_id,
                summary=request.summary,
                verdict=request.verdict,
                findings=request.findings,
                confidence=request.confidence,
                evidence_bundle_id=request.evidence_bundle_id,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_validation_reports (
                    report_id, idea_id, verdict, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    idea_id,
                    report.verdict.value,
                    self._timestamp(report.created_at),
                    self._encode(report),
                ),
            )
            idea.last_debate_refresh_at = report.created_at
            idea.updated_at = report.created_at
            if report.verdict.value == "pass":
                idea.validation_state = "validated"
            elif report.verdict.value == "fail":
                idea.validation_state = "invalidated"
            else:
                idea.validation_state = "reviewed"
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage="debated",
                    title="Validation report added",
                    detail=report.summary,
                    metadata={"verdict": report.verdict.value},
                ),
            )
            return report

    def add_decision(self, idea_id: str, request: IdeaDecisionCreateRequest) -> IdeaDecision:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            decision = IdeaDecision(
                idea_id=idea_id,
                decision_type=request.decision_type,
                rationale=request.rationale,
                actor=request.actor,
                metadata=request.metadata,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_decisions (
                    decision_id, idea_id, decision_type, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    idea_id,
                    decision.decision_type,
                    self._timestamp(decision.created_at),
                    self._encode(decision),
                ),
            )
            normalized = decision.decision_type.strip().lower()
            if normalized in {"pass", "maybe", "yes", "now"}:
                idea.swipe_state = normalized
                idea.latest_stage = "swiped"
            elif normalized == "handoff":
                idea.latest_stage = "handed_off"
            elif normalized == "ranked":
                idea.latest_stage = "ranked"
            idea.updated_at = decision.created_at
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage=idea.latest_stage,
                    title="Decision recorded",
                    detail=decision.rationale,
                    metadata={"decision_type": decision.decision_type, "actor": decision.actor},
                ),
            )
            return decision

    def archive_idea(self, idea_id: str, request: IdeaArchiveRequest) -> IdeaArchiveEntry:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            entry = IdeaArchiveEntry(
                idea_id=idea_id,
                reason=request.reason,
                superseded_by_idea_id=request.superseded_by_idea_id,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_archive_entries (
                    archive_id, idea_id, created_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    entry.archive_id,
                    idea_id,
                    self._timestamp(entry.created_at),
                    self._encode(entry),
                ),
            )
            idea.validation_state = "archived"
            if request.superseded_by_idea_id:
                idea.superseded_by = list(dict.fromkeys([*idea.superseded_by, request.superseded_by_idea_id]))
            idea.updated_at = entry.created_at
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage=idea.latest_stage,
                    title="Idea archived",
                    detail=request.reason,
                    metadata={"superseded_by_idea_id": request.superseded_by_idea_id},
                ),
            )
            return entry

    def add_timeline_event(self, idea_id: str, request: DossierTimelineEventCreateRequest) -> DossierTimelineEvent:
        with self._lock, self._connect() as conn:
            self._require_idea_conn(conn, idea_id)
            return self._append_timeline_conn(conn, idea_id, request)

    def upsert_evidence_bundle(self, idea_id: str, request: EvidenceBundleUpsertRequest) -> EvidenceBundleCandidate:
        with self._lock, self._connect() as conn:
            self._require_idea_conn(conn, idea_id)
            existing = conn.execute(
                "SELECT payload_json FROM discovery_evidence_bundles WHERE parent_id = ?",
                (idea_id,),
            ).fetchone()
            bundle = (
                self._decode(existing["payload_json"], EvidenceBundleCandidate)
                if existing
                else EvidenceBundleCandidate(parent_id=idea_id)
            )
            bundle.items = request.items
            bundle.overall_confidence = request.overall_confidence
            bundle.updated_at = datetime.now(UTC).replace(tzinfo=None)
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_evidence_bundles (
                    bundle_id, parent_id, updated_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    bundle.bundle_id,
                    idea_id,
                    self._timestamp(bundle.updated_at),
                    self._encode(bundle),
                ),
            )
            return bundle

    def upsert_execution_brief_candidate(
        self,
        idea_id: str,
        request: ExecutionBriefCandidateUpsertRequest,
    ) -> ExecutionBriefCandidate:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            existing = conn.execute(
                "SELECT payload_json FROM discovery_execution_briefs WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            brief = (
                self._decode(existing["payload_json"], ExecutionBriefCandidate)
                if existing
                else ExecutionBriefCandidate(idea_id=idea_id, title=request.title)
            )
            patch = {
                field_name: getattr(request, field_name)
                for field_name in request.model_fields_set
            }
            material_changed = any(
                getattr(brief, key) != value
                for key, value in patch.items()
                if key
                not in {
                    "founder_approval_required",
                    "brief_approval_status",
                    "approved_at",
                    "approved_by",
                }
            )
            for key, value in patch.items():
                setattr(brief, key, value)
            if material_changed:
                brief.revision_id = f"brief_rev_{uuid4().hex[:12]}"
            if material_changed and brief.brief_approval_status == "approved":
                brief.brief_approval_status = "pending"
                brief.approved_at = None
                brief.approved_by = None
            brief.updated_at = datetime.now(UTC).replace(tzinfo=None)
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_execution_briefs (
                    brief_id, idea_id, updated_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    brief.brief_id,
                    idea_id,
                    self._timestamp(brief.updated_at),
                    self._encode(brief),
                ),
            )
            idea.latest_stage = "handed_off"
            idea.updated_at = brief.updated_at
            self._save_idea_conn(conn, idea)
            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage="handed_off",
                    title="Execution brief drafted",
                    detail=brief.title,
                    metadata={"brief_id": brief.brief_id},
                ),
            )
            return brief

    def update_execution_brief_candidate_approval(
        self,
        idea_id: str,
        request: ExecutionBriefApprovalUpdateRequest,
        *,
        record_timeline: bool = True,
    ) -> ExecutionBriefCandidate:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            existing = conn.execute(
                "SELECT payload_json FROM discovery_execution_briefs WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if existing is None:
                raise KeyError(idea_id)

            brief = self._decode(existing["payload_json"], ExecutionBriefCandidate)
            expected_brief_id = str(request.expected_brief_id or "").strip()
            expected_revision_id = str(request.expected_revision_id or "").strip()
            if expected_brief_id and brief.brief_id != expected_brief_id:
                raise ValueError(
                    f"Execution brief changed before approval. Expected {expected_brief_id}, got {brief.brief_id}."
                )
            if expected_revision_id and brief.revision_id != expected_revision_id:
                raise ValueError(
                    "Execution brief changed before approval. "
                    f"Expected revision {expected_revision_id}, got {brief.revision_id}."
                )
            brief.brief_approval_status = request.status
            if request.status == "approved":
                brief.approved_at = datetime.now(UTC).replace(tzinfo=None)
                brief.approved_by = request.actor.strip() or "founder"
            else:
                brief.approved_at = None
                brief.approved_by = None
            brief.updated_at = datetime.now(UTC).replace(tzinfo=None)
            self._save_execution_brief_candidate_conn(conn, idea, brief)
            if record_timeline:
                self._append_timeline_conn(
                    conn,
                    idea_id,
                    self._build_execution_brief_approval_timeline_request(brief, request),
                )
            return brief

    def append_execution_brief_candidate_approval_timeline_event(
        self,
        idea_id: str,
        brief: ExecutionBriefCandidate,
        request: ExecutionBriefApprovalUpdateRequest,
    ) -> DossierTimelineEvent:
        with self._lock, self._connect() as conn:
            self._require_idea_conn(conn, idea_id)
            return self._append_timeline_conn(
                conn,
                idea_id,
                self._build_execution_brief_approval_timeline_request(brief, request),
            )

    def restore_execution_brief_candidate(
        self,
        idea_id: str,
        brief: ExecutionBriefCandidate,
        *,
        note: str = "",
    ) -> ExecutionBriefCandidate:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            restored = brief.model_copy(
                deep=True,
                update={"updated_at": datetime.now(UTC).replace(tzinfo=None)},
            )
            self._save_execution_brief_candidate_conn(conn, idea, restored)
            if note.strip():
                self._append_timeline_conn(
                    conn,
                    idea_id,
                    DossierTimelineEventCreateRequest(
                        stage="handed_off",
                        title="Execution brief approval rolled back",
                        detail=note.strip(),
                        metadata={
                            "brief_id": restored.brief_id,
                            "revision_id": restored.revision_id,
                            "status": restored.brief_approval_status,
                        },
                    ),
                )
            return restored

    def get_simulation_report(self, idea_id: str) -> SimulationFeedbackReport | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM discovery_simulation_reports WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], SimulationFeedbackReport)

    def upsert_simulation_report(
        self,
        idea_id: str,
        report: SimulationFeedbackReport,
    ) -> SimulationFeedbackReport:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_simulation_reports (
                    idea_id, report_id, updated_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    idea_id,
                    report.report_id,
                    self._timestamp(report.created_at),
                    self._encode(report),
                ),
            )
            idea.simulation_state = "complete"
            idea.latest_stage = "simulated"
            idea.updated_at = report.created_at
            self._save_idea_conn(conn, idea)

            brief_row = conn.execute(
                "SELECT payload_json FROM discovery_execution_briefs WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if brief_row:
                brief = self._decode(brief_row["payload_json"], ExecutionBriefCandidate)
                brief.simulation_summary = report.summary_headline
                brief.updated_at = report.created_at
                conn.execute(
                    """
                    INSERT OR REPLACE INTO discovery_execution_briefs (
                        brief_id, idea_id, updated_at, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        brief.brief_id,
                        idea_id,
                        self._timestamp(brief.updated_at),
                        self._encode(brief),
                    ),
                )

            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage="simulated",
                    title="Virtual focus group completed",
                    detail=report.summary_headline,
                    metadata={
                        "report_id": report.report_id,
                        "persona_count": report.run.persona_count,
                        "verdict": report.verdict,
                        "cost_usd": report.run.estimated_cost_usd,
                    },
                    ),
                )
        return report

    def get_market_simulation_report(self, idea_id: str) -> MarketSimulationReport | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM discovery_market_simulation_reports WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"], MarketSimulationReport)

    def upsert_market_simulation_report(
        self,
        idea_id: str,
        report: MarketSimulationReport,
    ) -> MarketSimulationReport:
        with self._lock, self._connect() as conn:
            idea = self._require_idea_conn(conn, idea_id)
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_market_simulation_reports (
                    idea_id, report_id, updated_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    idea_id,
                    report.report_id,
                    self._timestamp(report.created_at),
                    self._encode(report),
                ),
            )

            current_rank = float(idea.rank_score)
            current_belief = float(idea.belief_score)
            rank_delta = float(report.ranking_delta.get("rank_score_delta", 0.0))
            belief_delta = float(report.ranking_delta.get("belief_score_delta", 0.0))
            idea.rank_score = max(0.0, min(1.0, current_rank + rank_delta))
            idea.belief_score = max(0.0, min(1.0, current_belief + belief_delta))
            idea.latest_scorecard = {
                **idea.latest_scorecard,
                "simulation_adoption_rate": report.adoption_rate,
                "simulation_retention_rate": report.retention_rate,
                "simulation_virality_score": report.virality_score,
                "simulation_pain_relief_score": report.pain_relief_score,
                "simulation_objection_score": report.objection_score,
                "simulation_market_fit_score": report.market_fit_score,
                "simulation_build_priority_score": report.build_priority_score,
                "rank_score": idea.rank_score,
                "belief_score": idea.belief_score,
            }
            idea.score_snapshots.append(
                IdeaScoreSnapshot(
                    label="market_simulation_build_priority",
                    value=report.build_priority_score,
                    reason=report.executive_summary,
                )
            )
            idea.reason_snapshots.append(
                IdeaReasonSnapshot(
                    category="market_simulation",
                    summary=report.executive_summary,
                    detail="; ".join(report.recommended_actions[:2]),
                )
            )
            idea.simulation_state = "complete"
            idea.latest_stage = "simulated"
            idea.updated_at = report.created_at
            self._save_idea_conn(conn, idea)

            brief_row = conn.execute(
                "SELECT payload_json FROM discovery_execution_briefs WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if brief_row:
                brief = self._decode(brief_row["payload_json"], ExecutionBriefCandidate)
                brief.simulation_summary = report.executive_summary
                brief.updated_at = report.created_at
                conn.execute(
                    """
                    INSERT OR REPLACE INTO discovery_execution_briefs (
                        brief_id, idea_id, updated_at, payload_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        brief.brief_id,
                        idea_id,
                        self._timestamp(brief.updated_at),
                        self._encode(brief),
                    ),
                )

            self._append_timeline_conn(
                conn,
                idea_id,
                DossierTimelineEventCreateRequest(
                    stage="simulated",
                    title="Market sandbox completed",
                    detail=report.executive_summary,
                    metadata={
                        "report_id": report.report_id,
                        "population_size": report.parameters.population_size,
                        "round_count": report.parameters.round_count,
                        "verdict": report.verdict,
                        "rank_delta": rank_delta,
                        "belief_delta": belief_delta,
                    },
                ),
            )
        return report

    def record_execution_outcome(self, idea_id: str, outcome: ExecutionOutcomeRecord) -> ExecutionOutcomeRecord:
        with self._lock, self._connect() as conn:
            self._require_idea_conn(conn, idea_id)
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_execution_outcomes (
                    outcome_id, idea_id, status, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    outcome.outcome_id,
                    idea_id,
                    outcome.status.value,
                    self._timestamp(outcome.created_at),
                    self._encode(outcome),
                ),
            )
        return outcome

    def list_execution_outcomes(self, idea_id: str, limit: int = 50) -> list[ExecutionOutcomeRecord]:
        bounded_limit = max(1, min(limit, 500))
        with self._lock, self._connect() as conn:
            self._require_idea_conn(conn, idea_id)
            rows = conn.execute(
                """
                SELECT payload_json
                FROM discovery_execution_outcomes
                WHERE idea_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (idea_id, bounded_limit),
            ).fetchall()
        return [self._decode(row["payload_json"], ExecutionOutcomeRecord) for row in rows]

    def get_dossier(self, idea_id: str) -> IdeaDossier | None:
        with self._lock, self._connect() as conn:
            dossiers = self._list_dossiers_conn(
                conn,
                include_archived=True,
                idea_ids=[idea_id],
            )
            return dossiers[0] if dossiers else None


def get_discovery_store(db_path: str) -> DiscoveryStore:
    normalized = str(Path(db_path).expanduser().resolve())
    with _STORE_CACHE_LOCK:
        store = _STORE_CACHE.get(normalized)
        if store is None:
            store = DiscoveryStore(normalized)
            _STORE_CACHE[normalized] = store
        return store


def clear_discovery_store_cache() -> None:
    with _STORE_CACHE_LOCK:
        _STORE_CACHE.clear()
