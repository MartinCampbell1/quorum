"""Generic HTTP request tool."""

import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from orchestrator.tools.base import BaseTool, ToolParam


def _validate_url(url: str) -> str | None:
    """Return error message if URL is unsafe, None if OK."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL"
    if parsed.scheme not in ("http", "https"):
        return f"Scheme '{parsed.scheme}' not allowed (http/https only)"
    hostname = parsed.hostname or ""
    if not hostname:
        return "No hostname"
    # Block internal/private IPs
    try:
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return f"Internal IP {ip} blocked (SSRF protection)"
    except socket.gaierror:
        return f"Cannot resolve hostname: {hostname}"
    return None


class HttpRequestTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="http_request",
            description="Make HTTP requests to APIs. Supports GET, POST, PUT, DELETE.",
            parameters=[
                ToolParam(name="url", type="string", description="Full URL to request"),
                ToolParam(name="method", type="string", description="HTTP method: GET, POST, PUT, DELETE", required=False),
                ToolParam(name="body", type="string", description="JSON request body (for POST/PUT)", required=False),
                ToolParam(name="headers", type="string", description="JSON headers object", required=False),
            ],
        )

    async def execute(self, url: str, method: str = "GET", body: str = "", headers: str = "", **kwargs: Any) -> str:
        error = _validate_url(url)
        if error:
            return f"[http_request] Error: {error}"

        parsed_headers: dict[str, str] = {}
        if headers:
            try:
                parsed_headers = json.loads(headers)
            except json.JSONDecodeError:
                return "[http_request] Error: invalid headers JSON"

        parsed_body: dict[str, Any] | str | None = None
        if body:
            try:
                parsed_body = json.loads(body)
            except json.JSONDecodeError:
                parsed_body = body

        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            try:
                resp = await client.request(
                    method.upper(),
                    url,
                    json=parsed_body if isinstance(parsed_body, dict) else None,
                    content=parsed_body.encode() if isinstance(parsed_body, str) else None,
                    headers=parsed_headers,
                )
                text = resp.text[:5000]
                return f"[http_request] {method} {url} → {resp.status_code}\n{text}"
            except Exception as e:
                return f"[http_request] Error: {e}"
