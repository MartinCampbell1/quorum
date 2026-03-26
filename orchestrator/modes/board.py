"""Board mode: council of directors discuss, vote, then delegate."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class BoardState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    positions: list[dict]
    vote_round: int
    max_rounds: int
    consensus_reached: bool
    decision: str
    worker_results: Annotated[list[dict], operator.add]
    result: str


def directors_analyze(state: BoardState) -> dict:
    directors = state["agents"][:3]
    positions = []
    messages = []
    previous = ""
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
        response = call_agent(d["provider"], prompt, d.get("system_prompt", ""))
        try:
            pos = json.loads(response.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            pos = {"position": response[:300], "reasoning": "", "action_items": []}
        pos["director"] = d["role"]
        positions.append(pos)
        messages.append(make_message(d["role"], f"Position: {pos['position']}", f"board_round_{state['vote_round'] + 1}"))
    return {"positions": positions, "vote_round": state["vote_round"] + 1, "messages": messages}


def check_consensus(state: BoardState) -> dict:
    positions_text = "\n".join(f"- {p['director']}: {p['position']}" for p in state["positions"])
    response = call_agent(
        "minimax",
        f"Do these board members agree? Analyze their positions.\n\n"
        f"{positions_text}\n\nRespond with JSON: {{\"consensus\": true, \"unified_decision\": \"the agreed position\"}}\nReturn ONLY valid JSON.",
    )
    try:
        result = json.loads(response.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        result = {"consensus": True, "unified_decision": state["positions"][0]["position"]}
    return {
        "consensus_reached": result.get("consensus", False),
        "decision": result.get("unified_decision", ""),
        "messages": [make_message("system", f"Consensus: {result.get('consensus')}", "consensus_check")],
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
    chairman = state["agents"][0]
    positions_text = "\n".join(
        f"- {p['director']}: {p['position']}\n  Reasoning: {p['reasoning']}" for p in state["positions"]
    )
    response = call_agent(
        chairman["provider"],
        f"As chairman, no consensus after {state['vote_round']} rounds.\n\nPositions:\n{positions_text}\n\nMake the final decision.",
        chairman.get("system_prompt", ""),
    )
    return {"decision": response, "messages": [make_message(chairman["role"], response, "chairman_decision")]}


def delegate_to_workers(state: BoardState) -> dict:
    workers = state["agents"][3:]
    results = []
    messages = []
    for worker in workers:
        response = call_agent(
            worker["provider"],
            f"The board decided:\n{state['decision']}\n\nExecute your part.\nOriginal task: {state['task']}",
            worker.get("system_prompt", ""),
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


def build_board_graph() -> StateGraph:
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
    return builder.compile()
