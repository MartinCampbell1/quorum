"""Blueprint-level topology optimizer for node and edge weighting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.debate.blueprints import ProtocolBlueprint
from orchestrator.topology.team_builder import DynamicTeamPlan, TeamStrategy


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


class WeightedNode(BaseModel):
    node_id: str
    label: str
    stage: str
    importance_weight: float = 0.5
    parallelizable: bool = False
    branch_candidate: bool = False
    reason: str = ""


class WeightedEdge(BaseModel):
    guard_id: str
    source_node_id: str
    target_node_id: str
    transition_weight: float = 0.5
    routing_bias: Literal["sequential", "parallel", "branch", "blackboard"] = "sequential"
    reason: str = ""


class GraphOptimizationResult(BaseModel):
    selected_template: TeamStrategy = "baseline"
    recommended_execution_mode: Literal["sequential", "parallel"] = "sequential"
    estimated_parallelism: int = 1
    branch_factor: int = 1
    blackboard_enabled: bool = False
    node_weights: list[WeightedNode] = Field(default_factory=list)
    edge_weights: list[WeightedEdge] = Field(default_factory=list)
    optimization_notes: list[str] = Field(default_factory=list)


def optimize_protocol_blueprint(
    blueprint: ProtocolBlueprint,
    team_plan: DynamicTeamPlan,
    selected_template: TeamStrategy,
    provider_diversity: int,
) -> GraphOptimizationResult:
    task_profile = team_plan.task_profile
    stage_weights = {
        "planning": 0.8,
        "generation": 0.74,
        "aggregation": 0.71,
        "execution": 0.69,
        "evaluation": 0.82,
        "synthesis": 0.78,
        "debate": 0.77,
        "judging": 0.81,
    }
    hot_tags = {tag for role in team_plan.role_recommendations for tag in role.expertise_tags}
    node_weights: list[WeightedNode] = []
    for node in blueprint.nodes:
        base = stage_weights.get(node.stage, 0.62)
        role_bonus = 0.02 * len([hint for hint in node.role_hints if any(role.role == hint for role in team_plan.role_recommendations)])
        if "synthesizer" in hot_tags and node.stage in {"aggregation", "synthesis"}:
            role_bonus += 0.05
        if "skeptic" in hot_tags and node.stage in {"evaluation", "debate"}:
            role_bonus += 0.06
        importance = round(_clamp(base + role_bonus + (task_profile.reasoning_depth * 0.08)), 4)
        parallelizable = node.stage in {"generation", "execution", "aggregation"} or "parallel" in node.label.lower()
        branch_candidate = task_profile.uncertainty >= 0.68 and node.stage in {"planning", "evaluation", "generation"}
        node_weights.append(
            WeightedNode(
                node_id=node.node_id,
                label=node.label,
                stage=node.stage,
                importance_weight=importance,
                parallelizable=parallelizable,
                branch_candidate=branch_candidate,
                reason=f"{node.stage} stage weighted for {selected_template} topology.",
            )
        )

    node_by_id = {item.node_id: item for item in node_weights}
    routing_bias: Literal["sequential", "parallel", "branch", "blackboard"] = "sequential"
    if selected_template == "parallel_fanout":
        routing_bias = "parallel"
    elif selected_template == "branch_merge":
        routing_bias = "branch"
    elif selected_template == "blackboard":
        routing_bias = "blackboard"

    edge_weights: list[WeightedEdge] = []
    for transition in blueprint.transitions:
        left = node_by_id.get(transition.source_node_id)
        right = node_by_id.get(transition.target_node_id)
        base = 0.54
        if left is not None:
            base += left.importance_weight * 0.18
        if right is not None:
            base += right.importance_weight * 0.18
        if routing_bias == "parallel" and left is not None and left.parallelizable:
            base += 0.1
        if routing_bias == "branch" and left is not None and left.branch_candidate:
            base += 0.12
        if routing_bias == "blackboard" and right is not None and right.stage in {"planning", "evaluation", "synthesis"}:
            base += 0.09
        edge_weights.append(
            WeightedEdge(
                guard_id=transition.guard_id,
                source_node_id=transition.source_node_id,
                target_node_id=transition.target_node_id,
                transition_weight=round(_clamp(base), 4),
                routing_bias=routing_bias,
                reason=transition.description or f"Weighted for {selected_template} routing.",
            )
        )

    estimated_parallelism = 1
    if selected_template in {"parallel_fanout", "branch_merge", "blackboard"}:
        estimated_parallelism = max(1, min(4, max(provider_diversity, team_plan.branch_factor)))

    notes = [
        f"Selected template={selected_template}.",
        f"Estimated parallelism={estimated_parallelism}.",
        f"Top uncertainty={task_profile.uncertainty:.2f}, coordination={task_profile.coordination_need:.2f}.",
    ]
    if selected_template == "blackboard":
        notes.append("Blackboard mode keeps planning/evaluation nodes hot so opportunistic specialists can contribute.")
    elif selected_template == "branch_merge":
        notes.append("Branch-and-merge keeps planning and evaluation lanes weighted to preserve alternatives longer.")

    return GraphOptimizationResult(
        selected_template=selected_template,
        recommended_execution_mode=task_profile.recommended_execution_mode,
        estimated_parallelism=estimated_parallelism,
        branch_factor=team_plan.branch_factor,
        blackboard_enabled=(selected_template == "blackboard"),
        node_weights=node_weights,
        edge_weights=edge_weights,
        optimization_notes=notes,
    )


def apply_graph_optimization(
    blueprint: ProtocolBlueprint,
    optimization: GraphOptimizationResult,
) -> ProtocolBlueprint:
    optimized = blueprint.model_copy(deep=True)
    planner_hints = dict(optimized.planner_hints or {})
    planner_hints["topology"] = optimization.model_dump()
    optimized.planner_hints = planner_hints
    optimized.notes = list(optimized.notes) + list(optimization.optimization_notes)
    return optimized
