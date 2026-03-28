"""FastAPI router for orchestration endpoints."""

import asyncio
import json
import shlex
import uuid
from pathlib import Path

import httpx

from fastapi import APIRouter, HTTPException, Request
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from sse_starlette.sse import EventSourceResponse

from orchestrator.models import (
    WorkspacePreset,
    MODE_AGENT_REQUIREMENTS,
    capability_for_tool,
    capability_matrix_for_enabled_tools,
    collect_attached_tool_ids,
    build_provider_capabilities_snapshot,
    store,
    ControlRequest,
    RunRequest,
    MessageRequest,
    normalize_agent_configs,
    resolve_workspace_paths,
    validate_agents_for_mode,
)
from orchestrator.engine import (
    fork_from_checkpoint,
    has_checkpoint_runtime,
    has_live_runtime,
    inject_instruction,
    request_cancel,
    request_pause,
    request_resume,
    run,
    AVAILABLE_MODES,
    DEFAULT_AGENTS,
)
from orchestrator.scenarios import get_scenario, list_scenarios
from orchestrator.tool_configs import (
    PROMPT_TEMPLATES,
    TOOL_TYPES,
    ToolConfig,
    is_builtin_tool_instance,
    normalize_tool_id,
    tool_config_store,
)

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])

SETTINGS_PROVIDERS = ["claude", "gemini", "codex", "minimax"]
PAUSEABLE_STATUSES = {"running", "pause_requested"}
RESUMABLE_STATUSES = {"paused", "pause_requested"}
MESSAGEABLE_STATUSES = {"paused", "pause_requested"}
INSTRUCTIONABLE_STATUSES = {"running", "pause_requested", "paused"}
CANCELLABLE_STATUSES = {"running", "pause_requested", "paused", "cancel_requested"}
BRANCHABLE_STATUSES = {"paused", "completed", "failed", "cancelled"}
CONTINUABLE_STATUSES = {"completed", "failed", "cancelled"}
LEGACY_CUSTOM_TOOL_TYPES = {"http_api", "ssh", "shell_command"}


def _workspace_preset_to_dict(preset: WorkspacePreset) -> dict:
    return preset.model_dump()


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
) -> dict | None:
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
        if not checkpoint_runtime_available:
            return _reason("checkpoint_runtime_unavailable", "Checkpoint runtime snapshot is unavailable.")
        return None
    if status not in BRANCHABLE_STATUSES:
        return _reason("status_not_branchable", f"Session status '{status}' cannot branch from a checkpoint.")
    if not has_checkpoints:
        return _reason("checkpoint_history_missing", "Session has no checkpoints to branch from.")
    if not checkpoint_runtime_available:
        return _reason("checkpoint_runtime_unavailable", "Checkpoint runtime snapshot is unavailable.")
    return None


