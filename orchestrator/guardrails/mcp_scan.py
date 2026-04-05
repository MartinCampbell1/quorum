"""Static scans for configured tools and MCP connectors."""

from __future__ import annotations

import ipaddress
import json
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from orchestrator.guardrails.policies import GuardrailFinding, GuardrailScanReport, compile_scan_report
from orchestrator.guardrails.tool_safety import prompt_injection_signals
from orchestrator.tool_configs import ToolConfig, mcp_server_transport

LAUNCHER_BINARIES = {"python", "python3", "node", "bash", "sh", "uvx", "npx", "pnpm", "yarn", "bunx", "docker"}
SECRET_KEY_HINTS = ("token", "secret", "password", "auth", "api_key", "apikey")
UNSAFE_CHAIN_PATTERNS = [
    re.compile(r"\bcurl\b.*\|\s*(bash|sh)\b", re.IGNORECASE),
    re.compile(r"\bwget\b.*\|\s*(bash|sh)\b", re.IGNORECASE),
    re.compile(r"\b(bash|sh)\s+-c\b", re.IGNORECASE),
    re.compile(r"&&"),
    re.compile(r";"),
    re.compile(r"\$\("),
    re.compile(r"`"),
]


def _tool_record(tool: ToolConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool, ToolConfig):
        return tool.model_dump()
    return dict(tool)


def _is_local_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in {"localhost", "127.0.0.1", "::1"}


