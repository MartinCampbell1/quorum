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
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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


def build_mcp_config(tool_keys: list[str]) -> str | None:
    """Generate a temporary MCP config JSON file for the given tool keys.
    Returns the file path, or None if no tools need MCP servers."""
    if not tool_keys:
        return None

    # Determine which MCP servers are needed
    needed_servers = set()
    for key in tool_keys:
        server_name = MCP_SERVER_MAP.get(key)
        if server_name:
            needed_servers.add(server_name)

    if not needed_servers:
        return None

    # Build MCP config JSON
    config = {"mcpServers": {}}
    for server_name in needed_servers:
        defn = MCP_SERVER_DEFINITIONS.get(server_name)
        if defn:
            config["mcpServers"][server_name] = defn

    # Write with proper error handling
    fd, path = tempfile.mkstemp(suffix=".json", prefix="mcp_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config, f)
    except Exception:
        os.unlink(path)
        raise
    return path


def build_cmd(provider: str, prompt: str, model: str = None, mcp_config_path: str = None) -> list[str]:
    """Собрать команду для CLI."""
    if provider == "claude":
        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
        if model:
            cmd.extend(["--model", model])
        if mcp_config_path:
            cmd.extend(["--mcp-config", mcp_config_path])
        return cmd

    elif provider == "gemini":
        cmd = [GEMINI_BIN, "-p", prompt]
        if model:
            cmd.extend(["--model", model])
        # TODO: Gemini MCP config via --allowed-mcp-server-names or settings
        return cmd

    elif provider == "codex":
        cmd = [CODEX_BIN, "exec", "--skip-git-repo-check", prompt]
        if model:
            cmd.extend(["--model", model])
        # TODO: Codex MCP config via env/settings
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

    mcp_config_path = build_mcp_config(mcp_tools) if mcp_tools else None
    try:
        cmd = build_cmd(provider, prompt, model, mcp_config_path)
        pool = pools.get(provider)
        t0 = time.time()
        retries = 0

        # Если нет профилей - вызов с дефолтным env
        if not pool or not pool.profiles:
            try:
                stdout, stderr, rc = await run_cli(cmd, workdir, timeout)
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
    allow_origins=["*"],
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
                            mcp_tools=req.mcp_tools)

@app.post("/gemini")
async def ep_gemini(req: AgentRequest):
    return await call_agent("gemini", req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools)

@app.post("/codex")
async def ep_codex(req: AgentRequest):
    return await call_agent("codex", req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools)

@app.post("/ask")
async def ep_ask(req: AgentRequest):
    if not req.agent:
        raise HTTPException(400, "Specify 'agent': 'claude' | 'gemini' | 'codex'")
    return await call_agent(req.agent, req.prompt, req.workdir, req.model,
                            req.system_prompt, req.timeout or DEFAULT_TIMEOUT,
                            mcp_tools=req.mcp_tools)


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
    uvicorn.run(app, host="0.0.0.0", port=8800)