def _session_runtime_state(session: dict) -> dict:
    session_id = str(session.get("id", "")).strip()
    status = str(session.get("status", "")).strip().lower()
    live_runtime_available = bool(session_id) and has_live_runtime(session_id)
    checkpoint_runtime_available = bool(session_id) and has_checkpoint_runtime(session_id)
    has_checkpoints = _has_checkpoint_history(session)
    reasons = {
        "live_runtime": _live_runtime_reason(status, live_runtime_available),
        "checkpoint_runtime": _checkpoint_runtime_reason(status, has_checkpoints, checkpoint_runtime_available),
        "pause": _action_reason("pause", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "resume": _action_reason("resume", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "send_message": _action_reason("send_message", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "inject_instruction": _action_reason("inject_instruction", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "cancel": _action_reason("cancel", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "continue_conversation": _action_reason("continue_conversation", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
        "branch_from_checkpoint": _action_reason("branch_from_checkpoint", status, live_runtime_available, checkpoint_runtime_available, has_checkpoints),
    }
    return {
        "live_runtime_available": live_runtime_available,
        "checkpoint_runtime_available": checkpoint_runtime_available,
        "has_checkpoints": has_checkpoints,
        "can_pause": reasons["pause"] is None,
        "can_resume": reasons["resume"] is None,
        "can_send_message": reasons["send_message"] is None,
        "can_inject_instruction": reasons["inject_instruction"] is None,
        "can_cancel": reasons["cancel"] is None,
        "can_continue_conversation": reasons["continue_conversation"] is None,
        "can_branch_from_checkpoint": reasons["branch_from_checkpoint"] is None,
        "reasons": reasons,
    }


def _session_payload(session: dict) -> dict:
    payload = dict(session)
    payload["runtime_state"] = _session_runtime_state(session)
    return payload


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


async def _validate_mcp_stdio(tool: ToolConfig) -> dict:
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

    if tool.tool_type in {"brave_search", "perplexity"}:
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
    return DEFAULT_AGENTS.get(req.mode, [])


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
    if req.mode not in AVAILABLE_MODES:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(AVAILABLE_MODES.keys())}")
    agents = normalize_agent_configs(_resolve_agents(req))
    run_config = dict(scenario.get("default_config", {})) if scenario else {}
    run_config.update(req.config)
    resolved_preset_ids, resolved_workspace_paths = resolve_workspace_paths(
        req.workspace_preset_ids,
        req.workspace_paths,
    )
    workspace_errors = _validate_workspace_paths_exist(resolved_workspace_paths)
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
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return _session_payload(session)


@router.get("/session/{session_id}/events")
async def ep_session_events(
    session_id: str,
    request: Request,
    since: int = 0,
    once: bool = False,
):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    async def event_stream():
        cursor = since
        while True:
            if await request.is_disconnected():
                break

            events = store.list_events(session_id, cursor)
            for event in events:
                cursor = int(event.get("id", cursor))
                yield {
                    "id": str(event.get("id", "")),
                    "data": json.dumps(event),
                }

            if once:
                break

            await asyncio.sleep(0.75)

    return EventSourceResponse(event_stream())


@router.get("/sessions")
async def ep_sessions():
    return [_session_payload(session) for session in store.list_recent()]


@router.get("/scenarios")
async def ep_scenarios():
    return list_scenarios()


@router.post("/session/{session_id}/message")
async def ep_user_message(session_id: str, req: MessageRequest):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
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
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
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
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    action = req.action.strip().lower()
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
            "default_agents": [a.model_dump() for a in DEFAULT_AGENTS.get(mode, [])],
            "requirements": MODE_AGENT_REQUIREMENTS.get(mode, {}),
        }
        for mode, desc in AVAILABLE_MODES.items()
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
    try:
        return _tool_payload(tool_config_store.add(tool))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.put("/settings/tools/{tool_id}")
async def ep_update_tool(tool_id: str, updates: dict):
    """Update a configured tool."""
    if is_builtin_tool_instance(tool_id):
        raise HTTPException(409, f"Built-in tool '{tool_id}' cannot be edited via the settings API.")
    try:
        result = tool_config_store.update(tool_id, updates)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not result:
        raise HTTPException(404, f"Tool not found: {tool_id}")
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
    try:
        result = await _validate_tool_profile(tool)
    except Exception as exc:
        result = {
            "ok": False,
            "transport": _tool_transport(tool),
            "log": ["> Validation failed unexpectedly", f"> {type(exc).__name__}: {exc}"],
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = "valid" if result.get("ok") else "invalid"
    updated = tool_config_store.update(
        tool_id,
        {
            "validation_status": status,
            "last_validation_result": result,
        },
    )
    return _tool_payload(updated or tool)


@router.get("/settings/workspaces")
async def ep_list_workspaces():
    return [_workspace_preset_to_dict(preset) for preset in store.list_workspaces()]


@router.post("/settings/workspaces")
async def ep_add_workspace(preset: WorkspacePreset):
    if not preset.id.strip():
        preset = preset.model_copy(update={"id": f"ws_{uuid.uuid4().hex[:8]}"})
    errors = _validate_workspace_paths_exist(preset.paths)
    if errors:
        raise HTTPException(422, {"message": "Invalid workspace paths", "errors": errors})
    return _workspace_preset_to_dict(store.add_workspace(preset))


@router.put("/settings/workspaces/{workspace_id}")
async def ep_update_workspace(workspace_id: str, updates: dict):
    if "paths" in updates:
        errors = _validate_workspace_paths_exist(list(updates.get("paths") or []))
        if errors:
            raise HTTPException(422, {"message": "Invalid workspace paths", "errors": errors})
    updated = store.update_workspace(workspace_id, updates)
    if not updated:
        raise HTTPException(404, f"Workspace preset not found: {workspace_id}")
    return _workspace_preset_to_dict(updated)


@router.delete("/settings/workspaces/{workspace_id}")
async def ep_delete_workspace(workspace_id: str):
    if not store.delete_workspace(workspace_id):
        raise HTTPException(404, f"Workspace preset not found: {workspace_id}")
    return {"status": "deleted"}


# ---- Settings: Prompt Templates ----

@router.get("/settings/prompts")
async def ep_prompt_templates():
    """List available prompt templates."""
    return PROMPT_TEMPLATES
