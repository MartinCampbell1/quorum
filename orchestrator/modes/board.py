"""Board mode: council of directors discuss, vote, then delegate."""

from collections import Counter
import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import apply_user_instructions, call_agent_cfg, make_message, strip_markdown_fence


class BoardState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    positions: list[dict]
    vote_round: int
    max_rounds: int
    consensus_reached: bool
    decision: str
    worker_results: list[dict]
    result: str


def _normalize_position(position: str) -> str:
    return " ".join(position.split()).strip().lower()


def _summarize_positions(positions: list[dict]) -> tuple[Counter, dict[str, str], dict[str, int]]:
    counts: Counter = Counter()
    representatives: dict[str, str] = {}
    first_seen: dict[str, int] = {}

    for idx, position in enumerate(positions):
        raw = str(position.get("position", "")).strip()
        if not raw:
            continue
        key = _normalize_position(raw)
        counts[key] += 1
        representatives.setdefault(key, raw)
        first_seen.setdefault(key, idx)

    return counts, representatives, first_seen


def directors_analyze(state: BoardState) -> dict:
    directors = state["agents"][:3]
    positions = []
    messages = []
    previous = ""
    if not directors:
        return {
            "positions": [],
            "vote_round": state["vote_round"] + 1,
            "messages": [make_message("system", "No directors available", f"board_round_{state['vote_round'] + 1}")],
        }
    if state["positions"]:
        previous = "\n\nPrevious round positions (no consensus):\n" + "\n".join(
            f"- {p['director']}: {p['position']}" for p in state["positions"]
        )
    for d in directors:
        prompt = (
            f"You are on a board of directors. Analyze this task and give your position.\n\n"
            f"TASK: {state['task']}\n{previous}\n\n"
            f"Respond with JSON: {{\"position\": \"your stance\", \"reasoning\": \"why\", "
            f"\"action_items\": [\"what to delegate to workers\"]}}\nReturn ONLY valid JSON."
        )
        response = call_agent_cfg(d, apply_user_instructions(state, prompt))
        try:
            pos = json.loads(strip_markdown_fence(response))
        except json.JSONDecodeError:
            pos = {"position": response[:300], "reasoning": "", "action_items": []}
        pos["director"] = d["role"]
        positions.append(pos)
        messages.append(make_message(d["role"], f"Position: {pos['position']}", f"board_round_{state['vote_round'] + 1}"))
    return {"positions": positions, "vote_round": state["vote_round"] + 1, "messages": messages}


def check_consensus(state: BoardState) -> dict:
    counts, representatives, first_seen = _summarize_positions(state["positions"])
    if not counts:
        return {
            "consensus_reached": False,
            "decision": "",
            "messages": [make_message("system", "No board positions to compare", "consensus_check")],
        }

    consensus = len(counts) == 1
    decision = representatives[next(iter(counts))] if consensus else ""
    summary = ", ".join(
        f"{representatives[key]} x{counts[key]}"
        for key in sorted(counts.keys(), key=lambda key: (-counts[key], first_seen[key], key))
    )
    return {
        "consensus_reached": consensus,
        "decision": decision,
        "messages": [make_message("system", f"Consensus: {consensus}. Positions: {summary}", "consensus_check")],
    }


def route_after_consensus(state: BoardState) -> str:
    if state["consensus_reached"]:
        if len(state["agents"]) > 3:
            return "delegate_to_workers"
        return "finalize"
    if state["vote_round"] >= state["max_rounds"]:
        return "chairman_decides"
    return "directors_analyze"


def chairman_decides(state: BoardState) -> dict:
    if not state["agents"]:
        message = "No chairman available."
        return {"decision": "", "result": message, "messages": [make_message("system", message, "chairman_decision")]}

    chairman = state["agents"][0]
    chairman_position = ""
    for position in state["positions"]:
        if position.get("director") == chairman["role"] and position.get("position"):
            chairman_position = str(position["position"]).strip()
            break
    if not chairman_position:
        for position in state["positions"]:
            raw = str(position.get("position", "")).strip()
            if raw:
                chairman_position = raw
                break
    positions_text = "\n".join(
        f"- {p['director']}: {p['position']}\n  Reasoning: {p['reasoning']}" for p in state["positions"]
    )
    if chairman_position:
        response = (
            f"As chairman, no consensus after {state['vote_round']} rounds.\n\n"
            f"Positions:\n{positions_text}\n\n"
            f"Final decision: {chairman_position}"
        )
        return {
            "decision": chairman_position,
            "result": chairman_position,
            "messages": [make_message(chairman["role"], response, "chairman_decision")],
        }

    response = f"As chairman, no consensus after {state['vote_round']} rounds, but no position was recorded."
    return {"decision": "", "result": response, "messages": [make_message(chairman["role"], response, "chairman_decision")]}


def delegate_to_workers(state: BoardState) -> dict:
    workers = state["agents"][3:]
    results = []
    messages = []
    for worker in workers:
        response = call_agent_cfg(
            worker,
            apply_user_instructions(
                state,
                f"The board decided:\n{state['decision']}\n\nExecute your part.\nOriginal task: {state['task']}",
            ),
        )
        results.append({"worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, "worker_execution"))
    return {"worker_results": results, "messages": messages}


def finalize(state: BoardState) -> dict:
    if state["worker_results"]:
        combined = "\n\n".join(f"{r['worker']}: {r['result']}" for r in state["worker_results"])
        result = f"Board decision: {state['decision']}\n\nExecution:\n{combined}"
    else:
        result = state["decision"]
    return {"result": result, "messages": [make_message("system", "Session complete", "done")]}


def build_board_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(BoardState)
    builder.add_node("directors_analyze", directors_analyze)
    builder.add_node("check_consensus", check_consensus)
    builder.add_node("chairman_decides", chairman_decides)
    builder.add_node("delegate_to_workers", delegate_to_workers)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "directors_analyze")
    builder.add_edge("directors_analyze", "check_consensus")
    builder.add_conditional_edges("check_consensus", route_after_consensus, {
        "delegate_to_workers": "delegate_to_workers", "finalize": "finalize",
        "chairman_decides": "chairman_decides", "directors_analyze": "directors_analyze",
    })
    builder.add_edge("chairman_decides", "delegate_to_workers")
    builder.add_edge("delegate_to_workers", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(**compile_kwargs)
