"""Explainability surfaces for discovery dossiers."""

from __future__ import annotations

import re

from orchestrator.debate.judge_pack import heuristic_founder_scorecard
from orchestrator.discovery_models import IdeaDossier, IdeaExplainabilitySnapshot
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.models import SessionStore
from orchestrator.observability.evals import DiscoveryEvaluationService


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def _clip(value: str, limit: int = 160) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _tokenize(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(str(value or ""))}


def _metric_label(key: str) -> str:
    return key.replace("_", " ")


class DossierExplainabilityService:
    def __init__(
        self,
        discovery: DiscoveryStore,
        session_store: SessionStore,
        evals: DiscoveryEvaluationService,
    ):
        self._discovery = discovery
        self._session_store = session_store
        self._evals = evals

    def _supporting_sessions(self, dossier: IdeaDossier) -> tuple[list[str], list[str]]:
        idea_terms = _tokenize(" ".join([dossier.idea.title, dossier.idea.summary, *dossier.idea.topic_tags]))
        matched_ids: list[str] = []
        protocol_keys: list[str] = []
        for summary in self._session_store.list_recent_protocol_summaries(limit=50):
            overlap = idea_terms & _tokenize(str(summary.get("task") or ""))
            if not overlap:
                continue
            matched_ids.append(str(summary["id"]))
            blueprint = dict(summary.get("protocol_blueprint") or {})
            protocol_key = str(blueprint.get("protocol_key") or blueprint.get("cache_key") or "").strip()
            if protocol_key:
                protocol_keys.append(protocol_key)
            if len(matched_ids) >= 5:
                break
        deduped_protocols: list[str] = []
        seen: set[str] = set()
        for key in protocol_keys:
            if key in seen:
                continue
            seen.add(key)
            deduped_protocols.append(key)
        return matched_ids, deduped_protocols

    def build(self, idea_id: str) -> IdeaExplainabilitySnapshot | None:
        dossier = self._discovery.get_dossier(idea_id)
        if dossier is None:
            return None
        evaluation = self._evals.evaluate_idea(idea_id)
        supporting_sessions, linked_protocols = self._supporting_sessions(dossier)

        scorecard = {
            key: float(value)
            for key, value in dossier.idea.latest_scorecard.items()
            if isinstance(value, (int, float))
        }
        top_metrics = sorted(scorecard.items(), key=lambda item: item[1], reverse=True)[:4]
        low_metrics = sorted(scorecard.items(), key=lambda item: item[1])[:3]
        ranking_drivers = [
            f"{_metric_label(key)} at {round(value * 100)}."
            for key, value in top_metrics
            if value > 0
        ]
        if evaluation is not None:
            if evaluation.evidence_quality_score >= 0.6:
                ranking_drivers.append("Evidence quality is strong enough to justify the current rank.")
            if evaluation.anti_banality_score >= 0.6:
                ranking_drivers.append("The idea still escapes the obvious banality traps.")
        ranking_risks = [
            f"{_metric_label(key)} is weak at {round(value * 100)}."
            for key, value in low_metrics
        ]

        latest_report = dossier.validation_reports[-1] if dossier.validation_reports else None
        judge_summary = ""
        judge_pass_reasons: list[str] = []
        judge_fail_reasons: list[str] = []
        if latest_report is not None:
            judge_summary = _clip(latest_report.summary)
            founder_scorecard = heuristic_founder_scorecard(
                " ".join([latest_report.summary, *latest_report.findings])
            )
            judge_pass_reasons = [
                f"{metric.replace('_', ' ')} scored {round(score, 1)}/10."
                for metric, score in founder_scorecard.items()
                if score >= 6.5
            ][:4]
            judge_fail_reasons = [
                *[_clip(item) for item in latest_report.findings[:4]],
                *[
                    f"{metric.replace('_', ' ')} scored {round(score, 1)}/10."
                    for metric, score in founder_scorecard.items()
                    if score <= 4.5
                ][:2],
            ]
        else:
            judge_summary = "No validation report yet."
            judge_fail_reasons = ["The idea has not been through a formal judge pass yet."]

        recent_observations = sorted(dossier.observations, key=lambda item: item.captured_at, reverse=True)[:4]
        evidence_changes = [
            f"{item.source}: {_clip(item.raw_text)}"
            for item in recent_observations
        ]
        evidence_change_summary = (
            f"{len(recent_observations)} recent evidence updates are attached."
            if recent_observations
            else "No evidence refresh has landed yet."
        )

        simulation_summary = "No simulation feedback yet."
        simulation_objections: list[str] = []
        simulation_recommendations: list[str] = []
        if dossier.simulation_report is not None:
            simulation_summary = _clip(dossier.simulation_report.summary_headline)
            simulation_objections.extend(dossier.simulation_report.objections[:4])
            simulation_recommendations.extend(dossier.simulation_report.recommended_actions[:3])
        if dossier.market_simulation_report is not None:
            simulation_summary = _clip(dossier.market_simulation_report.executive_summary)
            simulation_objections.extend(dossier.market_simulation_report.key_objections[:4])
            simulation_recommendations.extend(dossier.market_simulation_report.recommended_actions[:3])

        if evaluation is not None:
            ranking_risks.extend(
                flag.replace("_", " ")
                for flag in evaluation.flags
                if flag not in {"unsimulated", "unvalidated"}
            )

        return IdeaExplainabilitySnapshot(
            idea_id=idea_id,
            ranking_summary=(
                f"{dossier.idea.title} is currently ranked at {round(dossier.idea.rank_score * 100)} "
                f"rank score and {round(dossier.idea.belief_score * 100)} belief."
            ),
            ranking_drivers=ranking_drivers[:5],
            ranking_risks=ranking_risks[:5],
            judge_summary=judge_summary,
            judge_pass_reasons=judge_pass_reasons[:5],
            judge_fail_reasons=judge_fail_reasons[:5],
            evidence_change_summary=evidence_change_summary,
            evidence_changes=evidence_changes,
            simulation_summary=simulation_summary,
            simulation_objections=[_clip(item) for item in simulation_objections[:5]],
            simulation_recommendations=[_clip(item) for item in simulation_recommendations[:5]],
            evaluation=evaluation,
            supporting_sessions=supporting_sessions,
            linked_protocols=linked_protocols,
        )
