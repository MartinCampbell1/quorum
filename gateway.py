"""
Multi-Agent Gateway v3 - FastAPI + Profile Rotation + Orchestrator
=================================================================

Единая точка входа для мультиагентной системы.
Все три CLI (Claude, Gemini, Codex) доступны как HTTP-эндпоинты
с автоматической ротацией аккаунтов при rate limit.

Запуск:
    pip install fastapi uvicorn httpx
    python gateway.py

Эндпоинты:
    POST /claude     - вызвать Claude Code
    POST /gemini     - вызвать Gemini (с ротацией аккаунтов)
    POST /codex      - вызвать Codex/ChatGPT (с ротацией аккаунтов)
    POST /ask        - универсальный (agent в теле)
    POST /ask-all    - параллельный вызов нескольких агентов
    POST /orchestrate - полный воркфлоу: plan -> implement -> review -> refine
    POST /consensus  - спросить всех, синтезировать лучший ответ
    GET  /pool       - статус всех аккаунтов
    POST /pool/reset - сбросить кулдауны
    GET  /health     - проверка CLI
"""

import asyncio
import json
import os
import shlex
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.models import capability_for_tool
from orchestrator.tool_configs import ToolConfig, normalize_tool_id, tool_config_store


# =========================================================================
#  CONFIG - поправь под себя если нужно
# =========================================================================

# Где лежат профили аккаунтов
PROFILES_DIR = Path.home() / ".cli-profiles"

# Пути к бинарникам (поправь если у тебя другие)
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
GEMINI_BIN = os.getenv("GEMINI_BIN", "gemini")
CODEX_BIN = os.getenv("CODEX_BIN", "codex")

# Реальный HOME (нужен для PATH)
REAL_HOME = str(Path.home())

# Таймауты
DEFAULT_TIMEOUT = 300  # 5 минут на один вызов
COOLDOWN_SECONDS = 300  # 5 минут кулдаун после rate limit

# Рабочая директория по умолчанию
DEFAULT_WORKDIR = REAL_HOME
DEFAULT_GATEWAY_HOST = os.getenv("GATEWAY_HOST", "127.0.0.1")


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


DEFAULT_CORS_ORIGINS = _parse_csv_env(
    "GATEWAY_CORS_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3737",
        "http://127.0.0.1:3737",
        "http://localhost:3740",
        "http://127.0.0.1:3740",
        "http://localhost:3741",
        "http://127.0.0.1:3741",
        "http://localhost:8800",
        "http://127.0.0.1:8800",
    ],
)

# Роли агентов для оркестрации
PLANNER = "gemini"      # большое контекстное окно, хорош для анализа
IMPLEMENTER = "claude"   # лучше всех кодит
REVIEWER = "codex"       # свежий взгляд, ловит edge cases


# =========================================================================
#  PROFILE DISCOVERY & ROTATION
# =========================================================================

@dataclass
class Profile:
    """Один аккаунт/профиль для CLI."""
    name: str           # "acc1", "acc2"
    provider: str       # "gemini", "codex", "claude"
    path: str           # полный путь к директории профиля

    is_available: bool = True
    requests_made: int = 0
    last_used: float = 0
    cooldown_until: float = 0
    consecutive_errors: int = 0


@dataclass
class ProfilePool:
    """Пул аккаунтов одного провайдера с round-robin ротацией."""
    provider: str
    profiles: list[Profile] = field(default_factory=list)
    _index: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get_next(self) -> Optional[Profile]:
        """Получить следующий доступный профиль."""
        async with self._lock:
            if not self.profiles:
                return None

            now = time.time()

            for i in range(len(self.profiles)):
                idx = (self._index + i) % len(self.profiles)
                p = self.profiles[idx]

                # Проверить кулдаун
                if not p.is_available and now >= p.cooldown_until:
                    p.is_available = True
                    p.consecutive_errors = 0

                if p.is_available:
                    self._index = (idx + 1) % len(self.profiles)
                    p.last_used = now
                    p.requests_made += 1
                    return p

            return None  # все на кулдауне

    async def mark_rate_limited(self, profile: Profile):
        """Пометить профиль как rate-limited."""
        async with self._lock:
            profile.is_available = False
            profile.consecutive_errors += 1
            # Экспоненциальный бэкофф: 5 мин, 10 мин, 15 мин... макс 30 мин
            cd = COOLDOWN_SECONDS + min(profile.consecutive_errors * 60, 1800)
            profile.cooldown_until = time.time() + cd

    async def mark_success(self, profile: Profile):
        """Сбросить счетчик ошибок при успехе."""
        profile.consecutive_errors = 0

    def status(self) -> list[dict]:
        now = time.time()
        return [
            {
                "name": p.name,
                "available": p.is_available or now >= p.cooldown_until,
                "requests_made": p.requests_made,
                "cooldown_remaining_sec": max(0, round(p.cooldown_until - now))
                if not p.is_available and now < p.cooldown_until else 0,
            }
            for p in self.profiles
        ]


