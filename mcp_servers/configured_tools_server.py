#!/usr/bin/env python3
"""Dynamic MCP server for user-configured tools."""

import asyncio
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_servers.logging_utils import sanitize_log_arguments, sanitize_result_preview
from orchestrator.tools.builtin.http_request import _validate_url

LOG_DIR = Path(__file__).parent.parent / ".tool_logs"
LOG_DIR.mkdir(exist_ok=True)


def _load_tools(config_path: str) -> dict[str, dict[str, Any]]:
    with open(config_path) as handle:
        payload = json.load(handle)
    return {
        item["id"]: item
        for item in payload.get("tools", [])
        if item.get("enabled", True)
    }


TOOLS = _load_tools(sys.argv[1]) if len(sys.argv) > 1 else {}
server = Server("configured-tools")


def log_tool_call(tool_name: str, arguments: dict, result: str, elapsed: float) -> None:
    entry = {
        "server": "configured-tools",
        "tool": tool_name,
        "arguments": sanitize_log_arguments(arguments),
        "result_preview": sanitize_result_preview(result),
        "elapsed_sec": elapsed,
        "timestamp": time.time(),
    }
    log_file = LOG_DIR / "configured-tools.jsonl"
    with open(log_file, "a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _schema_for(tool_cfg: dict[str, Any]) -> dict[str, Any]:
    tool_type = tool_cfg["tool_type"]
    if tool_type == "brave_search":
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "number", "description": "Number of results (1-10)", "default": 5},
            },
            "required": ["query"],
        }
    if tool_type == "perplexity":
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or search query"},
            },
            "required": ["query"],
        }
    if tool_type in {"http_api", "custom_api"}:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path appended to the configured base URL"},
                "method": {"type": "string", "description": "Override HTTP method"},
                "params": {"type": "string", "description": "JSON object with query params"},
                "body": {"type": "string", "description": "Request body or JSON string"},
                "input": {"type": "string", "description": "Short free-form input for body templates"},
                "headers": {"type": "string", "description": "JSON headers merged into the configured defaults"},
            },
        }
    if tool_type == "ssh":
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Remote shell command to execute over SSH"},
            },
            "required": ["command"],
        }
    if tool_type == "neo4j":
        return {
            "type": "object",
            "properties": {
                "cypher": {"type": "string", "description": "Cypher query to execute"},
                "parameters": {"type": "string", "description": "JSON object with Cypher parameters"},
            },
            "required": ["cypher"],
        }
    return {"type": "object", "properties": {}}


def _description_for(tool_cfg: dict[str, Any]) -> str:
    tool_type = tool_cfg["tool_type"]
    name = tool_cfg["name"]
    cfg = tool_cfg.get("config", {})
    if tool_type == "brave_search":
        return f"{name}: web search via Brave Search for current information."
    if tool_type == "perplexity":
        return f"{name}: Perplexity Sonar search with citations."
    if tool_type in {"http_api", "custom_api"}:
        extra = cfg.get("description") or "Use the configured API safely through its base URL."
        return f"{name}: {extra} Base URL: {cfg.get('base_url', '')}"
    if tool_type == "ssh":
        host = cfg.get("host", "unknown-host")
        user = cfg.get("user", "user")
        port = cfg.get("port") or "22"
        return f"{name}: execute remote commands on {user}@{host}:{port} over SSH."
    if tool_type == "neo4j":
        return f"{name}: run Cypher queries against Neo4j at {cfg.get('bolt_url', '')}."
    return name


def _merge_headers(tool_cfg: dict[str, Any], extra_headers: str) -> tuple[dict[str, str], str | None]:
    headers: dict[str, str] = {}
    cfg = tool_cfg.get("config", {})
    auth_header = cfg.get("auth_header", "").strip()
    content_type = cfg.get("content_type", "").strip()
    if auth_header:
        headers["Authorization"] = auth_header
    if content_type:
        headers["Content-Type"] = content_type
    if extra_headers:
        try:
            parsed = json.loads(extra_headers)
        except json.JSONDecodeError:
            return {}, "invalid headers JSON"
        if not isinstance(parsed, dict):
            return {}, "headers must be a JSON object"
        headers.update({str(key): str(value) for key, value in parsed.items()})
    return headers, None


