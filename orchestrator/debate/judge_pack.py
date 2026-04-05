"""Founder-calibrated startup judging helpers."""

from __future__ import annotations

import re
from statistics import fmean
from typing import Mapping, Sequence


FOUNDER_JUDGE_CRITERIA = [
    "problem_sharpness",
    "icp_clarity",
    "distribution_plausibility",
    "moat",
    "buildability",
    "ai_necessity",
    "evidence_quality",
    "risk_profile",
]

FOUNDER_JUDGE_GUIDANCE = {
    "problem_sharpness": "Is the pain acute, recurring, and expensive enough to force action?",
    "icp_clarity": "Is the initial buyer/user explicit rather than vague or 'everyone'?",
    "distribution_plausibility": "Is there a believable path to first customers and repeatable distribution?",
    "moat": "Is there a defensible asset, workflow lock-in, data loop, or structural wedge?",
    "buildability": "Can the team ship v1 with the stated assets, scope, and technical constraints?",
    "ai_necessity": "Is AI structurally required, or is it just decorative frosting on a standard SaaS?",
    "evidence_quality": "Are claims grounded in repo evidence, concrete observations, user pain, or benchmarks?",
    "risk_profile": "Are the main risks acknowledged and acceptable for an early-stage company?",
}

_NUMERIC_RE = re.compile(r"(\d+(?:\.\d+)?)")
_POSITIVE_HINTS = {
    "problem_sharpness": ("acute", "pain", "costly", "broken", "urgent", "recurring"),
    "icp_clarity": ("buyer", "icp", "team", "cto", "cfo", "compliance", "developer", "revops"),
    "distribution_plausibility": ("distribution", "channel", "github", "integration", "outbound", "community", "marketplace"),
    "moat": ("moat", "data", "workflow", "lock-in", "network", "proprietary", "feedback loop"),
    "buildability": ("build", "mvp", "ship", "existing", "api", "prototype", "repo"),
    "ai_necessity": ("model", "llm", "classification", "prediction", "generation", "extraction", "ranking"),
    "evidence_quality": ("evidence", "repo", "issue", "benchmark", "docs", "data", "observed"),
    "risk_profile": ("risk", "compliance", "go-to-market", "dependency", "sales cycle", "regulatory"),
}
_NEGATIVE_HINTS = {
    "problem_sharpness": ("nice to have", "vague", "optional"),
    "icp_clarity": ("everyone", "anyone", "all teams"),
    "distribution_plausibility": ("go viral", "broad awareness"),
    "moat": ("commodity", "me too", "wrapper"),
    "buildability": ("hard research", "boil the ocean", "full platform"),
    "ai_necessity": ("manual would work", "could be a script", "does not need ai"),
    "evidence_quality": ("no evidence", "assume", "guess"),
    "risk_profile": ("ignores risk", "unclear compliance"),
}


def founder_judge_criteria(criteria: Sequence[str] | None = None) -> list[str]:
    normalized = [str(item).strip() for item in list(criteria or []) if str(item).strip()]
    return normalized or list(FOUNDER_JUDGE_CRITERIA)


def _clamp_score(value: float) -> float:
    return max(0.0, min(10.0, round(float(value), 2)))


def _coerce_number(raw_value: object) -> float | None:
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    match = _NUMERIC_RE.search(str(raw_value or ""))
    if not match:
        return None
    return float(match.group(1))


def heuristic_founder_scorecard(text: str, *, criteria: Sequence[str] | None = None) -> dict[str, float]:
    lowered = str(text or "").lower()
    scorecard: dict[str, float] = {}
    for metric in founder_judge_criteria(criteria):
        score = 5.0
        positive_hits = sum(1 for marker in _POSITIVE_HINTS.get(metric, ()) if marker in lowered)
        negative_hits = sum(1 for marker in _NEGATIVE_HINTS.get(metric, ()) if marker in lowered)
        score += positive_hits * 0.8
        score -= negative_hits * 1.0
        if metric == "ai_necessity" and ("llm" in lowered or "model" in lowered):
            score += 0.7
        if metric == "evidence_quality" and ("repo" in lowered or "evidence" in lowered or "data" in lowered):
            score += 0.7
        scorecard[metric] = _clamp_score(score)
    return scorecard


def parse_founder_scorecard(
    payload: object,
    *,
    criteria: Sequence[str] | None = None,
    fallback_text: str = "",
) -> dict[str, float]:
    metric_keys = founder_judge_criteria(criteria)
    raw_metrics: object = payload
    if isinstance(payload, Mapping):
        mapping = dict(payload)
        for preferred_key in ("scorecard", "criteria", "metrics", "metric_scores"):
            if preferred_key in mapping:
                raw_metrics = mapping[preferred_key]
                break

    normalized: dict[str, float] = {}
    if isinstance(raw_metrics, Mapping):
        for metric in metric_keys:
            value = _coerce_number(raw_metrics.get(metric))
            if value is not None:
                normalized[metric] = _clamp_score(value)
    elif isinstance(raw_metrics, list):
        for entry in raw_metrics:
            if not isinstance(entry, Mapping):
                continue
            metric = str(entry.get("metric") or entry.get("name") or "").strip()
            if metric not in metric_keys:
                continue
            value = _coerce_number(entry.get("score"))
            if value is not None:
                normalized[metric] = _clamp_score(value)

    if normalized:
        return normalized
    if fallback_text.strip():
        return heuristic_founder_scorecard(fallback_text, criteria=metric_keys)
    return {}


def aggregate_founder_scorecards(
    scorecards: Sequence[Mapping[str, float]],
    *,
    criteria: Sequence[str] | None = None,
) -> dict[str, float]:
    metric_keys = founder_judge_criteria(criteria)
    aggregated: dict[str, float] = {}
    for metric in metric_keys:
        values = [float(scorecard[metric]) for scorecard in scorecards if metric in scorecard]
        if values:
            aggregated[metric] = _clamp_score(fmean(values))
    return aggregated


def scorecard_average(scorecard: Mapping[str, float], *, criteria: Sequence[str] | None = None) -> float:
    metric_keys = founder_judge_criteria(criteria)
    values = [float(scorecard[metric]) for metric in metric_keys if metric in scorecard]
    if not values:
        return 0.0
    return round(fmean(values), 3)


def build_founder_judge_pack_instructions(
    *,
    criteria: Sequence[str] | None = None,
    append_json: bool = False,
) -> str:
    metric_keys = founder_judge_criteria(criteria)
    lines = ["Founder-calibrated scorecard (0-10 for each metric):"]
    for metric in metric_keys:
        lines.append(f"- {metric}: {FOUNDER_JUDGE_GUIDANCE.get(metric, metric)}")
    if append_json:
        lines.append(
            'Append a JSON object at the end with keys "action", "winner_token", "confidence", "rationale", and "scorecard".'
        )
    return "\n".join(lines)
