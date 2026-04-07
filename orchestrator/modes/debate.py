"""Debate mode: proponent vs opponent, judge decides."""

import operator
import re
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.debate.factcheck import ValidatedTurn, validate_with_retry
from orchestrator.debate.judges import aggregate_panel_decisions, parse_judge_response
from orchestrator.debate.moderators import (
    build_argument_prompt,
    build_improvement_prompt_context,
    build_judge_prompt,
)
from orchestrator.debate.protocols import build_protocol_telemetry, resolve_protocol_for_mode
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
    config: dict
    rounds: list[dict]
    current_round: int
    max_rounds: int
    verdict: str
    judge_action: str
    protocol_name: str
    protocol_telemetry: dict
    fact_check_failures: dict
    disqualified_role: str
    result: str


FINAL_VERDICT_MARKER = "FINAL_VERDICT"
CONTINUE_MARKER = "NEED_MORE_ROUNDS"
CONTROL_MARKER_RE = re.compile(r"\b(?:FINAL_VERDICT|NEED_MORE_ROUNDS)\b[:\-\s]*", re.IGNORECASE)


def _protocol(state: DebateState):
    return resolve_protocol_for_mode("debate", state.get("config") or {})


def _history_text(state: DebateState) -> str:
    if not state["rounds"]:
        return ""
    return "\n\nPrevious rounds:\n" + "\n".join(
        f"Round {item['round']}:\n  PRO: {item.get('pro_arg', '')[:300]}\n  CON: {item.get('con_arg', '')[:300]}"
        for item in state["rounds"]
    )


def _validate_turn(
    state: DebateState,
    agent: dict,
    prompt: str,
    response: str,
    context: str,
) -> tuple[str, ValidatedTurn, dict]:
    protocol = _protocol(state)
    if not protocol.supports_factcheck:
        report = ValidatedTurn(
            response=response,
            report={
                "ok": True,
                "issues": [],
                "evidence_density": 0.0,
            },
        )
        return response, report, {}

    validated = validate_with_retry(
        response=response,
        responder=lambda retry_note: require_agent_response(
            agent,
            call_agent_cfg(agent, apply_user_instructions(state, f"{prompt}\n\n{retry_note}")),
            context,
        ),
    )
    updates: dict = {}
    if validated.disqualified:
        failures = dict(state.get("fact_check_failures") or {})
        failures[str(agent.get("role", "agent"))] = failures.get(str(agent.get("role", "agent")), 0) + 1
        updates = {
            "fact_check_failures": failures,
            "disqualified_role": str(agent.get("role", "agent")),
        }
    return validated.response, validated, updates


def proponent_argues(state: DebateState) -> dict:
    if state.get("disqualified_role"):
        return {"messages": []}

    pro = state["agents"][0]
    opp = state["agents"][1]
    protocol = _protocol(state)
    rnd = state["current_round"]
    prompt = build_argument_prompt(
        protocol=protocol,
        workspace_context=build_workspace_context_prompt(pro),
        task=state["task"],
        participant_label=pro["role"],
        opponent_label=opp["role"],
        role_kind="proposer",
        round_number=rnd + 1,
        max_rounds=state["max_rounds"],
        history_text=_history_text(state),
        extra_context=build_improvement_prompt_context(state.get("config"), "generator"),
    )
    raw_response = require_agent_response(
        pro,
        call_agent_cfg(pro, apply_user_instructions(state, prompt)),
        "Debate proponent step failed",
    )
    response, factcheck, extra_updates = _validate_turn(state, pro, prompt, raw_response, "Debate proponent retry failed")
    return {
        "protocol_name": protocol.name,
        "messages": [make_message(pro["role"], response, f"round_{rnd + 1}_pro", protocol_name=protocol.name, factcheck=factcheck.report.model_dump())],
        "rounds": [
            *state["rounds"],
            {
                "round": rnd + 1,
                "pro_arg": response,
                "con_arg": "",
                "pro_factcheck": factcheck.report.model_dump(),
                "con_factcheck": {},
            },
        ],
        **extra_updates,
    }


def opponent_argues(state: DebateState) -> dict:
    if state.get("disqualified_role") == state["agents"][0]["role"]:
        return {"current_round": int((state["rounds"][-1] if state["rounds"] else {}).get("round") or 0), "messages": []}

    opp = state["agents"][1]
    pro = state["agents"][0]
    protocol = _protocol(state)
    rnd = state["current_round"]
    current_round_data = state["rounds"][-1]
    pro_arg = current_round_data["pro_arg"]
    prompt = build_argument_prompt(
        protocol=protocol,
        workspace_context=build_workspace_context_prompt(opp),
        task=state["task"],
        participant_label=opp["role"],
        opponent_label=pro["role"],
        role_kind="critic",
        round_number=rnd + 1,
        max_rounds=state["max_rounds"],
        history_text=_history_text({**state, "rounds": state["rounds"][:-1]}),
        opponent_current_arg=pro_arg,
        extra_context=build_improvement_prompt_context(state.get("config"), "critic"),
    )
    raw_response = require_agent_response(
        opp,
        call_agent_cfg(opp, apply_user_instructions(state, prompt)),
        "Debate opponent step failed",
    )
    response, factcheck, extra_updates = _validate_turn(state, opp, prompt, raw_response, "Debate opponent retry failed")
    updated_rounds = list(state["rounds"])
    updated_rounds[-1] = {
        **updated_rounds[-1],
        "con_arg": response,
        "con_factcheck": factcheck.report.model_dump(),
    }
    return {
        "protocol_name": protocol.name,
        "messages": [make_message(opp["role"], response, f"round_{rnd + 1}_con", protocol_name=protocol.name, factcheck=factcheck.report.model_dump())],
        "rounds": updated_rounds,
        "current_round": rnd + 1,
        **extra_updates,
    }


