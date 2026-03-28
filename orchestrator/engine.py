"""Orchestration engine — routes tasks to the correct LangGraph mode."""

import asyncio
import copy
import os
import pickle
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver

from orchestrator.models import (
    AgentConfig,
    build_provider_capabilities_snapshot,
    collect_attached_tool_ids,
    store,
)
from orchestrator.modes.base import make_message
from orchestrator.modes.dictator import build_dictator_graph
from orchestrator.modes.democracy import build_democracy_graph
from orchestrator.modes.debate import build_debate_graph
from orchestrator.modes.board import build_board_graph
from orchestrator.modes.map_reduce import build_map_reduce_graph
from orchestrator.modes.creator_critic import build_creator_critic_graph
from orchestrator.modes.tournament import build_tournament_graph, build_tournament_match_graph


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
    "tournament": "Projects debate head-to-head through a bracket, judge picks who advances",
    "tournament_match": "Internal head-to-head tournament match executor",
}


def _build_initial_state(
    mode: str,
    task: str,
    agents: list[AgentConfig],
    config: dict,
    session_id: str,
    workspace_paths: list[str],
    attached_tool_ids: list[str],
) -> dict:
    session_provider_pool = list(dict.fromkeys(str(agent.provider) for agent in agents if str(agent.provider).strip()))
    agents_dicts = [
        {
            **agent.model_dump(),
            "workspace_paths": list(dict.fromkeys([*list(workspace_paths), *list(agent.workspace_paths)])),
            "workdir": str(config.get("workdir", "")) or None,
            "session_id": session_id,
            "session_provider_pool": list(session_provider_pool),
        }
        for agent in agents
    ]
    base = {
        "session_id": session_id,
        "mode": mode,
        "task": task,
        "agents": agents_dicts,
        "messages": [],
        "result": "",
        "user_messages": [],
        "status": "running",
        "config": dict(config),
        "created_at": time.time(),
        "workspace_paths": list(workspace_paths),
        "attached_tool_ids": list(attached_tool_ids),
    }

    if mode == "dictator":
        return {**base, "subtasks": [], "worker_results": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3)}
    if mode == "democracy":
        return {**base, "votes": [], "round": 0,
                "max_rounds": config.get("max_rounds", 3), "majority_position": ""}
    if mode == "debate":
        return {**base, "rounds": [], "current_round": 0,
                "max_rounds": config.get("max_rounds", 3), "verdict": "", "judge_action": ""}
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
                "current_round": 0, "current_match_index": 0, "current_match_round": 0,
                "current_match": {}, "max_rounds": config.get("max_rounds", 5),
                "winners": [], "champion": {}, "match_history": [], "match_verdict": "",
                "judge_action": "", "match_winner": "", "advance_target": "",
                "current_stage_label": "", "parallel_stage_children": [], "parallel_stage_group_id": ""}
    if mode == "tournament_match":
        return {**base,
                "current_round": int(config.get("tournament_round", 1) or 1),
                "current_stage_label": str(config.get("parallel_stage", "") or ""),
                "current_match_index": max(int(config.get("match_index", 1) or 1) - 1, 0),
                "current_match_round": 0,
                "current_match": {},
                "max_rounds": config.get("max_rounds", 5),
                "match_history": [], "match_verdict": "", "judge_action": "",
                "match_winner": "", "advance_target": "", "champion": {},
                "parallel_stage_children": [], "parallel_stage_group_id": ""}
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
        "tournament_match": build_tournament_match_graph,
    }
    builder = builders.get(mode)
    if not builder:
        raise ValueError(f"Unknown mode: {mode}")
    return builder(**compile_kwargs)


RUNNERS: dict[str, "SessionRunner"] = {}
CHECKPOINT_SAVERS: dict[str, MemorySaver] = {}
TRANSIENT_RUNTIME_STATUSES = {"running", "pause_requested", "cancel_requested"}


def _checkpoint_runtime_limit() -> int:
    raw_value = str(os.getenv("MULTI_AGENT_MAX_CHECKPOINT_RUNTIMES", "16")).strip()
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return 16


MAX_CHECKPOINT_RUNTIMES = _checkpoint_runtime_limit()


