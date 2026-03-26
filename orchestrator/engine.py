"""Orchestration engine — routes tasks to the correct LangGraph mode."""

import asyncio
import time
import traceback

from orchestrator.models import store, AgentConfig
from orchestrator.modes.dictator import build_dictator_graph
from orchestrator.modes.democracy import build_democracy_graph
from orchestrator.modes.debate import build_debate_graph
from orchestrator.modes.board import build_board_graph
from orchestrator.modes.map_reduce import build_map_reduce_graph
from orchestrator.modes.creator_critic import build_creator_critic_graph
from orchestrator.modes.tournament import build_tournament_graph


DEFAULT_AGENTS = {
    "dictator": [
        AgentConfig(role="director", provider="claude", tools=["web_search", "perplexity"]),
        AgentConfig(role="worker_1", provider="codex", tools=["code_exec", "shell_exec", "web_search"]),
        AgentConfig(role="worker_2", provider="gemini", tools=["web_search", "perplexity", "http_request"]),
    ],
    "board": [
        AgentConfig(role="director_1", provider="claude", tools=["web_search", "perplexity"]),
        AgentConfig(role="director_2", provider="codex", tools=["code_exec", "shell_exec"]),
        AgentConfig(role="director_3", provider="gemini", tools=["web_search", "perplexity"]),
    ],
    "democracy": [
        AgentConfig(role="voter_claude", provider="claude", tools=["web_search", "perplexity"]),
        AgentConfig(role="voter_gemini", provider="gemini", tools=["web_search", "perplexity"]),
        AgentConfig(role="voter_codex", provider="codex", tools=["code_exec", "web_search"]),
    ],
    "debate": [
        AgentConfig(role="proponent", provider="claude", tools=["web_search", "perplexity"]),
        AgentConfig(role="opponent", provider="codex", tools=["web_search", "perplexity"]),
        AgentConfig(role="judge", provider="gemini", tools=["perplexity"]),
    ],
    "map_reduce": [
        AgentConfig(role="planner", provider="claude", tools=["web_search", "perplexity"]),
        AgentConfig(role="worker_1", provider="codex", tools=["code_exec", "shell_exec", "web_search"]),
        AgentConfig(role="worker_2", provider="gemini", tools=["web_search", "http_request", "perplexity"]),
        AgentConfig(role="synthesizer", provider="claude", tools=["perplexity"]),
    ],
    "creator_critic": [
        AgentConfig(role="creator", provider="codex", tools=["code_exec", "web_search", "shell_exec"]),
        AgentConfig(role="critic", provider="claude", tools=["web_search", "perplexity"]),
    ],
    "tournament": [
        AgentConfig(role="contestant_1", provider="claude", tools=["web_search", "code_exec"]),
        AgentConfig(role="contestant_2", provider="codex", tools=["code_exec", "shell_exec"]),
        AgentConfig(role="contestant_3", provider="gemini", tools=["web_search", "perplexity"]),
        AgentConfig(role="contestant_4", provider="gemini", tools=["web_search", "http_request"]),
        AgentConfig(role="judge", provider="claude", tools=["perplexity"]),
    ],
}


AVAILABLE_MODES = {
    "dictator": "One director delegates to workers, collects and synthesizes results",
    "board": "Council of 3 directors discuss and vote, deadlocks resolve with the chairman",
    "democracy": "All agents vote equally, majority wins, ties trigger re-vote, final rounds use deterministic fallback",
    "debate": "Proponent vs opponent argue in rounds, judge decides winner",
    "map_reduce": "Split task into chunks, process in parallel, synthesize results",
    "creator_critic": "Creator produces work, critic reviews, iterate until approved",
    "tournament": "All agents compete, bracket elimination, judge picks champion",
}


def _build_initial_state(mode: str, task: str, agents: list[AgentConfig], config: dict) -> dict:
    agents_dicts = [a.model_dump() for a in agents]
    base = {"task": task, "agents": agents_dicts, "messages": [], "result": ""}

    if mode == "dictator":
        return {**base, "subtasks": [], "worker_results": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3)}
    elif mode == "democracy":
        return {**base, "votes": [], "round": 0,
                "max_rounds": config.get("max_rounds", 3), "majority_position": ""}
    elif mode == "debate":
        return {**base, "rounds": [], "current_round": 0,
                "max_rounds": config.get("max_rounds", 3), "verdict": ""}
    elif mode == "board":
        return {**base, "positions": [], "vote_round": 0,
                "max_rounds": config.get("max_rounds", 3),
                "consensus_reached": False, "decision": "", "worker_results": []}
    elif mode == "map_reduce":
        return {**base, "chunks": [], "chunk_results": [], "synthesis": ""}
    elif mode == "creator_critic":
        return {**base, "versions": [], "critiques": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3), "approved": False}
    elif mode == "tournament":
        return {**base, "submissions": [], "bracket": [],
                "current_round": 0, "winners": [], "champion": {}}
    raise ValueError(f"Unknown mode: {mode}")


def _build_graph(mode: str):
    builders = {
        "dictator": build_dictator_graph,
        "democracy": build_democracy_graph,
        "debate": build_debate_graph,
        "board": build_board_graph,
        "map_reduce": build_map_reduce_graph,
        "creator_critic": build_creator_critic_graph,
        "tournament": build_tournament_graph,
    }
    builder = builders.get(mode)
    if not builder:
        raise ValueError(f"Unknown mode: {mode}")
    return builder()


async def run(mode: str, task: str, agents: list[AgentConfig] | None = None, config: dict | None = None) -> str:
    config = config or {}
    agents = agents or DEFAULT_AGENTS.get(mode, [])
    session_id = store.create(mode, task, agents, config)

    async def _execute():
        t0 = time.time()
        try:
            graph = _build_graph(mode)
            initial_state = _build_initial_state(mode, task, agents, config)
            final_state = await graph.ainvoke(initial_state)
            store.update(session_id,
                status="completed",
                result=final_state.get("result", ""),
                elapsed_sec=round(time.time() - t0, 2),
            )
            store.append_messages(session_id, final_state.get("messages", []))
        except Exception as e:
            store.update(session_id,
                status="failed",
                result=f"Error: {type(e).__name__}: {e}\n{traceback.format_exc()}",
                elapsed_sec=round(time.time() - t0, 2),
            )

    asyncio.create_task(_execute())
    return session_id
