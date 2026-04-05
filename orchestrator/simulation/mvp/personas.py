"""Synthetic virtual-persona builder for the Quorum MVP simulation lane."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from orchestrator.discovery_models import (
    IdeaCandidate,
    PersonaMemoryEntry,
    PersonaPlanStep,
    SimulationRunRequest,
    VirtualPersona,
)


FIRST_NAMES = [
    "Ava",
    "Mason",
    "Nora",
    "Miles",
    "Ivy",
    "Lucas",
    "Elena",
    "Owen",
    "Julia",
    "Noah",
    "Leah",
    "Caleb",
]

LAST_NAMES = [
    "Carter",
    "Patel",
    "Nguyen",
    "Brooks",
    "Morris",
    "Diaz",
    "Kim",
    "Turner",
    "Reed",
    "Bennett",
    "Hayes",
    "Foster",
]


_B2B_TEMPLATES: list[dict[str, Any]] = [
    {
        "segment": "ops_lead",
        "archetype": "operator",
        "company_size": "mid_market",
        "budget_band": "high",
        "needs": ["remove manual triage", "shorten decision latency"],
        "objections": ["integration overhead", "unclear owner"],
    },
    {
        "segment": "builder_founder",
        "archetype": "builder",
        "company_size": "startup",
        "budget_band": "medium",
        "needs": ["fast setup", "small-team leverage"],
        "objections": ["tool sprawl", "maintenance burden"],
    },
    {
        "segment": "product_analyst",
        "archetype": "analyst",
        "company_size": "mid_market",
        "budget_band": "medium",
        "needs": ["clear metrics", "evidence-backed prioritization"],
        "objections": ["weak signal quality", "hard to benchmark"],
    },
    {
        "segment": "skeptical_exec",
        "archetype": "skeptic",
        "company_size": "enterprise",
        "budget_band": "enterprise",
        "needs": ["risk reduction", "credible ROI story"],
        "objections": ["too much novelty", "budget scrutiny"],
    },
    {
        "segment": "growth_owner",
        "archetype": "leader",
        "company_size": "startup",
        "budget_band": "high",
        "needs": ["repeatable distribution", "faster market learning"],
        "objections": ["unclear buyer wedge", "slow onboarding"],
    },
]

_B2C_TEMPLATES: list[dict[str, Any]] = [
    {
        "segment": "creator_operator",
        "archetype": "creator",
        "company_size": "solo",
        "budget_band": "low",
        "needs": ["save time every week", "feel instantly useful"],
        "objections": ["learning curve", "monthly price creep"],
    },
    {
        "segment": "power_user",
        "archetype": "builder",
        "company_size": "solo",
        "budget_band": "medium",
        "needs": ["automation depth", "customizable workflows"],
        "objections": ["ceiling too low", "not enough control"],
    },
    {
        "segment": "skeptical_consumer",
        "archetype": "skeptic",
        "company_size": "personal",
        "budget_band": "low",
        "needs": ["simple payoff", "trustworthy guidance"],
        "objections": ["AI gimmick risk", "privacy worries"],
    },
    {
        "segment": "busy_manager",
        "archetype": "operator",
        "company_size": "small_business",
        "budget_band": "medium",
        "needs": ["fewer repetitive tasks", "shareable outcomes"],
        "objections": ["needs team buy-in", "weak retention hook"],
    },
]


def stable_seed(*parts: object) -> int:
    payload = "||".join(str(part) for part in parts)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12], 16)


def _is_b2c(idea: IdeaCandidate, target_market: str | None) -> bool:
    text = " ".join(
        [
            idea.title,
            idea.thesis,
            idea.summary,
            idea.description,
            " ".join(idea.topic_tags),
            str(target_market or ""),
        ]
    ).lower()
    return any(token in text for token in ("consumer", "creator", "personal", "family", "shopping", "social"))


def _domain_context(idea: IdeaCandidate) -> str:
    if idea.topic_tags:
        return ", ".join(idea.topic_tags[:3])
    return idea.source or "workflow evaluation"


class PersonaBuilder:
    """Builds deterministic virtual personas from idea context."""

    def __init__(self, seed: int):
        self.seed = seed

    def build(
        self,
        idea: IdeaCandidate,
        request: SimulationRunRequest,
        evidence_snippets: list[str] | None = None,
    ) -> list[VirtualPersona]:
        evidence = list(evidence_snippets or [])
        templates = _B2C_TEMPLATES if _is_b2c(idea, request.target_market) else _B2B_TEMPLATES
        personas: list[VirtualPersona] = []

        for index in range(request.persona_count):
            rng = random.Random(stable_seed(self.seed, idea.idea_id, index, request.target_market or ""))
            template = templates[index % len(templates)]
            first = FIRST_NAMES[(index + rng.randint(0, len(FIRST_NAMES) - 1)) % len(FIRST_NAMES)]
            last = LAST_NAMES[(index * 3 + rng.randint(0, len(LAST_NAMES) - 1)) % len(LAST_NAMES)]
            urgency = round(min(0.95, 0.38 + rng.random() * 0.45), 4)
            skepticism = round(min(0.95, 0.18 + rng.random() * 0.55), 4)
            ai_affinity = round(min(0.95, 0.28 + rng.random() * 0.55), 4)
            price_sensitivity = round(min(0.95, 0.22 + rng.random() * 0.58), 4)

            memory = [
                PersonaMemoryEntry(
                    content=f"Currently evaluates tools through the lens of {template['needs'][0]}.",
                    weight=round(0.55 + rng.random() * 0.25, 4),
                ),
                PersonaMemoryEntry(
                    content=f"Has been burned before by {template['objections'][0]}.",
                    weight=round(0.46 + rng.random() * 0.22, 4),
                ),
            ]
            if evidence:
                memory.append(
                    PersonaMemoryEntry(
                        kind="external_signal",
                        content=evidence[index % len(evidence)][:180],
                        weight=round(0.44 + rng.random() * 0.18, 4),
                        source="dossier_evidence",
                    )
                )

            daily_plan = [
                PersonaPlanStep(label="Scan options", intent="Compare this idea to current workflow costs.", urgency=urgency),
                PersonaPlanStep(label="Check risks", intent=f"Pressure-test {template['objections'][0]}.", urgency=max(0.35, skepticism)),
                PersonaPlanStep(label="Share verdict", intent="Recommend trial, wait, or reject to the rest of the team.", urgency=0.58),
            ]

            personas.append(
                VirtualPersona(
                    display_name=f"{first} {last}",
                    segment=template["segment"],
                    archetype=template["archetype"],
                    company_size=template["company_size"],
                    budget_band=template["budget_band"],
                    urgency=urgency,
                    skepticism=skepticism,
                    ai_affinity=ai_affinity,
                    price_sensitivity=price_sensitivity,
                    domain_context=_domain_context(idea),
                    needs=list(template["needs"]),
                    objections=list(template["objections"]),
                    memory=memory,
                    daily_plan=daily_plan,
                )
            )

        return personas
