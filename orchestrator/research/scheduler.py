"""Scheduling helpers for recurring research scans."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from orchestrator.research.source_models import ResearchSource, ScheduledScanSeed, ScanRequest


DEFAULT_SOURCE_FRESHNESS_WINDOWS: dict[ResearchSource, int] = {
    "github": 12,
    "github_trending": 6,
    "hackernews": 12,
    "reddit": 6,
    "npm": 24,
    "pypi": 24,
    "producthunt": 24,
    "stackoverflow": 24,
}


def build_scan_request(seed: ScheduledScanSeed, now: datetime | None = None) -> ScanRequest:
    effective_now = (now or datetime.now(UTC)).replace(tzinfo=None)
    del effective_now
    sources = seed.sources or list(DEFAULT_SOURCE_FRESHNESS_WINDOWS)
    freshness = max(seed.freshness_windows_hours.values(), default=24) if seed.freshness_windows_hours else 24
    return ScanRequest(query=seed.query, sources=sources, freshness_window_hours=freshness)


def source_due(last_seen_at: datetime | None, source: ResearchSource, now: datetime | None = None) -> bool:
    if last_seen_at is None:
        return True
    effective_now = (now or datetime.now(UTC)).replace(tzinfo=None)
    window = timedelta(hours=DEFAULT_SOURCE_FRESHNESS_WINDOWS[source])
    return effective_now - last_seen_at >= window
