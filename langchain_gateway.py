"""
LangChain / LangGraph Adapter for CLI Gateway
===============================================

Подключает твой gateway (localhost:8800) как стандартные LangChain модели.
Никаких API ключей не нужно - все идет через CLI подписки.

Использование:

    from langchain_gateway import GatewayClaude, GatewayGemini, GatewayCodex

    # Как обычные LangChain модели
    claude = GatewayClaude()
    gemini = GatewayGemini()
    codex = GatewayCodex()

    # Обычный вызов
    response = claude.invoke("Explain async in Python")

    # В LangGraph / chains
    from langgraph.graph import StateGraph
    ...

Установка:
    pip install langchain-core httpx
"""

import os
import re
from typing import Any, Iterator, List, Optional

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


TOOL_SCAFFOLD_BLOCK_RE = re.compile(r"<tool_(?:call|result)>.*?</tool_(?:call|result)>", re.DOTALL | re.IGNORECASE)


def _has_usable_output(output: str) -> bool:
    normalized = str(output or "").strip()
    if not normalized:
        return False
    stripped = TOOL_SCAFFOLD_BLOCK_RE.sub("", normalized).strip()
    return bool(stripped)


class GatewayInvocationError(RuntimeError):
    """Raised when the local CLI gateway cannot provide a usable agent response."""

    def __init__(
        self,
        *,
        provider: str,
        agent_role: str | None,
        profile_used: str | None,
        retries: int,
        gateway_error: str,
    ) -> None:
        role_label = agent_role or "agent"
        profile_label = profile_used or "default"
        super().__init__(
            f"[{provider}:{role_label}] {gateway_error} "
            f"(profile={profile_label}, retries={retries})"
        )
        self.provider = provider
        self.agent_role = agent_role
        self.profile_used = profile_used
        self.retries = retries
        self.gateway_error = gateway_error


