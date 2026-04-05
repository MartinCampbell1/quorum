"""Export helpers for research observations."""

from __future__ import annotations

import json

from orchestrator.research.source_models import DailyQueueItem, ResearchObservation


def export_observations_jsonl(items: list[ResearchObservation]) -> str:
    return "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in items)


def export_daily_queue_markdown(items: list[DailyQueueItem]) -> str:
    lines = ["# Research Daily Queue", ""]
    for item in items:
        obs = item.observation
        lines.extend(
            [
                f"## {obs.entity}",
                f"- source: {obs.source}",
                f"- query: {obs.query}",
                f"- priority: {item.priority_score}",
                f"- trend_score: {obs.trend_score}",
                f"- pain_score: {obs.pain_score}",
                f"- url: {obs.url}",
                f"- tags: {', '.join(obs.topic_tags)}",
                f"- summary: {obs.raw_text}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"
