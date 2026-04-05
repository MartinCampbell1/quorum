"""Dynamic routing and branch planning for topology-aware sessions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from orchestrator.debate.blueprints import ProtocolBlueprint
from orchestrator.topology.graph_optimizer import GraphOptimizationResult
from orchestrator.topology.team_builder import DynamicTeamPlan


class BranchLine(BaseModel):
    branch_id: str
    focus: str
    owner_roles: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    merge_node_id: str | None = None


class DynamicRoutingPlan(BaseModel):
    route_family: str
    recommended_execution_mode: str
    branch_merge_enabled: bool = False
    blackboard_enabled: bool = False
    route_reasons: list[str] = Field(default_factory=list)
    opportunistic_roles: list[str] = Field(default_factory=list)
    branch_lines: list[BranchLine] = Field(default_factory=list)


def build_dynamic_routing_plan(
    blueprint: ProtocolBlueprint,
    team_plan: DynamicTeamPlan,
    optimization: GraphOptimizationResult,
) -> DynamicRoutingPlan:
    synthesis_node = next(
        (node.node_id for node in blueprint.nodes if node.stage in {"synthesis", "evaluation"}),
        blueprint.entry_node_id,
    )
    branch_lines: list[BranchLine] = []
    role_names = [role.role for role in team_plan.role_recommendations]
    suggested_names = [role.role for role in team_plan.suggested_roles]

    if optimization.selected_template == "branch_merge":
        branch_lines = [
            BranchLine(
                branch_id="branch_risk",
                focus="stress-test risk and objections",
                owner_roles=[role for role in role_names if any(token in role for token in ("critic", "judge", "skeptic"))] or role_names[:1],
                target_node_ids=[node.node_id for node in blueprint.nodes if node.stage in {"planning", "evaluation"}],
                merge_node_id=synthesis_node,
            ),
            BranchLine(
                branch_id="branch_distribution",
                focus="stress-test distribution and buyer wedge",
                owner_roles=[role for role in role_names if any(token in role for token in ("director", "aggregator", "planner"))] or role_names[-1:],
                target_node_ids=[node.node_id for node in blueprint.nodes if node.stage in {"planning", "generation", "execution"}],
                merge_node_id=synthesis_node,
            ),
        ]
    elif optimization.selected_template == "blackboard":
        branch_lines = [
            BranchLine(
                branch_id="board_opportunistic",
                focus="allow specialists to write into a shared blackboard before synthesis",
                owner_roles=role_names[: max(1, min(3, len(role_names)))],
                target_node_ids=[node.node_id for node in blueprint.nodes if node.stage in {"planning", "execution", "evaluation"}],
                merge_node_id=synthesis_node,
            )
        ]

    reasons = [
        f"Template {optimization.selected_template} matches task profile {team_plan.task_profile.domain_key}/{team_plan.task_profile.complexity}.",
        f"Execution recommendation={optimization.recommended_execution_mode}.",
    ]
    if branch_lines:
        reasons.append("Branch lines are bounded and merge back into the blueprint instead of forking unbounded graphs.")

    opportunistic_roles = [
        role.role
        for role in team_plan.suggested_roles
        if any(tag in {"research", "skeptic", "distribution", "builder"} for tag in role.expertise_tags)
    ]
    if optimization.selected_template == "blackboard":
        opportunistic_roles = list(dict.fromkeys([*opportunistic_roles, *suggested_names]))

    return DynamicRoutingPlan(
        route_family=optimization.selected_template,
        recommended_execution_mode=optimization.recommended_execution_mode,
        branch_merge_enabled=optimization.selected_template == "branch_merge",
        blackboard_enabled=optimization.blackboard_enabled,
        route_reasons=reasons,
        opportunistic_roles=opportunistic_roles,
        branch_lines=branch_lines,
    )
