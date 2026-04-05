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
from urllib.parse import quote_plus, urljoin

import httpx
from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_servers.logging_utils import sanitize_log_arguments, sanitize_result_preview
from orchestrator.guardrails.audit import record_guardrail_event
from orchestrator.guardrails.tool_safety import (
    scan_remote_tool_metadata,
    scan_tool_arguments,
    scan_tool_result,
)
from orchestrator.guardrails.wrappers import (
    build_block_message,
    build_guarded_tool_description,
    sanitize_tool_result,
)
from orchestrator.tools.builtin.code_exec import CodeExecTool
from orchestrator.tools.builtin.http_request import HttpRequestTool, _validate_url
from orchestrator.tools.builtin.shell_exec import ShellExecTool
from orchestrator.tools.security import tool_requires_guarded_wrapper, tool_runtime_allowed

LOG_DIR = Path(__file__).parent.parent / ".tool_logs"
LOG_DIR.mkdir(exist_ok=True)
EVENT_STREAM_PATH = os.getenv("CONFIGURED_TOOLS_EVENT_STREAM", "").strip()
EVENT_AGENT_ROLE = os.getenv("CONFIGURED_TOOLS_AGENT_ROLE", "").strip() or "agent"


def _load_tools(config_path: str | None) -> dict[str, dict[str, Any]]:
    if not config_path:
        return {}
    with open(config_path) as handle:
        payload = json.load(handle)
    return {
        item["id"]: item
        for item in payload.get("tools", [])
        if item.get("enabled", True)
    }

_CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CONFIGURED_TOOLS_PAYLOAD", "")
TOOLS = _load_tools(_CONFIG_PATH)
server = Server("configured-tools")
code_exec = CodeExecTool()
shell_exec = ShellExecTool()
http_request = HttpRequestTool()
EXTERNAL_MCP_TOOLS: dict[str, Tool] = {}
EXTERNAL_MCP_LOOKUP: dict[str, dict[str, Any]] = {}
EXTERNAL_MCP_INITIALIZED = False


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


def emit_runtime_event(event_type: str, title: str, detail: str = "", **extra: Any) -> None:
    if not EVENT_STREAM_PATH:
        return
    payload = {
        "type": event_type,
        "title": title,
        "detail": detail,
        "agent_id": EVENT_AGENT_ROLE,
        **extra,
    }
    event_path = Path(EVENT_STREAM_PATH)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _record_runtime_guardrail(
    action: str,
    phase: str,
    detail: str,
    *,
    tool_cfg: dict[str, Any],
    report: dict | Any = None,
    remote_name: str | None = None,
) -> None:
    tool_name = str(tool_cfg.get("name", tool_cfg.get("id", "")))
    if remote_name:
        tool_name = f"{tool_name}::{remote_name}"
    record_guardrail_event(
        source="configured_tools_server",
        action=action,
        phase=phase,
        tool_id=str(tool_cfg.get("id", "")),
        tool_name=tool_name,
        detail=detail,
        report=report,
        metadata={"remote_name": remote_name or ""},
    )


def _emit_guardrail_runtime_event(action: str, detail: str, *, tool_name: str, remote_name: str | None = None) -> None:
    emit_runtime_event(
        "tool_call_guardrailed",
        "Tool call guardrailed",
        detail,
        tool_name=tool_name,
        guardrail_action=action,
        remote_name=remote_name or "",
    )