def _coerce_gateway_output(agent: str, agent_role: str | None, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    output = data.get("output", "")
    profile_used = data.get("profile_used")
    retries = int(data.get("retries", 0) or 0)
    success = bool(data.get("success"))
    usable_output = data.get("usable_output")
    usable = bool(usable_output) if usable_output is not None else _has_usable_output(output)
    if not success:
        raise GatewayInvocationError(
            provider=agent,
            agent_role=agent_role,
            profile_used=profile_used,
            retries=retries,
            gateway_error=str(data.get("error") or "Gateway reported an unsuccessful agent invocation."),
        )
    if not usable:
        raise GatewayInvocationError(
            provider=agent,
            agent_role=agent_role,
            profile_used=profile_used,
            retries=retries,
            gateway_error=str(data.get("error") or "Agent returned no usable text output."),
        )

    metadata = {
        "profile_used": profile_used,
        "elapsed_sec": data.get("elapsed_sec"),
        "retries": retries,
    }
    return output, metadata


# =========================================================================
#  Base: Gateway Chat Model
# =========================================================================

class GatewayChatModel(BaseChatModel):
    """
    LangChain ChatModel, который вызывает локальный gateway.
    Gateway сам ротирует аккаунты и вызывает CLI.
    """

    gateway_url: str = "http://localhost:8800"
    agent: str = "claude"                # claude | gemini | codex
    workdir: Optional[str] = None
    workspace_paths: Optional[list[str]] = None
    model_override: Optional[str] = None
    timeout: int = 300
    mcp_tools: Optional[list[str]] = None
    session_id: Optional[str] = None
    agent_role: Optional[str] = None

    @property
    def _llm_type(self) -> str:
        return f"gateway-{self.agent}"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "gateway_url": self.gateway_url,
            "agent": self.agent,
            "model_override": self.model_override,
        }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Синхронный вызов gateway."""

        # Собрать промпт из messages
        prompt, system_prompt = self._messages_to_prompt(messages)

        # Вызвать gateway
        with httpx.Client(timeout=self.timeout + 10) as client:
            resp = client.post(
                f"{self.gateway_url}/ask",
                json={
                    "agent": self.agent,
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "workdir": self.workdir,
                    "model": self.model_override,
                    "timeout": self.timeout,
                    "mcp_tools": self.mcp_tools,
                    "workspace_paths": self.workspace_paths,
                    "session_id": self.session_id,
                    "agent_role": self.agent_role,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        output, metadata = _coerce_gateway_output(self.agent, self.agent_role, data)

        # Обработать stop tokens
        if stop:
            for s in stop:
                if s in output:
                    output = output[: output.index(s)]

        message = AIMessage(
            content=output,
            additional_kwargs=metadata,
        )

        return ChatResult(
            generations=[ChatGeneration(message=message)],
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        """Асинхронный вызов gateway."""

        prompt, system_prompt = self._messages_to_prompt(messages)

        async with httpx.AsyncClient(timeout=self.timeout + 10) as client:
            resp = await client.post(
                f"{self.gateway_url}/ask",
                json={
                    "agent": self.agent,
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "workdir": self.workdir,
                    "model": self.model_override,
                    "timeout": self.timeout,
                    "mcp_tools": self.mcp_tools,
                    "workspace_paths": self.workspace_paths,
                    "session_id": self.session_id,
                    "agent_role": self.agent_role,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        output, metadata = _coerce_gateway_output(self.agent, self.agent_role, data)

        if stop:
            for s in stop:
                if s in output:
                    output = output[: output.index(s)]

        message = AIMessage(
            content=output,
            additional_kwargs=metadata,
        )

        return ChatResult(
            generations=[ChatGeneration(message=message)],
        )

    def _messages_to_prompt(self, messages: List[BaseMessage]) -> tuple[str, str]:
        """
        Конвертировать LangChain messages в prompt + system_prompt.

        CLI не поддерживают message-based API как настоящие API -
        поэтому склеиваем все в один текстовый промпт.
        """
        system_parts = []
        conversation_parts = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_parts.append(msg.content)
            elif isinstance(msg, HumanMessage):
                conversation_parts.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                conversation_parts.append(f"Assistant: {msg.content}")
            else:
                conversation_parts.append(f"{msg.type}: {msg.content}")

        system_prompt = "\n".join(system_parts) if system_parts else None
        prompt = "\n\n".join(conversation_parts) if conversation_parts else ""

        # Если только один human message - не нужен префикс
        if len(messages) == 1 and isinstance(messages[0], HumanMessage):
            prompt = messages[0].content

        return prompt, system_prompt


# =========================================================================
#  Конкретные модели - просто алиасы с правильным agent
# =========================================================================

class GatewayClaude(GatewayChatModel):
    """Claude Code через gateway. Лучший для кодинга и сложных задач."""
    agent: str = "claude"


class GatewayGemini(GatewayChatModel):
    """Gemini через gateway с ротацией аккаунтов. Огромное контекстное окно."""
    agent: str = "gemini"


class GatewayCodex(GatewayChatModel):
    """Codex/ChatGPT через gateway с ротацией аккаунтов."""
    agent: str = "codex"


# =========================================================================
#  MiniMax via OpenRouter (API, not CLI)
# =========================================================================

from langchain_openai import ChatOpenAI


class GatewayMiniMax(ChatOpenAI):
    """MiniMax m2.7 via OpenRouter with a local gateway fallback when no API key is configured."""

    gateway_url: str = "http://localhost:8800"
    fallback_agent: str = "claude"
    workdir: Optional[str] = None
    workspace_paths: Optional[list[str]] = None
    mcp_tools: Optional[list[str]] = None
    session_id: Optional[str] = None
    agent_role: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(
            model=kwargs.pop("model", "minimax/minimax-m2.7"),
            api_key=kwargs.pop("api_key", os.environ.get("OPENROUTER_API_KEY", "")),
            base_url=kwargs.pop("base_url", "https://openrouter.ai/api/v1"),
            **kwargs,
        )

    def _has_openrouter_api_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value().strip())

    def _fallback_model(self) -> GatewayChatModel:
        request_timeout = self.request_timeout
        timeout = int(request_timeout) if isinstance(request_timeout, (int, float)) else 300
        return GatewayChatModel(
            gateway_url=self.gateway_url,
            agent=self.fallback_agent,
            workdir=self.workdir,
            workspace_paths=self.workspace_paths,
            timeout=timeout,
            mcp_tools=self.mcp_tools,
            session_id=self.session_id,
            agent_role=self.agent_role,
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self._has_openrouter_api_key():
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return self._fallback_model()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        if self._has_openrouter_api_key():
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return await self._fallback_model()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)


# =========================================================================
#  Быстрый тест
# =========================================================================

if __name__ == "__main__":
    print("=== Testing GatewayClaude ===")
    claude = GatewayClaude()
    result = claude.invoke("Say hello in one sentence")
    print(f"Output: {result.content}")
    print(f"Profile: {result.additional_kwargs.get('profile_used')}")
    print(f"Time: {result.additional_kwargs.get('elapsed_sec')}s")
