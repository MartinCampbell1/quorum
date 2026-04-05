"""Democracy mode: all agents vote, majority wins, tie -> re-vote.

If no majority appears after the configured rounds, a deterministic plurality
fallback picks the most-supported position so the graph can terminate without
hidden arbitration.
"""

from collections import Counter
import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.debate.moderators import review_unanimous_consensus
from orchestrator.debate.protocols import build_protocol_telemetry, resolve_protocol_for_mode
from orchestrator.modes.base import apply_user_instructions, call_agent_cfg, make_message, strip_markdown_fence


class DemocracyState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    config: dict
    votes: list[dict]
    round: int
    max_rounds: int
    majority_position: str
    majority_candidate: str
    protocol_name: str
    protocol_telemetry: dict
    scrutiny_requested: bool
    result: str


def _protocol(state: DemocracyState):
    return resolve_protocol_for_mode("democracy", state.get("config") or {})


def _normalize_position(position: str) -> str:
    return " ".join(position.split()).strip().lower()


def _vote_summary(votes: list[dict]) -> tuple[Counter, dict[str, str], dict[str, int]]:
    counts: Counter = Counter()
    representatives: dict[str, str] = {}
    first_seen: dict[str, int] = {}

    for idx, vote in enumerate(votes):
        raw_position = str(vote.get("position", "")).strip()
        if not raw_position:
            continue
        key = _normalize_position(raw_position)
        counts[key] += 1
        representatives.setdefault(key, raw_position)
        first_seen.setdefault(key, idx)

    return counts, representatives, first_seen


def _pick_plurality(votes: list[dict]) -> str:
    counts, representatives, first_seen = _vote_summary(votes)
    if not counts:
        return ""
    winner = max(counts.keys(), key=lambda key: (counts[key], -first_seen[key], key))
    return representatives[winner]


def collect_votes(state: DemocracyState) -> dict:
    protocol = _protocol(state)
    votes = []
    messages = []
    previous = ""
    if state["round"] > 1 and state["votes"]:
        previous = "\n\nPrevious round votes (no majority reached):\n" + "\n".join(
            f"- {v['agent_id']}: {v['position']}" for v in state["votes"]
        )
    for agent in state["agents"]:
        prompt = (
            f"Vote on this task. Give your position clearly.\n\n"
            f"TASK: {state['task']}\n{previous}\n\n"
            f"Respond with JSON: {{\"position\": \"your clear position\", \"reasoning\": \"why\"}}\n"
            f"Return ONLY valid JSON."
        )
        response = call_agent_cfg(agent, apply_user_instructions(state, prompt))
        try:
            vote = json.loads(strip_markdown_fence(response))
        except json.JSONDecodeError:
            vote = {"position": response[:200], "reasoning": ""}
        vote["agent_id"] = agent["role"]
        votes.append(vote)
        messages.append(make_message(agent["role"], f"Vote: {vote['position']}", f"voting_round_{state['round'] + 1}", protocol_name=protocol.name))
    if not votes:
        messages.append(make_message("system", "No agents available for voting", f"voting_round_{state['round'] + 1}", protocol_name=protocol.name))
    return {"votes": votes, "round": state["round"] + 1, "messages": messages, "protocol_name": protocol.name}


