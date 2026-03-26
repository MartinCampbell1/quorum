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
    model_override: Optional[str] = None
    timeout: int = 300
    mcp_tools: Optional[list[str]] = None

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
                },
            )
            resp.raise_for_status()
            data = resp.json()

        output = data.get("output", "")

        # Обработать stop tokens
        if stop:
            for s in stop:
                if s in output:
                    output = output[: output.index(s)]

        message = AIMessage(
            content=output,
            additional_kwargs={
                "profile_used": data.get("profile_used"),
                "elapsed_sec": data.get("elapsed_sec"),
                "retries": data.get("retries", 0),
            },
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
                },
            )
            resp.raise_for_status()
            data = resp.json()

        output = data.get("output", "")

        if stop:
            for s in stop:
                if s in output:
                    output = output[: output.index(s)]

        message = AIMessage(
            content=output,
            additional_kwargs={
                "profile_used": data.get("profile_used"),
                "elapsed_sec": data.get("elapsed_sec"),
                "retries": data.get("retries", 0),
            },
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
    """MiniMax m2.7 via OpenRouter. For lightweight tasks: summaries, formatting, voting."""

    def __init__(self, **kwargs):
        super().__init__(
            model=kwargs.pop("model", "minimax/minimax-m2.7"),
            api_key=kwargs.pop("api_key", "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"),
            base_url=kwargs.pop("base_url", "https://openrouter.ai/api/v1"),
            **kwargs,
        )


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
