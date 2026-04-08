"""FastAPI router for orchestration endpoints."""

import asyncio
import json
import shlex
import uuid
from pathlib import Path

import httpx

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from pydantic import BaseModel, TypeAdapter

from orchestrator.discovery_models import (
    DiscoveryDaemonControlRequest,
    ExecutionBriefApprovalUpdateRequest,
    DiscoveryInboxActionRequest,
    DiscoveryInboxResolveRequest,
    DossierTimelineEventCreateRequest,
    EvidenceBundleUpsertRequest,
    ExecutionFeedbackIngestRequest,
    ExecutionBriefCandidateUpsertRequest,
    IdeaArchiveRequest,
    IdeaCreateRequest,
    IdeaDecisionCreateRequest,
    IdeaSwipeRequest,
    IdeaUpdateRequest,
    IdeaValidationReportCreateRequest,
    MarketSimulationRunRequest,
    MarketSimulationRunResponse,
    MemoryQueryRequest,
    SimulationRunRequest,
    SimulationRunResponse,
    SourceObservationCreateRequest,
)
from orchestrator.daemon import get_discovery_daemon_service
from orchestrator.discovery_store import get_discovery_store
from orchestrator.guardrails import (
    guardrail_audit_store,
    policy_catalog_payload,
    record_guardrail_event,
    scan_tool_config,
)
from orchestrator.guardrails.policies import GuardrailScanReport
from orchestrator.handoff import DiscoveryHandoffExportRequest, get_handoff_service
from orchestrator.handoff_bridge import _send_brief_to_autopilot
from orchestrator.handoff_models import (
    AutopilotLaunchPreset,
    DEFAULT_AUTOPILOT_API_BASE,
    ExecutionBriefExportRequest,
    SendExecutionBriefRequest,
)
from orchestrator.improvement import (
    ImprovementEvolutionRequest,
    ImprovementSelfPlayRequest,
    ImprovementSessionReflectRequest,
    get_improvement_lab,
)
from orchestrator.idea_graph import get_idea_graph_service
from orchestrator.memory_graph import get_memory_graph_service
from orchestrator.observability.debate_replay import DebateReplayService
from orchestrator.observability.dossier_explainability import DossierExplainabilityService
from orchestrator.observability.evals import DiscoveryEvaluationService
from orchestrator.observability.scoreboards import DiscoveryScoreboardService
from orchestrator.observability.traces import DiscoveryTraceService
from orchestrator.preference_model import PreferenceModelService
from orchestrator.research.exports import export_daily_queue_markdown, export_observations_jsonl
from orchestrator.research.pipeline import ResearchPipeline
from orchestrator.research.search_index import get_research_index
from orchestrator.research.source_models import ScanRequest
from orchestrator.repodna import get_repo_dna_service
from orchestrator.repo_graph import get_repo_graph_service
from orchestrator.ranking import (
    FinalVoteRequest,
    PairwiseComparisonRequest,
    get_ranking_service,
)
from orchestrator.models import (
    WorkspacePreset,
    MODE_AGENT_REQUIREMENTS,
    capability_for_tool,
    capability_matrix_for_enabled_tools,
    collect_attached_tool_ids,
    build_provider_capabilities_snapshot,
    store,
    ControlRequest,
    RepoDigestAnalyzeRequest,
    RepoGraphAnalyzeRequest,
    RunRequest,
    MessageRequest,
    normalize_agent_configs,
    resolve_workspace_paths,
    validate_agents_for_mode,
)
from orchestrator.brief_v2_adapter import shared_brief_to_v2
from orchestrator.execution_feedback import get_execution_feedback_service
from orchestrator.scenarios import get_scenario, list_scenarios
from orchestrator.shared_contracts import (
    ExecutionBrief as SharedExecutionBrief,
    ExecutionOutcomeBundle as SharedExecutionOutcomeBundle,
    from_jsonable,
)
from orchestrator.simulation.mvp import FocusGroupRunner
from orchestrator.simulation.lab import MarketLabRunner
from orchestrator.tool_configs import (
    PROMPT_TEMPLATES,
    TOOL_TYPES,
    ToolConfig,
    is_builtin_tool_instance,
    normalize_tool_id,
    tool_config_store,
)
from orchestrator.models_bootstrap import FounderBootstrapRequest

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])

SETTINGS_PROVIDERS = ["claude", "gemini", "codex", "minimax"]
PAUSEABLE_STATUSES = {"running", "pause_requested"}
RESUMABLE_STATUSES = {"paused", "pause_requested"}
MESSAGEABLE_STATUSES = {"paused", "pause_requested"}
INSTRUCTIONABLE_STATUSES = {"running", "pause_requested", "paused"}
CANCELLABLE_STATUSES = {"running", "pause_requested", "paused", "cancel_requested"}
BRANCHABLE_STATUSES = {"paused", "completed", "failed", "cancelled"}
CONTINUABLE_STATUSES = {"completed", "failed", "cancelled"}
DELETABLE_STATUSES = {"completed", "failed", "cancelled"}
LEGACY_CUSTOM_TOOL_TYPES = {"http_api", "ssh", "shell_command"}
PARALLEL_EXECUTION_MODES = {"sequential", "parallel"}
_EVENT_SOURCE_RESPONSE_UNSET = object()
EventSourceResponse = _EVENT_SOURCE_RESPONSE_UNSET


class TournamentPreparationRequest(BaseModel):
    provider: str | None = None


async def _run_sync(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _mcp_client_bindings():
    try:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:  # pragma: no cover - exercised through validate route fallback
        raise RuntimeError(
            "MCP validation is unavailable because the MCP client dependency is missing. Install `mcp` and retry."
        ) from exc
    return ClientSession, StdioServerParameters, stdio_client, streamable_http_client


def _event_source_response_class():
    global EventSourceResponse
    if EventSourceResponse is None:
        raise HTTPException(
            503,
            "Session event streaming is unavailable because the SSE transport dependency is missing. Install `sse-starlette` and retry.",
        )
    if EventSourceResponse is not _EVENT_SOURCE_RESPONSE_UNSET:
        return EventSourceResponse
    try:
        from sse_starlette.sse import EventSourceResponse as _EventSourceResponse
    except ImportError as exc:
        raise HTTPException(
            503,
            "Session event streaming is unavailable because the SSE transport dependency is missing. Install `sse-starlette` and retry.",
        ) from exc
    EventSourceResponse = _EventSourceResponse
    return EventSourceResponse


def _workspace_preset_to_dict(preset: WorkspacePreset) -> dict:
    return preset.model_dump()


def _discovery_store():
    return get_discovery_store(str(store._db_path))


def _handoff_service():
    return get_handoff_service(str(store._db_path), _discovery_store())


def _execution_feedback_service():
    return get_execution_feedback_service(str(store._db_path), _discovery_store())


def _research_index():
    db_path = str(Path(store._db_path).with_name("research.db"))
    return get_research_index(db_path)


def _research_pipeline():
    return ResearchPipeline(_research_index())


def _preference_model():
    return PreferenceModelService(_discovery_store())


def _repo_dna_service():
    db_path = str(Path(store._db_path).with_name("repo_dna.db"))
    return get_repo_dna_service(db_path)


def _repo_graph_service():
    db_path = str(Path(store._db_path).with_name("repo_graph.db"))
    return get_repo_graph_service(db_path)


def _idea_graph_service():
    db_path = str(Path(store._db_path).with_name("idea_graph.db"))
    return get_idea_graph_service(db_path, _discovery_store())


def _memory_graph_service():
    db_path = str(Path(store._db_path).with_name("memory_graph.db"))
    return get_memory_graph_service(db_path, _discovery_store())


def _improvement_lab():
    db_path = str(Path(store._db_path).with_name("improvement.db"))
    return get_improvement_lab(db_path)


def _daemon_service():
    db_path = str(Path(store._db_path).with_name("discovery_daemon.db"))
    return get_discovery_daemon_service(db_path, _discovery_store(), store)


def _ranking_service():
    db_path = str(Path(store._db_path).with_name("ranking.db"))
    return get_ranking_service(db_path, _discovery_store())


def _focus_group_runner():
    return FocusGroupRunner()


def _market_lab_runner():
    return MarketLabRunner()


def _observability_eval_service():
    return DiscoveryEvaluationService(_discovery_store())


def _observability_trace_service():
    return DiscoveryTraceService(_discovery_store(), store)


def _observability_scoreboard_service():
    return DiscoveryScoreboardService(_discovery_store(), store, _observability_eval_service())


def _debate_replay_service():
    return DebateReplayService(store)


def _dossier_explainability_service():
    return DossierExplainabilityService(_discovery_store(), store, _observability_eval_service())


def _load_execution_brief_model():
    from orchestrator.execution_brief import ExecutionBrief

    return ExecutionBrief


def generate_session_execution_brief(session: dict, provider: str | None = None):
    from orchestrator.execution_brief import generate_session_execution_brief

    return generate_session_execution_brief(session, provider)


def generate_session_tournament_preparation(session: dict, provider: str | None = None):
    from orchestrator.execution_brief import generate_session_tournament_preparation

    return generate_session_tournament_preparation(session, provider)


def _engine_module():
    # Keep route-level imports hermetic: the LangGraph stack is only required
    # for execution surfaces, not for discovery/bootstrap/handoff routes.
    from orchestrator import engine as engine_module

    return engine_module


def has_checkpoint_runtime(session_id: str):
    return _engine_module().has_checkpoint_runtime(session_id)


def has_live_runtime(session_id: str):
    return _engine_module().has_live_runtime(session_id)


def inject_instruction(session_id: str, instruction: str):
    return _engine_module().inject_instruction(session_id, instruction)


def request_cancel(session_id: str):
    return _engine_module().request_cancel(session_id)


def request_pause(session_id: str):
    return _engine_module().request_pause(session_id)


def request_resume(session_id: str, content: str | None = None):
    return _engine_module().request_resume(session_id, content)


def fork_from_checkpoint(session_id: str, checkpoint_id: str, content: str | None = None):
    return _engine_module().fork_from_checkpoint(session_id, checkpoint_id, content)


async def run(*args, **kwargs):
    return await _engine_module().run(*args, **kwargs)


def _available_modes() -> dict[str, str]:
    return _engine_module().AVAILABLE_MODES


def _default_agents():
    return _engine_module().DEFAULT_AGENTS


async def _get_session_or_404(session_id: str) -> dict:
    session = await _run_sync(store.get, session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


async def _get_discovery_idea_or_404(idea_id: str):
    idea = await _run_sync(_discovery_store().get_idea, idea_id)
    if not idea:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}")
    return idea


async def _sync_existing_autopilot_brief_if_present(idea_id: str) -> dict[str, object] | None:
    dossier = await _run_sync(_discovery_store().get_dossier, idea_id)
    if dossier is None or dossier.execution_brief_candidate is None:
        return None

    provenance = dict(dossier.idea.provenance or {})
    autopilot_meta = dict(provenance.get("autopilot") or {})
    brief_id = str(
        autopilot_meta.get("brief_id") or dossier.execution_brief_candidate.brief_id or ""
    ).strip()
    project_id = str(autopilot_meta.get("project_id") or "").strip()
    if not brief_id or not project_id:
        return None

    handoff = await _run_sync(_handoff_service().build_packet, idea_id, persist_candidate=False)
    shared_brief = from_jsonable(SharedExecutionBrief, handoff.brief)
    candidate = dossier.execution_brief_candidate
    v2 = shared_brief_to_v2(
        shared_brief,
        initiative_id=shared_brief.idea_id,
        revision_id=candidate.revision_id,
        option_id=None,
        decision_id=None,
        founder_approval_required=candidate.founder_approval_required,
        brief_approval_status=candidate.brief_approval_status,
        approved_at=candidate.approved_at,
        approved_by=candidate.approved_by,
    )

    base = str(autopilot_meta.get("autopilot_api_base") or DEFAULT_AUTOPILOT_API_BASE).rstrip("/")
    url = f"{base}/projects/briefs/{v2.brief_id}/sync-v2"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json={"brief": v2.model_dump(mode="json")})
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to reach Autopilot sync bridge: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        if response.status_code in {400, 404, 409, 422, 503}:
            raise HTTPException(response.status_code, detail)
        raise HTTPException(502, f"Autopilot sync rejected execution brief: {detail}")

    return data if isinstance(data, dict) else {"detail": data}


