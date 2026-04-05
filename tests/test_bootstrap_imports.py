"""Smoke tests for bootstrap-critical imports and shared contracts."""

import importlib
import os
import sys

from orchestrator.shared_contracts import (
    Confidence,
    EffortEstimate,
    ExecutionBrief,
    RiskItem,
    RiskLevel,
    StoryDecompositionSeed,
    from_jsonable,
    to_jsonable,
)


def test_bootstrap_modules_import_cleanly():
    original_argv = sys.argv[:]
    original_payload = os.environ.pop("CONFIGURED_TOOLS_PAYLOAD", None)
    sys.modules.pop("mcp_servers.configured_tools_server", None)
    modules = [
        "orchestrator.api",
        "orchestrator.repo_digest",
        "orchestrator.repodna",
        "orchestrator.repo_graph",
        "orchestrator.preference_model",
        "orchestrator.ranking",
        "orchestrator.evolution.archive",
        "orchestrator.evolution.map_elites",
        "orchestrator.evolution.operators",
        "orchestrator.evolution.fitness",
        "orchestrator.evolution.prompt_evolution",
        "orchestrator.generation.moa",
        "orchestrator.novelty.semantic_tabu",
        "orchestrator.novelty.noise_seed",
        "orchestrator.novelty.breeding",
        "orchestrator.debate.protocols",
        "orchestrator.debate.blueprints",
        "orchestrator.debate.moderators",
        "orchestrator.debate.judges",
        "orchestrator.debate.judge_pack",
        "orchestrator.debate.factcheck",
        "orchestrator.topology.protocol_compiler",
        "orchestrator.topology.team_builder",
        "orchestrator.topology.graph_optimizer",
        "orchestrator.topology.dynamic_routing",
        "orchestrator.topology.meta_search",
        "orchestrator.simulation.mvp.personas",
        "orchestrator.simulation.mvp.world",
        "orchestrator.simulation.mvp.focus_group",
        "orchestrator.simulation.mvp.feedback",
        "orchestrator.simulation.lab.agent_state",
        "orchestrator.simulation.lab.world_builder",
        "orchestrator.simulation.lab.game_master",
        "orchestrator.simulation.lab.reporting",
        "orchestrator.simulation.lab.market_run",
        "orchestrator.idea_graph",
        "orchestrator.memory_graph",
        "orchestrator.handoff",
        "orchestrator.execution_feedback",
        "orchestrator.improvement.reflective_eval",
        "orchestrator.improvement.self_play",
        "orchestrator.improvement.prompt_evolution",
        "orchestrator.scheduler",
        "orchestrator.daemon",
        "orchestrator.observability.evals",
        "orchestrator.observability.traces",
        "orchestrator.observability.scoreboards",
        "orchestrator.observability.debate_replay",
        "orchestrator.observability.dossier_explainability",
        "orchestrator.guardrails.policies",
        "orchestrator.guardrails.mcp_scan",
        "orchestrator.guardrails.tool_safety",
        "orchestrator.guardrails.audit",
        "orchestrator.guardrails.wrappers",
        "mcp_server",
        "mcp_servers.configured_tools_server",
        "mcp_servers.search_server",
    ]
    try:
        sys.argv = [sys.argv[0]]
        for module_name in modules:
            assert importlib.import_module(module_name) is not None
    finally:
        sys.argv = original_argv
        if original_payload is not None:
            os.environ["CONFIGURED_TOOLS_PAYLOAD"] = original_payload


def test_shared_contracts_round_trip_through_jsonable_payload():
    brief = ExecutionBrief(
        brief_id="brief_123",
        idea_id="idea_123",
        title="Repo-aware ICP finder",
        prd_summary="Turn founder repo history into a ranked opportunity dossier.",
        acceptance_criteria=["Stores ideas", "Exports typed handoff briefs"],
        risks=[
            RiskItem(
                category="technical",
                description="Repo digest can overfit to noisy repositories.",
                level=RiskLevel.MEDIUM,
                mitigation="Run the digest path before deep indexing.",
            )
        ],
        recommended_tech_stack=["FastAPI", "SQLite", "Next.js"],
        first_stories=[
            StoryDecompositionSeed(
                title="Discovery store",
                description="Persist ideas with lineage and evidence.",
                acceptance_criteria=["Stable IDs", "List endpoint", "Dossier endpoint"],
                effort=EffortEstimate.SMALL,
            )
        ],
        confidence=Confidence.HIGH,
    )

    payload = to_jsonable(brief)
    restored = from_jsonable(ExecutionBrief, payload)

    assert restored == brief
    assert payload["confidence"] == "high"
    assert payload["created_at"].endswith("+00:00")
