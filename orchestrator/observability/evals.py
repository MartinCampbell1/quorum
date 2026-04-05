"""Portfolio eval packs for discovery quality monitoring."""

from __future__ import annotations

from statistics import fmean, pvariance
import threading

from orchestrator.debate.judge_pack import heuristic_founder_scorecard, scorecard_average
from orchestrator.discovery_models import (
    DiscoveryEvaluationPack,
    IdeaDossier,
    IdeaEvaluationScorecard,
)
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.novelty.semantic_tabu import assess_semantic_tabu


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _confidence_score(raw_value: object) -> float:
    value = str(getattr(raw_value, "value", raw_value) or "").strip().lower()
    return {"low": 0.35, "medium": 0.65, "high": 0.9}.get(value, 0.5)


def _mean(values: list[float], default: float = 0.0) -> float:
    filtered = [float(value) for value in values]
    if not filtered:
        return default
    return float(fmean(filtered))


def _clean_lines(values: list[str], limit: int = 4) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value or "").split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
        if len(output) >= limit:
            break
    return output


class DiscoveryEvaluationService:
    def __init__(self, discovery: DiscoveryStore):
        self._discovery = discovery
        self._cache_lock = threading.RLock()
        self._cached_token: str | None = None
        self._cached_pack: DiscoveryEvaluationPack | None = None
        self._cached_items_by_id: dict[str, IdeaEvaluationScorecard] = {}
        self._cached_dossier_count = 0

    def _peer_texts(self, dossiers: list[IdeaDossier], current_idea_id: str) -> list[str]:
        peers: list[str] = []
        for dossier in dossiers:
            if dossier.idea.idea_id == current_idea_id:
                continue
            peers.append(
                " ".join(
                    part
                    for part in [
                        dossier.idea.title,
                        dossier.idea.summary,
                        dossier.idea.description,
                        " ".join(dossier.idea.topic_tags),
                    ]
                    if str(part or "").strip()
                )
            )
        return peers

    def evaluate_dossier(
        self,
        dossier: IdeaDossier,
        *,
        portfolio: list[IdeaDossier] | None = None,
    ) -> IdeaEvaluationScorecard:
        candidate_text = " ".join(
            part
            for part in [
                dossier.idea.title,
                dossier.idea.thesis,
                dossier.idea.summary,
                dossier.idea.description,
            ]
            if str(part or "").strip()
        )
        domain_signals = list(dossier.idea.topic_tags)
        for observation in dossier.observations:
            domain_signals.extend(observation.topic_tags)
        taboo = assess_semantic_tabu(
            candidate_text,
            prior_candidates=self._peer_texts(portfolio or [], dossier.idea.idea_id),
            domain_signals=domain_signals,
        )

        observation_count = len(dossier.observations)
        observation_confidence = _mean(
            [_confidence_score(observation.evidence_confidence) for observation in dossier.observations],
            default=0.0,
        )
        signal_strength = _mean(
            [(float(item.pain_score) + float(item.trend_score)) / 2.0 for item in dossier.observations],
            default=0.0,
        )
        validation_count = len(dossier.validation_reports)
        evidence_quality_score = _clip(
            min(observation_count / 5.0, 1.0) * 0.35
            + observation_confidence * 0.25
            + signal_strength * 0.2
            + min(validation_count / 2.0, 1.0) * 0.1
            + (0.1 if dossier.evidence_bundle and dossier.evidence_bundle.items else 0.0)
        )

        novelty_score = _clip(
            1.0 - (taboo.similarity_to_prior * 0.65 + taboo.similarity_to_tabu_bank * 0.35)
        )
        anti_banality_score = _clip(
            taboo.specificity_score * 0.45
            + (1.0 - taboo.genericity_score) * 0.35
            + (1.0 - taboo.penalty) * 0.2
        )

        validation_confidences = [_confidence_score(report.confidence) for report in dossier.validation_reports]
        verdicts = [str(getattr(report.verdict, "value", report.verdict) or "") for report in dossier.validation_reports]
        verdict_ratio = 0.5
        if verdicts:
            verdict_ratio = max(verdicts.count(label) for label in set(verdicts)) / len(verdicts)
        founder_scores = [
            scorecard_average(heuristic_founder_scorecard(" ".join([report.summary, *report.findings])))
            for report in dossier.validation_reports
        ]
        founder_norm = _mean([score / 10.0 for score in founder_scores], default=0.5)
        variance_penalty = 0.0
        if len(founder_scores) > 1:
            variance_penalty = min(pvariance(founder_scores) / 16.0, 1.0)
        judge_consistency_score = _clip(
            verdict_ratio * 0.45
            + _mean(validation_confidences, default=0.5) * 0.25
            + founder_norm * 0.2
            + (1.0 - variance_penalty) * 0.1
        )

        calibration_samples: list[float] = []
        simulation_report = dossier.simulation_report
        if simulation_report is not None:
            verdict_weight = {
                "reject": 0.12,
                "watch": 0.42,
                "pilot": 0.72,
                "advance": 0.9,
            }.get(simulation_report.verdict, 0.45)
            focus_signal = _mean(
                [
                    float(simulation_report.support_ratio),
                    float(simulation_report.average_resonance),
                    float(simulation_report.average_purchase_intent),
                ],
                default=0.45,
            )
            calibration_samples.append(_clip(1.0 - abs(verdict_weight - focus_signal)))
        market_report = dossier.market_simulation_report
        if market_report is not None:
            verdict_weight = {
                "reject": 0.12,
                "watch": 0.42,
                "pilot": 0.72,
                "advance": 0.9,
            }.get(market_report.verdict, 0.45)
            market_signal = _mean(
                [
                    float(market_report.market_fit_score),
                    float(market_report.build_priority_score),
                    float(market_report.adoption_rate),
                    float(market_report.retention_rate),
                ],
                default=0.45,
            )
            calibration_samples.append(_clip(1.0 - abs(verdict_weight - market_signal)))
        if simulation_report is not None and market_report is not None:
            calibration_samples.append(
                _clip(
                    1.0
                    - abs(
                        float(simulation_report.support_ratio)
                        - _mean(
                            [float(market_report.market_fit_score), float(market_report.build_priority_score)],
                            default=0.45,
                        )
                    )
                )
            )
        simulation_calibration_score = _clip(_mean(calibration_samples, default=0.5))

        overall_health = _clip(
            novelty_score * 0.2
            + evidence_quality_score * 0.25
            + anti_banality_score * 0.2
            + judge_consistency_score * 0.15
            + simulation_calibration_score * 0.2
        )

        flags: list[str] = []
        rationales: list[str] = []
        if evidence_quality_score < 0.45:
            flags.append("thin_evidence")
            rationales.append("Evidence quality is still thin relative to the current claim surface.")
        if anti_banality_score < 0.45 or taboo.banned:
            flags.append("banality_risk")
        if taboo.reasons:
            rationales.extend(taboo.reasons[:2])
        if judge_consistency_score < 0.45:
            flags.append("judge_drift")
            rationales.append("Validation reports disagree or stay too shallow to trust.")
        if simulation_calibration_score < 0.45:
            flags.append("simulation_mismatch")
            rationales.append("Simulation verdict and measured traction signals do not align cleanly.")
        if not dossier.validation_reports:
            flags.append("unvalidated")
            rationales.append("No validation report exists yet, so the judge lane is still unproven.")
        if simulation_report is None and market_report is None:
            flags.append("unsimulated")
            rationales.append("No synthetic user or market simulation has been run yet.")

        return IdeaEvaluationScorecard(
            idea_id=dossier.idea.idea_id,
            title=dossier.idea.title,
            novelty_score=novelty_score,
            evidence_quality_score=evidence_quality_score,
            anti_banality_score=anti_banality_score,
            judge_consistency_score=judge_consistency_score,
            simulation_calibration_score=simulation_calibration_score,
            overall_health=overall_health,
            flags=_clean_lines(flags, limit=6),
            rationales=_clean_lines(rationales, limit=6),
        )

    def _build_pack_from_dossiers(self, dossiers: list[IdeaDossier]) -> DiscoveryEvaluationPack:
        items = [self.evaluate_dossier(dossier, portfolio=dossiers) for dossier in dossiers]
        averages = {
            "novelty_score": _clip(_mean([item.novelty_score for item in items], default=0.0)),
            "evidence_quality_score": _clip(_mean([item.evidence_quality_score for item in items], default=0.0)),
            "anti_banality_score": _clip(_mean([item.anti_banality_score for item in items], default=0.0)),
            "judge_consistency_score": _clip(_mean([item.judge_consistency_score for item in items], default=0.0)),
            "simulation_calibration_score": _clip(_mean([item.simulation_calibration_score for item in items], default=0.0)),
            "overall_health": _clip(_mean([item.overall_health for item in items], default=0.0)),
        }
        strongest = max(items, key=lambda item: item.overall_health, default=None)
        weakest = min(items, key=lambda item: item.overall_health, default=None)
        highlights: list[str] = []
        if strongest is not None:
            highlights.append(
                f"Strongest portfolio idea: {strongest.title} ({round(strongest.overall_health * 100)} health)."
            )
        if weakest is not None and weakest is not strongest:
            highlights.append(
                f"Primary watch item: {weakest.title} ({round(weakest.overall_health * 100)} health)."
            )
        return DiscoveryEvaluationPack(
            averages=averages,
            highlights=highlights,
            items=sorted(items, key=lambda item: item.overall_health, reverse=True),
        )

    def _cached_full_pack(self) -> DiscoveryEvaluationPack:
        token = self._discovery.portfolio_cache_token()
        with self._cache_lock:
            if self._cached_token == token and self._cached_pack is not None:
                return self._cached_pack

        dossiers = self._discovery.list_dossiers(include_archived=True)
        pack = self._build_pack_from_dossiers(dossiers)

        with self._cache_lock:
            self._cached_token = token
            self._cached_pack = pack
            self._cached_items_by_id = {item.idea_id: item for item in pack.items}
            self._cached_dossier_count = len(dossiers)
        return pack

    def evaluate_idea(self, idea_id: str) -> IdeaEvaluationScorecard | None:
        self._cached_full_pack()
        with self._cache_lock:
            return self._cached_items_by_id.get(idea_id)

    def build_pack(self, limit: int | None = None) -> DiscoveryEvaluationPack:
        pack = self._cached_full_pack()
        with self._cache_lock:
            dossier_count = self._cached_dossier_count
        if limit is None or limit >= dossier_count:
            return pack
        dossiers = self._discovery.list_dossiers(limit=limit, include_archived=True)
        return self._build_pack_from_dossiers(dossiers)