def tally_votes(state: DemocracyState) -> dict:
    protocol = _protocol(state)
    counts, representatives, first_seen = _vote_summary(state["votes"])
    messages = []

    if not counts:
        messages.append(make_message("system", "No valid votes were cast", f"tally_round_{state['round']}", protocol_name=protocol.name))
        return {"majority_position": "", "majority_candidate": "", "result": "", "messages": messages, "scrutiny_requested": False, "protocol_name": protocol.name}

    total_votes = sum(counts.values())
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[f"{item.get('position', '')}\n{item.get('reasoning', '')}".strip() for item in state["votes"]],
        confidence=(max(counts.values()) / total_votes) if total_votes else 0.0,
        stances=[str(vote.get("position") or "").strip() for vote in state["votes"]],
    )
    for key, count in counts.items():
        if count > total_votes / 2:
            position = representatives[key]
            if protocol.scrutiny_on_unanimous_consensus and count == total_votes and total_votes >= 2:
                messages.append(make_message(
                    "system",
                    f"Unanimous majority reached for: {position}. Triggering scrutiny before finalization.",
                    f"tally_round_{state['round']}",
                    protocol_name=protocol.name,
                    telemetry=telemetry.model_dump(),
                ))
                return {
                    "majority_position": "",
                    "majority_candidate": position,
                    "result": "",
                    "messages": messages,
                    "scrutiny_requested": True,
                    "protocol_name": protocol.name,
                    "protocol_telemetry": telemetry.model_dump(),
                }
            messages.append(make_message(
                "system",
                f"Majority reached: {position} ({count}/{total_votes})",
                f"tally_round_{state['round']}",
                protocol_name=protocol.name,
                telemetry=telemetry.model_dump(),
            ))
            return {
                "majority_position": position,
                "majority_candidate": position,
                "result": position,
                "messages": messages,
                "scrutiny_requested": False,
                "protocol_name": protocol.name,
                "protocol_telemetry": telemetry.model_dump(),
            }

    summary = ", ".join(
        f"{representatives[key]} x{counts[key]}"
        for key in sorted(counts.keys(), key=lambda key: (-counts[key], first_seen[key], key))
    )
    messages.append(make_message("system", f"No majority yet: {summary}", f"tally_round_{state['round']}", protocol_name=protocol.name, telemetry=telemetry.model_dump()))
    return {"majority_position": "", "majority_candidate": "", "result": "", "messages": messages, "scrutiny_requested": False, "protocol_name": protocol.name, "protocol_telemetry": telemetry.model_dump()}


def route_after_tally(state: DemocracyState) -> str:
    if state.get("scrutiny_requested"):
        return "scrutinize_majority"
    if state["majority_position"]:
        return END
    if state["round"] >= state["max_rounds"]:
        return "force_decision"
    return "collect_votes"


def scrutinize_majority(state: DemocracyState) -> dict:
    protocol = _protocol(state)
    candidate = str(state.get("majority_candidate") or "").strip()
    scrutiny = review_unanimous_consensus(protocol, list(state["votes"]), candidate)
    message = scrutiny.reason
    if scrutiny.passed:
        return {
            "majority_position": candidate,
            "majority_candidate": candidate,
            "result": candidate,
            "scrutiny_requested": False,
            "protocol_name": protocol.name,
            "protocol_telemetry": scrutiny.telemetry.model_dump(),
            "messages": [make_message("system", message, "majority_scrutiny", protocol_name=protocol.name, telemetry=scrutiny.telemetry.model_dump())],
        }
    return {
        "majority_position": "",
        "result": "",
        "scrutiny_requested": False,
        "protocol_name": protocol.name,
        "protocol_telemetry": scrutiny.telemetry.model_dump(),
        "messages": [make_message("system", message, "majority_scrutiny", protocol_name=protocol.name, telemetry=scrutiny.telemetry.model_dump())],
    }


def route_after_scrutiny(state: DemocracyState) -> str:
    if state["majority_position"]:
        return END
    if state["round"] >= state["max_rounds"]:
        return "force_decision"
    return "collect_votes"


def force_decision(state: DemocracyState) -> dict:
    winner = _pick_plurality(state["votes"])
    if winner:
        message = (
            f"No majority after {state['round']} rounds. "
            f"Deterministic fallback selected: {winner}"
        )
        return {
            "majority_position": winner,
            "result": winner,
            "messages": [make_message("system", message, "forced_decision")],
        }

    message = f"No valid votes available after {state['round']} rounds."
    return {
        "majority_position": "",
        "result": message,
        "messages": [make_message("system", message, "forced_decision")],
    }


def build_democracy_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(DemocracyState)
    builder.add_node("collect_votes", collect_votes)
    builder.add_node("tally_votes", tally_votes)
    builder.add_node("scrutinize_majority", scrutinize_majority)
    builder.add_node("force_decision", force_decision)
    builder.add_edge(START, "collect_votes")
    builder.add_edge("collect_votes", "tally_votes")
    builder.add_conditional_edges("tally_votes", route_after_tally, {
        END: END, "collect_votes": "collect_votes", "force_decision": "force_decision", "scrutinize_majority": "scrutinize_majority",
    })
    builder.add_conditional_edges("scrutinize_majority", route_after_scrutiny, {
        END: END, "collect_votes": "collect_votes", "force_decision": "force_decision",
    })
    builder.add_edge("force_decision", END)
    return builder.compile(**compile_kwargs)
