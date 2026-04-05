"""Deterministic focus-group simulation runner for cheap virtual-user checks."""

from __future__ import annotations

from collections import Counter

from orchestrator.discovery_models import (
    FocusGroupRound,
    FocusGroupRun,
    FocusGroupTurn,
    IdeaDossier,
    PersonaMemoryEntry,
    SimulationFeedbackReport,
    SimulationRunRequest,
)
from orchestrator.simulation.mvp.feedback import summarize_focus_group
from orchestrator.simulation.mvp.personas import PersonaBuilder, stable_seed
from orchestrator.simulation.mvp.world import build_focus_group_world


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _idea_text(dossier: IdeaDossier) -> str:
    idea = dossier.idea
    return " ".join(
        [
            idea.title,
            idea.thesis,
            idea.summary,
            idea.description,
            " ".join(idea.topic_tags),
            " ".join(observation.raw_text for observation in dossier.observations[:3]),
            " ".join(report.summary for report in dossier.validation_reports[:2]),
        ]
    ).lower()


def _evidence_bonus(dossier: IdeaDossier) -> float:
    bundle_items = len(dossier.evidence_bundle.items) if dossier.evidence_bundle else 0
    observation_count = len(dossier.observations)
    report_count = len(dossier.validation_reports)
    return min(0.14, (bundle_items * 0.015) + (observation_count * 0.018) + (report_count * 0.03))


def _concreteness_bonus(text: str) -> float:
    markers = ("automate", "rank", "reduce", "monitor", "route", "launch", "prove", "detect", "save")
    abstract_markers = ("platform", "ecosystem", "agentic future", "super app", "community")
    score = 0.08 if any(marker in text for marker in markers) else -0.02
    if any(marker in text for marker in abstract_markers):
        score -= 0.03
    return score


def _role_bonus(text: str, persona_segment: str, archetype: str) -> float:
    if archetype == "builder" and any(token in text for token in ("repo", "sdk", "developer", "api", "tooling", "code")):
        return 0.08
    if archetype == "operator" and any(token in text for token in ("ops", "workflow", "triage", "queue", "routing", "automation")):
        return 0.08
    if archetype == "analyst" and any(token in text for token in ("evidence", "benchmark", "ranking", "insight", "report")):
        return 0.08
    if "growth" in persona_segment and any(token in text for token in ("distribution", "buyer", "growth", "sales")):
        return 0.08
    return 0.02


def _stance_from_scores(resonance: float, purchase_intent: float) -> str:
    combined = (resonance * 0.6) + (purchase_intent * 0.4)
    if combined < 0.28:
        return "reject"
    if combined < 0.44:
        return "doubt"
    if combined < 0.6:
        return "curious"
    if combined < 0.76:
        return "trial"
    return "champion"


def _reason_bundle(persona, round_index: int, text: str) -> list[str]:
    reasons = [persona.needs[round_index % len(persona.needs)]]
    if round_index == 2:
        reasons.append(persona.objections[0])
    elif any(token in text for token in ("evidence", "benchmark", "validate")):
        reasons.append("needs proof that the signal quality holds under real usage")
    else:
        reasons.append(persona.objections[round_index % len(persona.objections)])
    return reasons


def _quote(persona, idea_title: str, prompt: str, stance: str, reasons: list[str]) -> str:
    subject = persona.segment.replace("_", " ")
    lead = {
        "reject": f"As a {subject}, I would pass for now because",
        "doubt": f"As a {subject}, I am not against {idea_title}, but",
        "curious": f"As a {subject}, I am curious about {idea_title} because",
        "trial": f"As a {subject}, I would try {idea_title} if",
        "champion": f"As a {subject}, I would push this forward because",
    }[stance]
    if "block" in prompt.lower():
        tail = f"{reasons[1]} is still the main blocker."
    elif "recommend or buy" in prompt.lower():
        tail = f"it already maps to {reasons[0]}, and I would want {reasons[1]} resolved."
    else:
        tail = f"it appears to address {reasons[0]}, but {reasons[1]} stays in my head."
    return f"{lead} {tail}"


