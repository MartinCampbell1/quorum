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
from orchestrator.tool_configs import tool_config_store, ToolConfig, TOOL_TYPES, PROMPT_TEMPLATES

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])

SETTINGS_PROVIDERS = ["claude", "gemini", "codex", "minimax"]
PAUSEABLE_STATUSES = {"running", "pause_requested"}
RESUMABLE_STATUSES = {"paused", "pause_requested"}
MESSAGEABLE_STATUSES = {"paused", "pause_requested"}
INSTRUCTIONABLE_STATUSES = {"running", "pause_requested", "paused"}
CANCELLABLE_STATUSES = {"running", "pause_requested", "paused", "cancel_requested"}
BRANCHABLE_STATUSES = {"paused", "completed", "failed", "cancelled"}


def _workspace_preset_to_dict(preset: WorkspacePreset) -> dict:
    return preset.model_dump()


def _tool_transport(tool: ToolConfig) -> str:
    if tool.tool_type == "mcp_server":
        return str(tool.config.get("transport", "stdio") or "stdio").strip().lower()
    if tool.tool_type in {"code_exec", "shell"}:
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


def _has_checkpoint_history(session: dict) -> bool:
    checkpoints = session.get("checkpoints")
    if isinstance(checkpoints, list):
        return bool(checkpoints)
    return bool(session.get("current_checkpoint_id"))


def _session_runtime_state(session: dict) -> dict:
    session_id = str(session.get("id", "")).strip()
    status = str(session.get("status", "")).strip().lower()
    live_runtime_available = bool(session_id) and has_live_runtime(session_id)
    checkpoint_runtime_available = bool(session_id) and has_checkpoint_runtime(session_id)
    has_checkpoints = _has_checkpoint_history(session)
    return {
        "live_runtime_available": live_runtime_available,
        "checkpoint_runtime_available": checkpoint_runtime_available,
        "has_checkpoints": has_checkpoints,
        "can_pause": status in PAUSEABLE_STATUSES and live_runtime_available,
        "can_resume": status in RESUMABLE_STATUSES and live_runtime_available,
        "can_send_message": status in MESSAGEABLE_STATUSES and live_runtime_available,
        "can_inject_instruction": status in INSTRUCTIONABLE_STATUSES and live_runtime_available,
        "can_cancel": status in CANCELLABLE_STATUSES and live_runtime_available,
        "can_branch_from_checkpoint": (
            status in BRANCHABLE_STATUSES
            and has_checkpoints
            and checkpoint_runtime_available
        ),
    }


def _session_payload(session: dict) -> dict:
    payload = dict(session)
    payload["runtime_state"] = _session_runtime_state(session)
    return payload


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
        raise HTTPException(
            409,
            "Pause the run first, then send an instruction so it can be applied at the next checkpoint.",
        )
    if not req.content.strip():
        raise HTTPException(422, "Instruction content cannot be empty.")
    if not has_live_runtime(session_id):
        raise HTTPException(
            409,
            "Session runtime is unavailable. The backend was likely restarted, so this paused run can no longer accept new instructions.",
        )
    queued = inject_instruction(session_id, req.content.strip())
    if not queued:
        raise HTTPException(409, "Instruction could not be queued because session runtime is unavailable.")
    return {"status": "queued", "pending_instructions": queued}


@router.post("/session/{session_id}/control")
async def ep_session_control(session_id: str, req: ControlRequest):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    action = req.action.strip().lower()
    if action == "pause":
        if session["status"] in PAUSEABLE_STATUSES and not has_live_runtime(session_id):
            raise HTTPException(
                409,
                "Session runtime is unavailable. The backend was likely restarted, so this run can no longer be paused or resumed.",
            )
        if not request_pause(session_id):
            raise HTTPException(409, f"Session '{session_id}' cannot be paused from status '{session['status']}'.")
        return {"status": "pause_requested"}
    if action == "resume":
        if session["status"] in RESUMABLE_STATUSES and not has_live_runtime(session_id):
            raise HTTPException(
                409,
                "Session runtime is unavailable. The backend was likely restarted, so this paused run can no longer be resumed.",
            )
        if not request_resume(session_id, req.content):
            raise HTTPException(409, f"Session '{session_id}' cannot be resumed from status '{session['status']}'.")
        return {"status": "running"}
    if action == "inject_instruction":
        if session["status"] not in INSTRUCTIONABLE_STATUSES:
            raise HTTPException(
                409,
                f"Session '{session_id}' cannot accept instructions from status '{session['status']}'.",
            )
        if not req.content.strip():
            raise HTTPException(422, "Instruction content cannot be empty.")
        if not has_live_runtime(session_id):
            raise HTTPException(
                409,
                "Session runtime is unavailable. The backend was likely restarted, so queued instructions can no longer be applied to this run.",
            )
        queued = inject_instruction(session_id, req.content.strip())
        if not queued:
            raise HTTPException(409, "Instruction could not be queued because session runtime is unavailable.")
        return {"status": "queued", "pending_instructions": queued}
    if action == "cancel":
        if session["status"] in CANCELLABLE_STATUSES and not has_live_runtime(session_id):
            raise HTTPException(
                409,
                "Session runtime is unavailable. The backend was likely restarted, so this run is no longer cancellable in place.",
            )
        if not request_cancel(session_id):
            raise HTTPException(409, f"Session '{session_id}' cannot be cancelled from status '{session['status']}'.")
        return {"status": "cancel_requested"}
    if action == "restart_from_checkpoint":
        if session["status"] not in BRANCHABLE_STATUSES:
            raise HTTPException(
                409,
                f"Session '{session_id}' must be paused or finished before creating a branch from a checkpoint.",
            )
        if not has_checkpoint_runtime(session_id):
            raise HTTPException(
                409,
                "Checkpoint runtime is unavailable. The backend was likely restarted, so this session can no longer branch from its in-memory checkpoint state.",
            )
        new_session_id = fork_from_checkpoint(session_id, req.checkpoint_id, req.content)
        if not new_session_id:
            raise HTTPException(422, "Checkpoint not found or branch restart is unavailable for this session.")
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
    return []


@router.post("/tools/custom")
async def ep_add_custom_tool():
    raise HTTPException(
        501,
        "Executable custom tools are not supported in this build yet. "
        "Only built-in tools are available.",
    )


@router.delete("/tools/custom/{tool_key}")
async def ep_remove_custom_tool(tool_key: str):
    raise HTTPException(
        501,
        f"Custom tool '{tool_key}' cannot be removed because custom tools are disabled in this build.",
    )


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
    return _tool_payload(tool_config_store.add(tool))


@router.put("/settings/tools/{tool_id}")
async def ep_update_tool(tool_id: str, updates: dict):
    """Update a configured tool."""
    result = tool_config_store.update(tool_id, updates)
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
