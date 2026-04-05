"""Regression coverage for topology meta-search and blueprint optimization."""

from orchestrator.debate.blueprints import ProtocolBlueprint, StateNode, TransitionGuard
from orchestrator.topology.graph_optimizer import apply_graph_optimization
from orchestrator.topology.meta_search import run_meta_agent_search
from orchestrator.topology.team_builder import build_dynamic_team, infer_task_profile


def _blueprint() -> ProtocolBlueprint:
    return ProtocolBlueprint(
        cache_key="pb_test",
        mode="board",
        mode_family="consensus",
        protocol_key="standard",
        blueprint_class="consensus.board",
        entry_node_id="plan",
        nodes=[
            StateNode(node_id="plan", label="Plan", stage="planning", purpose="Plan"),
            StateNode(node_id="evaluate", label="Evaluate", stage="evaluation", purpose="Evaluate"),
            StateNode(node_id="synthesize", label="Synthesize", stage="synthesis", purpose="Synthesize"),
        ],
        transitions=[
            TransitionGuard(source_node_id="plan", target_node_id="evaluate", description="plan -> evaluate"),
            TransitionGuard(source_node_id="evaluate", target_node_id="synthesize", description="evaluate -> synthesize"),
        ],
        notes=[],
        planner_hints={},
    )


def test_task_profile_detects_high_coordination_topology_work():
    profile = infer_task_profile(
        "board",
        "Optimize a multi-agent topology with branch merge, evidence ranking, and blackboard coordination.",
        {},
    )

    assert profile.complexity in {"high", "frontier"}
    assert profile.coordination_need >= 0.6
    assert profile.uncertainty >= 0.6


def test_dynamic_team_suggests_missing_specialists():
    team = build_dynamic_team(
        "board",
        "Explore security and distribution tradeoffs before launch.",
        [
            {"role": "director", "provider": "claude", "tools": ["web_search"]},
            {"role": "builder", "provider": "codex", "tools": ["code_exec", "shell_exec"]},
        ],
        {},
    )

    assert team.role_recommendations
    assert team.suggested_roles
    assert any(role.role in {"risk_auditor", "market_probe", "skeptic_reviewer"} for role in team.suggested_roles)


def test_meta_search_embeds_topology_hints_into_blueprint():
    blueprint = _blueprint()
    topology = run_meta_agent_search(
        "board",
        "Explore architecture tradeoffs with blackboard coordination and branch merge.",
        [
            {"role": "director_1", "provider": "claude", "tools": ["web_search", "perplexity"]},
            {"role": "director_2", "provider": "codex", "tools": ["code_exec", "shell_exec"]},
            {"role": "director_3", "provider": "gemini", "tools": ["web_search", "http_request"]},
        ],
        {},
        blueprint,
    )
    optimized = apply_graph_optimization(blueprint, topology.graph_optimization)

    assert topology.candidates
    assert topology.selected_template in {"baseline", "parallel_fanout", "branch_merge", "blackboard"}
    assert optimized.planner_hints["topology"]["selected_template"] == topology.selected_template
    assert optimized.planner_hints["topology"]["node_weights"]
