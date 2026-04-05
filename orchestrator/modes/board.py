"""Board mode: council of directors discuss, vote, then delegate."""

from collections import Counter
import json
import operator
import os
import re
import threading
import time
from typing import Annotated, Any

from typing_extensions import TypedDict
from langgraph.graph import END, START, StateGraph

from orchestrator.debate.moderators import review_unanimous_consensus
from orchestrator.debate.protocols import build_protocol_telemetry, resolve_protocol_for_mode
from orchestrator.models import store
from orchestrator.modes.base import (
    _provider_attempt_order,
    AgentStepError,
    apply_user_instructions,
    call_agent_cfg,
    make_message,
    strip_markdown_fence,
)


BOARD_DIRECTOR_TIMEOUT_SEC = int(os.getenv("MULTI_AGENT_BOARD_DIRECTOR_TIMEOUT_SEC", "240"))
BOARD_DIRECTOR_STALL_TIMEOUT_SEC = int(os.getenv("MULTI_AGENT_BOARD_DIRECTOR_STALL_TIMEOUT_SEC", "90"))
BOARD_PROGRESS_HEARTBEAT_SEC = int(os.getenv("MULTI_AGENT_BOARD_HEARTBEAT_SEC", "60"))
BOARD_MAX_INVALID_ATTEMPTS = int(os.getenv("MULTI_AGENT_BOARD_INVALID_ATTEMPTS", "2"))
META_POSITION_RE = re.compile(
    r"\b(i need|need .*permission|need search|need tool|need more context|let me analyze first|can't access|cannot access)\b",
    re.IGNORECASE,
)
NON_WORD_RE = re.compile(r"[^a-z0-9]+")


class BoardState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    config: dict
    positions: list[dict]
    vote_round: int
    max_rounds: int
    consensus_reached: bool
    decision: str
    protocol_name: str
    protocol_telemetry: dict
    scrutiny_requested: bool
    scrutiny_passed: bool
    worker_results: list[dict]
    result: str


def _protocol(state: BoardState):
    return resolve_protocol_for_mode("board", state.get("config") or {})


def _normalize_position(position: str) -> str:
    return " ".join(position.split()).strip().lower()


def _normalize_decision_key(value: str) -> str:
    normalized = NON_WORD_RE.sub("_", str(value or "").strip().lower()).strip("_")
    return normalized.upper()


def _derive_decision_key(position: str, reasoning: str = "") -> str:
    text = f"{position}\n{reasoning}".lower()
    if "graphrag" in text and "autopilot" in text:
        if any(phrase in text for phrase in ("graphrag first", "усиливать первым graphrag", "сначала graph", "продавать graphrag")):
            return "GRAPH_RAG_FIRST"
        if any(phrase in text for phrase in ("autopilot first", "автопилот первым", "усиливать первым autopilot")):
            return "AUTOPILOT_FIRST"
    if "graphrag" in text and any(
        phrase in text for phrase in ("paid diagnostic", "paid pilot", "service-led", "service led", "intelligence layer", "retainer")
    ):
        return "GRAPH_RAG_SERVICE_FIRST"
    if "autopilot" in text and any(
        phrase in text for phrase in ("internal engine", "internal execution", "dogfooding", "design partners")
    ):
        return "AUTOPILOT_INTERNAL_FIRST"
    if any(phrase in text for phrase in ("do not pivot", "не пивотить", "no pivot")):
        return "NO_PIVOT"
    normalized_position = _normalize_position(position)
    first_sentence = normalized_position.split(".", 1)[0]
    return _normalize_decision_key(first_sentence[:80] or normalized_position[:80] or "BOARD_DECISION")


def _is_meta_position(position: str, reasoning: str = "") -> bool:
    combined = f"{position}\n{reasoning}".strip()
    if not combined:
        return True
    return bool(META_POSITION_RE.search(combined))


def _normalize_action_items(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _format_board_message(pos: dict) -> str:
    lines = [f"Position: {pos['position']}"]
    reasoning = str(pos.get("reasoning", "")).strip()
    if reasoning:
        lines.extend(["", f"Reasoning: {reasoning}"])
    action_items = _normalize_action_items(pos.get("action_items"))
    if action_items:
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in action_items)
    decision_key = str(pos.get("decision_key", "")).strip()
    if decision_key:
        lines.extend(["", f"Decision key: {decision_key}"])
    return "\n".join(lines).strip()


