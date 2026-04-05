"""Discovery trace snapshots across evidence, validation, ranking, and simulation."""

from __future__ import annotations

import re
from statistics import fmean

from orchestrator.discovery_models import (
    DiscoveryTraceSnapshot,
    IdeaDossier,
    IdeaTraceBundle,
    IdeaTraceStep,
    SessionTraceSummary,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.models import SessionStore


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def _clip(value: str, limit: int = 160) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _tokenize(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(str(value or ""))}


def _mean(values: list[float], default: float = 0.0) -> float:
    filtered = [float(value) for value in values]
    if not filtered:
        return default
    return float(fmean(filtered))


class DiscoveryTraceService:
    def __init__(self, discovery: DiscoveryStore, session_store: SessionStore):
        self._discovery = discovery
        self._session_store = session_store

    def _matching_sessions(self, dossier: IdeaDossier, session_summaries: list[dict]) -> list[str]:
        idea_terms = _tokenize(" ".join([dossier.idea.title, dossier.idea.summary, *dossier.idea.topic_tags]))
        matches: list[tuple[float, str]] = []
        for summary in session_summaries:
            task_terms = _tokenize(str(summary.get("task") or ""))
            if not idea_terms or not task_terms:
                continue
            overlap = len(idea_terms & task_terms) / max(len(idea_terms), 1)
            if overlap >= 0.2:
                matches.append((overlap, str(summary["id"])))
        matches.sort(reverse=True)
        return [session_id for _score, session_id in matches[:4]]

    def _bundle_for_dossier(self, dossier: IdeaDossier, session_summaries: list[dict]) -> IdeaTraceBundle:
        steps: list[IdeaTraceStep] = []
        for observation in dossier.observations:
            steps.append(
                IdeaTraceStep(
                    trace_kind="evidence",
                    stage="sourced",
                    title=f"Evidence from {observation.source}",
                    detail=_clip(observation.raw_text),
                    actor=observation.entity,
                    created_at=observation.captured_at,
                    score_delta={
                        "pain_score": float(observation.pain_score),
                        "trend_score": float(observation.trend_score),
                    },
                    metadata={"url": observation.url, "topic_tags": observation.topic_tags},
                )
            )
        for report in dossier.validation_reports:
            verdict = str(getattr(report.verdict, "value", report.verdict) or "").strip() or "review"
            steps.append(
                IdeaTraceStep(
                    trace_kind="validation",
                    stage="debated",
                    title=f"Validation: {verdict}",
                    detail=_clip(report.summary),
                    actor="judge",
                    created_at=report.created_at,
                    metadata={"findings": report.findings, "confidence": str(report.confidence)},
                )
            )
        for score in dossier.idea.score_snapshots:
            steps.append(
                IdeaTraceStep(
                    trace_kind="ranking",
                    stage="ranked",
                    title=f"Score snapshot: {score.label}",
                    detail=_clip(score.reason),
                    created_at=score.created_at,
                    score_delta={score.label: float(score.value)},
                )
            )
        for decision in dossier.decisions:
            decision_type = str(decision.decision_type or "decision")
            steps.append(
                IdeaTraceStep(
                    trace_kind="decision",
                    stage=dossier.idea.latest_stage,
                    title=f"Decision: {decision_type}",
                    detail=_clip(decision.rationale),
                    actor=decision.actor,
                    created_at=decision.created_at,
                    metadata=decision.metadata,
                )
            )
        for swipe in self._discovery.list_swipe_events(dossier.idea.idea_id, limit=50):
            steps.append(
                IdeaTraceStep(
                    trace_kind="swipe",
                    stage="swiped",
                    title=f"Swipe: {swipe.action}",
                    detail=_clip(swipe.rationale),
                    actor=swipe.actor,
                    created_at=swipe.created_at,
                    score_delta={key: float(value) for key, value in swipe.preference_delta.items()},
                    metadata=swipe.metadata,
                )
            )
        if dossier.simulation_report is not None:
            report = dossier.simulation_report
            steps.append(
                IdeaTraceStep(
                    trace_kind="simulation",
                    stage="simulated",
                    title=f"Focus group: {report.verdict}",
                    detail=_clip(report.summary_headline),
                    created_at=report.created_at,
                    latency_sec=float(report.run.step_count),
                    cost_usd=float(report.run.estimated_cost_usd),
                    score_delta={
                        "support_ratio": float(report.support_ratio),
                        "average_purchase_intent": float(report.average_purchase_intent),
                    },
                    metadata={"segments": report.strongest_segments, "objections": report.objections[:4]},
                )
            )
        if dossier.market_simulation_report is not None:
            report = dossier.market_simulation_report
            steps.append(
                IdeaTraceStep(
                    trace_kind="simulation",
                    stage="simulated",
                    title=f"Market sandbox: {report.verdict}",
                    detail=_clip(report.executive_summary),
                    created_at=report.created_at,
                    latency_sec=float(report.parameters.round_count),
                    score_delta={
                        "market_fit_score": float(report.market_fit_score),
                        "build_priority_score": float(report.build_priority_score),
                        "adoption_rate": float(report.adoption_rate),
                    },
                    metadata={"segments": report.strongest_segments, "objections": report.key_objections[:4]},
                )
            )
        for event in dossier.timeline:
            steps.append(
                IdeaTraceStep(
                    trace_kind="timeline",
                    stage=event.stage,
                    title=event.title,
                    detail=_clip(event.detail),
                    created_at=event.created_at,
                    metadata=event.metadata,
                )
            )
        steps.sort(key=lambda item: item.created_at)
        return IdeaTraceBundle(
            idea_id=dossier.idea.idea_id,
            title=dossier.idea.title,
            latest_stage=dossier.idea.latest_stage,
            last_updated_at=dossier.idea.updated_at,
            linked_session_ids=self._matching_sessions(dossier, session_summaries),
            steps=steps,
        )

    def _session_summary(self, session_id: str) -> SessionTraceSummary | None:
        session = self._session_store.get(session_id)
        if session is None:
            return None
        generation_trace = dict((session.get("config") or {}).get("generation_trace") or {})
        trace_artifact_count = len(generation_trace.get("trace_artifacts") or [])
        if generation_trace.get("final_artifact"):
            trace_artifact_count += 1
        protocol_trace = list(session.get("protocol_trace") or [])
        shadow = dict(session.get("protocol_shadow_validation") or {})
        topology_state = dict((session.get("config") or {}).get("topology_state") or {})
        return SessionTraceSummary(
            session_id=session_id,
            mode=str(session.get("mode") or ""),
            task=str(session.get("task") or ""),
            status=str(session.get("status") or ""),
            created_at=float(session.get("created_at") or 0.0),
            elapsed_sec=session.get("elapsed_sec"),
            selected_template=str(topology_state.get("selected_template") or "") or None,
            execution_mode=str((session.get("config") or {}).get("execution_mode") or "") or None,
            step_count=len(session.get("events") or []) + len(protocol_trace),
            invalid_transition_count=int(shadow.get("invalid_transitions") or 0),
            generation_artifact_count=trace_artifact_count,
        )

    def build_snapshot(self, limit: int = 25) -> DiscoveryTraceSnapshot:
        dossiers = self._discovery.list_dossiers(limit=max(1, min(limit, 250)), include_archived=True)
        session_summaries = self._session_store.list_recent(limit=50)
        bundles = [self._bundle_for_dossier(dossier, session_summaries) for dossier in dossiers]
        recent_sessions = [
            summary
            for summary in (self._session_summary(str(item["id"])) for item in session_summaries[:10])
            if summary is not None
        ]
        trace_count = sum(len(bundle.steps) for bundle in bundles)
        simulation_cost = sum(
            step.cost_usd
            for bundle in bundles
            for step in bundle.steps
            if step.trace_kind == "simulation"
        )
        metrics = {
            "average_steps_per_idea": round(trace_count / max(len(bundles), 1), 4),
            "session_invalid_transition_mean": round(
                _mean([float(item.invalid_transition_count) for item in recent_sessions], default=0.0), 4
            ),
            "simulation_cost_usd": round(simulation_cost, 4),
        }
        return DiscoveryTraceSnapshot(
            trace_count=trace_count,
            idea_count=len(bundles),
            session_count=len(recent_sessions),
            traces=bundles,
            recent_sessions=recent_sessions,
            metrics=metrics,
        )

    def get_idea_trace(self, idea_id: str) -> IdeaTraceBundle | None:
        session_summaries = self._session_store.list_recent(limit=50)
        dossier = self._discovery.get_dossier(idea_id)
        if dossier is None:
            return None
        return self._bundle_for_dossier(dossier, session_summaries)

