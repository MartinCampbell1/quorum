"""Cumulative idea-graph snapshots for discovery dossiers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import re

from orchestrator.discovery_models import (
    IdeaDossier,
    IdeaGraphCommunity,
    IdeaGraphContext,
    IdeaGraphEdge,
    IdeaGraphNode,
    IdeaGraphSnapshot,
)
from orchestrator.discovery_store import DiscoveryStore


_SERVICE_CACHE: dict[str, "IdeaGraphService"] = {}
_SERVICE_CACHE_LOCK = threading.Lock()
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(joined.encode('utf-8', 'ignore')).hexdigest()[:12]}"


def _clip(value: str, limit: int = 140) -> str:
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


class _GraphAccumulator:
    def __init__(self) -> None:
        self.nodes: dict[str, IdeaGraphNode] = {}
        self.edges: dict[str, IdeaGraphEdge] = {}
        self.adjacency: dict[str, set[str]] = defaultdict(set)

    def add_node(
        self,
        kind: str,
        label: str,
        *,
        key: str | None = None,
        summary: str = "",
        weight: float = 1.0,
        metadata: dict[str, object] | None = None,
    ) -> str:
        node_id = _stable_id("idea_graph_node", kind, key or label)
        existing = self.nodes.get(node_id)
        if existing is None:
            self.nodes[node_id] = IdeaGraphNode(
                node_id=node_id,
                kind=kind,
                label=label,
                summary=summary,
                weight=weight,
                metadata=metadata or {},
            )
        else:
            existing.weight = max(existing.weight, weight)
            if summary and not existing.summary:
                existing.summary = summary
            if metadata:
                existing.metadata.update(metadata)
        return node_id

    def add_edge(
        self,
        kind: str,
        source_node_id: str,
        target_node_id: str,
        *,
        weight: float = 1.0,
        evidence: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        edge_id = _stable_id("idea_graph_edge", kind, source_node_id, target_node_id)
        existing = self.edges.get(edge_id)
        if existing is None:
            self.edges[edge_id] = IdeaGraphEdge(
                edge_id=edge_id,
                kind=kind,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                weight=weight,
                evidence=_dedupe_keep_order(evidence or [], limit=6),
                metadata=metadata or {},
            )
        else:
            existing.weight = max(existing.weight, weight)
            if evidence:
                existing.evidence = _dedupe_keep_order([*existing.evidence, *evidence], limit=6)
            if metadata:
                existing.metadata.update(metadata)
        self.adjacency[source_node_id].add(target_node_id)
        self.adjacency[target_node_id].add(source_node_id)
        return edge_id


class IdeaGraphIndex:
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
                CREATE TABLE IF NOT EXISTS discovery_idea_graph_snapshots (
                    graph_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovery_idea_graph_created_at ON discovery_idea_graph_snapshots(created_at DESC)"
            )

    @staticmethod
    def _decode(payload_json: str) -> IdeaGraphSnapshot:
        return IdeaGraphSnapshot.model_validate_json(payload_json)

    def get_cached(self, source_hash: str) -> IdeaGraphSnapshot | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM discovery_idea_graph_snapshots
                WHERE source_hash = ?
                """,
                (source_hash,),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None

    def save_snapshot(self, source_hash: str, snapshot: IdeaGraphSnapshot) -> IdeaGraphSnapshot:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_idea_graph_snapshots (
                    graph_id, source_hash, created_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.graph_id,
                    source_hash,
                    float(snapshot.created_at.timestamp()),
                    snapshot.model_dump_json(),
                ),
            )
        return snapshot

    def list_snapshots(self, limit: int = 20) -> list[IdeaGraphSnapshot]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM discovery_idea_graph_snapshots
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode(row["payload_json"]) for row in rows]

    def get_snapshot(self, graph_id: str) -> IdeaGraphSnapshot | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM discovery_idea_graph_snapshots
                WHERE graph_id = ?
                """,
                (graph_id,),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None


class IdeaGraphBuilder:
    def source_hash(self, dossiers: list[IdeaDossier]) -> str:
        payload = [
            dossier.model_dump(mode="json")
            for dossier in sorted(dossiers, key=lambda item: (item.idea.idea_id, item.idea.updated_at))
        ]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(encoded.encode("utf-8", "ignore")).hexdigest()

    def build_snapshot(self, dossiers: list[IdeaDossier]) -> IdeaGraphSnapshot:
        graph = _GraphAccumulator()
        idea_node_ids: dict[str, str] = {}
        idea_titles: dict[str, str] = {}
        node_to_idea_id: dict[str, str] = {}
        idea_domains: dict[str, list[str]] = defaultdict(list)
        idea_buyers: dict[str, list[str]] = defaultdict(list)
        idea_failures: dict[str, list[str]] = defaultdict(list)
        idea_patterns: dict[str, list[str]] = defaultdict(list)
        idea_evidence: dict[str, list[str]] = defaultdict(list)

        for dossier in dossiers:
            idea = dossier.idea
            summary = _clip(idea.summary or idea.thesis or idea.description or idea.title, 180)
            idea_node_id = graph.add_node(
                "idea",
                idea.title,
                key=idea.idea_id,
                summary=summary,
                weight=1.0 + (idea.rank_score * 0.5) + (idea.belief_score * 0.5),
                metadata={
                    "idea_id": idea.idea_id,
                    "latest_stage": idea.latest_stage,
                    "swipe_state": idea.swipe_state,
                    "validation_state": idea.validation_state,
                    "rank_score": idea.rank_score,
                    "belief_score": idea.belief_score,
                },
            )
            idea_node_ids[idea.idea_id] = idea_node_id
            idea_titles[idea.idea_id] = idea.title
            node_to_idea_id[idea_node_id] = idea.idea_id

            source_node_id = graph.add_node(
                "source",
                idea.source,
                key=f"source:{idea.source}",
                summary=f"Idea source: {idea.source}",
            )
            graph.add_edge("originates_from", idea_node_id, source_node_id, evidence=[idea.source], weight=0.9)

            for domain in self._domains_for_dossier(dossier):
                domain_node_id = graph.add_node(
                    "domain",
                    domain,
                    key=f"domain:{domain}",
                    summary=f"Repeated discovery domain: {domain}",
                    weight=1.1,
                )
                idea_domains[idea.idea_id].append(domain)
                graph.add_edge("maps_to_domain", idea_node_id, domain_node_id, evidence=[domain], weight=1.05)

            for observation in dossier.observations[-3:]:
                evidence_summary = _clip(observation.raw_text, 180) or observation.url
                evidence_node_id = graph.add_node(
                    "evidence",
                    f"{observation.source}:{observation.entity}",
                    key=observation.observation_id,
                    summary=evidence_summary,
                    weight=0.7 + min(0.25, observation.pain_score * 0.2 + observation.trend_score * 0.1),
                    metadata={"url": observation.url, "source": observation.source},
                )
                idea_evidence[idea.idea_id].append(evidence_summary)
                graph.add_edge(
                    "backed_by",
                    idea_node_id,
                    evidence_node_id,
                    evidence=[evidence_summary],
                    weight=0.95,
                )

            for decision_label, rationale in self._decision_signals(dossier):
                decision_node_id = graph.add_node(
                    "decision",
                    decision_label,
                    key=f"{idea.idea_id}:decision:{decision_label}",
                    summary=_clip(rationale or decision_label, 160),
                    weight=0.85,
                )
                graph.add_edge(
                    "decided_as",
                    idea_node_id,
                    decision_node_id,
                    evidence=[_clip(rationale or decision_label, 90)],
                    weight=0.9,
                )

            for buyer in self._buyers_for_dossier(dossier):
                buyer_node_id = graph.add_node(
                    "buyer",
                    buyer,
                    key=f"buyer:{buyer}",
                    summary=f"Buyer/persona segment: {buyer}",
                    weight=1.0,
                )
                idea_buyers[idea.idea_id].append(buyer)
                graph.add_edge("targets_buyer", idea_node_id, buyer_node_id, evidence=[buyer], weight=1.0)

            for failure in self._failure_signals(dossier):
                failure_node_id = graph.add_node(
                    "failure",
                    failure,
                    key=f"failure:{failure}",
                    summary=f"Challenge surfaced in discovery history: {failure}",
                    weight=1.0,
                )
                idea_failures[idea.idea_id].append(failure)
                graph.add_edge("challenged_by", idea_node_id, failure_node_id, evidence=[failure], weight=1.05)

            for pattern in self._reusable_patterns(dossier):
                pattern_node_id = graph.add_node(
                    "pattern",
                    pattern,
                    key=f"pattern:{pattern}",
                    summary=f"Reusable business pattern: {pattern}",
                    weight=0.95,
                )
                idea_patterns[idea.idea_id].append(pattern)
                graph.add_edge("suggests_pattern", idea_node_id, pattern_node_id, evidence=[pattern], weight=0.92)

            for channel in self._channel_signals(dossier):
                channel_node_id = graph.add_node(
                    "channel",
                    channel,
                    key=f"channel:{channel}",
                    summary=f"GTM/distribution channel: {channel}",
                    weight=0.9,
                )
                graph.add_edge("uses_channel", idea_node_id, channel_node_id, evidence=[channel], weight=0.88)

            for outcome in self._outcome_signals(dossier):
                outcome_node_id = graph.add_node(
                    "outcome",
                    outcome,
                    key=f"{idea.idea_id}:outcome:{outcome}",
                    summary=f"Observed discovery outcome: {outcome}",
                    weight=1.0,
                )
                graph.add_edge("resulted_in", idea_node_id, outcome_node_id, evidence=[outcome], weight=1.0)

        self._connect_lineage(graph, dossiers, idea_node_ids)
        self._connect_shared(graph, idea_node_ids, idea_domains, "shares_domain", 0.86)
        self._connect_shared(graph, idea_node_ids, idea_buyers, "shares_buyer", 0.84)
        self._connect_shared(graph, idea_node_ids, idea_failures, "shares_failure", 0.8)

        contexts = self._build_contexts(
            graph=graph,
            idea_node_ids=idea_node_ids,
            node_to_idea_id=node_to_idea_id,
            idea_domains=idea_domains,
            idea_buyers=idea_buyers,
            idea_failures=idea_failures,
            idea_patterns=idea_patterns,
            idea_evidence=idea_evidence,
        )
        communities = self._build_communities(
            idea_node_ids=idea_node_ids,
            idea_titles=idea_titles,
            idea_domains=idea_domains,
            idea_buyers=idea_buyers,
            idea_failures=idea_failures,
            graph=graph,
        )

        return IdeaGraphSnapshot(
            idea_count=len(idea_node_ids),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            nodes=sorted(graph.nodes.values(), key=lambda item: (item.kind, item.label)),
            edges=sorted(graph.edges.values(), key=lambda item: (item.kind, item.source_node_id, item.target_node_id)),
            communities=communities,
            idea_contexts=contexts,
        )

    def _domains_for_dossier(self, dossier: IdeaDossier) -> list[str]:
        idea = dossier.idea
        values = list(idea.topic_tags)
        if idea.source:
            values.append(idea.source)
        values.extend(
            segment
            for segment in (
                *(dossier.simulation_report.strongest_segments if dossier.simulation_report else []),
                *(dossier.market_simulation_report.strongest_segments if dossier.market_simulation_report else []),
            )
            if len(segment.split()) <= 4
        )
        return _dedupe_keep_order(values, limit=6)

    def _buyers_for_dossier(self, dossier: IdeaDossier) -> list[str]:
        candidates: list[str] = []
        if dossier.simulation_report:
            candidates.extend(dossier.simulation_report.strongest_segments)
        if dossier.market_simulation_report:
            candidates.extend(dossier.market_simulation_report.strongest_segments)
            candidates.extend(dossier.market_simulation_report.weakest_segments[:1])
        return _dedupe_keep_order(candidates, limit=5)

    def _failure_signals(self, dossier: IdeaDossier) -> list[str]:
        failures: list[str] = []
        for report in dossier.validation_reports[-2:]:
            failures.extend(report.findings[:2])
            if report.verdict.value == "fail":
                failures.append(report.summary)
        for entry in dossier.archive_entries[-2:]:
            failures.append(entry.reason)
        if dossier.simulation_report:
            failures.extend(dossier.simulation_report.objections[:3])
        if dossier.market_simulation_report:
            failures.extend(dossier.market_simulation_report.key_objections[:3])
        return _dedupe_keep_order([_clip(value, 110) for value in failures], limit=6)

    def _decision_signals(self, dossier: IdeaDossier) -> list[tuple[str, str]]:
        decisions = [(decision.decision_type, decision.rationale) for decision in dossier.decisions[-3:]]
        if dossier.idea.swipe_state != "unseen":
            decisions.append((f"swipe:{dossier.idea.swipe_state}", f"Founder swipe state is {dossier.idea.swipe_state}."))
        return decisions

    def _reusable_patterns(self, dossier: IdeaDossier) -> list[str]:
        patterns: list[str] = []
        if dossier.execution_brief_candidate:
            patterns.extend(dossier.execution_brief_candidate.acceptance_criteria[:2])
            patterns.extend(story.title for story in dossier.execution_brief_candidate.first_stories[:2])
        if dossier.simulation_report:
            patterns.extend(dossier.simulation_report.recommended_actions[:2])
        if dossier.market_simulation_report:
            patterns.extend(dossier.market_simulation_report.recommended_actions[:2])
        return _dedupe_keep_order([_clip(item, 110) for item in patterns], limit=6)

    def _channel_signals(self, dossier: IdeaDossier) -> list[str]:
        if not dossier.market_simulation_report:
            return []
        channels = [
            value.split(" produced ", 1)[0].strip()
            for value in dossier.market_simulation_report.channel_findings
            if value.strip()
        ]
        return _dedupe_keep_order(channels, limit=4)

    def _outcome_signals(self, dossier: IdeaDossier) -> list[str]:
        outcomes: list[str] = []
        if dossier.execution_brief_candidate:
            outcomes.append("execution_brief_ready")
        if dossier.simulation_report:
            outcomes.append(f"focus_group:{dossier.simulation_report.verdict}")
        if dossier.market_simulation_report:
            outcomes.append(f"market_lab:{dossier.market_simulation_report.verdict}")
        if dossier.idea.validation_state == "archived":
            outcomes.append("archived")
        return _dedupe_keep_order(outcomes, limit=4)

    def _connect_lineage(
        self,
        graph: _GraphAccumulator,
        dossiers: list[IdeaDossier],
        idea_node_ids: dict[str, str],
    ) -> None:
        for dossier in dossiers:
            idea_id = dossier.idea.idea_id
            source_node_id = idea_node_ids.get(idea_id)
            if source_node_id is None:
                continue
            lineage_ids = _dedupe_keep_order([*dossier.idea.lineage_parent_ids, *dossier.idea.evolved_from])
            for parent_id in lineage_ids:
                target_node_id = idea_node_ids.get(parent_id)
                if target_node_id:
                    graph.add_edge("evolved_from", source_node_id, target_node_id, evidence=["lineage"], weight=1.15)
            for successor_id in dossier.idea.superseded_by:
                target_node_id = idea_node_ids.get(successor_id)
                if target_node_id:
                    graph.add_edge("superseded_by", source_node_id, target_node_id, evidence=["superseded"], weight=1.08)

    def _connect_shared(
        self,
        graph: _GraphAccumulator,
        idea_node_ids: dict[str, str],
        label_map: dict[str, list[str]],
        edge_kind: str,
        base_weight: float,
    ) -> None:
        inverse: dict[str, set[str]] = defaultdict(set)
        for idea_id, labels in label_map.items():
            for label in labels:
                inverse[label].add(idea_id)
        for label, idea_ids in inverse.items():
            if len(idea_ids) < 2:
                continue
            ordered = sorted(idea_ids)
            for left_id, right_id in combinations(ordered, 2):
                left_node_id = idea_node_ids.get(left_id)
                right_node_id = idea_node_ids.get(right_id)
                if left_node_id and right_node_id:
                    graph.add_edge(
                        edge_kind,
                        left_node_id,
                        right_node_id,
                        evidence=[label],
                        weight=min(1.15, base_weight + (len(ordered) * 0.03)),
                    )

    def _build_contexts(
        self,
        *,
        graph: _GraphAccumulator,
        idea_node_ids: dict[str, str],
        node_to_idea_id: dict[str, str],
        idea_domains: dict[str, list[str]],
        idea_buyers: dict[str, list[str]],
        idea_failures: dict[str, list[str]],
        idea_patterns: dict[str, list[str]],
        idea_evidence: dict[str, list[str]],
    ) -> list[IdeaGraphContext]:
        contexts: list[IdeaGraphContext] = []
        for idea_id, node_id in idea_node_ids.items():
            related_scores: dict[str, float] = defaultdict(float)
            lineage_ids: list[str] = []
            for edge in graph.edges.values():
                left_idea_id = node_to_idea_id.get(edge.source_node_id)
                right_idea_id = node_to_idea_id.get(edge.target_node_id)
                if left_idea_id == idea_id and right_idea_id:
                    if edge.kind in {"evolved_from", "superseded_by"}:
                        lineage_ids.append(right_idea_id)
                    elif edge.kind.startswith("shares_"):
                        related_scores[right_idea_id] += edge.weight
                elif right_idea_id == idea_id and left_idea_id:
                    if edge.kind in {"evolved_from", "superseded_by"}:
                        lineage_ids.append(left_idea_id)
                    elif edge.kind.startswith("shares_"):
                        related_scores[left_idea_id] += edge.weight
            related_idea_ids = [
                item[0]
                for item in sorted(related_scores.items(), key=lambda item: (-item[1], item[0]))[:5]
            ]
            contexts.append(
                IdeaGraphContext(
                    idea_id=idea_id,
                    related_idea_ids=related_idea_ids,
                    lineage_idea_ids=_dedupe_keep_order(lineage_ids, limit=6),
                    domain_clusters=_dedupe_keep_order(idea_domains.get(idea_id, []), limit=6),
                    buyer_segments=_dedupe_keep_order(idea_buyers.get(idea_id, []), limit=5),
                    evidence_highlights=_dedupe_keep_order(idea_evidence.get(idea_id, []), limit=4),
                    failure_patterns=_dedupe_keep_order(idea_failures.get(idea_id, []), limit=4),
                    reusable_patterns=_dedupe_keep_order(idea_patterns.get(idea_id, []), limit=4),
                )
            )
        return sorted(contexts, key=lambda item: item.idea_id)

    def _build_communities(
        self,
        *,
        idea_node_ids: dict[str, str],
        idea_titles: dict[str, str],
        idea_domains: dict[str, list[str]],
        idea_buyers: dict[str, list[str]],
        idea_failures: dict[str, list[str]],
        graph: _GraphAccumulator,
    ) -> list[IdeaGraphCommunity]:
        communities: list[IdeaGraphCommunity] = []
        inverse_domains: dict[str, set[str]] = defaultdict(set)
        for idea_id, domains in idea_domains.items():
            for domain in domains:
                inverse_domains[domain].add(idea_id)
        for domain, idea_ids in inverse_domains.items():
            ordered = sorted(idea_ids)
            if not ordered:
                continue
            highlights = _dedupe_keep_order(
                [
                    *(idea_titles[idea_id] for idea_id in ordered[:2]),
                    *(buyer for idea_id in ordered for buyer in idea_buyers.get(idea_id, [])[:1]),
                    *(failure for idea_id in ordered for failure in idea_failures.get(idea_id, [])[:1]),
                ],
                limit=5,
            )
            communities.append(
                IdeaGraphCommunity(
                    community_id=_stable_id("idea_graph_comm", domain),
                    title=domain,
                    summary=f"{domain} links {len(ordered)} ideas across discovery history.",
                    node_ids=[idea_node_ids[idea_id] for idea_id in ordered if idea_id in idea_node_ids],
                    idea_ids=ordered,
                    highlights=highlights,
                    score=round(sum(graph.nodes[idea_node_ids[idea_id]].weight for idea_id in ordered if idea_id in idea_node_ids) / max(len(ordered), 1), 3),
                )
            )
        if not communities:
            communities.append(
                IdeaGraphCommunity(
                    title="portfolio-core",
                    summary="Fallback portfolio community for the current discovery graph.",
                    node_ids=sorted(idea_node_ids.values())[:12],
                    idea_ids=sorted(idea_node_ids.keys())[:12],
                    highlights=["The portfolio has not formed strong reusable clusters yet."],
                    score=0.1,
                )
            )
        communities.sort(key=lambda item: item.score, reverse=True)
        return communities[:6]


class IdeaGraphService:
    def __init__(self, index: IdeaGraphIndex, discovery_store: DiscoveryStore, builder: IdeaGraphBuilder | None = None):
        self._index = index
        self._store = discovery_store
        self._builder = builder or IdeaGraphBuilder()
        self._snapshot_lock = threading.RLock()
        self._cached_token: str | None = None
        self._cached_snapshot: IdeaGraphSnapshot | None = None

    async def rebuild(self, refresh: bool = False) -> IdeaGraphSnapshot:
        return await asyncio.to_thread(self._ensure_snapshot_sync, refresh)

    def _ensure_snapshot_sync(self, refresh: bool = False) -> IdeaGraphSnapshot:
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
        snapshot = self._builder.build_snapshot(dossiers)
        self._index.save_snapshot(source_hash, snapshot)
        with self._snapshot_lock:
            self._cached_token = source_hash
            self._cached_snapshot = snapshot
        return snapshot

    def list_snapshots(self, limit: int = 20) -> list[IdeaGraphSnapshot]:
        return self._index.list_snapshots(limit=limit)

    def get_snapshot(self, graph_id: str) -> IdeaGraphSnapshot | None:
        return self._index.get_snapshot(graph_id)

    def get_idea_context(self, idea_id: str, refresh: bool = False) -> IdeaGraphContext | None:
        snapshot = self._ensure_snapshot_sync(refresh=refresh)
        context = next((item for item in snapshot.idea_contexts if item.idea_id == idea_id), None)
        if context is None:
            return None
        return context.model_copy(update={"graph_id": snapshot.graph_id})


def get_idea_graph_service(db_path: str, discovery_store: DiscoveryStore) -> IdeaGraphService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(normalized)
        if service is None:
            service = IdeaGraphService(IdeaGraphIndex(normalized), discovery_store)
            _SERVICE_CACHE[normalized] = service
        return service


def clear_idea_graph_service_cache() -> None:
    with _SERVICE_CACHE_LOCK:
        _SERVICE_CACHE.clear()