def _parse_board_response(response: str) -> dict[str, Any]:
    parsed = json.loads(strip_markdown_fence(response))
    if not isinstance(parsed, dict):
        raise ValueError("board response must be a JSON object")
    position = str(parsed.get("position", "")).strip()
    reasoning = str(parsed.get("reasoning", "")).strip()
    action_items = _normalize_action_items(parsed.get("action_items"))
    decision_key = _normalize_decision_key(parsed.get("decision_key", "")) or _derive_decision_key(position, reasoning)
    if not position:
        raise ValueError("board response missing position")
    if _is_meta_position(position, reasoning):
        raise ValueError("board response is meta instead of a concrete recommendation")
    if not decision_key:
        raise ValueError("board response missing decision_key")
    return {
        "position": position,
        "reasoning": reasoning,
        "action_items": action_items,
        "decision_key": decision_key,
    }


def _provider_sequence(agent: dict) -> list[str]:
    session_pool = [str(provider) for provider in list(agent.get("session_provider_pool") or []) if str(provider).strip()]
    return _provider_attempt_order(str(agent.get("provider", "")), session_pool)


def _director_prompt(state: BoardState, previous: str, attempt_number: int) -> str:
    protocol = _protocol(state)
    retry_note = ""
    if attempt_number > 1:
        retry_note = (
            "\n\nPrevious answer was rejected because it was meta, malformed, or missing a stable decision key. "
            "Do not ask for permissions or more context. Give the best concrete recommendation from the current evidence."
        )
    return (
        f"You are on a board of directors operating under the {protocol.display_name} protocol. Analyze this task and give your position.\n\n"
        f"TASK: {state['task']}\n{previous}{retry_note}\n\n"
        "Respond ONLY with valid JSON using this schema:\n"
        "{"
        "\"decision_key\": \"UPPER_SNAKE_CASE stable key for the core recommendation\", "
        "\"position\": \"1-3 sentences with the recommendation\", "
        "\"reasoning\": \"concise explanation with the strongest rationale\", "
        "\"action_items\": [\"concrete next steps\"]"
        "}\n\n"
        "Rules:\n"
        "- decision_key must capture the recommendation, not the explanation.\n"
        "- Do not ask for permissions, more research, or more context.\n"
        "- Use the attached repo context and available tools as-is.\n"
        "- If evidence is incomplete, state assumptions inside reasoning but still choose a concrete direction."
    )


def _call_director_with_progress(agent: dict, prompt: str, round_number: int, attempt_number: int) -> str:
    session_id = str(agent.get("session_id", "")).strip()
    role = str(agent.get("role", "director") or "director")
    provider = str(agent.get("provider", "unknown") or "unknown")
    started_at = time.time()
    if session_id:
        store.append_event(
            session_id,
            "director_started",
            f"{role} started",
            f"Board round {round_number}: waiting on {provider}.",
            agent_id=role,
            phase=f"board_round_{round_number}",
            provider=provider,
            round=round_number,
            attempt=attempt_number,
        )

    result: dict[str, Any] = {"response": None, "error": None}

    def _runner() -> None:
        try:
            result["response"] = call_agent_cfg(agent, prompt)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    next_heartbeat_at = started_at + BOARD_PROGRESS_HEARTBEAT_SEC
    while thread.is_alive():
        thread.join(timeout=0.25)
        now = time.time()
        if session_id and now >= next_heartbeat_at:
            waited = int(now - started_at)
            store.append_event(
                session_id,
                "director_waiting",
                f"Waiting on {role}",
                f"Waiting on {provider} for {waited}s.",
                agent_id=role,
                phase=f"board_round_{round_number}",
                provider=provider,
                round=round_number,
                elapsed_sec=waited,
                attempt=attempt_number,
            )
            next_heartbeat_at += BOARD_PROGRESS_HEARTBEAT_SEC

    if result["error"] is not None:
        raise result["error"]

    response = str(result.get("response") or "")
    if session_id:
        elapsed = round(time.time() - started_at, 2)
        store.append_event(
            session_id,
            "director_completed",
            f"{role} completed",
            f"{provider} returned a board position in {elapsed}s.",
            agent_id=role,
            phase=f"board_round_{round_number}",
            provider=provider,
            round=round_number,
            elapsed_sec=elapsed,
            attempt=attempt_number,
        )
    return response


def _summarize_positions(positions: list[dict]) -> tuple[Counter, dict[str, str], dict[str, int]]:
    counts: Counter = Counter()
    representatives: dict[str, str] = {}
    first_seen: dict[str, int] = {}

    for idx, position in enumerate(positions):
        raw = str(position.get("position", "")).strip()
        if not raw:
            continue
        key = _normalize_decision_key(position.get("decision_key", "")) or _normalize_position(raw)
        counts[key] += 1
        representatives.setdefault(key, raw)
        first_seen.setdefault(key, idx)

    return counts, representatives, first_seen


