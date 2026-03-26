"""Perplexity Sonar API tool."""

import os
from typing import Any

import httpx

from orchestrator.tools.base import BaseTool, ToolParam


class PerplexityTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="perplexity",
            description="AI-powered search with citations. Better than web_search for complex questions requiring synthesis.",
            parameters=[
                ToolParam(name="query", type="string", description="Question or search query"),
            ],
        )
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "")

    async def execute(self, query: str, **kwargs: Any) -> str:
        if not self.api_key:
            return "[perplexity] Error: PERPLEXITY_API_KEY not set"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": "sonar", "messages": [{"role": "user", "content": query}]},
            )
            if resp.status_code != 200:
                return f"[perplexity] Error: HTTP {resp.status_code}"
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])
            result = f"## Perplexity answer for: {query}\n\n{content}"
            if citations:
                result += "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations[:5])
            return result
