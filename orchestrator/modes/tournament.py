"""Tournament mode: bracket-style competition with judge."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import apply_user_instructions, call_agent_cfg, make_message, strip_markdown_fence


class TournamentState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    submissions: list[dict]
    bracket: list[list[dict]]
    current_round: int
    winners: list[dict]
    champion: dict
    result: str


def all_compete(state: TournamentState) -> dict:
    competitors = state["agents"][:-1]
    submissions = []
    messages = []
    for agent in competitors:
        response = call_agent_cfg(agent, apply_user_instructions(state, f"Solve this task. Give your best answer.\n\n{state['task']}"))
        sub = {"agent_id": agent["role"], "provider": agent["provider"], "solution": response}
        submissions.append(sub)
        messages.append(make_message(agent["role"], response, "submission"))
    return {"submissions": submissions, "messages": messages}


def setup_bracket(state: TournamentState) -> dict:
    subs = list(state["submissions"])
    matchups = []
    while len(subs) >= 2:
        matchups.append({"a": subs.pop(0), "b": subs.pop(0)})
    byes = subs
    winners = [{"agent_id": b["agent_id"], "provider": b["provider"], "solution": b["solution"]} for b in byes]
    return {
        "bracket": [matchups], "winners": winners, "current_round": 1,
        "messages": [make_message("system", f"Tournament bracket: {len(matchups)} matches, {len(byes)} byes", "bracket_setup")],
    }


def judge_matches(state: TournamentState) -> dict:
    judge = state["agents"][-1]
    current_matchups = state["bracket"][-1]
    new_winners = list(state["winners"])
    messages = []
    for i, match in enumerate(current_matchups):
        prompt = (
            f"Judge this match (round {state['current_round']}, match {i + 1}).\n\n"
            f"TASK: {state['task']}\n\n"
            f"CONTESTANT A ({match['a']['agent_id']}):\n{match['a']['solution']}\n\n"
            f"CONTESTANT B ({match['b']['agent_id']}):\n{match['b']['solution']}\n\n"
            f"Which solution is better? Respond with JSON:\n"
            f'{{\"winner\": \"A\" or \"B\", \"reasoning\": \"why\"}}\nReturn ONLY valid JSON.'
        )
        response = call_agent_cfg(judge, apply_user_instructions(state, prompt))
        try:
            verdict = json.loads(strip_markdown_fence(response))
        except json.JSONDecodeError:
            verdict = {"winner": "A", "reasoning": response}
        winner_entry = match["a"] if verdict.get("winner", "A").upper() == "A" else match["b"]
        loser_entry = match["b"] if verdict.get("winner", "A").upper() == "A" else match["a"]
        new_winners.append(winner_entry)
        messages.append(make_message(judge["role"],
            f"Match {i+1}: {winner_entry['agent_id']} beats {loser_entry['agent_id']}. {verdict.get('reasoning', '')}",
            f"round_{state['current_round']}_match_{i+1}"))
    return {"winners": new_winners, "messages": messages}


def route_after_judging(state: TournamentState) -> str:
    if len(state["winners"]) <= 1:
        return "crown_champion"
    return "next_round"


def next_round(state: TournamentState) -> dict:
    subs = list(state["winners"])
    matchups = []
    while len(subs) >= 2:
        matchups.append({"a": subs.pop(0), "b": subs.pop(0)})
    byes = subs
    winners = [{"agent_id": b["agent_id"], "provider": b["provider"], "solution": b["solution"]} for b in byes]
    return {
        "bracket": [*state["bracket"], matchups], "winners": winners,
        "current_round": state["current_round"] + 1,
        "messages": [make_message("system", f"Round {state['current_round'] + 1}: {len(matchups)} matches", "next_round")],
    }


def crown_champion(state: TournamentState) -> dict:
    if state["winners"]:
        champ = state["winners"][0]
    elif state["submissions"]:
        champ = state["submissions"][0]
    else:
        champ = {"agent_id": "none", "solution": "No submissions"}
    return {
        "champion": champ,
        "result": f"Champion: {champ['agent_id']}\n\nSolution:\n{champ['solution']}",
        "messages": [make_message("system", f"Champion: {champ['agent_id']}", "champion")],
    }


def build_tournament_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(TournamentState)
    builder.add_node("all_compete", all_compete)
    builder.add_node("setup_bracket", setup_bracket)
    builder.add_node("judge_matches", judge_matches)
    builder.add_node("next_round", next_round)
    builder.add_node("crown_champion", crown_champion)
    builder.add_edge(START, "all_compete")
    builder.add_edge("all_compete", "setup_bracket")
    builder.add_edge("setup_bracket", "judge_matches")
    builder.add_conditional_edges("judge_matches", route_after_judging, {
        "next_round": "next_round", "crown_champion": "crown_champion",
    })
    builder.add_edge("next_round", "judge_matches")
    builder.add_edge("crown_champion", END)
    return builder.compile(**compile_kwargs)
