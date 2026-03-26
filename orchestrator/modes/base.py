"""Base class for orchestration modes and agent factory."""

import asyncio
import re
import time
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


def make_llm(provider: str, mcp_tools: list[str] | None = None) -> BaseChatModel:
    """Create a LangChain model for the given provider."""
    if provider == "claude":
        return GatewayClaude(mcp_tools=mcp_tools)
    elif provider == "gemini":
        return GatewayGemini(mcp_tools=mcp_tools)
    elif provider == "codex":
        return GatewayCodex(mcp_tools=mcp_tools)
    elif provider == "minimax":
        return GatewayMiniMax()
    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_agent(provider: str, prompt: str, system_prompt: str = "", tools: list[str] | None = None) -> str:
    """Call an agent and return the text response."""
    llm = make_llm(provider, mcp_tools=tools)
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
            tools = asyncio.run(
                route_tool_visibility(
                    task=prompt,
                    role=agent.get("role", ""),
                    available_tool_keys=tools,
                )
            )
    return call_agent(
        agent["provider"], prompt,
        agent.get("system_prompt", ""),
        tools=tools,
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