def _render_template(template: str, input_text: str) -> str:
    if not template:
        return ""
    return template.replace("{input}", input_text)


async def _call_brave(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    api_key = tool_cfg.get("config", {}).get("api_key", "").strip()
    if not api_key:
        return f"[{tool_cfg['id']}] Error: API key is not configured"
    query = str(arguments.get("query", "")).strip()
    if not query:
        return f"[{tool_cfg['id']}] Error: 'query' is required"
    count = min(int(arguments.get("count", 5)), 10)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params={"q": query, "count": count},
        )
    if response.status_code != 200:
        return f"[{tool_cfg['id']}] Error: HTTP {response.status_code}"
    data = response.json()
    results = data.get("web", {}).get("results", [])
    if not results:
        return f"[{tool_cfg['id']}] No results for: {query}"
    lines = [f"## {tool_cfg['name']} results for: {query}", ""]
    for result in results[:count]:
        lines.append(f"**{result.get('title', '')}**")
        lines.append(result.get("url", ""))
        lines.append(result.get("description", ""))
        lines.append("")
    return "\n".join(lines).strip()


async def _call_perplexity(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    api_key = tool_cfg.get("config", {}).get("api_key", "").strip()
    if not api_key:
        return f"[{tool_cfg['id']}] Error: API key is not configured"
    query = str(arguments.get("query", "")).strip()
    if not query:
        return f"[{tool_cfg['id']}] Error: 'query' is required"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "sonar", "messages": [{"role": "user", "content": query}]},
        )
    if response.status_code != 200:
        return f"[{tool_cfg['id']}] Error: HTTP {response.status_code}"
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations", [])
    result = f"## {tool_cfg['name']} answer for: {query}\n\n{content}"
    if citations:
        result += "\n\nSources:\n" + "\n".join(f"- {citation}" for citation in citations[:5])
    return result


