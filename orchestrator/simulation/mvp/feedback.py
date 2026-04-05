"""Aggregation helpers for MVP focus-group simulation output."""

from __future__ import annotations

from collections import Counter, defaultdict

from orchestrator.discovery_models import (
    FocusGroupRun,
    FocusGroupTurn,
    SimulationFeedbackReport,
    VirtualPersona,
)


def _top_counts(values: list[str], limit: int = 4) -> list[str]:
    counter = Counter(value.strip() for value in values if value and value.strip())
    return [label for label, _ in counter.most_common(limit)]


def _verdict_from_support(support_ratio: float, purchase_intent: float) -> str:
    if support_ratio >= 0.68 and purchase_intent >= 0.62:
        return "advance"
    if support_ratio >= 0.48 and purchase_intent >= 0.46:
        return "pilot"
    if support_ratio >= 0.28:
        return "watch"
    return "reject"


def summarize_focus_group(
    idea_id: str,
    run: FocusGroupRun,
    personas: list[VirtualPersona],
) -> SimulationFeedbackReport:
    final_round = run.rounds[-1] if run.rounds else None
    final_responses = list(final_round.responses if final_round else [])
    if not final_responses:
        return SimulationFeedbackReport(
            idea_id=idea_id,
            run=run,
            personas=personas,
            summary_headline="The synthetic focus group produced no usable responses.",
            verdict="reject",
            recommended_actions=["Rerun the simulation with a different prompt frame and fresher evidence."],
        )

    support_ratio = round(
        sum(1 for response in final_responses if response.stance in {"trial", "champion"}) / max(len(final_responses), 1),
        4,
    )
    average_resonance = round(
        sum(response.resonance_score for response in final_responses) / max(len(final_responses), 1),
        4,
    )
    average_purchase_intent = round(
        sum(response.purchase_intent for response in final_responses) / max(len(final_responses), 1),
        4,
    )
    verdict = _verdict_from_support(support_ratio, average_purchase_intent)

    persona_by_id = {persona.persona_id: persona for persona in personas}
    segment_scores: dict[str, list[float]] = defaultdict(list)
    positive_reasons: list[str] = []
    blocking_reasons: list[str] = []
    desired_capabilities: list[str] = []
    pricing_signals: list[str] = []
    quotes: list[tuple[float, str]] = []

    for response in final_responses:
        persona = persona_by_id.get(response.persona_id)
        if persona is not None:
            segment_scores[persona.segment].append(response.purchase_intent)
            if response.purchase_intent >= 0.58:
                pricing_signals.append(f"{persona.segment} can justify {persona.budget_band} spend if activation is immediate.")
            else:
                pricing_signals.append(f"{persona.segment} wants proof before approving {persona.budget_band} spend.")
        quotes.append((response.purchase_intent + response.resonance_score, response.quote))

        if response.stance in {"trial", "champion"}:
            positive_reasons.extend(response.key_reasons[:2])
        else:
            blocking_reasons.extend(response.key_reasons[:2])
            desired_capabilities.extend(response.key_reasons[:2])

    strongest_segments = [
        label
        for label, _ in sorted(
            ((segment, sum(scores) / max(len(scores), 1)) for segment, scores in segment_scores.items()),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
    ]

    go_to_market_signals = [
        f"Early pull is strongest in {segment.replace('_', ' ')}." for segment in strongest_segments
    ]
    if support_ratio < 0.45:
        go_to_market_signals.append("The opening wedge is still weak enough that founder-led selling should stay narrow.")
    else:
        go_to_market_signals.append("The wedge is coherent enough for a narrowly scoped pilot motion.")

    if verdict == "advance":
        headline = "Synthetic buyers show enough pull to justify a narrowly scoped build."
        recommended_actions = [
            "Turn the top requested capability into the first activation loop.",
            "Run a small pilot against the strongest synthetic segment before broadening the wedge.",
        ]
    elif verdict == "pilot":
        headline = "The idea has believable pilot pull, but adoption depends on sharper proof and workflow fit."
        recommended_actions = [
            "Package the pilot around one concrete workflow and one measurable outcome.",
            "Trim objections that repeatedly mention setup friction or unclear ROI.",
        ]
    elif verdict == "watch":
        headline = "Synthetic interest exists, but the wedge is still soft and objections dominate commitment."
        recommended_actions = [
            "Rework the value proposition around one painkiller use case.",
            "Gather fresher evidence before moving this higher in the queue.",
        ]
    else:
        headline = "The current concept does not create enough believable pull in the MVP simulation."
        recommended_actions = [
            "Do not build yet; tighten the ICP and rewrite the pitch around a more painful workflow.",
            "Only rerun once new evidence changes the distribution or ROI story.",
        ]

    return SimulationFeedbackReport(
        idea_id=idea_id,
        run=run,
        personas=personas,
        summary_headline=headline,
        verdict=verdict,
        support_ratio=support_ratio,
        average_resonance=average_resonance,
        average_purchase_intent=average_purchase_intent,
        strongest_segments=strongest_segments,
        positive_signals=_top_counts(positive_reasons),
        objections=_top_counts(blocking_reasons),
        desired_capabilities=_top_counts(desired_capabilities),
        pricing_signals=list(dict.fromkeys(pricing_signals))[:4],
        go_to_market_signals=go_to_market_signals[:4],
        sample_quotes=[quote for _, quote in sorted(quotes, key=lambda item: item[0], reverse=True)[:3]],
        recommended_actions=recommended_actions,
    )
