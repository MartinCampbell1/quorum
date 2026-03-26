#!/usr/bin/env python3
"""MCP Execution Server — exposes code_exec, shell_exec, http_request tools."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_DIR = Path(__file__).parent.parent / ".tool_logs"
LOG_DIR.mkdir(exist_ok=True)


def log_tool_call(server_name: str, tool_name: str, arguments: dict, result: str, elapsed: float) -> None:
    """Append tool call to log file."""
    entry = {
        "server": server_name,
        "tool": tool_name,
        "arguments": arguments,
        "result_preview": result[:500],
        "elapsed_sec": elapsed,
        "timestamp": time.time(),
    }
    log_file = LOG_DIR / f"{server_name}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from orchestrator.tools.builtin.code_exec import CodeExecTool
from orchestrator.tools.builtin.shell_exec import ShellExecTool
from orchestrator.tools.builtin.http_request import HttpRequestTool

server = Server("exec-server")
code_exec = CodeExecTool()
shell_exec = ShellExecTool()
http_request = HttpRequestTool()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="code_exec",
            description="Execute Python code and return stdout/stderr. Use for calculations, data processing, testing code snippets. 30s timeout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="shell_exec",
            description="Execute shell commands. Use for file operations, git, system info, package management. 30s timeout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "workdir": {"type": "string", "description": "Working directory (default: /tmp)"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="http_request",
            description="Make HTTP requests to any API. Supports GET, POST, PUT, DELETE with custom headers and body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to request"},
                    "method": {"type": "string", "description": "HTTP method (GET/POST/PUT/DELETE)", "default": "GET"},
                    "body": {"type": "string", "description": "JSON request body for POST/PUT"},
                    "headers": {"type": "string", "description": "JSON headers object"},
                },
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    t0 = time.time()
    try:
        if name == "code_exec":
            result = await code_exec.execute(**arguments)
        elif name == "shell_exec":
            result = await shell_exec.execute(**arguments)
        elif name == "http_request":
            result = await http_request.execute(**arguments)
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        result = f"[{name}] Error: {e}"

    log_tool_call("exec-server", name, arguments, result, round(time.time() - t0, 2))
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
