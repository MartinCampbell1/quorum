"""Swipe queue ordering and founder preference learning for discovery ideas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from orchestrator.discovery_models import (
    FounderPreferenceProfile,
    IdeaChangeRecord,
    IdeaDecisionCreateRequest,
    IdeaDossier,
    IdeaQueueExplanation,
    IdeaQueueItem,
    IdeaSwipeRequest,
    IdeaSwipeResult,
    MaybeQueueEntry,
    MaybeQueueResponse,
    MaybeQueueSummary,
    SwipeEventRecord,
    SwipeQueueResponse,
    SwipeQueueSummary,
)
from orchestrator.discovery_store import DiscoveryStore


ACTION_WEIGHT = {
    "pass": -1.0,
    "maybe": 0.18,
    "yes": 0.7,
    "now": 1.0,
}
COMPLEXITY_VALUES = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.75,
    "very_high": 0.95,
}
MARKET_KEYWORDS = {
    "developer-tools": {"developer", "devtools", "repo", "cli", "sdk", "terminal", "plugin"},
    "workflow-automation": {"workflow", "orchestrator", "queue", "approval", "pipeline", "task"},
    "vertical-ai": {"vertical", "agent", "copilot", "automation", "assistant"},
    "analytics": {"analytics", "dashboard", "query", "metric", "insight", "report"},
    "security": {"security", "compliance", "audit", "policy"},
    "commerce": {"commerce", "ecommerce", "checkout", "cart", "merchant"},
    "sales": {"sales", "crm", "pipeline", "lead"},
    "support": {"support", "helpdesk", "ticket", "incident"},
    "healthtech": {"health", "clinical", "medical", "patient"},
    "fintech": {"fintech", "finance", "payment", "banking", "accounting"},
    "education": {"education", "learning", "course", "student"},
}
GENERIC_TAGS = {
    "idea",
    "startup",
    "saas",
    "ai",
    "b2b",
    "b2c",
    "consumer",
    "enterprise",
    "founder",
    "founderos",
    "repo",
    "portfolio",
    "discovery",
}
AI_KEYWORDS = {
    "ai",
    "agent",
    "agents",
    "llm",
    "model",
    "models",
    "prompt",
    "rag",
    "copilot",
    "openai",
    "langchain",
    "langgraph",
}
BUYER_B2B = {"b2b", "enterprise", "team", "workflow", "ops", "developer", "platform", "admin"}
BUYER_B2C = {"b2c", "consumer", "creator", "personal", "individual", "shopping", "family"}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def _first_sentence(text: str, limit: int = 120) -> str:
    rendered = " ".join(text.split())
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[: limit - 1].rstrip()}…"


def _flatten_strings(value: Any, limit: int = 40) -> list[str]:
    items: list[str] = []
    stack = [value]
    while stack and len(items) < limit:
        current = stack.pop(0)
        if isinstance(current, str):
            rendered = current.strip()
            if rendered:
                items.append(rendered)
        elif isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, (list, tuple, set)):
            stack.extend(current)
    return items


@dataclass
class IdeaFeatureVector:
    domains: list[str]
    markets: list[str]
    buyer: str | None
    complexity: float
    ai_necessity: float
    repo_dna_domains: list[str]
    repo_dna_present: bool

    def payload(self) -> dict[str, Any]:
        return {
            "domains": self.domains,
            "markets": self.markets,
            "buyer": self.buyer,
            "complexity": round(self.complexity, 4),
            "ai_necessity": round(self.ai_necessity, 4),
            "repo_dna_domains": self.repo_dna_domains,
            "repo_dna_present": self.repo_dna_present,
        }


class PreferenceModelService:
    def __init__(self, store: DiscoveryStore):
        self._store = store

    def get_preference_profile(self) -> FounderPreferenceProfile:
        return self._store.get_preference_profile()

    def swipe_idea(self, idea_id: str, request: IdeaSwipeRequest) -> IdeaSwipeResult:
        dossier = self._store.get_dossier(idea_id)
        if dossier is None:
            raise KeyError(f"Unknown idea id: {idea_id}")
        profile = self._store.get_preference_profile()
        features = self._extract_features(dossier)
        updated_profile, delta = self._apply_swipe(profile, features, request.action)
        decision = self._store.add_decision(
            idea_id,
            IdeaDecisionCreateRequest(
                decision_type=request.action,
                rationale=request.rationale or f"Portfolio triage marked this idea as {request.action}.",
                actor=request.actor,
                metadata={
                    **request.metadata,
                    "preference_model": "founder_default",
                    "feature_snapshot": features.payload(),
                },
            ),
        )
        swipe_event = SwipeEventRecord(
            idea_id=idea_id,
            action=request.action,
            rationale=request.rationale,
            actor=request.actor,
            feature_snapshot=features.payload(),
            preference_delta=delta,
            created_at=decision.created_at,
            metadata=request.metadata,
        )
        self._store.add_swipe_event(swipe_event)

        maybe_entry: MaybeQueueEntry | None = None
        existing_maybe = self._store.get_maybe_queue_entry(idea_id)
        if request.action == "maybe":
            revisit_after = max(1, int(request.revisit_after_hours))
            maybe_entry = MaybeQueueEntry(
                entry_id=existing_maybe.entry_id if existing_maybe else MaybeQueueEntry(idea_id=idea_id).entry_id,
                idea_id=idea_id,
                queued_at=decision.created_at,
                due_at=decision.created_at + timedelta(hours=revisit_after),
                last_seen_at=decision.created_at,
                last_rechecked_at=decision.created_at if existing_maybe else None,
                metadata={
                    **request.metadata,
                    "revisit_after_hours": revisit_after,
                },
            )
            self._store.upsert_maybe_queue_entry(maybe_entry)
        else:
            self._store.remove_maybe_queue_entry(idea_id)

        updated_profile.updated_at = decision.created_at
        self._store.save_preference_profile(updated_profile)
        return IdeaSwipeResult(
            idea=self._store.get_idea(idea_id) or dossier.idea,
            decision=decision,
            swipe_event=swipe_event,
            maybe_entry=maybe_entry,
            preference_profile=updated_profile,
        )

    def get_swipe_queue(self, limit: int = 20) -> SwipeQueueResponse:
        bounded_limit = max(1, min(limit, 100))
        profile = self._store.get_preference_profile()
        ideas = [idea for idea in self._store.list_ideas(limit=500) if idea.validation_state != "archived"]
        maybe_map = {entry.idea_id: entry for entry in self._store.list_maybe_queue_entries(limit=500)}
        now = _utcnow()

        items: list[IdeaQueueItem] = []
        maybe_ready_count = 0
        maybe_waiting_count = 0
        unseen_count = 0
        pass_count = 0
        yes_count = 0
        now_count = 0

        for idea in ideas:
            if idea.swipe_state == "unseen":
                unseen_count += 1
            elif idea.swipe_state == "pass":
                pass_count += 1
            elif idea.swipe_state == "yes":
                yes_count += 1
            elif idea.swipe_state == "now":
                now_count += 1

            if idea.swipe_state not in {"unseen", "maybe"}:
                continue
            dossier = self._store.get_dossier(idea.idea_id)
            if dossier is None:
                continue
            maybe_entry = maybe_map.get(idea.idea_id)
            change_record = self._build_change_record(
                dossier,
                maybe_entry.last_seen_at if maybe_entry else None,
            )
            recheck_ready = self._is_maybe_ready(maybe_entry, change_record, now)
            if idea.swipe_state == "maybe":
                if recheck_ready:
                    maybe_ready_count += 1
                else:
                    maybe_waiting_count += 1
                    continue
            item = self._build_queue_item(
                dossier=dossier,
                profile=profile,
                queue_kind="active",
                maybe_entry=maybe_entry,
                change_record=change_record,
                recheck_ready=recheck_ready,
            )
            items.append(item)

        items.sort(key=lambda item: (item.priority_score, item.idea.updated_at.timestamp()), reverse=True)
        return SwipeQueueResponse(
            items=items[:bounded_limit],
            preference_profile=profile,
            summary=SwipeQueueSummary(
                active_count=len(items),
                unseen_count=unseen_count,
                maybe_ready_count=maybe_ready_count,
                maybe_waiting_count=maybe_waiting_count,
                pass_count=pass_count,
                yes_count=yes_count,
                now_count=now_count,
            ),
        )

    def get_maybe_queue(self, limit: int = 20) -> MaybeQueueResponse:
        bounded_limit = max(1, min(limit, 100))
        profile = self._store.get_preference_profile()
        entries = self._store.list_maybe_queue_entries(limit=500)
        now = _utcnow()
        items: list[IdeaQueueItem] = []
        ready_count = 0
        waiting_count = 0

        for entry in entries:
            dossier = self._store.get_dossier(entry.idea_id)
            if dossier is None or dossier.idea.validation_state == "archived":
                continue
            change_record = self._build_change_record(dossier, entry.last_seen_at)
            recheck_ready = self._is_maybe_ready(entry, change_record, now)
            if recheck_ready:
                ready_count += 1
            else:
                waiting_count += 1
            items.append(
                self._build_queue_item(
                    dossier=dossier,
                    profile=profile,
                    queue_kind="maybe",
                    maybe_entry=entry,
                    change_record=change_record,
                    recheck_ready=recheck_ready,
                )
            )

        items.sort(
            key=lambda item: (
                1 if item.recheck_status == "ready" else 0,
                item.priority_score,
                item.idea.updated_at.timestamp(),
            ),
            reverse=True,
        )
        return MaybeQueueResponse(
            items=items[:bounded_limit],
            summary=MaybeQueueSummary(
                total_count=len(items),
                ready_count=ready_count,
                waiting_count=waiting_count,
            ),
        )

    def get_idea_changes(self, idea_id: str) -> IdeaChangeRecord:
        dossier = self._store.get_dossier(idea_id)
        if dossier is None:
            raise KeyError(f"Unknown idea id: {idea_id}")
        maybe_entry = self._store.get_maybe_queue_entry(idea_id)
        last_swipe = self._store.get_last_swipe_event(idea_id)
        since = maybe_entry.last_seen_at if maybe_entry else (last_swipe.created_at if last_swipe else None)
        return self._build_change_record(dossier, since)

    def _apply_swipe(
        self,
        profile: FounderPreferenceProfile,
        features: IdeaFeatureVector,
        action: str,
    ) -> tuple[FounderPreferenceProfile, dict[str, float]]:
        updated = profile.model_copy(deep=True)
        updated.swipe_count += 1
        updated.action_counts[action] = int(updated.action_counts.get(action, 0)) + 1
        weight = ACTION_WEIGHT[action]
        preference_delta: dict[str, float] = {}

        domain_step = 0.18 * weight if action != "maybe" else 0.05
        for domain in features.domains:
            previous = float(updated.domain_weights.get(domain, 0.0))
            updated.domain_weights[domain] = round(_clamp(previous + domain_step, -2.0, 2.0), 4)
            preference_delta[f"domain:{domain}"] = round(updated.domain_weights[domain] - previous, 4)

        market_step = 0.15 * weight if action != "maybe" else 0.04
        for market in features.markets:
            previous = float(updated.market_weights.get(market, 0.0))
            updated.market_weights[market] = round(_clamp(previous + market_step, -2.0, 2.0), 4)
            preference_delta[f"market:{market}"] = round(updated.market_weights[market] - previous, 4)

        if features.buyer in {"b2b", "b2c"}:
            previous = float(updated.buyer_preferences.get(features.buyer, 0.0))
            updated.buyer_preferences[features.buyer] = round(_clamp(previous + 0.16 * weight, -2.0, 2.0), 4)
            preference_delta[f"buyer:{features.buyer}"] = round(updated.buyer_preferences[features.buyer] - previous, 4)

        complexity_before = updated.preferred_complexity
        complexity_target = features.complexity if action in {"yes", "now", "maybe"} else 1.0 - features.complexity
        updated.preferred_complexity = round(
            _clamp(complexity_before + (complexity_target - complexity_before) * (0.22 if action != "pass" else 0.16), 0.0, 1.0),
            4,
        )
        preference_delta["preferred_complexity"] = round(updated.preferred_complexity - complexity_before, 4)

        tolerance_before = updated.complexity_tolerance
        distance = abs(features.complexity - complexity_before)
        tolerance_shift = 0.06 - distance * 0.04 if action in {"yes", "now"} else -0.04 if action == "pass" else 0.01
        updated.complexity_tolerance = round(_clamp(tolerance_before + tolerance_shift, 0.08, 0.95), 4)
        preference_delta["complexity_tolerance"] = round(updated.complexity_tolerance - tolerance_before, 4)

        ai_before = updated.ai_necessity_preference
        ai_target = features.ai_necessity if action in {"yes", "now", "maybe"} else 1.0 - features.ai_necessity
        updated.ai_necessity_preference = round(
            _clamp(ai_before + (ai_target - ai_before) * (0.24 if action in {"yes", "now"} else 0.1), 0.0, 1.0),
            4,
        )
        preference_delta["ai_necessity_preference"] = round(updated.ai_necessity_preference - ai_before, 4)
        return updated, preference_delta

    def _build_queue_item(
        self,
        dossier: IdeaDossier,
        profile: FounderPreferenceProfile,
        queue_kind: str,
        maybe_entry: MaybeQueueEntry | None,
        change_record: IdeaChangeRecord,
        recheck_ready: bool,
    ) -> IdeaQueueItem:
        idea = dossier.idea
        features = self._extract_features(dossier)
        score_deltas = self._score_idea(profile, dossier, features, maybe_entry, change_record, recheck_ready)
        last_swipe = self._store.get_last_swipe_event(idea.idea_id)
        latest_observation = dossier.observations[-1] if dossier.observations else None
        latest_validation = dossier.validation_reports[-1] if dossier.validation_reports else None
        explanation = IdeaQueueExplanation(
            headline=self._headline(idea, maybe_entry, recheck_ready, score_deltas["priority"]),
            source_signals=self._source_signals(dossier),
            score_deltas={key: round(value, 4) for key, value in score_deltas.items() if key != "priority"},
            lineage=self._lineage_summary(idea),
            newest_evidence=self._newest_evidence(dossier),
            repo_dna_match=self._repo_dna_match_text(features),
            preference_signals=self._preference_signals(profile, features),
            change_summary=change_record.summary_points,
        )
        return IdeaQueueItem(
            queue_kind=queue_kind,
            idea=idea,
            priority_score=round(score_deltas["priority"], 4),
            explanation=explanation,
            latest_observation=latest_observation,
            latest_validation_report=latest_validation,
            last_swipe_action=last_swipe.action if last_swipe else None,
            last_swiped_at=last_swipe.created_at if last_swipe else None,
            maybe_entry=maybe_entry,
            recheck_status="ready" if maybe_entry and recheck_ready else ("watching" if maybe_entry else None),
            has_new_evidence=bool(change_record.new_observations or change_record.new_validation_reports),
            repo_dna_match_score=round(score_deltas["repo_dna"], 4),
        )

    def _score_idea(
        self,
        profile: FounderPreferenceProfile,
        dossier: IdeaDossier,
        features: IdeaFeatureVector,
        maybe_entry: MaybeQueueEntry | None,
        change_record: IdeaChangeRecord,
        recheck_ready: bool,
    ) -> dict[str, float]:
        idea = dossier.idea
        observations = dossier.observations[-5:]
        if observations:
            evidence_strength = sum((obs.pain_score * 0.6) + (obs.trend_score * 0.4) for obs in observations) / len(observations)
        else:
            evidence_strength = 0.0

        validation_bonus = 0.0
        if dossier.validation_reports:
            verdict = dossier.validation_reports[-1].verdict.value
            if verdict == "pass":
                validation_bonus = 0.12
            elif verdict == "partial":
                validation_bonus = 0.04
            elif verdict == "fail":
                validation_bonus = -0.12

        domain_alignment = self._average_weight(profile.domain_weights, features.domains)
        market_alignment = self._average_weight(profile.market_weights, features.markets)
        buyer_alignment = 0.0
        if features.buyer:
            buyer_alignment = float(profile.buyer_preferences.get(features.buyer, 0.0)) / 2.0
        ai_alignment = 1.0 - abs(profile.ai_necessity_preference - features.ai_necessity)
        complexity_gap = abs(profile.preferred_complexity - features.complexity)
        complexity_alignment = 1.0 - max(0.0, complexity_gap - profile.complexity_tolerance)
        preference_alignment = (
            (domain_alignment * 0.35)
            + (market_alignment * 0.2)
            + (buyer_alignment * 0.15)
            + (ai_alignment * 0.15)
            + (complexity_alignment * 0.15)
        )

        repo_dna = 0.0
        if features.repo_dna_present:
            overlap = len(set(features.repo_dna_domains) & set(features.domains))
            repo_dna = min(1.0, 0.28 + (0.18 * overlap))

        change_bonus = min(
            0.16,
            (0.04 * len(change_record.new_observations))
            + (0.06 * len(change_record.new_validation_reports))
            + (0.02 * len(change_record.new_timeline_events)),
        )
        maybe_bonus = 0.08 if maybe_entry and recheck_ready else 0.0
        freshness_bonus = 0.02 if dossier.idea.swipe_state == "unseen" else 0.0
        base_rank = (idea.rank_score * 0.55) + (idea.belief_score * 0.45)
        priority = (
            (base_rank * 0.52)
            + (evidence_strength * 0.16)
            + (validation_bonus)
            + (preference_alignment * 0.18)
            + (repo_dna * 0.09)
            + change_bonus
            + maybe_bonus
            + freshness_bonus
        )
        return {
            "priority": priority,
            "base_rank": base_rank,
            "evidence": evidence_strength + validation_bonus,
            "preference": preference_alignment,
            "repo_dna": repo_dna,
            "change": change_bonus + maybe_bonus + freshness_bonus,
        }

    def _extract_features(self, dossier: IdeaDossier) -> IdeaFeatureVector:
        idea = dossier.idea
        provenance_strings = _flatten_strings(idea.provenance)
        repo_snapshot = self._repo_dna_snapshot(dossier)
        repo_dna_domains = [
            _normalize_label(item)
            for item in _flatten_strings(
                [
                    repo_snapshot.get("domain_clusters"),
                    repo_snapshot.get("dominant_domains"),
                    repo_snapshot.get("adjacent_product_opportunities"),
                ]
            )
        ]

        raw_tags = [item for item in idea.topic_tags if item]
        text_corpus = " ".join(
            [
                idea.title,
                idea.thesis,
                idea.summary,
                idea.description,
                " ".join(raw_tags),
                " ".join(provenance_strings),
                " ".join(obs.raw_text for obs in dossier.observations[-4:]),
            ]
        ).lower()
        tokens = {_normalize_label(token) for token in re.findall(r"[a-zA-Z0-9_\-]+", text_corpus)}
        domains = []
        for tag in raw_tags:
            normalized = _normalize_label(tag)
            if not normalized or normalized in GENERIC_TAGS or normalized in {"pass", "maybe", "yes", "now"}:
                continue
            domains.append(normalized)
        domains.extend(repo_dna_domains)
        domains = list(dict.fromkeys(item for item in domains if item))
        if not domains:
            for market, keywords in MARKET_KEYWORDS.items():
                if tokens & keywords:
                    domains.append(market)
        domains = domains[:6]

        markets: list[str] = []
        for market, keywords in MARKET_KEYWORDS.items():
            if market in domains or tokens & keywords:
                markets.append(market)
        markets = list(dict.fromkeys(markets))[:4]
        if not markets and domains:
            markets = domains[:2]

        buyer = None
        if tokens & BUYER_B2C:
            buyer = "b2c"
        elif tokens & BUYER_B2B or "developer-tools" in markets or "workflow-automation" in markets:
            buyer = "b2b"

        complexity = self._infer_complexity(idea.provenance, repo_snapshot, dossier)
        ai_hits = len(tokens & AI_KEYWORDS)
        ai_necessity = 1.0 if bool(repo_snapshot.get("idea_generation_context")) and ai_hits > 0 else min(1.0, 0.15 + (0.18 * ai_hits))
        if isinstance(idea.provenance.get("ai_native"), bool):
            ai_necessity = 0.92 if idea.provenance["ai_native"] else 0.18

        return IdeaFeatureVector(
            domains=domains,
            markets=markets,
            buyer=buyer,
            complexity=complexity,
            ai_necessity=round(ai_necessity, 4),
            repo_dna_domains=list(dict.fromkeys(repo_dna_domains))[:6],
            repo_dna_present=bool(repo_snapshot),
        )

    def _infer_complexity(self, provenance: dict[str, Any], repo_snapshot: dict[str, Any], dossier: IdeaDossier) -> float:
        for source in (provenance, repo_snapshot):
            for key in ("preferred_complexity", "complexity", "repo_complexity"):
                value = source.get(key)
                if isinstance(value, str) and value.strip().lower() in COMPLEXITY_VALUES:
                    return COMPLEXITY_VALUES[value.strip().lower()]
                if isinstance(value, (int, float)):
                    return _clamp(float(value), 0.0, 1.0)
        structural_weight = 0.35
        if dossier.execution_brief_candidate:
            structural_weight += min(0.22, len(dossier.execution_brief_candidate.first_stories) * 0.06)
        structural_weight += min(0.15, len(dossier.observations) * 0.03)
        structural_weight += min(0.12, len(dossier.idea.topic_tags) * 0.02)
        return round(_clamp(structural_weight, 0.15, 0.92), 4)

    def _repo_dna_snapshot(self, dossier: IdeaDossier) -> dict[str, Any]:
        idea = dossier.idea
        candidates = [
            idea.provenance.get("repo_dna_profile"),
            idea.provenance.get("repo_dna"),
            idea.provenance.get("repo_profile"),
        ]
        if dossier.execution_brief_candidate and dossier.execution_brief_candidate.repo_dna_snapshot:
            candidates.append(dossier.execution_brief_candidate.repo_dna_snapshot)
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate:
                return candidate
        return {}

    def _build_change_record(self, dossier: IdeaDossier, since: datetime | None) -> IdeaChangeRecord:
        if since is None:
            summary_points = ["First review pending."]
            if dossier.observations:
                summary_points.append(f"{len(dossier.observations)} evidence items already attached.")
            if dossier.validation_reports:
                summary_points.append(f"{len(dossier.validation_reports)} validation reports already attached.")
            return IdeaChangeRecord(
                idea_id=dossier.idea.idea_id,
                since=None,
                summary_points=summary_points,
                new_observations=dossier.observations,
                new_validation_reports=dossier.validation_reports,
                new_timeline_events=dossier.timeline,
            )

        new_observations = [item for item in dossier.observations if item.captured_at > since]
        new_validation_reports = [item for item in dossier.validation_reports if item.created_at > since]
        new_timeline_events = [item for item in dossier.timeline if item.created_at > since]
        summary_points: list[str] = []
        if new_observations:
            summary_points.append(f"{len(new_observations)} new evidence observations landed.")
        if new_validation_reports:
            summary_points.append(f"{len(new_validation_reports)} new validation reports were added.")
        noteworthy_titles = [
            event.title
            for event in new_timeline_events
            if event.title not in {"Decision recorded"}
        ][:2]
        summary_points.extend(noteworthy_titles)
        if not summary_points:
            summary_points.append("No new evidence since the last swipe.")
        return IdeaChangeRecord(
            idea_id=dossier.idea.idea_id,
            since=since,
            summary_points=summary_points,
            new_observations=new_observations,
            new_validation_reports=new_validation_reports,
            new_timeline_events=new_timeline_events,
        )

    def _is_maybe_ready(
        self,
        maybe_entry: MaybeQueueEntry | None,
        change_record: IdeaChangeRecord,
        now: datetime,
    ) -> bool:
        if maybe_entry is None:
            return True
        if now >= maybe_entry.due_at:
            return True
        meaningful_timeline = [
            event
            for event in change_record.new_timeline_events
            if event.title not in {"Decision recorded"}
        ]
        return bool(change_record.new_observations or change_record.new_validation_reports or meaningful_timeline)

    def _source_signals(self, dossier: IdeaDossier) -> list[str]:
        points: list[str] = []
        if dossier.observations:
            latest = dossier.observations[-1]
            points.append(
                f"{latest.source} evidence: pain {latest.pain_score:.2f}, trend {latest.trend_score:.2f}."
            )
        if dossier.validation_reports:
            latest_report = dossier.validation_reports[-1]
            points.append(f"Latest validation verdict: {latest_report.verdict.value}.")
        if dossier.execution_brief_candidate:
            points.append(
                f"Execution brief candidate exists with {len(dossier.execution_brief_candidate.first_stories)} starter stories."
            )
        return points[:3]

    def _lineage_summary(self, idea) -> list[str]:
        points: list[str] = []
        if idea.lineage_parent_ids:
            points.append(f"Lineage parents: {', '.join(idea.lineage_parent_ids[:2])}")
        if idea.evolved_from:
            points.append(f"Evolved from: {', '.join(idea.evolved_from[:2])}")
        if not points:
            points.append("Standalone idea candidate.")
        return points

    def _newest_evidence(self, dossier: IdeaDossier) -> list[str]:
        if not dossier.observations:
            return ["No external evidence captured yet."]
        rendered = []
        for observation in dossier.observations[-2:]:
            rendered.append(_first_sentence(observation.raw_text or observation.url))
        return rendered

    def _repo_dna_match_text(self, features: IdeaFeatureVector) -> str | None:
        if not features.repo_dna_present:
            return None
        if features.repo_dna_domains:
            return f"RepoDNA aligns with {', '.join(features.repo_dna_domains[:3])}."
        return "RepoDNA context is attached to this idea."

    def _preference_signals(
        self,
        profile: FounderPreferenceProfile,
        features: IdeaFeatureVector,
    ) -> list[str]:
        signals: list[str] = []
        strong_domains = [
            domain
            for domain in features.domains
            if float(profile.domain_weights.get(domain, 0.0)) > 0.2
        ]
        if strong_domains:
            signals.append(f"Strong domain fit: {', '.join(strong_domains[:3])}.")
        if features.buyer and float(profile.buyer_preferences.get(features.buyer, 0.0)) > 0.1:
            signals.append(f"Buyer tilt currently favors {features.buyer.upper()}.")
        complexity_gap = abs(profile.preferred_complexity - features.complexity)
        if complexity_gap <= profile.complexity_tolerance:
            signals.append("Complexity lands inside the current comfort band.")
        else:
            signals.append("Complexity sits outside the current comfort band.")
        return signals[:3]

    def _headline(
        self,
        idea,
        maybe_entry: MaybeQueueEntry | None,
        recheck_ready: bool,
        priority_score: float,
    ) -> str:
        if maybe_entry and recheck_ready:
            return "Maybe is back because either the timer expired or the evidence moved."
        if maybe_entry:
            return "Maybe is parked until more evidence or the revisit window arrives."
        if priority_score >= 0.6:
            return "Fresh idea with enough signal density to justify a decision now."
        return "Fresh idea with moderate signal; a fast portfolio call will sharpen the priors."

    def _average_weight(self, weights: dict[str, float], labels: Iterable[str]) -> float:
        values = [float(weights.get(label, 0.0)) for label in labels]
        if not values:
            return 0.0
        return sum(values) / max(1, len(values))
