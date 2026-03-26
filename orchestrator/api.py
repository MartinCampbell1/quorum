"""FastAPI router for orchestration endpoints."""

from fastapi import APIRouter, HTTPException

from orchestrator.models import (
    MODE_AGENT_REQUIREMENTS,
    store,
    RunRequest,
    MessageRequest,
    normalize_agent_configs,
    validate_agents_for_mode,
)
from orchestrator.engine import run, AVAILABLE_MODES, DEFAULT_AGENTS
from orchestrator.tool_configs import tool_config_store, ToolConfig, TOOL_TYPES, PROMPT_TEMPLATES

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])


def _resolve_agents(req: RunRequest):
    return req.agents if req.agents else DEFAULT_AGENTS.get(req.mode, [])


@router.post("/run")
async def ep_run(req: RunRequest):
    if req.mode not in AVAILABLE_MODES:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(AVAILABLE_MODES.keys())}")
    agents = normalize_agent_configs(_resolve_agents(req))
    errors = validate_agents_for_mode(req.mode, agents)
    if errors:
        raise HTTPException(422, {
            "message": "Invalid agent topology or tool selection",
            "errors": errors,
            "requirements": MODE_AGENT_REQUIREMENTS.get(req.mode, {}),
        })
    session_id = await run(
        mode=req.mode, task=req.task,
        agents=agents, config=req.config,
    )
    return {"session_id": session_id, "mode": req.mode, "status": "running"}


@router.get("/session/{session_id}")
async def ep_session(session_id: str):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.get("/sessions")
async def ep_sessions():
    return store.list_recent()


@router.post("/session/{session_id}/message")
async def ep_user_message(session_id: str, req: MessageRequest):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    raise HTTPException(
        409,
        "Live user messages are not wired into running graphs in this build. "
        "Treat sessions as read-only until interactive resume support is implemented.",
    )


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
    return [{"key": t.id, "name": t.name, "icon": t.icon, "tool_type": t.tool_type} for t in enabled]


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
    return [t.model_dump() for t in tool_config_store.list_all()]


@router.get("/settings/tools/types")
async def ep_tool_types():
    """List available tool types with their config schemas."""
    return TOOL_TYPES


@router.post("/settings/tools")
async def ep_add_tool(tool: ToolConfig):
    """Add a new configured tool."""
    if tool.tool_type not in TOOL_TYPES:
        raise HTTPException(422, f"Unknown tool type: {tool.tool_type}")
    return tool_config_store.add(tool).model_dump()


@router.put("/settings/tools/{tool_id}")
async def ep_update_tool(tool_id: str, updates: dict):
    """Update a configured tool."""
    result = tool_config_store.update(tool_id, updates)
    if not result:
        raise HTTPException(404, f"Tool not found: {tool_id}")
    return result.model_dump()


@router.delete("/settings/tools/{tool_id}")
async def ep_delete_tool(tool_id: str):
    if not tool_config_store.delete(tool_id):
        raise HTTPException(404, f"Tool not found: {tool_id}")
    return {"status": "deleted"}


# ---- Settings: Prompt Templates ----

@router.get("/settings/prompts")
async def ep_prompt_templates():
    """List available prompt templates."""
    return PROMPT_TEMPLATES
