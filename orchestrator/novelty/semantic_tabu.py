"""Semantic anti-banality heuristics for startup idea generation."""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from pydantic import BaseModel, Field


_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")
_SPACE_RE = re.compile(r"\s+")
_SPECIFICITY_RE = re.compile(r"\b\d+(?:[%x]|(?:\.\d+)?)\b")

_ROLE_HINTS = {
    "founder",
    "operator",
    "developer",
    "engineer",
    "cto",
    "cfo",
    "sales",
    "revops",
    "support",
    "compliance",
    "security",
    "recruiter",
    "procurement",
}
_CHANNEL_HINTS = {
    "github",
    "slack",
    "shopify",
    "salesforce",
    "hubspot",
    "integration",
    "api",
    "community",
    "marketplace",
    "channel",
    "seo",
    "outbound",
    "referral",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}
_GENERIC_TERMS = {
    "platform",
    "solution",
    "assistant",
    "copilot",
    "dashboard",
    "tool",
    "suite",
    "marketplace",
    "seamless",
    "end-to-end",
    "all-in-one",
    "workflow",
    "automate",
    "optimize",
    "enable",
}

_CLICHE_PATTERNS = {
    "ai_saas_for_x": re.compile(r"\bai\s+(?:saas|platform|tool)\s+for\b"),
    "ai_copilot_for_x": re.compile(r"\bai\s+copilot\s+for\b"),
    "uber_for_x": re.compile(r"\buber\s+for\b"),
    "marketplace_for_x": re.compile(r"\bmarketplace\s+for\b"),
    "all_in_one": re.compile(r"\ball[- ]in[- ]one\b"),
    "one_stop_shop": re.compile(r"\bone[- ]stop\s+shop\b"),
    "generic_automation": re.compile(r"\b(?:automate|streamline|optimize)\s+\w+\s+with\s+ai\b"),
    "verticalized_wrapper": re.compile(r"\bllm\s+wrapper\b|\bwrapper\s+around\b"),
}

DEFAULT_TABU_BANK = [
    "ai copilot for x",
    "ai saas for x",
    "chatbot for x",
    "uber for x",
    "all-in-one platform for x",
    "generic workflow automation",
    "dashboard for everyone",
    "marketplace for x",
]


class SemanticTabuAssessment(BaseModel):
    banned: bool = False
    penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    similarity_to_prior: float = Field(default=0.0, ge=0.0, le=1.0)
    similarity_to_tabu_bank: float = Field(default=0.0, ge=0.0, le=1.0)
    specificity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    genericity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cliche_hits: list[str] = Field(default_factory=list)
    taboo_matches: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _normalize_text(text: str) -> str:
    lowered = _NON_WORD_RE.sub(" ", str(text or "").lower())
    return _SPACE_RE.sub(" ", lowered).strip()


def _tokenize(text: str) -> list[str]:
    return [token for token in _normalize_text(text).split() if token and token not in _STOPWORDS]


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _max_similarity(candidate_tokens: list[str], peers: Iterable[str]) -> tuple[float, list[str]]:
    max_similarity = 0.0
    matched: list[str] = []
    for peer in peers:
        peer_text = str(peer or "").strip()
        if not peer_text:
            continue
        similarity = _jaccard(candidate_tokens, _tokenize(peer_text))
        if similarity > max_similarity:
            max_similarity = similarity
        if similarity >= 0.45 or _normalize_text(peer_text) in " ".join(candidate_tokens):
            matched.append(peer_text[:120])
    return max_similarity, matched[:4]


def _specificity_score(text: str, *, domain_signals: Sequence[str]) -> float:
    normalized = _normalize_text(text)
    tokens = _tokenize(normalized)
    role_hits = sum(1 for item in _ROLE_HINTS if item in normalized)
    channel_hits = sum(1 for item in _CHANNEL_HINTS if item in normalized)
    domain_hits = 0
    for signal in domain_signals:
        signal_tokens = _tokenize(signal)
        if signal_tokens and _jaccard(tokens, signal_tokens) >= 0.2:
            domain_hits += 1
    score = 0.0
    score += min(len(tokens) / 28.0, 1.0) * 0.35
    score += min(role_hits * 0.12, 0.24)
    score += min(channel_hits * 0.1, 0.2)
    score += min(domain_hits * 0.12, 0.24)
    if _SPECIFICITY_RE.search(normalized):
        score += 0.12
    return max(0.0, min(1.0, score))