def _runtime_argument_preview(arguments: dict[str, Any]) -> str:
    if not arguments:
        return ""
    preferred_keys = [
        "cypher",
        "query",
        "command",
        "path",
        "url",
        "input",
        "body",
        "params",
        "code",
    ]
    for key in preferred_keys:
        value = arguments.get(key)
        if value is None:
            continue
        text = str(value).replace("\n", " ").strip()
        if not text:
            continue
        return sanitize_result_preview(f"{key}: {text}")
    return sanitize_result_preview(json.dumps(sanitize_log_arguments(arguments), ensure_ascii=False))


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
    if tool_type == "bright_data_serp":
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Plain search query. The tool converts it into a Google search URL via Bright Data."},
                "url": {"type": "string", "description": "Optional full target URL instead of a query."},
                "format": {"type": "string", "description": "Optional response format override, usually raw or json."},
            },
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
    if tool_type == "http_request":
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to request"},
                "method": {"type": "string", "description": "HTTP method"},
                "body": {"type": "string", "description": "Request body or JSON string"},
                "headers": {"type": "string", "description": "JSON headers object"},
            },
            "required": ["url"],
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
    if tool_type == "code_exec":
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        }
    if tool_type == "shell":
        required = [] if str(tool_cfg.get("config", {}).get("command_template", "") or "").strip() else ["command"]
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "input": {"type": "string", "description": "Optional input rendered into the configured command template"},
                "workdir": {"type": "string", "description": "Working directory under /tmp"},
            },
            "required": required,
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
    if tool_type == "bright_data_serp":
        extra = cfg.get("description") or "Fetch current Google SERP pages or arbitrary URLs through Bright Data."
        return f"{name}: {extra} Use query for a search term or url for a full target URL."
    if tool_type in {"http_api", "custom_api"}:
        extra = cfg.get("description") or "Use the configured API safely through its base URL."
        return f"{name}: {extra} Base URL: {cfg.get('base_url', '')}"
    if tool_type == "http_request":
        return f"{name}: make an HTTP request to a full URL with SSRF protection."
    if tool_type == "ssh":
        host = cfg.get("host", "unknown-host")
        user = cfg.get("user", "user")
        port = cfg.get("port") or "22"
        extra = str(cfg.get("description", "") or "").strip()
        return f"{name}: {extra or f'execute remote commands on {user}@{host}:{port} over SSH.'}"
    if tool_type == "neo4j":
        return f"{name}: run Cypher queries against Neo4j at {cfg.get('bolt_url', '')}."
    if tool_type == "code_exec":
        return f"{name}: execute Python code in an isolated subprocess."
    if tool_type == "shell":
        extra = str(cfg.get("description", "") or cfg.get("command_template", "") or "").strip()
        return f"{name}: {extra or 'execute shell commands in a restricted /tmp workspace.'}"
    return name


def _proxy_tool_name(server_id: str, remote_name: str) -> str:
    return f"{server_id}__{remote_name}"


def _parse_json_object(raw_value: str, field_name: str) -> tuple[dict[str, str], str | None]:
    text = raw_value.strip()
    if not text:
        return {}, None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, f"invalid {field_name} JSON: {exc}"
    if not isinstance(parsed, dict):
        return {}, f"{field_name} must be a JSON object"
    return {str(key): str(value) for key, value in parsed.items()}, None


async def _list_remote_tools(tool_cfg: dict[str, Any]) -> list[Tool]:
    cfg = tool_cfg.get("config", {})
    transport = str(cfg.get("transport", "stdio") or "stdio").strip().lower()
    if transport == "http":
        url = str(cfg.get("url", "") or "").strip()
        if not url:
            raise ValueError("HTTP MCP URL is required")
        headers, error = _parse_json_object(str(cfg.get("headers", "") or ""), "headers")
        if error:
            raise ValueError(error)
        async with httpx.AsyncClient(headers=headers, timeout=10) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    result = await asyncio.wait_for(session.list_tools(), timeout=10)
        return list(getattr(result, "tools", []) or [])

    command = str(cfg.get("command", "") or "").strip()
    if not command:
        raise ValueError("stdio MCP command is required")
    parts = shlex.split(command)
    extra_args = shlex.split(str(cfg.get("args", "") or "").strip()) if str(cfg.get("args", "") or "").strip() else []
    env_vars, error = _parse_json_object(str(cfg.get("env", "") or ""), "env")
    if error:
        raise ValueError(error)
    params = StdioServerParameters(
        command=parts[0],
        args=[*parts[1:], *extra_args],
        env=env_vars or None,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=10)
            result = await asyncio.wait_for(session.list_tools(), timeout=10)
    return list(getattr(result, "tools", []) or [])