# ---- Глобальные пулы ----
pools: dict[str, ProfilePool] = {}


def discover_profiles():
    """Найти все профили на диске и заполнить пулы."""
    global pools
    pools.clear()

    for provider in ["gemini", "codex", "claude"]:
        provider_dir = PROFILES_DIR / provider
        if not provider_dir.exists():
            continue

        pool = ProfilePool(provider=provider)

        for acc_dir in sorted(provider_dir.iterdir()):
            if not acc_dir.is_dir() or not acc_dir.name.startswith("acc"):
                continue

            # Gemini и Claude: проверить что есть home/
            if provider in ("gemini", "claude"):
                home_dir = acc_dir / "home"
                if not home_dir.exists():
                    continue
            # Codex: проверить что есть auth.json или config.toml
            elif provider == "codex":
                if not (acc_dir / "config.toml").exists():
                    continue

            pool.profiles.append(Profile(
                name=acc_dir.name,
                provider=provider,
                path=str(acc_dir),
            ))

        if pool.profiles:
            pools[provider] = pool


def build_env(profile: Profile) -> dict:
    """Собрать environment variables для запуска CLI с конкретным профилем."""
    env = os.environ.copy()

    if profile.provider == "gemini":
        env["HOME"] = os.path.join(profile.path, "home")
        # Обязательно сохранить рабочий PATH
        env["PATH"] = ":".join([
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            f"{REAL_HOME}/.npm-global/bin",
            f"{REAL_HOME}/.local/bin",
            f"{REAL_HOME}/.cargo/bin",
            f"{REAL_HOME}/.bun/bin",
            env.get("PATH", ""),
        ])
        # NVM
        nvm = f"{REAL_HOME}/.nvm"
        if os.path.exists(nvm):
            env["NVM_DIR"] = nvm

    elif profile.provider == "codex":
        env["CODEX_HOME"] = profile.path

    elif profile.provider == "claude":
        env["HOME"] = os.path.join(profile.path, "home")
        env["PATH"] = ":".join([
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            f"{REAL_HOME}/.npm-global/bin",
            f"{REAL_HOME}/.local/bin",
            env.get("PATH", ""),
        ])

    return env


def default_env() -> dict:
    """Environment по умолчанию (без подмены HOME)."""
    return os.environ.copy()


def _strip_mcp_sections_from_toml(raw_toml: str) -> str:
    """Remove persisted MCP sections so a temp CODEX_HOME starts with a clean server registry."""
    output: list[str] = []
    skipping = False
    for line in raw_toml.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skipping = stripped.startswith("[mcp_servers.")
            if not skipping:
                output.append(line)
            continue
        if skipping:
            continue
        output.append(line)
    rendered = "\n".join(output).strip()
    return f"{rendered}\n" if rendered else 'cli_auth_credentials_store = "file"\n'


def prepare_isolated_codex_home(env: dict) -> tuple[dict, str | None]:
    """Create a per-run CODEX_HOME so native MCP servers don't leak between sessions."""
    source_home = Path(env.get("CODEX_HOME") or (Path(REAL_HOME) / ".codex"))
    if not source_home.exists():
        return env, None

    temp_home = Path(tempfile.mkdtemp(prefix="codex_home_"))

    for item in source_home.iterdir():
        if item.name == "config.toml":
            continue
        if item.is_file():
            shutil.copy2(item, temp_home / item.name)

    config_path = source_home / "config.toml"
    if config_path.exists():
        sanitized = _strip_mcp_sections_from_toml(config_path.read_text(encoding="utf-8"))
    else:
        sanitized = 'cli_auth_credentials_store = "file"\n'
    (temp_home / "config.toml").write_text(sanitized, encoding="utf-8")

    isolated_env = env.copy()
    isolated_env["CODEX_HOME"] = str(temp_home)
    return isolated_env, str(temp_home)


# ---- Rate limit detection ----

RATE_LIMIT_PATTERNS = [
    "resource has been exhausted",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "quota exceeded",
    "quota_exceeded",
    "429",
    "too many requests",
    "insufficient_quota",
    "capacity",
    "overloaded",
    "try again later",
]


def is_rate_limited(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in RATE_LIMIT_PATTERNS)


# =========================================================================
#  CLI RUNNERS
# =========================================================================

