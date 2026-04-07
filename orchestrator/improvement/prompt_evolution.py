"""Persistent prompt-improvement lab backed by reflective eval and self-play."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from orchestrator.evolution.archive import PromptEvolutionProfile
from orchestrator.improvement.reflective_eval import (
    ImprovementArtifact,
    ImprovementRole,
    ReflectiveEvalReport,
    build_reflective_report,
)
from orchestrator.improvement.self_play import (
    PromptSelfPlayMatch,
    build_challenge_cards,
    play_profiles,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _timestamp(value: datetime) -> float:
    return value.replace(tzinfo=UTC).timestamp()


class ImprovementSessionReflectRequest(BaseModel):
    session_id: str | None = None
    task: str = ""
    source_kind: str = "manual"
    source_id: str | None = None
    role_focus: list[ImprovementRole] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    artifacts: list[ImprovementArtifact] = Field(default_factory=list)
    judge_scores: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImprovementSelfPlayRequest(BaseModel):
    left_profile_id: str | None = None
    right_profile_id: str | None = None
    reflection_ids: list[str] = Field(default_factory=list)
    task: str = ""
    role_focus: list[ImprovementRole] = Field(default_factory=list)
    challenge_count: int = Field(default=3, ge=1, le=12)
    activate_winner: bool = False


class ImprovementEvolutionRequest(BaseModel):
    seed_profile_id: str | None = None
    reflection_ids: list[str] = Field(default_factory=list)
    task: str = ""
    mutation_budget: int = Field(default=3, ge=1, le=6)
    challenge_count: int = Field(default=3, ge=1, le=12)
    activate_best: bool = True


class ImprovementEvolutionResult(BaseModel):
    seed_profile: PromptEvolutionProfile
    reflections: list[ReflectiveEvalReport] = Field(default_factory=list)
    generated_profiles: list[PromptEvolutionProfile] = Field(default_factory=list)
    matches: list[PromptSelfPlayMatch] = Field(default_factory=list)
    activated_profile_id: str | None = None


def _default_profiles() -> list[PromptEvolutionProfile]:
    return [
        PromptEvolutionProfile(
            profile_id="improv_founder_rigor",
            label="Founder rigor",
            operator_kind="baseline",
            instruction="Keep every prompt concrete, founder-calibrated, and scoped to a believable first product wedge.",
            metadata={
                "generator_prefix": (
                    "Name one buyer, one painful workflow, one distribution wedge, one MVP slice, and one explicit risk. "
                    "Reject generic AI platform language unless evidence justifies it."
                ),
                "judge_prefix": (
                    "Reward concrete buyer clarity, distribution realism, evidence quality, and honest scoping. "
                    "Penalize polished vagueness."
                ),
                "critic_prefix": (
                    "Attack genericity, fuzzy ICPs, missing evidence, and platform sprawl. "
                    "Surface one execution trap and one go-to-market trap."
                ),
                "tactics": ["buyer_clarity", "distribution_wedge", "scope_guard", "risk_admission"],
                "failure_tags_covered": ["genericity", "weak_distribution", "risk_blindness", "overbuild"],
            },
        ),
        PromptEvolutionProfile(
            profile_id="improv_evidence_hardliner",
            label="Evidence hardliner",
            operator_kind="mutate",
            instruction="Bias the system toward explicit evidence, observed signals, and discounted-claims accounting before confidence.",
            metadata={
                "generator_prefix": (
                    "Separate evidence used from evidence missing. "
                    "Do not imply validation you cannot point to."
                ),
                "judge_prefix": (
                    "Require an evidence-used section and a discounted-claims section before high scores are allowed."
                ),
                "critic_prefix": (
                    "Push on unsupported claims, fabricated confidence, and missing source links harder than stylistic issues."
                ),
                "tactics": ["evidence_pressure", "discounted_claims", "validation_gaps"],
                "failure_tags_covered": ["evidence_gaps", "judge_leniency"],
            },
        ),
        PromptEvolutionProfile(
            profile_id="improv_novelty_pressure",
            label="Novelty pressure",
            operator_kind="mutate",
            instruction="Preserve founder realism while forcing a more surprising, less banal wedge.",
            metadata={
                "generator_prefix": (
                    "Escape obvious AI wrapper framing. "
                    "Require one unfair or adjacent-domain angle that still sounds believable."
                ),
                "judge_prefix": (
                    "Penalize candidates that read like generic AI SaaS for X. "
                    "Reward specific and surprising edges."
                ),
                "critic_prefix": (
                    "Call out banality, derivative framing, and fake differentiation aggressively."
                ),
                "tactics": ["anti_banality", "adjacent_domain", "differentiation_pressure"],
                "failure_tags_covered": ["genericity", "novelty_collapse"],
            },
        ),
        PromptEvolutionProfile(
            profile_id="improv_scope_guard",
            label="Scope guard",
            operator_kind="mutate",
            instruction="Keep ambition subordinate to a fast first sprint and a credible first story.",
            metadata={
                "generator_prefix": (
                    "Describe the thinnest executable MVP, not the eventual platform. "
                    "Anchor plans in a first workflow and a first story."
                ),
                "judge_prefix": (
                    "Down-rank ecosystem fantasies that do not map to a believable first sprint or story decomposition."
                ),
                "critic_prefix": (
                    "Use 'how does this ship in one sprint?' as a default attack unless the scope is already narrow."
                ),
                "tactics": ["mvp_guard", "story_decomposition", "scope_constraint"],
                "failure_tags_covered": ["overbuild", "risk_blindness"],
            },
        ),
    ]


class PromptImprovementLab:
    def __init__(self, db_path: str):
        self._db_path = Path(db_path).expanduser().resolve()
        self._lock = threading.RLock()
        self._init_db()
        self._seed_defaults()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS improvement_profiles (
                    profile_id TEXT PRIMARY KEY,
                    active INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS improvement_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS improvement_selfplay_matches (
                    match_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def _encode(self, value: BaseModel) -> str:
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=True, sort_keys=True)

    def _decode_profile(self, row: sqlite3.Row) -> PromptEvolutionProfile:
        payload = json.loads(row["payload_json"])
        profile = PromptEvolutionProfile.model_validate(payload)
        profile.metadata = dict(profile.metadata or {})
        profile.metadata["active"] = bool(row["active"])
        return profile

    def _seed_defaults(self) -> None:
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT COUNT(*) AS count FROM improvement_profiles").fetchone()
            if existing and int(existing["count"] or 0) > 0:
                return
            now = _timestamp(_utcnow())
            defaults = _default_profiles()
            for index, profile in enumerate(defaults):
                conn.execute(
                    """
                    INSERT INTO improvement_profiles (profile_id, active, updated_at, payload_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        profile.profile_id,
                        1 if index == 0 else 0,
                        now,
                        self._encode(profile),
                    ),
                )

    def list_profiles(self, limit: int = 20) -> list[PromptEvolutionProfile]:
        bounded_limit = max(1, min(int(limit or 20), 200))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT profile_id, active, updated_at, payload_json
                FROM improvement_profiles
                ORDER BY active DESC, updated_at DESC, profile_id ASC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [self._decode_profile(row) for row in rows]

    def get_profile(self, profile_id: str) -> PromptEvolutionProfile | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT profile_id, active, updated_at, payload_json FROM improvement_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return self._decode_profile(row) if row else None

    def active_profile(self) -> PromptEvolutionProfile:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT profile_id, active, updated_at, payload_json
                FROM improvement_profiles
                ORDER BY active DESC, updated_at DESC, profile_id ASC
                """,
            ).fetchone()
        if row is None:
            self._seed_defaults()
            profile = self.get_profile("improv_founder_rigor")
            assert profile is not None
            return profile
        return self._decode_profile(row)

    def _save_profile(self, profile: PromptEvolutionProfile, *, active: bool | None = None) -> PromptEvolutionProfile:
        now = _utcnow()
        profile.last_updated = now
        is_active = bool(profile.metadata.get("active")) if active is None else active
        profile.metadata = dict(profile.metadata or {})
        profile.metadata["active"] = is_active
        with self._lock, self._connect() as conn:
            if is_active:
                conn.execute("UPDATE improvement_profiles SET active = 0")
            conn.execute(
                """
                INSERT OR REPLACE INTO improvement_profiles (profile_id, active, updated_at, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    profile.profile_id,
                    1 if is_active else 0,
                    _timestamp(now),
                    self._encode(profile),
                ),
            )
        return profile

    def _save_reflection(self, report: ReflectiveEvalReport) -> ReflectiveEvalReport:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO improvement_reflections (reflection_id, created_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    report.reflection_id,
                    _timestamp(report.created_at),
                    self._encode(report),
                ),
            )
        return report

    def _save_match(self, match: PromptSelfPlayMatch) -> PromptSelfPlayMatch:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO improvement_selfplay_matches (match_id, created_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    match.match_id,
                    _timestamp(match.created_at),
                    self._encode(match),
                ),
            )
        return match

    def list_reflections(self, limit: int = 20) -> list[ReflectiveEvalReport]:
        bounded_limit = max(1, min(int(limit or 20), 200))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM improvement_reflections
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [ReflectiveEvalReport.model_validate(json.loads(row["payload_json"])) for row in rows]

    def get_reflections(self, reflection_ids: Iterable[str]) -> list[ReflectiveEvalReport]:
        wanted = [item for item in reflection_ids if item]
        if not wanted:
            return self.list_reflections(limit=10)
        placeholders = ",".join("?" for _ in wanted)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload_json FROM improvement_reflections WHERE reflection_id IN ({placeholders})",
                tuple(wanted),
            ).fetchall()
        reflections = [ReflectiveEvalReport.model_validate(json.loads(row["payload_json"])) for row in rows]
        reflections.sort(key=lambda item: item.created_at, reverse=True)
        return reflections

    def list_matches(self, limit: int = 20) -> list[PromptSelfPlayMatch]:
        bounded_limit = max(1, min(int(limit or 20), 200))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM improvement_selfplay_matches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [PromptSelfPlayMatch.model_validate(json.loads(row["payload_json"])) for row in rows]

    def _session_payload_to_artifacts(self, session: dict[str, Any]) -> tuple[str, list[ImprovementArtifact], list[dict[str, Any]]]:
        task = str(session.get("task") or "")
        config = dict(session.get("config") or {})
        trace = dict(config.get("generation_trace") or {})
        artifacts: list[ImprovementArtifact] = []
        judge_scores = list(trace.get("judge_scores") or [])

        for item in list(trace.get("layer1_outputs") or []):
            if str(item.get("content") or "").strip():
                artifacts.append(ImprovementArtifact(role="generator", content=str(item["content"]), metadata=dict(item.get("metadata") or {})))
        for item in list(trace.get("layer2_outputs") or []):
            if str(item.get("content") or "").strip():
                artifacts.append(ImprovementArtifact(role="generator", content=str(item["content"]), metadata=dict(item.get("metadata") or {})))
        final_artifact = trace.get("final_artifact")
        if isinstance(final_artifact, dict) and str(final_artifact.get("content") or "").strip():
            artifacts.append(ImprovementArtifact(role="generator", content=str(final_artifact["content"]), metadata=dict(final_artifact.get("metadata") or {})))

        for message in list(session.get("messages") or []):
            role = str(message.get("agent_id") or message.get("role") or "").lower()
            content = str(message.get("content") or "")
            if not content.strip():
                continue
            mapped_role: ImprovementRole = "generator"
            if "judge" in role:
                mapped_role = "judge"
            elif "critic" in role or "opponent" in role:
                mapped_role = "critic"
            artifacts.append(ImprovementArtifact(role=mapped_role, content=content))
        return task, artifacts, judge_scores

    def reflect(
        self,
        request: ImprovementSessionReflectRequest,
        *,
        session_lookup: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> ReflectiveEvalReport:
        task = request.task
        artifacts = list(request.artifacts)
        judge_scores = list(request.judge_scores)
        source_id = request.source_id
        metadata = dict(request.metadata or {})
        if request.session_id:
            if session_lookup is None:
                raise KeyError(f"Unknown session id: {request.session_id}")
            session = session_lookup(request.session_id)
            if session is None:
                raise KeyError(f"Unknown session id: {request.session_id}")
            derived_task, derived_artifacts, derived_scores = self._session_payload_to_artifacts(session)
            task = task or derived_task
            artifacts.extend(derived_artifacts)
            judge_scores.extend(derived_scores)
            source_id = source_id or request.session_id
            metadata.setdefault("session_mode", session.get("mode"))
        report = build_reflective_report(
            task=task,
            source_kind=request.source_kind,
            source_id=source_id,
            artifacts=artifacts,
            judge_scores=judge_scores,
            failure_tags=request.failure_tags,
            notes=request.notes,
            role_focus=request.role_focus,
            metadata=metadata,
        )
        return self._save_reflection(report)

    def _mutate_profile(
        self,
        seed: PromptEvolutionProfile,
        reflection: ReflectiveEvalReport,
        *,
        mutation_index: int,
    ) -> PromptEvolutionProfile:
        metadata = dict(seed.metadata or {})
        generator_prefix = str(metadata.get("generator_prefix") or "")
        judge_prefix = str(metadata.get("judge_prefix") or "")
        critic_prefix = str(metadata.get("critic_prefix") or "")

        for signal in reflection.signals:
            patch = str(signal.suggested_patch or "").strip()
            if not patch:
                continue
            if "generator" in signal.target_roles and patch not in generator_prefix:
                generator_prefix = f"{generator_prefix} {patch}".strip()
            if "judge" in signal.target_roles and patch not in judge_prefix:
                judge_prefix = f"{judge_prefix} {patch}".strip()
            if "critic" in signal.target_roles and patch not in critic_prefix:
                critic_prefix = f"{critic_prefix} {patch}".strip()

        tactics = list(dict.fromkeys([*list(metadata.get("tactics") or []), *reflection.failure_tags, *reflection.role_focus]))
        covered = list(dict.fromkeys([*list(metadata.get("failure_tags_covered") or []), *reflection.failure_tags]))
        variant = PromptEvolutionProfile(
            profile_id=f"{seed.profile_id}_mut_{mutation_index}",
            label=f"{seed.label} v{mutation_index}",
            operator_kind="self_improve",
            instruction=" ".join(
                [
                    seed.instruction,
                    *reflection.recommendations[:2],
                ]
            ).strip(),
            elo_rating=seed.elo_rating,
            wins=seed.wins,
            losses=seed.losses,
            ties=seed.ties,
            usage_count=0,
            debate_influence=seed.debate_influence,
            metadata={
                **metadata,
                "generator_prefix": generator_prefix,
                "judge_prefix": judge_prefix,
                "critic_prefix": critic_prefix,
                "tactics": tactics[:10],
                "failure_tags_covered": covered[:10],
                "parent_profile_id": seed.profile_id,
                "active": False,
                "reflection_id": reflection.reflection_id,
            },
        )
        return variant

    def _update_match_ratings(
        self,
        left: PromptEvolutionProfile,
        right: PromptEvolutionProfile,
        match: PromptSelfPlayMatch,
    ) -> tuple[PromptEvolutionProfile, PromptEvolutionProfile]:
        if match.winner_profile_id is None:
            left.ties += 1
            right.ties += 1
            left.elo_rating += 4.0
            right.elo_rating += 4.0
            return left, right

        actual_left = 1.0 if match.winner_profile_id == left.profile_id else 0.0
        expected_left = 1.0 / (1.0 + 10.0 ** ((right.elo_rating - left.elo_rating) / 400.0))
        delta = 22.0 * (actual_left - expected_left)
        left.elo_rating += delta
        right.elo_rating -= delta
        if actual_left == 1.0:
            left.wins += 1
            right.losses += 1
        else:
            right.wins += 1
            left.losses += 1
        return left, right

    def run_self_play(self, request: ImprovementSelfPlayRequest) -> PromptSelfPlayMatch:
        left = self.get_profile(request.left_profile_id or self.active_profile().profile_id)
        if left is None:
            raise KeyError(f"Unknown improvement profile: {request.left_profile_id}")
        right = self.get_profile(request.right_profile_id or self.active_profile().profile_id)
        if right is None:
            raise KeyError(f"Unknown improvement profile: {request.right_profile_id}")
        reflections = self.get_reflections(request.reflection_ids)
        challenge_cards = build_challenge_cards(
            task=request.task,
            reflections=reflections,
            role_focus=request.role_focus,
            challenge_count=request.challenge_count,
        )
        match = play_profiles(left, right, challenge_cards=challenge_cards, role_focus=request.role_focus or ["generator", "judge", "critic"])
        left, right = self._update_match_ratings(left, right, match)
        self._save_profile(left, active=bool(left.metadata.get("active")))
        self._save_profile(right, active=bool(right.metadata.get("active")))
        if request.activate_winner and match.winner_profile_id:
            winner = left if match.winner_profile_id == left.profile_id else right
            self._save_profile(winner, active=True)
        return self._save_match(match)

    def evolve(self, request: ImprovementEvolutionRequest) -> ImprovementEvolutionResult:
        seed = self.get_profile(request.seed_profile_id or self.active_profile().profile_id)
        if seed is None:
            raise KeyError(f"Unknown improvement profile: {request.seed_profile_id}")
        reflections = self.get_reflections(request.reflection_ids)
        if not reflections:
            reflections = [
                ReflectiveEvalReport(
                    source_kind="bootstrap",
                    task=request.task or "Improve prompt quality",
                    role_focus=["generator", "judge", "critic"],
                    recommendations=["Sharpen buyer clarity, evidence pressure, and scope control."],
                    failure_tags=["genericity", "evidence_gaps", "overbuild"],
                )
            ]

        generated: list[PromptEvolutionProfile] = []
        matches: list[PromptSelfPlayMatch] = []
        for index in range(1, request.mutation_budget + 1):
            reflection = reflections[(index - 1) % len(reflections)]
            challenger = self._mutate_profile(seed, reflection, mutation_index=index)
            self._save_profile(challenger, active=False)
            generated.append(challenger)
            match = self.run_self_play(
                ImprovementSelfPlayRequest(
                    left_profile_id=challenger.profile_id,
                    right_profile_id=seed.profile_id,
                    reflection_ids=[reflection.reflection_id],
                    task=request.task,
                    role_focus=reflection.role_focus,
                    challenge_count=request.challenge_count,
                    activate_winner=False,
                )
            )
            matches.append(match)

        winner_id = seed.profile_id
        ranked = sorted(
            [seed, *generated],
            key=lambda profile: (profile.elo_rating, profile.wins - profile.losses, profile.usage_count),
            reverse=True,
        )
        if ranked:
            winner_id = ranked[0].profile_id
        if request.activate_best:
            winner = self.get_profile(winner_id)
            if winner is not None:
                self._save_profile(winner, active=True)

        return ImprovementEvolutionResult(
            seed_profile=self.get_profile(seed.profile_id) or seed,
            reflections=reflections,
            generated_profiles=[self.get_profile(item.profile_id) or item for item in generated],
            matches=matches,
            activated_profile_id=winner_id if request.activate_best else None,
        )

    def runtime_profile(self, mode: str) -> dict[str, Any]:
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {"moa", "debate", "tournament"}:
            return {}
        profile = self.active_profile()
        metadata = dict(profile.metadata or {})
        return {
            "prompt_profile_id": profile.profile_id,
            "prompt_profile_label": profile.label,
            "prompt_profile_overrides": {
                "generator_prefix": str(metadata.get("generator_prefix") or ""),
                "judge_prefix": str(metadata.get("judge_prefix") or ""),
                "critic_prefix": str(metadata.get("critic_prefix") or ""),
                "tactics": list(metadata.get("tactics") or []),
            },
        }


_IMPROVEMENT_CACHE: dict[str, PromptImprovementLab] = {}


def get_improvement_lab(db_path: str) -> PromptImprovementLab:
    key = str(Path(db_path).expanduser().resolve())
    service = _IMPROVEMENT_CACHE.get(key)
    if service is None:
        service = PromptImprovementLab(key)
        _IMPROVEMENT_CACHE[key] = service
    return service


def clear_improvement_lab_cache() -> None:
    _IMPROVEMENT_CACHE.clear()
