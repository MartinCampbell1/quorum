"""Deterministic ergodic noise seeds for ideation."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


_SEED_BANK = [
    ("constraint", "Assume the buyer refuses to buy new software and only pays for a measurable weekly outcome."),
    ("constraint", "Assume the wedge must hide inside an existing workflow rather than start with a new dashboard."),
    ("analogy", "Borrow the escalation pattern from incident response and apply it to a non-obvious business workflow."),
    ("analogy", "Borrow the margin structure of logistics brokers and translate it into a software-plus-service wedge."),
    ("data", "Treat unloved operational exhaust as the moat instead of model quality."),
    ("data", "Assume the only durable edge is a private feedback loop created after every transaction."),
    ("distribution", "Assume the initial distribution comes from a repo, integration, or community artifact the founder already owns."),
    ("distribution", "Assume the wedge rides a compliance or audit deadline instead of pure product-led growth."),
    ("mechanism", "Force the product to create a new workflow checkpoint, not just summarize an existing one."),
    ("mechanism", "Optimize for changing a decision threshold, not just saving a few minutes of labor."),
]


class NoiseSeed(BaseModel):
    seed_id: str
    family: str
    seed_text: str
    prompt_note: str = ""


def generate_noise_seeds(task: str, *, count: int = 3, salt: str = "") -> list[NoiseSeed]:
    if count <= 0:
        return []
    digest = hashlib.sha256(f"{salt}|{task}".encode("utf-8")).hexdigest()
    start = int(digest[:8], 16) % len(_SEED_BANK)
    step = (int(digest[8:12], 16) % (len(_SEED_BANK) - 1)) + 1

    seeds: list[NoiseSeed] = []
    used_indices: set[int] = set()
    cursor = start
    for slot in range(count):
        while cursor in used_indices:
            cursor = (cursor + step) % len(_SEED_BANK)
        used_indices.add(cursor)
        family, seed_text = _SEED_BANK[cursor]
        seeds.append(
            NoiseSeed(
                seed_id=f"noise_seed_{slot + 1}",
                family=family,
                seed_text=seed_text,
                prompt_note=f"Noise seed ({family}): {seed_text}",
            )
        )
        cursor = (cursor + step) % len(_SEED_BANK)
    return seeds
