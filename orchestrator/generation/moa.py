"""Mixture-of-Agents layered generation mode."""

from __future__ import annotations

import asyncio
import json
import operator
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from orchestrator.debate.judge_pack import (
    FOUNDER_JUDGE_CRITERIA,
    build_founder_judge_pack_instructions,
    parse_founder_scorecard,
    scorecard_average,
)
from orchestrator.models import MoAGenerationTrace, MoAJudgeScore, MoALayerArtifact
from orchestrator.modes.base import (
    apply_user_instructions,
    call_agent_cfg,
    make_message,
    require_agent_response,
    strip_markdown_fence,
)
from orchestrator.novelty.breeding import generate_trisociation_blends
from orchestrator.novelty.noise_seed import generate_noise_seeds
from orchestrator.novelty.semantic_tabu import DEFAULT_TABU_BANK, assess_semantic_tabu, render_tabu_guardrails

DEFAULT_JUDGE_CRITERIA = list(FOUNDER_JUDGE_CRITERIA)


class MoAState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    user_messages: list[str]
    config: dict
    layer1_outputs: list[dict]
    layer2_outputs: list[dict]
    judge_scores: list[dict]
    trace_artifacts: list[dict]
    selected_candidate_id: str
    result: str


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _judge_criteria(state: MoAState) -> list[str]:
    configured = (state.get("config") or {}).get("judge_criteria")
    if not isinstance(configured, list):
        return list(DEFAULT_JUDGE_CRITERIA)
    normalized = [str(item).strip() for item in configured if str(item).strip()]
    return normalized or list(DEFAULT_JUDGE_CRITERIA)


def _collect_domain_signals(state: MoAState) -> list[str]:
    config = dict(state.get("config") or {})
    collected: list[str] = []
    seen: set[str] = set()
    interesting_keys = {
        "domain_signals",
        "domain_clusters",
        "dominant_domains",
        "adjacent_product_opportunities",
        "adjacent_buyer_pain",
        "recurring_pain_areas",
        "issue_themes",
        "topic_tags",
        "tech_stack",
    }

    def append_value(value: object) -> None:
        text = str(value or "").strip()
        if len(text) < 4 or len(text) > 80:
            return
        normalized = text.lower()
        if normalized in seen:
            return
        seen.add(normalized)
        collected.append(text)

    def walk(value: object, *, key: str = "") -> None:
        if isinstance(value, str):
            if key in interesting_keys or len(value.split()) <= 5:
                append_value(value)
            return
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                if inner_key in interesting_keys:
                    walk(inner_value, key=inner_key)
            return
        if isinstance(value, list):
            for item in value[:12]:
                walk(item, key=key)

    for key in interesting_keys:
        walk(config.get(key), key=key)
    return collected[:8]


def _novelty_context(state: MoAState, *, proposer_count: int = 3) -> dict[str, Any]:
    existing = dict(((state.get("config") or {}).get("generation_trace") or {}).get("novelty_context") or {})
    desired_count = max(proposer_count, 3)
    if existing:
        seed_count = len(list(existing.get("noise_seeds") or []))
        blend_count = len(list(existing.get("trisociation_blends") or []))
        if seed_count >= desired_count and blend_count >= desired_count:
            return existing

    domain_signals = _collect_domain_signals(state)
    noise_seeds = generate_noise_seeds(
        state.get("task") or "",
        count=desired_count,
        salt=str((state.get("config") or {}).get("seed_salt") or ""),
    )
    trisociation_blends = generate_trisociation_blends(
        state.get("task") or "",
        domain_candidates=domain_signals,
        seed_texts=[seed.seed_text for seed in noise_seeds],
        count=desired_count,
    )
    return {
        "domain_signals": domain_signals,
        "taboo_bank_preview": list(DEFAULT_TABU_BANK),
        "noise_seeds": [seed.model_dump() for seed in noise_seeds],
        "trisociation_blends": [blend.model_dump() for blend in trisociation_blends],
    }


