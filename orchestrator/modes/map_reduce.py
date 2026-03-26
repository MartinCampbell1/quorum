"""Map-Reduce mode: split task into chunks, process in parallel, synthesize."""

import asyncio
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


def _normalize_chunks(value: object, fallback: str) -> list[str]:
    if not isinstance(value, list):
        return [fallback]
    chunks = [str(item).strip() for item in value if str(item).strip()]
    return chunks or [fallback]


def plan_chunks(state: MapReduceState) -> dict:
    if not state["agents"]:
        return {
            "chunks": [state["task"]],
            "messages": [make_message("system", "No agents available; using the task as a single chunk", "planning")],
        }

    planner = state["agents"][0]
    num_workers = max(len(state["agents"]) - 2, 1)
    prompt = (
        f"Split this task into {num_workers} independent sub-tasks that can be worked on in parallel.\n\n"
        f"TASK: {state['task']}\n\nRespond with a JSON array of strings.\nReturn ONLY valid JSON."
    )
    response = call_agent_cfg(planner, prompt)
    try:
        chunks = _normalize_chunks(json.loads(strip_markdown_fence(response)), state["task"])
    except json.JSONDecodeError:
        chunks = [state["task"]]
    return {"chunks": chunks, "messages": [make_message(planner["role"], f"Split into {len(chunks)} chunks", "planning")]}


async def process_chunks(state: MapReduceState) -> dict:
    workers = state["agents"][1:-1] or state["agents"][:1]
    if not workers:
        return {
            "chunk_results": [],
            "messages": [make_message("system", "No workers available for chunk processing", "chunks")],
        }

    async def run_chunk(i: int, chunk: str) -> tuple[dict, dict]:
        worker = workers[i % len(workers)]
        response = await asyncio.to_thread(
            call_agent_cfg,
            worker,
            f"Process this sub-task:\n{chunk}\n\nOverall context: {state['task']}",
        )
        return (
            {"chunk": chunk, "worker": worker["role"], "result": response},
            make_message(worker["role"], response, f"chunk_{i}"),
        )

    results = await asyncio.gather(*(run_chunk(i, chunk) for i, chunk in enumerate(state["chunks"])))
    chunk_results = [item[0] for item in results]
    messages = [item[1] for item in results]
    return {"chunk_results": chunk_results, "messages": messages}


def synthesize(state: MapReduceState) -> dict:
    if not state["agents"]:
        return {
            "synthesis": state["task"],
            "result": state["task"],
            "messages": [make_message("system", "No synthesizer available; returning the original task", "synthesis")],
        }

    synth = state["agents"][-1]
    if not state["chunk_results"]:
        return {
            "synthesis": state["task"],
            "result": state["task"],
            "messages": [make_message(synth["role"], "No chunk results available; returning the original task", "synthesis")],
        }

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
