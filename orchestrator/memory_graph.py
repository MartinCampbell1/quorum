"""Institutional memory snapshots and query layer for discovery."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
import re

from orchestrator.discovery_models import (
    CrossSessionPreferenceMemory,
    ExecutionOutcomeRecord,
    FounderPreferenceProfile,
    IdeaDossier,
    IdeaSkillLibraryEntry,
    InstitutionalMemoryContext,
    MemoryEpisode,
    MemoryGraphSnapshot,
    MemoryQueryMatch,
    MemoryQueryRequest,
    MemoryQueryResponse,
    SemanticMemoryRecord,
    SwipeEventRecord,
)
from orchestrator.discovery_store import DiscoveryStore


_SERVICE_CACHE: dict[str, "MemoryGraphService"] = {}
_SERVICE_CACHE_LOCK = threading.Lock()
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
_STOP_CATEGORIES = {
    "manual",
    "draft",
    "reviewed",
    "decision",
    "brief",
    "validation",
    "simulation",
    "market_lab",
    "archive",
    "source",
    "github",
    "research",
}


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(joined.encode('utf-8', 'ignore')).hexdigest()[:12]}"


def _clip(value: str, limit: int = 160) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _dedupe_keep_order(values: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
        if limit is not None and len(output) >= limit:
            break
    return output


def _tokenize(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_PATTERN.finditer(value or "")}


def _overlap_score(query_tokens: set[str], texts: list[str], base_strength: float) -> float:
    if not query_tokens:
        return 0.0
    item_tokens = set().union(*(_tokenize(text) for text in texts if text))
    overlap = len(query_tokens & item_tokens)
    if overlap == 0:
        joined = " ".join(texts).lower()
        substring_hits = sum(1 for token in query_tokens if token in joined)
        if substring_hits == 0:
            return 0.0
        overlap = substring_hits
    lexical = overlap / max(len(query_tokens), 1)
    return round(min(1.0, lexical * 0.75 + base_strength * 0.25), 4)


class MemoryGraphIndex:
    def __init__(self, db_path: str):
        self._db_path = Path(db_path).expanduser().resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_memory_graph_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_memory_graph_created_at ON discovery_memory_graph_snapshots(created_at DESC)"
            )

    @staticmethod
    def _decode(payload_json: str) -> MemoryGraphSnapshot:
        return MemoryGraphSnapshot.model_validate_json(payload_json)

    def get_cached(self, source_hash: str) -> MemoryGraphSnapshot | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM discovery_memory_graph_snapshots
                WHERE source_hash = ?
                """,
                (source_hash,),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None

    def save_snapshot(self, source_hash: str, snapshot: MemoryGraphSnapshot) -> MemoryGraphSnapshot:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_memory_graph_snapshots (
                    snapshot_id, source_hash, created_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    source_hash,
                    float(snapshot.created_at.timestamp()),
                    snapshot.model_dump_json(),
                ),
            )
        return snapshot

    def list_snapshots(self, limit: int = 20) -> list[MemoryGraphSnapshot]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM discovery_memory_graph_snapshots
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode(row["payload_json"]) for row in rows]

    def get_snapshot(self, snapshot_id: str) -> MemoryGraphSnapshot | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM discovery_memory_graph_snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None


