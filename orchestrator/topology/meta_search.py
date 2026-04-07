"""Meta-search over bounded topology templates, roles, and routing plans."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.debate.blueprints import ProtocolBlueprint
from orchestrator.topology.dynamic_routing import DynamicRoutingPlan, build_dynamic_routing_plan
from orchestrator.topology.graph_optimizer import GraphOptimizationResult, optimize_protocol_blueprint
from orchestrator.topology.team_builder import DynamicTeamPlan, TaskDomainProfile, TeamStrategy, build_dynamic_team


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


class MetaSearchCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: f"topo_{uuid.uuid4().hex[:12]}")
    template: TeamStrategy
    score: float
    recommended_execution_mode: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    estimated_parallelism: int = 1


class MetaTopologyState(BaseModel):
    search_id: str = Field(default_factory=lambda: f"search_{uuid.uuid4().hex[:12]}")
    generated_at: float = Field(default_factory=time.time)
    class_key: str
    selected_template: TeamStrategy
    selected_execution_mode: str
    chosen_reason: str
    task_profile: TaskDomainProfile
    team_plan: DynamicTeamPlan
    graph_optimization: GraphOptimizationResult
    routing_plan: DynamicRoutingPlan
    candidates: list[MetaSearchCandidate] = Field(default_factory=list)


def _class_key(mode: str, task_profile: TaskDomainProfile, scenario_id: str | None) -> str:
    scenario = str(scenario_id or "default").strip().lower() or "default"
    return f"{mode}:{scenario}:{task_profile.domain_key}:{task_profile.complexity}"


def _candidate_templates(mode: str, team_plan: DynamicTeamPlan) -> list[TeamStrategy]:
    templates: list[TeamStrategy] = ["baseline"]
    if mode in {"tournament", "map_reduce", "moa"} or team_plan.task_profile.recommended_execution_mode == "parallel":
        templates.append("parallel_fanout")
    if team_plan.task_profile.uncertainty >= 0.62:
        templates.append("branch_merge")
    if team_plan.task_profile.coordination_need >= 0.72 or team_plan.blackboard_enabled:
        templates.append("blackboard")
    templates.append(team_plan.strategy)
    return list(dict.fromkeys(templates))


def _score_candidate(
    template: TeamStrategy,
    mode: str,
    team_plan: DynamicTeamPlan,
) -> tuple[float, list[str], list[str], int]:
    task_profile = team_plan.task_profile
    unique_tools = {
        tool
        for role in [*team_plan.role_recommendations, *team_plan.suggested_roles]
        for tool in role.tools
    }
    provider_diversity = len({role.provider for role in team_plan.role_recommendations if role.provider})
    average_importance = (
        sum(role.importance_score for role in team_plan.role_recommendations) / max(len(team_plan.role_recommendations), 1)
    )
    average_believability = (
        sum(role.believability_score for role in team_plan.role_recommendations) / max(len(team_plan.role_recommendations), 1)
    )

    score = 0.34 + (average_importance * 0.16) + (average_believability * 0.16)
    score += min(len(unique_tools), 6) / 6.0 * 0.08
    score += min(provider_diversity, 3) / 3.0 * 0.08
    strengths: list[str] = []
    risks: list[str] = []

    if template == team_plan.strategy:
        score += 0.12
        strengths.append("Matches the task-derived team strategy.")
    if template == "parallel_fanout":
        score += 0.08 if mode in {"tournament", "map_reduce", "moa"} else 0.03
        score += task_profile.coordination_need * 0.08
        strengths.append("Improves throughput on parallel-safe stages.")
        if provider_diversity < 2:
            risks.append("Low provider diversity limits the value of parallel fan-out.")
    elif template == "branch_merge":
        score += task_profile.uncertainty * 0.12
        score += task_profile.reasoning_depth * 0.06
        strengths.append("Keeps alternative strategic lines alive before merge.")
        if task_profile.delivery_pressure >= 0.72:
            risks.append("Branching can slow down urgent delivery loops.")
    elif template == "blackboard":
        score += task_profile.coordination_need * 0.12
        score += min(len(team_plan.suggested_roles), 3) * 0.03
        strengths.append("Lets specialists contribute opportunistically through a shared plan.")
        if len(team_plan.suggested_roles) == 0:
            risks.append("Blackboard mode is weaker when the team lacks differentiated specialists.")
    else:
        score += (1.0 - abs(task_profile.delivery_pressure - 0.5)) * 0.04
        strengths.append("Stable baseline with low coordination overhead.")

    estimated_parallelism = 1
    if template in {"parallel_fanout", "branch_merge", "blackboard"}:
        estimated_parallelism = max(1, min(4, max(provider_diversity, team_plan.branch_factor)))
    return round(_clamp(score), 4), strengths, risks, estimated_parallelism


def run_meta_agent_search(
    mode: str,
    task: str,
    agents: list[Any],
    config: dict[str, Any] | None,
    blueprint: ProtocolBlueprint,
    provider_capabilities_snapshot: dict[str, Any] | None = None,
    scenario_id: str | None = None,
) -> MetaTopologyState:
    team_plan = build_dynamic_team(mode, task, agents, config, provider_capabilities_snapshot)
    candidates: list[MetaSearchCandidate] = []
    for template in _candidate_templates(mode, team_plan):
        score, strengths, risks, estimated_parallelism = _score_candidate(template, mode, team_plan)
        candidates.append(
            MetaSearchCandidate(
                template=template,
                score=score,
                recommended_execution_mode=team_plan.task_profile.recommended_execution_mode,
                strengths=strengths,
                risks=risks,
                estimated_parallelism=estimated_parallelism,
            )
        )
    candidates.sort(key=lambda item: (item.score, item.estimated_parallelism), reverse=True)
    winner = candidates[0]
    graph_optimization = optimize_protocol_blueprint(
        blueprint,
        team_plan,
        selected_template=winner.template,
        provider_diversity=len({role.provider for role in team_plan.role_recommendations if role.provider}),
    )
    routing_plan = build_dynamic_routing_plan(blueprint, team_plan, graph_optimization)
    class_key = _class_key(mode, team_plan.task_profile, scenario_id)
    return MetaTopologyState(
        class_key=class_key,
        selected_template=winner.template,
        selected_execution_mode=winner.recommended_execution_mode,
        chosen_reason="; ".join(winner.strengths[:2]) or f"Highest heuristic score for {winner.template}.",
        task_profile=team_plan.task_profile,
        team_plan=team_plan,
        graph_optimization=graph_optimization,
        routing_plan=routing_plan,
        candidates=candidates,
    )
