"""Post-processing helpers for normalized research observations."""

from __future__ import annotations

import re
from collections import Counter

from orchestrator.research.source_models import ResearchObservation


_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "have", "more",
    "will", "what", "when", "where", "which", "their", "there", "about", "using", "used",
    "into", "than", "been", "also", "over", "under", "after", "before", "through",
}

_PAIN_TERMS = {
    "pain", "problem", "broken", "difficult", "annoying", "manual", "frustrating", "slow",
    "expensive", "missing", "blocked", "hard", "bottleneck", "error", "failure",
}

_TREND_TERMS = {
    "trending", "fastest", "popular", "rising", "growth", "launch", "new", "momentum",
    "stars", "forks", "votes", "velocity",
}


def extract_topic_tags(text: str, limit: int = 6) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", text.lower())
    filtered = [token for token in tokens if token not in _STOP_WORDS]
    counts = Counter(filtered)
    return [token for token, _count in counts.most_common(limit)]


def infer_pain_score(text: str) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(term) for term in _PAIN_TERMS)
    return min(1.0, hits / 4.0)


def infer_trend_score(text: str, metadata: dict) -> float:
    lowered = text.lower()
    keyword_hits = sum(lowered.count(term) for term in _TREND_TERMS)
    social_score = 0.0
    for key in ("stars", "forks", "votes", "score", "comments", "upvotes"):
        value = metadata.get(key)
        if isinstance(value, (int, float)) and value > 0:
            social_score += min(float(value) / 100.0, 0.5)
    return min(1.0, keyword_hits / 4.0 + social_score)


def deduplicate_observations(items: list[ResearchObservation]) -> list[ResearchObservation]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ResearchObservation] = []
    for item in items:
        key = (item.source, item.entity.strip().lower(), item.url.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def enrich_observations(items: list[ResearchObservation]) -> list[ResearchObservation]:
    enriched: list[ResearchObservation] = []
    for item in items:
        tags = item.topic_tags or extract_topic_tags(f"{item.entity} {item.raw_text}")
        item.topic_tags = tags
        if item.pain_score <= 0:
            item.pain_score = infer_pain_score(item.raw_text)
        if item.trend_score <= 0:
            item.trend_score = infer_trend_score(item.raw_text, item.metadata)
        enriched.append(item)
    return deduplicate_observations(enriched)