def judge_decides(state: DebateState) -> dict:
    protocol = _protocol(state)
    judges = state["agents"][2:] if protocol.supports_panel_judging and len(state["agents"]) > 3 else [state["agents"][2]]
    current_round = int(state["current_round"] or 0)
    max_rounds = max(int(state["max_rounds"] or 1), 1)
    final_round = current_round >= max_rounds
    debate_text = "\n\n".join(
        f"=== Round {r['round']} ===\nPRO: {r['pro_arg']}\nCON: {r['con_arg']}"
        for r in state["rounds"]
    )
    disqualified_role = str(state.get("disqualified_role") or "").strip()

    panel_decisions = []
    raw_responses: list[str] = []
    if disqualified_role:
        winner_token = "opponent" if disqualified_role == state["agents"][0]["role"] else "proponent"
        raw_response = (
            f"{FINAL_VERDICT_MARKER}: {winner_token}\n"
            f"Disqualified role: {disqualified_role}.\n"
            "Unsupported claims or meta/tool-seeking behavior persisted after retry.\n"
            "Confidence: 0.90"
        )
        raw_responses.append(raw_response)
        panel_decisions.append(
            parse_judge_response(
                raw_response,
                protocol_name=protocol.name,
                final_marker=FINAL_VERDICT_MARKER,
                continue_marker=CONTINUE_MARKER,
                allowed_winners=("proponent", "opponent"),
            )
        )
    else:
        for judge in judges:
            prompt = build_judge_prompt(
                protocol=protocol,
                workspace_context=build_workspace_context_prompt(judge),
                task=state["task"],
                transcript=debate_text,
                current_round=current_round,
                max_rounds=max_rounds,
                final_marker=FINAL_VERDICT_MARKER,
                continue_marker=CONTINUE_MARKER,
                winner_tokens=("proponent", "opponent"),
                extra_context=build_improvement_prompt_context(state.get("config"), "judge"),
                final_round=final_round,
            )
            response = require_agent_response(
                judge,
                call_agent_cfg(judge, apply_user_instructions(state, prompt)),
                "Debate judge step failed",
            )
            raw_responses.append(response)
            panel_decisions.append(
                parse_judge_response(
                    response,
                    protocol_name=protocol.name,
                    final_marker=FINAL_VERDICT_MARKER,
                    continue_marker=CONTINUE_MARKER,
                    allowed_winners=("proponent", "opponent"),
                )
            )

    panel = aggregate_panel_decisions(panel_decisions)
    if final_round and panel.action == "continue":
        panel.action = "final"
    cleaned_response = CONTROL_MARKER_RE.sub("", panel.rationale).strip() or CONTROL_MARKER_RE.sub("", raw_responses[0]).strip()
    evidence_lines = []
    unsupported_lines = []
    for decision in panel.decisions:
        evidence_lines.extend(item.summary for item in decision.evidence_items[:2])
        unsupported_lines.extend(decision.unsupported_claims[:2])
    if evidence_lines:
        cleaned_response += "\n\nEvidence used:\n" + "\n".join(f"- {line}" for line in evidence_lines[:4])
    if unsupported_lines:
        cleaned_response += "\n\nUnsupported claims:\n" + "\n".join(f"- {line}" for line in unsupported_lines[:4])
    cleaned_response += f"\n\nConfidence: {panel.confidence:.2f}"
    telemetry = build_protocol_telemetry(
        protocol.name,
        texts=[item.get("pro_arg", "") for item in state["rounds"]] + [item.get("con_arg", "") for item in state["rounds"]],
        confidence=panel.confidence,
        stances=[item.winner_token or item.action for item in panel.decisions],
    )
    if panel.action in {"final", "disqualify"}:
        judge_action = "final"
    else:
        judge_action = "continue"
    return {
        "protocol_name": protocol.name,
        "protocol_telemetry": telemetry.model_dump(),
        "judge_action": judge_action,
        "verdict": cleaned_response,
        "result": cleaned_response,
        "messages": [make_message(judges[0]["role"], cleaned_response, "verdict", protocol_name=protocol.name, telemetry=telemetry.model_dump(), judge_schema=panel.model_dump())],
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