async def run_cli(
    cmd: list[str],
    workdir: str = None,
    timeout: int = DEFAULT_TIMEOUT,
    env: dict = None,
) -> tuple[str, str, int]:
    """Запустить CLI команду, вернуть (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir or DEFAULT_WORKDIR,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(408, f"Timeout after {timeout}s")

    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        proc.returncode,
    )


# =========================================================================
#  MCP SERVER CONFIG
# =========================================================================

# Tool key → MCP server mapping
MCP_SERVER_MAP = {
    "web_search": "search-server",
    "perplexity": "search-server",
    "code_exec": "exec-server",
    "shell_exec": "exec-server",
    "http_request": "exec-server",
}

MCP_SERVER_DEFINITIONS = {
    "search-server": {
        "command": "python3",
        "args": [str(Path(__file__).parent / "mcp_servers" / "search_server.py")],
    },
    "exec-server": {
        "command": "python3",
        "args": [str(Path(__file__).parent / "mcp_servers" / "exec_server.py")],
    },
}

REGISTERED_MCP_SERVERS = {
    "search-server": {
        "command": "python3",
        "args": [str(Path(__file__).parent / "mcp_servers" / "search_server.py")],
    },
    "exec-server": {
        "command": "python3",
        "args": [str(Path(__file__).parent / "mcp_servers" / "exec_server.py")],
    },
    "configured-tools": {
        "command": "python3",
        "args": [str(Path(__file__).parent / "mcp_servers" / "configured_tools_server.py")],
    },
}

BOOTSTRAPPED_MCP_SERVERS: set[tuple[str, str, str]] = set()


def _write_temp_json(payload: dict, prefix: str) -> str:
    """Write a JSON payload to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix=prefix)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle)
    except Exception:
        os.unlink(path)
        raise
    return path


def _runtime_event_stream_path(session_id: str | None) -> str | None:
    if not session_id:
        return None
    runtime_dir = Path(REAL_HOME) / ".multi-agent" / "runtime_events"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return str(runtime_dir / f"{session_id}.jsonl")


def _bridge_tool_definition(tool_id: str) -> dict | None:
    canonical = normalize_tool_id(tool_id)
    configured = tool_config_store.get(canonical)
    if configured and configured.enabled:
        return configured.model_dump()

    builtin_bridge_tools = {
        "perplexity": {"name": "Perplexity AI", "tool_type": "perplexity", "icon": "🧠", "config": {}},
        "code_exec": {"name": "Python", "tool_type": "code_exec", "icon": "🐍", "config": {}},
        "shell_exec": {"name": "Shell", "tool_type": "shell", "icon": "⚡", "config": {}},
        "http_request": {"name": "HTTP Request", "tool_type": "http_request", "icon": "🔗", "config": {}},
    }
    definition = builtin_bridge_tools.get(canonical)
    if not definition:
        return None
    return {
        "id": canonical,
        "enabled": True,
        **definition,
    }


def build_bridge_payload(provider: str, tool_keys: list[str]) -> str | None:
    """Create payload for the stable configured-tools bridge server."""
    payload_tools: list[dict] = []
    seen: set[str] = set()
    for raw_key in tool_keys:
        tool_id = normalize_tool_id(raw_key)
        if capability_for_tool(provider, tool_id) != "bridged":
            continue
        if tool_id in seen:
            continue
        definition = _bridge_tool_definition(tool_id)
        if not definition:
            continue
        payload_tools.append(definition)
        seen.add(tool_id)
    if not payload_tools:
        return None
    return _write_temp_json({"tools": payload_tools}, "configured_tools_")


def _registered_server_definition(provider: str, server_name: str) -> dict | None:
    definition = REGISTERED_MCP_SERVERS.get(server_name)
    if definition:
        return definition

    configured = tool_config_store.get(server_name)
    if not configured or not configured.enabled or configured.tool_type != "mcp_server":
        return None
    if capability_for_tool(provider, server_name) != "native":
        return None

    transport = str(configured.config.get("transport", "stdio") or "stdio").strip().lower()
    if transport == "http":
        url = str(configured.config.get("url", "") or "").strip()
        if not url:
            return None
        headers: dict[str, str] = {}
        raw_headers = str(configured.config.get("headers", "") or "").strip()
        if raw_headers:
            try:
                parsed_headers = json.loads(raw_headers)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed_headers, dict):
                return None
            headers = {str(key): str(value) for key, value in parsed_headers.items()}
        return {
            "transport": "http",
            "url": url,
            "headers": headers,
        }

    command = str(configured.config.get("command", "") or "").strip()
    if not command:
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    extra_args = shlex.split(str(configured.config.get("args", "") or "").strip()) if str(configured.config.get("args", "") or "").strip() else []
    env_vars: dict[str, str] = {}
    raw_env = str(configured.config.get("env", "") or "").strip()
    if raw_env:
        try:
            parsed_env = json.loads(raw_env)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed_env, dict):
            return None
        env_vars = {str(key): str(value) for key, value in parsed_env.items()}
    return {
        "transport": "stdio",
        "command": parts[0],
        "args": [*parts[1:], *extra_args],
        "env": env_vars,
    }