class MemoryGraphBuilder:
    def source_hash(
        self,
        dossiers: list[IdeaDossier],
        swipe_events: list[SwipeEventRecord],
        preference_profile: FounderPreferenceProfile,
    ) -> str:
        payload = {
            "dossiers": [
                dossier.model_dump(mode="json")
                for dossier in sorted(dossiers, key=lambda item: (item.idea.idea_id, item.idea.updated_at))
            ],
            "swipe_events": [
                event.model_dump(mode="json")
                for event in sorted(swipe_events, key=lambda item: (item.idea_id, item.created_at))
            ],
            "preference_profile": preference_profile.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(encoded.encode("utf-8", "ignore")).hexdigest()

    def build_snapshot(
        self,
        dossiers: list[IdeaDossier],
        swipe_events: list[SwipeEventRecord],
        preference_profile: FounderPreferenceProfile,
    ) -> MemoryGraphSnapshot:
        episodes = self._build_episodes(dossiers, swipe_events)
        semantic_memories = self._consolidate_semantic(episodes)
        skill_library = self._build_skill_library(dossiers, episodes)
        preference_memory = self._build_preference_memory(preference_profile)
        return MemoryGraphSnapshot(
            episode_count=len(episodes),
            semantic_memory_count=len(semantic_memories),
            skill_count=len(skill_library),
            episodes=episodes,
            semantic_memories=semantic_memories,
            skill_library=skill_library,
            preference_memory=preference_memory,
        )

    def _build_episodes(
        self,
        dossiers: list[IdeaDossier],
        swipe_events: list[SwipeEventRecord],
    ) -> list[MemoryEpisode]:
        episodes: list[MemoryEpisode] = []
        for dossier in dossiers:
            idea = dossier.idea
            idea_categories = list(idea.topic_tags[:3]) or [idea.source]
            for observation in dossier.observations:
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="observation",
                        title=f"{observation.source}:{observation.entity}",
                        summary=_clip(observation.raw_text, 180),
                        categories=_dedupe_keep_order(
                            [
                                *observation.topic_tags[:3],
                                observation.source,
                                observation.entity,
                                *(["pain"] if observation.pain_score >= 0.65 else []),
                                *(["trend"] if observation.trend_score >= 0.6 else []),
                            ],
                            limit=6,
                        ),
                        source_ref=observation.observation_id,
                        weight=min(1.0, 0.55 + observation.pain_score * 0.25 + observation.trend_score * 0.15),
                        created_at=observation.captured_at,
                        metadata={"url": observation.url, "source": observation.source},
                    )
                )
            for report in dossier.validation_reports:
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="validation",
                        title=f"validation:{report.verdict.value}",
                        summary=_clip(report.summary, 180),
                        categories=_dedupe_keep_order(
                            ["validation", report.verdict.value, *idea_categories, *report.findings[:2]],
                            limit=6,
                        ),
                        source_ref=report.report_id,
                        weight=0.72 if report.verdict.value == "pass" else 0.68,
                        created_at=report.created_at,
                        metadata={"verdict": report.verdict.value},
                    )
                )
            for decision in dossier.decisions:
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="decision",
                        title=decision.decision_type,
                        summary=_clip(decision.rationale, 180),
                        categories=_dedupe_keep_order(
                            ["decision", decision.decision_type, *idea_categories],
                            limit=5,
                        ),
                        source_ref=decision.decision_id,
                        weight=0.7,
                        created_at=decision.created_at,
                        metadata={"actor": decision.actor},
                    )
                )
            if dossier.execution_brief_candidate:
                brief = dossier.execution_brief_candidate
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="execution_brief",
                        title=brief.title,
                        summary=_clip(brief.prd_summary or brief.title, 180),
                        categories=_dedupe_keep_order(
                            ["brief", *idea_categories, *brief.recommended_tech_stack[:2]],
                            limit=6,
                        ),
                        source_ref=brief.brief_id,
                        weight=0.84,
                        created_at=brief.updated_at,
                        metadata={"confidence": brief.confidence.value, "effort": brief.effort.value},
                    )
                )
            if dossier.simulation_report:
                report = dossier.simulation_report
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="simulation",
                        title=f"focus_group:{report.verdict}",
                        summary=_clip(report.summary_headline, 180),
                        categories=_dedupe_keep_order(
                            ["simulation", report.verdict, *report.strongest_segments[:2], *report.objections[:2]],
                            limit=6,
                        ),
                        source_ref=report.report_id,
                        weight=0.75,
                        created_at=report.created_at,
                        metadata={"support_ratio": report.support_ratio},
                    )
                )
            if dossier.market_simulation_report:
                report = dossier.market_simulation_report
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="market_simulation",
                        title=f"market_lab:{report.verdict}",
                        summary=_clip(report.executive_summary, 180),
                        categories=_dedupe_keep_order(
                            [
                                "market_lab",
                                report.verdict,
                                *report.strongest_segments[:2],
                                *report.key_objections[:2],
                                *[value.split(" produced ", 1)[0] for value in report.channel_findings[:2]],
                            ],
                            limit=7,
                        ),
                        source_ref=report.report_id,
                        weight=min(1.0, 0.76 + report.build_priority_score * 0.2),
                        created_at=report.created_at,
                        metadata={"build_priority_score": report.build_priority_score},
                    )
                )
            for outcome in dossier.execution_outcomes:
                episodes.append(
                    self._execution_outcome_episode(idea.idea_id, outcome, idea_categories)
                )
            for archive in dossier.archive_entries:
                episodes.append(
                    MemoryEpisode(
                        idea_id=idea.idea_id,
                        kind="archive",
                        title="archive",
                        summary=_clip(archive.reason, 180),
                        categories=_dedupe_keep_order(["archive", "failure", *idea_categories, archive.reason], limit=6),
                        source_ref=archive.archive_id,
                        weight=0.68,
                        created_at=archive.created_at,
                        metadata={"superseded_by": archive.superseded_by_idea_id},
                    )
                )
        for event in swipe_events:
            episodes.append(
                MemoryEpisode(
                    idea_id=event.idea_id,
                    kind="swipe",
                    title=f"swipe:{event.action}",
                    summary=_clip(event.rationale or f"Founder marked idea as {event.action}.", 180),
                    categories=_dedupe_keep_order(["swipe", event.action], limit=3),
                    source_ref=event.event_id,
                    weight=0.63,
                    created_at=event.created_at,
                    metadata={"actor": event.actor},
                )
            )
        episodes.sort(key=lambda item: (item.created_at, item.idea_id, item.kind))
        return episodes

    def _consolidate_semantic(self, episodes: list[MemoryEpisode]) -> list[SemanticMemoryRecord]:
        grouped: dict[str, list[MemoryEpisode]] = defaultdict(list)
        labels: dict[str, str] = {}
        for episode in episodes:
            for category in episode.categories:
                label = category.strip()
                key = label.lower()
                if not label or key in _STOP_CATEGORIES or len(key) < 3:
                    continue
                grouped[key].append(episode)
                labels.setdefault(key, label)

        now = datetime.now(UTC).replace(tzinfo=None)
        records: list[SemanticMemoryRecord] = []
        for key, grouped_episodes in grouped.items():
            idea_ids = _dedupe_keep_order([item.idea_id for item in grouped_episodes], limit=12)
            episode_ids = [item.episode_id for item in grouped_episodes[:12]]
            latest = max(item.created_at for item in grouped_episodes)
            age_days = max((now - latest).total_seconds(), 0.0) / 86_400
            recency_score = round(max(0.15, 1.0 / (1.0 + age_days)), 4)
            base_strength = sum(item.weight for item in grouped_episodes) / max(len(grouped_episodes), 1)
            strength = round(min(1.0, base_strength * 0.65 + min(len(idea_ids), 4) * 0.08 + min(len(grouped_episodes), 6) * 0.03), 4)
            display_label = labels[key]
            dominant_kind = max(
                ((kind, sum(1 for item in grouped_episodes if item.kind == kind)) for kind in {item.kind for item in grouped_episodes}),
                key=lambda item: item[1],
            )[0]
            summary = f"Repeated {display_label} signal across {len(idea_ids)} ideas and {len(grouped_episodes)} episodes."
            records.append(
                SemanticMemoryRecord(
                    key=display_label,
                    category=dominant_kind,
                    summary=summary,
                    supporting_idea_ids=idea_ids,
                    supporting_episode_ids=episode_ids,
                    strength=strength,
                    recency_score=recency_score,
                    metadata={"episode_count": len(grouped_episodes), "dominant_kind": dominant_kind},
                )
            )
        records.sort(key=lambda item: (-item.strength, -item.recency_score, item.key.lower()))
        return records[:48]

    def _build_skill_library(
        self,
        dossiers: list[IdeaDossier],
        episodes: list[MemoryEpisode],
    ) -> list[IdeaSkillLibraryEntry]:
        episode_ids_by_idea: dict[str, list[str]] = defaultdict(list)
        for episode in episodes:
            episode_ids_by_idea[episode.idea_id].append(episode.episode_id)

        grouped: dict[str, IdeaSkillLibraryEntry] = {}
        for dossier in dossiers:
            idea = dossier.idea
            latest_execution = dossier.execution_outcomes[-1] if dossier.execution_outcomes else None
            positive_execution = latest_execution is not None and latest_execution.status.value in {
                "validated",
                "follow_on_opportunity",
            }
            positive = (
                idea.swipe_state in {"yes", "now"}
                or dossier.execution_brief_candidate is not None
                or (dossier.simulation_report is not None and dossier.simulation_report.verdict in {"pilot", "advance"})
                or (
                    dossier.market_simulation_report is not None
                    and dossier.market_simulation_report.verdict in {"pilot", "advance"}
                )
                or positive_execution
            )
            if not positive:
                continue

            buyers = []
            if dossier.simulation_report:
                buyers.extend(dossier.simulation_report.strongest_segments[:1])
            if dossier.market_simulation_report:
                buyers.extend(dossier.market_simulation_report.strongest_segments[:1])
            domain = idea.topic_tags[0] if idea.topic_tags else idea.source
            buyer = buyers[0] if buyers else "unscoped buyer"
            label = f"{domain} for {buyer}"
            recommended_moves: list[str] = []
            if dossier.market_simulation_report:
                recommended_moves.extend(dossier.market_simulation_report.recommended_actions[:2])
            if dossier.simulation_report:
                recommended_moves.extend(dossier.simulation_report.recommended_actions[:2])
            if dossier.execution_brief_candidate:
                recommended_moves.extend(dossier.execution_brief_candidate.acceptance_criteria[:2])
            if latest_execution is not None:
                recommended_moves.extend(latest_execution.lessons_learned[:2])
            trigger_signals = _dedupe_keep_order(
                [
                    *idea.topic_tags[:3],
                    *buyers[:2],
                    idea.source,
                    *(latest_execution.failure_modes[:1] if latest_execution is not None else []),
                ],
                limit=6,
            )
            confidence = min(
                1.0,
                0.55
                + (0.15 if dossier.execution_brief_candidate else 0.0)
                + (0.12 if idea.swipe_state in {"yes", "now"} else 0.0)
                + (0.14 if positive_execution else 0.0)
                + (
                    float(dossier.market_simulation_report.build_priority_score) * 0.15
                    if dossier.market_simulation_report
                    else 0.0
                ),
            )
            description = _clip(
                (
                    latest_execution.lessons_learned[0]
                    if latest_execution is not None and latest_execution.lessons_learned
                    else dossier.market_simulation_report.executive_summary
                    if dossier.market_simulation_report
                    else dossier.simulation_report.summary_headline
                    if dossier.simulation_report
                    else dossier.execution_brief_candidate.prd_summary
                    if dossier.execution_brief_candidate
                    else idea.summary or idea.title
                ),
                180,
            )
            group_key = label.lower()
            entry = grouped.get(group_key)
            if entry is None:
                grouped[group_key] = IdeaSkillLibraryEntry(
                    label=label,
                    pattern_type="buyer_wedge",
                    description=description,
                    trigger_signals=trigger_signals,
                    recommended_moves=_dedupe_keep_order([_clip(item, 110) for item in recommended_moves], limit=4),
                    supporting_idea_ids=[idea.idea_id],
                    source_episode_ids=episode_ids_by_idea.get(idea.idea_id, [])[:6],
                    confidence=round(confidence, 4),
                )
            else:
                entry.trigger_signals = _dedupe_keep_order([*entry.trigger_signals, *trigger_signals], limit=6)
                entry.recommended_moves = _dedupe_keep_order(
                    [*entry.recommended_moves, *[_clip(item, 110) for item in recommended_moves]],
                    limit=4,
                )
                entry.supporting_idea_ids = _dedupe_keep_order([*entry.supporting_idea_ids, idea.idea_id], limit=12)
                entry.source_episode_ids = _dedupe_keep_order(
                    [*entry.source_episode_ids, *episode_ids_by_idea.get(idea.idea_id, [])],
                    limit=12,
                )
                entry.confidence = round(max(entry.confidence, confidence), 4)
        skill_library = list(grouped.values())
        skill_library.sort(key=lambda item: (-item.confidence, item.label.lower()))
        return skill_library[:18]

    def _build_preference_memory(self, profile: FounderPreferenceProfile) -> CrossSessionPreferenceMemory:
        top_domains = [
            label
            for label, _ in sorted(profile.domain_weights.items(), key=lambda item: item[1], reverse=True)[:4]
        ]
        buyer_tilt = (
            "B2B"
            if profile.buyer_preferences.get("b2b", 0.0) >= profile.buyer_preferences.get("b2c", 0.0)
            else "B2C"
        )
        summary_points = [
            f"Founder bias leans toward {buyer_tilt} buyers.",
            f"Top repeated domains: {', '.join(top_domains) if top_domains else 'neutral portfolio'}.",
            f"AI necessity preference sits at {round(profile.ai_necessity_preference * 100)}%.",
            f"Preferred complexity sits at {round(profile.preferred_complexity * 100)}%.",
        ]
        return CrossSessionPreferenceMemory(
            profile_id=profile.profile_id,
            summary_points=summary_points,
            top_domains=top_domains,
            buyer_tilt=buyer_tilt,
            ai_necessity_preference=profile.ai_necessity_preference,
            preferred_complexity=profile.preferred_complexity,
            updated_at=profile.updated_at,
        )

    def _execution_outcome_episode(
        self,
        idea_id: str,
        outcome: ExecutionOutcomeRecord,
        idea_categories: list[str],
    ) -> MemoryEpisode:
        summary = _clip(
            "; ".join(
                [
                    *(outcome.lessons_learned[:2]),
                    *(outcome.failure_modes[:2]),
                    *(outcome.shipped_artifacts[:1]),
                ]
            )
            or f"Execution returned {outcome.status.value} with verdict {outcome.verdict.value}.",
            180,
        )
        weight = min(
            1.0,
            0.72
            + (0.1 if outcome.status.value in {"validated", "follow_on_opportunity"} else 0.0)
            + min(outcome.critic_pass_rate, 1.0) * 0.08
            + min(outcome.stories_passed / max(outcome.stories_attempted, 1), 1.0) * 0.06,
        )
        return MemoryEpisode(
            idea_id=idea_id,
            kind="execution_feedback",
            title=f"execution:{outcome.status.value}",
            summary=summary,
            categories=_dedupe_keep_order(
                [
                    "execution_feedback",
                    outcome.status.value,
                    outcome.verdict.value,
                    *idea_categories,
                    *outcome.failure_modes[:2],
                    *outcome.lessons_learned[:2],
                ],
                limit=8,
            ),
            source_ref=outcome.outcome_id,
            weight=weight,
            created_at=outcome.created_at,
            metadata={
                "project_id": outcome.autopilot_project_id,
                "approvals_count": outcome.approvals_count,
                "shipped_experiment_count": outcome.shipped_experiment_count,
            },
        )


