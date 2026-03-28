"""Base class for orchestration modes and agent factory."""

import asyncio
import re
import time
import threading
from pathlib import Path
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

import sys
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from langchain_gateway import GatewayClaude, GatewayGemini, GatewayCodex, GatewayMiniMax
from orchestrator.tools.router import route_tool_visibility


class AgentStepError(ValueError):
    """Raised when a mode step cannot use an agent response as valid state."""

    def __init__(self, agent: dict, context: str, detail: str) -> None:
        role = str(agent.get("role", "agent") or "agent")
        provider = str(agent.get("provider", "unknown") or "unknown")
        super().__init__(f"{context}: {role} ({provider}) {detail}")
        self.agent_role = role
        self.provider = provider
        self.gateway_error = str(self)


def _route_tool_visibility_sync(task: str, role: str, available_tool_keys: list[str]) -> list[str]:
    result: list[str] = []

    def runner() -> None:
        nonlocal result
        result = asyncio.run(
            route_tool_visibility(
                task=task,
                role=role,
                available_tool_keys=available_tool_keys,
            )
        )

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    return result or available_tool_keys


def make_llm(
    provider: str,
    mcp_tools: list[str] | None = None,
    workdir: str | None = None,
    workspace_paths: list[str] | None = None,
    session_id: str | None = None,
    agent_role: str | None = None,
) -> BaseChatModel:
    """Create a LangChain model for the given provider."""
    kwargs = {
        "mcp_tools": mcp_tools,
        "workdir": workdir or str(PROJECT_ROOT),
        "workspace_paths": workspace_paths or [],
        "session_id": session_id,
        "agent_role": agent_role,
    }
    if provider == "claude":
        return GatewayClaude(**kwargs)
    elif provider == "gemini":
        return GatewayGemini(**kwargs)
    elif provider == "codex":
        return GatewayCodex(**kwargs)
    elif provider == "minimax":
        return GatewayMiniMax()
    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_agent(
    provider: str,
    prompt: str,
    system_prompt: str = "",
    tools: list[str] | None = None,
    workdir: str | None = None,
    workspace_paths: list[str] | None = None,
    session_id: str | None = None,
    agent_role: str | None = None,
) -> str:
    """Call an agent and return the text response."""
    llm = make_llm(
        provider,
        mcp_tools=tools,
        workdir=workdir,
        workspace_paths=workspace_paths,
        session_id=session_id,
        agent_role=agent_role,
    )
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    result = llm.invoke(messages)
    return result.content


def call_agent_cfg(agent: dict, prompt: str) -> str:
    """Call an agent using an agent config dict (with provider, system_prompt, tools keys)."""
    tools = list(agent.get("tools") or [])
    if tools:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            tools = _route_tool_visibility_sync(prompt, agent.get("role", ""), tools)
        else:
            tools = _route_tool_visibility_sync(prompt, agent.get("role", ""), tools)
    return call_agent(
        agent["provider"], prompt,
        agent.get("system_prompt", ""),
        tools=tools,
        workdir=agent.get("workdir") or str(PROJECT_ROOT),
        workspace_paths=list(agent.get("workspace_paths") or []),
        session_id=agent.get("session_id"),
        agent_role=agent.get("role"),
    )


def apply_user_instructions(state: dict, prompt: str) -> str:
    """Append queued user instructions so the next node can react to them."""
    user_messages = [msg.strip() for msg in state.get("user_messages", []) if str(msg).strip()]
    if not user_messages:
        return prompt
    latest = user_messages[-3:]
    instructions = "\n".join(f"- {item}" for item in latest)
    return (
        f"{prompt}\n\n"
        f"ADDITIONAL USER INSTRUCTIONS:\n{instructions}\n\n"
        f"Treat these as higher-priority guidance for this step."
    )


def require_agent_response(agent: dict, response: str, context: str) -> str:
    """Reject blank orchestration outputs before they are persisted as valid state."""
    text = str(response or "").strip()
    if text:
        return text
    raise AgentStepError(agent, context, "returned an empty response.")


def strip_markdown_fence(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from text."""
    stripped = re.sub(r"^```(?:\w+)?\s*\n?", "", text.strip())
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


# Deprecated: kept for backward compatibility with code referencing TOOLS_BY_KEY.
# Tool descriptions are now provided via real MCP servers, not prompt injection.
def _build_tools_prompt(tool_keys: list[str]) -> str:
    """DEPRECATED: Build a text description of tools for prompt injection.
    Use MCP servers via mcp_tools parameter instead."""
    try:
        from orchestrator.models import TOOLS_BY_KEY
        parts = []
        for key in tool_keys:
            tool = TOOLS_BY_KEY.get(key)
            if tool:
                parts.append(f"- {tool.name}: {tool.description}")
        if parts:
            return "Available tools:\n" + "\n".join(parts)
    except ImportError:
        pass
    return ""


def make_message(agent_id: str, content: str, phase: str = "", **meta) -> dict:
    """Create a message dict for the session log."""
    return {
        "agent_id": agent_id,
        "content": content,
        "timestamp": time.time(),
        "phase": phase,
        **meta,
    }