def _genericity_score(text: str, cliche_hits: Sequence[str]) -> float:
    normalized = _normalize_text(text)
    tokens = _tokenize(normalized)
    generic_terms = sum(1 for token in tokens if token in _GENERIC_TERMS)
    score = 0.0
    score += min(len(cliche_hits) * 0.22, 0.66)
    score += min(generic_terms * 0.06, 0.24)
    if len(tokens) < 12:
        score += 0.16
    if "everyone" in normalized or "anyone" in normalized:
        score += 0.12
    return max(0.0, min(1.0, score))


def assess_semantic_tabu(
    candidate_text: str,
    *,
    prior_candidates: Iterable[str] = (),
    taboo_bank: Sequence[str] | None = None,
    domain_signals: Sequence[str] = (),
) -> SemanticTabuAssessment:
    text = str(candidate_text or "").strip()
    tokens = _tokenize(text)
    taboo_bank = list(taboo_bank or DEFAULT_TABU_BANK)
    cliche_hits = [name for name, pattern in _CLICHE_PATTERNS.items() if pattern.search(_normalize_text(text))]
    similarity_to_prior, prior_matches = _max_similarity(tokens, prior_candidates)
    similarity_to_tabu_bank, taboo_matches = _max_similarity(tokens, taboo_bank)
    specificity_score = _specificity_score(text, domain_signals=domain_signals)
    genericity_score = _genericity_score(text, cliche_hits)

    penalty = 0.0
    penalty += similarity_to_prior * 0.42
    penalty += similarity_to_tabu_bank * 0.22
    penalty += genericity_score * 0.2
    penalty += (1.0 - specificity_score) * 0.16
    if cliche_hits:
        penalty += min(len(cliche_hits) * 0.08, 0.24)
    penalty = max(0.0, min(1.0, penalty))

    reasons: list[str] = []
    if similarity_to_prior >= 0.72:
        reasons.append("Too close to an existing candidate; likely a median-trap variant.")
    if cliche_hits:
        reasons.append(f"Cliche startup pattern detected: {', '.join(cliche_hits)}.")
    if genericity_score >= 0.55:
        reasons.append("Language is too generic and reads like a stock 'AI SaaS for X' pitch.")
    if specificity_score <= 0.35:
        reasons.append("Missing concrete buyer, channel, or operational constraints.")
    if taboo_matches and similarity_to_tabu_bank >= 0.35:
        reasons.append("Candidate overlaps with the taboo bank instead of escaping it.")

    banned = bool(
        similarity_to_prior >= 0.9
        or (len(cliche_hits) >= 2 and specificity_score <= 0.4)
        or (genericity_score >= 0.78 and specificity_score <= 0.28)
    )
    if banned and not reasons:
        reasons.append("Rejected by semantic tabu guardrails.")

    return SemanticTabuAssessment(
        banned=banned,
        penalty=penalty,
        similarity_to_prior=similarity_to_prior,
        similarity_to_tabu_bank=similarity_to_tabu_bank,
        specificity_score=specificity_score,
        genericity_score=genericity_score,
        cliche_hits=cliche_hits,
        taboo_matches=[*prior_matches, *taboo_matches][:6],
        reasons=reasons,
    )


def render_tabu_guardrails(taboo_bank: Sequence[str], *, limit: int = 6) -> str:
    preview = [str(item).strip() for item in taboo_bank if str(item).strip()][:limit]
    if not preview:
        return ""
    bullets = "\n".join(f"- Avoid converging to: {item}" for item in preview)
    return (
        "ANTI-BANALITY GUARDRAILS:\n"
        "Escape the median trap. Do not pitch another generic wrapper or broad 'AI for X' shell.\n"
        f"{bullets}\n"
    )
