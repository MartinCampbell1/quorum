"""Orchestration engine — routes tasks to the correct LangGraph mode."""

import asyncio
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver

from orchestrator.models import store, AgentConfig
from orchestrator.modes.base import make_message
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
    base = {
        "task": task,
        "agents": agents_dicts,
        "messages": [],
        "result": "",
        "user_messages": [],
    }

    if mode == "dictator":
        return {**base, "subtasks": [], "worker_results": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3)}
    if mode == "democracy":
        return {**base, "votes": [], "round": 0,
                "max_rounds": config.get("max_rounds", 3), "majority_position": ""}
    if mode == "debate":
        return {**base, "rounds": [], "current_round": 0,
                "max_rounds": config.get("max_rounds", 3), "verdict": ""}
    if mode == "board":
        return {**base, "positions": [], "vote_round": 0,
                "max_rounds": config.get("max_rounds", 3),
                "consensus_reached": False, "decision": "", "worker_results": []}
    if mode == "map_reduce":
        return {**base, "chunks": [], "chunk_results": [], "synthesis": ""}
    if mode == "creator_critic":
        return {**base, "versions": [], "critiques": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3), "approved": False}
    if mode == "tournament":
        return {**base, "submissions": [], "bracket": [],
                "current_round": 0, "winners": [], "champion": {}}
    raise ValueError(f"Unknown mode: {mode}")


def _build_graph(mode: str, **compile_kwargs):
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
    return builder(**compile_kwargs)


RUNNERS: dict[str, "SessionRunner"] = {}


@dataclass
class SessionRunner:
    session_id: str
    mode: str
    graph: Any
    graph_config: dict[str, Any]
    initial_state: dict[str, Any]
    started_at: float = field(default_factory=time.time)
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_requested: bool = False
    cancel_requested: bool = False
    checkpoint_index: int = 0
    last_graph_message_count: int = 0

    def __post_init__(self) -> None:
        self.resume_event.set()

    def request_pause(self) -> bool:
        session = store.get(self.session_id)
        if not session or session["status"] not in {"running", "pause_requested"}:
            return False
        self.pause_requested = True
        store.update(self.session_id, status="pause_requested")
        return True

    def request_cancel(self) -> bool:
        session = store.get(self.session_id)
        if not session or session["status"] in {"completed", "failed", "cancelled"}:
            return False
        self.cancel_requested = True
        if session["status"] == "paused":
            self.resume_event.set()
        store.update(self.session_id, status="cancel_requested")
        return True

    def inject_instruction(self, content: str) -> int:
        text = content.strip()
        if not text:
            return 0
        queued = store.queue_instruction(self.session_id, text)
        store.append_messages(
            self.session_id,
            [make_message("user", text, "user_instruction")],
        )
        return queued

    def resume(self, content: str = "") -> bool:
        session = store.get(self.session_id)
        if not session or session["status"] not in {"paused", "pause_requested"}:
            return False
        if content.strip():
            self.inject_instruction(content)
        self.resume_event.set()
        store.update(self.session_id, status="running")
        return True

    async def _apply_pending_instructions(self) -> None:
        instructions = store.pop_pending_instructions(self.session_id)
        if not instructions:
            return
        snapshot = await self.graph.aget_state(self.graph_config)
        current = list((snapshot.values or {}).get("user_messages", []))
        await self.graph.aupdate_state(
            self.graph_config,
            {"user_messages": [*current, *instructions]},
        )

    async def _sync_from_snapshot(self, snapshot: Any) -> None:
        values = snapshot.values or {}
        graph_messages = list(values.get("messages", []))
        new_messages = graph_messages[self.last_graph_message_count:]
        if new_messages:
            store.append_messages(self.session_id, new_messages)
        self.last_graph_message_count = len(graph_messages)

        self.checkpoint_index += 1
        next_node = snapshot.next[0] if snapshot.next else None
        checkpoint = {
            "id": f"cp_{self.checkpoint_index}",
            "timestamp": time.time(),
            "next_node": next_node,
            "status": "terminal" if not snapshot.next else "ready",
            "result_preview": str(values.get("result", ""))[:160],
        }
        store.add_checkpoint(self.session_id, checkpoint)
        store.update(
            self.session_id,
            result=values.get("result", ""),
            elapsed_sec=round(time.time() - self.started_at, 2),
            active_node=next_node,
        )

    async def run(self) -> None:
        next_input: Any = self.initial_state
        try:
            while True:
                await self.resume_event.wait()
                if self.cancel_requested:
                    store.update(
                        self.session_id,
                        status="cancelled",
                        elapsed_sec=round(time.time() - self.started_at, 2),
                        active_node=None,
                    )
                    return

                await self._apply_pending_instructions()
                await self.graph.ainvoke(next_input, self.graph_config)
                next_input = None

                snapshot = await self.graph.aget_state(self.graph_config)
                await self._sync_from_snapshot(snapshot)

                if not snapshot.next:
                    values = snapshot.values or {}
                    store.update(
                        self.session_id,
                        status="completed",
                        result=values.get("result", ""),
                        elapsed_sec=round(time.time() - self.started_at, 2),
                        active_node=None,
                    )
                    return

                if self.cancel_requested:
                    store.update(
                        self.session_id,
                        status="cancelled",
                        elapsed_sec=round(time.time() - self.started_at, 2),
                        active_node=None,
                    )
                    return

                if self.pause_requested:
                    self.pause_requested = False
                    self.resume_event.clear()
                    store.update(self.session_id, status="paused")
                else:
                    store.update(self.session_id, status="running")
        except Exception as exc:
            store.update(
                self.session_id,
                status="failed",
                result=f"Error: {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                elapsed_sec=round(time.time() - self.started_at, 2),
                active_node=None,
            )
        finally:
            RUNNERS.pop(self.session_id, None)


async def run(mode: str, task: str, agents: list[AgentConfig] | None = None, config: dict | None = None) -> str:
    config = config or {}
    agents = agents or DEFAULT_AGENTS.get(mode, [])
    session_id = store.create(mode, task, agents, config)

    graph = _build_graph(
        mode,
        checkpointer=MemorySaver(),
        interrupt_after="*",
    )
    graph_config = {"configurable": {"thread_id": session_id}}
    initial_state = _build_initial_state(mode, task, agents, config)
    runner = SessionRunner(
        session_id=session_id,
        mode=mode,
        graph=graph,
        graph_config=graph_config,
        initial_state=initial_state,
    )
    RUNNERS[session_id] = runner
    asyncio.create_task(runner.run())
    return session_id


def get_runner(session_id: str) -> Optional[SessionRunner]:
    return RUNNERS.get(session_id)


def request_pause(session_id: str) -> bool:
    runner = get_runner(session_id)
    return runner.request_pause() if runner else False


def request_resume(session_id: str, content: str = "") -> bool:
    runner = get_runner(session_id)
    return runner.resume(content) if runner else False


def inject_instruction(session_id: str, content: str) -> int:
    runner = get_runner(session_id)
    return runner.inject_instruction(content) if runner else 0


def request_cancel(session_id: str) -> bool:
    runner = get_runner(session_id)
    return runner.request_cancel() if runner else False