def _result_to_text(result: Any) -> str:
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            chunks.append(str(text))
            continue
        if hasattr(item, "model_dump"):
            chunks.append(json.dumps(item.model_dump(), ensure_ascii=False))
            continue
        chunks.append(str(item))
    structured = getattr(result, "structuredContent", None)
    if structured:
        chunks.append(json.dumps(structured, ensure_ascii=False, indent=2))
    if not chunks:
        return ""
    return "\n\n".join(chunk for chunk in chunks if str(chunk).strip()).strip()


async def _call_remote_tool(tool_cfg: dict[str, Any], remote_name: str, arguments: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    transport = str(cfg.get("transport", "stdio") or "stdio").strip().lower()
    if transport == "http":
        url = str(cfg.get("url", "") or "").strip()
        headers, error = _parse_json_object(str(cfg.get("headers", "") or ""), "headers")
        if error:
            raise ValueError(error)
        async with httpx.AsyncClient(headers=headers, timeout=30) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    result = await asyncio.wait_for(session.call_tool(remote_name, arguments or {}), timeout=45)
        return _result_to_text(result)

    command = str(cfg.get("command", "") or "").strip()
    parts = shlex.split(command)
    extra_args = shlex.split(str(cfg.get("args", "") or "").strip()) if str(cfg.get("args", "") or "").strip() else []
    env_vars, error = _parse_json_object(str(cfg.get("env", "") or ""), "env")
    if error:
        raise ValueError(error)
    params = StdioServerParameters(
        command=parts[0],
        args=[*parts[1:], *extra_args],
        env=env_vars or None,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=10)
            result = await asyncio.wait_for(session.call_tool(remote_name, arguments or {}), timeout=45)
    return _result_to_text(result)


async def _ensure_external_tool_cache() -> None:
    global EXTERNAL_MCP_INITIALIZED
    if EXTERNAL_MCP_INITIALIZED:
        return

    external_tools: dict[str, Tool] = {}
    external_lookup: dict[str, dict[str, Any]] = {}
    for tool_cfg in TOOLS.values():
        if tool_cfg.get("tool_type") != "mcp_server" or not tool_runtime_allowed(tool_cfg):
            continue
        try:
            remote_tools = await _list_remote_tools(tool_cfg)
        except Exception as exc:
            fallback_name = _proxy_tool_name(tool_cfg["id"], "connection_error")
            external_tools[fallback_name] = Tool(
                name=fallback_name,
                description=f"{tool_cfg['name']}: MCP connection failed ({exc})",
                inputSchema={"type": "object", "properties": {}},
            )
            external_lookup[fallback_name] = {
                "tool_cfg": tool_cfg,
                "remote_name": "__connection_error__",
                "error": str(exc),
            }
            continue

        for remote_tool in remote_tools:
            wrapped_name = _proxy_tool_name(tool_cfg["id"], remote_tool.name)
            description = (remote_tool.description or remote_tool.name or "").strip()
            metadata_report = scan_remote_tool_metadata(tool_cfg, remote_tool.name, description)
            if metadata_report.recommended_action == "block":
                blocked_description = build_guarded_tool_description(tool_cfg["name"], metadata_report)
                external_tools[wrapped_name] = Tool(
                    name=wrapped_name,
                    description=blocked_description,
                    inputSchema={"type": "object", "properties": {}},
                )
                external_lookup[wrapped_name] = {
                    "tool_cfg": tool_cfg,
                    "remote_name": remote_tool.name,
                    "blocked_report": metadata_report.model_dump(),
                }
                _record_runtime_guardrail(
                    "block",
                    "metadata",
                    metadata_report.summary,
                    tool_cfg=tool_cfg,
                    report=metadata_report,
                    remote_name=remote_tool.name,
                )
                continue
            rendered_description = f"{tool_cfg['name']} · {description}"
            if metadata_report.recommended_action in {"warn", "log"} or tool_requires_guarded_wrapper(tool_cfg):
                rendered_description = (
                    build_guarded_tool_description(rendered_description, metadata_report)
                    if metadata_report.recommended_action in {"warn", "log"}
                    else f"{rendered_description} (guarded wrapper)"
                )
                _record_runtime_guardrail(
                    "warn",
                    "metadata",
                    metadata_report.summary if metadata_report.recommended_action in {"warn", "log"} else "Remote MCP tool is exposed through a guarded wrapper.",
                    tool_cfg=tool_cfg,
                    report=metadata_report,
                    remote_name=remote_tool.name,
                )
            external_tools[wrapped_name] = Tool(
                name=wrapped_name,
                description=rendered_description,
                inputSchema=remote_tool.inputSchema or {"type": "object", "properties": {}},
                annotations=getattr(remote_tool, "annotations", None),
            )
            external_lookup[wrapped_name] = {
                "tool_cfg": tool_cfg,
                "remote_name": remote_tool.name,
                "guardrail_report": metadata_report.model_dump() if metadata_report.recommended_action in {"warn", "log"} else {},
            }

    EXTERNAL_MCP_TOOLS.clear()
    EXTERNAL_MCP_TOOLS.update(external_tools)
    EXTERNAL_MCP_LOOKUP.clear()
    EXTERNAL_MCP_LOOKUP.update(external_lookup)
    EXTERNAL_MCP_INITIALIZED = True


def _merge_headers(tool_cfg: dict[str, Any], extra_headers: str) -> tuple[dict[str, str], str | None]:
    headers: dict[str, str] = {}
    cfg = tool_cfg.get("config", {})
    auth_header = cfg.get("auth_header", "").strip()
    content_type = cfg.get("content_type", "").strip()
    static_headers_raw = str(cfg.get("headers_json", "") or "").strip()
    if auth_header:
        headers["Authorization"] = auth_header
    if content_type:
        headers["Content-Type"] = content_type
    if static_headers_raw:
        try:
            parsed_static_headers = json.loads(static_headers_raw)
        except json.JSONDecodeError:
            return {}, "invalid configured static headers JSON"
        if not isinstance(parsed_static_headers, dict):
            return {}, "configured static headers must be a JSON object"
        headers.update({str(key): str(value) for key, value in parsed_static_headers.items()})
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


async def _call_bright_data_serp(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    api_key = str(cfg.get("api_key", "")).strip()
    zone = str(cfg.get("zone", "")).strip()
    response_format = str(arguments.get("format") or cfg.get("format") or "raw").strip() or "raw"
    query = str(arguments.get("query", "")).strip()
    target_url = str(arguments.get("url", "")).strip()

    if not api_key:
        return f"[{tool_cfg['id']}] Error: API key is not configured"
    if not zone:
        return f"[{tool_cfg['id']}] Error: zone is not configured"
    if not target_url and not query:
        return f"[{tool_cfg['id']}] Error: provide either 'query' or 'url'"

    if not target_url:
        target_url = f"https://www.google.com/search?q={quote_plus(query)}"

    safety_error = _validate_url(target_url)
    if safety_error:
        return f"[{tool_cfg['id']}] Error: {safety_error}"

    payload = {
        "zone": zone,
        "url": target_url,
        "format": response_format,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.brightdata.com/request",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    return f"[{tool_cfg['id']}] Bright Data SERP {response.status_code} for {query or target_url}\n{response.text[:5000]}"


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


async def _call_http_request(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    url = str(arguments.get("url", "")).strip()
    if not url:
        return f"[{tool_cfg['id']}] Error: 'url' is required"
    result = await http_request.execute(
        url=url,
        method=str(arguments.get("method", "GET") or "GET"),
        body=str(arguments.get("body", "") or ""),
        headers=str(arguments.get("headers", "") or ""),
    )
    return result.replace("[http_request]", f"[{tool_cfg['id']}]")


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


async def _call_code_exec(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    code = str(arguments.get("code", "")).strip()
    if not code:
        return f"[{tool_cfg['id']}] Error: 'code' is required"
    result = await code_exec.execute(code=code)
    return result.replace("[code_exec]", f"[{tool_cfg['id']}]")


async def _call_shell(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    cfg = tool_cfg.get("config", {})
    command = str(arguments.get("command", "")).strip()
    if not command:
        command_template = str(cfg.get("command_template", "")).strip()
        if command_template:
            command = _render_template(command_template, str(arguments.get("input", "") or ""))
    if not command:
        return f"[{tool_cfg['id']}] Error: 'command' is required"
    workdir = str(arguments.get("workdir", "/tmp") or "/tmp")
    result = await shell_exec.execute(command=command, workdir=workdir)
    return result.replace("[shell]", f"[{tool_cfg['id']}]")


async def _dispatch(tool_cfg: dict[str, Any], arguments: dict[str, Any]) -> str:
    tool_type = tool_cfg["tool_type"]
    if tool_type == "brave_search":
        return await _call_brave(tool_cfg, arguments)
    if tool_type == "perplexity":
        return await _call_perplexity(tool_cfg, arguments)
    if tool_type == "bright_data_serp":
        return await _call_bright_data_serp(tool_cfg, arguments)
    if tool_type in {"http_api", "custom_api"}:
        return await _call_http_api(tool_cfg, arguments)
    if tool_type == "http_request":
        return await _call_http_request(tool_cfg, arguments)
    if tool_type == "ssh":
        return await _call_ssh(tool_cfg, arguments)
    if tool_type == "neo4j":
        return await _call_neo4j(tool_cfg, arguments)
    if tool_type == "code_exec":
        return await _call_code_exec(tool_cfg, arguments)
    if tool_type == "shell":
        return await _call_shell(tool_cfg, arguments)
    return f"[{tool_cfg['id']}] Error: unsupported tool type '{tool_type}'"


@server.list_tools()
async def list_tools() -> list[Tool]:
    await _ensure_external_tool_cache()
    base_tools = [
        Tool(
            name=tool_cfg["id"],
            description=_description_for(tool_cfg),
            inputSchema=_schema_for(tool_cfg),
        )
        for tool_cfg in TOOLS.values()
        if tool_cfg.get("tool_type") != "mcp_server" and tool_runtime_allowed(tool_cfg)
    ]
    return [*base_tools, *EXTERNAL_MCP_TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    t0 = time.time()
    preview = _runtime_argument_preview(arguments)
    emit_runtime_event(
        "tool_call_started",
        "Tool call started",
        preview or name,
        tool_name=name,
    )
    await _ensure_external_tool_cache()
    tool_cfg = TOOLS.get(name)
    success = False
    if tool_cfg:
        if not tool_runtime_allowed(tool_cfg):
            report = tool_cfg.get("last_guardrail_report") or {}
            summary = str(report.get("summary") or "tool is blocked")
            result = f"[{name}] Blocked by guardrails: {summary}"
            _record_runtime_guardrail("block", "config", summary, tool_cfg=tool_cfg, report=report)
            _emit_guardrail_runtime_event("block", summary, tool_name=name)
        else:
            argument_report = scan_tool_arguments(tool_cfg, arguments)
            if argument_report.recommended_action == "block":
                result = build_block_message(name, argument_report)
                _record_runtime_guardrail("block", "arguments", argument_report.summary, tool_cfg=tool_cfg, report=argument_report)
                _emit_guardrail_runtime_event("block", argument_report.summary, tool_name=name)
            else:
                if argument_report.recommended_action in {"warn", "log"}:
                    _record_runtime_guardrail("warn", "arguments", argument_report.summary, tool_cfg=tool_cfg, report=argument_report)
                    _emit_guardrail_runtime_event("warn", argument_report.summary, tool_name=name)
                try:
                    result = await _dispatch(tool_cfg, arguments)
                    success = not result.lstrip().startswith(f"[{name}] Error:")
                except Exception as exc:
                    result = f"[{name}] Error: {exc}"
                result_report = scan_tool_result(tool_cfg, result)
                if result_report.recommended_action == "block":
                    result = build_block_message(name, result_report)
                    success = False
                    _record_runtime_guardrail("block", "result", result_report.summary, tool_cfg=tool_cfg, report=result_report)
                    _emit_guardrail_runtime_event("block", result_report.summary, tool_name=name)
                elif result_report.recommended_action in {"warn", "log"}:
                    result = sanitize_tool_result(result, result_report)
                    _record_runtime_guardrail("warn", "result", result_report.summary, tool_cfg=tool_cfg, report=result_report)
                    _emit_guardrail_runtime_event("warn", result_report.summary, tool_name=name)
    elif name in EXTERNAL_MCP_LOOKUP:
        remote = EXTERNAL_MCP_LOOKUP[name]
        blocked_report = remote.get("blocked_report") or {}
        if blocked_report:
            summary = str(blocked_report.get("summary") or "remote tool metadata is blocked")
            result = f"[{name}] Blocked by guardrails: {summary}"
            _record_runtime_guardrail("block", "metadata", summary, tool_cfg=remote["tool_cfg"], report=blocked_report, remote_name=remote.get("remote_name"))
            _emit_guardrail_runtime_event("block", summary, tool_name=name, remote_name=remote.get("remote_name"))
        elif remote.get("remote_name") == "__connection_error__":
            result = f"[{name}] Error: {remote.get('error', 'MCP connection failed')}"
        else:
            argument_report = scan_tool_arguments(remote["tool_cfg"], arguments, remote_name=remote["remote_name"])
            if argument_report.recommended_action == "block":
                result = build_block_message(name, argument_report)
                _record_runtime_guardrail("block", "arguments", argument_report.summary, tool_cfg=remote["tool_cfg"], report=argument_report, remote_name=remote["remote_name"])
                _emit_guardrail_runtime_event("block", argument_report.summary, tool_name=name, remote_name=remote["remote_name"])
            else:
                if argument_report.recommended_action in {"warn", "log"}:
                    _record_runtime_guardrail("warn", "arguments", argument_report.summary, tool_cfg=remote["tool_cfg"], report=argument_report, remote_name=remote["remote_name"])
                    _emit_guardrail_runtime_event("warn", argument_report.summary, tool_name=name, remote_name=remote["remote_name"])
                try:
                    result = await _call_remote_tool(remote["tool_cfg"], remote["remote_name"], arguments)
                    if result:
                        result = f"[{name}] {result}"
                    else:
                        result = f"[{name}] Tool executed successfully."
                    success = True
                except Exception as exc:
                    result = f"[{name}] Error: {exc}"
                result_report = scan_tool_result(remote["tool_cfg"], result, remote_name=remote["remote_name"])
                if result_report.recommended_action == "block":
                    result = build_block_message(name, result_report)
                    success = False
                    _record_runtime_guardrail("block", "result", result_report.summary, tool_cfg=remote["tool_cfg"], report=result_report, remote_name=remote["remote_name"])
                    _emit_guardrail_runtime_event("block", result_report.summary, tool_name=name, remote_name=remote["remote_name"])
                elif result_report.recommended_action in {"warn", "log"}:
                    result = sanitize_tool_result(result, result_report)
                    _record_runtime_guardrail("warn", "result", result_report.summary, tool_cfg=remote["tool_cfg"], report=result_report, remote_name=remote["remote_name"])
                    _emit_guardrail_runtime_event("warn", result_report.summary, tool_name=name, remote_name=remote["remote_name"])
    else:
        result = f"Unknown configured tool: {name}"
    log_tool_call(name, arguments, result, round(time.time() - t0, 2))
    emit_runtime_event(
        "tool_call_finished",
        "Tool call finished",
        sanitize_result_preview(result),
        tool_name=name,
        elapsed_sec=round(time.time() - t0, 2),
        success=success,
    )
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
