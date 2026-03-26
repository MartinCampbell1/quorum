#!/usr/bin/env python3
"""MCP Search Server — exposes web_search and perplexity_search tools via stdio transport."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_DIR = Path(__file__).parent.parent / ".tool_logs"
LOG_DIR.mkdir(exist_ok=True)


def log_tool_call(server_name: str, tool_name: str, arguments: dict, result: str, elapsed: float) -> None:
    """Append tool call to log file."""
    entry = {
        "server": server_name,
        "tool": tool_name,
        "arguments": sanitize_log_arguments(arguments),
        "result_preview": sanitize_result_preview(result),
        "elapsed_sec": elapsed,
        "timestamp": time.time(),
    }
    log_file = LOG_DIR / f"{server_name}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_servers.logging_utils import sanitize_log_arguments, sanitize_result_preview
from orchestrator.tools.builtin.perplexity import PerplexityTool
from orchestrator.tools.builtin.web_search import WebSearchTool

server = Server("search-server")
web_search = WebSearchTool()
perplexity = PerplexityTool()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web for current information using Brave Search. Use for factual queries, recent events, technical documentation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {
                        "type": "number",
                        "description": "Number of results (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="perplexity_search",
            description="AI-powered search with citations via Perplexity Sonar. Better than web_search for complex questions requiring synthesis and analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Question or search query"},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    t0 = time.time()
    if name == "web_search":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            result = "[web_search] Error: 'query' parameter required (string)"
        else:
            result = await web_search.execute(query=query, count=int(arguments.get("count", 5)))
    elif name == "perplexity_search":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            result = "[perplexity] Error: 'query' parameter required (string)"
        else:
            result = await perplexity.execute(query=query)
    else:
        result = f"Unknown tool: {name}"
    log_tool_call("search-server", name, arguments, result, round(time.time() - t0, 2))
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
