"""Tournament mode: bracket-style project debates with a judge."""

from __future__ import annotations

import asyncio
import operator
import re
import uuid
from pathlib import Path
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from orchestrator.debate.factcheck import ValidatedTurn, validate_with_retry
from orchestrator.debate.judges import aggregate_panel_decisions, parse_judge_response
from orchestrator.debate.moderators import (
    build_argument_prompt,
    build_improvement_prompt_context,
    build_judge_prompt,
)
from orchestrator.debate.protocols import build_protocol_telemetry, resolve_protocol_for_mode
from orchestrator.models import AgentConfig, store
from orchestrator.modes.base import (
    apply_user_instructions,
    build_workspace_context_prompt,
    call_agent_cfg,
    make_message,
    require_agent_response,
)
from orchestrator.ranking import order_tournament_pairings


ADVANCE_MATCH_MARKER = "ADVANCE_MATCH"
NEED_MORE_ROUNDS_MARKER = "NEED_MORE_ROUNDS"
ADVANCE_MATCH_RE = re.compile(r"^\s*`?ADVANCE_MATCH\s*:\s*([AB])\b`?\s*$", re.IGNORECASE | re.MULTILINE)
NEED_MORE_ROUNDS_RE = re.compile(r"^\s*`?NEED_MORE_ROUNDS`?\b\s*$", re.IGNORECASE | re.MULTILINE)
WINNER_RE = re.compile(r"^\s*winner\s*:\s*([AB])\b", re.IGNORECASE | re.MULTILINE)
CONTROL_LINE_RE = re.compile(r"^\s*`?(?:ADVANCE_MATCH\s*:\s*[AB]\b|NEED_MORE_ROUNDS)\s*`?\s*$", re.IGNORECASE)

ACTIVE_CHILD_STATUSES = {"running", "pause_requested", "paused", "cancel_requested"}
TERMINAL_CHILD_STATUSES = {"completed", "failed", "cancelled"}

OWNER_CONTEXT = (
    "OWNER CONTEXT:\n"
    "- One solo founder with a strong AI stack (Claude Code, Codex, Gemini, Quorum).\n"
    "- Can operate far above solo-founder baseline because of AI automation.\n"
    "- Can hire later if needed, but wants a path that works without a full team first.\n"
    "- Risk-tolerant, but not chasing huge venture outcomes for their own sake.\n"
    "- Goal: reach stable income around $2K+/month from products or automation.\n"
    "- Freelance work is out of scope.\n"
    "- Existing edge: VPS, infrastructure, Neo4j, ClickHouse, ML, and agent systems.\n"
)

PAIRWISE_CRITERIA = (
    "PAIRWISE DECISION CRITERIA:\n"
    "- Speed to first credible revenue\n"
    "- Reliability and repeatability of income\n"
    "- Realistic launch complexity for this owner\n"
    "- Upside beyond the first $2K+/month once it works\n"
    "- Whether the owner's AI stack creates a real unfair advantage\n"
)


class TournamentState(TypedDict):
    session_id: str
    mode: str
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    config: dict
    workspace_paths: list[str]
    attached_tool_ids: list[str]
    submissions: list[dict]
    bracket: list[list[dict]]
    current_round: int
    current_stage_label: str
    current_match_index: int
    current_match_round: int
    current_match: dict
    max_rounds: int
    winners: list[dict]
    champion: dict
    match_history: list[dict]
    match_verdict: str
    judge_action: str
    match_winner: str
    advance_target: str
    result: str
    parallel_stage_children: list[dict]
    parallel_stage_group_id: str
    protocol_name: str
    protocol_telemetry: dict
    fact_check_failures: dict
    disqualified_role: str


def _entry_label(entry: dict) -> str:
    paths = [str(path).strip() for path in list(entry.get("workspace_paths") or []) if str(path).strip()]
    if paths:
        primary = Path(paths[0]).name.strip()
        if primary:
            return primary
    return str(entry.get("project_label") or entry.get("role") or entry.get("agent_id") or "contestant")


def _match_protocol(state: TournamentState):
    return resolve_protocol_for_mode("tournament", state.get("config") or {})


def _entrant(agent: dict) -> dict:
    return {
        **agent,
        "project_label": _entry_label(agent),
    }