def _bootstrap_cache_key(provider: str, env: dict, server_name: str, definition: dict) -> tuple[str, str, str]:
    profile_root = env.get("CODEX_HOME") or env.get("HOME") or REAL_HOME
    fingerprint = json.dumps(definition, sort_keys=True, ensure_ascii=True)
    return provider, profile_root, f"{server_name}:{fingerprint}"


async def ensure_registered_mcp_servers(
    provider: str,
    env: dict,
    server_names: list[str],
) -> None:
    """Ensure stable MCP servers are registered for Gemini/Codex profiles."""
    if provider not in {"gemini", "codex"}:
        return

    for server_name in server_names:
        definition = _registered_server_definition(provider, server_name)
        if not definition:
            continue
        cache_key = _bootstrap_cache_key(provider, env, server_name, definition)
        if cache_key in BOOTSTRAPPED_MCP_SERVERS:
            continue

        if provider == "gemini":
            transport = definition.get("transport", "stdio")
            if server_name not in REGISTERED_MCP_SERVERS:
                await run_cli(
                    [GEMINI_BIN, "mcp", "remove", "--scope", "user", server_name],
                    DEFAULT_WORKDIR,
                    20,
                    env,
                )
            cmd = [GEMINI_BIN, "mcp", "add", "--scope", "user", "--transport", transport]
            if transport == "http":
                cmd.extend([server_name, definition["url"]])
                for key, value in definition.get("headers", {}).items():
                    cmd.extend(["--header", f"{key}: {value}"])
            else:
                cmd.extend([server_name, definition["command"], *definition.get("args", [])])
                for key, value in definition.get("env", {}).items():
                    cmd.extend(["--env", f"{key}={value}"])
        else:
            if definition.get("transport") == "http":
                cmd = [
                    CODEX_BIN,
                    "mcp",
                    "add",
                    server_name,
                    "--url",
                    definition["url"],
                ]
            else:
                cmd = [CODEX_BIN, "mcp", "add"]
                for key, value in definition.get("env", {}).items():
                    cmd.extend(["--env", f"{key}={value}"])
                cmd.extend([server_name, "--", definition["command"], *definition.get("args", [])])

        stdout, stderr, rc = await run_cli(cmd, DEFAULT_WORKDIR, 20, env)
        combined = f"{stdout}\n{stderr}".lower()
        if rc == 0 or "already" in combined or "exists" in combined:
            BOOTSTRAPPED_MCP_SERVERS.add(cache_key)
            continue
        raise HTTPException(
            500,
            f"Failed to register MCP server '{server_name}' for {provider}: {(stderr or stdout).strip()[:300]}",
        )


def build_mcp_config(tool_keys: list[str]) -> str | None:
    """Generate a temporary MCP config JSON file for the given tool keys.
    Returns the file path, or None if no tools need MCP servers.

    Handles both built-in MCP servers and custom MCP servers from tool_configs.
    """
    if not tool_keys:
        return None

    config = {"mcpServers": {}}

    # 1. Resolve built-in MCP servers
    for server_name in resolve_mcp_servers(tool_keys):
        defn = MCP_SERVER_DEFINITIONS.get(server_name)
        if defn:
            config["mcpServers"][server_name] = defn

    configured_runtime_tools: list[dict] = []

    # 2. Resolve configured tools from tool_configs
    try:
        from orchestrator.tool_configs import normalize_tool_id, tool_config_store
        for tool_id in tool_keys:
            tc = tool_config_store.get(normalize_tool_id(tool_id))
            if not tc or not tc.enabled:
                continue
            if tc.tool_type == "mcp_server":
                transport = tc.config.get("transport", "").strip().lower() or "stdio"
                if transport == "http":
                    url = tc.config.get("url", "").strip()
                    if not url:
                        continue
                    headers_str = tc.config.get("headers", "").strip()
                    headers = {}
                    if headers_str:
                        try:
                            headers = json.loads(headers_str)
                        except json.JSONDecodeError:
                            pass
                    server_def = {"type": "http", "url": url}
                    if headers:
                        server_def["headers"] = headers
                else:
                    command = tc.config.get("command", "").strip()
                    if not command:
                        continue
                    parts = shlex.split(command)
                    env_str = tc.config.get("env", "")
                    env_vars = {}
                    if env_str:
                        try:
                            env_vars = json.loads(env_str)
                        except json.JSONDecodeError:
                            pass
                    args_str = tc.config.get("args", "").strip()
                    extra_args = shlex.split(args_str) if args_str else []
                    server_def = {"command": parts[0], "args": parts[1:] + extra_args}
                    if env_vars:
                        server_def["env"] = env_vars
                config["mcpServers"][tc.id] = server_def
            elif tc.tool_type not in {"code_exec", "shell"}:
                configured_runtime_tools.append(tc.model_dump())
    except ImportError:
        pass

    if configured_runtime_tools:
        payload_path = _write_temp_json({"tools": configured_runtime_tools}, "configured_tools_")
        config["mcpServers"]["configured-tools"] = {
            "command": "python3",
            "args": [str(Path(__file__).parent / "mcp_servers" / "configured_tools_server.py"), payload_path],
        }

    if not config["mcpServers"]:
        return None

    return _write_temp_json(config, "mcp_")


