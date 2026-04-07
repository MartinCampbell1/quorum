"""Reporting and ranking-delta synthesis for market-lab runs."""

from __future__ import annotations

from collections import Counter, defaultdict

from orchestrator.discovery_models import (
    AgentActivityConfig,
    LabAgentState,
    MarketSimulationReport,
    ReportOutlineSection,
    SimulationParameters,
    SimulationRunState,
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def compile_market_report(
    idea_id: str,
    parameters: SimulationParameters,
    activity_config: AgentActivityConfig,
    run_state: SimulationRunState,
    agents: list[LabAgentState],
) -> MarketSimulationReport:
    last_round = run_state.round_summaries[-1]
    segment_scores: dict[str, list[float]] = defaultdict(list)
    objections = Counter()
    channel_scores = Counter()
    for agent in agents:
        stage_bonus = {
            "unaware": 0.0,
            "aware": 0.2,
            "considering": 0.4,
            "trial": 0.6,
            "adopted": 0.78,
            "retained": 0.9,
            "churned": 0.18,
        }.get(agent.adoption_stage, 0.0)
        segment_scores[agent.segment].append(stage_bonus)
        objections.update(agent.objections[:1] or ["unclear ROI"])
        channel_scores[agent.preferred_channel] += stage_bonus

    strongest_segments = [
        label
        for label, _ in sorted(
            ((segment, sum(values) / max(len(values), 1)) for segment, values in segment_scores.items()),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
    ]
    weakest_segments = [
        label
        for label, _ in sorted(
            ((segment, sum(values) / max(len(values), 1)) for segment, values in segment_scores.items()),
            key=lambda item: item[1],
        )[:2]
    ]

    adoption_rate = last_round.adoption_rate
    retention_rate = last_round.retention_rate
    virality_score = last_round.virality_score
    pain_relief_score = last_round.pain_relief_score
    objection_score = last_round.objection_pressure
    market_fit_score = round(
        _clamp(
            (adoption_rate * 0.28)
            + (retention_rate * 0.27)
            + (pain_relief_score * 0.27)
            + (virality_score * 0.12)
            - (objection_score * 0.18)
        ),
        4,
    )
    build_priority_score = round(
        _clamp(
            (market_fit_score * 0.62)
            + (retention_rate * 0.2)
            + (pain_relief_score * 0.14)
            - (objection_score * 0.1)
        ),
        4,
    )
    ranking_delta = {
        "rank_score_delta": round(max(-0.12, min(0.18, (build_priority_score - 0.5) * 0.24)), 4),
        "belief_score_delta": round(max(-0.1, min(0.16, ((retention_rate + pain_relief_score - objection_score) - 0.5) * 0.2)), 4),
    }

    if build_priority_score >= 0.68:
        verdict = "advance"
        executive_summary = "The market sandbox shows enough simulated pull to justify build approval or an immediate narrow pilot."
        recommended_actions = [
            "Move the strongest segment into an explicit pilot plan with one measurable success metric.",
            "Preserve the winning channel mix in the first GTM motion instead of widening too early.",
        ]
    elif build_priority_score >= 0.52:
        verdict = "pilot"
        executive_summary = "The market sandbox supports a pilot, but the wedge still needs disciplined scope and proof."
        recommended_actions = [
            "Package the product around the top segment and one dominant objection to remove first.",
            "Use the highest-lift channel from the simulation as the opening GTM path.",
        ]
    elif build_priority_score >= 0.38:
        verdict = "watch"
        executive_summary = "The sandbox shows partial demand, but objection pressure is still too high for broad build approval."
        recommended_actions = [
            "Keep the idea alive, but tighten proof and onboarding before allocating build bandwidth.",
            "Re-run after stronger evidence or a narrower ICP changes the adoption curve.",
        ]
    else:
        verdict = "reject"
        executive_summary = "The sandbox does not produce enough simulated adoption to justify build approval."
        recommended_actions = [
            "Do not build yet; rewrite the wedge or choose a sharper buyer with a more painful workflow.",
            "Only revisit when new evidence materially changes adoption or retention assumptions.",
        ]

    channel_findings = [
        f"{label} produced the most durable movement across the sandbox."
        for label, _ in channel_scores.most_common(3)
    ]
    outline = [
        ReportOutlineSection(
            title="Demand",
            bullets=[
                f"Adoption reached {round(adoption_rate * 100)}% by the final round.",
                f"Retention settled at {round(retention_rate * 100)}% of agents who entered the funnel.",
            ],
        ),
        ReportOutlineSection(
            title="Dynamics",
            bullets=[
                f"Virality ended at {round(virality_score * 100)}%, with strongest resonance in {', '.join(strongest_segments) or 'mixed segments'}.",
                f"Pain relief stabilized at {round(pain_relief_score * 100)}%, while objection pressure stayed at {round(objection_score * 100)}%.",
            ],
        ),
        ReportOutlineSection(
            title="Recommendation",
            bullets=recommended_actions,
        ),
    ]

    return MarketSimulationReport(
        idea_id=idea_id,
        parameters=parameters,
        activity_config=activity_config,
        run_state=run_state,
        agents=agents,
        executive_summary=executive_summary,
        verdict=verdict,
        adoption_rate=adoption_rate,
        retention_rate=retention_rate,
        virality_score=virality_score,
        pain_relief_score=pain_relief_score,
        objection_score=objection_score,
        market_fit_score=market_fit_score,
        build_priority_score=build_priority_score,
        ranking_delta=ranking_delta,
        strongest_segments=strongest_segments,
        weakest_segments=weakest_segments,
        channel_findings=channel_findings,
        key_objections=[label for label, _ in objections.most_common(4)],
        report_outline=outline,
        recommended_actions=recommended_actions,
    )
