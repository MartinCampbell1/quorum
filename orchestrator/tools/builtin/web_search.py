"""Brave Search API tool."""

import os

import httpx

from orchestrator.tools.base import BaseTool, ToolParam


class WebSearchTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="web_search",
            description="Search the web for current information. Use for factual queries, recent events, technical docs.",
            parameters=[
                ToolParam(name="query", type="string", description="Search query"),
                ToolParam(name="count", type="number", description="Number of results (1-10)", required=False),
            ],
        )
        self.api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")

    async def execute(self, query: str, count: int = 5, **kwargs) -> str:  # type: ignore[override]
        if not self.api_key:
            return "[web_search] Error: BRAVE_SEARCH_API_KEY not set"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
                params={"q": query, "count": min(count, 10)},
            )
            if resp.status_code != 200:
                return f"[web_search] Error: HTTP {resp.status_code}"
            data = resp.json()
            results = data.get("web", {}).get("results", [])
            if not results:
                return f"[web_search] No results for: {query}"
            lines = [f"## Web search results for: {query}\n"]
            for r in results[:count]:
                lines.append(f"**{r.get('title', '')}**\n{r.get('url', '')}\n{r.get('description', '')}\n")
            return "\n".join(lines)
