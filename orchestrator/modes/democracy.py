"""Democracy mode: all agents vote, majority wins, tie → re-vote."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, call_agent_cfg, make_message, strip_markdown_fence


class DemocracyState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    votes: list[dict]
    round: int
    max_rounds: int
    majority_position: str
    result: str


def collect_votes(state: DemocracyState) -> dict:
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
        response = call_agent_cfg(agent, prompt)
        try:
            vote = json.loads(strip_markdown_fence(response))
        except json.JSONDecodeError:
            vote = {"position": response[:200], "reasoning": ""}
        vote["agent_id"] = agent["role"]
        votes.append(vote)
        messages.append(make_message(agent["role"], f"Vote: {vote['position']}", f"voting_round_{state['round'] + 1}"))
    return {"votes": votes, "round": state["round"] + 1, "messages": messages}


def tally_votes(state: DemocracyState) -> dict:
    votes_text = "\n".join(f"- {v['agent_id']}: {v['position']}" for v in state["votes"])
    prompt = (
        f"Analyze these votes and determine if there is a clear majority.\n\n"
        f"VOTES:\n{votes_text}\n\n"
        f"Respond with JSON:\n"
        f'{{"has_majority": true, "majority_position": "the winning position", "summary": "brief summary"}}\n'
        f"Return ONLY valid JSON."
    )
    # TODO: make arbitrator provider configurable via state config
    response = call_agent("minimax", prompt)
    try:
        tally = json.loads(strip_markdown_fence(response))
    except json.JSONDecodeError:
        tally = {"has_majority": True, "majority_position": state["votes"][0]["position"], "summary": response}
    messages = [make_message("system", f"Tally: {tally.get('summary', '')}", f"tally_round_{state['round']}")]
    if tally.get("has_majority"):
        return {"majority_position": tally.get("majority_position", ""), "result": tally.get("majority_position", ""), "messages": messages}
    return {"majority_position": "", "messages": messages}


def route_after_tally(state: DemocracyState) -> str:
    if state["majority_position"]:
        return END
    if state["round"] >= state["max_rounds"]:
        return "force_decision"
    return "collect_votes"


def force_decision(state: DemocracyState) -> dict:
    votes_text = "\n".join(f"- {v['agent_id']}: {v['position']}" for v in state["votes"])
    # TODO: make arbitrator provider configurable via state config
    response = call_agent(
        "minimax",
        f"No majority was reached after {state['round']} rounds.\n\nVotes:\n{votes_text}\n\n"
        f"Summarize both positions and pick the most-supported one as the final answer.",
    )
    return {"result": response, "messages": [make_message("system", response, "forced_decision")]}


def build_democracy_graph() -> StateGraph:
    builder = StateGraph(DemocracyState)
    builder.add_node("collect_votes", collect_votes)
    builder.add_node("tally_votes", tally_votes)
    builder.add_node("force_decision", force_decision)
    builder.add_edge(START, "collect_votes")
    builder.add_edge("collect_votes", "tally_votes")
    builder.add_conditional_edges("tally_votes", route_after_tally, {
        END: END, "collect_votes": "collect_votes", "force_decision": "force_decision",
    })
    builder.add_edge("force_decision", END)
    return builder.compile()
