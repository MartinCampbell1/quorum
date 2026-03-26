"""Base class for orchestration modes and agent factory."""

import re
import time
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

import sys
sys.path.insert(0, "/Users/martin/multi-agent")
from langchain_gateway import GatewayClaude, GatewayGemini, GatewayCodex, GatewayMiniMax


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
    return call_agent(
        agent["provider"], prompt,
        agent.get("system_prompt", ""),
        tools=agent.get("tools"),
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
