"""Large-population agent-state generation for the Quorum market lab."""

from __future__ import annotations

import random

from orchestrator.discovery_models import (
    IdeaDossier,
    LabAgentState,
    MarketChannel,
    SimulationParameters,
    SimulationRunRequest,
)
from orchestrator.simulation.lab.world_builder import MarketWorldConfig
from orchestrator.simulation.mvp.personas import PersonaBuilder, stable_seed


_CHANNELS: tuple[MarketChannel, ...] = (
    "founder_outreach",
    "community",
    "content",
    "referral",
    "partner",
    "social",
)


def _choose_channel(rng: random.Random, world: MarketWorldConfig) -> MarketChannel:
    weighted = sorted(world.channel_strength.items(), key=lambda item: item[1], reverse=True)
    if rng.random() < 0.58:
        return weighted[0][0]  # type: ignore[return-value]
    return rng.choice([key for key, _ in weighted])  # type: ignore[return-value]


def build_market_population(
    dossier: IdeaDossier,
    parameters: SimulationParameters,
    world: MarketWorldConfig,
) -> list[LabAgentState]:
    seed = parameters.seed if parameters.seed is not None else stable_seed(dossier.idea.idea_id, parameters.population_size, "lab")
    persona_builder = PersonaBuilder(seed)
    base_personas = persona_builder.build(
        dossier.idea,
        SimulationRunRequest(
            persona_count=max(10, min(24, parameters.population_size // 3)),
            max_rounds=min(5, parameters.round_count),
            seed=seed,
            target_market=parameters.target_market,
        ),
        evidence_snippets=world.problem_surface[:4],
    )

    population: list[LabAgentState] = []
    segments = list(world.segment_mix.keys()) or ["ops_lead"]
    for index in range(parameters.population_size):
        rng = random.Random(stable_seed(seed, index, "agent_state"))
        persona = base_personas[index % len(base_personas)]
        segment = segments[index % len(segments)]
        population.append(
            LabAgentState(
                display_name=persona.display_name,
                segment=segment,
                archetype=persona.archetype,
                need_intensity=round(min(0.96, persona.urgency + rng.random() * 0.12), 4),
                trust_threshold=round(min(0.96, 0.28 + persona.skepticism * 0.44), 4),
                budget_fit=round(min(0.96, 0.34 + persona.ai_affinity * 0.28 + (0.14 if persona.budget_band in {"high", "enterprise"} else 0.0)), 4),
                network_reach=round(min(0.96, 0.24 + rng.random() * 0.54), 4),
                referral_propensity=round(min(0.96, 0.18 + persona.ai_affinity * 0.32 + rng.random() * 0.16), 4),
                skepticism=persona.skepticism,
                price_sensitivity=persona.price_sensitivity,
                preferred_channel=_choose_channel(rng, world),
                objections=list(persona.objections),
                memory=[entry.content for entry in persona.memory[:3]],
            )
        )

    return population