def resolve_mcp_servers(tool_keys: list[str] | None) -> list[str]:
    """Map tool keys to the MCP servers needed for this run."""
    needed_servers = {
        server_name
        for key in (tool_keys or [])
        if (server_name := MCP_SERVER_MAP.get(key))
    }
    try:
        from orchestrator.tool_configs import normalize_tool_id, tool_config_store

        for raw_key in tool_keys or []:
            tool_id = normalize_tool_id(raw_key)
            configured_tool = tool_config_store.get(tool_id)
            if not configured_tool or not configured_tool.enabled:
                continue
            if configured_tool.tool_type == "mcp_server":
                needed_servers.add(configured_tool.id)
            elif configured_tool.tool_type not in {"code_exec", "shell"}:
                needed_servers.add("configured-tools")
    except ImportError:
        pass
    return sorted(needed_servers)


def build_cmd(
    provider: str,
    prompt: str,
    model: str = None,
    mcp_config_path: str = None,
    allowed_mcp_servers: list[str] | None = None,
    selected_tools: list[str] | None = None,
    workspace_paths: list[str] | None = None,
) -> list[str]:
    """Собрать команду для CLI."""
    workspace_paths = [path for path in (workspace_paths or []) if path]
    if provider == "claude":
        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
        if model:
            cmd.extend(["--model", model])
        if workspace_paths:
            cmd.extend(["--add-dir", *workspace_paths])
        if mcp_config_path:
            cmd.extend(["--mcp-config", mcp_config_path, "--strict-mcp-config", "--tools", ""])
        return cmd

    elif provider == "gemini":
        cmd = [GEMINI_BIN, "-p", prompt]
        if model:
            cmd.extend(["--model", model])
        if allowed_mcp_servers:
            cmd.extend(["--allowed-mcp-server-names", *allowed_mcp_servers])
        for workspace_path in workspace_paths:
            cmd.extend(["--include-directories", workspace_path])
        return cmd

    elif provider == "codex":
        cmd = [CODEX_BIN, "exec", "--skip-git-repo-check", prompt]
        if model:
            cmd.extend(["--model", model])
        if selected_tools and "web_search" in selected_tools:
            cmd.append("--search")
        for workspace_path in workspace_paths:
            cmd.extend(["--add-dir", workspace_path])
        return cmd

    raise ValueError(f"Unknown provider: {provider}")


def parse_output(provider: str, stdout: str) -> str:
    """Извлечь чистый текст из CLI output."""
    if provider == "claude":
        try:
            data = json.loads(stdout)
            return data.get("result", stdout)
        except json.JSONDecodeError:
            return stdout.strip()

    # codex exec: clean response goes to stdout, metadata to stderr
    # gemini: plain text to stdout

    return stdout.strip()


# =========================================================================
#  CORE: CALL WITH ROTATION
# =========================================================================

