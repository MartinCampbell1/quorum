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

from orchestrator.models import AgentConfig, store
from orchestrator.modes.base import (
    apply_user_instructions,
    build_workspace_context_prompt,
    call_agent_cfg,
    make_message,
    require_agent_response,
)


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


def _entry_label(entry: dict) -> str:
    paths = [str(path).strip() for path in list(entry.get("workspace_paths") or []) if str(path).strip()]
    if paths:
        primary = Path(paths[0]).name.strip()
        if primary:
            return primary
    return str(entry.get("project_label") or entry.get("role") or entry.get("agent_id") or "contestant")


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


def _execution_mode(state: TournamentState) -> str:
    rendered = str((state.get("config") or {}).get("execution_mode", "sequential") or "sequential").strip().lower()
    return rendered if rendered in {"sequential", "parallel"} else "sequential"


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
    opponent_arg_section = ""
    if opponent_current_arg.strip():
        opponent_arg_section = (
            f"\n\nOpponent's argument this round ({_entry_label(opponent)}):\n"
            f"{opponent_current_arg}\n"
        )

    return (
        f"{build_workspace_context_prompt(agent)}"
        f"{OWNER_CONTEXT}\n"
        f"{PAIRWISE_CRITERIA}\n"
        "You are in a head-to-head tournament match between two projects.\n"
        f"You are contestant {side} and you represent exactly one project: {_entry_label(agent)}.\n"
        f"Your opponent in this match is: {_entry_label(opponent)}.\n"
        f"Match: {_match_title(state)}.\n"
        f"Debate round: {match_round} of {state['max_rounds']}.\n\n"
        f"TASK:\n{state['task']}\n"
        f"{history}"
        f"{opponent_arg_section}\n\n"
        "Your job is not to give a generic pitch. Your job is to defeat the opposing project and advance.\n"
        "Argue specifically why your project is the stronger answer to the task for this owner.\n"
        "Use evidence from your project roots, call out implementation leverage, defend against risks, and rebut the opponent's claims directly.\n"
        "Do not optimize for hype, storytelling, or presentation polish. Optimize for the strongest evidence-backed case.\n"
        "Prefer direct comparison over isolated self-praise.\n"
        "Be concrete and comparative.\n\n"
        "Round guidance:\n"
        "- Round 1: state what the project is, current state, fastest credible path to money, why it beats this opponent, and your biggest admitted risk.\n"
        "- Round 2+: rebut the opponent point by point, show where their case is weaker, and include one honest concession if they are right about something."
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
    decision_instruction = (
        f"This is the final allowed debate round ({match_round} of {state['max_rounds']}).\n"
        f"Your first line must be exactly `{ADVANCE_MATCH_MARKER}: A` or `{ADVANCE_MATCH_MARKER}: B`.\n"
        "Then provide:\n"
        "1. Which project wins and why\n"
        "2. The strongest argument from each side\n"
        "3. The decisive weakness that kept the loser from advancing"
        if final_round
        else (
            f"This is match round {match_round} of {state['max_rounds']}.\n"
            f"If one side has already clearly won, your first line must be exactly `{ADVANCE_MATCH_MARKER}: A` or `{ADVANCE_MATCH_MARKER}: B`.\n"
            f"Otherwise your first line must be exactly `{NEED_MORE_ROUNDS_MARKER}`.\n"
            "After the first line, give an interim assessment and one concrete challenge for each side to address next round."
        )
    )
    return (
        f"{build_workspace_context_prompt(judge)}"
        f"{OWNER_CONTEXT}\n"
        f"{PAIRWISE_CRITERIA}\n"
        "You are the tournament judge for a head-to-head project debate.\n"
        "This is a pairwise elimination decision, not a scorecard exercise.\n"
        "Do not produce numeric scores, weighted tables, or synthetic point systems unless the user explicitly asks for them.\n"
        "Your job is to decide which project made the stronger, more credible case for being prioritized first by this owner.\n"
        "Prefer verified facts, realistic monetization, and execution fit over ambitious narratives.\n"
        "Punish invented claims. Reward honesty and concrete evidence.\n"
        f"Match: {_match_title(state)}.\n"
        f"TASK:\n{state['task']}\n\n"
        f"CONTESTANT A: {_entry_label(match['a'])}\n"
        f"CONTESTANT B: {_entry_label(match['b'])}\n\n"
        f"MATCH TRANSCRIPT:\n{rounds_text}\n\n"
        f"{decision_instruction}"
    )


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

    for match_index, match in enumerate(matchups, start=1):
        slot_key = _parallel_slot_key(stage_label, match_index)
        label = _parallel_match_label(stage_label, match_index, match)
        child_agents = [
            _dict_to_agent_cfg(match["a"]),
            _dict_to_agent_cfg(match["b"]),
            _dict_to_agent_cfg(judge),
        ]
        child_config = {
            **session_config,
            "execution_mode": "sequential",
            "tournament_round": int(state["current_round"] or 0),
            "match_index": match_index,
            "parallel_stage": stage_label,
            "parallel_slot_key": slot_key,
            "parallel_label": label,
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
            parallel_slot_key=slot_key,
            parallel_stage=stage_label,
            parallel_label=label,
        )
        child_entries.append(
            {
                "id": child_id,
                "slot_key": slot_key,
                "stage": stage_label,
                "label": label,
                "match": match,
            }
        )

    total = len(child_entries)
    messages = [
        make_message(
            "system",
            f"{stage_label}: launched {total} parallel match(es).",
            f"tournament_parallel_{str(stage_label).lower()}_started",
        )
    ]
    store.update(
        session_id,
        parallel_progress={
            "execution_mode": "parallel",
            "stage_label": stage_label,
            "total": total,
            "running": total,
            "completed": 0,
            "failed": 0,
            "group_id": group_id,
        },
    )

    cancel_cascaded = False
    child_sessions: list[dict] = []
    while True:
        child_sessions = [store.get(item["id"]) or {} for item in child_entries]
        running = sum(1 for child in child_sessions if child.get("status") in ACTIVE_CHILD_STATUSES)
        completed = sum(1 for child in child_sessions if child.get("status") == "completed")
        failed = sum(1 for child in child_sessions if child.get("status") in {"failed", "cancelled"})
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
            for child in child_sessions:
                if child.get("status") in ACTIVE_CHILD_STATUSES and child.get("id"):
                    request_cancel(str(child["id"]))
            cancel_cascaded = True

        if running == 0 and all(child.get("status") in TERMINAL_CHILD_STATUSES for child in child_sessions):
            break
        await asyncio.sleep(1.0)

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
    match = dict(state["current_match"])
    contestant = match["a"]
    opponent = match["b"]
    match_round = int(state["current_match_round"] or 0) + 1
    response = require_agent_response(
        contestant,
        call_agent_cfg(contestant, apply_user_instructions(state, _contestant_prompt(state, contestant, opponent, "A"))),
        "Tournament contestant A step failed",
    )
    rounds = list(match.get("rounds") or [])
    rounds.append({"round": match_round, "a_arg": response, "b_arg": "", "judge_note": ""})
    return {
        "current_match": {**match, "rounds": rounds},
        "messages": [make_message(contestant["role"], response, _match_phase(state, f"round_{match_round}_a"))],
    }


def contestant_b_argues(state: TournamentState) -> dict:
    match = dict(state["current_match"])
    contestant = match["b"]
    opponent = match["a"]
    rounds = list(match.get("rounds") or [])
    current_round = dict(rounds[-1])
    response = require_agent_response(
        contestant,
        call_agent_cfg(
            contestant,
            apply_user_instructions(
                state,
                _contestant_prompt(state, contestant, opponent, "B", opponent_current_arg=current_round.get("a_arg", "")),
            ),
        ),
        "Tournament contestant B step failed",
    )
    current_round["b_arg"] = response
    rounds[-1] = current_round
    match_round = int(current_round.get("round") or 0)
    return {
        "current_match": {**match, "rounds": rounds},
        "current_match_round": match_round,
        "messages": [make_message(contestant["role"], response, _match_phase(state, f"round_{match_round}_b"))],
    }


def judge_match(state: TournamentState) -> dict:
    judge = state["agents"][-1]
    match = dict(state["current_match"])
    judge_agent = _judge_agent_for_match(judge, match)
    response = require_agent_response(
        judge_agent,
        call_agent_cfg(judge_agent, apply_user_instructions(state, _judge_prompt(state, judge_agent, match))),
        "Tournament judge step failed",
    )
    cleaned_response = _clean_judge_response(response)
    rounds = list(match.get("rounds") or [])
    if rounds:
        latest_round = dict(rounds[-1])
        latest_round["judge_note"] = cleaned_response
        rounds[-1] = latest_round
    final_round = int(state["current_match_round"] or 0) >= max(int(state["max_rounds"] or 1), 1)
    if final_round or ADVANCE_MATCH_RE.search(response):
        judge_action = "advance"
    elif NEED_MORE_ROUNDS_RE.search(response):
        judge_action = "continue"
    else:
        judge_action = "continue"
    return {
        "current_match": {
            **match,
            "rounds": rounds,
            "verdict": cleaned_response,
        },
        "judge_action": judge_action,
        "match_winner": _extract_match_winner(response),
        "match_verdict": cleaned_response,
        "result": cleaned_response,
        "messages": [make_message(judge["role"], cleaned_response, _match_phase(state, f"round_{state['current_match_round']}_verdict"))],
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