async def _update_execution_brief_candidate_approval(
    idea_id: str,
    body: ExecutionBriefApprovalUpdateRequest,
    *,
    decision_type: str | None = None,
    rationale: str | None = None,
):
    prior_dossier = await _run_sync(_discovery_store().get_dossier, idea_id)
    if prior_dossier is None or prior_dossier.execution_brief_candidate is None:
        raise HTTPException(404, f"Execution brief candidate not found for idea: {idea_id}")
    prior_candidate = prior_dossier.execution_brief_candidate.model_copy(deep=True)

    def apply_approval_update():
        _handoff_service().build_packet(idea_id, persist_candidate=True)
        return _discovery_store().update_execution_brief_candidate_approval(
            idea_id,
            body,
            record_timeline=False,
        )

    try:
        brief = await _run_sync(apply_approval_update)
    except KeyError:
        raise HTTPException(404, f"Execution brief candidate not found for idea: {idea_id}") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        sync_result = await _sync_existing_autopilot_brief_if_present(idea_id)
    except HTTPException as exc:
        rollback_note = (
            "Rolled back execution brief approval update after Autopilot sync failure: "
            f"{exc.detail}"
        )
        await _run_sync(
            _discovery_store().restore_execution_brief_candidate,
            idea_id,
            prior_candidate,
            note=rollback_note,
        )
        raise HTTPException(
            exc.status_code,
            f"Autopilot sync failed; local approval update was rolled back: {exc.detail}",
        ) from exc

    await _run_sync(
        _discovery_store().append_execution_brief_candidate_approval_timeline_event,
        idea_id,
        brief,
        body,
    )
    await _run_sync(
        _discovery_store().add_decision,
        idea_id,
        IdeaDecisionCreateRequest(
            decision_type=decision_type or f"execution_brief_{body.status}",
            rationale=rationale or body.note or f"{body.actor} set the execution brief to {body.status}.",
            actor=body.actor,
            metadata={
                "brief_id": brief.brief_id,
                "revision_id": brief.revision_id,
                "status": body.status,
            },
        ),
    )

    if sync_result is None:
        return brief, {"status": "not_linked"}
    return brief, {"status": "ok", "result": sync_result}


def _tool_transport(tool: ToolConfig) -> str:
    if tool.tool_type == "mcp_server":
        return str(tool.config.get("transport", "stdio") or "stdio").strip().lower()
    if is_builtin_tool_instance(tool.id):
        return "builtin"
    return "bridge"


def _tool_payload(tool: ToolConfig) -> dict:
    payload = tool.model_dump()
    payload["transport"] = _tool_transport(tool)
    payload["compatibility"] = {
        provider: capability_for_tool(provider, tool.id)
        for provider in SETTINGS_PROVIDERS
    }
    return payload


def _scan_tool_guardrails(tool: ToolConfig) -> GuardrailScanReport:
    return scan_tool_config(tool)


def _apply_guardrails(tool: ToolConfig) -> tuple[ToolConfig, GuardrailScanReport]:
    report = _scan_tool_guardrails(tool)
    guarded = tool.model_copy(
        update={
            "guardrail_status": report.status,
            "last_guardrail_report": report.model_dump(),
            "wrapper_mode": report.wrapper_mode,
            "trust_level": report.trust_level,
        }
    )
    return guarded, report


def _guardrail_block_detail(report: GuardrailScanReport, *, message: str | None = None) -> dict:
    return _error_detail(
        message or "Tool configuration blocked by guardrails.",
        reason=_reason("guardrail_block", report.summary),
        guardrail_report=report.model_dump(),
    )


def _guardrail_validation_result(tool: ToolConfig, report: GuardrailScanReport) -> dict:
    return {
        "ok": False,
        "transport": _tool_transport(tool),
        "log": ["> Guardrails blocked validation", f"> {report.summary}"],
        "error": report.summary,
    }


