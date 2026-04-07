"""Base class for orchestration modes and agent factory."""

import asyncio
import os
import re
import time
import threading
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_gateway import (
        GatewayClaude,
        GatewayCodex,
        GatewayGemini,
        GatewayInvocationError,
        GatewayMiniMax,
    )
except ImportError:
    GatewayClaude = None  # type: ignore[assignment,misc]
    GatewayCodex = None  # type: ignore[assignment,misc]
    GatewayGemini = None  # type: ignore[assignment,misc]
    GatewayInvocationError = None  # type: ignore[assignment,misc]
    GatewayMiniMax = None  # type: ignore[assignment,misc]

from orchestrator.models import store
from orchestrator.tools.router import route_tool_visibility


FALLBACK_PROVIDER_ORDER = {
    "claude": ("claude", "codex", "gemini"),
    "gemini": ("gemini", "codex", "claude"),
    "codex": ("codex", "claude", "gemini"),
    "minimax": ("minimax", "claude", "codex", "gemini"),
}


def agent_workspace_paths(agent: dict) -> list[str]:
    """Return normalized non-empty workspace paths assigned to an agent."""
    return [str(path).strip() for path in list(agent.get("workspace_paths") or []) if str(path).strip()]


def agent_default_workdir(agent: dict) -> str:
    """Prefer the agent's explicit workdir, otherwise a single attached project root, otherwise repo root."""
    explicit = str(agent.get("workdir") or "").strip()
    if explicit:
        return explicit

    workspace_paths = agent_workspace_paths(agent)
    if len(workspace_paths) == 1:
        return workspace_paths[0]

    return str(PROJECT_ROOT)


def build_workspace_context_prompt(agent: dict) -> str:
    """Describe attached project roots so prompts can reference them explicitly."""
    workspace_paths = agent_workspace_paths(agent)
    if not workspace_paths:
        return ""

    lines = [
        "PROJECT ROOT CONTEXT:",
        "Your accessible project roots are:",
        *[f"- {path}" for path in workspace_paths],
        "Use only these project roots as your code context unless the task explicitly points elsewhere.",
    ]
    if len(workspace_paths) == 1:
        lines.append(
            f"When the task or system prompt references relative file paths, resolve them relative to this root: {workspace_paths[0]}"
        )
    else:
        lines.append(
            "If the task mentions relative paths, first determine which listed root they belong to before inspecting files."
        )
    return "\n".join(lines) + "\n\n"


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
    timeout: int | None = None,
    stall_timeout: int | None = None,
    session_id: str | None = None,
    agent_role: str | None = None,
) -> BaseChatModel:
    """Create a LangChain model for the given provider."""
    kwargs = {
        "mcp_tools": mcp_tools,
        "workdir": workdir or str(PROJECT_ROOT),
        "workspace_paths": workspace_paths or [],
        "timeout": timeout,
        "stall_timeout": stall_timeout,
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
        return GatewayMiniMax(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_agent(
    provider: str,
    prompt: str,
    system_prompt: str = "",
    tools: list[str] | None = None,
    workdir: str | None = None,
    workspace_paths: list[str] | None = None,
    timeout: int | None = None,
    stall_timeout: int | None = None,
    session_id: str | None = None,
    agent_role: str | None = None,
) -> str:
    """Call an agent and return the text response."""
    llm = make_llm(
        provider,
        mcp_tools=tools,
        workdir=workdir,
        workspace_paths=workspace_paths,
        timeout=timeout,
        stall_timeout=stall_timeout,
        session_id=session_id,
        agent_role=agent_role,
    )
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    result = llm.invoke(messages)
    return result.content


def _needs_plain_text_contract(role: str | None) -> bool:
    normalized = str(role or "").strip().lower()
    return "critic" in normalized or "judge" in normalized


def _minimax_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _provider_attempt_order(primary_provider: str, session_provider_pool: list[str] | None = None) -> list[str]:
    ordered = [primary_provider]
    preferred = FALLBACK_PROVIDER_ORDER.get(primary_provider, (primary_provider, "codex", "claude", "gemini"))
    ordered.extend(
        provider
        for provider in preferred
        if provider != primary_provider and provider not in ordered
    )
    ordered.extend(
        provider
        for provider in ("codex", "claude", "gemini", "minimax")
        if provider != primary_provider and provider not in ordered
    )
    if session_provider_pool:
        allowed = set(session_provider_pool)
        ordered = [provider for provider in ordered if provider in allowed or provider == primary_provider]
    if not _minimax_available():
        ordered = [provider for provider in ordered if provider != "minimax" or provider == primary_provider]
    return ordered


def _plain_text_contract(prompt: str, role: str | None) -> str:
    if not _needs_plain_text_contract(role):
        return prompt
    return (
        f"{prompt}\n\n"
        "FINAL RESPONSE CONTRACT:\n"
        "- Return a direct plain-text answer for the orchestrator.\n"
        "- Do not return tool XML, tool scaffolding, or an empty response.\n"
        "- If you used tools internally, finish with a normal final answer."
    )


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
    role = agent.get("role")
    prompt = _plain_text_contract(prompt, role)
    providers = _provider_attempt_order(
        str(agent["provider"]),
        [str(provider) for provider in list(agent.get("session_provider_pool") or []) if str(provider).strip()],
    )
    last_error: GatewayInvocationError | None = None

    for attempt_index, provider in enumerate(providers):
        call_kwargs = {
            "tools": tools,
            "workdir": agent_default_workdir(agent),
            "workspace_paths": agent_workspace_paths(agent),
            "session_id": agent.get("session_id"),
            "agent_role": role,
        }
        if agent.get("timeout") is not None:
            call_kwargs["timeout"] = agent.get("timeout")
        if agent.get("stall_timeout") is not None:
            call_kwargs["stall_timeout"] = agent.get("stall_timeout")
        try:
            return call_agent(
                provider,
                prompt,
                agent.get("system_prompt", ""),
                **call_kwargs,
            )
        except GatewayInvocationError as exc:
            last_error = exc
            next_provider = providers[attempt_index + 1] if attempt_index + 1 < len(providers) else None
            session_id = str(agent.get("session_id") or "").strip()
            if session_id and next_provider:
                detail = f"{provider} failed for {role or 'agent'}: {exc.gateway_error}"
                if exc.process_log_path:
                    detail += f" Log: {exc.process_log_path}"
                store.append_event(
                    session_id,
                    "provider_fallback",
                    "Provider fallback",
                    detail,
                    agent_id=role,
                    provider=provider,
                    next_provider=next_provider,
                    process_log_path=exc.process_log_path,
                )
            if provider == providers[-1]:
                raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("Agent invocation failed before any provider attempt was made.")


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
