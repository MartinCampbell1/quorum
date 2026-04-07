"""SQLite-backed storage and search helpers for research observations."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from orchestrator.research.source_models import DailyQueueItem, ResearchObservation, ResearchScanRun, ResearchSearchResult


T = TypeVar("T")
_INDEX_CACHE: dict[str, "ResearchIndex"] = {}
_INDEX_CACHE_LOCK = threading.Lock()


class ResearchIndex:
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
                CREATE TABLE IF NOT EXISTS research_observations (
                    observation_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    query TEXT NOT NULL,
                    url TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    topic_tags_json TEXT NOT NULL,
                    pain_score REAL NOT NULL,
                    trend_score REAL NOT NULL,
                    evidence_confidence TEXT NOT NULL,
                    collected_at REAL NOT NULL,
                    freshness_deadline REAL,
                    metadata_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_runs (
                    run_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_research_observations_collected_at ON research_observations(collected_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_research_observations_source ON research_observations(source, collected_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_research_runs_started_at ON research_runs(started_at DESC)")

    @staticmethod
    def _encode(model: T) -> str:
        return model.model_dump_json()

    @staticmethod
    def _decode(payload: str, cls: type[T]) -> T:
        return cls.model_validate_json(payload)

    @staticmethod
    def _ts(value: datetime | None) -> float | None:
        if value is None:
            return None
        return value.timestamp()

    def save_run(self, run: ResearchScanRun) -> ResearchScanRun:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO research_runs (
                    run_id, query, status, started_at, finished_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.query,
                    run.status,
                    self._ts(run.started_at),
                    self._ts(run.finished_at),
                    self._encode(run),
                ),
            )
        return run

    def add_observations(self, items: list[ResearchObservation]) -> list[ResearchObservation]:
        if not items:
            return items
        with self._lock, self._connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO research_observations (
                        observation_id, source, entity, query, url, raw_text, topic_tags_json,
                        pain_score, trend_score, evidence_confidence, collected_at, freshness_deadline,
                        metadata_json, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.observation_id,
                        item.source,
                        item.entity,
                        item.query,
                        item.url,
                        item.raw_text,
                        item.model_dump_json(include={"topic_tags"}),
                        float(item.pain_score),
                        float(item.trend_score),
                        item.evidence_confidence.value,
                        self._ts(item.collected_at),
                        self._ts(item.freshness_deadline),
                        item.model_dump_json(include={"metadata"}),
                        self._encode(item),
                    ),
                )
        return items

    def list_observations(self, limit: int = 100, source: str | None = None, include_stale: bool = False) -> list[ResearchObservation]:
        limit = max(1, min(int(limit or 100), 500))
        now_ts = datetime.now(UTC).timestamp()
        with self._lock, self._connect() as conn:
            if source and include_stale:
                rows = conn.execute(
                    "SELECT payload_json FROM research_observations WHERE source = ? ORDER BY collected_at DESC LIMIT ?",
                    (source, limit),
                ).fetchall()
            elif source:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM research_observations
                    WHERE source = ? AND (freshness_deadline IS NULL OR freshness_deadline >= ?)
                    ORDER BY collected_at DESC
                    LIMIT ?
                    """,
                    (source, now_ts, limit),
                ).fetchall()
            elif include_stale:
                rows = conn.execute(
                    "SELECT payload_json FROM research_observations ORDER BY collected_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM research_observations
                    WHERE freshness_deadline IS NULL OR freshness_deadline >= ?
                    ORDER BY collected_at DESC
                    LIMIT ?
                    """,
                    (now_ts, limit),
                ).fetchall()
            return [self._decode(row["payload_json"], ResearchObservation) for row in rows]

    def search(self, query: str, limit: int = 50) -> ResearchSearchResult:
        token = f"%{query.strip().lower()}%"
        if not query.strip():
            items = self.list_observations(limit=limit)
            return ResearchSearchResult(items=items, total=len(items))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM research_observations
                WHERE lower(entity) LIKE ? OR lower(raw_text) LIKE ? OR lower(url) LIKE ?
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                (token, token, token, limit),
            ).fetchall()
            items = [self._decode(row["payload_json"], ResearchObservation) for row in rows]
            return ResearchSearchResult(items=items, total=len(items))

    def daily_queue(self, limit: int = 50) -> list[DailyQueueItem]:
        items = self.list_observations(limit=max(limit * 3, 50))
        now = datetime.now(UTC).replace(tzinfo=None)
        ranked: list[DailyQueueItem] = []
        for item in items:
            age_hours = max((now - item.collected_at).total_seconds() / 3600.0, 0.0)
            freshness_bonus = max(0.0, 1.0 - min(age_hours / 48.0, 1.0))
            priority = (item.trend_score * 0.5) + (item.pain_score * 0.35) + (freshness_bonus * 0.15)
            bucket = "daily" if age_hours <= 48 else "weekly"
            ranked.append(DailyQueueItem(observation=item, priority_score=round(priority, 4), bucket=bucket))
        ranked.sort(key=lambda item: item.priority_score, reverse=True)
        return ranked[:limit]

    def export_payload(self, limit: int = 200) -> list[dict]:
        return [item.model_dump(mode="json") for item in self.list_observations(limit=limit, include_stale=True)]

    def list_runs(self, limit: int = 50) -> list[ResearchScanRun]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM research_runs ORDER BY started_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
            return [self._decode(row["payload_json"], ResearchScanRun) for row in rows]


def get_research_index(db_path: str) -> ResearchIndex:
    normalized = str(Path(db_path).expanduser().resolve())
    with _INDEX_CACHE_LOCK:
        index = _INDEX_CACHE.get(normalized)
        if index is None:
            index = ResearchIndex(normalized)
            _INDEX_CACHE[normalized] = index
        return index


def clear_research_index_cache() -> None:
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE.clear()
