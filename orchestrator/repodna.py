"""SQLite-backed RepoDNA cache and service layer."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path

from orchestrator.models import RepoDigestAnalyzeRequest, RepoDigestResult, RepoDNAProfile
from orchestrator.repo_digest import RepoDigestAnalyzer


_SERVICE_CACHE: dict[str, "RepoDNAService"] = {}
_SERVICE_CACHE_LOCK = threading.Lock()


class RepoDNAIndex:
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
                CREATE TABLE IF NOT EXISTS repo_dna_results (
                    source_key TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL,
                    profile_id TEXT NOT NULL UNIQUE,
                    digest_id TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    generated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_repo_dna_results_generated_at ON repo_dna_results(generated_at DESC)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_dna_results_profile_id ON repo_dna_results(profile_id)")

    @staticmethod
    def _decode(payload_json: str) -> RepoDigestResult:
        return RepoDigestResult.model_validate_json(payload_json)

    def get_cached(self, source_key: str, source_hash: str) -> RepoDigestResult | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM repo_dna_results
                WHERE source_key = ? AND source_hash = ?
                """,
                (source_key, source_hash),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"])

    def save_result(self, source_key: str, source_hash: str, result: RepoDigestResult) -> RepoDigestResult:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO repo_dna_results (
                    source_key,
                    source_hash,
                    profile_id,
                    digest_id,
                    repo_name,
                    source,
                    generated_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    source_hash,
                    result.profile.profile_id,
                    result.digest.digest_id,
                    result.profile.repo_name,
                    result.profile.source,
                    float(result.profile.generated_at),
                    result.model_dump_json(),
                ),
            )
        return result

    def list_profiles(self, limit: int = 50) -> list[RepoDNAProfile]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM repo_dna_results
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode(row["payload_json"]).profile for row in rows]

    def get_profile(self, profile_id: str) -> RepoDNAProfile | None:
        result = self.get_result(profile_id)
        return result.profile if result else None

    def get_result(self, profile_id: str) -> RepoDigestResult | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM repo_dna_results
                WHERE profile_id = ?
                """,
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode(row["payload_json"])


class RepoDNAService:
    def __init__(self, index: RepoDNAIndex, analyzer: RepoDigestAnalyzer | None = None):
        self._index = index
        self._analyzer = analyzer or RepoDigestAnalyzer()

    async def analyze(self, request: RepoDigestAnalyzeRequest) -> RepoDigestResult:
        return await asyncio.to_thread(self._analyze_sync, request)

    def _analyze_sync(self, request: RepoDigestAnalyzeRequest) -> RepoDigestResult:
        with self._analyzer.checkout(request) as checkout:
            source_hash = self._analyzer.source_hash(checkout, request)
            if not request.refresh:
                cached = self._index.get_cached(checkout.source_key, source_hash)
                if cached is not None:
                    return cached.model_copy(update={"cache_hit": True})
            result = self._analyzer.analyze_checkout(checkout, request, source_hash)
            self._index.save_result(checkout.source_key, source_hash, result)
            return result

    def list_profiles(self, limit: int = 50) -> list[RepoDNAProfile]:
        return self._index.list_profiles(limit=limit)

    def get_profile(self, profile_id: str) -> RepoDNAProfile | None:
        return self._index.get_profile(profile_id)

    def get_result(self, profile_id: str) -> RepoDigestResult | None:
        return self._index.get_result(profile_id)


def get_repo_dna_service(db_path: str) -> RepoDNAService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(normalized)
        if service is None:
            service = RepoDNAService(RepoDNAIndex(normalized))
            _SERVICE_CACHE[normalized] = service
        return service


def clear_repo_dna_service_cache() -> None:
    with _SERVICE_CACHE_LOCK:
        _SERVICE_CACHE.clear()