def _prune_checkpoint_savers(limit: int = MAX_CHECKPOINT_RUNTIMES) -> None:
    if limit < 1:
        limit = 1
    keep_ids = {item["id"] for item in store.list_recent(limit)}
    keep_ids.update(RUNNERS.keys())
    for session_id in list(CHECKPOINT_SAVERS.keys()):
        if session_id not in keep_ids:
            CHECKPOINT_SAVERS.pop(session_id, None)


def _plain_checkpoint_value(value: Any) -> Any:
    if isinstance(value, defaultdict):
        return {key: _plain_checkpoint_value(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: _plain_checkpoint_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_checkpoint_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_plain_checkpoint_value(item) for item in value)
    return copy.deepcopy(value)


def _persist_checkpointer_state(session_id: str, saver: MemorySaver) -> None:
    payload = {
        "version": 1,
        "session_id": session_id,
        "storage": _plain_checkpoint_value(saver.storage.get(session_id, {})),
        "writes": {
            key: _plain_checkpoint_value(value)
            for key, value in saver.writes.items()
            if key[0] == session_id
        },
        "blobs": {
            key: _plain_checkpoint_value(value)
            for key, value in saver.blobs.items()
            if key[0] == session_id
        },
    }
    path = store.checkpoint_runtime_path(session_id)
    temp_path = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    with temp_path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temp_path.replace(path)


def _load_persisted_checkpointer_state(session_id: str) -> MemorySaver | None:
    path = store.checkpoint_runtime_path(session_id)
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    except Exception:
        path.unlink(missing_ok=True)
        return None

    if str(payload.get("session_id", "")).strip() != session_id:
        path.unlink(missing_ok=True)
        return None

    saver = MemorySaver()
    saver.storage.pop(session_id, None)
    storage_bucket = defaultdict(dict)
    for namespace, values in dict(payload.get("storage", {})).items():
        storage_bucket[namespace] = dict(values)
    if storage_bucket:
        saver.storage[session_id] = storage_bucket
    saver.writes.update(
        {
            tuple(key): dict(value)
            for key, value in dict(payload.get("writes", {})).items()
        }
    )
    saver.blobs.update(
        {
            tuple(key): value
            for key, value in dict(payload.get("blobs", {})).items()
        }
    )
    return saver


@dataclass
class SessionRunner:
    session_id: str
    mode: str
    graph: Any
    graph_config: dict[str, Any]
    initial_state: dict[str, Any] | None
    checkpointer: MemorySaver
    started_at: float = field(default_factory=time.time)
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_requested: bool = False
    cancel_requested: bool = False
    checkpoint_index: int = 0
    last_graph_message_count: int = 0
    resume_from_checkpoint_id: str | None = None
    last_vote_count: int = 0
    last_board_position_count: int = 0
    last_chunk_result_count: int = 0
    last_round_started: int = 0
    last_round_completed: int = 0

    def __post_init__(self) -> None:
        self.resume_event.set()

    def _emit_event(self, event_type: str, title: str, detail: str = "", **extra: object) -> None:
        store.append_event(self.session_id, event_type, title, detail, **extra)

    def request_pause(self) -> bool:
        session = store.get(self.session_id)
        if not session or session["status"] not in {"running", "pause_requested"}:
            return False
        self.pause_requested = True
        store.update(self.session_id, status="pause_requested")
        self._emit_event(
            "pause_requested",
            "Пауза запрошена",
            "Сессия остановится после завершения текущего узла.",
            status="pause_requested",
        )
        return True

    def request_cancel(self) -> bool:
        session = store.get(self.session_id)
        if not session or session["status"] in {"completed", "failed", "cancelled"}:
            return False
        self.cancel_requested = True
        if session["status"] == "paused":
            self.resume_event.set()
        store.update(self.session_id, status="cancel_requested")
        self._emit_event(
            "cancel_requested",
            "Остановка запрошена",
            "Сессия завершится на ближайшем безопасном checkpoint.",
            status="cancel_requested",
        )
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
        self._emit_event(
            "instruction_queued",
            "Инструкция добавлена",
            text,
            agent_id="user",
            phase="user_instruction",
            pending_instructions=queued,
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
        self._emit_event(
            "run_resumed",
            "Сессия продолжена",
            "Выполнение возобновлено с текущего checkpoint.",
            status="running",
        )
        return True

    async def _apply_pending_instructions(self) -> None:
        instructions = store.pop_pending_instructions(self.session_id)
        if not instructions:
            return
        snapshot = await self.graph.aget_state(self.graph_config)
        current = list((snapshot.values or {}).get("user_messages", []))
        self.graph_config = await self.graph.aupdate_state(
            self.graph_config,
            {"user_messages": [*current, *instructions]},
        )
        self._emit_event(
            "instruction_applied",
            "Инструкция применена",
            instructions[-1],
            applied_count=len(instructions),
        )

    async def _sync_from_snapshot(self, snapshot: Any) -> None:
        # Tool bridge events are written during the just-finished graph node; ingest them now
        # so the canonical session timeline is up to date before the next checkpoint is persisted.
        store.ingest_runtime_events(self.session_id)
        values = snapshot.values or {}
        graph_messages = list(values.get("messages", []))
        new_messages = graph_messages[self.last_graph_message_count:]
        if new_messages:
            store.append_messages(self.session_id, new_messages)
            for message in new_messages:
                self._emit_event(
                    "agent_message",
                    message.get("agent_id", "agent"),
                    message.get("content", ""),
                    agent_id=message.get("agent_id"),
                    phase=message.get("phase"),
                )
        self.last_graph_message_count = len(graph_messages)
        self._emit_mode_progress_events(values, snapshot.next[0] if snapshot.next else None)

        self.checkpoint_index += 1
        next_node = snapshot.next[0] if snapshot.next else None
        checkpoint = {
            "id": f"cp_{self.checkpoint_index}",
            "timestamp": time.time(),
            "next_node": next_node,
            "status": "terminal" if not snapshot.next else "ready",
            "result_preview": str(values.get("result", ""))[:160],
            "graph_checkpoint_id": ((snapshot.config or {}).get("configurable") or {}).get("checkpoint_id"),
        }
        store.add_checkpoint(self.session_id, checkpoint)
        checkpoint_detail = (
            f"Следующий узел: {next_node}" if next_node else "Граф дошёл до terminal state."
        )
        self._emit_event(
            "checkpoint_created",
            f"Checkpoint {checkpoint['id']}",
            checkpoint_detail,
            checkpoint_id=checkpoint["id"],
            next_node=next_node,
            status=checkpoint["status"],
        )
        if self.checkpointer is not None:
            _persist_checkpointer_state(self.session_id, self.checkpointer)
        store.update(
            self.session_id,
            result=values.get("result", ""),
            elapsed_sec=round(time.time() - self.started_at, 2),
            active_node=next_node,
            config=values.get("config", {}),
        )

    def _emit_mode_progress_events(self, values: dict[str, Any], next_node: str | None) -> None:
        if self.mode == "democracy":
            votes = list(values.get("votes", []) or [])
            for vote in votes[self.last_vote_count:]:
                self._emit_event(
                    "vote_recorded",
                    "Голос зафиксирован",
                    str(vote.get("position", "")).strip(),
                    agent_id=str(vote.get("agent_id", "")).strip() or None,
                    round=values.get("round", 0),
                )
            self.last_vote_count = len(votes)

            round_number = int(values.get("round", 0) or 0)
            if round_number > self.last_round_started and next_node == "tally_votes":
                self.last_round_started = round_number
                self._emit_event(
                    "round_started",
                    f"Раунд {round_number}",
                    "Голоса собраны, начинается подсчёт.",
                    round=round_number,
                )
            if round_number > self.last_round_completed and next_node in {None, "collect_votes", "force_decision"}:
                self.last_round_completed = round_number
                detail = str(values.get("majority_position") or values.get("result") or "Подсчёт завершён.")
                self._emit_event(
                    "round_completed",
                    f"Раунд {round_number} завершён",
                    detail[:240],
                    round=round_number,
                )
            return

        if self.mode == "board":
            positions = list(values.get("positions", []) or [])
            for position in positions[self.last_board_position_count:]:
                self._emit_event(
                    "vote_recorded",
                    "Позиция директора",
                    str(position.get("position", "")).strip(),
                    agent_id=str(position.get("director", "")).strip() or None,
                    round=values.get("vote_round", 0),
                )
            self.last_board_position_count = len(positions)

            round_number = int(values.get("vote_round", 0) or 0)
            if round_number > self.last_round_started and next_node == "check_consensus":
                self.last_round_started = round_number
                self._emit_event(
                    "round_started",
                    f"Board round {round_number}",
                    "Собраны позиции директоров, начинается проверка консенсуса.",
                    round=round_number,
                )
            if round_number > self.last_round_completed and next_node in {None, "directors_analyze", "chairman_decides", "delegate_to_workers", "finalize"}:
                self.last_round_completed = round_number
                detail = str(values.get("decision") or values.get("result") or "Раунд совета завершён.")
                self._emit_event(
                    "round_completed",
                    f"Board round {round_number} завершён",
                    detail[:240],
                    round=round_number,
                )
            return

        if self.mode in {"debate", "tournament_match"}:
            round_key = "current_match_round" if self.mode == "tournament_match" else "current_round"
            round_number = int(values.get(round_key, 0) or 0)
            judge_node = "judge_match" if self.mode == "tournament_match" else "judge_decides"
            restart_node = "contestant_a_argues" if self.mode == "tournament_match" else "proponent_argues"
            if round_number > self.last_round_started and next_node == judge_node:
                self.last_round_started = round_number
                self._emit_event(
                    "round_started",
                    f"Debate round {round_number}",
                    "Аргументы обеих сторон собраны, слово за судьёй.",
                    round=round_number,
                )
            if round_number > self.last_round_completed and next_node in {None, restart_node}:
                self.last_round_completed = round_number
                detail = str(values.get("verdict") or values.get("result") or "Раунд дебатов завершён.")
                self._emit_event(
                    "round_completed",
                    f"Debate round {round_number} завершён",
                    detail[:240],
                    round=round_number,
                )
            return

        if self.mode == "map_reduce":
            chunk_results = list(values.get("chunk_results", []) or [])
            for chunk_result in chunk_results[self.last_chunk_result_count:]:
                self._emit_event(
                    "chunk_completed",
                    "Chunk processed",
                    str(chunk_result.get("chunk", "")).strip()[:240],
                    agent_id=str(chunk_result.get("worker", "")).strip() or None,
                )
            self.last_chunk_result_count = len(chunk_results)

    async def run(self) -> None:
        next_input: Any = self.initial_state
        try:
            session = store.get(self.session_id) or {}
            if self.resume_from_checkpoint_id:
                self._emit_event(
                    "branch_started",
                    "Создана новая ветка",
                    f"Продолжение с checkpoint {self.resume_from_checkpoint_id}.",
                    mode=self.mode,
                    status="running",
                    forked_from=session.get("forked_from"),
                    checkpoint_id=self.resume_from_checkpoint_id,
                )
            else:
                self._emit_event(
                    "run_started",
                    "Сессия запущена",
                    (self.initial_state or {}).get("task", ""),
                    mode=self.mode,
                    status="running",
                )
            while True:
                await self.resume_event.wait()
                if self.cancel_requested:
                    store.update(
                        self.session_id,
                        status="cancelled",
                        elapsed_sec=round(time.time() - self.started_at, 2),
                        active_node=None,
                    )
                    self._emit_event(
                        "run_cancelled",
                        "Сессия остановлена",
                        "Выполнение было остановлено пользователем.",
                        status="cancelled",
                    )
                    return

                await self._apply_pending_instructions()
                await self.graph.ainvoke(next_input, self.graph_config)
                if ((self.graph_config.get("configurable") or {}).get("checkpoint_id")):
                    self.graph_config = {"configurable": {"thread_id": self.session_id}}
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
                    self._emit_event(
                        "run_completed",
                        "Сессия завершена",
                        str(values.get("result", ""))[:240],
                        status="completed",
                    )
                    return

                if self.cancel_requested:
                    store.update(
                        self.session_id,
                        status="cancelled",
                        elapsed_sec=round(time.time() - self.started_at, 2),
                        active_node=None,
                    )
                    self._emit_event(
                        "run_cancelled",
                        "Сессия остановлена",
                        "Выполнение было остановлено пользователем.",
                        status="cancelled",
                    )
                    return

                if self.pause_requested:
                    self.pause_requested = False
                    self.resume_event.clear()
                    store.update(self.session_id, status="paused")
                    self._emit_event(
                        "run_paused",
                        "Сессия на паузе",
                        "Checkpoint достигнут, можно дать новую инструкцию.",
                        status="paused",
                        checkpoint_id=store.get(self.session_id).get("current_checkpoint_id"),
                    )
                else:
                    store.update(self.session_id, status="running")
        except Exception as exc:
            failed_agent = getattr(exc, "agent_role", None)
            failed_provider = getattr(exc, "provider", None)
            gateway_error = getattr(exc, "gateway_error", None)
            if failed_agent or failed_provider:
                label = failed_agent or failed_provider or "agent"
                detail = str(gateway_error or exc)
                self._emit_event(
                    "agent_failed",
                    f"Агент {label} не завершил шаг",
                    detail[:240],
                    agent_id=failed_agent,
                    provider=failed_provider,
                    status="failed",
                )
            failure_detail = str(gateway_error or exc)
            if failed_agent or failed_provider or gateway_error:
                result_text = f"Error: {type(exc).__name__}: {failure_detail}"
            else:
                result_text = f"Error: {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            store.update(
                self.session_id,
                status="failed",
                result=result_text,
                elapsed_sec=round(time.time() - self.started_at, 2),
                active_node=None,
            )
            self._emit_event(
                "run_failed",
                f"Ошибка: {type(exc).__name__}",
                failure_detail,
                status="failed",
            )
        finally:
            RUNNERS.pop(self.session_id, None)
            _prune_checkpoint_savers()


async def run(
    mode: str,
    task: str,
    agents: list[AgentConfig] | None = None,
    config: dict | None = None,
    scenario_id: str | None = None,
    workspace_preset_ids: list[str] | None = None,
    workspace_paths: list[str] | None = None,
    attached_tool_ids: list[str] | None = None,
    parallel_parent_id: str | None = None,
    parallel_group_id: str | None = None,
    parallel_slot_key: str | None = None,
    parallel_stage: str | None = None,
    parallel_label: str | None = None,
) -> str:
    config = config or {}
    agents = agents or DEFAULT_AGENTS.get(mode, [])
    resolved_attached_tools = collect_attached_tool_ids(agents, attached_tool_ids)
    provider_capabilities_snapshot = build_provider_capabilities_snapshot(agents)
    session_id = store.create(
        mode,
        task,
        agents,
        config,
        scenario_id=scenario_id,
        workspace_preset_ids=workspace_preset_ids,
        workspace_paths=workspace_paths,
        attached_tool_ids=resolved_attached_tools,
        provider_capabilities_snapshot=provider_capabilities_snapshot,
        parallel_parent_id=parallel_parent_id,
        parallel_group_id=parallel_group_id,
        parallel_slot_key=parallel_slot_key,
        parallel_stage=parallel_stage,
        parallel_label=parallel_label,
    )

    saver = MemorySaver()
    graph = _build_graph(
        mode,
        checkpointer=saver,
        interrupt_after="*",
    )
    graph_config = {"configurable": {"thread_id": session_id}}
    initial_state = _build_initial_state(
        mode,
        task,
        agents,
        config,
        session_id=session_id,
        workspace_paths=list(workspace_paths or []),
        attached_tool_ids=resolved_attached_tools,
    )
    runner = SessionRunner(
        session_id=session_id,
        mode=mode,
        graph=graph,
        graph_config=graph_config,
        initial_state=initial_state,
        checkpointer=saver,
    )
    RUNNERS[session_id] = runner
    CHECKPOINT_SAVERS[session_id] = saver
    _prune_checkpoint_savers()
    asyncio.create_task(runner.run())
    return session_id


def get_runner(session_id: str) -> Optional[SessionRunner]:
    return RUNNERS.get(session_id)


def has_live_runtime(session_id: str) -> bool:
    return session_id in RUNNERS


def has_checkpoint_runtime(session_id: str) -> bool:
    return session_id in CHECKPOINT_SAVERS or store.checkpoint_runtime_path(session_id).exists()


def reconcile_orphaned_sessions() -> int:
    recovered = 0
    for session in store.list_by_statuses(sorted(TRANSIENT_RUNTIME_STATUSES)):
        status = session["status"]
        new_status = "cancelled" if status == "cancel_requested" else "failed"
        detail = (
            "Backend restarted before cancellation completed; session was finalized as cancelled."
            if status == "cancel_requested"
            else "Backend restarted while the in-memory runtime was active; session was finalized because execution state was lost."
        )
        result = (
            "Execution cancelled after backend restart."
            if new_status == "cancelled"
            else "Execution interrupted by backend restart. Restart the run from scratch or create a new session."
        )
        store.update(
            session["id"],
            status=new_status,
            result=result,
            active_node=None,
        )
        store.append_event(
            session["id"],
            "runtime_recovered",
            "Состояние восстановлено после рестарта backend",
            detail,
            status=new_status,
            checkpoint_id=session.get("current_checkpoint_id"),
        )
        recovered += 1
    return recovered


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


def _copy_checkpointer_state(
    source_saver: MemorySaver,
    source_thread_id: str,
    target_saver: MemorySaver,
    target_thread_id: str,
) -> None:
    if source_thread_id in source_saver.storage:
        target_saver.storage[target_thread_id] = copy.deepcopy(source_saver.storage[source_thread_id])

    for key, value in list(source_saver.writes.items()):
        if key[0] == source_thread_id:
            target_saver.writes[(target_thread_id, key[1], key[2])] = copy.deepcopy(value)

    for key, value in list(source_saver.blobs.items()):
        if key[0] == source_thread_id:
            target_saver.blobs[(target_thread_id, key[1], key[2], key[3])] = copy.deepcopy(value)


def _resolve_checkpoint(session: dict, checkpoint_id: str | None) -> dict | None:
    checkpoints = session.get("checkpoints", [])
    target_id = checkpoint_id or session.get("current_checkpoint_id")
    if not target_id:
        return None
    for checkpoint in checkpoints:
        if checkpoint.get("id") == target_id or checkpoint.get("graph_checkpoint_id") == target_id:
            return checkpoint
    return None


def fork_from_checkpoint(session_id: str, checkpoint_id: str = "", content: str = "") -> str | None:
    session = store.get(session_id)
    if not session:
        return None

    checkpoint = _resolve_checkpoint(session, checkpoint_id or None)
    graph_checkpoint_id = (checkpoint or {}).get("graph_checkpoint_id")
    if not checkpoint or not graph_checkpoint_id:
        return None

    source_saver = CHECKPOINT_SAVERS.get(session_id) or _load_persisted_checkpointer_state(session_id)
    if not source_saver:
        return None

    agents = [AgentConfig(**agent) for agent in session.get("agents", [])]
    new_session_id = store.create(
        session["mode"],
        session["task"],
        agents,
        session.get("config", {}),
        scenario_id=session.get("active_scenario"),
        forked_from=session_id,
        forked_checkpoint_id=checkpoint.get("id"),
        workspace_preset_ids=session.get("workspace_preset_ids", []),
        workspace_paths=session.get("workspace_paths", []),
        attached_tool_ids=session.get("attached_tool_ids", []),
        provider_capabilities_snapshot=session.get("provider_capabilities_snapshot", {}),
    )

    saver = MemorySaver()
    _copy_checkpointer_state(source_saver, session_id, saver, new_session_id)
    graph = _build_graph(
        session["mode"],
        checkpointer=saver,
        interrupt_after="*",
    )
    graph_config = {
        "configurable": {
            "thread_id": new_session_id,
            "checkpoint_ns": "",
            "checkpoint_id": graph_checkpoint_id,
        }
    }
    runner = SessionRunner(
        session_id=new_session_id,
        mode=session["mode"],
        graph=graph,
        graph_config=graph_config,
        initial_state=None,
        checkpointer=saver,
        resume_from_checkpoint_id=checkpoint.get("id"),
    )
    if content.strip():
        runner.inject_instruction(content)

    RUNNERS[new_session_id] = runner
    CHECKPOINT_SAVERS[new_session_id] = saver
    _prune_checkpoint_savers()
    asyncio.create_task(runner.run())
    return new_session_id
