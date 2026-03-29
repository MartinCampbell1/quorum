"""Execution brief schema and synthesis helpers for Quorum -> Autopilot handoff."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.modes.base import call_agent, strip_markdown_fence
from orchestrator.models import AgentConfig
from orchestrator.scenarios import get_scenario

DEFAULT_AUTOPILOT_API_BASE = "http://127.0.0.1:8420/api"


class FounderContext(BaseModel):
    mode: str = "solo_ai_augmented"
    strengths: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    unfair_advantages: list[str] = Field(default_factory=list)
    available_capital_usd: int | None = None
    weekly_hours: int | None = None


class MarketContext(BaseModel):
    icp: str = ""
    pain: str = ""
    why_now: str = ""
    wedge: str = ""


class ExecutionContext(BaseModel):
    mvp_scope: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    existing_repos: list[str] = Field(default_factory=list)


class MonetizationContext(BaseModel):
    revenue_model: str = ""
    pricing_hint: str = ""
    time_to_first_dollar: str = ""


class EvaluationContext(BaseModel):
    success_metrics: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    major_risks: list[str] = Field(default_factory=list)


class ProvenanceContext(BaseModel):
    source_system: str = "quorum"
    source_session_id: str = ""
    source_mode: str = ""
    source_scenario_id: str = ""
    ranking_rationale: str = ""


class ExecutionBrief(BaseModel):
    version: str = "1.0"
    title: str
    thesis: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    founder: FounderContext = Field(default_factory=FounderContext)
    market: MarketContext = Field(default_factory=MarketContext)
    execution: ExecutionContext = Field(default_factory=ExecutionContext)
    monetization: MonetizationContext = Field(default_factory=MonetizationContext)
    evaluation: EvaluationContext = Field(default_factory=EvaluationContext)
    provenance: ProvenanceContext = Field(default_factory=ProvenanceContext)


class ExecutionBriefExportRequest(BaseModel):
    provider: str | None = None


class AutopilotLaunchProfile(BaseModel):
    preset: str = "fast"
    story_execution_mode: str | None = None
    project_concurrency_mode: str | None = None
    max_parallel_stories: int | None = None


class AutopilotLaunchPreset(BaseModel):
    id: str
    label: str
    description: str = ""
    launch_profile: AutopilotLaunchProfile


class SendExecutionBriefRequest(ExecutionBriefExportRequest):
    autopilot_url: str = DEFAULT_AUTOPILOT_API_BASE
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: AutopilotLaunchProfile | None = None


class TournamentCandidate(BaseModel):
    label: str
    thesis: str
    rationale: str = ""
    source_workspace_path: str
    tags: list[str] = Field(default_factory=list)


class TournamentPreparation(BaseModel):
    version: str = "1.0"
    title: str
    scenario_id: str = "project_tournament"
    mode: str = "tournament"
    task: str
    recommended_max_rounds: int = 3
    recommended_execution_mode: str = "sequential"
    contestants: list[TournamentCandidate] = Field(default_factory=list)
    agents: list[AgentConfig] = Field(default_factory=list)
    workspace_paths: list[str] = Field(default_factory=list)


class TournamentPreparationRequest(BaseModel):
    provider: str | None = None


def _compact(text: str | None, limit: int = 900) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _preferred_provider(session: dict, requested: str | None = None) -> str:
    if requested and str(requested).strip():
        return str(requested).strip().lower()
    agents = list(session.get("agents") or [])
    for preferred_role in ("judge", "chairman", "director", "planner"):
        for agent in agents:
            if str(agent.get("role") or "").strip().lower() == preferred_role:
                provider = str(agent.get("provider") or "").strip().lower()
                if provider:
                    return provider
    for agent in agents:
        provider = str(agent.get("provider") or "").strip().lower()
        if provider:
            return provider
    return "codex"


def _session_context_packet(session: dict) -> str:
    messages = list(session.get("messages") or [])
    selected: list[dict[str, Any]] = [
        message
        for message in messages
        if str(message.get("phase") or "").strip().lower() in {
            "verdict",
            "champion",
            "match_complete",
            "chairman_decision",
            "synthesis",
            "done",
        }
    ]
    if not selected:
        selected = messages[-8:]
    else:
        selected = selected[-10:]

    message_lines = []
    for message in selected:
        agent = str(message.get("agent_id") or "system").strip()
        phase = str(message.get("phase") or "").strip() or "message"
        message_lines.append(f"- {agent} [{phase}]: {_compact(message.get('content'))}")

    task = _compact(session.get("task"), 2000)
    result = _compact(session.get("result"), 3000)
    scenario_id = str(session.get("active_scenario") or "").strip()
    workspace_paths = [str(path).strip() for path in list(session.get("workspace_paths") or []) if str(path).strip()]

    lines = [
        f"Session id: {session.get('id', '')}",
        f"Mode: {session.get('mode', '')}",
        f"Scenario: {scenario_id or 'none'}",
        f"Status: {session.get('status', '')}",
        f"Task:\n{task}",
        "",
        f"Final result / outcome:\n{result}",
        "",
        "Workspace paths:",
    ]
    if workspace_paths:
        lines.extend(f"- {path}" for path in workspace_paths)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Key conversation excerpts:",
        ]
    )
    lines.extend(message_lines or ["- none"])
    return "\n".join(lines)


def _session_workspace_paths(session: dict) -> list[str]:
    direct = [str(path).strip() for path in list(session.get("workspace_paths") or []) if str(path).strip()]
    per_agent = [
        str(path).strip()
        for agent in list(session.get("agents") or [])
        for path in list(agent.get("workspace_paths") or [])
        if str(path).strip()
    ]
    return list(dict.fromkeys([*direct, *per_agent]))


def _brief_prompt(context: str, scenario_id: str = "") -> str:
    strengthening_rules = ""
    normalized_scenario = str(scenario_id or "").strip().lower()
    if normalized_scenario == "project_strengthening_lab":
        strengthening_rules = (
            "- Treat the strongest recommendation as a strengthening plan for an already-promising product, not as a fresh pivot.\n"
            "- Preserve the core product unless the session explicitly concluded that a deeper pivot is required.\n"
            "- MVP scope should focus on the first strengthening wedge: monetization fix, packaging, growth loop, onboarding, pricing, or execution bottleneck removal.\n"
            "- existing_repos should prioritize the concrete repo roots discussed in the strengthening session.\n"
        )
    return (
        "Convert this orchestration session into an execution-ready brief for an autonomous build system.\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "version": "1.0",\n'
        '  "title": "project title",\n'
        '  "thesis": "one-sentence thesis",\n'
        '  "summary": "one concise paragraph",\n'
        '  "tags": ["tag"],\n'
        '  "founder": {"mode": "solo_ai_augmented", "strengths": [], "interests": [], "constraints": [], "unfair_advantages": [], "available_capital_usd": null, "weekly_hours": null},\n'
        '  "market": {"icp": "", "pain": "", "why_now": "", "wedge": ""},\n'
        '  "execution": {"mvp_scope": [], "non_goals": [], "required_capabilities": [], "required_connectors": [], "existing_repos": []},\n'
        '  "monetization": {"revenue_model": "", "pricing_hint": "", "time_to_first_dollar": ""},\n'
        '  "evaluation": {"success_metrics": [], "kill_criteria": [], "open_questions": [], "major_risks": []},\n'
        '  "provenance": {"source_system": "quorum", "source_session_id": "", "source_mode": "", "source_scenario_id": "", "ranking_rationale": ""}\n'
        "}\n\n"
        "Rules:\n"
        "- Focus on the single strongest initiative recommended by the session.\n"
        "- If the session names a winner, champion, or preferred direction, center the brief on that.\n"
        "- Do not invent traction, users, or proof that does not appear in the session.\n"
        "- Keep execution grounded and MVP-scoped.\n"
        "- existing_repos should include any attached workspace paths when relevant.\n"
        "- required_connectors should only include connectors that are concretely implied by the work.\n\n"
        f"{strengthening_rules}"
        f"SESSION PACK:\n{context}"
    )


def _tournament_prep_prompt(context: str, workspace_paths: list[str]) -> str:
    workspace_lines = "\n".join(f"- {path}" for path in workspace_paths) or "- none"
    return (
        "Convert this session into a tournament-ready shortlist for FounderOS.\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "version": "1.0",\n'
        '  "title": "short title",\n'
        '  "scenario_id": "project_tournament",\n'
        '  "mode": "tournament",\n'
        '  "task": "full tournament task text",\n'
        '  "recommended_max_rounds": 3,\n'
        '  "recommended_execution_mode": "sequential",\n'
        '  "contestants": [\n'
        '    {"label": "", "thesis": "", "rationale": "", "source_workspace_path": "", "tags": []}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Choose the strongest 2 to 8 candidates from the session.\n"
        "- Each candidate must be a `project + pivot` framing, not just a raw repo name.\n"
        "- Each candidate MUST use source_workspace_path exactly from the available workspace path list below.\n"
        "- You may reuse the same workspace path for multiple pivots if the session clearly supports that.\n"
        "- recommended_max_rounds should usually be 2 or 3, not 5.\n"
        "- recommended_execution_mode should default to sequential unless parallel is clearly justified.\n"
        "- task must explicitly ask the tournament to compare these candidates for a solo founder with a strong AI stack.\n"
        "- task should ask for: winner, second place, what to freeze, and why.\n"
        "- Do not invent repos or workspace paths that are not present below.\n\n"
        f"AVAILABLE WORKSPACE PATHS:\n{workspace_lines}\n\n"
        f"SESSION PACK:\n{context}"
    )


def _build_tournament_agents(preparation: TournamentPreparation) -> list[AgentConfig]:
    scenario = get_scenario("project_tournament") or {}
    defaults = list(scenario.get("default_agents") or [])
    contestant_templates = [agent for agent in defaults if str(agent.role).startswith("contestant_")]
    judge_template = next((agent for agent in defaults if agent.role == "judge"), None)

    agents: list[AgentConfig] = []
    for index, contestant in enumerate(preparation.contestants, start=1):
        template = contestant_templates[(index - 1) % max(len(contestant_templates), 1)] if contestant_templates else AgentConfig(
            role=f"contestant_{index}",
            provider="codex",
            tools=["web_search", "code_exec", "shell_exec"],
        )
        system_prompt = (
            "You represent a pivoted tournament candidate, not the raw repository in isolation.\n"
            f"Candidate label: {contestant.label}\n"
            f"Pivot thesis: {contestant.thesis}\n"
            f"Rationale: {contestant.rationale}\n"
            f"Primary workspace root for this candidate: {contestant.source_workspace_path}\n"
            "Defend this specific pivot and explain why it is the stronger founder-fit direction."
        )
        agents.append(
            AgentConfig(
                role=f"contestant_{index}",
                provider=template.provider,
                system_prompt=system_prompt,
                tools=list(template.tools),
                workspace_paths=[contestant.source_workspace_path],
            )
        )

    if judge_template is None:
        judge_template = AgentConfig(role="judge", provider="gemini", tools=["web_search", "perplexity", "http_request"])
    agents.append(
        AgentConfig(
            role="judge",
            provider=judge_template.provider,
            system_prompt=judge_template.system_prompt,
            tools=list(judge_template.tools),
            workspace_paths=[],
        )
    )
    return agents


def generate_session_tournament_preparation(session: dict, provider: str | None = None) -> TournamentPreparation:
    workspace_paths = _session_workspace_paths(session)
    if len(workspace_paths) < 2:
        raise ValueError("Tournament preparation requires at least two attached workspace paths in the source session.")

    resolved_provider = _preferred_provider(session, provider)
    context = _session_context_packet(session)
    raw = call_agent(
        resolved_provider,
        _tournament_prep_prompt(context, workspace_paths),
        system_prompt="You produce strict JSON tournament preparation payloads. No markdown fences, no commentary.",
        session_id=str(session.get("id") or "").strip() or None,
        agent_role="tournament_preparation_exporter",
    )
    try:
        payload = json.loads(strip_markdown_fence(raw))
        preparation = TournamentPreparation.model_validate(payload)
    except Exception as exc:  # pragma: no cover - defensive validation
        raise ValueError(f"Tournament preparation export failed: {exc}. Raw output: {_compact(raw, 800)}") from exc

    allowed_paths = set(workspace_paths)
    filtered: list[TournamentCandidate] = []
    for contestant in preparation.contestants:
        if contestant.source_workspace_path not in allowed_paths:
            continue
        if not contestant.label.strip() or not contestant.thesis.strip():
            continue
        filtered.append(contestant)

    if len(filtered) < 2:
        raise ValueError("Tournament preparation did not produce at least two valid contestants bound to attached workspaces.")

    preparation.contestants = filtered[:8]
    preparation.recommended_max_rounds = min(max(int(preparation.recommended_max_rounds or 3), 1), 5)
    preparation.recommended_execution_mode = (
        "parallel" if str(preparation.recommended_execution_mode).strip().lower() == "parallel" else "sequential"
    )
    preparation.workspace_paths = list(dict.fromkeys(contestant.source_workspace_path for contestant in preparation.contestants))
    preparation.agents = _build_tournament_agents(preparation)
    return preparation


def generate_session_execution_brief(session: dict, provider: str | None = None) -> ExecutionBrief:
    resolved_provider = _preferred_provider(session, provider)
    context = _session_context_packet(session)
    scenario_id = str(session.get("active_scenario") or "").strip()
    raw = call_agent(
        resolved_provider,
        _brief_prompt(context, scenario_id),
        system_prompt="You produce execution briefs as strict JSON. No markdown fences, no commentary.",
        session_id=str(session.get("id") or "").strip() or None,
        agent_role="execution_brief_exporter",
    )
    try:
        payload = json.loads(strip_markdown_fence(raw))
        brief = ExecutionBrief.model_validate(payload)
    except Exception as exc:  # pragma: no cover - defensive validation
        raise ValueError(f"Execution brief export failed: {exc}. Raw output: {_compact(raw, 800)}") from exc

    if not brief.execution.existing_repos:
        brief.execution.existing_repos = [
            str(path).strip()
            for path in list(session.get("workspace_paths") or [])
            if str(path).strip()
        ]
    brief.provenance.source_system = "quorum"
    brief.provenance.source_session_id = str(session.get("id") or "")
    brief.provenance.source_mode = str(session.get("mode") or "")
    brief.provenance.source_scenario_id = str(session.get("active_scenario") or "")
    return brief