async def call_agent(
    provider: str,
    prompt: str,
    workdir: str = None,
    model: str = None,
    system_prompt: str = None,
    timeout: int = DEFAULT_TIMEOUT,
    mcp_tools: list[str] = None,
    workspace_paths: list[str] | None = None,
    session_id: str | None = None,
    agent_role: str | None = None,
) -> dict:
    """
    Вызвать агента с автоматической ротацией аккаунтов.

    1. Взять следующий профиль из пула
    2. Запустить CLI с его env
    3. Если rate limit - пометить, взять следующий, повторить
    4. Если все исчерпаны - вернуть ошибку
    """
    if system_prompt:
        prompt = f"[System]: {system_prompt}\n\n{prompt}"

    selected_tools = [normalize_tool_id(tool) for tool in (mcp_tools or []) if str(tool).strip()]
    native_tools = [tool for tool in selected_tools if capability_for_tool(provider, tool) == "native"]
    bridged_tools = [tool for tool in selected_tools if capability_for_tool(provider, tool) == "bridged"]
    codex_native_external_servers = [
        tool
        for tool in native_tools
        if (configured := tool_config_store.get(tool))
        and configured.enabled
        and configured.tool_type == "mcp_server"
    ]
    allowed_mcp_servers = resolve_mcp_servers(native_tools)
    bridge_payload_path = build_bridge_payload(provider, bridged_tools) if bridged_tools else None
    mcp_config_path = build_mcp_config(native_tools) if provider == "claude" and native_tools else None
    runtime_event_stream_path = _runtime_event_stream_path(session_id)
    temp_codex_home: str | None = None
    try:
        cmd = build_cmd(
            provider,
            prompt,
            model,
            mcp_config_path,
            allowed_mcp_servers=allowed_mcp_servers,
            selected_tools=selected_tools,
            workspace_paths=workspace_paths,
        )
        pool = pools.get(provider)
        t0 = time.time()
        retries = 0

        # Если нет профилей - вызов с дефолтным env
        if not pool or not pool.profiles:
            try:
                env = default_env()
                if provider == "codex" and codex_native_external_servers:
                    env, temp_codex_home = prepare_isolated_codex_home(env)
                if bridge_payload_path:
                    env["CONFIGURED_TOOLS_PAYLOAD"] = bridge_payload_path
                if runtime_event_stream_path:
                    env["CONFIGURED_TOOLS_EVENT_STREAM"] = runtime_event_stream_path
                if agent_role:
                    env["CONFIGURED_TOOLS_AGENT_ROLE"] = agent_role
                bootstrap_servers = list(dict.fromkeys(allowed_mcp_servers + (["configured-tools"] if bridge_payload_path and provider in {"gemini", "codex"} else [])))
                await ensure_registered_mcp_servers(provider, env, bootstrap_servers)
                stdout, stderr, rc = await run_cli(cmd, workdir, timeout, env)
                output = parse_output(provider, stdout)
                return {
                    "agent": provider,
                    "profile_used": "default",
                    "output": output,
                    "elapsed_sec": round(time.time() - t0, 2),
                    "success": rc == 0,
                    "error": stderr.strip() if rc != 0 else None,
                    "retries": 0,
                }
            except Exception as e:
                return {
                    "agent": provider,
                    "profile_used": "default",
                    "output": "",
                    "elapsed_sec": round(time.time() - t0, 2),
                    "success": False,
                    "error": str(e),
                    "retries": 0,
                }

        # С ротацией
        max_attempts = len(pool.profiles)

        for attempt in range(max_attempts):
            profile = await pool.get_next()

            if profile is None:
                statuses = pool.status()
                soonest = min((s["cooldown_remaining_sec"] for s in statuses), default=0)
                return {
                    "agent": provider,
                    "profile_used": None,
                    "output": "",
                    "elapsed_sec": round(time.time() - t0, 2),
                    "success": False,
                    "error": f"All {len(pool.profiles)} accounts rate-limited. "
                             f"Soonest recovery: {soonest}s",
                    "retries": retries,
                    "pool_status": statuses,
                }

            env = build_env(profile)
            if temp_codex_home:
                shutil.rmtree(temp_codex_home, ignore_errors=True)
                temp_codex_home = None
            if provider == "codex" and codex_native_external_servers:
                env, temp_codex_home = prepare_isolated_codex_home(env)
            if bridge_payload_path:
                env["CONFIGURED_TOOLS_PAYLOAD"] = bridge_payload_path
            if runtime_event_stream_path:
                env["CONFIGURED_TOOLS_EVENT_STREAM"] = runtime_event_stream_path
            if agent_role:
                env["CONFIGURED_TOOLS_AGENT_ROLE"] = agent_role
            bootstrap_servers = list(
                dict.fromkeys(
                    allowed_mcp_servers
                    + (["configured-tools"] if bridge_payload_path and provider in {"gemini", "codex"} else [])
                )
            )
            await ensure_registered_mcp_servers(provider, env, bootstrap_servers)

            try:
                stdout, stderr, rc = await run_cli(cmd, workdir, timeout, env)
            except Exception as e:
                await pool.mark_rate_limited(profile)
                retries += 1
                print(f"[ROTATE] {provider}/{profile.name} error: {e}")
                continue

            combined = stdout + " " + stderr

            if is_rate_limited(combined):
                await pool.mark_rate_limited(profile)
                retries += 1
                print(f"[ROTATE] {provider}/{profile.name} rate-limited, switching...")
                continue

            # Успех
            await pool.mark_success(profile)
            output = parse_output(provider, stdout)

            # Debug: log if output is empty
            if not output and stdout.strip() == "" and stderr.strip():
                print(f"[DEBUG] {provider}/{profile.name} stdout empty, stderr: {stderr[:300]}")

            return {
                "agent": provider,
                "profile_used": profile.name,
                "output": output,
                "elapsed_sec": round(time.time() - t0, 2),
                "success": rc == 0 and bool(output),
                "error": stderr.strip()[:500] if rc != 0 or not output else None,
                "retries": retries,
            }

        return {
            "agent": provider,
            "profile_used": None,
            "output": "",
            "elapsed_sec": round(time.time() - t0, 2),
            "success": False,
            "error": f"Exhausted all {max_attempts} profiles",
            "retries": retries,
        }
    finally:
        # Clean up temp MCP config
        if mcp_config_path:
            try:
                os.unlink(mcp_config_path)
            except OSError:
                pass
        if temp_codex_home:
            shutil.rmtree(temp_codex_home, ignore_errors=True)
        if bridge_payload_path:
            try:
                os.unlink(bridge_payload_path)
            except OSError:
                pass


