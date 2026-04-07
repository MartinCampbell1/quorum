"""Cross-domain trisociation helpers for startup ideation."""

from __future__ import annotations

import hashlib
import itertools
import re
from typing import Sequence

from pydantic import BaseModel, Field


_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")
_SPACE_RE = re.compile(r"\s+")
_FALLBACK_DOMAINS = [
    "developer tooling",
    "compliance ops",
    "vertical SaaS",
    "supply chain",
    "embedded finance",
    "healthcare admin",
    "research operations",
    "field operations",
    "community-led growth",
    "security response",
]


class TrisociationBlend(BaseModel):
    blend_id: str
    domains: list[str] = Field(default_factory=list)
    distance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    bridge_hypothesis: str
    prompt_note: str


def _normalize(text: str) -> str:
    lowered = _NON_WORD_RE.sub(" ", str(text or "").lower())
    return _SPACE_RE.sub(" ", lowered).strip()


def _tokens(text: str) -> set[str]:
    return {token for token in _normalize(text).split() if token}


def _distance(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return 1.0 - (len(left_tokens & right_tokens) / len(left_tokens | right_tokens))


def _coerce_domains(task: str, domain_candidates: Sequence[str]) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()
    for item in [*domain_candidates, *_FALLBACK_DOMAINS]:
        normalized = _normalize(item)
        if len(normalized) < 4 or normalized in seen:
            continue
        seen.add(normalized)
        domains.append(str(item).strip())
        if len(domains) >= 8:
            break
    if len(domains) >= 3:
        return domains
    digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    cursor = int(digest[:6], 16) % len(_FALLBACK_DOMAINS)
    while len(domains) < 3:
        candidate = _FALLBACK_DOMAINS[cursor % len(_FALLBACK_DOMAINS)]
        if candidate not in domains:
            domains.append(candidate)
        cursor += 1
    return domains


def generate_trisociation_blends(
    task: str,
    *,
    domain_candidates: Sequence[str],
    seed_texts: Sequence[str] = (),
    count: int = 3,
) -> list[TrisociationBlend]:
    if count <= 0:
        return []
    domains = _coerce_domains(task, domain_candidates)
    combos = list(itertools.combinations(domains, 3))
    if not combos:
        combos = [tuple(domains[:3])]

    task_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    ranked = []
    for combo in combos:
        distances = [_distance(left, right) for left, right in itertools.combinations(combo, 2)]
        score = sum(distances) / max(len(distances), 1)
        tie_break = hashlib.sha256(f"{task_digest}|{'|'.join(combo)}".encode("utf-8")).hexdigest()
        ranked.append((score, tie_break, combo))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    blends: list[TrisociationBlend] = []
    for index, (distance_score, _, combo) in enumerate(ranked[:count]):
        seed_text = str(seed_texts[index % len(seed_texts)]) if seed_texts else "Force a non-obvious bridge between these domains."
        bridge = (
            f"Fuse {combo[0]} operating constraints, {combo[1]} distribution mechanics, "
            f"and {combo[2]} defensibility into one startup thesis."
        )
        blends.append(
            TrisociationBlend(
                blend_id=f"trisociation_{index + 1}",
                domains=list(combo),
                distance_score=max(0.0, min(1.0, distance_score)),
                bridge_hypothesis=bridge,
                prompt_note=f"{bridge} Use this seed while staying grounded: {seed_text}",
            )
        )
    return blends