def _is_private_ip(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _collect_secret_keys(payload: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    for key in payload:
        normalized = str(key).strip().lower()
        if any(hint in normalized for hint in SECRET_KEY_HINTS):
            hits.append(str(key))
    return hits


def _scan_command(command_text: str) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    if not command_text:
        return findings
    for pattern in UNSAFE_CHAIN_PATTERNS:
        match = pattern.search(command_text)
        if match:
            findings.append(
                GuardrailFinding(
                    category="supply_chain",
                    severity="critical",
                    action="block",
                    title="Unsafe MCP launch chain",
                    detail="The MCP stdio launcher contains shell chaining or pipe-to-shell execution.",
                    evidence=[match.group(0)],
                )
            )
            return findings
    try:
        parts = shlex.split(command_text)
    except ValueError as exc:
        findings.append(
            GuardrailFinding(
                category="supply_chain",
                severity="high",
                action="block",
                title="Invalid MCP launch command",
                detail="The MCP stdio launcher could not be parsed safely.",
                evidence=[str(exc)],
            )
        )
        return findings
    if not parts:
        return findings
    binary = Path(parts[0]).name.lower()
    if binary in LAUNCHER_BINARIES:
        findings.append(
            GuardrailFinding(
                category="supply_chain",
                severity="high",
                action="warn",
                title="Code-launcher binary detected",
                detail="The MCP connector starts through a generic launcher binary and should remain wrapped until explicitly trusted.",
                evidence=[binary],
            )
        )
    if binary in {"npx", "pnpm", "yarn", "bunx", "uvx"}:
        package_tokens = [token for token in parts[1:] if token and not token.startswith("-")]
        pinned = any("@" in token and not token.startswith("@") for token in package_tokens)
        if not pinned:
            findings.append(
                GuardrailFinding(
                    category="supply_chain",
                    severity="high",
                    action="warn",
                    title="Unpinned package runner",
                    detail="The MCP connector is launched through a package runner without an explicit version pin.",
                    evidence=package_tokens[:3] or [binary],
                )
            )
    return findings


def _scan_url(url: str) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    if not url:
        return findings
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    scheme = parsed.scheme.lower()
    if scheme == "http" and not _is_local_host(host):
        findings.append(
            GuardrailFinding(
                category="unsafe_transport",
                severity="critical",
                action="block",
                title="Non-TLS remote MCP transport",
                detail="Remote MCP servers must use HTTPS unless they are explicitly local.",
                evidence=[url],
            )
        )
    elif scheme == "http" and _is_local_host(host):
        findings.append(
            GuardrailFinding(
                category="unsafe_transport",
                severity="medium",
                action="warn",
                title="Local plaintext MCP transport",
                detail="Local HTTP MCP transport is allowed, but it remains wrapped and audited.",
                evidence=[url],
            )
        )
    if host and (_is_private_ip(host) or host.endswith(".local")) and not _is_local_host(host):
        findings.append(
            GuardrailFinding(
                category="tool_poisoning",
                severity="high",
                action="warn",
                title="Private or shadow MCP endpoint",
                detail="The connector points at a private or shadow-network endpoint and should not be trusted as a first-class native server.",
                evidence=[host],
            )
        )
    return findings


def _scan_inline_text(tool_name: str, config: dict[str, Any]) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    candidate_text = "\n".join(
        part
        for part in [
            tool_name,
            str(config.get("description", "") or ""),
            str(config.get("body_template", "") or ""),
        ]
        if str(part).strip()
    )
    injection_hits = prompt_injection_signals(candidate_text)
    if injection_hits:
        findings.append(
            GuardrailFinding(
                category="tool_poisoning",
                severity="high",
                action="block",
                title="Poisoned local tool metadata",
                detail="Configured tool metadata contains prompt-injection patterns and cannot be enabled.",
                evidence=injection_hits,
            )
        )
    return findings


def scan_tool_config(tool: ToolConfig | dict[str, Any]) -> GuardrailScanReport:
    data = _tool_record(tool)
    tool_id = str(data.get("id", "")).strip()
    tool_name = str(data.get("name", tool_id) or tool_id)
    tool_type = str(data.get("tool_type", "")).strip()
    config = data.get("config") or {}
    findings: list[GuardrailFinding] = []

    findings.extend(_scan_inline_text(tool_name, config))

    if tool_type == "mcp_server":
        transport = mcp_server_transport(config)
        if transport == "http":
            findings.extend(_scan_url(str(config.get("url", "") or "").strip()))
            raw_headers = config.get("headers", {})
            try:
                headers = raw_headers if isinstance(raw_headers, dict) else json.loads(str(raw_headers or "{}"))
            except json.JSONDecodeError:
                headers = {}
            if isinstance(headers, dict):
                secret_header_keys = _collect_secret_keys(headers)
                if secret_header_keys:
                    findings.append(
                        GuardrailFinding(
                            category="secret_exposure",
                            severity="medium",
                            action="warn",
                            title="Inline MCP auth headers",
                            detail="Connector stores inline auth headers and should be treated as guarded until credentials are externalized.",
                            evidence=secret_header_keys[:5],
                        )
                    )
        else:
            command_text = " ".join(
                part for part in [str(config.get("command", "") or "").strip(), str(config.get("args", "") or "").strip()] if part
            )
            findings.extend(_scan_command(command_text))
            raw_env = config.get("env", {})
            try:
                env_vars = raw_env if isinstance(raw_env, dict) else json.loads(str(raw_env or "{}"))
            except json.JSONDecodeError:
                env_vars = {}
            if isinstance(env_vars, dict):
                secret_env_keys = _collect_secret_keys(env_vars)
                if secret_env_keys:
                    findings.append(
                        GuardrailFinding(
                            category="secret_exposure",
                            severity="medium",
                            action="warn",
                            title="Inline MCP environment secrets",
                            detail="Connector stores inline environment secrets and should remain wrapped and audited.",
                            evidence=secret_env_keys[:5],
                        )
                    )
    elif tool_type in {"shell", "ssh", "code_exec"}:
        findings.append(
            GuardrailFinding(
                category="unsafe_capability",
                severity="high",
                action="warn",
                title="Exec-capable tool",
                detail="This tool can execute commands or code and should remain in a guarded posture.",
                evidence=[tool_type],
            )
        )
        if tool_type == "shell":
            command_template = str(config.get("command_template", "") or "").strip()
            findings.extend(_scan_command(command_template))
    elif tool_type in {"http_api", "custom_api"}:
        findings.extend(_scan_url(str(config.get("base_url", "") or "").strip()))
        headers_keys = _collect_secret_keys(config)
        if headers_keys:
            findings.append(
                GuardrailFinding(
                    category="secret_exposure",
                    severity="low",
                    action="log",
                    title="Inline connector secrets",
                    detail="The connector stores inline auth material and should be covered by audit logs.",
                    evidence=headers_keys[:5],
                )
            )

    return compile_scan_report(
        tool_id,
        tool_name,
        tool_type,
        findings,
        phase="config",
        scanned_target=tool_id,
    )
