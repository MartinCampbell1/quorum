"""Map-Reduce mode: split task into chunks, process in parallel, synthesize."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent_cfg, make_message, strip_markdown_fence


class MapReduceState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    chunks: list[str]
    chunk_results: list[dict]
    synthesis: str
    result: str


def plan_chunks(state: MapReduceState) -> dict:
    planner = state["agents"][0]
    num_workers = max(len(state["agents"]) - 2, 1)
    prompt = (
        f"Split this task into {num_workers} independent sub-tasks that can be worked on in parallel.\n\n"
        f"TASK: {state['task']}\n\nRespond with a JSON array of strings.\nReturn ONLY valid JSON."
    )
    response = call_agent_cfg(planner, prompt)
    try:
        chunks = json.loads(strip_markdown_fence(response))
    except json.JSONDecodeError:
        chunks = [state["task"]]
    return {"chunks": chunks, "messages": [make_message(planner["role"], f"Split into {len(chunks)} chunks", "planning")]}


def process_chunks(state: MapReduceState) -> dict:
    workers = state["agents"][1:-1] or [state["agents"][0]]
    results = []
    messages = []
    for i, chunk in enumerate(state["chunks"]):
        worker = workers[i % len(workers)]
        response = call_agent_cfg(worker, f"Process this sub-task:\n{chunk}\n\nOverall context: {state['task']}")
        results.append({"chunk": chunk, "worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, f"chunk_{i}"))
    return {"chunk_results": results, "messages": messages}


def synthesize(state: MapReduceState) -> dict:
    synth = state["agents"][-1]
    chunks_text = "\n\n".join(f"## Chunk: {r['chunk']}\nResult: {r['result']}" for r in state["chunk_results"])
    prompt = (
        f"Synthesize these partial results into one comprehensive answer.\n\n"
        f"ORIGINAL TASK: {state['task']}\n\nPARTIAL RESULTS:\n{chunks_text}\n\nProduce a unified, coherent final answer."
    )
    response = call_agent_cfg(synth, prompt)
    return {"synthesis": response, "result": response, "messages": [make_message(synth["role"], response, "synthesis")]}


def build_map_reduce_graph() -> StateGraph:
    builder = StateGraph(MapReduceState)
    builder.add_node("plan_chunks", plan_chunks)
    builder.add_node("process_chunks", process_chunks)
    builder.add_node("synthesize", synthesize)
    builder.add_edge(START, "plan_chunks")
    builder.add_edge("plan_chunks", "process_chunks")
    builder.add_edge("process_chunks", "synthesize")
    builder.add_edge("synthesize", END)
    return builder.compile()