def _pair_entries(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    remaining = list(entries)
    matchups: list[dict] = []
    while len(remaining) >= 2:
        matchups.append({"a": remaining.pop(0), "b": remaining.pop(0)})
    return matchups, remaining


def _pairing_strategy(state: TournamentState) -> str:
    rendered = str((state.get("config") or {}).get("pairing_strategy", "sequential") or "sequential").strip().lower()
    return rendered if rendered in {"sequential", "adaptive"} else "sequential"


def _pairing_priors(state: TournamentState) -> dict[str, float]:
    raw = (state.get("config") or {}).get("pairing_priors")
    if not isinstance(raw, dict):
        return {}
    priors: dict[str, float] = {}
    for key, value in raw.items():
        try:
            priors[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return priors


def _pairing_archive_cells(state: TournamentState) -> dict[str, str]:
    raw = (state.get("config") or {}).get("pairing_archive_cells")
    if not isinstance(raw, dict):
        return {}
    cells: dict[str, str] = {}
    for key, value in raw.items():
        label = str(key).strip()
        cell = str(value).strip()
        if label and cell:
            cells[label] = cell
    return cells


def _execution_mode(state: TournamentState) -> str:
    rendered = str((state.get("config") or {}).get("execution_mode", "sequential") or "sequential").strip().lower()
    return rendered if rendered in {"sequential", "parallel"} else "sequential"


def _configured_parallelism_limit(state: TournamentState) -> int | None:
    raw_value = (state.get("config") or {}).get("parallelism_limit")
    if raw_value in {None, ""}:
        return None
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return None


def _provider_capacity(provider: str) -> int:
    normalized = str(provider or "").strip().lower()
    if not normalized:
        return 1
    try:
        from gateway import _provider_pool, discover_profiles

        discover_profiles()
        pool = _provider_pool(normalized)
        healthy_profiles = [
            profile
            for profile in pool.profiles
            if getattr(profile, "auth_state", "unknown") != "error"
        ]
        if healthy_profiles:
            return sum(max(int(getattr(profile, "max_parallel_leases", 1) or 1), 1) for profile in healthy_profiles)
        if pool.profiles:
            return 1
    except Exception:
        return 1
    return 1


def _auto_parallelism_limit(matchups: list[dict], judge: dict) -> int:
    capacities: dict[str, int] = {}
    usage: dict[str, int] = {}
    allowed = 0

    for match in matchups:
        providers = {
            str(match.get("a", {}).get("provider", "")).strip().lower(),
            str(match.get("b", {}).get("provider", "")).strip().lower(),
            str(judge.get("provider", "")).strip().lower(),
        }
        providers.discard("")
        if not providers:
            providers = {"default"}

        if any(usage.get(provider, 0) + 1 > capacities.setdefault(provider, _provider_capacity(provider)) for provider in providers):
            break

        for provider in providers:
            usage[provider] = usage.get(provider, 0) + 1
        allowed += 1

    return max(allowed, 1)


def _parallelism_limit_for_stage(state: TournamentState, matchups: list[dict], judge: dict) -> int:
    total = max(len(matchups), 1)
    configured = _configured_parallelism_limit(state)
    if configured is not None:
        return min(configured, total)
    return min(_auto_parallelism_limit(matchups, judge), total)


def _next_power_of_two_at_least(value: int) -> int:
    power = 1
    while power < value:
        power *= 2
    return power


def _stage_label_for_entries(entry_count: int, tournament_round: int) -> str:
    participants = _next_power_of_two_at_least(max(entry_count, 2))
    if participants <= 2:
        return "FINAL"
    if participants == 4:
        return "SF"
    if participants == 8:
        return "QF"
    return f"R{tournament_round}"


def _parallel_slot_key(stage_label: str, match_index: int) -> str:
    return f"{stage_label.lower()}-{match_index}"


def _parallel_match_label(stage_label: str, match_index: int, match: dict) -> str:
    return f"{stage_label} match {match_index}: {_entry_label(match['a'])} vs {_entry_label(match['b'])}"


def _dict_to_agent_cfg(agent: dict) -> AgentConfig:
    return AgentConfig(
        role=str(agent.get("role", "")).strip(),
        provider=str(agent.get("provider", "")).strip(),
        system_prompt=str(agent.get("system_prompt", "")).strip(),
        tools=list(agent.get("tools") or []),
        workspace_paths=list(agent.get("workspace_paths") or []),
    )


def _match_title(state: TournamentState) -> str:
    stage = str(state.get("current_stage_label") or "").strip()
    prefix = f"{stage} " if stage else ""
    return f"{prefix}round {state['current_round']}, match {state['current_match_index'] + 1}"


def _match_phase(state: TournamentState, suffix: str) -> str:
    return f"tournament_r{state['current_round']}_m{state['current_match_index'] + 1}_{suffix}"


def _match_history_text(state: TournamentState) -> str:
    current_match = dict(state.get("current_match") or {})
    rounds = list(current_match.get("rounds") or [])
    if not rounds:
        return ""

    chunks: list[str] = []
    for round_data in rounds:
        lines = [
            f"Round {round_data['round']}:",
            f"A ({_entry_label(current_match['a'])}): {round_data.get('a_arg', '')[:500]}",
            f"B ({_entry_label(current_match['b'])}): {round_data.get('b_arg', '')[:500]}",
        ]
        if round_data.get("judge_note"):
            lines.append(f"Judge note: {round_data['judge_note'][:400]}")
        chunks.append("\n".join(lines))
    return "\n\nPrevious rounds in this match:\n" + "\n\n".join(chunks)


def _contestant_prompt(state: TournamentState, agent: dict, opponent: dict, side: str, opponent_current_arg: str = "") -> str:
    match_round = state["current_match_round"] + 1
    history = _match_history_text(state)
    protocol = _match_protocol(state)
    return build_argument_prompt(
        protocol=protocol,
        workspace_context=build_workspace_context_prompt(agent),
        task=state["task"],
        participant_label=_entry_label(agent),
        opponent_label=_entry_label(opponent),
        role_kind=f"contestant {side}",
        round_number=match_round,
        max_rounds=state["max_rounds"],
        history_text=history,
        opponent_current_arg=opponent_current_arg,
        extra_context=(
            f"{build_improvement_prompt_context(state.get('config'), 'generator')}"
            f"{OWNER_CONTEXT}\n"
            f"{PAIRWISE_CRITERIA}\n"
            "You are in a head-to-head tournament match between two projects.\n"
            f"Match: {_match_title(state)}.\n"
            "Your job is to defeat the opposing project and advance, not to deliver a generic pitch.\n"
            "Round guidance:\n"
            "- Round 1: explain current project state, fastest credible path to money, why it beats this opponent, and your biggest admitted risk.\n"
            "- Round 2+: rebut the opponent point by point and include one honest concession if they are right about something.\n\n"
        ),
    )


def _judge_agent_for_match(judge: dict, match: dict) -> dict:
    merged_paths = list(
        dict.fromkeys(
            [
                *list(judge.get("workspace_paths") or []),
                *list(match.get("a", {}).get("workspace_paths") or []),
                *list(match.get("b", {}).get("workspace_paths") or []),
            ]
        )
    )
    return {
        **judge,
        "workspace_paths": merged_paths,
    }


def _judge_prompt(state: TournamentState, judge: dict, match: dict) -> str:
    protocol = _match_protocol(state)
    match_round = int(state["current_match_round"] or 0)
    final_round = match_round >= max(int(state["max_rounds"] or 1), 1)
    rounds_text = "\n\n".join(
        (
            f"=== Match round {round_data['round']} ===\n"
            f"CONTESTANT A ({_entry_label(match['a'])}): {round_data.get('a_arg', '')}\n\n"
            f"CONTESTANT B ({_entry_label(match['b'])}): {round_data.get('b_arg', '')}\n\n"
            f"JUDGE NOTE: {round_data.get('judge_note', '')}"
        )
        for round_data in list(match.get("rounds") or [])
    )
    return build_judge_prompt(
        protocol=protocol,
        workspace_context=build_workspace_context_prompt(judge),
        task=state["task"],
        transcript=(
            f"Match: {_match_title(state)}\n"
            f"CONTESTANT A: {_entry_label(match['a'])}\n"
            f"CONTESTANT B: {_entry_label(match['b'])}\n\n"
            f"{rounds_text}"
        ),
        current_round=match_round,
        max_rounds=state["max_rounds"],
        final_marker=ADVANCE_MATCH_MARKER,
        continue_marker=NEED_MORE_ROUNDS_MARKER,
        winner_tokens=("A", "B"),
        extra_context=(
            f"{build_improvement_prompt_context(state.get('config'), 'judge')}"
            f"{OWNER_CONTEXT}\n"
            f"{PAIRWISE_CRITERIA}\n"
            "You are the tournament judge for a head-to-head project debate.\n"
            "This is a pairwise elimination decision, not a scorecard exercise.\n"
            "Do not produce numeric tables unless explicitly asked.\n"
            "Prefer verified facts, realistic monetization, and execution fit over ambition theater.\n\n"
        ),
        final_round=final_round,
    )


def _validate_match_turn(
    state: TournamentState,
    agent: dict,
    prompt: str,
    response: str,
    context: str,
) -> tuple[str, ValidatedTurn, dict]:
    protocol = _match_protocol(state)
    if not protocol.supports_factcheck:
        report = ValidatedTurn(
            response=response,
            report={
                "ok": True,
                "issues": [],
                "evidence_density": 0.0,
            },
        )
        return response, report, {}

    validated = validate_with_retry(
        response=response,
        responder=lambda retry_note: require_agent_response(
            agent,
            call_agent_cfg(agent, apply_user_instructions(state, f"{prompt}\n\n{retry_note}")),
            context,
        ),
    )
    updates: dict = {}
    if validated.disqualified:
        failures = dict(state.get("fact_check_failures") or {})
        failures[str(agent.get("role", "agent"))] = failures.get(str(agent.get("role", "agent")), 0) + 1
        updates = {
            "fact_check_failures": failures,
            "disqualified_role": str(agent.get("role", "agent")),
        }
    return validated.response, validated, updates


def _clean_judge_response(text: str) -> str:
    cleaned_lines = [
        line for line in str(text or "").strip().splitlines()
        if not CONTROL_LINE_RE.match(line.strip())
    ]
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or str(text or "").strip()


def _extract_match_winner(text: str, default: str = "A") -> str:
    for pattern in (ADVANCE_MATCH_RE, WINNER_RE):
        match = pattern.search(text or "")
        if match:
            return match.group(1).upper()
    return default


def _extract_match_result_from_session(child_session: dict, match: dict) -> dict:
    match_result = ((child_session.get("config") or {}).get("match_result") or {})
    winner_token = str(match_result.get("winner_token") or _extract_match_winner(child_session.get("result", ""))).strip().upper()
    winner_token = "B" if winner_token == "B" else "A"
    winner = match["b"] if winner_token == "B" else match["a"]
    loser = match["a"] if winner_token == "B" else match["b"]
    verdict = str(match_result.get("verdict") or child_session.get("result") or "").strip()
    return {
        "winner_token": winner_token,
        "winner": winner,
        "loser": loser,
        "verdict": verdict,
    }


def seed_contestants(state: TournamentState) -> dict:
    contestants = [_entrant(agent) for agent in state["agents"][:-1]]
    names = ", ".join(_entry_label(agent) for agent in contestants)
    return {
        "submissions": contestants,
        "messages": [
            make_message(
                "system",
                f"Tournament entrants: {names}",
                "tournament_seed",
            )
        ],
    }


def start_round(state: TournamentState) -> dict:
    entrants = list(state["submissions"] if state["current_round"] == 0 else state["winners"])
    if _pairing_strategy(state) == "adaptive" and _pairing_priors(state):
        previous_pairs = {
            tuple(sorted((_entry_label(match["a"]), _entry_label(match["b"]))))
            for match in list(state.get("match_history") or [])
            if isinstance(match, dict) and match.get("a") and match.get("b")
        }
        matchups, byes = order_tournament_pairings(
            entrants,
            prior_scores=_pairing_priors(state),
            previous_pairs=previous_pairs,
            cell_signatures=_pairing_archive_cells(state),
        )
        if not matchups and len(entrants) >= 2:
            matchups, byes = _pair_entries(entrants)
    else:
        matchups, byes = _pair_entries(entrants)
    next_round_number = int(state["current_round"] or 0) + 1
    stage_label = _stage_label_for_entries(len(entrants), next_round_number)
    current_match = {
        **matchups[0],
        "rounds": [],
        "winner": "",
        "verdict": "",
    } if matchups else {}
    bye_labels = ", ".join(_entry_label(entry) for entry in byes)
    setup_line = f"{stage_label}: {len(matchups)} matches"
    if byes:
        setup_line += f", {len(byes)} bye(s): {bye_labels}"

    if not matchups and len(byes) <= 1:
        advance_target = "crown_champion"
    elif _execution_mode(state) == "parallel":
        advance_target = "run_parallel_stage"
    else:
        advance_target = "contestant_a_argues"

    return {
        "bracket": [*state["bracket"], matchups],
        "winners": list(byes),
        "current_round": next_round_number,
        "current_stage_label": stage_label,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": current_match,
        "parallel_stage_children": [],
        "parallel_stage_group_id": "",
        "advance_target": advance_target,
        "messages": [make_message("system", setup_line, f"tournament_round_{next_round_number}_setup")],
        "result": setup_line,
    }


def route_after_start_round(state: TournamentState) -> str:
    return state.get("advance_target") or "contestant_a_argues"


async def run_parallel_stage(state: TournamentState) -> dict:
    from orchestrator.engine import request_cancel, run

    session_id = str(state["session_id"]).strip()
    matchups = list(state["bracket"][-1] if state["bracket"] else [])
    stage_label = str(state.get("current_stage_label") or "").strip() or _stage_label_for_entries(len(matchups) * 2, int(state.get("current_round") or 1))
    group_id = f"pg_{uuid.uuid4().hex[:10]}"
    judge = state["agents"][-1]
    child_entries: list[dict] = []
    session_config = dict(state.get("config") or {})
    session_workspace_paths = list(state.get("workspace_paths") or [])
    attached_tool_ids = list(state.get("attached_tool_ids") or [])
    parallelism_limit = _parallelism_limit_for_stage(state, matchups, judge)

    pending_entries = []
    for match_index, match in enumerate(matchups, start=1):
        pending_entries.append(
            {
                "match_index": match_index,
                "slot_key": _parallel_slot_key(stage_label, match_index),
                "stage": stage_label,
                "label": _parallel_match_label(stage_label, match_index, match),
                "match": match,
            }
        )

    total = len(pending_entries)
    messages = [
        make_message(
            "system",
            f"{stage_label}: launching {total} parallel match(es) with batch limit {parallelism_limit}.",
            f"tournament_parallel_{str(stage_label).lower()}_started",
        )
    ]
    store.update(
        session_id,
        parallel_progress={
            "execution_mode": "parallel",
            "stage_label": stage_label,
            "total": total,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "group_id": group_id,
        },
    )

    cancel_cascaded = False
    child_sessions_by_id: dict[str, dict] = {}
    active_entries: list[dict] = []
    stage_failed = False
    while True:
        while not stage_failed and pending_entries and len(active_entries) < parallelism_limit:
            entry = pending_entries.pop(0)
            match = entry["match"]
            child_agents = [
                _dict_to_agent_cfg(match["a"]),
                _dict_to_agent_cfg(match["b"]),
                _dict_to_agent_cfg(judge),
            ]
            child_config = {
                **session_config,
                "execution_mode": "sequential",
                "tournament_round": int(state["current_round"] or 0),
                "match_index": int(entry["match_index"]),
                "parallel_stage": stage_label,
                "parallel_slot_key": entry["slot_key"],
                "parallel_label": entry["label"],
            }
            child_id = await run(
                mode="tournament_match",
                task=state["task"],
                agents=child_agents,
                config=child_config,
                workspace_paths=session_workspace_paths,
                attached_tool_ids=attached_tool_ids,
                parallel_parent_id=session_id,
                parallel_group_id=group_id,
                parallel_slot_key=entry["slot_key"],
                parallel_stage=stage_label,
                parallel_label=entry["label"],
            )
            launched_entry = {**entry, "id": child_id}
            child_entries.append(launched_entry)
            active_entries.append(launched_entry)

        active_sessions = [store.get(item["id"]) or {"id": item["id"], "status": "running"} for item in active_entries]
        for child in active_sessions:
            if child.get("status") in TERMINAL_CHILD_STATUSES:
                child_sessions_by_id[str(child.get("id"))] = child

        active_entries = [
            item
            for item in active_entries
            if (child_sessions_by_id.get(item["id"]) or {}).get("status") not in TERMINAL_CHILD_STATUSES
        ]

        completed = sum(1 for child in child_sessions_by_id.values() if child.get("status") == "completed")
        failed = sum(1 for child in child_sessions_by_id.values() if child.get("status") in {"failed", "cancelled"})
        running = len(active_entries)
        store.update(
            session_id,
            parallel_progress={
                "execution_mode": "parallel",
                "stage_label": stage_label,
                "total": total,
                "running": running,
                "completed": completed,
                "failed": failed,
                "group_id": group_id,
            },
        )

        parent_session = store.get(session_id) or {}
        if parent_session.get("status") == "cancel_requested" and not cancel_cascaded:
            for child in active_sessions:
                if child.get("status") in ACTIVE_CHILD_STATUSES and child.get("id"):
                    request_cancel(str(child["id"]))
            cancel_cascaded = True

        if failed and not cancel_cascaded:
            for child in active_sessions:
                if child.get("status") in ACTIVE_CHILD_STATUSES and child.get("id"):
                    request_cancel(str(child["id"]))
            cancel_cascaded = True
            stage_failed = True

        if running == 0 and (not pending_entries or stage_failed):
            break
        await asyncio.sleep(1.0)

    child_sessions = [child_sessions_by_id.get(item["id"]) or store.get(item["id"]) or {} for item in child_entries]
    failed_children = [
        child
        for child in child_sessions
        if child.get("status") in {"failed", "cancelled"}
    ]
    if failed_children:
        labels = ", ".join(str(child.get("parallel_label") or child.get("id") or "child").strip() for child in failed_children)
        detail = " | ".join(
            f"{child.get('parallel_label') or child.get('id')}: {str(child.get('result') or child.get('status')).strip()[:180]}"
            for child in failed_children
        )
        raise RuntimeError(f"Parallel tournament stage {stage_label} failed in {labels}. {detail}")

    next_winners = list(state["winners"])
    match_history = list(state["match_history"])
    last_result = ""

    for index, child in enumerate(child_sessions, start=1):
        match = child_entries[index - 1]["match"]
        resolved = _extract_match_result_from_session(child, match)
        winner = resolved["winner"]
        loser = resolved["loser"]
        verdict = resolved["verdict"]
        next_winners.append(winner)
        match_history.append(
            {
                "tournament_round": int(state["current_round"] or 0),
                "match_index": index,
                "winner": winner,
                "loser": loser,
                "verdict": verdict,
                "rounds": [],
                "child_session_id": child.get("id"),
            }
        )
        summary = f"Round {state['current_round']}, match {index}: {_entry_label(winner)} advances over {_entry_label(loser)}."
        messages.append(make_message("system", summary, _match_phase(state, f"match_{index}_complete")))
        last_result = verdict or summary

    store.update(
        session_id,
        parallel_progress={
            "execution_mode": "parallel",
            "stage_label": stage_label,
            "total": total,
            "running": 0,
            "completed": total,
            "failed": 0,
            "group_id": group_id,
        },
    )

    return {
        "winners": next_winners,
        "match_history": match_history,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "parallel_stage_children": child_entries,
        "parallel_stage_group_id": group_id,
        "advance_target": "crown_champion" if len(next_winners) <= 1 else "start_round",
        "messages": messages,
        "result": last_result or state.get("result", ""),
    }


def contestant_a_argues(state: TournamentState) -> dict:
    if state.get("disqualified_role"):
        return {"messages": []}

    match = dict(state["current_match"])
    contestant = match["a"]
    opponent = match["b"]
    match_round = int(state["current_match_round"] or 0) + 1
    protocol = _match_protocol(state)
    prompt = _contestant_prompt(state, contestant, opponent, "A")
    raw_response = require_agent_response(
        contestant,
        call_agent_cfg(contestant, apply_user_instructions(state, prompt)),
        "Tournament contestant A step failed",
    )
    response, factcheck, extra_updates = _validate_match_turn(state, contestant, prompt, raw_response, "Tournament contestant A retry failed")
    rounds = list(match.get("rounds") or [])
    rounds.append({"round": match_round, "a_arg": response, "b_arg": "", "judge_note": "", "a_factcheck": factcheck.report.model_dump(), "b_factcheck": {}})
    return {
        "protocol_name": protocol.name,
        "current_match": {**match, "rounds": rounds},
        "messages": [make_message(contestant["role"], response, _match_phase(state, f"round_{match_round}_a"), protocol_name=protocol.name, factcheck=factcheck.report.model_dump())],
        **extra_updates,
    }


def contestant_b_argues(state: TournamentState) -> dict:
    if state.get("disqualified_role") == state["current_match"]["a"]["role"]:
        return {"current_match_round": int((state["current_match"].get("rounds") or [{}])[-1].get("round") or 0), "messages": []}

    match = dict(state["current_match"])
    contestant = match["b"]
    opponent = match["a"]
    rounds = list(match.get("rounds") or [])
    current_round = dict(rounds[-1])
    protocol = _match_protocol(state)
    prompt = _contestant_prompt(state, contestant, opponent, "B", opponent_current_arg=current_round.get("a_arg", ""))
    raw_response = require_agent_response(
        contestant,
        call_agent_cfg(contestant, apply_user_instructions(state, prompt)),
        "Tournament contestant B step failed",
    )
    response, factcheck, extra_updates = _validate_match_turn(state, contestant, prompt, raw_response, "Tournament contestant B retry failed")
    current_round["b_arg"] = response
    current_round["b_factcheck"] = factcheck.report.model_dump()
    rounds[-1] = current_round
    match_round = int(current_round.get("round") or 0)
    return {
        "protocol_name": protocol.name,
        "current_match": {**match, "rounds": rounds},
        "current_match_round": match_round,
        "messages": [make_message(contestant["role"], response, _match_phase(state, f"round_{match_round}_b"), protocol_name=protocol.name, factcheck=factcheck.report.model_dump())],
        **extra_updates,
    }


def judge_match(state: TournamentState) -> dict:
    protocol = _match_protocol(state)
    judge = state["agents"][-1]
    match = dict(state["current_match"])
    judge_agent = _judge_agent_for_match(judge, match)
    final_round = int(state["current_match_round"] or 0) >= max(int(state["max_rounds"] or 1), 1)
    disqualified_role = str(state.get("disqualified_role") or "").strip()
    if disqualified_role:
        winner_token = "B" if disqualified_role == match["a"]["role"] else "A"
        response = (
            f"{ADVANCE_MATCH_MARKER}: {winner_token}\n"
            f"Disqualified role: {disqualified_role}.\n"
            "Unsupported claims or meta/tool-seeking behavior persisted after retry.\n"
            "Confidence: 0.90"
        )
        decisions = [
            parse_judge_response(
                response,
                protocol_name=protocol.name,
                final_marker=ADVANCE_MATCH_MARKER,
                continue_marker=NEED_MORE_ROUNDS_MARKER,
                allowed_winners=("A", "B"),
            )
        ]
    else:
        response = require_agent_response(
            judge_agent,
            call_agent_cfg(judge_agent, apply_user_instructions(state, _judge_prompt(state, judge_agent, match))),
            "Tournament judge step failed",
        )
        decisions = [
            parse_judge_response(
                response,
                protocol_name=protocol.name,
                final_marker=ADVANCE_MATCH_MARKER,
                continue_marker=NEED_MORE_ROUNDS_MARKER,
                allowed_winners=("A", "B"),
            )
        ]

    panel = aggregate_panel_decisions(decisions)
    if final_round and panel.action == "continue":
        panel.action = "final"
    cleaned_response = _clean_judge_response(panel.rationale or response)
    evidence_lines = [item.summary for item in decisions[0].evidence_items[:3]]
    unsupported_lines = decisions[0].unsupported_claims[:3]
    if evidence_lines:
        cleaned_response += "\n\nEvidence used:\n" + "\n".join(f"- {line}" for line in evidence_lines)
    if unsupported_lines:
        cleaned_response += "\n\nUnsupported claims:\n" + "\n".join(f"- {line}" for line in unsupported_lines)
    cleaned_response += f"\n\nConfidence: {panel.confidence:.2f}"
    rounds = list(match.get("rounds") or [])
    if rounds:
        latest_round = dict(rounds[-1])
        latest_round["judge_note"] = cleaned_response
        rounds[-1] = latest_round
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[item.get("a_arg", "") for item in rounds] + [item.get("b_arg", "") for item in rounds],
        confidence=panel.confidence,
        stances=[decision.winner_token or decision.action for decision in decisions],
    )
    if panel.action in {"final", "disqualify"}:
        judge_action = "advance"
    else:
        judge_action = "continue"
    return {
        "protocol_name": protocol.name,
        "protocol_telemetry": telemetry.model_dump(),
        "current_match": {
            **match,
            "rounds": rounds,
            "verdict": cleaned_response,
        },
        "judge_action": judge_action,
        "match_winner": panel.winner_token or _extract_match_winner(response),
        "match_verdict": cleaned_response,
        "result": cleaned_response,
        "messages": [make_message(judge["role"], cleaned_response, _match_phase(state, f"round_{state['current_match_round']}_verdict"), protocol_name=protocol.name, telemetry=telemetry.model_dump(), judge_schema=panel.model_dump())],
    }


def route_after_judge(state: TournamentState) -> str:
    if state.get("judge_action") == "continue" and state["current_match_round"] < state["max_rounds"]:
        return "contestant_a_argues"
    return "advance_match"


def advance_match(state: TournamentState) -> dict:
    match = dict(state["current_match"])
    round_number = int(state["current_round"] or 0)
    match_number = int(state["current_match_index"] or 0) + 1
    winner_token = "A" if str(state.get("match_winner") or "").strip().upper() != "B" else "B"
    winner = match["a"] if winner_token == "A" else match["b"]
    loser = match["b"] if winner_token == "A" else match["a"]
    next_winners = [*state["winners"], winner]
    match_history = [
        *state["match_history"],
        {
            "tournament_round": round_number,
            "match_index": match_number,
            "winner": winner,
            "loser": loser,
            "verdict": state.get("match_verdict", ""),
            "rounds": list(match.get("rounds") or []),
        },
    ]
    summary = f"Round {round_number}, match {match_number}: {_entry_label(winner)} advances over {_entry_label(loser)}."
    current_round_matches = list(state["bracket"][-1]) if state["bracket"] else []

    if match_number < len(current_round_matches):
        next_match = {
            **current_round_matches[match_number],
            "rounds": [],
            "winner": "",
            "verdict": "",
        }
        return {
            "winners": next_winners,
            "match_history": match_history,
            "current_match_index": match_number,
            "current_match_round": 0,
            "current_match": next_match,
            "advance_target": "contestant_a_argues",
            "messages": [make_message("system", summary, _match_phase(state, f"match_{match_number}_complete"))],
            "result": state.get("match_verdict") or summary,
        }

    if len(next_winners) <= 1:
        return {
            "winners": next_winners,
            "match_history": match_history,
            "current_match_index": 0,
            "current_match_round": 0,
            "current_match": {},
            "advance_target": "crown_champion",
            "messages": [make_message("system", summary, _match_phase(state, "round_complete"))],
            "result": state.get("match_verdict") or summary,
        }

    return {
        "winners": next_winners,
        "match_history": match_history,
        "current_match_index": 0,
        "current_match_round": 0,
        "current_match": {},
        "advance_target": "start_round",
        "messages": [make_message("system", summary, _match_phase(state, "round_complete"))],
        "result": state.get("match_verdict") or summary,
    }


def route_after_advance(state: TournamentState) -> str:
    return state.get("advance_target") or "crown_champion"


def crown_champion(state: TournamentState) -> dict:
    if state["winners"]:
        champion = state["winners"][0]
    elif state["submissions"]:
        champion = state["submissions"][0]
    else:
        champion = {"role": "none", "project_label": "none"}

    lines = [
        f"Champion: {_entry_label(champion)} ({champion.get('role') or champion.get('agent_id') or 'contestant'})",
    ]
    if state["match_history"]:
        final_match = state["match_history"][-1]
        if final_match.get("verdict"):
            lines.extend(["", "Final match verdict:", str(final_match["verdict"]).strip()])

        lines.extend(["", "Bracket summary:"])
        for match in state["match_history"]:
            lines.append(
                f"- Round {match['tournament_round']} match {match['match_index']}: "
                f"{_entry_label(match['winner'])} defeated {_entry_label(match['loser'])}"
            )

    result = "\n".join(lines).strip()
    return {
        "champion": champion,
        "result": result,
        "messages": [make_message("system", f"Champion: {_entry_label(champion)}", "champion")],
    }


def init_match(state: TournamentState) -> dict:
    contestant_a = _entrant(state["agents"][0])
    contestant_b = _entrant(state["agents"][1])
    summary = f"{state.get('current_stage_label') or 'MATCH'} match {state['current_match_index'] + 1}: {_entry_label(contestant_a)} vs {_entry_label(contestant_b)}"
    return {
        "current_match": {
            "a": contestant_a,
            "b": contestant_b,
            "rounds": [],
            "winner": "",
            "verdict": "",
        },
        "messages": [make_message("system", summary, _match_phase(state, "setup"))],
        "result": summary,
    }


def finalize_match(state: TournamentState) -> dict:
    match = dict(state["current_match"])
    winner_token = "A" if str(state.get("match_winner") or "").strip().upper() != "B" else "B"
    winner = match["a"] if winner_token == "A" else match["b"]
    loser = match["b"] if winner_token == "A" else match["a"]
    verdict = str(state.get("match_verdict") or match.get("verdict") or "").strip()
    summary = f"{_entry_label(winner)} advances over {_entry_label(loser)}."
    match_result = {
        "winner_token": winner_token,
        "winner_role": winner.get("role"),
        "winner_label": _entry_label(winner),
        "loser_role": loser.get("role"),
        "loser_label": _entry_label(loser),
        "verdict": verdict,
        "stage": state.get("current_stage_label"),
        "match_index": int(state.get("current_match_index", 0) or 0) + 1,
        "tournament_round": int(state.get("current_round", 0) or 0),
    }
    next_config = {
        **dict(state.get("config") or {}),
        "match_result": match_result,
    }
    result = "\n".join(part for part in [summary, "", verdict] if part).strip()
    return {
        "champion": winner,
        "current_match": {**match, "winner": winner_token, "verdict": verdict},
        "config": next_config,
        "result": result,
        "messages": [make_message("system", summary, _match_phase(state, "match_complete"))],
    }


def build_tournament_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(TournamentState)
    builder.add_node("seed_contestants", seed_contestants)
    builder.add_node("start_round", start_round)
    builder.add_node("run_parallel_stage", run_parallel_stage)
    builder.add_node("contestant_a_argues", contestant_a_argues)
    builder.add_node("contestant_b_argues", contestant_b_argues)
    builder.add_node("judge_match", judge_match)
    builder.add_node("advance_match", advance_match)
    builder.add_node("crown_champion", crown_champion)
    builder.add_edge(START, "seed_contestants")
    builder.add_edge("seed_contestants", "start_round")
    builder.add_conditional_edges(
        "start_round",
        route_after_start_round,
        {
            "run_parallel_stage": "run_parallel_stage",
            "contestant_a_argues": "contestant_a_argues",
            "crown_champion": "crown_champion",
        },
    )
    builder.add_conditional_edges(
        "run_parallel_stage",
        route_after_advance,
        {
            "start_round": "start_round",
            "crown_champion": "crown_champion",
        },
    )
    builder.add_edge("contestant_a_argues", "contestant_b_argues")
    builder.add_edge("contestant_b_argues", "judge_match")
    builder.add_conditional_edges(
        "judge_match",
        route_after_judge,
        {
            "contestant_a_argues": "contestant_a_argues",
            "advance_match": "advance_match",
        },
    )
    builder.add_conditional_edges(
        "advance_match",
        route_after_advance,
        {
            "contestant_a_argues": "contestant_a_argues",
            "start_round": "start_round",
            "crown_champion": "crown_champion",
        },
    )
    builder.add_edge("crown_champion", END)
    return builder.compile(**compile_kwargs)


def build_tournament_match_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(TournamentState)
    builder.add_node("init_match", init_match)
    builder.add_node("contestant_a_argues", contestant_a_argues)
    builder.add_node("contestant_b_argues", contestant_b_argues)
    builder.add_node("judge_match", judge_match)
    builder.add_node("finalize_match", finalize_match)
    builder.add_edge(START, "init_match")
    builder.add_edge("init_match", "contestant_a_argues")
    builder.add_edge("contestant_a_argues", "contestant_b_argues")
    builder.add_edge("contestant_b_argues", "judge_match")
    builder.add_conditional_edges(
        "judge_match",
        route_after_judge,
        {
            "contestant_a_argues": "contestant_a_argues",
            "advance_match": "finalize_match",
        },
    )
    builder.add_edge("finalize_match", END)
    return builder.compile(**compile_kwargs)