async def _call_http_api(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    base_url = cfg.get("base_url", "").strip()
    if not base_url:
        return f"[{tool_cfg['id']}] Error: base_url is not configured"

    path = str(arguments.get("path", "")).strip()
    if path and not path.startswith("/"):
        path = f"/{path}"
    url = urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/")) if path else base_url
    safety_error = _validate_url(url)
    if safety_error:
        return f"[{tool_cfg['id']}] Error: {safety_error}"

    method = str(arguments.get("method") or cfg.get("method") or "GET").upper()
    params_raw = str(arguments.get("params", "")).strip()
    params = None
    if params_raw:
        try:
            params = json.loads(params_raw)
        except json.JSONDecodeError:
            return f"[{tool_cfg['id']}] Error: params must be valid JSON"
        if not isinstance(params, dict):
            return f"[{tool_cfg['id']}] Error: params must be a JSON object"

    headers, header_error = _merge_headers(tool_cfg, str(arguments.get("headers", "")).strip())
    if header_error:
        return f"[{tool_cfg['id']}] Error: {header_error}"

    body = str(arguments.get("body", "")).strip()
    if not body and cfg.get("body_template") and arguments.get("input"):
        body = _render_template(str(cfg.get("body_template", "")), str(arguments.get("input", "")))

    json_body: Any = None
    content_body: bytes | None = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError:
            content_body = body.encode()

    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.request(
            method,
            url,
            params=params,
            json=json_body,
            content=content_body,
            headers=headers,
        )

    text = response.text[:5000]
    return f"[{tool_cfg['id']}] {method} {url} -> {response.status_code}\n{text}"


async def _call_ssh(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    command = str(arguments.get("command", "")).strip()
    if not command:
        return f"[{tool_cfg['id']}] Error: 'command' is required"

    host = cfg.get("host", "").strip()
    user = cfg.get("user", "").strip()
    if not host or not user:
        return f"[{tool_cfg['id']}] Error: host and user must be configured"

    auth_type = (cfg.get("auth_type") or "key").strip()
    if auth_type == "password":
        return f"[{tool_cfg['id']}] Error: password SSH auth is not supported in this build; use a key path"

    ssh_cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(cfg.get("port") or "22"),
    ]
    key_path = cfg.get("password", "").strip()
    if key_path:
        ssh_cmd.extend(["-i", key_path])
    ssh_cmd.append(f"{user}@{host}")
    ssh_cmd.append(command)

    proc = await asyncio.create_subprocess_exec(
        *ssh_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        return f"[{tool_cfg['id']}] Error: SSH command timed out after 30s"

    output = stdout.decode("utf-8", errors="replace")[:3000]
    errors = stderr.decode("utf-8", errors="replace")[:1000]
    result = f"[{tool_cfg['id']}] ssh {user}@{host}\nExit: {proc.returncode}\n"
    if output:
        result += output + "\n"
    if errors:
        result += f"stderr: {errors}\n"
    return result.strip()


def _run_neo4j_query(tool_cfg: dict[str, Any], cypher: str, parameters: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    driver = GraphDatabase.driver(
        cfg.get("bolt_url", ""),
        auth=(cfg.get("user", ""), cfg.get("password", "")),
    )
    try:
        with driver.session(database=cfg.get("database") or None) as session:
            result = session.run(cypher, parameters)
            records = result.data()
            summary = result.consume()
    finally:
        driver.close()

    payload = json.dumps(records[:20], ensure_ascii=False, indent=2)
    return (
        f"[{tool_cfg['id']}] Query completed.\n"
        f"Records: {len(records)}\n"
        f"Nodes created: {summary.counters.nodes_created}\n"
        f"Relationships created: {summary.counters.relationships_created}\n"
        f"{payload}"
    )


async def _call_neo4j(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    cypher = str(arguments.get("cypher", "")).strip()
    if not cypher:
        return f"[{tool_cfg['id']}] Error: 'cypher' is required"

    parameters_raw = str(arguments.get("parameters", "")).strip()
    parameters: dict[str, Any] = {}
    if parameters_raw:
        try:
            parsed = json.loads(parameters_raw)
        except json.JSONDecodeError:
            return f"[{tool_cfg['id']}] Error: parameters must be valid JSON"
        if not isinstance(parsed, dict):
            return f"[{tool_cfg['id']}] Error: parameters must be a JSON object"
        parameters = parsed

    try:
        return await asyncio.to_thread(_run_neo4j_query, tool_cfg, cypher, parameters)
    except Exception as exc:
        return f"[{tool_cfg['id']}] Error: {exc}"


async def _dispatch(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    tool_type = tool_cfg["tool_type"]
    if tool_type == "brave_search":
        return await _call_brave(tool_cfg, arguments)
    if tool_type == "perplexity":
        return await _call_perplexity(tool_cfg, arguments)
    if tool_type in {"http_api", "custom_api"}:
        return await _call_http_api(tool_cfg, arguments)
    if tool_type == "ssh":
        return await _call_ssh(tool_cfg, arguments)
    if tool_type == "neo4j":
        return await _call_neo4j(tool_cfg, arguments)
    return f"[{tool_cfg['id']}] Error: unsupported tool type '{tool_type}'"


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=tool_cfg["id"],
            description=_description_for(tool_cfg),
            inputSchema=_schema_for(tool_cfg),
        )
        for tool_cfg in TOOLS.values()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    tool_cfg = TOOLS.get(name)
    t0 = time.time()
    if not tool_cfg:
        result = f"Unknown configured tool: {name}"
    else:
        try:
            result = await _dispatch(tool_cfg, arguments)
        except Exception as exc:
            result = f"[{name}] Error: {exc}"
    log_tool_call(name, arguments, result, round(time.time() - t0, 2))
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
