"""Creator-Critic mode: iterative refinement loop."""

import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.debate.protocols import build_protocol_telemetry, resolve_protocol_for_mode
from orchestrator.modes.base import apply_user_instructions, call_agent_cfg, make_message, require_agent_response


class CreatorCriticState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    config: dict
    versions: list[str]
    critiques: list[str]
    iteration: int
    max_iterations: int
    approved: bool
    protocol_name: str
    protocol_telemetry: dict
    result: str


def _protocol(state: CreatorCriticState):
    return resolve_protocol_for_mode("creator_critic", state.get("config") or {})


def creator_produces(state: CreatorCriticState) -> dict:
    protocol = _protocol(state)
    creator = state["agents"][0]
    if state["iteration"] == 0:
        prompt = f"Complete this task:\n\n{state['task']}"
    else:
        last_critique = state["critiques"][-1] if state["critiques"] else ""
        last_version = state["versions"][-1] if state["versions"] else ""
        prompt = (
            f"Revise your work based on the critic's feedback.\n\n"
            f"ORIGINAL TASK: {state['task']}\n\nYOUR PREVIOUS VERSION:\n{last_version}\n\n"
            f"CRITIC'S FEEDBACK:\n{last_critique}\n\nProduce an improved version addressing all feedback."
        )
    response = require_agent_response(
        creator,
        call_agent_cfg(creator, apply_user_instructions(state, prompt)),
        "Creator step failed",
    )
    return {
        "protocol_name": protocol.name,
        "versions": [*state["versions"], response],
        "messages": [make_message(creator["role"], response, f"version_{state['iteration'] + 1}", protocol_name=protocol.name)],
    }


def critic_evaluates(state: CreatorCriticState) -> dict:
    protocol = _protocol(state)
    critic = state["agents"][1]
    latest_version = state["versions"][-1]
    prompt = (
        f"Evaluate this work critically.\n\nTASK: {state['task']}\n\n"
        f"WORK (version {state['iteration'] + 1}):\n{latest_version}\n\n"
        f"Rate: APPROVED (if good enough) or NEEDS_WORK (with specific feedback).\nIf NEEDS_WORK, list exactly what needs to change."
    )
    response = require_agent_response(
        critic,
        call_agent_cfg(critic, apply_user_instructions(state, prompt)),
        "Critic step failed",
    )
    approved = "APPROVED" in response.upper() and "NEEDS_WORK" not in response.upper()
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[*state["versions"], response],
        confidence=0.82 if approved else 0.46,
    )
    return {
        "critiques": [*state["critiques"], response], "iteration": state["iteration"] + 1,
        "approved": approved, "result": latest_version if approved else "",
        "protocol_name": protocol.name,
        "protocol_telemetry": telemetry.model_dump(),
        "messages": [make_message(critic["role"], response, f"critique_{state['iteration'] + 1}", protocol_name=protocol.name, telemetry=telemetry.model_dump())],
    }


def route_after_critique(state: CreatorCriticState) -> str:
    if state["approved"]:
        return END
    if state["iteration"] >= state["max_iterations"]:
        return "final_version"
    return "creator_produces"


def final_version(state: CreatorCriticState) -> dict:
    protocol = _protocol(state)
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[*state["versions"], *state["critiques"]],
        confidence=0.68 if state["versions"] else 0.0,
    )
    return {
        "result": state["versions"][-1] if state["versions"] else "",
        "protocol_name": protocol.name,
        "protocol_telemetry": telemetry.model_dump(),
        "messages": [make_message("system", f"Max iterations ({state['max_iterations']}) reached.", "max_iterations", protocol_name=protocol.name, telemetry=telemetry.model_dump())],
    }


def build_creator_critic_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(CreatorCriticState)
    builder.add_node("creator_produces", creator_produces)
    builder.add_node("critic_evaluates", critic_evaluates)
    builder.add_node("final_version", final_version)
    builder.add_edge(START, "creator_produces")
    builder.add_edge("creator_produces", "critic_evaluates")
    builder.add_conditional_edges("critic_evaluates", route_after_critique, {
        "creator_produces": "creator_produces", "final_version": "final_version", END: END,
    })
    builder.add_edge("final_version", END)
    return builder.compile(**compile_kwargs)