def directors_analyze(state: BoardState) -> dict:
    directors = state["agents"][:3]
    positions: list[dict] = []
    messages: list[dict] = []
    previous = ""
    if not directors:
        return {
            "positions": [],
            "vote_round": state["vote_round"] + 1,
            "messages": [make_message("system", "No directors available", f"board_round_{state['vote_round'] + 1}")],
        }
    if state["positions"]:
        previous = "\n\nPrevious round positions (no consensus):\n" + "\n".join(
            f"- {p['director']}: {p['position']}" for p in state["positions"]
        )

    round_number = state["vote_round"] + 1
    for director_config in directors:
        provider_order = _provider_sequence(director_config)
        parsed_position: dict[str, Any] | None = None
        last_error: Exception | None = None

        for attempt_index, provider in enumerate(provider_order[:BOARD_MAX_INVALID_ATTEMPTS], start=1):
            director = {
                **director_config,
                "provider": provider,
                "timeout": int(director_config.get("timeout") or BOARD_DIRECTOR_TIMEOUT_SEC),
                "stall_timeout": int(director_config.get("stall_timeout") or BOARD_DIRECTOR_STALL_TIMEOUT_SEC),
            }
            prompt = _director_prompt(state, previous, attempt_index)
            response = _call_director_with_progress(
                director,
                apply_user_instructions(state, prompt),
                round_number,
                attempt_index,
            )
            try:
                parsed_position = _parse_board_response(response)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                session_id = str(director.get("session_id", "")).strip()
                if session_id:
                    store.append_event(
                        session_id,
                        "director_invalid",
                        f"{director['role']} invalid reply",
                        str(exc),
                        agent_id=str(director["role"]),
                        phase=f"board_round_{round_number}",
                        provider=provider,
                        round=round_number,
                        attempt=attempt_index,
                    )
                if attempt_index >= BOARD_MAX_INVALID_ATTEMPTS:
                    raise AgentStepError(director, "board response invalid", str(exc)) from exc

        if parsed_position is None:
            raise AgentStepError(director_config, "board response invalid", str(last_error or "missing board position"))

        parsed_position["director"] = director_config["role"]
        positions.append(parsed_position)
        messages.append(make_message(director_config["role"], _format_board_message(parsed_position), f"board_round_{round_number}"))

    return {"positions": positions, "vote_round": round_number, "messages": messages}


def check_consensus(state: BoardState) -> dict:
    protocol = _protocol(state)
    counts, representatives, first_seen = _summarize_positions(state["positions"])
    if not counts:
        return {
            "consensus_reached": False,
            "decision": "",
            "scrutiny_requested": False,
            "protocol_name": protocol.name,
            "messages": [make_message("system", "No board positions to compare", "consensus_check", protocol_name=protocol.name)],
        }

    consensus = len(counts) == 1
    decision = representatives[next(iter(counts))] if consensus else ""
    summary = ", ".join(
        f"{representatives[key]} x{counts[key]}"
        for key in sorted(counts.keys(), key=lambda key: (-counts[key], first_seen[key], key))
    )
    total = sum(counts.values())
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[f"{item.get('position', '')}\n{item.get('reasoning', '')}".strip() for item in state["positions"]],
        confidence=(max(counts.values()) / total) if total else 0.0,
        stances=[str(item.get("decision_key") or item.get("position") or "").strip() for item in state["positions"]],
    )
    if consensus and protocol.scrutiny_on_unanimous_consensus and len(state["positions"]) >= 3:
        return {
            "consensus_reached": False,
            "decision": "",
            "scrutiny_requested": True,
            "protocol_name": protocol.name,
            "protocol_telemetry": telemetry.model_dump(),
            "messages": [
                make_message(
                    "system",
                    f"Consensus: True. Positions: {summary}\nUnanimous consensus triggers another scrutiny step.",
                    "consensus_check",
                    protocol_name=protocol.name,
                    telemetry=telemetry.model_dump(),
                )
            ],
        }
    return {
        "consensus_reached": consensus,
        "decision": decision,
        "scrutiny_requested": False,
        "protocol_name": protocol.name,
        "protocol_telemetry": telemetry.model_dump(),
        "messages": [make_message("system", f"Consensus: {consensus}. Positions: {summary}", "consensus_check", protocol_name=protocol.name, telemetry=telemetry.model_dump())],
    }