class MemoryGraphService:
    def __init__(self, index: MemoryGraphIndex, discovery_store: DiscoveryStore, builder: MemoryGraphBuilder | None = None):
        self._index = index
        self._store = discovery_store
        self._builder = builder or MemoryGraphBuilder()
        self._snapshot_lock = threading.RLock()
        self._cached_token: str | None = None
        self._cached_snapshot: MemoryGraphSnapshot | None = None

    async def rebuild(self, refresh: bool = False) -> MemoryGraphSnapshot:
        return await asyncio.to_thread(self._ensure_snapshot_sync, refresh)

    def _ensure_snapshot_sync(self, refresh: bool = False) -> MemoryGraphSnapshot:
        source_hash = self._store.portfolio_cache_token()
        with self._snapshot_lock:
            if (
                not refresh
                and self._cached_token == source_hash
                and self._cached_snapshot is not None
            ):
                return self._cached_snapshot

        if not refresh:
            cached = self._index.get_cached(source_hash)
            if cached is not None:
                with self._snapshot_lock:
                    self._cached_token = source_hash
                    self._cached_snapshot = cached
                return cached

        dossiers = self._store.list_dossiers(limit=None, include_archived=True)
        swipe_events = self._store.list_swipe_events(limit=500)
        preference_profile = self._store.get_preference_profile()
        snapshot = self._builder.build_snapshot(dossiers, swipe_events, preference_profile)
        self._index.save_snapshot(source_hash, snapshot)
        with self._snapshot_lock:
            self._cached_token = source_hash
            self._cached_snapshot = snapshot
        return snapshot

    def list_snapshots(self, limit: int = 20) -> list[MemoryGraphSnapshot]:
        return self._index.list_snapshots(limit=limit)

    def get_snapshot(self, snapshot_id: str) -> MemoryGraphSnapshot | None:
        return self._index.get_snapshot(snapshot_id)

    def get_idea_context(self, idea_id: str, refresh: bool = False) -> InstitutionalMemoryContext | None:
        dossier = self._store.get_dossier(idea_id)
        if dossier is None:
            return None
        snapshot = self._ensure_snapshot_sync(refresh=refresh)
        idea_terms = _tokenize(" ".join([dossier.idea.title, dossier.idea.summary, *dossier.idea.topic_tags]))
        related_episode_ids = [episode.episode_id for episode in snapshot.episodes if episode.idea_id == idea_id][:8]
        related_idea_ids: list[str] = []
        semantic_highlights: list[str] = []
        for memory in snapshot.semantic_memories:
            if idea_id in memory.supporting_idea_ids or idea_terms & _tokenize(memory.key):
                semantic_highlights.append(memory.summary)
                related_idea_ids.extend(item for item in memory.supporting_idea_ids if item != idea_id)
        skill_hits: list[IdeaSkillLibraryEntry] = []
        for skill in snapshot.skill_library:
            trigger_overlap = idea_terms & set().union(*(_tokenize(item) for item in skill.trigger_signals))
            if idea_id in skill.supporting_idea_ids or trigger_overlap:
                skill_hits.append(skill)
                related_idea_ids.extend(item for item in skill.supporting_idea_ids if item != idea_id)
        preference_notes = (
            snapshot.preference_memory.summary_points if snapshot.preference_memory is not None else []
        )
        return InstitutionalMemoryContext(
            idea_id=idea_id,
            snapshot_id=snapshot.snapshot_id,
            semantic_highlights=_dedupe_keep_order(semantic_highlights, limit=4),
            related_episode_ids=related_episode_ids,
            related_idea_ids=_dedupe_keep_order(related_idea_ids, limit=6),
            skill_hits=skill_hits[:3],
            preference_notes=preference_notes[:3],
        )

    def query(self, request: MemoryQueryRequest, refresh: bool = False) -> MemoryQueryResponse:
        snapshot = self._ensure_snapshot_sync(refresh=refresh)
        query_tokens = _tokenize(request.query)
        matches: list[MemoryQueryMatch] = []

        for memory in snapshot.semantic_memories:
            score = _overlap_score(query_tokens, [memory.key, memory.summary], memory.strength)
            if score <= 0:
                continue
            matches.append(
                MemoryQueryMatch(
                    kind="semantic_memory",
                    title=memory.key,
                    summary=memory.summary,
                    score=score,
                    supporting_idea_ids=memory.supporting_idea_ids,
                    supporting_episode_ids=memory.supporting_episode_ids,
                    metadata={"category": memory.category},
                )
            )

        for skill in snapshot.skill_library:
            score = _overlap_score(query_tokens, [skill.label, skill.description, *skill.trigger_signals], skill.confidence)
            if score <= 0:
                continue
            matches.append(
                MemoryQueryMatch(
                    kind="skill",
                    title=skill.label,
                    summary=skill.description,
                    score=score,
                    supporting_idea_ids=skill.supporting_idea_ids,
                    supporting_episode_ids=skill.source_episode_ids,
                    metadata={"pattern_type": skill.pattern_type},
                )
            )

        for episode in snapshot.episodes:
            score = _overlap_score(query_tokens, [episode.title, episode.summary, *episode.categories], episode.weight)
            if score < 0.35:
                continue
            matches.append(
                MemoryQueryMatch(
                    kind="episode",
                    title=episode.title,
                    summary=episode.summary,
                    score=score,
                    supporting_idea_ids=[episode.idea_id],
                    supporting_episode_ids=[episode.episode_id],
                    metadata={"episode_kind": episode.kind},
                )
            )

        matches.sort(key=lambda item: (-item.score, item.kind, item.title.lower()))
        limited_matches = matches[: request.limit]
        related_idea_ids = _dedupe_keep_order(
            [idea_id for match in limited_matches for idea_id in match.supporting_idea_ids],
            limit=12,
        )
        counts = defaultdict(int)
        for match in limited_matches:
            counts[match.kind] += 1
        explanation = (
            f"Matched {counts['semantic_memory']} semantic memories, "
            f"{counts['skill']} skill patterns, and {counts['episode']} episodic memories."
        )
        return MemoryQueryResponse(
            query=request.query,
            snapshot_id=snapshot.snapshot_id,
            matches=limited_matches,
            related_idea_ids=related_idea_ids,
            explanation=explanation,
        )


def get_memory_graph_service(db_path: str, discovery_store: DiscoveryStore) -> MemoryGraphService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(normalized)
        if service is None:
            service = MemoryGraphService(MemoryGraphIndex(normalized), discovery_store)
            _SERVICE_CACHE[normalized] = service
        return service


def clear_memory_graph_service_cache() -> None:
    with _SERVICE_CACHE_LOCK:
        _SERVICE_CACHE.clear()
