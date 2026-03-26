"""Dictator mode: one director delegates to workers, collects results."""

import asyncio
import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import apply_user_instructions, call_agent, call_agent_cfg, make_message, strip_markdown_fence


class DictatorState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    subtasks: list[dict]
    worker_results: list[dict]
    iteration: int
    max_iterations: int
    result: str


def director_plan(state: DictatorState) -> dict:
    """Director breaks task into subtasks."""
    director = state["agents"][0]
    workers = state["agents"][1:]

    prompt = (
        f"You are the director. Break this task into {len(workers)} subtasks.\n\n"
        f"TASK: {state['task']}\n\n"
        f"Available workers: {json.dumps([w['role'] for w in workers])}\n\n"
        f"Respond with a JSON array of objects: "
        f'[{{"description": "subtask text", "worker_index": 0}}, ...]\n'
        f"worker_index is 0-based index into the workers list.\n"
        f"Return ONLY valid JSON, no markdown."
    )

    response = call_agent_cfg(director, apply_user_instructions(state, prompt))

    try:
        subtasks = json.loads(strip_markdown_fence(response))
    except json.JSONDecodeError:
        subtasks = [{"description": state["task"], "worker_index": i}
                    for i in range(len(workers))]

    return {
        "subtasks": subtasks,
        "messages": [make_message(director["role"], f"Plan: {json.dumps(subtasks, ensure_ascii=False)}", "planning")],
    }


def workers_execute(state: DictatorState) -> dict:
    """Workers execute their assigned subtasks."""
    workers = state["agents"][1:]
    results = []
    messages = []

    for st in state["subtasks"]:
        idx = st.get("worker_index", 0) % len(workers)
        worker = workers[idx]

        prompt = (
            f"Complete this subtask:\n{st['description']}\n\n"
            f"Context — overall task: {state['task']}"
        )

        response = call_agent_cfg(worker, apply_user_instructions(state, prompt))
        results.append({"subtask": st["description"], "worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, "executing"))

    return {"worker_results": results, "messages": messages}


def director_synthesize(state: DictatorState) -> dict:
    """Director reviews worker results and synthesizes final answer."""
    director = state["agents"][0]

    results_text = "\n\n".join(
        f"## {r['worker']}: {r['subtask']}\n{r['result']}"
        for r in state["worker_results"]
    )

    prompt = (
        f"You are the director. Your workers completed their subtasks.\n\n"
        f"ORIGINAL TASK: {state['task']}\n\n"
        f"WORKER RESULTS:\n{results_text}\n\n"
        f"Synthesize a comprehensive final answer. "
        f"If results are insufficient, say NEEDS_MORE_WORK and explain what's missing."
    )

    response = call_agent_cfg(director, apply_user_instructions(state, prompt))

    return {
        "result": response,
        "iteration": state["iteration"] + 1,
        "messages": [make_message(director["role"], response, "synthesizing")],
    }


def route_after_synthesis(state: DictatorState) -> str:
    """Check if director needs another round."""
    if "NEEDS_MORE_WORK" in state["result"] and state["iteration"] < state["max_iterations"]:
        return "director_plan"
    return END


def build_dictator_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(DictatorState)

    builder.add_node("director_plan", director_plan)
    builder.add_node("workers_execute", workers_execute)
    builder.add_node("director_synthesize", director_synthesize)

    builder.add_edge(START, "director_plan")
    builder.add_edge("director_plan", "workers_execute")
    builder.add_edge("workers_execute", "director_synthesize")
    builder.add_conditional_edges("director_synthesize", route_after_synthesis, {
        "director_plan": "director_plan",
        END: END,
    })

    return builder.compile(**compile_kwargs)
