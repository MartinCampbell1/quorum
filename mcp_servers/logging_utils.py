"""Helpers for safe MCP tool-call logging."""

from __future__ import annotations

from json import JSONDecodeError, loads
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_MARKERS = (
    "authorization",
    "token",
    "secret",
    "password",
    "cookie",
    "api_key",
    "apikey",
    "bearer",
)

ALWAYS_REDACT_FIELDS = {"body", "code", "command", "headers"}


def _sanitize_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<redacted-url>"

    if not parsed.scheme or not parsed.netloc:
        return "<redacted-url>"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _summarize_scalar(key: str, value) -> object:
    lower_key = key.lower()
    if lower_key in ALWAYS_REDACT_FIELDS or any(marker in lower_key for marker in SENSITIVE_MARKERS):
        return f"<redacted:{type(value).__name__}>"
    if isinstance(value, str):
        if lower_key == "url":
            return _sanitize_url(value)
        lowered = value.lower()
        if any(marker in lowered for marker in SENSITIVE_MARKERS):
            return f"<redacted:{len(value)} chars>"
        compact = " ".join(value.split())
        return compact[:160] + ("..." if len(compact) > 160 else "")
    return value


def sanitize_log_arguments(arguments: dict) -> dict:
    """Redact raw tool arguments before writing to disk."""
    sanitized: dict = {}
    for key, value in (arguments or {}).items():
        if isinstance(value, dict):
            sanitized[key] = {
                nested_key: _summarize_scalar(nested_key, nested_value)
                for nested_key, nested_value in value.items()
            }
        elif isinstance(value, list):
            sanitized[key] = [_summarize_scalar(key, item) for item in value[:10]]
        else:
            sanitized[key] = _summarize_scalar(key, value)

        if key == "headers" and isinstance(value, str):
            try:
                headers = loads(value)
            except JSONDecodeError:
                continue
            sanitized[key] = {
                header: "<redacted>" if any(marker in header.lower() for marker in SENSITIVE_MARKERS) else "<provided>"
                for header in headers
            }
    return sanitized


def sanitize_result_preview(result: str) -> str:
    """Keep a short, scrubbed preview of tool output."""
    if not isinstance(result, str):
        return "<non-string-result>"

    lines = []
    for raw_line in result.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if any(marker in lowered for marker in SENSITIVE_MARKERS):
            lines.append("[redacted line]")
        elif line:
            lines.append(line[:160])
        if sum(len(item) for item in lines) >= 400:
            break

    preview = " | ".join(lines)
    return preview[:400] + ("..." if len(preview) > 400 else "")