class FocusGroupRunner:
    """Runs a bounded, deterministic synthetic focus group."""

    def run(self, dossier: IdeaDossier, request: SimulationRunRequest) -> SimulationFeedbackReport:
        idea = dossier.idea
        text = _idea_text(dossier)
        seed = request.seed if request.seed is not None else stable_seed(
            idea.idea_id,
            idea.title,
            idea.summary,
            request.persona_count,
            request.target_market or "",
        )
        evidence_snippets = []
        if dossier.evidence_bundle:
            evidence_snippets.extend(item.summary for item in dossier.evidence_bundle.items[:3])
        evidence_snippets.extend(observation.raw_text for observation in dossier.observations[:3])
        evidence_snippets.extend(report.summary for report in dossier.validation_reports[:2])

        world = build_focus_group_world(dossier, request)
        personas = PersonaBuilder(seed).build(idea, request, evidence_snippets=evidence_snippets)
        rounds: list[FocusGroupRound] = []
        evidence_bonus = _evidence_bonus(dossier)
        concreteness_bonus = _concreteness_bonus(text)

        for round_index, prompt in enumerate(world.discussion_prompts, start=1):
            responses: list[FocusGroupTurn] = []
            for persona in personas:
                role_bonus = _role_bonus(text, persona.segment, persona.archetype)
                round_bonus = 0.03 if round_index == 1 else (0.01 if round_index == 2 else 0.05)
                resonance = _clamp(
                    0.24
                    + evidence_bonus
                    + concreteness_bonus
                    + role_bonus
                    + (persona.urgency * 0.18)
                    + (persona.ai_affinity * 0.12)
                    - (persona.skepticism * 0.11)
                    - (persona.price_sensitivity * 0.08)
                    + round_bonus
                )
                purchase_intent = _clamp(
                    (resonance * 0.82)
                    + (persona.urgency * 0.08)
                    - (persona.price_sensitivity * 0.12)
                    - (persona.skepticism * 0.05)
                    + (0.04 if persona.budget_band in {"high", "enterprise"} else 0.0)
                )
                sentiment = round((resonance * 2.0) - 1.0, 4)
                reasons = _reason_bundle(persona, round_index, text)
                stance = _stance_from_scores(resonance, purchase_intent)
                quote = _quote(persona, idea.title, prompt, stance, reasons)
                responses.append(
                    FocusGroupTurn(
                        round_index=round_index,
                        persona_id=persona.persona_id,
                        prompt=prompt,
                        quote=quote,
                        stance=stance,
                        sentiment=sentiment,
                        resonance_score=round(resonance, 4),
                        purchase_intent=round(purchase_intent, 4),
                        key_reasons=reasons,
                    )
                )
                persona.memory.append(
                    PersonaMemoryEntry(
                        kind="simulation_reaction",
                        content=f"Round {round_index}: {quote}",
                        weight=round(max(0.38, resonance), 4),
                        source="focus_group_run",
                    )
                )

            stance_counts = Counter(response.stance for response in responses)
            rounds.append(
                FocusGroupRound(
                    round_index=round_index,
                    prompt=prompt,
                    aggregate_note=", ".join(
                        f"{label}:{count}" for label, count in sorted(stance_counts.items())
                    ),
                    responses=responses,
                )
            )

        run = FocusGroupRun(
            idea_id=idea.idea_id,
            world_name=world.name,
            persona_count=len(personas),
            step_count=len(rounds),
            estimated_token_count=len(personas) * len(rounds) * 180,
            estimated_cost_usd=round((len(personas) * len(rounds) * 180 / 1000.0) * 0.00045, 4),
            seed=seed,
            rounds=rounds,
        )
        return summarize_focus_group(idea.idea_id, run, personas)
