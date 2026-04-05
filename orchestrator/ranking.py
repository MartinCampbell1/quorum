"""Pairwise ranking kernel for discovery ideas and tournament seeding."""

from __future__ import annotations

import math
import sqlite3
import threading
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.discovery_models import IdeaCandidate, IdeaUpdateRequest
from orchestrator.discovery_store import DiscoveryStore
from orchestrator.evolution.archive import ArchiveCheckpointDigest, IdeaArchiveSnapshot
from orchestrator.evolution.fitness import build_idea_genome
from orchestrator.evolution.map_elites import MapElitesArchive
from orchestrator.evolution.operators import build_recommendations
from orchestrator.evolution.prompt_evolution import evolve_prompt_profiles, infer_prompt_profile_id


PairwiseVerdict = Literal["left", "right", "tie"]
JudgeSource = Literal["human", "agent", "council", "system"]
ARCHIVE_CHECKPOINT_INTERVAL = 5

_SERVICE_CACHE: dict[str, "RankingService"] = {}
_SERVICE_CACHE_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _logistic_rating_gap(left_rating: float, right_rating: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((right_rating - left_rating) / 400.0))


def _rank_correlation(left: dict[str, int], right: dict[str, int]) -> float:
    keys = [item for item in left if item in right]
    count = len(keys)
    if count < 2:
        return 1.0
    diff_sq = sum((left[key] - right[key]) ** 2 for key in keys)
    denominator = count * ((count**2) - 1)
    if denominator <= 0:
        return 1.0
    return _clamp(1.0 - ((6.0 * diff_sq) / denominator), -1.0, 1.0)


def _label_for_entry(entry: dict[str, Any]) -> str:
    for key in ("project_label", "title", "idea_id", "role"):
        value = str(entry.get(key, "")).strip()
        if value:
            return value
    workspace_paths = [str(item).strip() for item in entry.get("workspace_paths") or [] if str(item).strip()]
    if workspace_paths:
        return Path(workspace_paths[0]).name
    return "candidate"


class PairwiseComparisonRequest(BaseModel):
    left_idea_id: str
    right_idea_id: str
    verdict: PairwiseVerdict
    rationale: str = ""
    judge_source: JudgeSource = "human"
    judge_model: str | None = None
    judge_agent_id: str | None = None
    domain_key: str | None = None
    judge_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    evidence_weight: float = Field(default=1.0, ge=0.1, le=3.0)
    agent_importance_score: float = Field(default=1.0, ge=0.1, le=3.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PairwiseComparisonRecord(BaseModel):
    comparison_id: str = Field(default_factory=lambda: _new_id("cmp"))
    left_idea_id: str
    right_idea_id: str
    verdict: PairwiseVerdict
    winner_idea_id: str | None = None
    loser_idea_id: str | None = None
    rationale: str = ""
    judge_source: JudgeSource = "human"
    judge_model: str | None = None
    judge_agent_id: str | None = None
    domain_key: str | None = None
    judge_confidence: float = 0.75
    evidence_weight: float = 1.0
    agent_importance_score: float = 1.0
    believability_weight: float = 1.0
    comparison_weight: float = 1.0
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def judge_key(self) -> str:
        identity = self.judge_agent_id or self.judge_model or "anonymous"
        domain = self.domain_key or "global"
        return f"{self.judge_source}:{identity}:{domain}"


class RankedIdeaRecord(BaseModel):
    idea: IdeaCandidate
    rank_position: int
    rating: float
    merit_score: float
    matches_played: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    stability_score: float
    volatility_score: float
    confidence_low: float
    confidence_high: float
    last_compared_at: datetime | None = None


class RankingJudgeBelievability(BaseModel):
    judge_key: str
    judge_source: JudgeSource
    judge_model: str | None = None
    judge_agent_id: str | None = None
    domain_key: str | None = None
    comparisons_count: int
    agreement_rate: float
    believability_score: float


class RankingMetrics(BaseModel):
    comparisons_count: int
    unique_pairs: int
    reliability_weighted: float
    rank_stability: float
    volatility_mean: float
    average_ci_width: float


class RankingLeaderboardResponse(BaseModel):
    items: list[RankedIdeaRecord] = Field(default_factory=list)
    judges: list[RankingJudgeBelievability] = Field(default_factory=list)
    metrics: RankingMetrics


class NextPairResponse(BaseModel):
    left: RankedIdeaRecord
    right: RankedIdeaRecord
    utility_score: float
    reason: str
    direct_comparisons: int
    candidate_pool_size: int


class PairwiseComparisonResponse(BaseModel):
    comparison: PairwiseComparisonRecord
    leaderboard: RankingLeaderboardResponse
    next_pair: NextPairResponse | None = None


class FinalVoteBallot(BaseModel):
    voter_id: str
    ranked_idea_ids: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.1, le=5.0)
    judge_source: JudgeSource = "human"
    judge_model: str | None = None
    judge_agent_id: str | None = None
    domain_key: str | None = None
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    agent_importance_score: float = Field(default=1.0, ge=0.1, le=3.0)

    @property
    def judge_key(self) -> str:
        identity = self.judge_agent_id or self.judge_model or self.voter_id
        domain = self.domain_key or "global"
        return f"{self.judge_source}:{identity}:{domain}"


