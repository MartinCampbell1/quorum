"""Base class for orchestration modes and agent factory."""

import time
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

import sys
sys.path.insert(0, "/Users/example/multi-agent")
from langchain_gateway import GatewayClaude, GatewayGemini, GatewayCodex, GatewayMiniMax


def make_llm(provider: str) -> BaseChatModel:
    """Create a LangChain model for the given provider."""
    if provider == "claude":
        return GatewayClaude()
    elif provider == "gemini":
        return GatewayGemini()
    elif provider == "codex":
        return GatewayCodex()
    elif provider == "minimax":
        return GatewayMiniMax()
    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_agent(provider: str, prompt: str, system_prompt: str = "") -> str:
    """Call an agent and return the text response."""
    llm = make_llm(provider)
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    result = llm.invoke(messages)
    return result.content


def make_message(agent_id: str, content: str, phase: str = "", **meta) -> dict:
    """Create a message dict for the session log."""
    return {
        "agent_id": agent_id,
        "content": content,
        "timestamp": time.time(),
        "phase": phase,
        **meta,
    }