# =========================================================================
#  FASTAPI APP
# =========================================================================

app = FastAPI(
    title="Multi-Agent Gateway",
    description="Claude + Gemini + Codex с ротацией аккаунтов",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    discover_profiles()
    print(f"\nProfiles directory: {PROFILES_DIR}")
    for provider, pool in pools.items():
        names = [p.name for p in pool.profiles]
        print(f"  {provider}: {names}")
    if not pools:
        print("  No profiles found - using default accounts")
    print()


# ---- Request/Response models ----

class AgentRequest(BaseModel):
    prompt: str
    agent: Optional[str] = None
    workdir: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    timeout: Optional[int] = DEFAULT_TIMEOUT
    mcp_tools: Optional[list[str]] = None
    workspace_paths: Optional[list[str]] = None
    session_id: Optional[str] = None
    agent_role: Optional[str] = None


class MultiRequest(BaseModel):
    prompt: str
    agents: list[str] = ["claude", "gemini", "codex"]
    workdir: Optional[str] = None
    system_prompt: Optional[str] = None
    timeout: Optional[int] = DEFAULT_TIMEOUT


class OrchestrateRequest(BaseModel):
    task: str
    workdir: Optional[str] = None
    context: Optional[str] = None
    max_refinements: int = 1


class ConsensusRequest(BaseModel):
    question: str
    workdir: Optional[str] = None


# ---- Endpoints: Individual agents ----

@app.post("/claude")
async def ep_claude(req: AgentRequest):
    return await call_agent("claude", req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools, workspace_paths=req.workspace_paths,
                            session_id=req.session_id, agent_role=req.agent_role)

@app.post("/gemini")
async def ep_gemini(req: AgentRequest):
    return await call_agent("gemini", req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools, workspace_paths=req.workspace_paths,
                            session_id=req.session_id, agent_role=req.agent_role)

@app.post("/codex")
async def ep_codex(req: AgentRequest):
    return await call_agent("codex", req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools, workspace_paths=req.workspace_paths,
                            session_id=req.session_id, agent_role=req.agent_role)

@app.post("/ask")
async def ep_ask(req: AgentRequest):
    if not req.agent:
        raise HTTPException(400, "Specify 'agent': 'claude' | 'gemini' | 'codex'")
    return await call_agent(req.agent, req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools, workspace_paths=req.workspace_paths,
                            session_id=req.session_id, agent_role=req.agent_role)


# ---- Endpoint: Fan-out to multiple agents ----

@app.post("/ask-all")
async def ep_ask_all(req: MultiRequest):
    t0 = time.time()
    tasks = [
        call_agent(agent, req.prompt, req.workdir, system_prompt=req.system_prompt,
                   timeout=req.timeout or DEFAULT_TIMEOUT)
        for agent in req.agents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = []
    for r in results:
        if isinstance(r, Exception):
            responses.append({"agent": "?", "success": False, "error": str(r)})
        else:
            responses.append(r)

    return {
        "results": responses,
        "total_elapsed_sec": round(time.time() - t0, 2),
    }


# ---- Endpoint: Full orchestration workflow ----

@app.post("/orchestrate")
async def ep_orchestrate(req: OrchestrateRequest):
    """
    Plan (Gemini) -> Implement (Claude) -> Review (Codex) -> Refine (Claude)
    """
    t0 = time.time()
    log = []

    # 1. PLAN
    plan_result = await call_agent(
        PLANNER,
        f"You are a senior architect. Create a detailed implementation plan.\n\n"
        f"TASK: {req.task}\n\n"
        f"{'CONTEXT: ' + req.context if req.context else ''}\n\n"
        f"Respond with:\n"
        f"1. Analysis\n2. Step-by-step plan\n3. Files to change\n4. Risks\n5. Tests",
        workdir=req.workdir,
    )
    log.append({"phase": "plan", **plan_result})

    if not plan_result["success"]:
        return {"status": "failed_at_plan", "log": log}

    plan = plan_result["output"]

    # 2. IMPLEMENT
    impl_result = await call_agent(
        IMPLEMENTER,
        f"Implement this plan exactly.\n\n"
        f"TASK: {req.task}\n\nPLAN:\n{plan}\n\n"
        f"Create/modify all files. Handle edge cases.",
        workdir=req.workdir,
    )
    log.append({"phase": "implement", **impl_result})

    if not impl_result["success"]:
        return {"status": "failed_at_implement", "log": log}

    implementation = impl_result["output"]

    # 3. REVIEW
    review_result = await call_agent(
        REVIEWER,
        f"Review this implementation against the plan.\n\n"
        f"TASK: {req.task}\n\nPLAN:\n{plan}\n\n"
        f"IMPLEMENTATION:\n{implementation}\n\n"
        f"Check: bugs, edge cases, security, performance.\n"
        f"Rate: APPROVED | MINOR_ISSUES | NEEDS_REWORK",
    )
    log.append({"phase": "review", **review_result})

    review = review_result.get("output", "")

    # 4. REFINE (if needed)
    needs_fix = any(w in review.upper() for w in ["NEEDS_REWORK", "MINOR_ISSUES", "BUG", "FIX"])

    if needs_fix and req.max_refinements > 0:
        refine_result = await call_agent(
            IMPLEMENTER,
            f"Fix all issues from review.\n\n"
            f"REVIEW:\n{review}\n\n"
            f"ORIGINAL CODE:\n{implementation}",
            workdir=req.workdir,
        )
        log.append({"phase": "refine", **refine_result})

    return {
        "status": "completed",
        "total_elapsed_sec": round(time.time() - t0, 2),
        "log": log,
    }


# ---- Endpoint: Consensus ----

@app.post("/consensus")
async def ep_consensus(req: ConsensusRequest):
    """Спросить всех трех, синтезировать лучший ответ."""
    t0 = time.time()

    # Параллельный запрос ко всем
    results = await asyncio.gather(
        call_agent("claude", req.question, req.workdir),
        call_agent("gemini", req.question, req.workdir),
        call_agent("codex", req.question, req.workdir),
    )

    answers = {r["agent"]: r["output"] for r in results if r["success"]}

    # Синтез через Claude
    synthesis = await call_agent(
        "claude",
        f"Three AI agents answered the same question. Synthesize the best answer.\n\n"
        f"QUESTION: {req.question}\n\n"
        + "\n\n".join(f"{k.upper()}'s answer:\n{v}" for k, v in answers.items())
        + "\n\nProvide:\n1. Best synthesized answer\n2. Where they agreed\n3. Disagreements",
    )

    return {
        "individual": answers,
        "synthesis": synthesis["output"],
        "total_elapsed_sec": round(time.time() - t0, 2),
    }


# ---- Pool management ----

@app.get("/pool")
async def ep_pool_status():
    """Статус всех аккаунтов."""
    return {
        provider: pool.status()
        for provider, pool in pools.items()
    }


@app.post("/pool/reset")
async def ep_pool_reset():
    """Сбросить все кулдауны."""
    for pool in pools.values():
        for p in pool.profiles:
            p.is_available = True
            p.cooldown_until = 0
            p.consecutive_errors = 0
    return {"status": "all cooldowns reset"}


@app.post("/pool/reload")
async def ep_pool_reload():
    """Пересканировать профили с диска."""
    discover_profiles()
    return {
        provider: [p.name for p in pool.profiles]
        for provider, pool in pools.items()
    }


# ---- Health ----

@app.get("/health")
async def ep_health():
    checks = {}
    for name, binary in [("claude", CLAUDE_BIN), ("gemini", GEMINI_BIN), ("codex", CODEX_BIN)]:
        proc = await asyncio.create_subprocess_exec(
            "which", binary,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        pool = pools.get(name)
        checks[name] = {
            "binary": binary,
            "installed": proc.returncode == 0,
            "path": stdout.decode().strip() if proc.returncode == 0 else None,
            "profiles": len(pool.profiles) if pool else 0,
            "profiles_available": sum(
                1 for s in pool.status() if s["available"]
            ) if pool else 0,
        }
    return checks


# Mount orchestrator
from orchestrator.api import router as orchestrate_router
app.include_router(orchestrate_router)


# =========================================================================
#  RUN
# =========================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=DEFAULT_GATEWAY_HOST, port=8800)
