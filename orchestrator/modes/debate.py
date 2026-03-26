"""Debate mode: proponent vs opponent, judge decides."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import apply_user_instructions, call_agent_cfg, make_message


class DebateState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    rounds: list[dict]
    current_round: int
    max_rounds: int
    verdict: str
    result: str


def proponent_argues(state: DebateState) -> dict:
    pro = state["agents"][0]
    rnd = state["current_round"]
    history = ""
    if state["rounds"]:
        history = "\n\nPrevious rounds:\n" + "\n".join(
            f"Round {r['round']}:\n  PRO: {r['pro_arg'][:300]}\n  CON: {r['con_arg'][:300]}"
            for r in state["rounds"]
        )
    prompt = (
        f"You are arguing FOR the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n{history}\n\n"
        f"Make your strongest argument. Be specific and evidence-based. "
        f"If this is round 2+, rebut the opponent's previous points."
    )
    response = call_agent_cfg(pro, apply_user_instructions(state, prompt))
    return {
        "messages": [make_message(pro["role"], response, f"round_{rnd + 1}_pro")],
        "rounds": [*state["rounds"], {"round": rnd + 1, "pro_arg": response, "con_arg": ""}],
    }


def opponent_argues(state: DebateState) -> dict:
    opp = state["agents"][1]
    rnd = state["current_round"]
    current_round_data = state["rounds"][-1]
    pro_arg = current_round_data["pro_arg"]
    history = ""
    if len(state["rounds"]) > 1:
        history = "\n\nPrevious rounds:\n" + "\n".join(
            f"Round {r['round']}:\n  PRO: {r['pro_arg'][:300]}\n  CON: {r['con_arg'][:300]}"
            for r in state["rounds"][:-1]
        )
    prompt = (
        f"You are arguing AGAINST the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n{history}\n\n"
        f"Proponent's argument this round:\n{pro_arg}\n\n"
        f"Counter-argue. Be specific. Attack weak points."
    )
    response = call_agent_cfg(opp, apply_user_instructions(state, prompt))
    updated_rounds = list(state["rounds"])
    updated_rounds[-1] = {**updated_rounds[-1], "con_arg": response}
    return {
        "messages": [make_message(opp["role"], response, f"round_{rnd + 1}_con")],
        "rounds": updated_rounds,
        "current_round": rnd + 1,
    }


def judge_decides(state: DebateState) -> dict:
    judge = state["agents"][2]
    debate_text = "\n\n".join(
        f"=== Round {r['round']} ===\nPRO: {r['pro_arg']}\nCON: {r['con_arg']}"
        for r in state["rounds"]
    )
    prompt = (
        f"You are the judge. Evaluate this debate.\n\n"
        f"TOPIC: {state['task']}\n\nDEBATE:\n{debate_text}\n\n"
        f"Provide:\n1. Your verdict (which side won and why)\n"
        f"2. The strongest argument from each side\n3. Your final recommendation\n\n"
        f"If you need one more round of debate, say NEED_MORE_ROUNDS."
    )
    response = call_agent_cfg(judge, apply_user_instructions(state, prompt))
    return {
        "verdict": response, "result": response,
        "messages": [make_message(judge["role"], response, "verdict")],
    }


def route_after_judge(state: DebateState) -> str:
    if "NEED_MORE_ROUNDS" in state["verdict"] and state["current_round"] < state["max_rounds"]:
        return "proponent_argues"
    return END


def build_debate_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(DebateState)
    builder.add_node("proponent_argues", proponent_argues)
    builder.add_node("opponent_argues", opponent_argues)
    builder.add_node("judge_decides", judge_decides)
    builder.add_edge(START, "proponent_argues")
    builder.add_edge("proponent_argues", "opponent_argues")
    builder.add_edge("opponent_argues", "judge_decides")
    builder.add_conditional_edges("judge_decides", route_after_judge, {
        "proponent_argues": "proponent_argues", END: END,
    })
    return builder.compile(**compile_kwargs)
