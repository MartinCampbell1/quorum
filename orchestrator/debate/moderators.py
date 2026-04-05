"""Shared prompt and scrutiny helpers for debate-family protocols."""

from __future__ import annotations

import re
from statistics import fmean
from typing import Mapping

from pydantic import BaseModel, Field

from orchestrator.debate.judge_pack import build_founder_judge_pack_instructions
from orchestrator.debate.protocols import DebateProtocolSpec, ProtocolTelemetry, build_protocol_telemetry


_EVIDENCE_RE = re.compile(
    r"(https?://|github|readme|issue|commit|docs?/|evidence|data|study|benchmark|source|observed|measured)",
    re.IGNORECASE,
)


class ConsensusScrutinyResult(BaseModel):
    passed: bool
    reason: str
    telemetry: ProtocolTelemetry


def build_improvement_prompt_context(config: Mapping[str, object] | None, kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized not in {"generator", "judge", "critic"}:
        return ""
    payload = dict(config or {})
    overrides = dict(payload.get("prompt_profile_overrides") or {})
    note = str(overrides.get(f"{normalized}_prefix") or "").strip()
    if not note:
        return ""
    label = str(payload.get("prompt_profile_label") or payload.get("prompt_profile_id") or "active_profile").strip()
    return f"IMPROVEMENT PROFILE ({label} / {normalized}):\n{note}\n\n"


def build_argument_prompt(
    *,
    protocol: DebateProtocolSpec,
    workspace_context: str,
    task: str,
    participant_label: str,
    opponent_label: str,
    role_kind: str,
    round_number: int,
    max_rounds: int,
    history_text: str = "",
    opponent_current_arg: str = "",
    extra_context: str = "",
) -> str:
    opponent_section = ""
    if opponent_current_arg.strip():
        opponent_section = f"\n\nOpponent's latest argument:\n{opponent_current_arg}\n"

    style_section = (
        "Structure your answer as: Thesis -> Evidence -> Rebuttal -> Risk."
        if protocol.prompt_style == "dag"
        else (
            "Treat this as a crossfire turn. Challenge one concrete opponent claim directly and answer the strongest likely objection to your own case."
            if protocol.prompt_style == "crossfire"
            else "Make the strongest concrete case for your side and directly rebut the other side."
        )
    )
    return (
        f"{workspace_context}"
        f"{extra_context}"
        f"PROTOCOL: {protocol.display_name} ({protocol.name}).\n"
        f"You are acting as the {role_kind} in a structured multi-agent protocol.\n"
        f"You represent: {participant_label}.\n"
        f"Your direct opponent is: {opponent_label}.\n"
        f"Round {round_number} of {max_rounds}.\n\n"
        f"TASK:\n{task}\n"
        f"{history_text}"
        f"{opponent_section}\n"
        "Requirements:\n"
        "- Stay concrete and grounded in available repo/task evidence.\n"
        "- Admit real risks instead of hiding them.\n"
        "- Do not ask for more permissions or more context.\n"
        "- Prefer direct comparison over generic self-praise.\n"
        f"- {style_section}"
    )


def build_judge_prompt(
    *,
    protocol: DebateProtocolSpec,
    workspace_context: str,
    task: str,
    transcript: str,
    current_round: int,
    max_rounds: int,
    final_marker: str,
    continue_marker: str,
    winner_tokens: tuple[str, str],
    extra_context: str = "",
    final_round: bool = False,
    disqualification_note: str = "",
) -> str:
    if final_round:
        control_instruction = (
            f"Your first line must be exactly `{final_marker}: {winner_tokens[0]}` or `{final_marker}: {winner_tokens[1]}`.\n"
            "Then provide:\n"
            "1. Verdict and why it wins\n"
            "2. Evidence actually used\n"
            "3. Unsupported or weak claims you discounted\n"
            "4. Confidence (0.0-1.0)"
        )
    else:
        control_instruction = (
            f"If the winner is already clear, your first line must be exactly `{final_marker}: {winner_tokens[0]}` or `{final_marker}: {winner_tokens[1]}`.\n"
            f"Otherwise your first line must be exactly `{continue_marker}`.\n"
            "After the first line, provide:\n"
            "1. Interim verdict\n"
            "2. Evidence used so far\n"
            "3. Unsupported or weak claims to watch\n"
            "4. One concrete challenge for each side\n"
            "5. Confidence (0.0-1.0)"
        )
    if disqualification_note.strip():
        control_instruction += f"\n\nDisqualification context:\n{disqualification_note.strip()}"
    scorecard_instruction = build_founder_judge_pack_instructions(append_json=True)

    return (
        f"{workspace_context}"
        f"{extra_context}"
        f"PROTOCOL: {protocol.display_name} ({protocol.name}).\n"
        "You are the evidence-aware judge.\n"
        "Do not hide unsupported claims behind generic consensus language.\n"
        "If both sides sound aligned, scrutinize them harder instead of softer.\n"
        f"Round {current_round} of {max_rounds}.\n\n"
        f"TASK:\n{task}\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"{control_instruction}\n\n"
        f"{scorecard_instruction}"
    )


def review_unanimous_consensus(
    protocol: DebateProtocolSpec,
    stances: list[dict],
    candidate_decision: str,
) -> ConsensusScrutinyResult:
    rendered = [
        f"{item.get('position', '')}\n{item.get('reasoning', '')}".strip()
        for item in stances
        if str(item.get("position", "")).strip()
    ]
    telemetry = build_protocol_telemetry(
        protocol.name,
        rendered,
        confidence=0.72 if rendered else 0.0,
        stances=[str(item.get("decision_key") or item.get("position") or "").strip() for item in stances],
    )

    evidence_score = telemetry.evidence_density
    novelty_score = telemetry.novelty
    reasoning_lengths = [len(str(item.get("reasoning", "")).strip()) for item in stances]
    avg_reasoning = fmean(reasoning_lengths) if reasoning_lengths else 0.0
    evidence_mentions = sum(len(_EVIDENCE_RE.findall(text)) for text in rendered)

    passed = bool(rendered) and (
        evidence_score >= 0.09
        or novelty_score >= 0.16
        or avg_reasoning >= 80
        or evidence_mentions >= 2
    )
    if passed:
        reason = (
            f"Unanimous consensus passed scrutiny for '{candidate_decision}'. "
            f"Evidence density={evidence_score:.2f}, novelty={novelty_score:.2f}."
        )
    else:
        reason = (
            "Unanimous consensus is too shallow to trust yet. "
            f"Evidence density={evidence_score:.2f}, novelty={novelty_score:.2f}; run another review round."
        )
    return ConsensusScrutinyResult(passed=passed, reason=reason, telemetry=telemetry)