def _reason(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _error_detail(message: str, reason: dict | None = None, **extra: object) -> str | dict:
    payload = {"message": message}
    if reason is not None:
        payload["reason"] = reason
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    return payload if reason is not None or extra else message


def _parse_json_mapping(raw_value: object, field_name: str) -> tuple[dict[str, str], str | None]:
    if isinstance(raw_value, dict):
        parsed = raw_value
    else:
        rendered = str(raw_value or "").strip()
        if not rendered:
            return {}, None
        try:
            parsed = json.loads(rendered)
        except json.JSONDecodeError as exc:
            return {}, f"{field_name} must be valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return {}, f"{field_name} must be a JSON object"
    return {str(key): str(value) for key, value in parsed.items()}, None


def _legacy_custom_tool_payload(tool: ToolConfig) -> dict | None:
    if is_builtin_tool_instance(tool.id):
        return None
    cfg = tool.config or {}
    description = str(cfg.get("description", "")).strip() or tool.name

    if tool.tool_type in {"http_api", "custom_api"}:
        headers, _ = _parse_json_mapping(cfg.get("headers_json", ""), "headers")
        auth_header = str(cfg.get("auth_header", "") or "").strip()
        content_type = str(cfg.get("content_type", "") or "").strip()
        if auth_header:
            headers.setdefault("Authorization", auth_header)
        if content_type:
            headers.setdefault("Content-Type", content_type)
        return {
            "key": tool.id,
            "name": tool.name,
            "description": description,
            "category": TOOL_TYPES.get(tool.tool_type, {}).get("category", "custom"),
            "tool_type": "http_api",
            "config": {
                "url": str(cfg.get("base_url", "") or "").strip(),
                "base_url": str(cfg.get("base_url", "") or "").strip(),
                "method": str(cfg.get("method", "") or "GET").strip().upper(),
                "headers": json.dumps(headers, ensure_ascii=False) if headers else "",
            },
        }

    if tool.tool_type == "ssh":
        return {
            "key": tool.id,
            "name": tool.name,
            "description": description,
            "category": TOOL_TYPES.get(tool.tool_type, {}).get("category", "custom"),
            "tool_type": "ssh",
            "config": {
                "host": str(cfg.get("host", "") or "").strip(),
                "port": str(cfg.get("port", "") or "22").strip(),
                "username": str(cfg.get("user", "") or "").strip(),
                "user": str(cfg.get("user", "") or "").strip(),
                "auth_type": str(cfg.get("auth_type", "") or "key").strip(),
                "password": str(cfg.get("password", "") or "").strip(),
            },
        }

    if tool.tool_type == "shell":
        return {
            "key": tool.id,
            "name": tool.name,
            "description": description,
            "category": "custom",
            "tool_type": "shell_command",
            "config": {
                "command": str(cfg.get("command_template", "") or "").strip(),
            },
        }

    return None


def _legacy_custom_tool_to_config(payload: dict) -> ToolConfig:
    tool_type = str(payload.get("tool_type", "") or "").strip()
    if tool_type not in LEGACY_CUSTOM_TOOL_TYPES:
        raise HTTPException(422, f"Unsupported custom tool type: {tool_type}")

    tool_id = normalize_tool_id(str(payload.get("key", "") or payload.get("id", "")).strip())
    if not tool_id:
        raise HTTPException(422, "Custom tool key is required.")
    if is_builtin_tool_instance(tool_id):
        raise HTTPException(409, f"Custom tool key '{tool_id}' conflicts with a built-in tool id.")

    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise HTTPException(422, "Custom tool name is required.")

    description = str(payload.get("description", "") or "").strip() or name
    raw_config = payload.get("config") or {}
    if not isinstance(raw_config, dict):
        raise HTTPException(422, "Custom tool config must be an object.")

    if tool_type == "http_api":
        base_url = str(raw_config.get("base_url") or raw_config.get("url") or "").strip()
        if not base_url:
            raise HTTPException(422, "Custom HTTP API tool requires a URL.")
        static_headers, error = _parse_json_mapping(raw_config.get("headers", ""), "headers")
        if error:
            raise HTTPException(422, error)
        auth_header = str(raw_config.get("auth_header") or static_headers.pop("Authorization", "")).strip()
        content_type = str(
            raw_config.get("content_type")
            or static_headers.pop("Content-Type", "")
            or static_headers.pop("content-type", "")
        ).strip()
        mapped_config = {
            "base_url": base_url,
            "method": str(raw_config.get("method", "") or "GET").strip().upper(),
            "auth_header": auth_header,
            "content_type": content_type,
            "description": description,
        }
        if static_headers:
            mapped_config["headers_json"] = json.dumps(static_headers, ensure_ascii=False)
        return ToolConfig(
            id=tool_id,
            name=name,
            tool_type="http_api",
            icon=str(payload.get("icon", "") or TOOL_TYPES["http_api"]["icon"]),
            config=mapped_config,
            enabled=bool(payload.get("enabled", True)),
        )

    if tool_type == "ssh":
        host = str(raw_config.get("host", "") or "").strip()
        user = str(raw_config.get("user") or raw_config.get("username") or "").strip()
        if not host or not user:
            raise HTTPException(422, "Custom SSH tool requires host and username.")
        return ToolConfig(
            id=tool_id,
            name=name,
            tool_type="ssh",
            icon=str(payload.get("icon", "") or TOOL_TYPES["ssh"]["icon"]),
            config={
                "host": host,
                "port": str(raw_config.get("port", "") or "22").strip(),
                "user": user,
                "auth_type": str(raw_config.get("auth_type", "") or "key").strip(),
                "password": str(raw_config.get("password", "") or "").strip(),
                "description": description,
            },
            enabled=bool(payload.get("enabled", True)),
        )

    command_template = str(raw_config.get("command", "") or "").strip()
    if not command_template:
        raise HTTPException(422, "Custom shell tool requires a command template.")
    return ToolConfig(
        id=tool_id,
        name=name,
        tool_type="shell",
        icon=str(payload.get("icon", "") or TOOL_TYPES["shell"]["icon"]),
        config={
            "command_template": command_template,
            "description": description,
        },
        enabled=bool(payload.get("enabled", True)),
    )


def _has_checkpoint_history(session: dict) -> bool:
    checkpoints = session.get("checkpoints")
    if isinstance(checkpoints, list):
        return bool(checkpoints)
    return bool(session.get("current_checkpoint_id"))


def _has_branchable_checkpoint(session: dict) -> bool:
    checkpoints = session.get("checkpoints")
    if not isinstance(checkpoints, list):
        return False
    return any(
        bool(checkpoint.get("graph_checkpoint_id"))
        and checkpoint.get("status") != "terminal"
        and bool(checkpoint.get("next_node"))
        for checkpoint in checkpoints
    )


def _live_runtime_reason(status: str, live_runtime_available: bool) -> dict | None:
    if live_runtime_available:
        return None
    if status in PAUSEABLE_STATUSES | RESUMABLE_STATUSES | CANCELLABLE_STATUSES:
        return _reason(
            "runtime_unavailable_after_restart",
            "In-memory runtime is unavailable. The backend likely restarted or evicted the active runner.",
        )
    return _reason(
        "session_not_active",
        f"Session is in status '{status}' and does not currently require a live runtime.",
    )


def _checkpoint_runtime_reason(
    status: str,
    has_checkpoints: bool,
    checkpoint_runtime_available: bool,
    has_branchable_checkpoints: bool,
) -> dict | None:
    if has_checkpoints and not has_branchable_checkpoints:
        return _reason(
            "checkpoint_terminal_only",
            "Session only has terminal checkpoints. Go back to an earlier parent session or resume from a non-terminal checkpoint.",
        )
    if checkpoint_runtime_available:
        return None
    if not has_checkpoints:
        return _reason(
            "checkpoint_history_missing",
            "Session has no recorded checkpoints to branch from.",
        )
    if status not in BRANCHABLE_STATUSES:
        return _reason(
            "session_not_branchable",
            f"Session in status '{status}' cannot branch from a checkpoint yet.",
        )
    return _reason(
        "checkpoint_runtime_unavailable",
        "Checkpoint runtime snapshot is unavailable for this session.",
    )


def _action_reason(
    action: str,
    status: str,
    live_runtime_available: bool,
    checkpoint_runtime_available: bool,
    has_checkpoints: bool,
    has_branchable_checkpoints: bool,
) -> dict | None:
    if action == "pause":
        if status not in PAUSEABLE_STATUSES:
            return _reason("status_not_pauseable", f"Session status '{status}' cannot be paused.")
        if not live_runtime_available:
            return _reason("runtime_unavailable_after_restart", "Cannot pause because live runtime is unavailable.")
        return None
    if action == "resume":
        if status not in RESUMABLE_STATUSES:
            return _reason("status_not_resumable", f"Session status '{status}' cannot be resumed.")
        if not live_runtime_available:
            return _reason("runtime_unavailable_after_restart", "Cannot resume because live runtime is unavailable.")
        return None
    if action == "send_message":
        if status not in MESSAGEABLE_STATUSES:
            return _reason("status_not_messageable", f"Session status '{status}' cannot accept paused-state messages.")
        if not live_runtime_available:
            return _reason("runtime_unavailable_after_restart", "Cannot send a message because live runtime is unavailable.")
        return None
    if action == "inject_instruction":
        if status not in INSTRUCTIONABLE_STATUSES:
            return _reason("status_not_instructionable", f"Session status '{status}' cannot accept instructions.")
        if not live_runtime_available:
            return _reason("runtime_unavailable_after_restart", "Cannot queue an instruction because live runtime is unavailable.")
        return None
    if action == "cancel":
        if status not in CANCELLABLE_STATUSES:
            return _reason("status_not_cancellable", f"Session status '{status}' cannot be cancelled.")
        if not live_runtime_available:
            return _reason("runtime_unavailable_after_restart", "Cannot cancel because live runtime is unavailable.")
        return None
    if action == "continue_conversation":
        if status not in CONTINUABLE_STATUSES:
            return _reason("status_not_continuable", f"Session status '{status}' cannot continue the conversation.")
        if not has_checkpoints:
            return _reason("checkpoint_history_missing", "Session has no checkpoints to continue from.")
        if not has_branchable_checkpoints:
            return _reason(
                "checkpoint_terminal_only",
                "This session only has terminal checkpoints, so it cannot meaningfully continue the discussion.",
            )
        if not checkpoint_runtime_available:
            return _reason("checkpoint_runtime_unavailable", "Checkpoint runtime snapshot is unavailable.")
        return None
    if status not in BRANCHABLE_STATUSES:
        return _reason("status_not_branchable", f"Session status '{status}' cannot branch from a checkpoint.")
    if not has_checkpoints:
        return _reason("checkpoint_history_missing", "Session has no checkpoints to branch from.")
    if not has_branchable_checkpoints:
        return _reason(
            "checkpoint_terminal_only",
            "This session only has terminal checkpoints. Branch from an earlier parent session instead.",
        )
    if not checkpoint_runtime_available:
        return _reason("checkpoint_runtime_unavailable", "Checkpoint runtime snapshot is unavailable.")
    return None


def _parallel_child_reason(session: dict, action: str) -> dict | None:
    parent_id = str(session.get("parallel_parent_id") or "").strip()
    if not parent_id:
        return None
    return _reason(
        "parallel_child_parent_managed",
        f"This parallel child session is managed by parent session '{parent_id}'. Control it from the parent tournament run.",
    )


def _session_runtime_state(session: dict, *, include_reasons: bool = True) -> dict:
    session_id = str(session.get("id", "")).strip()
    status = str(session.get("status", "")).strip().lower()
    live_runtime_available = bool(session_id) and has_live_runtime(session_id)
    checkpoint_runtime_available = bool(session_id) and has_checkpoint_runtime(session_id)
    has_checkpoints = _has_checkpoint_history(session)
    has_branchable_checkpoints = _has_branchable_checkpoint(session)
    child_reason = _parallel_child_reason(session, "runtime")
    reasons = {
        "live_runtime": _live_runtime_reason(status, live_runtime_available),
        "checkpoint_runtime": _checkpoint_runtime_reason(
            status,
            has_checkpoints,
            checkpoint_runtime_available,
            has_branchable_checkpoints,
        ),
        "pause": child_reason
        or _action_reason("pause", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "resume": child_reason
        or _action_reason("resume", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "send_message": child_reason
        or _action_reason("send_message", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "inject_instruction": child_reason
        or _action_reason("inject_instruction", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "cancel": child_reason
        or _action_reason("cancel", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "continue_conversation": child_reason
        or _action_reason("continue_conversation", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
        "branch_from_checkpoint": child_reason
        or _action_reason("branch_from_checkpoint", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints, has_branchable_checkpoints),
    }
    runtime_state = {
        "live_runtime_available": live_runtime_available,
        "checkpoint_runtime_available": checkpoint_runtime_available,
        "has_checkpoints": has_checkpoints,
        "has_branchable_checkpoints": has_branchable_checkpoints,
        "can_pause": reasons["pause"] is None,
        "can_resume": reasons["resume"] is None,
        "can_send_message": reasons["send_message"] is None,
        "can_inject_instruction": reasons["inject_instruction"] is None,
        "can_cancel": reasons["cancel"] is None,
        "can_continue_conversation": reasons["continue_conversation"] is None,
        "can_branch_from_checkpoint": reasons["branch_from_checkpoint"] is None,
    }
    if include_reasons:
        runtime_state["reasons"] = reasons
    return runtime_state


def _session_payload(session: dict, *, include_runtime_reasons: bool = True) -> dict:
    payload = dict(session)
    payload["runtime_state"] = _session_runtime_state(
        session,
        include_reasons=include_runtime_reasons,
    )
    topology_state = dict(payload.get("config") or {}).get("topology_state")
    if isinstance(topology_state, dict) and topology_state:
        payload["topology_state"] = topology_state
    generation_trace = dict(payload.get("config") or {}).get("generation_trace")
    if isinstance(generation_trace, dict) and generation_trace:
        payload["generation_trace"] = generation_trace
    return payload


def _dossier_summary_payload(dossier) -> dict:
    evidence_bundle = dossier.evidence_bundle
    observation_timestamps = [item.captured_at.isoformat() for item in dossier.observations]
    validation_timestamps = [
        (item.updated_at or item.created_at).isoformat()
        for item in dossier.validation_reports
    ]
    decision_timestamps = [item.created_at.isoformat() for item in dossier.decisions]
    timeline_timestamps = [item.created_at.isoformat() for item in dossier.timeline]
    evidence_timestamp = evidence_bundle.updated_at.isoformat() if evidence_bundle else None
    last_updated_at = max(
        [
            timestamp
            for timestamp in [
                evidence_timestamp,
                *observation_timestamps,
                *validation_timestamps,
                *decision_timestamps,
                *timeline_timestamps,
            ]
            if timestamp
        ],
        default=None,
    )
    return {
        "idea": dossier.idea.model_dump(mode="json"),
        "authoring_summary": {
            "observation_count": len(dossier.observations),
            "evidence_item_count": len(evidence_bundle.items) if evidence_bundle else 0,
            "validation_count": len(dossier.validation_reports),
            "decision_count": len(dossier.decisions),
            "timeline_count": len(dossier.timeline),
            "overall_confidence": (
                evidence_bundle.overall_confidence
                if evidence_bundle
                else (dossier.validation_reports[0].confidence if dossier.validation_reports else "unknown")
            ),
            "last_updated_at": last_updated_at,
        },
        "execution_brief_candidate": (
            dossier.execution_brief_candidate.model_dump(mode="json")
            if dossier.execution_brief_candidate
            else None
        ),
        "execution_outcomes": [
            outcome.model_dump(mode="json")
            for outcome in dossier.execution_outcomes
        ],
    }


def _raise_session_action_error(
    status_code: int,
    session: dict,
    action: str,
    message: str,
    **extra: object,
) -> None:
    runtime_state = _session_runtime_state(session)
    raise HTTPException(
        status_code,
        _error_detail(
            message,
            reason=runtime_state["reasons"].get(action),
            session_status=session.get("status"),
            action=action,
            **extra,
        ),
    )


def _validate_workspace_paths_exist(paths: list[str]) -> list[str]:
    errors: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            errors.append(f"Workspace path does not exist: {path}")
        elif not path.is_dir():
            errors.append(f"Workspace path is not a directory: {path}")
    return errors


async def _fetch_autopilot_launch_presets(base_url: str = DEFAULT_AUTOPILOT_API_BASE) -> list[AutopilotLaunchPreset]:
    base = str(base_url or DEFAULT_AUTOPILOT_API_BASE).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{base}/capabilities/launch-presets")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to reach Autopilot launch presets: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise HTTPException(502, f"Autopilot launch presets request failed: {detail}")

    raw_presets = data.get("launch_presets") if isinstance(data, dict) else None
    if not isinstance(raw_presets, list):
        raise HTTPException(502, "Autopilot launch presets response is malformed.")
    return [AutopilotLaunchPreset.model_validate(item) for item in raw_presets]


async def _fetch_autopilot_projects(
    *,
    include_archived: bool = False,
    base_url: str = DEFAULT_AUTOPILOT_API_BASE,
) -> list[dict]:
    base = str(base_url or DEFAULT_AUTOPILOT_API_BASE).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{base}/projects/",
                params={"include_archived": "true" if include_archived else "false"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to reach Autopilot projects: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise HTTPException(502, f"Autopilot projects request failed: {detail}")

    projects = data.get("projects") if isinstance(data, dict) else None
    if not isinstance(projects, list):
        raise HTTPException(502, "Autopilot projects response is malformed.")
    return projects


async def _post_autopilot_project_action(
    project_id: str,
    action: str,
    *,
    base_url: str = DEFAULT_AUTOPILOT_API_BASE,
) -> dict:
    base = str(base_url or DEFAULT_AUTOPILOT_API_BASE).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{base}/projects/{project_id}/{action}")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to reach Autopilot project action '{action}': {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        if response.status_code in {400, 409, 422, 503}:
            raise HTTPException(response.status_code, detail)
        raise HTTPException(502, f"Autopilot project action '{action}' failed: {detail}")
    if not isinstance(data, dict):
        raise HTTPException(502, f"Autopilot project action '{action}' returned malformed payload.")
    return data


async def _validate_mcp_stdio(tool: ToolConfig) -> dict:
    ClientSession, StdioServerParameters, stdio_client, _ = _mcp_client_bindings()
    logs = ["> Connecting to server..."]
    command_text = str(tool.config.get("command", "")).strip()
    if not command_text:
        return {"ok": False, "log": [*logs, "> Missing command"], "error": "Command is required for stdio MCP"}
    parts = shlex.split(command_text)
    extra_args = shlex.split(str(tool.config.get("args", "") or ""))
    env_vars: dict[str, str] = {}
    raw_env = str(tool.config.get("env", "") or "").strip()
    if raw_env:
        try:
            parsed_env = json.loads(raw_env)
        except json.JSONDecodeError as exc:
            return {"ok": False, "log": [*logs, "> Invalid env JSON"], "error": f"Invalid env JSON: {exc}"}
        if not isinstance(parsed_env, dict):
            return {"ok": False, "log": [*logs, "> Invalid env payload"], "error": "env must be a JSON object"}
        env_vars = {str(key): str(value) for key, value in parsed_env.items()}
    logs.append("> Handshake initiated...")
    params = StdioServerParameters(
        command=parts[0],
        args=[*parts[1:], *extra_args],
        env=env_vars or None,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=8)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=8)
    tool_count = len(getattr(tools_result, "tools", []) or [])
    logs.extend([
        "> Waiting for response...",
        f"> Connection successful. Server ready. Listed tools: {tool_count}",
    ])
    return {"ok": True, "transport": "stdio", "log": logs, "tool_count": tool_count}


async def _validate_mcp_http(tool: ToolConfig) -> dict:
    ClientSession, _, _, streamable_http_client = _mcp_client_bindings()
    logs = ["> Connecting to server..."]
    url = str(tool.config.get("url", "")).strip()
    if not url:
        return {"ok": False, "log": [*logs, "> Missing URL"], "error": "HTTP URL is required for HTTP MCP"}
    headers: dict[str, str] = {}
    raw_headers = str(tool.config.get("headers", "") or "").strip()
    if raw_headers:
        try:
            parsed_headers = json.loads(raw_headers)
        except json.JSONDecodeError as exc:
            return {"ok": False, "log": [*logs, "> Invalid headers JSON"], "error": f"Invalid headers JSON: {exc}"}
        if not isinstance(parsed_headers, dict):
            return {"ok": False, "log": [*logs, "> Invalid headers payload"], "error": "headers must be a JSON object"}
        headers = {str(key): str(value) for key, value in parsed_headers.items()}
    logs.append("> Handshake initiated...")
    async with httpx.AsyncClient(headers=headers, timeout=8) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=8)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=8)
    tool_count = len(getattr(tools_result, "tools", []) or [])
    logs.extend([
        "> Waiting for response...",
        f"> Connection successful. Server ready. Listed tools: {tool_count}",
    ])
    return {"ok": True, "transport": "http", "log": logs, "tool_count": tool_count}


async def _validate_tool_profile(tool: ToolConfig) -> dict:
    required_fields = [
        field["name"]
        for field in TOOL_TYPES.get(tool.tool_type, {}).get("fields", [])
        if field.get("required")
    ]
    missing = [
        field_name
        for field_name in required_fields
        if not str(tool.config.get(field_name, "") or "").strip()
    ]
    if missing:
        return {
            "ok": False,
            "transport": _tool_transport(tool),
            "log": [f"> Missing required fields: {', '.join(missing)}"],
            "error": f"Missing required fields: {', '.join(missing)}",
        }

    if tool.tool_type == "mcp_server":
        transport = _tool_transport(tool)
        if transport == "http":
            return await _validate_mcp_http(tool)
        return await _validate_mcp_stdio(tool)

    if tool.tool_type == "neo4j":
        from neo4j import GraphDatabase

        logs = ["> Opening Neo4j driver...", "> Running connectivity check..."]
        driver = GraphDatabase.driver(
            tool.config.get("bolt_url", ""),
            auth=(tool.config.get("user", ""), tool.config.get("password", "")),
        )
        try:
            await asyncio.to_thread(driver.verify_connectivity)
        finally:
            await asyncio.to_thread(driver.close)
        logs.append("> Connection successful. Driver verified.")
        return {"ok": True, "transport": "bridge", "log": logs}

    if tool.tool_type == "ssh":
        command = ["ssh", "-V"]
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        version = (stderr or stdout).decode("utf-8", errors="replace").strip()
        return {
            "ok": proc.returncode == 0,
            "transport": "bridge",
            "log": ["> Checking local SSH client...", f"> {version or 'ssh client available'}"],
            "error": None if proc.returncode == 0 else version,
        }

    if tool.tool_type in {"http_api", "custom_api"}:
        base_url = str(tool.config.get("base_url", "")).strip()
        if not base_url.startswith(("http://", "https://")):
            return {
                "ok": False,
                "transport": "bridge",
                "log": ["> Invalid base URL"],
                "error": "base_url must start with http:// or https://",
            }
        return {
            "ok": True,
            "transport": "bridge",
            "log": ["> Configuration looks valid.", f"> Base URL: {base_url}"],
        }

    if tool.tool_type in {"brave_search", "perplexity", "bright_data_serp"}:
        return {
            "ok": True,
            "transport": "bridge",
            "log": ["> API key present.", "> Tool profile is ready for runtime use."],
        }

    return {"ok": True, "transport": _tool_transport(tool), "log": ["> Built-in tool is ready."]}


def _resolve_agents(req: RunRequest):
    if req.agents:
        return req.agents
    scenario = get_scenario(req.scenario_id) if req.scenario_id else None
    if scenario:
        return scenario["default_agents"]
    return _default_agents().get(req.mode, [])


@router.post("/run")
async def ep_run(req: RunRequest):
    scenario = get_scenario(req.scenario_id) if req.scenario_id else None
    if req.scenario_id and not scenario:
        raise HTTPException(422, f"Unknown scenario: {req.scenario_id}")
    if scenario and scenario["mode"] != req.mode:
        raise HTTPException(
            422,
            f"Scenario '{req.scenario_id}' is bound to mode '{scenario['mode']}', not '{req.mode}'.",
        )
    available_modes = _available_modes()
    if req.mode not in available_modes:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(available_modes.keys())}")
    agents = normalize_agent_configs(_resolve_agents(req))
    run_config = dict(scenario.get("default_config", {})) if scenario else {}
    run_config.update(req.config)
    for key, value in _improvement_lab().runtime_profile(req.mode).items():
        run_config.setdefault(key, value)
    execution_mode = str(run_config.get("execution_mode", "sequential") or "sequential").strip().lower()
    if execution_mode not in PARALLEL_EXECUTION_MODES:
        raise HTTPException(422, f"Invalid execution_mode: {execution_mode}. Expected one of {sorted(PARALLEL_EXECUTION_MODES)}")
    if req.mode != "tournament" and execution_mode != "sequential":
        raise HTTPException(422, "Parallel execution_mode is currently supported only for tournament.")
    run_config["execution_mode"] = execution_mode
    if "parallelism_limit" in run_config and run_config["parallelism_limit"] is not None:
        try:
            run_config["parallelism_limit"] = max(int(run_config["parallelism_limit"]), 1)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, f"parallelism_limit must be a positive integer: {exc}") from exc
    resolved_preset_ids, resolved_workspace_paths = resolve_workspace_paths(
        req.workspace_preset_ids,
        req.workspace_paths,
    )
    workspace_errors = _validate_workspace_paths_exist(resolved_workspace_paths)
    for agent in agents:
        agent_workspace_errors = _validate_workspace_paths_exist(agent.workspace_paths)
        if agent_workspace_errors:
            workspace_errors.extend(
                [f"{agent.role}: {error}" for error in agent_workspace_errors]
            )
    if workspace_errors:
        raise HTTPException(422, {"message": "Invalid workspace paths", "errors": workspace_errors})
    errors = validate_agents_for_mode(req.mode, agents)
    if errors:
        raise HTTPException(422, {
            "message": "Invalid agent topology or tool selection",
            "errors": errors,
            "requirements": MODE_AGENT_REQUIREMENTS.get(req.mode, {}),
        })
    attached_tool_ids = collect_attached_tool_ids(agents, req.attached_tool_ids)
    provider_capabilities_snapshot = build_provider_capabilities_snapshot(agents)
    session_id = await run(
        mode=req.mode, task=req.task,
        agents=agents, config=run_config,
        scenario_id=req.scenario_id,
        workspace_preset_ids=resolved_preset_ids,
        workspace_paths=resolved_workspace_paths,
        attached_tool_ids=attached_tool_ids,
    )
    return {
        "session_id": session_id,
        "mode": req.mode,
        "status": "running",
        "scenario_id": req.scenario_id,
        "workspace_preset_ids": resolved_preset_ids,
        "workspace_paths": resolved_workspace_paths,
        "attached_tool_ids": attached_tool_ids,
        "provider_capabilities_snapshot": provider_capabilities_snapshot,
    }


@router.get("/session/{session_id}")
async def ep_session(session_id: str):
    session = await _get_session_or_404(session_id)
    return _session_payload(session)


@router.delete("/session/{session_id}")
async def ep_delete_session(session_id: str):
    session = await _get_session_or_404(session_id)

    tree_ids = await _run_sync(store.session_tree_ids, session_id)
    active_sessions: list[dict[str, str]] = []
    for related_id in tree_ids:
        related = await _run_sync(store.get, related_id)
        if not related:
            continue
        status = str(related.get("status") or "").strip().lower()
        if status not in DELETABLE_STATUSES:
            active_sessions.append({"id": related_id, "status": status or "unknown"})

    if active_sessions:
        raise HTTPException(
            409,
            _error_detail(
                "Only completed, failed, or cancelled sessions can be deleted. Stop active runs first.",
                reason=_reason(
                    "session_not_deletable",
                    "Only completed, failed, or cancelled sessions can be deleted. Stop active runs first.",
                ),
                session_status=session.get("status"),
                action="delete_session",
                active_sessions=active_sessions,
            ),
        )

    deleted_session_ids = await _run_sync(store.delete_session_tree, session_id)
    return {"status": "deleted", "deleted_session_ids": deleted_session_ids}


@router.get("/execution-brief/schema")
async def ep_execution_brief_schema():
    return _load_execution_brief_model().model_json_schema()


@router.get("/discovery/handoff/schema")
async def ep_discovery_handoff_schema():
    return TypeAdapter(SharedExecutionBrief).json_schema()


@router.get("/discovery/execution-feedback/schema")
async def ep_discovery_execution_feedback_schema():
    return TypeAdapter(SharedExecutionOutcomeBundle).json_schema()


@router.get("/autopilot/launch-presets")
async def ep_autopilot_launch_presets():
    presets = await _fetch_autopilot_launch_presets()
    return {"launch_presets": [preset.model_dump() for preset in presets]}


@router.get("/autopilot/projects")
async def ep_autopilot_projects(include_archived: bool = False):
    projects = await _fetch_autopilot_projects(include_archived=include_archived)
    return {"projects": projects}


@router.post("/autopilot/projects/{project_id}/pause")
async def ep_autopilot_project_pause(project_id: str):
    return await _post_autopilot_project_action(project_id, "pause")


@router.post("/autopilot/projects/{project_id}/resume")
async def ep_autopilot_project_resume(project_id: str):
    return await _post_autopilot_project_action(project_id, "resume")


@router.post("/session/{session_id}/execution-brief")
async def ep_execution_brief(session_id: str, req: ExecutionBriefExportRequest | None = None):
    session = await _get_session_or_404(session_id)
    try:
        brief = await asyncio.to_thread(
            generate_session_execution_brief,
            session,
            req.provider if req else None,
        )
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"status": "ok", "brief": brief.model_dump()}


@router.post("/session/{session_id}/tournament-preparation")
async def ep_tournament_preparation(session_id: str, req: TournamentPreparationRequest | None = None):
    session = await _get_session_or_404(session_id)
    try:
        preparation = await asyncio.to_thread(
            generate_session_tournament_preparation,
            session,
            req.provider if req else None,
        )
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"status": "ok", "tournament": preparation.model_dump()}


@router.post("/session/{session_id}/send-to-autopilot")
async def ep_send_to_autopilot(session_id: str, req: SendExecutionBriefRequest):
    session = await _get_session_or_404(session_id)
    try:
        brief = await asyncio.to_thread(generate_session_execution_brief, session, req.provider)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    autopilot = await _send_brief_to_autopilot(brief, req, discovery_store=_discovery_store())
    return {"status": "ok", "brief": brief.model_dump(), "autopilot": autopilot}


@router.post("/discovery/ideas/{idea_id}/handoff/export")
async def ep_export_discovery_handoff(idea_id: str, req: DiscoveryHandoffExportRequest | None = None):
    try:
        handoff = await _run_sync(
            _handoff_service().build_packet,
            idea_id,
            persist_candidate=req.persist_candidate if req else True,
        )
    except KeyError:
        raise HTTPException(404, f"Unknown idea id: {idea_id}") from None
    return {"status": "ok", "handoff": handoff.model_dump(mode="json")}


@router.post("/discovery/ideas/{idea_id}/handoff/send-to-autopilot")
async def ep_send_discovery_handoff_to_autopilot(idea_id: str, req: SendExecutionBriefRequest):
    try:
        handoff = await _run_sync(_handoff_service().build_packet, idea_id, persist_candidate=True)
    except KeyError:
        raise HTTPException(404, f"Unknown idea id: {idea_id}") from None
    effective_request = req
    if not req.project_name:
        effective_request = req.model_copy(update={"project_name": handoff.brief.get("title")})
    autopilot = await _send_brief_to_autopilot(
        handoff.brief,
        effective_request,
        discovery_store=_discovery_store(),
    )
    autopilot_payload = dict(autopilot if isinstance(autopilot, dict) else {"detail": autopilot})
    autopilot_payload["autopilot_api_base"] = str(
        effective_request.autopilot_url or DEFAULT_AUTOPILOT_API_BASE
    ).rstrip("/")
    await _run_sync(
        _handoff_service().mark_sent_to_autopilot,
        idea_id,
        project_name=effective_request.project_name,
        autopilot_payload=autopilot_payload,
    )
    return {"status": "ok", "handoff": handoff.model_dump(mode="json"), "autopilot": autopilot}


@router.get("/discovery/ideas/{idea_id}/execution-feedback")
async def ep_list_discovery_execution_feedback(idea_id: str, limit: int = 20):
    await _get_discovery_idea_or_404(idea_id)
    items = await _run_sync(_execution_feedback_service().list_outcomes, idea_id, limit=limit)
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.post("/discovery/ideas/{idea_id}/execution-feedback")
async def ep_ingest_discovery_execution_feedback(idea_id: str, body: ExecutionFeedbackIngestRequest):
    try:
        outcome = from_jsonable(SharedExecutionOutcomeBundle, body.outcome)
    except Exception as exc:
        raise HTTPException(422, f"Malformed execution outcome bundle: {exc}") from exc

    try:
        result = await _run_sync(
            _execution_feedback_service().ingest_outcome_bundle,
            idea_id,
            outcome,
            actor=body.actor,
            autopilot_project_id=body.autopilot_project_id,
            autopilot_project_name=body.autopilot_project_name,
            approvals_count=body.approvals_count,
            shipped_experiment_count=body.shipped_experiment_count,
            autopilot_payload=body.autopilot_payload,
        )
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {
        "status": "ok",
        "outcome": result.outcome.model_dump(mode="json"),
        "idea": result.idea.model_dump(mode="json"),
        "preference_profile": result.preference_profile.model_dump(mode="json"),
        "learning_summary": result.learning_summary,
    }


@router.get("/session/{session_id}/events")
async def ep_session_events(
    session_id: str,
    request: Request,
    since: int = 0,
    once: bool = False,
):
    await _get_session_or_404(session_id)
    event_source_response = _event_source_response_class()

    async def event_stream():
        cursor = since
        while True:
            if await request.is_disconnected():
                break

            events = await _run_sync(store.list_events, session_id, cursor)
            for event in events:
                cursor = int(event.get("id", cursor))
                yield {
                    "id": str(event.get("id", "")),
                    "data": json.dumps(event),
                }

            if once:
                break

            await asyncio.sleep(0.75)

    return event_source_response(event_stream())


@router.get("/sessions")
async def ep_sessions():
    sessions = await _run_sync(store.list_recent)
    return [
        _session_payload(session, include_runtime_reasons=False)
        for session in sessions
    ]


@router.get("/discovery/ideas")
async def ep_discovery_ideas(limit: int = 100):
    bounded_limit = max(1, min(int(limit or 100), 500))
    ideas = await _run_sync(_discovery_store().list_ideas, limit=bounded_limit)
    return {"ideas": ideas}


@router.get("/discovery/dossiers")
async def ep_discovery_dossiers(
    limit: int = 100,
    include_archived: bool = True,
    summary: bool = False,
):
    bounded_limit = max(1, min(int(limit or 100), 500))
    dossiers = await _run_sync(
        _discovery_store().list_dossiers,
        limit=bounded_limit,
        include_archived=include_archived,
    )
    if summary:
        return {"dossiers": [_dossier_summary_payload(dossier) for dossier in dossiers]}
    return {"dossiers": dossiers}


@router.post("/discovery/ideas")
async def ep_create_discovery_idea(body: IdeaCreateRequest):
    return await _run_sync(_discovery_store().create_idea, body)


@router.get("/discovery/ideas/{idea_id}")
async def ep_get_discovery_idea(idea_id: str):
    return await _get_discovery_idea_or_404(idea_id)


@router.patch("/discovery/ideas/{idea_id}")
async def ep_update_discovery_idea(idea_id: str, body: IdeaUpdateRequest):
    try:
        return await _run_sync(_discovery_store().update_idea, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/observations")
async def ep_add_discovery_observation(idea_id: str, body: SourceObservationCreateRequest):
    try:
        return await _run_sync(_discovery_store().add_observation, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/validation-reports")
async def ep_add_discovery_validation_report(idea_id: str, body: IdeaValidationReportCreateRequest):
    try:
        return await _run_sync(_discovery_store().add_validation_report, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/decisions")
async def ep_add_discovery_decision(idea_id: str, body: IdeaDecisionCreateRequest):
    try:
        return await _run_sync(_discovery_store().add_decision, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/archive")
async def ep_archive_discovery_idea(idea_id: str, body: IdeaArchiveRequest):
    try:
        return await _run_sync(_discovery_store().archive_idea, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/timeline")
async def ep_add_discovery_timeline_event(idea_id: str, body: DossierTimelineEventCreateRequest):
    try:
        return await _run_sync(_discovery_store().add_timeline_event, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.put("/discovery/ideas/{idea_id}/evidence-bundle")
async def ep_upsert_discovery_evidence_bundle(idea_id: str, body: EvidenceBundleUpsertRequest):
    try:
        return await _run_sync(_discovery_store().upsert_evidence_bundle, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.put("/discovery/ideas/{idea_id}/execution-brief-candidate")
async def ep_upsert_discovery_execution_brief_candidate(
    idea_id: str,
    body: ExecutionBriefCandidateUpsertRequest,
):
    try:
        return await _run_sync(_discovery_store().upsert_execution_brief_candidate, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/ideas/{idea_id}/execution-brief-candidate/approval")
async def ep_update_discovery_execution_brief_approval(
    idea_id: str,
    body: ExecutionBriefApprovalUpdateRequest,
):
    brief, autopilot_sync = await _update_execution_brief_candidate_approval(idea_id, body)
    return {
        **brief.model_dump(mode="json"),
        "autopilot_sync": autopilot_sync,
    }


@router.get("/discovery/ideas/{idea_id}/dossier")
async def ep_get_discovery_dossier(idea_id: str):
    def build_dossier() -> object:
        dossier = _discovery_store().get_dossier(idea_id)
        if dossier is None:
            return None
        dossier.idea_graph_context = _idea_graph_service().get_idea_context(idea_id)
        dossier.memory_context = _memory_graph_service().get_idea_context(idea_id)
        dossier.explainability_context = _dossier_explainability_service().build(idea_id)
        return dossier

    dossier = await _run_sync(build_dossier)
    if not dossier:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}")
    return dossier


@router.get("/discovery/ideas/{idea_id}/explainability")
async def ep_get_discovery_explainability(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    explainability = await _run_sync(_dossier_explainability_service().build, idea_id)
    if explainability is None:
        raise HTTPException(404, f"No explainability context for idea: {idea_id}")
    return explainability


@router.get("/discovery/ideas/{idea_id}/simulation")
async def ep_get_discovery_simulation(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    report = await _run_sync(_discovery_store().get_simulation_report, idea_id)
    if not report:
        raise HTTPException(404, f"No simulation report for idea: {idea_id}")
    return report


@router.post("/discovery/ideas/{idea_id}/simulation")
async def ep_run_discovery_simulation(idea_id: str, body: SimulationRunRequest):
    def run_simulation():
        discovery = _discovery_store()
        idea = discovery.get_idea(idea_id)
        if not idea:
            raise KeyError(idea_id)

        existing = discovery.get_simulation_report(idea_id)
        if existing and not body.force_refresh:
            return SimulationRunResponse(idea=idea, report=existing, cached=True)

        discovery.update_idea(idea_id, IdeaUpdateRequest(simulation_state="running"))
        dossier = discovery.get_dossier(idea_id)
        if not dossier:
            raise KeyError(idea_id)

        report = _focus_group_runner().run(dossier, body)
        stored = discovery.upsert_simulation_report(idea_id, report)
        updated_idea = discovery.get_idea(idea_id)
        if not updated_idea:
            raise KeyError(idea_id)
        return SimulationRunResponse(idea=updated_idea, report=stored, cached=False)

    try:
        return await _run_sync(run_simulation)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.get("/discovery/ideas/{idea_id}/simulation/lab")
async def ep_get_discovery_market_simulation(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    report = await _run_sync(_discovery_store().get_market_simulation_report, idea_id)
    if not report:
        raise HTTPException(404, f"No market simulation report for idea: {idea_id}")
    return report


@router.post("/discovery/ideas/{idea_id}/simulation/lab")
async def ep_run_discovery_market_simulation(idea_id: str, body: MarketSimulationRunRequest):
    def run_market_simulation():
        discovery = _discovery_store()
        idea = discovery.get_idea(idea_id)
        if not idea:
            raise KeyError(idea_id)

        existing = discovery.get_market_simulation_report(idea_id)
        if existing and not body.force_refresh:
            return MarketSimulationRunResponse(idea=idea, report=existing, cached=True)

        discovery.update_idea(idea_id, IdeaUpdateRequest(simulation_state="running"))
        dossier = discovery.get_dossier(idea_id)
        if not dossier:
            raise KeyError(idea_id)

        report = _market_lab_runner().run(dossier, body)
        stored = discovery.upsert_market_simulation_report(idea_id, report)
        updated_idea = discovery.get_idea(idea_id)
        if not updated_idea:
            raise KeyError(idea_id)
        return MarketSimulationRunResponse(idea=updated_idea, report=stored, cached=False)

    try:
        return await _run_sync(run_market_simulation)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.post("/discovery/idea-graph/rebuild")
async def ep_rebuild_discovery_idea_graph(refresh: bool = False):
    return await _idea_graph_service().rebuild(refresh=refresh)


@router.get("/discovery/idea-graph/snapshots")
async def ep_list_discovery_idea_graph_snapshots(limit: int = 20):
    return {"items": await _run_sync(_idea_graph_service().list_snapshots, limit=limit)}


@router.get("/discovery/idea-graph/snapshots/{graph_id}")
async def ep_get_discovery_idea_graph_snapshot(graph_id: str):
    snapshot = await _run_sync(_idea_graph_service().get_snapshot, graph_id)
    if snapshot is None:
        raise HTTPException(404, f"Unknown idea graph snapshot: {graph_id}")
    return snapshot


@router.get("/discovery/ideas/{idea_id}/idea-graph")
async def ep_get_discovery_idea_graph_context(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    context = await _run_sync(_idea_graph_service().get_idea_context, idea_id)
    if context is None:
        raise HTTPException(404, f"No idea graph context for idea: {idea_id}")
    return context


@router.post("/discovery/memory/rebuild")
async def ep_rebuild_discovery_memory(refresh: bool = False):
    return await _memory_graph_service().rebuild(refresh=refresh)


@router.get("/discovery/memory/snapshots")
async def ep_list_discovery_memory_snapshots(limit: int = 20):
    return {"items": await _run_sync(_memory_graph_service().list_snapshots, limit=limit)}


@router.get("/discovery/memory/snapshots/{snapshot_id}")
async def ep_get_discovery_memory_snapshot(snapshot_id: str):
    snapshot = await _run_sync(_memory_graph_service().get_snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, f"Unknown discovery memory snapshot: {snapshot_id}")
    return snapshot


@router.get("/discovery/ideas/{idea_id}/memory")
async def ep_get_discovery_memory_context(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    context = await _run_sync(_memory_graph_service().get_idea_context, idea_id)
    if context is None:
        raise HTTPException(404, f"No institutional memory context for idea: {idea_id}")
    return context


@router.post("/discovery/memory/query")
async def ep_query_discovery_memory(body: MemoryQueryRequest):
    return await _run_sync(_memory_graph_service().query, body)


@router.get("/discovery/daemon/status")
async def ep_get_discovery_daemon_status():
    return await _run_sync(_daemon_service().get_status)


@router.post("/discovery/daemon/control")
async def ep_control_discovery_daemon(body: DiscoveryDaemonControlRequest):
    service = _daemon_service()
    if body.action == "start":
        return await _run_sync(service.start)
    if body.action == "pause":
        return await _run_sync(service.pause)
    if body.action == "resume":
        return await _run_sync(service.resume)
    if body.action == "stop":
        return await _run_sync(service.stop)
    if body.action == "tick":
        return await _run_sync(service.tick)
    if not body.routine_kind:
        raise HTTPException(422, "routine_kind is required when action=run_routine")
    try:
        return await _run_sync(service.run_routine, body.routine_kind)
    except KeyError:
        raise HTTPException(404, f"Unknown daemon routine: {body.routine_kind}") from None


@router.get("/discovery/daemon/digests")
async def ep_get_discovery_daemon_digests(limit: int = 14):
    bounded_limit = max(1, min(int(limit or 14), 90))
    items = await _run_sync(_daemon_service().list_digests, limit=bounded_limit)
    return {"items": items}


@router.get("/discovery/daemon/runs")
async def ep_get_discovery_daemon_runs(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 200))
    items = await _run_sync(_daemon_service().list_runs, limit=bounded_limit)
    return {"items": items}


@router.get("/discovery/inbox")
async def ep_get_discovery_inbox(limit: int = 50, status: str | None = "open"):
    bounded_limit = max(1, min(int(limit or 50), 500))
    normalized_status = (status or "").strip().lower() or None
    if normalized_status not in {None, "open", "resolved"}:
        raise HTTPException(422, "status must be one of: open, resolved")
    return await _run_sync(
        _daemon_service().get_inbox_feed,
        limit=bounded_limit,
        status=normalized_status,
    )


@router.get("/discovery/inbox/{item_id}")
async def ep_get_discovery_inbox_item(item_id: str):
    item = await _run_sync(_daemon_service().get_inbox_item, item_id)
    if item is None:
        raise HTTPException(404, f"Unknown discovery inbox item: {item_id}")
    return item


@router.get("/improvement/prompt-profiles")
async def ep_get_improvement_prompt_profiles(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 200))
    profiles = await _run_sync(_improvement_lab().list_profiles, limit=bounded_limit)
    return {"items": [item.model_dump(mode="json") for item in profiles]}


@router.get("/improvement/prompt-profiles/{profile_id}")
async def ep_get_improvement_prompt_profile(profile_id: str):
    profile = await _run_sync(_improvement_lab().get_profile, profile_id)
    if profile is None:
        raise HTTPException(404, f"Unknown improvement prompt profile: {profile_id}")
    return profile.model_dump(mode="json")


@router.post("/improvement/prompt-profiles/{profile_id}/activate")
async def ep_activate_improvement_prompt_profile(profile_id: str):
    try:
        profile = await _run_sync(_improvement_lab().activate_profile, profile_id)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown improvement prompt profile: {profile_id}") from exc
    return {"status": "ok", "profile": profile.model_dump(mode="json")}


@router.get("/improvement/reflections")
async def ep_get_improvement_reflections(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 200))
    reflections = await _run_sync(_improvement_lab().list_reflections, limit=bounded_limit)
    return {"items": [item.model_dump(mode="json") for item in reflections]}


@router.get("/improvement/self-play/matches")
async def ep_get_improvement_self_play_matches(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 200))
    matches = await _run_sync(_improvement_lab().list_matches, limit=bounded_limit)
    return {"items": [item.model_dump(mode="json") for item in matches]}


@router.post("/improvement/reflect")
async def ep_run_improvement_reflection(body: ImprovementSessionReflectRequest):
    try:
        report = await _run_sync(_improvement_lab().reflect, body, session_lookup=store.get)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "ok", "reflection": report.model_dump(mode="json")}


@router.post("/improvement/self-play")
async def ep_run_improvement_self_play(body: ImprovementSelfPlayRequest):
    try:
        match = await _run_sync(_improvement_lab().run_self_play, body)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "ok", "match": match.model_dump(mode="json")}


@router.post("/improvement/evolve")
async def ep_run_improvement_evolution(body: ImprovementEvolutionRequest):
    try:
        result = await _run_sync(_improvement_lab().evolve, body)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "ok", "result": result.model_dump(mode="json")}


@router.post("/discovery/inbox/{item_id}/act")
async def ep_act_on_discovery_inbox_item(item_id: str, body: DiscoveryInboxActionRequest):
    item = await _run_sync(_daemon_service().act_on_inbox_item, item_id, body)
    if item is None:
        raise HTTPException(404, f"Unknown discovery inbox item: {item_id}")
    return item


@router.post("/discovery/inbox/{item_id}/resolve")
async def ep_resolve_discovery_inbox_item(item_id: str, body: DiscoveryInboxResolveRequest | None = None):
    item = await _run_sync(_daemon_service().resolve_inbox_item, item_id, body)
    if item is None:
        raise HTTPException(404, f"Unknown discovery inbox item: {item_id}")
    return item


@router.get("/observability/evals/discovery")
async def ep_get_observability_discovery_evals(limit: int = 100):
    bounded_limit = max(1, min(int(limit or 100), 500))
    return await _run_sync(_observability_eval_service().build_pack, limit=bounded_limit)


@router.get("/observability/traces/discovery")
async def ep_get_observability_discovery_traces(limit: int = 25):
    bounded_limit = max(1, min(int(limit or 25), 250))
    return await _run_sync(_observability_trace_service().build_snapshot, limit=bounded_limit)


@router.get("/observability/traces/discovery/{idea_id}")
async def ep_get_observability_discovery_trace(idea_id: str):
    await _get_discovery_idea_or_404(idea_id)
    trace_bundle = await _run_sync(_observability_trace_service().get_idea_trace, idea_id)
    if trace_bundle is None:
        raise HTTPException(404, f"No trace bundle for idea: {idea_id}")
    return trace_bundle


@router.get("/observability/scoreboards/discovery")
async def ep_get_observability_discovery_scoreboard():
    return await _run_sync(_observability_scoreboard_service().build_scoreboard)


@router.get("/observability/debate-replay/sessions/{session_id}")
async def ep_get_observability_debate_replay(session_id: str):
    replay = await _run_sync(_debate_replay_service().build_replay, session_id)
    if replay is None:
        raise HTTPException(404, f"Unknown session: {session_id}")
    return replay


@router.post("/discovery/ideas/{idea_id}/swipe")
async def ep_swipe_discovery_idea(idea_id: str, body: IdeaSwipeRequest):
    try:
        return await _run_sync(_preference_model().swipe_idea, idea_id, body)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.get("/discovery/swipe-queue")
async def ep_get_discovery_swipe_queue(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 100))
    return await _run_sync(_preference_model().get_swipe_queue, limit=bounded_limit)


@router.get("/discovery/maybe-queue")
async def ep_get_discovery_maybe_queue(limit: int = 20):
    bounded_limit = max(1, min(int(limit or 20), 100))
    return await _run_sync(_preference_model().get_maybe_queue, limit=bounded_limit)


@router.get("/discovery/preferences")
async def ep_get_discovery_preferences():
    return await _run_sync(_preference_model().get_preference_profile)


@router.get("/discovery/ideas/{idea_id}/changes")
async def ep_get_discovery_idea_changes(idea_id: str):
    try:
        return await _run_sync(_preference_model().get_idea_changes, idea_id)
    except KeyError:
        raise HTTPException(404, f"Unknown discovery idea: {idea_id}") from None


@router.get("/ranking/leaderboard")
async def ep_get_ranking_leaderboard(limit: int = 50):
    bounded_limit = max(1, min(int(limit or 50), 200))
    return await _run_sync(_ranking_service().get_leaderboard, limit=bounded_limit)


@router.get("/ranking/next-pair")
async def ep_get_ranking_next_pair():
    pair = await _run_sync(_ranking_service().get_next_pair)
    return {"pair": pair}


@router.get("/ranking/archive")
async def ep_get_ranking_archive(limit_cells: int = 24):
    bounded_limit = max(1, min(int(limit_cells or 24), 64))
    return await _run_sync(_ranking_service().get_archive_view, limit_cells=bounded_limit)


@router.post("/ranking/compare")
async def ep_record_ranking_comparison(body: PairwiseComparisonRequest):
    try:
        return await _run_sync(_ranking_service().record_comparison, body)
    except KeyError:
        raise HTTPException(404, "Unknown idea id for pairwise comparison") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/ranking/finals/resolve")
async def ep_resolve_ranking_finals(body: FinalVoteRequest):
    return await _run_sync(_ranking_service().resolve_finals, body)


@router.post("/research/scan")
async def ep_run_research_scan(body: ScanRequest):
    return await _research_pipeline().run_scan(body)


@router.get("/research/observations")
async def ep_list_research_observations(limit: int = 100, source: str | None = None, include_stale: bool = False):
    return {
        "items": await _run_sync(
            _research_index().list_observations,
            limit=limit,
            source=source,
            include_stale=include_stale,
        )
    }


@router.get("/research/search")
async def ep_search_research_observations(q: str, limit: int = 50):
    return await _run_sync(_research_index().search, q, limit=limit)


@router.get("/research/queue/daily")
async def ep_research_daily_queue(limit: int = 25):
    return {"items": await _run_sync(_research_pipeline().daily_queue, limit=limit)}


@router.get("/research/runs")
async def ep_research_runs(limit: int = 50):
    return {"items": await _run_sync(_research_index().list_runs, limit=limit)}


@router.get("/research/exports/jsonl", response_class=PlainTextResponse)
async def ep_export_research_jsonl(limit: int = 200):
    observations = await _run_sync(_research_index().list_observations, limit=limit, include_stale=True)
    return export_observations_jsonl(observations)


@router.get("/research/exports/daily-queue.md", response_class=PlainTextResponse)
async def ep_export_research_daily_queue(limit: int = 25):
    queue = await _run_sync(_research_pipeline().daily_queue, limit=limit)
    return export_daily_queue_markdown(queue)


@router.post("/repo-digest/analyze")
async def ep_analyze_repo_digest(body: RepoDigestAnalyzeRequest):
    try:
        return await _repo_dna_service().analyze(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/repo-digest/profiles")
async def ep_list_repo_dna_profiles(limit: int = 50):
    return {"items": await _run_sync(_repo_dna_service().list_profiles, limit=limit)}


@router.get("/repo-digest/profiles/{profile_id}")
async def ep_get_repo_dna_profile(profile_id: str):
    profile = await _run_sync(_repo_dna_service().get_profile, profile_id)
    if profile is None:
        raise HTTPException(404, f"Unknown RepoDNA profile: {profile_id}")
    return profile


@router.get("/repo-digest/results/{profile_id}")
async def ep_get_repo_digest_result(profile_id: str):
    result = await _run_sync(_repo_dna_service().get_result, profile_id)
    if result is None:
        raise HTTPException(404, f"Unknown RepoDNA profile: {profile_id}")
    return result


@router.post("/repo-graph/analyze")
async def ep_analyze_repo_graph(body: RepoGraphAnalyzeRequest):
    try:
        return await _repo_graph_service().analyze(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/repo-graph/results")
async def ep_list_repo_graph_results(limit: int = 50):
    return {"items": await _run_sync(_repo_graph_service().list_results, limit=limit)}


@router.get("/repo-graph/results/{graph_id}")
async def ep_get_repo_graph_result(graph_id: str):
    result = await _run_sync(_repo_graph_service().get_result, graph_id)
    if result is None:
        raise HTTPException(404, f"Unknown repo graph: {graph_id}")
    return result


@router.get("/scenarios")
async def ep_scenarios():
    return list_scenarios()


@router.post("/session/{session_id}/message")
async def ep_user_message(session_id: str, req: MessageRequest):
    session = await _get_session_or_404(session_id)
    if session.get("parallel_parent_id"):
        _raise_session_action_error(
            409,
            session,
            "send_message",
            "Parallel child sessions are controlled from their parent tournament run.",
        )
    if session["status"] not in MESSAGEABLE_STATUSES:
        _raise_session_action_error(
            409,
            session,
            "send_message",
            "Pause the run first, then send an instruction so it can be applied at the next checkpoint.",
        )
    if not req.content.strip():
        raise HTTPException(
            422,
            _error_detail(
                "Instruction content cannot be empty.",
                reason=_reason("instruction_empty", "Instruction content cannot be empty."),
                session_status=session.get("status"),
                action="send_message",
            ),
        )
    if not has_live_runtime(session_id):
        _raise_session_action_error(
            409,
            session,
            "send_message",
            "Session runtime is unavailable. The backend was likely restarted, so this paused run can no longer accept new instructions.",
        )
    queued = inject_instruction(session_id, req.content.strip())
    if not queued:
        _raise_session_action_error(
            409,
            session,
            "send_message",
            "Instruction could not be queued because session runtime is unavailable.",
        )
    return {"status": "queued", "pending_instructions": queued}


@router.post("/session/{session_id}/continue")
async def ep_continue_session(session_id: str, req: MessageRequest):
    session = await _get_session_or_404(session_id)
    if session.get("parallel_parent_id"):
        _raise_session_action_error(
            409,
            session,
            "continue_conversation",
            "Parallel child sessions are controlled from their parent tournament run.",
        )
    if session["status"] not in CONTINUABLE_STATUSES:
        _raise_session_action_error(
            409,
            session,
            "continue_conversation",
            f"Session '{session_id}' must be completed, failed, or cancelled before continuing the conversation.",
        )
    if not req.content.strip():
        raise HTTPException(
            422,
            _error_detail(
                "Continuation content cannot be empty.",
                reason=_reason("instruction_empty", "Continuation content cannot be empty."),
                session_status=session.get("status"),
                action="continue_conversation",
            ),
        )
    checkpoint_id = session.get("current_checkpoint_id")
    if not checkpoint_id:
        raise HTTPException(
            409,
            _error_detail(
                "This session has no current checkpoint to continue from.",
                reason=_reason(
                    "no_current_checkpoint",
                    "This session has no current checkpoint to continue from.",
                ),
                session_status=session.get("status"),
                action="continue_conversation",
            ),
        )
    if not has_checkpoint_runtime(session_id):
        _raise_session_action_error(
            409,
            session,
            "continue_conversation",
            "Checkpoint runtime snapshot is unavailable. The backend likely restarted or discarded this session's branch state.",
        )
    new_session_id = fork_from_checkpoint(session_id, checkpoint_id, req.content.strip())
    if not new_session_id:
        raise HTTPException(
            422,
            _error_detail(
                "Checkpoint not found or conversation continuation is unavailable for this session.",
                reason=_reason(
                    "checkpoint_not_found",
                    "Checkpoint not found or conversation continuation is unavailable for this session.",
                ),
                session_status=session.get("status"),
                action="continue_conversation",
                checkpoint_id=checkpoint_id,
            ),
        )
    return {"status": "running", "new_session_id": new_session_id}


@router.post("/session/{session_id}/control")
async def ep_session_control(session_id: str, req: ControlRequest):
    session = await _get_session_or_404(session_id)

    action = req.action.strip().lower()
    if session.get("parallel_parent_id"):
        action_name = {
            "pause": "pause",
            "resume": "resume",
            "inject_instruction": "inject_instruction",
            "cancel": "cancel",
            "restart_from_checkpoint": "branch_from_checkpoint",
        }.get(action, "cancel")
        _raise_session_action_error(
            409,
            session,
            action_name,
            "Parallel child sessions are controlled from their parent tournament run.",
        )
    if action == "pause":
        if session["status"] in PAUSEABLE_STATUSES and not has_live_runtime(session_id):
            _raise_session_action_error(
                409,
                session,
                "pause",
                "Session runtime is unavailable. The backend was likely restarted, so this run can no longer be paused or resumed.",
            )
        if not request_pause(session_id):
            _raise_session_action_error(
                409,
                session,
                "pause",
                f"Session '{session_id}' cannot be paused from status '{session['status']}'.",
            )
        return {"status": "pause_requested"}
    if action == "resume":
        if session["status"] in RESUMABLE_STATUSES and not has_live_runtime(session_id):
            _raise_session_action_error(
                409,
                session,
                "resume",
                "Session runtime is unavailable. The backend was likely restarted, so this paused run can no longer be resumed.",
            )
        if not request_resume(session_id, req.content):
            _raise_session_action_error(
                409,
                session,
                "resume",
                f"Session '{session_id}' cannot be resumed from status '{session['status']}'.",
            )
        return {"status": "running"}
    if action == "inject_instruction":
        if session["status"] not in INSTRUCTIONABLE_STATUSES:
            _raise_session_action_error(
                409,
                session,
                "inject_instruction",
                f"Session '{session_id}' cannot accept instructions from status '{session['status']}'.",
            )
        if not req.content.strip():
            raise HTTPException(
                422,
                _error_detail(
                    "Instruction content cannot be empty.",
                    reason=_reason("instruction_empty", "Instruction content cannot be empty."),
                    session_status=session.get("status"),
                    action="inject_instruction",
                ),
            )
        if not has_live_runtime(session_id):
            _raise_session_action_error(
                409,
                session,
                "inject_instruction",
                "Session runtime is unavailable. The backend was likely restarted, so queued instructions can no longer be applied to this run.",
            )
        queued = inject_instruction(session_id, req.content.strip())
        if not queued:
            _raise_session_action_error(
                409,
                session,
                "inject_instruction",
                "Instruction could not be queued because session runtime is unavailable.",
            )
        return {"status": "queued", "pending_instructions": queued}
    if action == "cancel":
        if session["status"] in CANCELLABLE_STATUSES and not has_live_runtime(session_id):
            _raise_session_action_error(
                409,
                session,
                "cancel",
                "Session runtime is unavailable. The backend was likely restarted, so this run is no longer cancellable in place.",
            )
        if not request_cancel(session_id):
            _raise_session_action_error(
                409,
                session,
                "cancel",
                f"Session '{session_id}' cannot be cancelled from status '{session['status']}'.",
            )
        return {"status": "cancel_requested"}
    if action == "restart_from_checkpoint":
        if session["status"] not in BRANCHABLE_STATUSES:
            _raise_session_action_error(
                409,
                session,
                "branch_from_checkpoint",
                f"Session '{session_id}' must be paused or finished before creating a branch from a checkpoint.",
            )
        if not has_checkpoint_runtime(session_id):
            _raise_session_action_error(
                409,
                session,
                "branch_from_checkpoint",
                "Checkpoint runtime snapshot is unavailable. The backend likely restarted or discarded this session's branch state.",
            )
        new_session_id = fork_from_checkpoint(session_id, req.checkpoint_id, req.content)
        if not new_session_id:
            raise HTTPException(
                422,
                _error_detail(
                    "Checkpoint not found or branch restart is unavailable for this session.",
                    reason=_reason(
                        "checkpoint_not_found",
                        "Checkpoint not found or branch restart is unavailable for this session.",
                    ),
                    session_status=session.get("status"),
                    action="branch_from_checkpoint",
                    checkpoint_id=req.checkpoint_id or session.get("current_checkpoint_id"),
                ),
            )
        return {"status": "running", "new_session_id": new_session_id}
    raise HTTPException(422, f"Unknown control action: {req.action}")


@router.get("/modes")
async def ep_modes():
    return {
        mode: {
            "description": desc,
            "default_agents": [a.model_dump() for a in _default_agents().get(mode, [])],
            "requirements": MODE_AGENT_REQUIREMENTS.get(mode, {}),
        }
        for mode, desc in _available_modes().items()
    }


@router.get("/tools")
async def ep_tools():
    """List enabled tools for agent configuration (wizard use)."""
    enabled = tool_config_store.list_enabled()
    return [
        {
            "key": tool.id,
            "name": tool.name,
            "icon": tool.icon,
            "tool_type": tool.tool_type,
            "transport": _tool_transport(tool),
            "compatibility": {
                provider: capability_for_tool(provider, tool.id)
                for provider in SETTINGS_PROVIDERS
            },
        }
        for tool in enabled
    ]


@router.get("/tools/custom")
async def ep_custom_tools():
    payloads: list[dict] = []
    for tool in tool_config_store.list_all():
        payload = _legacy_custom_tool_payload(tool)
        if payload is not None:
            payloads.append(payload)
    return payloads


@router.post("/tools/custom")
async def ep_add_custom_tool(payload: dict):
    tool = _legacy_custom_tool_to_config(payload)
    try:
        saved = tool_config_store.add(tool)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    legacy_payload = _legacy_custom_tool_payload(saved)
    if legacy_payload is None:
        raise HTTPException(422, f"Tool '{saved.id}' cannot be exposed through the legacy custom-tools API.")
    return legacy_payload


@router.delete("/tools/custom/{tool_key}")
async def ep_remove_custom_tool(tool_key: str):
    tool = tool_config_store.get(tool_key)
    if not tool:
        raise HTTPException(404, f"Custom tool not found: {tool_key}")
    if _legacy_custom_tool_payload(tool) is None:
        raise HTTPException(409, f"Tool '{tool_key}' is not managed by the legacy custom-tools API.")
    if not tool_config_store.delete(tool_key):
        raise HTTPException(409, f"Custom tool '{tool_key}' could not be removed.")
    return {"status": "deleted"}


@router.get("/tool-logs")
async def ep_tool_logs(limit: int = 50):
    """Read recent tool call logs."""
    import json
    from pathlib import Path
    log_dir = Path(__file__).parent.parent / ".tool_logs"
    if not log_dir.exists():
        return []
    entries = []
    for log_file in log_dir.glob("*.jsonl"):
        with open(log_file) as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return entries[:limit]


@router.get("/agents")
async def ep_agents():
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8800/pool")
            pool = resp.json()
    except Exception:
        pool = {}
    return {
        "providers": ["claude", "gemini", "codex", "minimax"],
        "pool_status": pool,
        "minimax": {"model": "minimax/minimax-m2.7", "via": "OpenRouter API"},
    }


# ---- Settings: Tool Configuration ----

@router.get("/settings/tools")
async def ep_settings_tools():
    """List all configured tools."""
    return [_tool_payload(tool) for tool in tool_config_store.list_all()]


@router.get("/settings/providers/capabilities")
async def ep_provider_capabilities():
    return {
        "providers": SETTINGS_PROVIDERS,
        "tools": capability_matrix_for_enabled_tools(),
    }


@router.get("/settings/tools/types")
async def ep_tool_types():
    """List available tool types with their config schemas."""
    return TOOL_TYPES


@router.post("/settings/tools")
async def ep_add_tool(tool: ToolConfig):
    """Add a new configured tool."""
    if tool.tool_type not in TOOL_TYPES:
        raise HTTPException(422, f"Unknown tool type: {tool.tool_type}")
    if is_builtin_tool_instance(tool.id):
        raise HTTPException(409, f"Built-in tool '{tool.id}' cannot be replaced via the settings API.")
    guarded, report = _apply_guardrails(tool)
    if guarded.enabled and report.recommended_action == "block":
        record_guardrail_event(
            source="settings_api",
            action="block",
            phase="config",
            tool_id=guarded.id,
            tool_name=guarded.name,
            detail=report.summary,
            report=report,
        )
        raise HTTPException(409, _guardrail_block_detail(report, message="Tool blocked by guardrails and was not added."))
    if report.recommended_action in {"warn", "log"}:
        record_guardrail_event(
            source="settings_api",
            action="warn",
            phase="config",
            tool_id=guarded.id,
            tool_name=guarded.name,
            detail=report.summary,
            report=report,
        )
    try:
        return _tool_payload(tool_config_store.add(guarded))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.put("/settings/tools/{tool_id}")
async def ep_update_tool(tool_id: str, updates: dict):
    """Update a configured tool."""
    if is_builtin_tool_instance(tool_id):
        raise HTTPException(409, f"Built-in tool '{tool_id}' cannot be edited via the settings API.")
    existing = tool_config_store.get(tool_id)
    if not existing:
        raise HTTPException(404, f"Tool not found: {tool_id}")
    guarded, report = _apply_guardrails(existing.model_copy(update=updates))
    if guarded.enabled and report.recommended_action == "block":
        record_guardrail_event(
            source="settings_api",
            action="block",
            phase="config",
            tool_id=guarded.id,
            tool_name=guarded.name,
            detail=report.summary,
            report=report,
        )
        raise HTTPException(409, _guardrail_block_detail(report, message="Tool update blocked by guardrails."))
    if report.recommended_action in {"warn", "log"}:
        record_guardrail_event(
            source="settings_api",
            action="warn",
            phase="config",
            tool_id=guarded.id,
            tool_name=guarded.name,
            detail=report.summary,
            report=report,
        )
    try:
        result = tool_config_store.update(tool_id, guarded.model_dump())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _tool_payload(result)


@router.delete("/settings/tools/{tool_id}")
async def ep_delete_tool(tool_id: str):
    if not tool_config_store.delete(tool_id):
        raise HTTPException(404, f"Tool not found: {tool_id}")
    return {"status": "deleted"}


@router.post("/settings/tools/{tool_id}/validate")
async def ep_validate_tool(tool_id: str):
    tool = tool_config_store.get(tool_id)
    if not tool:
        raise HTTPException(404, f"Tool not found: {tool_id}")
    guarded, report = _apply_guardrails(tool)
    if report.recommended_action == "block":
        result = _guardrail_validation_result(guarded, report)
        status = "invalid"
        record_guardrail_event(
            source="settings_api",
            action="block",
            phase="validation",
            tool_id=guarded.id,
            tool_name=guarded.name,
            detail=report.summary,
            report=report,
        )
    else:
        if report.recommended_action in {"warn", "log"}:
            record_guardrail_event(
                source="settings_api",
                action="warn",
                phase="validation",
                tool_id=guarded.id,
                tool_name=guarded.name,
                detail=report.summary,
                report=report,
            )
        try:
            result = await _validate_tool_profile(guarded)
        except Exception as exc:
            result = {
                "ok": False,
                "transport": _tool_transport(guarded),
                "log": ["> Validation failed unexpectedly", f"> {type(exc).__name__}: {exc}"],
                "error": f"{type(exc).__name__}: {exc}",
            }
        status = "valid" if result.get("ok") else "invalid"
    updated = tool_config_store.update(
        tool_id,
        {
            "validation_status": status,
            "last_validation_result": result,
            "guardrail_status": report.status,
            "last_guardrail_report": report.model_dump(),
            "wrapper_mode": report.wrapper_mode,
            "trust_level": report.trust_level,
        },
    )
    return _tool_payload(updated or guarded)


@router.get("/settings/tools/{tool_id}/guardrails")
async def ep_tool_guardrails(tool_id: str):
    tool = tool_config_store.get(tool_id)
    if not tool:
        raise HTTPException(404, f"Tool not found: {tool_id}")
    guarded, report = _apply_guardrails(tool)
    if report.model_dump() != (tool.last_guardrail_report or {}):
        tool_config_store.update(
            tool_id,
            {
                "guardrail_status": report.status,
                "last_guardrail_report": report.model_dump(),
                "wrapper_mode": report.wrapper_mode,
                "trust_level": report.trust_level,
            },
        )
    return report.model_dump()


@router.get("/guardrails/policies")
async def ep_guardrail_policies():
    return policy_catalog_payload()


@router.get("/guardrails/audit")
async def ep_guardrail_audit(limit: int = 100, tool_id: str | None = None):
    events = guardrail_audit_store.list_recent(limit=max(1, min(limit, 500)), tool_id=tool_id)
    return [event.model_dump() for event in events]


@router.get("/settings/workspaces")
async def ep_list_workspaces():
    presets = await _run_sync(store.list_workspaces)
    return [_workspace_preset_to_dict(preset) for preset in presets]


@router.post("/settings/workspaces")
async def ep_add_workspace(preset: WorkspacePreset):
    if not preset.id.strip():
        preset = preset.model_copy(update={"id": f"ws_{uuid.uuid4().hex[:8]}"})
    errors = _validate_workspace_paths_exist(preset.paths)
    if errors:
        raise HTTPException(422, {"message": "Invalid workspace paths", "errors": errors})
    created = await _run_sync(store.add_workspace, preset)
    return _workspace_preset_to_dict(created)


@router.put("/settings/workspaces/{workspace_id}")
async def ep_update_workspace(workspace_id: str, updates: dict):
    if "paths" in updates:
        errors = _validate_workspace_paths_exist(list(updates.get("paths") or []))
        if errors:
            raise HTTPException(422, {"message": "Invalid workspace paths", "errors": errors})
    updated = await _run_sync(store.update_workspace, workspace_id, updates)
    if not updated:
        raise HTTPException(404, f"Workspace preset not found: {workspace_id}")
    return _workspace_preset_to_dict(updated)


@router.delete("/settings/workspaces/{workspace_id}")
async def ep_delete_workspace(workspace_id: str):
    if not await _run_sync(store.delete_workspace, workspace_id):
        raise HTTPException(404, f"Workspace preset not found: {workspace_id}")
    return {"status": "deleted"}


# ---- Settings: Prompt Templates ----

@router.get("/settings/prompts")
async def ep_prompt_templates():
    """List available prompt templates."""
    return PROMPT_TEMPLATES


@router.post("/founder/bootstrap/github")
async def ep_founder_bootstrap_github(request: FounderBootstrapRequest):
    """Bootstrap a founder profile from their GitHub portfolio.

    Enumerates repos, clusters interests, generates opportunity hypotheses,
    and seeds the discovery queue.

    """
    from orchestrator.founder_bootstrap import (
        FounderBootstrapPipeline,
        get_github_portfolio_client,
    )

    github_client = get_github_portfolio_client()

    # Best-effort repo_digest injection — deep scan skipped if unavailable
    repo_digest_instance = None
    try:
        from orchestrator.repo_digest import RepoDigestAnalyzer
        repo_digest_instance = RepoDigestAnalyzer()
    except Exception:
        pass

    pipeline = FounderBootstrapPipeline()
    result = await pipeline.run(
        request,
        github_client=github_client,
        repo_digest=repo_digest_instance,
        discovery_store=_discovery_store(),
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# Founder approval workflow — convenience aliases around discovery_store
# ---------------------------------------------------------------------------


@router.get("/founder/approval/pending")
async def ep_list_pending_approvals():
    """List all execution briefs awaiting founder approval.

    Reads from discovery_store — the single source of truth for brief state.
    """
    ds = _discovery_store()
    # Iterate dossiers and collect briefs with pending approval status
    pending = []
    for idea in ds.list_ideas(limit=500):
        dossier = ds.get_dossier(idea.idea_id)
        if dossier is None:
            continue
        brief = dossier.execution_brief_candidate
        if brief is None:
            continue
        if getattr(brief, "brief_approval_status", "") == "pending":
            pending.append({
                "idea_id": idea.idea_id,
                "idea_title": idea.title,
                "brief": brief.model_dump(mode="json"),
            })
    return {"items": pending}


class _ApproveBriefRequest(BaseModel):
    actor: str = "founder"
    note: str = ""
    expected_brief_id: str | None = None
    expected_revision_id: str | None = None


@router.post("/founder/approval/{idea_id}/approve")
async def ep_approve_brief(idea_id: str, body: _ApproveBriefRequest | None = None):
    """Approve a pending execution brief for launch."""
    payload = body or _ApproveBriefRequest()
    brief, autopilot_sync = await _update_execution_brief_candidate_approval(
        idea_id,
        ExecutionBriefApprovalUpdateRequest(
            status="approved",
            actor=payload.actor,
            note=payload.note,
            expected_brief_id=payload.expected_brief_id,
            expected_revision_id=payload.expected_revision_id,
        ),
        decision_type="execution_brief_approved",
        rationale="Founder approved the execution brief.",
    )
    return {
        "status": "ok",
        "idea_id": idea_id,
        "brief": brief.model_dump(mode="json"),
        "autopilot_sync": autopilot_sync,
    }


class _RejectBriefRequest(BaseModel):
    actor: str = "founder"
    reason: str = ""
    expected_brief_id: str | None = None
    expected_revision_id: str | None = None


@router.post("/founder/approval/{idea_id}/reject")
async def ep_reject_brief(idea_id: str, body: _RejectBriefRequest | None = None):
    """Reject a pending execution brief."""
    payload = body or _RejectBriefRequest()
    brief, autopilot_sync = await _update_execution_brief_candidate_approval(
        idea_id,
        ExecutionBriefApprovalUpdateRequest(
            status="rejected",
            actor=payload.actor,
            note=payload.reason,
            expected_brief_id=payload.expected_brief_id,
            expected_revision_id=payload.expected_revision_id,
        ),
        decision_type="execution_brief_rejected",
        rationale=payload.reason or "Founder rejected the execution brief.",
    )
    return {
        "status": "ok",
        "idea_id": idea_id,
        "brief": brief.model_dump(mode="json"),
        "autopilot_sync": autopilot_sync,
    }
