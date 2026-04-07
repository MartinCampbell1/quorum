"""Structured judge parsing and panel aggregation helpers."""

from __future__ import annotations

import json
import re
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.debate.judge_pack import (
    FOUNDER_JUDGE_CRITERIA,
    aggregate_founder_scorecards,
    parse_founder_scorecard,
)


JudgeAction = Literal["continue", "final", "disqualify"]

_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?|\n?```\s*$")
_CONTROL_RE = re.compile(
    r"^\s*`?(?:FINAL_VERDICT\s*:\s*\w+|ADVANCE_MATCH\s*:\s*[AB]|NEED_MORE_ROUNDS)\s*`?\s*$",
    re.IGNORECASE,
)
_WINNER_RE = re.compile(r"winner\s*:\s*([A-Z_]+)", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"confidence\s*[:=]\s*([01](?:\.\d+)?)", re.IGNORECASE)


def _strip_markdown_fence(text: str) -> str:
    return _FENCE_RE.sub("", str(text or "").strip()).strip()


class JudgeEvidenceItem(BaseModel):
    summary: str
    source_ref: str | None = None
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class JudgeDecision(BaseModel):
    protocol_name: str
    action: JudgeAction
    winner_token: str | None = None
    rationale: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_items: list[JudgeEvidenceItem] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    scorecard: dict[str, float] = Field(default_factory=dict)
    dissent: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_response: str = ""


class JudgePanelResult(BaseModel):
    action: JudgeAction
    winner_token: str | None = None
    rationale: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    dissent: float = Field(default=0.0, ge=0.0, le=1.0)
    scorecard: dict[str, float] = Field(default_factory=dict)
    decisions: list[JudgeDecision] = Field(default_factory=list)


def _extract_json(text: str) -> dict | None:
    candidate = _strip_markdown_fence(text)
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _default_confidence(raw_text: str, action: JudgeAction) -> float:
    lowered = raw_text.lower()
    if "clear" in lowered or "decisive" in lowered:
        return 0.86 if action != "continue" else 0.62
    if action == "final":
        return 0.74
    if action == "disqualify":
        return 0.9
    return 0.48


def _infer_action(raw_text: str, final_marker: str, continue_marker: str) -> JudgeAction:
    upper = raw_text.upper()
    if "DISQUALIFIED" in upper:
        return "disqualify"
    if final_marker.upper() in upper or _WINNER_RE.search(raw_text):
        return "final"
    if continue_marker.upper() in upper:
        return "continue"
    return "continue"


def _infer_winner(raw_text: str, allowed_winners: tuple[str, ...]) -> str | None:
    upper = raw_text.upper()
    for token in allowed_winners:
        marker = f": {token.upper()}"
        if marker in upper:
            return token
    match = _WINNER_RE.search(raw_text)
    if match:
        inferred = match.group(1).strip().upper()
        for token in allowed_winners:
            if inferred == token.upper():
                return token
    return None


def _clean_rationale(raw_text: str) -> str:
    lines = [
        line for line in str(raw_text or "").strip().splitlines()
        if not _CONTROL_RE.match(line.strip())
    ]
    cleaned = "\n".join(lines).strip()
    return cleaned or str(raw_text or "").strip()


def parse_judge_response(
    raw_text: str,
    *,
    protocol_name: str,
    final_marker: str,
    continue_marker: str,
    allowed_winners: tuple[str, ...],
) -> JudgeDecision:
    payload = _extract_json(raw_text)
    if payload is not None:
        action = str(payload.get("action", "") or "").strip().lower()
        if action not in {"continue", "final", "disqualify"}:
            action = _infer_action(raw_text, final_marker, continue_marker)
        winner_token = str(payload.get("winner_token", "") or payload.get("winner", "") or "").strip() or None
        if winner_token is not None:
            winner_token = winner_token.upper()
        if winner_token not in {token.upper() for token in allowed_winners}:
            winner_token = _infer_winner(raw_text, allowed_winners)
        evidence_items = []
        for item in list(payload.get("evidence_items") or []):
            if isinstance(item, dict) and str(item.get("summary", "")).strip():
                evidence_items.append(JudgeEvidenceItem(**item))
        unsupported_claims = [str(item).strip() for item in list(payload.get("unsupported_claims") or []) if str(item).strip()]
        confidence = float(payload.get("confidence", _default_confidence(raw_text, action)))  # type: ignore[arg-type]
        dissent = float(payload.get("dissent", 0.0))  # type: ignore[arg-type]
        rationale = str(payload.get("rationale", "") or _clean_rationale(raw_text)).strip()
        scorecard = parse_founder_scorecard(payload, criteria=FOUNDER_JUDGE_CRITERIA, fallback_text=rationale or raw_text)
        return JudgeDecision(
            protocol_name=protocol_name,
            action=action,  # type: ignore[arg-type]
            winner_token=winner_token,
            rationale=rationale,
            confidence=max(0.0, min(1.0, confidence)),
            evidence_items=evidence_items,
            unsupported_claims=unsupported_claims,
            scorecard=scorecard,
            dissent=max(0.0, min(1.0, dissent)),
            raw_response=raw_text,
        )

    action = _infer_action(raw_text, final_marker, continue_marker)
    winner_token = _infer_winner(raw_text, allowed_winners)
    confidence_match = _CONFIDENCE_RE.search(raw_text)
    confidence = float(confidence_match.group(1)) if confidence_match else _default_confidence(raw_text, action)

    evidence_items: list[JudgeEvidenceItem] = []
    unsupported_claims: list[str] = []
    for line in [line.strip(" -*") for line in raw_text.splitlines() if line.strip()]:
        lowered = line.lower()
        if "unsupported" in lowered or "hallucinat" in lowered or "unverified" in lowered:
            unsupported_claims.append(line)
        if any(marker in lowered for marker in ("evidence", "repo", "issue", "readme", "data", "benchmark", "docs")):
            evidence_items.append(JudgeEvidenceItem(summary=line, confidence=0.65))
    scorecard = parse_founder_scorecard({}, criteria=FOUNDER_JUDGE_CRITERIA, fallback_text=raw_text)
    return JudgeDecision(
        protocol_name=protocol_name,
        action=action,
        winner_token=winner_token,
        rationale=_clean_rationale(raw_text),
        confidence=max(0.0, min(1.0, confidence)),
        evidence_items=evidence_items[:4],
        unsupported_claims=unsupported_claims[:4],
        scorecard=scorecard,
        dissent=0.0,
        raw_response=raw_text,
    )


def aggregate_panel_decisions(decisions: list[JudgeDecision]) -> JudgePanelResult:
    if not decisions:
        return JudgePanelResult(action="continue", rationale="", confidence=0.0, dissent=1.0, scorecard={}, decisions=[])

    action = "final"
    if any(item.action == "disqualify" for item in decisions):
        action = "disqualify"
    elif sum(item.action == "final" for item in decisions) < max(1, (len(decisions) // 2) + 1):
        action = "continue"

    winners = [item.winner_token for item in decisions if item.winner_token]
    winner_token = None
    if winners:
        counts = {token: winners.count(token) for token in set(winners)}
        winner_token = max(counts, key=counts.get)
        dissent = 1.0 - (counts[winner_token] / len(winners))
    else:
        dissent = 1.0 if len(decisions) > 1 else 0.0

    confidence = fmean([item.confidence for item in decisions])
    rationales = [item.rationale for item in decisions if item.rationale]
    rationale = rationales[0] if len(rationales) == 1 else "\n\n".join(rationales[:2])
    scorecard = aggregate_founder_scorecards([item.scorecard for item in decisions if item.scorecard], criteria=FOUNDER_JUDGE_CRITERIA)
    return JudgePanelResult(
        action=action,  # type: ignore[arg-type]
        winner_token=winner_token,
        rationale=rationale.strip(),
        confidence=max(0.0, min(1.0, confidence)),
        dissent=max(0.0, min(1.0, dissent)),
        scorecard=scorecard,
        decisions=decisions,
    )
