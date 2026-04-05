"""Heuristic dynamic-team builder for topology-aware Quorum sessions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaskComplexity = Literal["low", "medium", "high", "frontier"]
TopologyExecutionMode = Literal["sequential", "parallel"]
TeamStrategy = Literal["baseline", "parallel_fanout", "branch_merge", "blackboard"]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _task_text(mode: str, task: str, config: dict[str, Any]) -> str:
    parts = [mode, task, str(config.get("protocol") or ""), str(config.get("task_class") or "")]
    return " ".join(part for part in parts if str(part).strip()).lower()


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


class TaskDomainProfile(BaseModel):
    domain_key: str = "general"
    complexity: TaskComplexity = "medium"
    uncertainty: float = 0.5
    coordination_need: float = 0.5
    delivery_pressure: float = 0.4
    reasoning_depth: float = 0.5
    recommended_execution_mode: TopologyExecutionMode = "sequential"
    specializations: list[str] = Field(default_factory=list)
    evidence_bias: float = 0.5


class TeamRoleRecommendation(BaseModel):
    role: str
    provider: str
    tools: list[str] = Field(default_factory=list)
    expertise_tags: list[str] = Field(default_factory=list)
    importance_score: float = 0.5
    believability_score: float = 0.5
    origin: Literal["existing", "suggested"] = "existing"
    rationale: str = ""


class DynamicTeamPlan(BaseModel):
    strategy: TeamStrategy = "baseline"
    quorum_size: int = 1
    branch_factor: int = 1
    blackboard_enabled: bool = False
    task_profile: TaskDomainProfile
    role_recommendations: list[TeamRoleRecommendation] = Field(default_factory=list)
    suggested_roles: list[TeamRoleRecommendation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def infer_task_profile(mode: str, task: str, config: dict[str, Any] | None = None) -> TaskDomainProfile:
    normalized_config = dict(config or {})
    text = _task_text(mode, task, normalized_config)

    domain = "general"
    if _has_any(text, ("security", "threat", "soc2", "vulnerability")):
        domain = "security"
    elif _has_any(text, ("compliance", "audit", "regulatory", "governance")):
        domain = "compliance"
    elif _has_any(text, ("market", "growth", "sales", "distribution", "buyer", "pricing")):
        domain = "go_to_market"
    elif _has_any(text, ("repo", "code", "sdk", "developer", "api", "tooling")):
        domain = "developer_tooling"
    elif _has_any(text, ("infra", "ops", "workflow", "incident", "platform")):
        domain = "operations"

    complexity = "medium"
    if _has_any(text, ("frontier", "research", "novel", "simulation", "multi-agent society")):
        complexity = "frontier"
    elif _has_any(text, ("graph", "optimizer", "topology", "compiler", "evolution", "orchestrator")):
        complexity = "high"
    elif _has_any(text, ("quick", "mvp", "small", "simple")):
        complexity = "low"

    uncertainty = 0.42
    if _has_any(text, ("explore", "unknown", "search", "debate", "tradeoff", "optimize", "rank")):
        uncertainty += 0.22
    if complexity in {"high", "frontier"}:
        uncertainty += 0.12

    coordination_need = 0.4
    if mode in {"board", "debate", "democracy", "tournament", "moa"}:
        coordination_need += 0.2
    if _has_any(text, ("parallel", "branch", "merge", "team", "council", "multi-step", "multi agent")):
        coordination_need += 0.2

    delivery_pressure = 0.35
    if _has_any(text, ("today", "urgent", "ship", "launch", "prod", "production")):
        delivery_pressure += 0.3
    if _has_any(text, ("mvp", "quick")):
        delivery_pressure += 0.12

    reasoning_depth = 0.45
    if mode in {"board", "debate", "creator_critic", "moa"}:
        reasoning_depth += 0.18
    if _has_any(text, ("why", "strategy", "thesis", "architecture", "root cause")):
        reasoning_depth += 0.15

    evidence_bias = 0.45
    if _has_any(text, ("evidence", "source", "fact", "validate", "benchmark", "data")):
        evidence_bias += 0.22

    recommended_execution_mode: TopologyExecutionMode = "sequential"
    if mode in {"tournament", "map_reduce"} or coordination_need >= 0.75:
        recommended_execution_mode = "parallel"

    specializations: list[str] = []
    if domain in {"security", "compliance"}:
        specializations.extend(["risk", domain])
    if domain in {"developer_tooling", "operations"}:
        specializations.extend(["builder", "operator"])
    if domain == "go_to_market":
        specializations.extend(["distribution", "buyer_research"])
    if uncertainty >= 0.62:
        specializations.append("skeptic")
    if reasoning_depth >= 0.62:
        specializations.append("synthesizer")

    return TaskDomainProfile(
        domain_key=domain,
        complexity=complexity,
        uncertainty=round(_clamp(uncertainty), 4),
        coordination_need=round(_clamp(coordination_need), 4),
        delivery_pressure=round(_clamp(delivery_pressure), 4),
        reasoning_depth=round(_clamp(reasoning_depth), 4),
        recommended_execution_mode=recommended_execution_mode,
        specializations=list(dict.fromkeys(specializations)),
        evidence_bias=round(_clamp(evidence_bias), 4),
    )


def _provider_believability(provider: str) -> float:
    return {
        "claude": 0.86,
        "codex": 0.83,
        "gemini": 0.78,
        "minimax": 0.67,
    }.get(str(provider or "").strip().lower(), 0.72)


def _role_tags(role: str, tools: list[str], task_profile: TaskDomainProfile) -> list[str]:
    normalized_role = role.lower()
    tags: list[str] = []
    if "judge" in normalized_role or "critic" in normalized_role or "skeptic" in normalized_role:
        tags.append("skeptic")
    if "planner" in normalized_role or "director" in normalized_role or "operator" in normalized_role:
        tags.append("operator")
    if "builder" in normalized_role or "worker" in normalized_role or "creator" in normalized_role:
        tags.append("builder")
    if "synth" in normalized_role or "aggregator" in normalized_role:
        tags.append("synthesizer")
    if any(tool in {"web_search", "perplexity", "http_request"} for tool in tools):
        tags.append("research")
    if any(tool in {"code_exec", "shell_exec"} for tool in tools):
        tags.append("implementation")
    if task_profile.domain_key in {"security", "compliance"} and "research" in tags:
        tags.append(task_profile.domain_key)
    if task_profile.domain_key == "go_to_market" and "research" in tags:
        tags.append("distribution")
    return list(dict.fromkeys(tags))


def _importance_score(role: str, tools: list[str], mode: str) -> float:
    normalized_role = role.lower()
    base = 0.46
    if any(marker in normalized_role for marker in ("judge", "final", "director", "planner", "synth")):
        base += 0.2
    if "worker" in normalized_role or "builder" in normalized_role or "creator" in normalized_role:
        base += 0.12
    if mode in {"debate", "board"} and ("judge" in normalized_role or "critic" in normalized_role):
        base += 0.08
    base += min(len(tools), 4) * 0.045
    if any(tool in {"code_exec", "shell_exec"} for tool in tools):
        base += 0.06
    return round(_clamp(base), 4)


def _suggested_role(
    role: str,
    provider_pool: list[str],
    expertise_tags: list[str],
    rationale: str,
) -> TeamRoleRecommendation:
    provider = provider_pool[0] if provider_pool else "claude"
    tools: list[str] = ["web_search"]
    if "builder" in expertise_tags:
        tools = ["code_exec", "shell_exec", "web_search"]
        provider = "codex" if "codex" in provider_pool else provider
    elif "distribution" in expertise_tags or "research" in expertise_tags:
        tools = ["web_search", "perplexity", "http_request"]
        provider = "gemini" if "gemini" in provider_pool else provider
    return TeamRoleRecommendation(
        role=role,
        provider=provider,
        tools=tools,
        expertise_tags=list(dict.fromkeys(expertise_tags)),
        importance_score=_importance_score(role, tools, "dictator"),
        believability_score=_provider_believability(provider),
        origin="suggested",
        rationale=rationale,
    )


def build_dynamic_team(
    mode: str,
    task: str,
    agents: list[Any],
    config: dict[str, Any] | None = None,
    provider_capabilities_snapshot: dict[str, Any] | None = None,
) -> DynamicTeamPlan:
    task_profile = infer_task_profile(mode, task, config)
    normalized_config = dict(config or {})
    provider_pool = list(
        dict.fromkeys(
            [
                str(getattr(agent, "provider", "") or (agent.get("provider", "") if isinstance(agent, dict) else "")).strip()
                for agent in agents
                if str(getattr(agent, "provider", "") or (agent.get("provider", "") if isinstance(agent, dict) else "")).strip()
            ]
        )
    )
    role_recommendations: list[TeamRoleRecommendation] = []
    seen_tags: set[str] = set()

    for agent in agents:
        role = str(getattr(agent, "role", "") or (agent.get("role", "") if isinstance(agent, dict) else "")).strip() or "agent"
        provider = str(getattr(agent, "provider", "") or (agent.get("provider", "") if isinstance(agent, dict) else "")).strip() or "unknown"
        tools = list(getattr(agent, "tools", None) or (agent.get("tools", []) if isinstance(agent, dict) else []))
        tags = _role_tags(role, tools, task_profile)
        seen_tags.update(tags)
        role_recommendations.append(
            TeamRoleRecommendation(
                role=role,
                provider=provider,
                tools=tools,
                expertise_tags=tags,
                importance_score=_importance_score(role, tools, mode),
                believability_score=_provider_believability(provider),
                rationale=f"{role} contributes {', '.join(tags) or 'general'} coverage.",
            )
        )

    suggested_roles: list[TeamRoleRecommendation] = []
    missing_specs = [spec for spec in task_profile.specializations if spec not in seen_tags]
    if "research" not in seen_tags and task_profile.evidence_bias >= 0.6:
        missing_specs.append("research")
    if "builder" not in seen_tags and task_profile.domain_key in {"developer_tooling", "operations"}:
        missing_specs.append("builder")

    for specialization in list(dict.fromkeys(missing_specs)):
        if specialization == "skeptic":
            suggested_roles.append(
                _suggested_role(
                    "skeptic_reviewer",
                    provider_pool,
                    ["skeptic", task_profile.domain_key],
                    "High-uncertainty work benefits from an explicit contradiction seeker.",
                )
            )
        elif specialization in {"distribution", "buyer_research"}:
            suggested_roles.append(
                _suggested_role(
                    "market_probe",
                    provider_pool,
                    ["distribution", "research"],
                    "Go-to-market tasks need a dedicated distribution and buyer signal owner.",
                )
            )
        elif specialization == "builder":
            suggested_roles.append(
                _suggested_role(
                    "implementation_probe",
                    provider_pool,
                    ["builder", "implementation"],
                    "Code-heavy tasks need an execution-oriented agent in the topology.",
                )
            )
        elif specialization in {"risk", "security", "compliance"}:
            suggested_roles.append(
                _suggested_role(
                    "risk_auditor",
                    provider_pool,
                    ["skeptic", specialization],
                    "Regulated or risk-heavy tasks need a dedicated constraint owner.",
                )
            )
        elif specialization == "operator":
            suggested_roles.append(
                _suggested_role(
                    "workflow_operator",
                    provider_pool,
                    ["operator", "research"],
                    "A workflow owner reduces coordination leakage across branches.",
                )
            )
        elif specialization == "synthesizer":
            suggested_roles.append(
                _suggested_role(
                    "merge_editor",
                    provider_pool,
                    ["synthesizer"],
                    "Multiple lines of work need an explicit merge and arbitration owner.",
                )
            )
        elif specialization == "research":
            suggested_roles.append(
                _suggested_role(
                    "research_probe",
                    provider_pool,
                    ["research"],
                    "The current team lacks explicit external evidence gathering coverage.",
                )
            )

    provider_diversity = len(provider_pool)
    strategy: TeamStrategy = "baseline"
    if bool(normalized_config.get("blackboard_mode")):
        strategy = "blackboard"
    elif task_profile.coordination_need >= 0.78 and (len(role_recommendations) + len(suggested_roles)) >= 4:
        strategy = "blackboard"
    elif task_profile.uncertainty >= 0.72 and provider_diversity >= 2:
        strategy = "branch_merge"
    elif task_profile.recommended_execution_mode == "parallel" or mode in {"tournament", "map_reduce", "moa"}:
        strategy = "parallel_fanout"

    quorum_size = max(1, min(len(role_recommendations), max(3, len(role_recommendations) // 2 + 1)))
    branch_factor = 1
    if strategy == "parallel_fanout":
        branch_factor = max(2, min(4, provider_diversity or len(role_recommendations)))
    elif strategy in {"branch_merge", "blackboard"}:
        branch_factor = max(2, min(3, len(role_recommendations) + len(suggested_roles)))

    notes = [
        f"Task profile inferred as {task_profile.domain_key} / {task_profile.complexity}.",
        f"Provider diversity={provider_diversity}, strategy={strategy}.",
    ]
    if suggested_roles:
        notes.append("Dynamic-team suggestions fill expertise gaps instead of replacing the current team.")
    if provider_capabilities_snapshot:
        notes.append("Provider capability snapshot was considered when scoring team believability.")

    return DynamicTeamPlan(
        strategy=strategy,
        quorum_size=quorum_size,
        branch_factor=branch_factor,
        blackboard_enabled=(strategy == "blackboard"),
        task_profile=task_profile,
        role_recommendations=role_recommendations,
        suggested_roles=suggested_roles,
        notes=notes,
    )
