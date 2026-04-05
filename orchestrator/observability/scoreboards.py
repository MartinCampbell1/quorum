"""Aggregate scoreboards and protocol regressions for discovery."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import fmean

from orchestrator.discovery_models import (
    DiscoveryObservabilityScoreboard,
    ObservabilityMetricRecord,
    ProtocolRegressionRecord,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.models import SessionStore
from orchestrator.observability.evals import DiscoveryEvaluationService


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _mean(values: list[float], default: float = 0.0) -> float:
    filtered = [float(value) for value in values]
    if not filtered:
        return default
    return float(fmean(filtered))


class DiscoveryScoreboardService:
    def __init__(
        self,
        discovery: DiscoveryStore,
        session_store: SessionStore,
        evals: DiscoveryEvaluationService,
    ):
        self._discovery = discovery
        self._session_store = session_store
        self._evals = evals

    def _protocol_regressions(self, sessions: list[dict]) -> list[ProtocolRegressionRecord]:
        groups: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for session in sessions:
            blueprint = dict(session.get("protocol_blueprint") or {})
            shadow = dict(session.get("protocol_shadow_validation") or {})
            protocol_key = str(blueprint.get("protocol_key") or blueprint.get("cache_key") or session.get("mode") or "unknown")
            bucket = groups[(str(session.get("mode") or ""), protocol_key)]
            bucket["session_count"] += 1
            if session.get("status") == "completed":
                bucket["completed_count"] += 1
            if session.get("status") == "failed":
                bucket["failed_count"] += 1
            bucket["latency_sum"] += float(session.get("elapsed_sec") or 0.0)
            bucket["cache_hits"] += 1 if shadow.get("cache_hit") else 0
            validated = int(shadow.get("validated_transitions") or 0)
            invalid = int(shadow.get("invalid_transitions") or 0)
            bucket["validated"] += validated
            bucket["invalid"] += invalid

        records: list[ProtocolRegressionRecord] = []
        for (mode, protocol_key), bucket in groups.items():
            total = max(bucket["session_count"], 1.0)
            transition_total = max(bucket["validated"] + bucket["invalid"], 1.0)
            records.append(
                ProtocolRegressionRecord(
                    protocol_key=protocol_key,
                    mode=mode,
                    session_count=int(bucket["session_count"]),
                    completed_count=int(bucket["completed_count"]),
                    failed_count=int(bucket["failed_count"]),
                    avg_latency_sec=round(bucket["latency_sum"] / total, 4),
                    invalid_transition_rate=round(bucket["invalid"] / transition_total, 4),
                    cache_hit_rate=round(bucket["cache_hits"] / total, 4),
                )
            )
        return sorted(records, key=lambda item: (item.invalid_transition_rate, -item.session_count), reverse=True)

    def build_scoreboard(self) -> DiscoveryObservabilityScoreboard:
        dossiers = self._discovery.list_dossiers(include_archived=True)
        ideas = [dossier.idea for dossier in dossiers]
        swipe_events = self._discovery.list_swipe_events(limit=5000)
        sessions = [
            session
            for session in (self._session_store.get(item["id"]) for item in self._session_store.list_recent(limit=100))
            if session is not None
        ]
        eval_pack = self._evals.build_pack()

        stage_distribution = Counter(str(idea.latest_stage or "unknown") for idea in ideas)
        swipe_distribution = Counter(str(event.action or "unknown") for event in swipe_events)
        active_ideas = [idea for idea in ideas if str(idea.validation_state) != "archived"]
        evidence_coverage = sum(1 for dossier in dossiers if dossier.observations)
        validation_coverage = sum(1 for dossier in dossiers if dossier.validation_reports)
        simulation_coverage = sum(
            1 for dossier in dossiers if dossier.simulation_report is not None or dossier.market_simulation_report is not None
        )
        total_simulation_cost = round(
            sum(float(dossier.simulation_report.run.estimated_cost_usd) for dossier in dossiers if dossier.simulation_report),
            4,
        )
        metrics = [
            ObservabilityMetricRecord(
                key="swipe_acceptance_rate",
                label="Swipe acceptance",
                value=_ratio(swipe_distribution.get("yes", 0) + swipe_distribution.get("now", 0), len(swipe_events)),
                unit="ratio",
                detail="Share of founder swipes that advanced an idea.",
            ),
            ObservabilityMetricRecord(
                key="maybe_rate",
                label="Maybe rate",
                value=_ratio(swipe_distribution.get("maybe", 0), len(swipe_events)),
                unit="ratio",
                detail="How often ideas are deferred instead of advanced or rejected.",
            ),
            ObservabilityMetricRecord(
                key="evidence_hit_rate",
                label="Evidence hit rate",
                value=_ratio(evidence_coverage, len(ideas)),
                unit="ratio",
                detail="Ideas with at least one supporting observation.",
            ),
            ObservabilityMetricRecord(
                key="validation_hit_rate",
                label="Validation hit rate",
                value=_ratio(validation_coverage, len(ideas)),
                unit="ratio",
                detail="Ideas with at least one validation report.",
            ),
            ObservabilityMetricRecord(
                key="simulation_hit_rate",
                label="Simulation coverage",
                value=_ratio(simulation_coverage, len(ideas)),
                unit="ratio",
                detail="Ideas with either focus-group or market-lab coverage.",
            ),
            ObservabilityMetricRecord(
                key="avg_session_latency_sec",
                label="Avg session latency",
                value=round(_mean([float(session.get("elapsed_sec") or 0.0) for session in sessions], default=0.0), 4),
                unit="seconds",
                detail="Average completed runtime duration across tracked sessions.",
            ),
            ObservabilityMetricRecord(
                key="estimated_cost_usd",
                label="Estimated sim cost",
                value=total_simulation_cost,
                unit="usd",
                detail="Synthetic-user cost accumulated from focus-group runs.",
            ),
        ]

        strongest = sorted(eval_pack.items, key=lambda item: item.overall_health, reverse=True)[:3]
        weakest = sorted(eval_pack.items, key=lambda item: item.overall_health)[:3]
        protocol_regressions = self._protocol_regressions(sessions)

        highlights: list[str] = []
        if strongest:
            highlights.append(
                f"Most resilient idea: {strongest[0].title} ({round(strongest[0].overall_health * 100)} health)."
            )
        if weakest:
            highlights.append(
                f"Needs scrutiny: {weakest[0].title} ({round(weakest[0].overall_health * 100)} health)."
            )
        if protocol_regressions:
            worst_protocol = protocol_regressions[0]
            highlights.append(
                f"Highest protocol drift currently sits in {worst_protocol.protocol_key} ({round(worst_protocol.invalid_transition_rate * 100)}% invalid transitions)."
            )

        return DiscoveryObservabilityScoreboard(
            idea_count=len(ideas),
            active_idea_count=len(active_ideas),
            session_count=len(sessions),
            stage_distribution=dict(stage_distribution),
            swipe_distribution=dict(swipe_distribution),
            metrics=metrics,
            evaluation_averages=eval_pack.averages,
            weakest_ideas=weakest,
            strongest_ideas=strongest,
            protocol_regressions=protocol_regressions[:8],
            highlights=highlights,
        )