def route_after_consensus(state: BoardState) -> str:
    if state.get("scrutiny_requested"):
        return "scrutinize_consensus"
    if state["consensus_reached"]:
        if len(state["agents"]) > 3:
            return "delegate_to_workers"
        return "finalize"
    if state["vote_round"] >= state["max_rounds"]:
        return "chairman_decides"
    return "directors_analyze"


def scrutinize_consensus(state: BoardState) -> dict:
    protocol = _protocol(state)
    counts, representatives, _ = _summarize_positions(state["positions"])
    candidate = representatives[next(iter(counts))] if counts else ""
    scrutiny = review_unanimous_consensus(protocol, state["positions"], candidate)
    return {
        "scrutiny_requested": False,
        "scrutiny_passed": scrutiny.passed,
        "consensus_reached": scrutiny.passed,
        "decision": candidate if scrutiny.passed else "",
        "protocol_name": protocol.name,
        "protocol_telemetry": scrutiny.telemetry.model_dump(),
        "messages": [make_message("system", scrutiny.reason, "consensus_scrutiny", protocol_name=protocol.name, telemetry=scrutiny.telemetry.model_dump())],
    }


def route_after_scrutiny(state: BoardState) -> str:
    if state.get("consensus_reached"):
        if len(state["agents"]) > 3:
            return "delegate_to_workers"
        return "finalize"
    if state["vote_round"] >= state["max_rounds"]:
        return "chairman_decides"
    return "directors_analyze"


def chairman_decides(state: BoardState) -> dict:
    if not state["agents"]:
        message = "No chairman available."
        return {"decision": "", "result": message, "messages": [make_message("system", message, "chairman_decision")]}

    chairman = state["agents"][0]
    chairman_position = ""
    for position in state["positions"]:
        if position.get("director") == chairman["role"] and position.get("position"):
            chairman_position = str(position["position"]).strip()
            break
    if not chairman_position:
        for position in state["positions"]:
            raw = str(position.get("position", "")).strip()
            if raw:
                chairman_position = raw
                break
    positions_text = "\n".join(
        f"- {p['director']}: {p['position']}\n  Reasoning: {p.get('reasoning', '')}" for p in state["positions"]
    )
    if chairman_position:
        response = (
            f"As chairman, no consensus after {state['vote_round']} rounds.\n\n"
            f"Positions:\n{positions_text}\n\n"
            f"Final decision: {chairman_position}"
        )
        return {
            "decision": chairman_position,
            "result": chairman_position,
            "messages": [make_message(chairman["role"], response, "chairman_decision")],
        }

    response = f"As chairman, no consensus after {state['vote_round']} rounds, but no position was recorded."
    return {"decision": "", "result": response, "messages": [make_message(chairman["role"], response, "chairman_decision")]}


def delegate_to_workers(state: BoardState) -> dict:
    workers = state["agents"][3:]
    results = []
    messages = []
    for worker in workers:
        response = call_agent_cfg(
            worker,
            apply_user_instructions(
                state,
                f"The board decided:\n{state['decision']}\n\nExecute your part.\nOriginal task: {state['task']}",
            ),
        )
        results.append({"worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, "worker_execution"))
    return {"worker_results": results, "messages": messages}


def finalize(state: BoardState) -> dict:
    if state["worker_results"]:
        combined = "\n\n".join(f"{r['worker']}: {r['result']}" for r in state["worker_results"])
        result = f"Board decision: {state['decision']}\n\nExecution:\n{combined}"
    else:
        result = state["decision"]
    return {"result": result, "messages": [make_message("system", "Session complete", "done")]}


def build_board_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(BoardState)
    builder.add_node("directors_analyze", directors_analyze)
    builder.add_node("check_consensus", check_consensus)
    builder.add_node("scrutinize_consensus", scrutinize_consensus)
    builder.add_node("chairman_decides", chairman_decides)
    builder.add_node("delegate_to_workers", delegate_to_workers)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "directors_analyze")
    builder.add_edge("directors_analyze", "check_consensus")
    builder.add_conditional_edges(
        "check_consensus",
        route_after_consensus,
        {
            "delegate_to_workers": "delegate_to_workers",
            "finalize": "finalize",
            "chairman_decides": "chairman_decides",
            "directors_analyze": "directors_analyze",
            "scrutinize_consensus": "scrutinize_consensus",
        },
    )
    builder.add_conditional_edges(
        "scrutinize_consensus",
        route_after_scrutiny,
        {
            "delegate_to_workers": "delegate_to_workers",
            "finalize": "finalize",
            "chairman_decides": "chairman_decides",
            "directors_analyze": "directors_analyze",
        },
    )
    builder.add_edge("chairman_decides", "delegate_to_workers")
    builder.add_edge("delegate_to_workers", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(**compile_kwargs)
