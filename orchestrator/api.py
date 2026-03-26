"""FastAPI router for orchestration endpoints."""

from fastapi import APIRouter, HTTPException

from orchestrator.models import store, RunRequest, MessageRequest
from orchestrator.engine import run, AVAILABLE_MODES, DEFAULT_AGENTS

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])


@router.post("/run")
async def ep_run(req: RunRequest):
    if req.mode not in AVAILABLE_MODES:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(AVAILABLE_MODES.keys())}")
    session_id = await run(
        mode=req.mode, task=req.task,
        agents=req.agents if req.agents else None, config=req.config,
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
    if session["status"] != "running":
        raise HTTPException(400, f"Session is {session['status']}, cannot send messages")
    import time
    store.append_messages(session_id, [{
        "agent_id": "user", "content": req.content,
        "timestamp": time.time(), "phase": "user_intervention",
    }])
    return {"status": "message_sent"}


@router.get("/modes")
async def ep_modes():
    return {
        mode: {
            "description": desc,
            "default_agents": [a.model_dump() for a in DEFAULT_AGENTS.get(mode, [])],
        }
        for mode, desc in AVAILABLE_MODES.items()
    }


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