def _partition_agents(state: MoAState) -> tuple[list[dict], list[dict], dict | None]:
    agents = list(state.get("agents") or [])
    if not agents:
        return [], [], None

    requested_aggregators = max(_safe_int((state.get("config") or {}).get("aggregator_count"), 2), 1)
    aggregator_count = min(requested_aggregators, max(len(agents) - 3, 1))
    proposer_count = max(len(agents) - aggregator_count - 1, 1)
    if proposer_count < 2 and len(agents) >= 5:
        aggregator_count = max(1, len(agents) - 3)
        proposer_count = len(agents) - aggregator_count - 1

    proposers = agents[:proposer_count]
    aggregators = agents[proposer_count : proposer_count + aggregator_count]
    final_synthesizer = agents[-1]
    return proposers, aggregators, final_synthesizer


def _local_first_note(state: MoAState) -> str:
    if not bool((state.get("config") or {}).get("local_first")):
        return ""
    return (
        "LOCAL-FIRST OVERNIGHT MODE:\n"
        "- Prefer local workspace evidence before browsing.\n"
        "- Avoid unnecessary tool calls.\n"
        "- Bias toward batch-friendly, cheaper, or offline-safe reasoning.\n"
        "- Keep outputs structured and compact so later layers can process them cheaply.\n\n"
    )