class FinalVoteRound(BaseModel):
    round_number: int
    tallies: dict[str, float] = Field(default_factory=dict)
    eliminated_idea_id: str | None = None
    total_weight: float = 0.0


class FinalVoteRequest(BaseModel):
    candidate_idea_ids: list[str] = Field(default_factory=list)
    ballots: list[FinalVoteBallot] = Field(default_factory=list)


class FinalVoteResult(BaseModel):
    winner_idea_id: str | None = None
    rounds: list[FinalVoteRound] = Field(default_factory=list)
    aggregate_rankings: list[dict[str, float | int | str]] = Field(default_factory=list)


def order_tournament_pairings(
    entries: list[dict[str, Any]],
    prior_scores: dict[str, float] | None = None,
    previous_pairs: set[tuple[str, str]] | None = None,
    cell_signatures: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Greedy informative pairing for tournament entrants when priors are available."""

    remaining = list(entries)
    if len(remaining) < 2 or not prior_scores:
        matchups: list[dict[str, Any]] = []
        while len(remaining) >= 2:
            matchups.append({"a": remaining.pop(0), "b": remaining.pop(0)})
        return matchups, remaining

    pair_history = previous_pairs or set()
    cell_signatures = cell_signatures or {}

    def score(entry: dict[str, Any]) -> float:
        label = _label_for_entry(entry)
        return float(prior_scores.get(label, prior_scores.get(str(entry.get("role", "")).strip(), 0.5)))

    def niche(entry: dict[str, Any]) -> str:
        label = _label_for_entry(entry)
        explicit = str(entry.get("archive_cell") or entry.get("niche_key") or "").strip()
        return explicit or str(cell_signatures.get(label) or "")

    byes: list[dict[str, Any]] = []
    if len(remaining) % 2 == 1:
        bye = max(remaining, key=score)
        byes.append(bye)
        remaining.remove(bye)

    matchups: list[dict[str, Any]] = []
    while len(remaining) >= 2:
        best_indices: tuple[int, int] | None = None
        best_utility = float("-inf")
        for left_index in range(len(remaining)):
            for right_index in range(left_index + 1, len(remaining)):
                left = remaining[left_index]
                right = remaining[right_index]
                left_label = _label_for_entry(left)
                right_label = _label_for_entry(right)
                pair_key = tuple(sorted((left_label, right_label)))
                novelty = 0.6 if pair_key in pair_history else 1.0
                closeness = 1.0 - min(1.0, abs(score(left) - score(right)))
                left_niche = niche(left)
                right_niche = niche(right)
                diversity_multiplier = 1.0
                if left_niche and right_niche:
                    diversity_multiplier = 1.16 if left_niche != right_niche else 0.82
                utility = closeness * novelty * diversity_multiplier
                if utility > best_utility:
                    best_utility = utility
                    best_indices = (left_index, right_index)
        if best_indices is None:
            break
        left_index, right_index = best_indices
        right = remaining.pop(right_index)
        left = remaining.pop(left_index)
        pair_history.add(tuple(sorted((_label_for_entry(left), _label_for_entry(right)))))
        matchups.append({"a": left, "b": right})

    return matchups, byes


class RankingIndex:
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
                CREATE TABLE IF NOT EXISTS ranking_comparisons (
                    comparison_id TEXT PRIMARY KEY,
                    left_idea_id TEXT NOT NULL,
                    right_idea_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ranking_comparisons_created_at ON ranking_comparisons(created_at ASC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ranking_comparisons_pair ON ranking_comparisons(left_idea_id, right_idea_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ranking_archive_snapshots (
                    archive_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ranking_archive_snapshots_generation ON ranking_archive_snapshots(generation DESC)"
            )

    def save_comparison(self, comparison: PairwiseComparisonRecord) -> PairwiseComparisonRecord:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ranking_comparisons (
                    comparison_id, left_idea_id, right_idea_id, verdict, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    comparison.comparison_id,
                    comparison.left_idea_id,
                    comparison.right_idea_id,
                    comparison.verdict,
                    comparison.created_at.timestamp(),
                    comparison.model_dump_json(),
                ),
            )
        return comparison

    def list_comparisons(self, limit: int = 5000) -> list[PairwiseComparisonRecord]:
        bounded_limit = max(1, min(limit, 20000))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM ranking_comparisons
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [PairwiseComparisonRecord.model_validate_json(row["payload_json"]) for row in rows]

    def save_archive_snapshot(self, snapshot: IdeaArchiveSnapshot) -> IdeaArchiveSnapshot:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ranking_archive_snapshots (
                    archive_id, generation, created_at, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.archive_id,
                    int(snapshot.generation),
                    snapshot.created_at.timestamp(),
                    snapshot.model_dump_json(),
                ),
            )
        return snapshot

    def latest_archive_snapshot(self) -> IdeaArchiveSnapshot | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM ranking_archive_snapshots
                ORDER BY generation DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return IdeaArchiveSnapshot.model_validate_json(row["payload_json"])

    def list_archive_snapshots(self, limit: int = 20) -> list[IdeaArchiveSnapshot]:
        bounded_limit = max(1, min(limit, 100))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM ranking_archive_snapshots
                ORDER BY generation DESC, created_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [IdeaArchiveSnapshot.model_validate_json(row["payload_json"]) for row in rows]


class RankingService:
    def __init__(self, index: RankingIndex, discovery: DiscoveryStore):
        self._index = index
        self._discovery = discovery

    def record_comparison(self, request: PairwiseComparisonRequest) -> PairwiseComparisonResponse:
        active = self._active_ideas()
        if request.left_idea_id == request.right_idea_id:
            raise ValueError("left_idea_id and right_idea_id must differ")
        if request.left_idea_id not in active or request.right_idea_id not in active:
            raise KeyError("Unknown idea id for pairwise comparison")

        existing = self._index.list_comparisons(limit=5000)
        existing_profiles = self._judge_profiles(active, existing)
        believability = self._judge_believability_for_request(request, existing_profiles)
        winner_id: str | None = None
        loser_id: str | None = None
        if request.verdict == "left":
            winner_id = request.left_idea_id
            loser_id = request.right_idea_id
        elif request.verdict == "right":
            winner_id = request.right_idea_id
            loser_id = request.left_idea_id

        comparison_weight = round(
            _clamp(
                (0.55 + (0.45 * request.judge_confidence))
                * request.evidence_weight
                * request.agent_importance_score
                * believability,
                0.15,
                4.5,
            ),
            4,
        )
        record = PairwiseComparisonRecord(
            left_idea_id=request.left_idea_id,
            right_idea_id=request.right_idea_id,
            verdict=request.verdict,
            winner_idea_id=winner_id,
            loser_idea_id=loser_id,
            rationale=request.rationale,
            judge_source=request.judge_source,
            judge_model=request.judge_model,
            judge_agent_id=request.judge_agent_id,
            domain_key=request.domain_key,
            judge_confidence=request.judge_confidence,
            evidence_weight=request.evidence_weight,
            agent_importance_score=request.agent_importance_score,
            believability_weight=round(believability, 4),
            comparison_weight=comparison_weight,
            metadata=request.metadata,
        )
        self._index.save_comparison(record)
        comparisons = self._index.list_comparisons(limit=5000)
        leaderboard = self._build_leaderboard(active, comparisons, limit=50)
        archive_snapshot = self._build_archive_snapshot(active, leaderboard.items, comparisons, limit_cells=24)
        self._sync_discovery_scores(leaderboard.items, archive_snapshot=archive_snapshot)
        leaderboard = self.get_leaderboard(limit=50)
        return PairwiseComparisonResponse(
            comparison=record,
            leaderboard=leaderboard,
            next_pair=self.get_next_pair(),
        )

    def get_leaderboard(self, limit: int = 50) -> RankingLeaderboardResponse:
        ideas = self._active_ideas()
        comparisons = self._index.list_comparisons(limit=5000)
        leaderboard = self._build_leaderboard(ideas, comparisons, limit=limit)
        previous_order = self._build_previous_order(ideas, comparisons)
        current_order = {item.idea.idea_id: item.rank_position for item in leaderboard.items}
        rank_stability = _rank_correlation(current_order, previous_order)
        volatility_mean = fmean([item.volatility_score for item in leaderboard.items]) if leaderboard.items else 0.0
        average_ci_width = (
            fmean([item.confidence_high - item.confidence_low for item in leaderboard.items])
            if leaderboard.items
            else 0.0
        )
        pair_keys = {
            tuple(sorted((item.left_idea_id, item.right_idea_id)))
            for item in comparisons
        }
        leaderboard.metrics = RankingMetrics(
            comparisons_count=len(comparisons),
            unique_pairs=len(pair_keys),
            reliability_weighted=self._reliability_weighted(leaderboard.items, comparisons),
            rank_stability=round(rank_stability, 4),
            volatility_mean=round(volatility_mean, 4),
            average_ci_width=round(average_ci_width, 4),
        )
        leaderboard.judges = self._judge_profiles(ideas, comparisons)
        return leaderboard.model_copy(update={"items": leaderboard.items[: max(1, min(limit, 200))]})

    def get_next_pair(self) -> NextPairResponse | None:
        ideas = self._active_ideas()
        if len(ideas) < 2:
            return None
        comparisons = self._index.list_comparisons(limit=5000)
        leaderboard = self._build_leaderboard(ideas, comparisons, limit=200)
        by_id = {item.idea.idea_id: item for item in leaderboard.items}
        if len(by_id) < 2:
            return None

        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for comparison in comparisons:
            pair_counts[tuple(sorted((comparison.left_idea_id, comparison.right_idea_id)))] += 1
        genomes = {item.idea.idea_id: build_idea_genome(item.idea, item) for item in leaderboard.items}
        cell_counts: dict[str, int] = defaultdict(int)
        for genome in genomes.values():
            cell_counts[genome.cell_key] += 1

        best_pair: tuple[RankedIdeaRecord, RankedIdeaRecord] | None = None
        best_utility = float("-inf")
        best_direct_count = 0
        for left_index in range(len(leaderboard.items)):
            for right_index in range(left_index + 1, len(leaderboard.items)):
                left = leaderboard.items[left_index]
                right = leaderboard.items[right_index]
                if left.idea.idea_id == right.idea.idea_id:
                    continue
                pair_key = tuple(sorted((left.idea.idea_id, right.idea.idea_id)))
                direct_count = pair_counts.get(pair_key, 0)
                expected = _logistic_rating_gap(left.rating, right.rating)
                uncertainty = expected * (1.0 - expected)
                ci_overlap = max(
                    0.0,
                    ((left.confidence_high - left.confidence_low) + (right.confidence_high - right.confidence_low))
                    - abs(left.rating - right.rating),
                )
                ci_total = (left.confidence_high - left.confidence_low) + (right.confidence_high - right.confidence_low) + 1e-6
                ci_overlap_score = _clamp(ci_overlap / ci_total, 0.0, 1.0)
                balance = 1.0 - min(1.0, abs(left.matches_played - right.matches_played) / max(3, max(left.matches_played, right.matches_played, 1)))
                novelty = 1.0 / (1.0 + direct_count)
                left_genome = genomes[left.idea.idea_id]
                right_genome = genomes[right.idea.idea_id]
                diversity_bonus = 0.0
                if left_genome.cell_key != right_genome.cell_key:
                    diversity_bonus += 0.09
                if cell_counts[left_genome.cell_key] == 1 or cell_counts[right_genome.cell_key] == 1:
                    diversity_bonus += 0.06
                utility = (uncertainty * 0.42) + (ci_overlap_score * 0.27) + (balance * 0.1) + (novelty * 0.15) + diversity_bonus
                if utility > best_utility:
                    best_utility = utility
                    best_pair = (left, right)
                    best_direct_count = direct_count

        if best_pair is None:
            return None
        left, right = best_pair
        reason = (
            f"Near-tie utility is high ({best_utility:.2f}) because ratings are close "
            f"({abs(left.rating - right.rating):.1f} gap) and direct comparisons are only {best_direct_count}."
        )
        return NextPairResponse(
            left=left,
            right=right,
            utility_score=round(best_utility, 4),
            reason=reason,
            direct_comparisons=best_direct_count,
            candidate_pool_size=len(leaderboard.items),
        )

    def get_archive_view(self, limit_cells: int = 24) -> IdeaArchiveSnapshot:
        ideas = self._active_ideas()
        comparisons = self._index.list_comparisons(limit=5000)
        leaderboard = self._build_leaderboard(ideas, comparisons, limit=200)
        snapshot = self._build_archive_snapshot(ideas, leaderboard.items, comparisons, limit_cells=limit_cells)
        self._sync_discovery_scores(leaderboard.items, archive_snapshot=snapshot)
        return snapshot

    def resolve_finals(self, request: FinalVoteRequest) -> FinalVoteResult:
        leaderboard = self.get_leaderboard(limit=200)
        allowed_ids = request.candidate_idea_ids or [item.idea.idea_id for item in leaderboard.items[: max(2, min(8, len(leaderboard.items)))]]
        active = list(dict.fromkeys([item for item in allowed_ids if any(rank.idea.idea_id == item for rank in leaderboard.items)]))
        if not active:
            return FinalVoteResult()

        score_lookup = {item.idea.idea_id: item.rating for item in leaderboard.items}
        judge_profiles = {item.judge_key: item for item in leaderboard.judges}
        rounds: list[FinalVoteRound] = []
        working = list(active)

        while len(working) > 1:
            tallies = {idea_id: 0.0 for idea_id in working}
            total_weight = 0.0
            for ballot in request.ballots:
                ordered = [idea_id for idea_id in ballot.ranked_idea_ids if idea_id in working]
                if not ordered:
                    continue
                profile = judge_profiles.get(ballot.judge_key)
                believability = float(profile.believability_score if profile else 0.7)
                weight = ballot.weight * ballot.agent_importance_score * (0.55 + (0.45 * ballot.confidence)) * believability
                tallies[ordered[0]] += weight
                total_weight += weight

            round_number = len(rounds) + 1
            winner_id = max(tallies, key=tallies.get)
            if total_weight > 0 and tallies[winner_id] > (total_weight / 2.0):
                rounds.append(FinalVoteRound(round_number=round_number, tallies={key: round(value, 4) for key, value in tallies.items()}, total_weight=round(total_weight, 4)))
                return FinalVoteResult(
                    winner_idea_id=winner_id,
                    rounds=rounds,
                    aggregate_rankings=self._aggregate_rankings(request.ballots),
                )

            loser_id = min(
                tallies,
                key=lambda idea_id: (
                    tallies[idea_id],
                    score_lookup.get(idea_id, 0.0),
                ),
            )
            rounds.append(
                FinalVoteRound(
                    round_number=round_number,
                    tallies={key: round(value, 4) for key, value in tallies.items()},
                    eliminated_idea_id=loser_id,
                    total_weight=round(total_weight, 4),
                )
            )
            working.remove(loser_id)

        return FinalVoteResult(
            winner_idea_id=working[0] if working else None,
            rounds=rounds,
            aggregate_rankings=self._aggregate_rankings(request.ballots),
        )

    def _active_ideas(self) -> dict[str, IdeaCandidate]:
        ideas = self._discovery.list_ideas(limit=500)
        return {
            idea.idea_id: idea
            for idea in ideas
            if idea.validation_state != "archived" and idea.swipe_state != "pass"
        }

    def _build_leaderboard(
        self,
        ideas: dict[str, IdeaCandidate],
        comparisons: list[PairwiseComparisonRecord],
        limit: int,
    ) -> RankingLeaderboardResponse:
        ideas_state = self._rank_state(ideas, comparisons)
        items = sorted(ideas_state.values(), key=lambda item: item["rating"], reverse=True)
        ranked_items: list[RankedIdeaRecord] = []
        for index, item in enumerate(items, start=1):
            idea = ideas[item["idea_id"]]
            confidence_half_width = max(30.0, (260.0 / math.sqrt(item["matches"] + 1.0)) * (1.0 + (item["volatility"] / 140.0)))
            ranked_items.append(
                RankedIdeaRecord(
                    idea=idea,
                    rank_position=index,
                    rating=round(item["rating"], 3),
                    merit_score=round(item["merit"], 4),
                    matches_played=item["matches"],
                    wins=item["wins"],
                    losses=item["losses"],
                    ties=item["ties"],
                    win_rate=round(item["win_rate"], 4),
                    stability_score=round(item["stability"], 4),
                    volatility_score=round(item["volatility"], 4),
                    confidence_low=round(item["rating"] - confidence_half_width, 3),
                    confidence_high=round(item["rating"] + confidence_half_width, 3),
                    last_compared_at=item["last_compared_at"],
                )
            )
        return RankingLeaderboardResponse(
            items=ranked_items[: max(1, min(limit, 200))],
            judges=[],
            metrics=RankingMetrics(
                comparisons_count=0,
                unique_pairs=0,
                reliability_weighted=0.0,
                rank_stability=1.0,
                volatility_mean=0.0,
                average_ci_width=0.0,
            ),
        )

    def _rank_state(
        self,
        ideas: dict[str, IdeaCandidate],
        comparisons: list[PairwiseComparisonRecord],
    ) -> dict[str, dict[str, Any]]:
        state: dict[str, dict[str, Any]] = {}
        max_matches = 1
        for idea in ideas.values():
            merit = self._idea_merit(idea)
            state[idea.idea_id] = {
                "idea_id": idea.idea_id,
                "rating": 1200.0 + (600.0 * merit),
                "merit": merit,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "matches": 0,
                "deltas": [],
                "last_compared_at": None,
            }

        for comparison in comparisons:
            if comparison.left_idea_id not in state or comparison.right_idea_id not in state:
                continue
            left = state[comparison.left_idea_id]
            right = state[comparison.right_idea_id]
            expected_left = _logistic_rating_gap(left["rating"], right["rating"])
            if comparison.verdict == "left":
                actual_left = 1.0
                left["wins"] += 1
                right["losses"] += 1
            elif comparison.verdict == "right":
                actual_left = 0.0
                right["wins"] += 1
                left["losses"] += 1
            else:
                actual_left = 0.5
                left["ties"] += 1
                right["ties"] += 1

            k_factor = 28.0 * comparison.comparison_weight
            delta = k_factor * (actual_left - expected_left)
            left["rating"] += delta
            right["rating"] -= delta
            left["deltas"].append(delta)
            right["deltas"].append(-delta)
            left["matches"] += 1
            right["matches"] += 1
            left["last_compared_at"] = comparison.created_at
            right["last_compared_at"] = comparison.created_at
            max_matches = max(max_matches, left["matches"], right["matches"])

        for item in state.values():
            volatility = float(pstdev(item["deltas"])) if len(item["deltas"]) > 1 else abs(float(item["deltas"][0])) if item["deltas"] else 0.0
            coverage = min(1.0, math.log1p(item["matches"]) / math.log1p(max_matches + 1.0))
            stability = _clamp((coverage * 0.55) + (0.45 / (1.0 + (volatility / 75.0))), 0.0, 1.0)
            bt_component = math.log((item["wins"] + (0.5 * item["ties"]) + 1.0) / (item["losses"] + (0.5 * item["ties"]) + 1.0))
            item["rating"] = float(item["rating"] + (bt_component * 40.0))
            item["volatility"] = volatility
            item["stability"] = stability
            item["win_rate"] = (item["wins"] + (0.5 * item["ties"])) / item["matches"] if item["matches"] else 0.5
        return state

    def _build_previous_order(
        self,
        ideas: dict[str, IdeaCandidate],
        comparisons: list[PairwiseComparisonRecord],
    ) -> dict[str, int]:
        if len(comparisons) < 2:
            return {idea_id: index for index, idea_id in enumerate(ideas, start=1)}
        lag = max(1, min(5, len(comparisons) // 3))
        previous_state = self._rank_state(ideas, comparisons[:-lag])
        ordered = sorted(previous_state.values(), key=lambda item: item["rating"], reverse=True)
        return {item["idea_id"]: index for index, item in enumerate(ordered, start=1)}

    def _idea_merit(self, idea: IdeaCandidate) -> float:
        swipe_bonus = {
            "unseen": 0.0,
            "maybe": 0.05,
            "yes": 0.1,
            "now": 0.15,
            "pass": -0.1,
        }.get(idea.swipe_state, 0.0)
        source_bonus = 0.05 if idea.source in {"github", "research", "repo_graph", "repo_dna"} else 0.0
        return _clamp((idea.rank_score * 0.52) + (idea.belief_score * 0.38) + swipe_bonus + source_bonus, 0.0, 1.0)

    def _judge_profiles(
        self,
        ideas: dict[str, IdeaCandidate],
        comparisons: list[PairwiseComparisonRecord],
    ) -> list[RankingJudgeBelievability]:
        if not comparisons:
            return []
        leaderboard = self._build_leaderboard(ideas, comparisons, limit=500)
        order = {item.idea.idea_id: item.rank_position for item in leaderboard.items}
        grouped: dict[str, list[float]] = defaultdict(list)
        fields: dict[str, PairwiseComparisonRecord] = {}
        for comparison in comparisons:
            agreement = 0.5
            if comparison.verdict == "tie":
                distance = abs(
                    next((item.rating for item in leaderboard.items if item.idea.idea_id == comparison.left_idea_id), 0.0)
                    - next((item.rating for item in leaderboard.items if item.idea.idea_id == comparison.right_idea_id), 0.0)
                )
                agreement = 1.0 - min(1.0, distance / 140.0)
            elif comparison.winner_idea_id and comparison.loser_idea_id:
                agreement = 1.0 if order.get(comparison.winner_idea_id, 9999) <= order.get(comparison.loser_idea_id, 9999) else 0.0
            grouped[comparison.judge_key].append(agreement)
            fields.setdefault(comparison.judge_key, comparison)

        profiles: list[RankingJudgeBelievability] = []
        for judge_key, agreements in grouped.items():
            agreement_rate = fmean(agreements)
            comparisons_count = len(agreements)
            score = _clamp(0.4 + (agreement_rate * 0.45) + (min(1.0, comparisons_count / 8.0) * 0.15), 0.0, 1.0)
            reference = fields[judge_key]
            profiles.append(
                RankingJudgeBelievability(
                    judge_key=judge_key,
                    judge_source=reference.judge_source,
                    judge_model=reference.judge_model,
                    judge_agent_id=reference.judge_agent_id,
                    domain_key=reference.domain_key,
                    comparisons_count=comparisons_count,
                    agreement_rate=round(agreement_rate, 4),
                    believability_score=round(score, 4),
                )
            )
        profiles.sort(key=lambda item: (item.believability_score, item.comparisons_count), reverse=True)
        return profiles

    def _judge_believability_for_request(
        self,
        request: PairwiseComparisonRequest,
        profiles: list[RankingJudgeBelievability],
    ) -> float:
        identity = request.judge_agent_id or request.judge_model or "anonymous"
        domain = request.domain_key or "global"
        judge_key = f"{request.judge_source}:{identity}:{domain}"
        profile = next((item for item in profiles if item.judge_key == judge_key), None)
        if profile is not None:
            return float(profile.believability_score)
        return {
            "human": 0.86,
            "council": 0.78,
            "agent": 0.68,
            "system": 0.74,
        }.get(request.judge_source, 0.7)

    def _reliability_weighted(
        self,
        items: list[RankedIdeaRecord],
        comparisons: list[PairwiseComparisonRecord],
    ) -> float:
        if not items or not comparisons:
            return 0.0
        order = {item.idea.idea_id: item.rank_position for item in items}
        total_weight = 0.0
        matched_weight = 0.0
        for comparison in comparisons:
            total_weight += comparison.comparison_weight
            if comparison.verdict == "tie":
                gap = abs(
                    next((item.rating for item in items if item.idea.idea_id == comparison.left_idea_id), 0.0)
                    - next((item.rating for item in items if item.idea.idea_id == comparison.right_idea_id), 0.0)
                )
                matched_weight += comparison.comparison_weight * (1.0 - min(1.0, gap / 120.0))
            elif comparison.winner_idea_id and comparison.loser_idea_id:
                if order.get(comparison.winner_idea_id, 9999) <= order.get(comparison.loser_idea_id, 9999):
                    matched_weight += comparison.comparison_weight
        if total_weight <= 0:
            return 0.0
        return round(_clamp(matched_weight / total_weight, 0.0, 1.0), 4)

    def _aggregate_rankings(self, ballots: list[FinalVoteBallot]) -> list[dict[str, float | int | str]]:
        positions: dict[str, list[int]] = defaultdict(list)
        for ballot in ballots:
            for index, idea_id in enumerate(ballot.ranked_idea_ids, start=1):
                positions[idea_id].append(index)
        aggregate: list[dict[str, float | int | str]] = []
        for idea_id, values in positions.items():
            aggregate.append(
                {
                    "idea_id": idea_id,
                    "average_rank": round(sum(values) / len(values), 3),
                    "rankings_count": len(values),
                }
            )
        aggregate.sort(key=lambda item: float(item["average_rank"]))
        return aggregate

    def _checkpoint_digests(self, limit: int = 6) -> list[ArchiveCheckpointDigest]:
        return [
            ArchiveCheckpointDigest(
                checkpoint_id=snapshot.archive_id,
                generation=int(snapshot.generation),
                filled_cells=int(snapshot.filled_cells),
                coverage=float(snapshot.coverage),
                qd_score=float(snapshot.qd_score),
                created_at=snapshot.created_at,
            )
            for snapshot in self._index.list_archive_snapshots(limit=limit)
        ]

    def _should_checkpoint_snapshot(self, snapshot: IdeaArchiveSnapshot) -> bool:
        latest = self._index.latest_archive_snapshot()
        if latest is None:
            return True
        if latest.generation == snapshot.generation:
            return False
        return snapshot.generation % ARCHIVE_CHECKPOINT_INTERVAL == 0

    def _build_archive_snapshot(
        self,
        ideas: dict[str, IdeaCandidate],
        ranked_items: list[RankedIdeaRecord],
        comparisons: list[PairwiseComparisonRecord],
        *,
        limit_cells: int = 24,
    ) -> IdeaArchiveSnapshot:
        genomes = [build_idea_genome(item.idea, item) for item in ranked_items]
        for genome in genomes:
            genome.prompt_profile_id = infer_prompt_profile_id(genome)
        prompt_profiles = evolve_prompt_profiles(genomes, [item.model_dump() for item in comparisons])
        archive = MapElitesArchive()
        archive.bulk_insert(genomes)
        recommendations = build_recommendations(genomes, archive.cells(), limit=6)
        generation = len(comparisons)
        checkpointed = False
        checkpoint_digests = self._checkpoint_digests(limit=6)
        snapshot = archive.snapshot(
            generation=generation,
            prompt_profiles=prompt_profiles[:6],
            recommendations=recommendations,
            checkpoints=checkpoint_digests,
            checkpointed=False,
            limit_cells=limit_cells,
        )
        if self._should_checkpoint_snapshot(snapshot):
            self._index.save_archive_snapshot(snapshot)
            checkpointed = True
            checkpoint_digests = self._checkpoint_digests(limit=6)
            snapshot = archive.snapshot(
                generation=generation,
                prompt_profiles=prompt_profiles[:6],
                recommendations=recommendations,
                checkpoints=checkpoint_digests,
                checkpointed=checkpointed,
                limit_cells=limit_cells,
            )
        return snapshot

    def _sync_discovery_scores(
        self,
        items: list[RankedIdeaRecord],
        *,
        archive_snapshot: IdeaArchiveSnapshot | None = None,
    ) -> None:
        if not items:
            return
        min_rating = min(item.rating for item in items)
        max_rating = max(item.rating for item in items)
        span = max(max_rating - min_rating, 1.0)
        cell_lookup = {
            cell.elite.idea_id: cell
            for cell in list(archive_snapshot.cells if archive_snapshot is not None else [])
        }
        for item in items:
            idea = item.idea
            normalized_rating = _clamp((item.rating - min_rating) / span, 0.0, 1.0)
            scorecard = dict(idea.latest_scorecard or {})
            provenance = dict(idea.provenance or {})
            scorecard.update(
                {
                    "pairwise_rating": round(item.rating, 4),
                    "pairwise_stability": round(item.stability_score, 4),
                    "pairwise_volatility": round(item.volatility_score, 4),
                    "pairwise_matches": float(item.matches_played),
                    "pairwise_ci_low": round(item.confidence_low, 4),
                    "pairwise_ci_high": round(item.confidence_high, 4),
                }
            )
            archive_cell = cell_lookup.get(idea.idea_id)
            if archive_cell is not None and archive_snapshot is not None:
                scorecard.update(
                    {
                        "evolution_archive_fitness": round(archive_cell.elite.fitness, 4),
                        "evolution_archive_novelty": round(archive_cell.elite.novelty_score, 4),
                        "evolution_archive_generation": float(archive_snapshot.generation),
                        "evolution_archive_coverage": round(archive_snapshot.coverage, 4),
                        "evolution_archive_qd_score": round(archive_snapshot.qd_score, 4),
                    }
                )
                provenance["evolution_archive"] = {
                    "cell_key": archive_cell.key,
                    "prompt_profile_id": archive_cell.elite.prompt_profile_id or "",
                    "generation": int(archive_snapshot.generation),
                    "coverage": float(archive_snapshot.coverage),
                    "qd_score": float(archive_snapshot.qd_score),
                    "checkpointed": bool(archive_snapshot.checkpointed),
                    "axes": {
                        "domain": archive_cell.domain,
                        "complexity": archive_cell.complexity,
                        "distribution_strategy": archive_cell.distribution_strategy,
                        "buyer_type": archive_cell.buyer_type,
                    },
                }
            next_stage = idea.latest_stage
            if idea.latest_stage in {"sourced", "ranked"}:
                next_stage = "ranked"
            self._discovery.update_idea(
                idea.idea_id,
                IdeaUpdateRequest(
                    provenance=provenance,
                    rank_score=round(normalized_rating, 4),
                    belief_score=round(item.stability_score, 4),
                    latest_stage=next_stage,
                    latest_scorecard=scorecard,
                ),
            )


def get_ranking_service(db_path: str, discovery: DiscoveryStore) -> RankingService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _SERVICE_CACHE_LOCK:
        service = _SERVICE_CACHE.get(normalized)
        if service is None:
            service = RankingService(RankingIndex(normalized), discovery)
            _SERVICE_CACHE[normalized] = service
        return service


def clear_ranking_service_cache() -> None:
    with _SERVICE_CACHE_LOCK:
        _SERVICE_CACHE.clear()
