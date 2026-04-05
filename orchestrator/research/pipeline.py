"""End-to-end research pipeline orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from orchestrator.research.postprocessors import enrich_observations
from orchestrator.research.scheduler import DEFAULT_SOURCE_FRESHNESS_WINDOWS
from orchestrator.research.search_index import ResearchIndex
from orchestrator.research.source_models import DailyQueueItem, ResearchObservation, ResearchScanRun, ScanRequest
from orchestrator.research.source_scanners import DEFAULT_SCANNERS, SourceScanner


class ResearchPipeline:
    def __init__(self, index: ResearchIndex, scanners: dict[str, SourceScanner] | None = None):
        self.index = index
        self.scanners = scanners or DEFAULT_SCANNERS

    async def run_scan(self, request: ScanRequest) -> ResearchScanRun:
        run = ResearchScanRun(query=request.query, sources=request.sources or list(self.scanners))
        self.index.save_run(run)
        selected_sources = request.sources or list(self.scanners)
        tasks = [
            self._scan_source(
                source_name=source_name,
                scanner=self.scanners[source_name],
                query=request.query,
                max_items=request.max_items_per_source,
                freshness_window_hours=request.freshness_window_hours or DEFAULT_SOURCE_FRESHNESS_WINDOWS[source_name],
            )
            for source_name in selected_sources
            if source_name in self.scanners
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        collected: list[ResearchObservation] = []
        errors: list[str] = []
        for source_name, result in zip(selected_sources, results):
            if isinstance(result, Exception):
                errors.append(f"{source_name}: {type(result).__name__}: {result}")
            else:
                collected.extend(result)
        processed = enrich_observations(collected)
        self.index.add_observations(processed)
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        run.status = "failed" if errors and not processed else "completed"
        run.observation_count = len(processed)
        run.error_messages = errors
        self.index.save_run(run)
        return run

    async def _scan_source(
        self,
        *,
        source_name: str,
        scanner: SourceScanner,
        query: str,
        max_items: int,
        freshness_window_hours: int,
    ) -> list[ResearchObservation]:
        del source_name
        return await scanner.scan(query=query, max_items=max_items, freshness_window_hours=freshness_window_hours)

    def daily_queue(self, limit: int = 25) -> list[DailyQueueItem]:
        return self.index.daily_queue(limit=limit)