def _artifact(
    layer: str,
    agent: dict,
    content: str,
    *,
    candidate_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = MoALayerArtifact(
        layer=layer,
        agent_role=str(agent.get("role") or "agent"),
        provider=str(agent.get("provider") or "unknown"),
        candidate_id=candidate_id,
        content=content.strip(),
        summary=content.strip().replace("\n", " ")[:220],
        metadata=dict(metadata or {}),
    )
    return artifact.model_dump()


def _trace_config(
    state: MoAState,
    *,
    novelty_context: dict[str, Any] | None = None,
    layer1_outputs: list[dict] | None = None,
    layer2_outputs: list[dict] | None = None,
    judge_scores: list[dict] | None = None,
    trace_artifacts: list[dict] | None = None,
    selected_candidate_id: str | None = None,
    final_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(state.get("config") or {})
    existing = dict(config.get("generation_trace") or {})
    prompt_overrides = dict(config.get("prompt_profile_overrides") or {})
    trace = MoAGenerationTrace(
        local_first=bool(config.get("local_first")),
        aggregator_count=max(_safe_int(config.get("aggregator_count"), 2), 1),
        judge_criteria=_judge_criteria(state),
        prompt_profile_id=str(config.get("prompt_profile_id") or existing.get("prompt_profile_id") or "") or None,
        prompt_profile_label=str(config.get("prompt_profile_label") or existing.get("prompt_profile_label") or "") or None,
        improvement_tactics=list(prompt_overrides.get("tactics") or existing.get("improvement_tactics") or []),
        novelty_context=dict(novelty_context if novelty_context is not None else existing.get("novelty_context") or {}),
        layer1_outputs=list(layer1_outputs if layer1_outputs is not None else existing.get("layer1_outputs") or []),
        layer2_outputs=list(layer2_outputs if layer2_outputs is not None else existing.get("layer2_outputs") or []),
        judge_scores=list(judge_scores if judge_scores is not None else existing.get("judge_scores") or []),
        trace_artifacts=list(trace_artifacts if trace_artifacts is not None else existing.get("trace_artifacts") or []),
        selected_candidate_id=selected_candidate_id if selected_candidate_id is not None else existing.get("selected_candidate_id"),
        final_artifact=final_artifact if final_artifact is not None else existing.get("final_artifact"),
    )
    config["generation_trace"] = trace.model_dump()
    return config


def _profile_note(state: MoAState, kind: str) -> str:
    config = dict(state.get("config") or {})
    overrides = dict(config.get("prompt_profile_overrides") or {})
    note = str(overrides.get(f"{kind}_prefix") or "").strip()
    if not note:
        return ""
    label = str(config.get("prompt_profile_label") or config.get("prompt_profile_id") or "active_profile").strip()
    return f"IMPROVEMENT PROFILE ({label} / {kind}):\n{note}\n\n"


def _proposer_novelty_note(state: MoAState, index: int, proposer_count: int) -> str:
    novelty_context = _novelty_context(state, proposer_count=proposer_count)
    seeds = list(novelty_context.get("noise_seeds") or [])
    blends = list(novelty_context.get("trisociation_blends") or [])
    seed = dict(seeds[index % len(seeds)]) if seeds else {}
    blend = dict(blends[index % len(blends)]) if blends else {}
    guardrails = render_tabu_guardrails(list(novelty_context.get("taboo_bank_preview") or DEFAULT_TABU_BANK))
    blend_note = str(blend.get("prompt_note") or "").strip()
    seed_note = str(seed.get("prompt_note") or "").strip()
    return (
        f"{guardrails}"
        "DIVERGENCE ASSIGNMENT:\n"
        f"- {seed_note or 'Force a non-obvious mechanism into the thesis.'}\n"
        f"- {blend_note or 'Fuse two or three distant domains into one concrete wedge.'}\n"
        "- Do not mention the seed or blend explicitly in the answer; translate them into a believable startup direction.\n\n"
    )


def _layer1_prompt(state: MoAState, agent: dict, index: int, proposer_count: int) -> str:
    return apply_user_instructions(
        state,
        (
            "You are a layer-1 proposer inside a Mixture-of-Agents generation stack.\n"
            f"Your job is to produce one strong candidate from the vantage point of role '{agent['role']}'.\n"
            "Be meaningfully distinct from the other proposers rather than converging too early.\n\n"
            f"{_local_first_note(state)}"
            f"{_profile_note(state, 'generator')}"
            f"{_proposer_novelty_note(state, index, proposer_count)}"
            f"TASK:\n{state['task']}\n\n"
            f"PIPELINE CONTEXT:\nThis is proposer {index + 1} of {proposer_count}. Later layers will compare and merge proposals.\n\n"
            "Return a plain-text candidate memo with these sections:\n"
            "- Core thesis\n"
            "- ICP / buyer\n"
            "- Distribution wedge\n"
            "- Build plan\n"
            "- Evidence gaps\n"
            "- Biggest risk\n"
        ),
    )


def _format_candidates(entries: list[dict]) -> str:
    blocks: list[str] = []
    for entry in entries:
        metadata = dict(entry.get("metadata") or {})
        assessment = dict(metadata.get("novelty_assessment") or {})
        novelty_note = ""
        if assessment:
            status = "blocked" if assessment.get("banned") else (
                "penalized" if float(assessment.get("penalty") or 0.0) >= 0.35 else "clear"
            )
            novelty_note = (
                f"\nAnti-banality: status={status}, penalty={float(assessment.get('penalty') or 0.0):.2f}, "
                f"reasons={assessment.get('reasons') or []}"
            )
        blocks.append(
            f"{entry.get('candidate_id') or entry.get('artifact_id')} | {entry.get('agent_role')} ({entry.get('provider')})\n"
            f"{entry.get('content', '')}"
            f"{novelty_note}"
        )
    return "\n\n".join(blocks)


def _layer2_prompt(state: MoAState, agent: dict, candidate_inputs: list[dict]) -> str:
    novelty_context = _novelty_context(state, proposer_count=max(len(candidate_inputs), 3))
    guardrails = render_tabu_guardrails(list(novelty_context.get("taboo_bank_preview") or DEFAULT_TABU_BANK))
    return apply_user_instructions(
        state,
        (
            "You are a layer-2 aggregator in a Mixture-of-Agents generation stack.\n"
            f"Your role is '{agent['role']}'. You can see every layer-1 proposal and must synthesize one stronger candidate.\n"
            "Do not average them blindly. Keep the strongest claims, cut weak parts, and fill obvious gaps.\n\n"
            f"{_local_first_note(state)}"
            f"{_profile_note(state, 'generator')}"
            f"{guardrails}"
            "Prefer the candidate spine that escapes generic 'AI SaaS for X' framing and has the sharpest founder-distribution wedge.\n\n"
            f"TASK:\n{state['task']}\n\n"
            f"LAYER-1 PROPOSALS:\n{_format_candidates(candidate_inputs)}\n\n"
            "Return one plain-text synthesized candidate with these sections:\n"
            "- Winning thesis\n"
            "- Target buyer / ICP\n"
            "- Why this beats the raw proposals\n"
            "- Distribution + monetization path\n"
            "- Build scope for the first version\n"
            "- Remaining evidence gaps / risks\n"
        ),
    )


def _judge_prompt(state: MoAState, agent: dict, aggregate_candidates: list[dict]) -> str:
    criteria = _judge_criteria(state)
    criteria_json = json.dumps(criteria)
    judge_pack_note = build_founder_judge_pack_instructions(criteria=criteria)
    return apply_user_instructions(
        state,
        (
            "You are part of the judge pack for a Mixture-of-Agents generation stack.\n"
            f"Evaluate the layer-2 candidates from the vantage point of role '{agent['role']}'.\n"
            "Higher scores mean stronger quality. For 'risk_profile', a higher score means the risk profile is more acceptable.\n\n"
            f"{_profile_note(state, 'judge')}"
            f"TASK:\n{state['task']}\n\n"
            f"LAYER-2 CANDIDATES:\n{_format_candidates(aggregate_candidates)}\n\n"
            f"{judge_pack_note}\n"
            "Penalize candidates that collapse into a generic wrapper or broad 'AI copilot for X' shell even if they sound polished.\n\n"
            "Return ONLY valid JSON with this shape:\n"
            "{\n"
            '  "winner_candidate_id": "aggregate_1",\n'
            '  "summary": "short summary",\n'
            '  "scores": [\n'
            "    {\n"
            '      "candidate_id": "aggregate_1",\n'
            '      "overall_score": 8.4,\n'
            '      "criteria": {"problem_sharpness": 8, "icp_clarity": 9},\n'
            '      "rationale": "why this candidate scored this way"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Use these criteria keys exactly: {criteria_json}"
        ),
    )


def _parse_judge_response(
    response: str,
    *,
    judge_role: str,
    candidate_ids: list[str],
    criteria: list[str],
) -> list[dict[str, Any]]:
    cleaned = strip_markdown_fence(response)
    payload: dict[str, Any] = {}
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        payload = {}

    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raw_scores = []

    scores: list[dict[str, Any]] = []
    for raw_score in raw_scores:
        if not isinstance(raw_score, dict):
            continue
        candidate_id = str(raw_score.get("candidate_id") or "").strip()
        if candidate_id not in candidate_ids:
            continue
        normalized_criteria = parse_founder_scorecard(
            raw_score,
            criteria=criteria,
            fallback_text=str(raw_score.get("rationale") or payload.get("summary") or response),
        )
        overall_score = raw_score.get("overall_score")
        if overall_score is None:
            overall_score = scorecard_average(normalized_criteria, criteria=criteria)
        score = MoAJudgeScore(
            judge_role=judge_role,
            candidate_id=candidate_id,
            overall_score=float(overall_score or 0.0),
            criteria=normalized_criteria,
            rationale=str(raw_score.get("rationale") or payload.get("summary") or response).strip(),
        )
        scores.append(score.model_dump())

    if scores:
        return scores

    fallback_candidate = str(payload.get("winner_candidate_id") or candidate_ids[0] if candidate_ids else "").strip()
    if fallback_candidate:
        fallback_criteria = parse_founder_scorecard(payload, criteria=criteria, fallback_text=str(payload.get("summary") or response))
        fallback = MoAJudgeScore(
            judge_role=judge_role,
            candidate_id=fallback_candidate,
            overall_score=scorecard_average(fallback_criteria or {key: 5.0 for key in criteria}, criteria=criteria) or 5.0,
            criteria=fallback_criteria or {key: 5.0 for key in criteria},
            rationale=str(payload.get("summary") or response).strip()[:280],
        )
        return [fallback.model_dump()]
    return []


def _select_best_candidate(layer2_outputs: list[dict], judge_scores: list[dict]) -> tuple[str, list[dict[str, Any]]]:
    candidate_ids = [str(entry.get("candidate_id") or "").strip() for entry in layer2_outputs if str(entry.get("candidate_id") or "").strip()]
    aggregates: dict[str, dict[str, Any]] = {
        candidate_id: {"candidate_id": candidate_id, "score_total": 0.0, "vote_count": 0, "judge_roles": []}
        for candidate_id in candidate_ids
    }
    for score in judge_scores:
        candidate_id = str(score.get("candidate_id") or "").strip()
        if candidate_id not in aggregates:
            continue
        aggregates[candidate_id]["score_total"] += float(score.get("overall_score") or 0.0)
        aggregates[candidate_id]["vote_count"] += 1
        judge_role = str(score.get("judge_role") or "").strip()
        if judge_role:
            aggregates[candidate_id]["judge_roles"].append(judge_role)

    leaderboard = []
    for candidate_id in candidate_ids:
        entry = aggregates[candidate_id]
        vote_count = max(int(entry["vote_count"]), 1)
        artifact = next((item for item in layer2_outputs if str(item.get("candidate_id") or "").strip() == candidate_id), {})
        assessment = dict(dict(artifact.get("metadata") or {}).get("novelty_assessment") or {})
        novelty_penalty = float(assessment.get("penalty") or 0.0)
        blocked = bool(assessment.get("banned"))
        average_score = round(float(entry["score_total"]) / vote_count, 3)
        adjusted_score = average_score - (novelty_penalty * 2.4) - (1.15 if blocked else 0.0)
        leaderboard.append(
            {
                "candidate_id": candidate_id,
                "average_score": average_score,
                "adjusted_score": round(adjusted_score, 3),
                "vote_count": int(entry["vote_count"]),
                "judge_roles": list(entry["judge_roles"]),
                "novelty_penalty": round(novelty_penalty, 3),
                "novelty_blocked": blocked,
            }
        )
    leaderboard.sort(key=lambda item: (-item["adjusted_score"], -item["average_score"], item["candidate_id"]))
    winner = leaderboard[0]["candidate_id"] if leaderboard else (candidate_ids[0] if candidate_ids else "")
    return winner, leaderboard


def _annotate_artifacts_with_novelty(
    artifacts: list[dict],
    *,
    novelty_context: dict[str, Any],
    baseline_candidates: list[str] | None = None,
) -> list[dict]:
    baseline_candidates = list(baseline_candidates or [])
    all_contents = [str(item.get("content") or "") for item in artifacts]
    updated: list[dict] = []
    for index, artifact in enumerate(artifacts):
        peer_candidates = [text for position, text in enumerate(all_contents) if position != index]
        assessment = assess_semantic_tabu(
            str(artifact.get("content") or ""),
            prior_candidates=[*baseline_candidates, *peer_candidates],
            taboo_bank=list(novelty_context.get("taboo_bank_preview") or DEFAULT_TABU_BANK),
            domain_signals=list(novelty_context.get("domain_signals") or []),
        )
        artifact_copy = dict(artifact)
        metadata = dict(artifact_copy.get("metadata") or {})
        metadata["novelty_assessment"] = assessment.model_dump()
        metadata["anti_banality_status"] = (
            "blocked" if assessment.banned else "penalized" if assessment.penalty >= 0.35 else "clear"
        )
        artifact_copy["metadata"] = metadata
        updated.append(artifact_copy)
    return updated


async def generate_layer_one(state: MoAState) -> dict[str, Any]:
    proposers, aggregators, final_synthesizer = _partition_agents(state)
    novelty_context = _novelty_context(state, proposer_count=max(len(proposers), 3))
    if not proposers:
        config = _trace_config(state, novelty_context=novelty_context, layer1_outputs=[], trace_artifacts=[])
        return {
            "layer1_outputs": [],
            "trace_artifacts": [],
            "config": config,
            "messages": [make_message("system", "No proposer agents available for layer 1.", "moa_layer1")],
        }

    async def run_proposer(index: int, agent: dict) -> tuple[dict, dict]:
        response = await asyncio.to_thread(
            call_agent_cfg,
            agent,
            _layer1_prompt(state, agent, index, len(proposers)),
        )
        response = require_agent_response(agent, response, "Layer-1 proposer failed")
        candidate_id = f"proposal_{index + 1}"
        artifact = _artifact(
            "layer1",
            agent,
            response,
            candidate_id=candidate_id,
            metadata={
                "proposer_index": index + 1,
                "aggregator_roles": [item.get("role") for item in aggregators],
                "final_role": final_synthesizer.get("role") if final_synthesizer else None,
                "noise_seed": novelty_context.get("noise_seeds", [])[index % max(len(list(novelty_context.get("noise_seeds") or [])), 1)] if novelty_context.get("noise_seeds") else None,
                "trisociation_blend": novelty_context.get("trisociation_blends", [])[index % max(len(list(novelty_context.get("trisociation_blends") or [])), 1)] if novelty_context.get("trisociation_blends") else None,
            },
        )
        message = make_message(
            agent["role"],
            response,
            f"moa_layer1_{index + 1}",
            layer="layer1",
            candidate_id=candidate_id,
        )
        return artifact, message

    results = await asyncio.gather(*(run_proposer(index, agent) for index, agent in enumerate(proposers)))
    artifacts = _annotate_artifacts_with_novelty([item[0] for item in results], novelty_context=novelty_context)
    messages = [item[1] for item in results]
    config = _trace_config(
        state,
        novelty_context=novelty_context,
        layer1_outputs=artifacts,
        trace_artifacts=artifacts,
    )
    return {
        "layer1_outputs": artifacts,
        "trace_artifacts": artifacts,
        "config": config,
        "messages": messages,
    }


async def aggregate_layer_two(state: MoAState) -> dict[str, Any]:
    _, aggregators, _ = _partition_agents(state)
    layer1_outputs = list(state.get("layer1_outputs") or [])
    trace_artifacts = list(state.get("trace_artifacts") or [])
    novelty_context = _novelty_context(state, proposer_count=max(len(layer1_outputs), 3))
    if not aggregators or not layer1_outputs:
        config = _trace_config(
            state,
            novelty_context=novelty_context,
            layer1_outputs=layer1_outputs,
            layer2_outputs=[],
            trace_artifacts=trace_artifacts,
        )
        return {
            "layer2_outputs": [],
            "config": config,
            "messages": [make_message("system", "Skipping layer 2 aggregation because inputs are missing.", "moa_layer2")],
        }

    async def run_aggregator(index: int, agent: dict) -> tuple[dict, dict]:
        response = await asyncio.to_thread(
            call_agent_cfg,
            agent,
            _layer2_prompt(state, agent, layer1_outputs),
        )
        response = require_agent_response(agent, response, "Layer-2 aggregation failed")
        candidate_id = f"aggregate_{index + 1}"
        artifact = _artifact(
            "layer2",
            agent,
            response,
            candidate_id=candidate_id,
            metadata={
                "input_candidate_ids": [entry.get("candidate_id") for entry in layer1_outputs],
                "aggregator_index": index + 1,
                "taboo_bank_preview": novelty_context.get("taboo_bank_preview"),
            },
        )
        message = make_message(
            agent["role"],
            response,
            f"moa_layer2_{index + 1}",
            layer="layer2",
            candidate_id=candidate_id,
        )
        return artifact, message

    results = await asyncio.gather(*(run_aggregator(index, agent) for index, agent in enumerate(aggregators)))
    artifacts = _annotate_artifacts_with_novelty(
        [item[0] for item in results],
        novelty_context=novelty_context,
        baseline_candidates=[str(entry.get("content") or "") for entry in layer1_outputs],
    )
    messages = [item[1] for item in results]
    updated_trace_artifacts = [*trace_artifacts, *artifacts]
    config = _trace_config(
        state,
        novelty_context=novelty_context,
        layer1_outputs=layer1_outputs,
        layer2_outputs=artifacts,
        trace_artifacts=updated_trace_artifacts,
    )
    return {
        "layer2_outputs": artifacts,
        "trace_artifacts": updated_trace_artifacts,
        "config": config,
        "messages": messages,
    }


async def judge_layer_two(state: MoAState) -> dict[str, Any]:
    proposers, aggregators, final_synthesizer = _partition_agents(state)
    judges = [*proposers, *aggregators]
    layer1_outputs = list(state.get("layer1_outputs") or [])
    layer2_outputs = list(state.get("layer2_outputs") or [])
    trace_artifacts = list(state.get("trace_artifacts") or [])
    novelty_context = _novelty_context(state, proposer_count=max(len(layer2_outputs), 3))
    if not judges or not layer2_outputs:
        config = _trace_config(
            state,
            novelty_context=novelty_context,
            layer1_outputs=layer1_outputs,
            layer2_outputs=layer2_outputs,
            judge_scores=[],
            trace_artifacts=trace_artifacts,
        )
        return {
            "judge_scores": [],
            "config": config,
            "messages": [make_message("system", "Skipping judge pack because no layer-2 candidates are available.", "moa_judge")],
        }

    candidate_ids = [str(entry.get("candidate_id") or "").strip() for entry in layer2_outputs if str(entry.get("candidate_id") or "").strip()]
    criteria = _judge_criteria(state)

    async def run_judge(index: int, agent: dict) -> tuple[list[dict], dict]:
        response = await asyncio.to_thread(
            call_agent_cfg,
            agent,
            _judge_prompt(state, agent, layer2_outputs),
        )
        response = require_agent_response(agent, response, "Judge-pack scoring failed")
        parsed_scores = _parse_judge_response(
            response,
            judge_role=str(agent.get("role") or f"judge_{index + 1}"),
            candidate_ids=candidate_ids,
            criteria=criteria,
        )
        message = make_message(
            agent["role"],
            response,
            f"moa_judge_{index + 1}",
            layer="judge_pack",
            candidate_ids=candidate_ids,
            final_role=final_synthesizer.get("role") if final_synthesizer else None,
        )
        return parsed_scores, message

    results = await asyncio.gather(*(run_judge(index, agent) for index, agent in enumerate(judges)))
    judge_scores = [score for scores, _ in results for score in scores]
    messages = [message for _, message in results]
    config = _trace_config(
        state,
        novelty_context=novelty_context,
        layer1_outputs=layer1_outputs,
        layer2_outputs=layer2_outputs,
        judge_scores=judge_scores,
        trace_artifacts=trace_artifacts,
    )
    return {
        "judge_scores": judge_scores,
        "config": config,
        "messages": messages,
    }


def finalize_generation(state: MoAState) -> dict[str, Any]:
    _, _, final_synthesizer = _partition_agents(state)
    layer1_outputs = list(state.get("layer1_outputs") or [])
    layer2_outputs = list(state.get("layer2_outputs") or [])
    judge_scores = list(state.get("judge_scores") or [])
    trace_artifacts = list(state.get("trace_artifacts") or [])
    novelty_context = _novelty_context(state, proposer_count=max(len(layer2_outputs), 3))
    selected_candidate_id, leaderboard = _select_best_candidate(layer2_outputs, judge_scores)
    selected_candidate = next(
        (entry for entry in layer2_outputs if str(entry.get("candidate_id") or "").strip() == selected_candidate_id),
        layer2_outputs[0] if layer2_outputs else None,
    )

    if final_synthesizer is None or selected_candidate is None:
        message = "Unable to run the final synthesis because the MoA pipeline has no final candidate."
        config = _trace_config(
            state,
            novelty_context=novelty_context,
            layer1_outputs=layer1_outputs,
            layer2_outputs=layer2_outputs,
            judge_scores=judge_scores,
            trace_artifacts=trace_artifacts,
            selected_candidate_id=selected_candidate_id or "",
        )
        return {
            "selected_candidate_id": selected_candidate_id or "",
            "result": message,
            "config": config,
            "messages": [make_message("system", message, "moa_final")],
        }

    prompt = apply_user_instructions(
        state,
        (
            "You are the layer-3 final synthesizer in a Mixture-of-Agents generation stack.\n"
            "Use the winning layer-2 candidate as the default spine, but improve it using judge-pack feedback.\n"
            "Do not rehash the full process; deliver the best final answer.\n\n"
            f"{_local_first_note(state)}"
            f"{_profile_note(state, 'generator')}"
            f"{_profile_note(state, 'critic')}"
            f"TASK:\n{state['task']}\n\n"
            f"WINNING LAYER-2 CANDIDATE ({selected_candidate_id}):\n{selected_candidate.get('content', '')}\n\n"
            f"NOVELTY CONTEXT:\n{json.dumps(novelty_context, indent=2)}\n\n"
            f"LEADERBOARD:\n{json.dumps(leaderboard, indent=2)}\n\n"
            f"JUDGE SCORES:\n{json.dumps(judge_scores, indent=2)}\n\n"
            f"RAW LAYER-1 INPUTS:\n{_format_candidates(layer1_outputs)}\n\n"
            "Return a plain-text final synthesis with:\n"
            "- Recommended direction\n"
            "- Why it won\n"
            "- Immediate next steps\n"
            "- Biggest unresolved risk\n"
        ),
    )
    response = require_agent_response(
        final_synthesizer,
        call_agent_cfg(final_synthesizer, prompt),
        "Final MoA synthesis failed",
    )
    final_artifact = _artifact(
        "final",
        final_synthesizer,
        response,
        candidate_id=selected_candidate_id,
        metadata={
            "selected_candidate_id": selected_candidate_id,
            "leaderboard": leaderboard,
            "novelty_context": novelty_context,
            "selected_candidate_novelty": dict(dict(selected_candidate.get("metadata") or {}).get("novelty_assessment") or {}),
        },
    )
    updated_trace_artifacts = [*trace_artifacts, final_artifact]
    config = _trace_config(
        state,
        novelty_context=novelty_context,
        layer1_outputs=layer1_outputs,
        layer2_outputs=layer2_outputs,
        judge_scores=judge_scores,
        trace_artifacts=updated_trace_artifacts,
        selected_candidate_id=selected_candidate_id,
        final_artifact=final_artifact,
    )
    return {
        "selected_candidate_id": selected_candidate_id,
        "trace_artifacts": updated_trace_artifacts,
        "result": response,
        "config": config,
        "messages": [
            make_message(
                final_synthesizer["role"],
                response,
                "moa_final",
                layer="final",
                candidate_id=selected_candidate_id,
                leaderboard=leaderboard,
            )
        ],
    }


def build_moa_graph(**compile_kwargs) -> StateGraph:
    builder = StateGraph(MoAState)
    builder.add_node("generate_layer_one", generate_layer_one)
    builder.add_node("aggregate_layer_two", aggregate_layer_two)
    builder.add_node("judge_layer_two", judge_layer_two)
    builder.add_node("finalize_generation", finalize_generation)
    builder.add_edge(START, "generate_layer_one")
    builder.add_edge("generate_layer_one", "aggregate_layer_two")
    builder.add_edge("aggregate_layer_two", "judge_layer_two")
    builder.add_edge("judge_layer_two", "finalize_generation")
    builder.add_edge("finalize_generation", END)
    return builder.compile(**compile_kwargs)
