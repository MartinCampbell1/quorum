"""Debate mode: proponent vs opponent, judge decides."""

import operator
import re
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import (
    apply_user_instructions,
    build_workspace_context_prompt,
    call_agent_cfg,
    make_message,
    require_agent_response,
)


class DebateState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    rounds: list[dict]
    current_round: int
    max_rounds: int
    verdict: str
    judge_action: str
    result: str


FINAL_VERDICT_MARKER = "FINAL_VERDICT"
CONTINUE_MARKER = "NEED_MORE_ROUNDS"
CONTROL_MARKER_RE = re.compile(r"\b(?:FINAL_VERDICT|NEED_MORE_ROUNDS)\b[:\-\s]*", re.IGNORECASE)


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
        f"{build_workspace_context_prompt(pro)}"
        f"You are arguing FOR the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n{history}\n\n"
        f"Make your strongest argument. Be specific and evidence-based. "
        f"If this is round 2+, rebut the opponent's previous points."
    )
    response = require_agent_response(
        pro,
        call_agent_cfg(pro, apply_user_instructions(state, prompt)),
        "Debate proponent step failed",
    )
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
        f"{build_workspace_context_prompt(opp)}"
        f"You are arguing AGAINST the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n{history}\n\n"
        f"Proponent's argument this round:\n{pro_arg}\n\n"
        f"Counter-argue. Be specific. Attack weak points."
    )
    response = require_agent_response(
        opp,
        call_agent_cfg(opp, apply_user_instructions(state, prompt)),
        "Debate opponent step failed",
    )
    updated_rounds = list(state["rounds"])
    updated_rounds[-1] = {**updated_rounds[-1], "con_arg": response}
    return {
        "messages": [make_message(opp["role"], response, f"round_{rnd + 1}_con")],
        "rounds": updated_rounds,
        "current_round": rnd + 1,
    }


def judge_decides(state: DebateState) -> dict:
    judge = state["agents"][2]
    current_round = int(state["current_round"] or 0)
    max_rounds = max(int(state["max_rounds"] or 1), 1)
    final_round = current_round >= max_rounds
    debate_text = "\n\n".join(
        f"=== Round {r['round']} ===\nPRO: {r['pro_arg']}\nCON: {r['con_arg']}"
        for r in state["rounds"]
    )
    if final_round:
        round_instruction = (
            f"This is round {current_round} of {max_rounds}, which is the final allowed round.\n"
            f"Return {FINAL_VERDICT_MARKER} and then provide:\n"
            f"1. Your verdict (which side won and why)\n"
            f"2. The strongest argument from each side\n"
            f"3. Your final recommendation"
        )
    else:
        round_instruction = (
            f"This is round {current_round} of {max_rounds}.\n"
            f"By default, the debate should continue until the configured round limit.\n"
            f"If one side has already clearly won and more rounds are unnecessary, start your answer with {FINAL_VERDICT_MARKER}.\n"
            f"Otherwise start your answer with {CONTINUE_MARKER} and give a short interim assessment plus one concrete challenge for each side to address next round."
        )
    prompt = (
        f"{build_workspace_context_prompt(judge)}"
        f"You are the judge. Evaluate this debate.\n\n"
        f"TOPIC: {state['task']}\n\nDEBATE:\n{debate_text}\n\n"
        f"{round_instruction}"
    )
    response = require_agent_response(
        judge,
        call_agent_cfg(judge, apply_user_instructions(state, prompt)),
        "Debate judge step failed",
    )
    cleaned_response = CONTROL_MARKER_RE.sub("", response).strip() or response.strip()
    if final_round:
        judge_action = "final"
    elif FINAL_VERDICT_MARKER in response.upper():
        judge_action = "final"
    elif CONTINUE_MARKER in response.upper():
        judge_action = "continue"
    else:
        # Default to using the configured round budget unless the judge explicitly finalizes early.
        judge_action = "continue"
    return {
        "judge_action": judge_action,
        "verdict": cleaned_response,
        "result": cleaned_response,
        "messages": [make_message(judge["role"], cleaned_response, "verdict")],
    }


def route_after_judge(state: DebateState) -> str:
    if state.get("judge_action") == "continue" and state["current_round"] < state["max_rounds"]:
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
