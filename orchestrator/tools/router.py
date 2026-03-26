"""MCP visibility router — decides which tools to expose per agent run."""

import json
import logging
from langchain_openai import ChatOpenAI
from orchestrator.tools.base import BaseTool

logger = logging.getLogger(__name__)

ROUTER_SYSTEM = """You are a tool visibility router. Given a task and an agent's role, decide which tools should be available to the agent.

Available tools will be provided. Return a JSON array of tool names that this agent needs.

Rules:
- Only enable tools the agent actually needs for this specific task
- Search tools for research/information tasks
- Code/shell tools for implementation/debugging tasks
- HTTP tool for API integration tasks
- Be conservative — fewer tools = faster, more focused agent
- Return ONLY a JSON array of tool name strings, nothing else."""


async def route_tool_visibility(
    task: str,
    role: str,
    available_tool_keys: list[str],
) -> list[str]:
    """Use MiniMax to decide which tools to enable for this agent run.

    Returns filtered list of tool keys that should be active.
    Falls back to all available tools on error.
    """
    if not available_tool_keys:
        return []

    # If 3 or fewer tools, just use all — not worth routing
    if len(available_tool_keys) <= 3:
        return available_tool_keys

    try:
        router_llm = ChatOpenAI(
            model="minimax/minimax-m2.7",
            api_key="sk-or-v1-[REDACTED]",
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )

        tools_desc = "\n".join(f"- {k}" for k in available_tool_keys)
        prompt = f"Agent role: {role}\nTask: {task}\n\nAvailable tools:\n{tools_desc}\n\nWhich tools should this agent have access to? Return JSON array."

        response = await router_llm.ainvoke([
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": prompt},
        ])

        # Parse response
        text = response.content.strip()
        # Try to extract JSON array
        if "[" in text:
            text = text[text.index("["):text.rindex("]") + 1]
        selected = json.loads(text)

        # Filter to only valid keys
        valid = [k for k in selected if k in available_tool_keys]
        return valid if valid else available_tool_keys

    except Exception as e:
        logger.warning("Tool router failed, using all tools: %s", e)
        return available_tool_keys
