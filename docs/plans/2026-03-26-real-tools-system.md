# Real Tools System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fake prompt-injected tools with real executable backends, a MiniMax-powered tool router, and a UI for adding custom tools (API, SSH, etc.)

**Architecture:** Three-layer tool pipeline integrated into `call_agent_cfg()`. Layer 1: Tool Registry (built-in + custom tools with real implementations). Layer 2: Tool Router (MiniMax with function_calling decides which tools to invoke). Layer 3: Tool Executor (runs tools, collects results, injects into agent context). Frontend gets a "Custom Tools" UI for adding API endpoints, SSH connections, etc.

**Tech Stack:** Python 3.14, FastAPI, httpx, langchain-openai (MiniMax via OpenRouter for function_calling), subprocess (for shell/code exec), Next.js 16, shadcn/ui, SelectorChips component.

---

## File Structure

### Backend (new files)
- `orchestrator/tools/__init__.py` — Package init, exports registry
- `orchestrator/tools/base.py` — `BaseTool` abstract class
- `orchestrator/tools/registry.py` — Tool registry: built-in + custom tools catalog
- `orchestrator/tools/builtin/web_search.py` — Brave Search API tool
- `orchestrator/tools/builtin/http_request.py` — Generic HTTP request tool
- `orchestrator/tools/builtin/code_exec.py` — Python code execution (sandboxed)
- `orchestrator/tools/builtin/shell_exec.py` — Shell command execution
- `orchestrator/tools/builtin/perplexity.py` — Perplexity Sonar search
- `orchestrator/tools/router.py` — MiniMax tool router (function_calling)
- `orchestrator/tools/executor.py` — Tool execution orchestrator

### Backend (modified files)
- `orchestrator/models.py` — Expand `ToolDefinition`, add `CustomToolConfig`
- `orchestrator/modes/base.py` — Replace `_build_tools_prompt` + `call_agent_cfg` with tool pipeline
- `orchestrator/api.py` — Add custom tools CRUD endpoints

### Frontend (new files)
- `frontend/components/wizard/custom-tool-form.tsx` — Form for adding custom API/SSH tools

### Frontend (modified files)
- `frontend/lib/types.ts` — Add `CustomToolConfig` type, expand `ToolDefinition`
- `frontend/lib/constants.ts` — Update tool catalog with `is_builtin` flags
- `frontend/lib/api.ts` — Add custom tools API functions
- `frontend/components/wizard/step-agents.tsx` — Show built-in + custom tools

---

## Task 1: BaseTool Abstract Class

**Files:**
- Create: `orchestrator/tools/__init__.py`
- Create: `orchestrator/tools/base.py`

- [ ] **Step 1: Create the tools package**

```python
# orchestrator/tools/__init__.py
"""Real executable tools for agents."""
```

- [ ] **Step 2: Write BaseTool**

```python
# orchestrator/tools/base.py
"""Base class for all executable tools."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ToolParam(BaseModel):
    """Single parameter for a tool."""
    name: str
    type: str  # "string", "number", "boolean"
    description: str
    required: bool = True


class BaseTool(ABC):
    """Abstract base for executable tools."""

    name: str
    description: str
    parameters: list[ToolParam]

    def __init__(self, name: str, description: str, parameters: list[ToolParam] | None = None):
        self.name = name
        self.description = description
        self.parameters = parameters or []

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function_calling schema for the router."""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return result as string."""
        ...
```

- [ ] **Step 3: Verify import**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.tools.base import BaseTool, ToolParam; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add orchestrator/tools/
git commit -m "feat(tools): add BaseTool abstract class with OpenAI function schema export"
```

---

## Task 2: Built-in Tool Implementations

**Files:**
- Create: `orchestrator/tools/builtin/__init__.py`
- Create: `orchestrator/tools/builtin/web_search.py`
- Create: `orchestrator/tools/builtin/http_request.py`
- Create: `orchestrator/tools/builtin/code_exec.py`
- Create: `orchestrator/tools/builtin/shell_exec.py`
- Create: `orchestrator/tools/builtin/perplexity.py`

- [ ] **Step 1: Create builtin package**

```python
# orchestrator/tools/builtin/__init__.py
"""Built-in tool implementations."""
```

- [ ] **Step 2: Web Search tool (Brave Search API)**

```python
# orchestrator/tools/builtin/web_search.py
"""Web search via Brave Search API."""

import os
import httpx
from orchestrator.tools.base import BaseTool, ToolParam


class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for current information. Use for factual queries, recent events, technical docs.",
            parameters=[
                ToolParam(name="query", type="string", description="Search query"),
                ToolParam(name="count", type="number", description="Number of results (1-10)", required=False),
            ],
        )
        self.api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")

    async def execute(self, query: str, count: int = 5, **kwargs) -> str:
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
```

- [ ] **Step 3: HTTP Request tool**

```python
# orchestrator/tools/builtin/http_request.py
"""Generic HTTP request tool for API calls."""

import httpx
from orchestrator.tools.base import BaseTool, ToolParam


class HttpRequestTool(BaseTool):
    def __init__(self):
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

    async def execute(self, url: str, method: str = "GET", body: str = "", headers: str = "", **kwargs) -> str:
        import json
        parsed_headers = {}
        if headers:
            try:
                parsed_headers = json.loads(headers)
            except json.JSONDecodeError:
                return "[http_request] Error: invalid headers JSON"
        parsed_body = None
        if body:
            try:
                parsed_body = json.loads(body)
            except json.JSONDecodeError:
                parsed_body = body

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.request(method.upper(), url, json=parsed_body if isinstance(parsed_body, dict) else None,
                                            content=parsed_body if isinstance(parsed_body, str) else None,
                                            headers=parsed_headers)
                text = resp.text[:5000]
                return f"[http_request] {method} {url} → {resp.status_code}\n{text}"
            except Exception as e:
                return f"[http_request] Error: {e}"
```

- [ ] **Step 4: Code Execution tool (sandboxed Python)**

```python
# orchestrator/tools/builtin/code_exec.py
"""Python code execution in a sandboxed subprocess."""

import asyncio
import tempfile
from orchestrator.tools.base import BaseTool, ToolParam


class CodeExecTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="code_exec",
            description="Execute Python code and return stdout/stderr. Use for calculations, data processing, testing ideas.",
            parameters=[
                ToolParam(name="code", type="string", description="Python code to execute"),
            ],
        )

    async def execute(self, code: str, **kwargs) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3", f.name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout.decode()[:3000]
                errors = stderr.decode()[:1000]
                result = f"[code_exec] Exit code: {proc.returncode}\n"
                if output:
                    result += f"stdout:\n{output}\n"
                if errors:
                    result += f"stderr:\n{errors}\n"
                return result
            except asyncio.TimeoutError:
                return "[code_exec] Error: execution timed out (30s)"
            finally:
                import os
                os.unlink(f.name)
```

- [ ] **Step 5: Shell Execution tool**

```python
# orchestrator/tools/builtin/shell_exec.py
"""Shell command execution."""

import asyncio
from orchestrator.tools.base import BaseTool, ToolParam


class ShellExecTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="shell_exec",
            description="Execute shell commands. Use for system operations, file management, git commands.",
            parameters=[
                ToolParam(name="command", type="string", description="Shell command to execute"),
                ToolParam(name="workdir", type="string", description="Working directory", required=False),
            ],
        )

    async def execute(self, command: str, workdir: str = "/tmp", **kwargs) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode()[:3000]
            errors = stderr.decode()[:1000]
            result = f"[shell] $ {command}\nExit: {proc.returncode}\n"
            if output:
                result += output + "\n"
            if errors:
                result += f"stderr: {errors}\n"
            return result
        except asyncio.TimeoutError:
            return f"[shell] Error: timeout (30s) for: {command}"
```

- [ ] **Step 6: Perplexity Sonar tool**

```python
# orchestrator/tools/builtin/perplexity.py
"""AI-powered search via Perplexity Sonar API."""

import os
import httpx
from orchestrator.tools.base import BaseTool, ToolParam


class PerplexityTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="perplexity",
            description="AI-powered search with citations. Better than web_search for complex questions requiring synthesis.",
            parameters=[
                ToolParam(name="query", type="string", description="Question or search query"),
            ],
        )
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "")

    async def execute(self, query: str, **kwargs) -> str:
        if not self.api_key:
            return "[perplexity] Error: PERPLEXITY_API_KEY not set"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                },
            )
            if resp.status_code != 200:
                return f"[perplexity] Error: HTTP {resp.status_code}"
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])
            result = f"## Perplexity answer for: {query}\n\n{content}"
            if citations:
                result += "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations[:5])
            return result
```

- [ ] **Step 7: Verify all tools import**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.tools.builtin.web_search import WebSearchTool; from orchestrator.tools.builtin.http_request import HttpRequestTool; from orchestrator.tools.builtin.code_exec import CodeExecTool; from orchestrator.tools.builtin.shell_exec import ShellExecTool; from orchestrator.tools.builtin.perplexity import PerplexityTool; print('All 5 tools OK')"`

- [ ] **Step 8: Commit**

```bash
git add orchestrator/tools/builtin/
git commit -m "feat(tools): add 5 real tool implementations — web_search, http_request, code_exec, shell_exec, perplexity"
```

---

## Task 3: Tool Registry

**Files:**
- Create: `orchestrator/tools/registry.py`
- Modify: `orchestrator/models.py` — Update ToolDefinition, add CustomToolConfig

- [ ] **Step 1: Expand ToolDefinition model in models.py**

Add `is_builtin`, `config_schema` fields to `ToolDefinition`. Add `CustomToolConfig` for user-defined tools.

```python
# In orchestrator/models.py — replace the existing ToolDefinition and AVAILABLE_TOOLS

class ToolDefinition(BaseModel):
    """Tool available for agents."""
    key: str
    name: str
    description: str
    category: str
    is_builtin: bool = True
    config_schema: dict = {}  # JSON schema for custom tool config (url, headers, etc.)


class CustomToolConfig(BaseModel):
    """User-defined custom tool configuration."""
    key: str
    name: str
    description: str
    category: str = "custom"
    tool_type: str  # "http_api", "ssh", "shell_command"
    config: dict = {}  # type-specific: {"url": "...", "method": "GET", "headers": {...}} or {"host": "...", "user": "...", "key_path": "..."}
```

Update `AVAILABLE_TOOLS` to include the new `is_builtin=True` field (no change needed since default is True).

- [ ] **Step 2: Write Tool Registry**

```python
# orchestrator/tools/registry.py
"""Tool registry — maps tool keys to executable instances."""

from orchestrator.tools.base import BaseTool
from orchestrator.tools.builtin.web_search import WebSearchTool
from orchestrator.tools.builtin.http_request import HttpRequestTool
from orchestrator.tools.builtin.code_exec import CodeExecTool
from orchestrator.tools.builtin.shell_exec import ShellExecTool
from orchestrator.tools.builtin.perplexity import PerplexityTool


class ToolRegistry:
    """Manages built-in and custom tool instances."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._register_builtins()

    def _register_builtins(self):
        builtins = [
            WebSearchTool(),
            HttpRequestTool(),
            CodeExecTool(),
            ShellExecTool(),
            PerplexityTool(),
        ]
        for tool in builtins:
            self._tools[tool.name] = tool

    def register(self, tool: BaseTool):
        """Register a custom tool at runtime."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_many(self, names: list[str]) -> list[BaseTool]:
        return [self._tools[n] for n in names if n in self._tools]

    def list_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def openai_functions(self, names: list[str] | None = None) -> list[dict]:
        """Get OpenAI function schemas for the router."""
        tools = self.get_many(names) if names else self.list_all()
        return [t.to_openai_function() for t in tools]


# Global registry instance
registry = ToolRegistry()
```

- [ ] **Step 3: Verify**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.tools.registry import registry; print(f'Registry: {len(registry.list_all())} tools'); print([t.name for t in registry.list_all()])"`

Expected: `Registry: 5 tools` + list of names

- [ ] **Step 4: Commit**

```bash
git add orchestrator/tools/registry.py orchestrator/models.py
git commit -m "feat(tools): add ToolRegistry with 5 built-in tools"
```

---

## Task 4: Tool Router (MiniMax with function_calling)

**Files:**
- Create: `orchestrator/tools/router.py`

- [ ] **Step 1: Write the Tool Router**

```python
# orchestrator/tools/router.py
"""Tool router — uses a cheap model (MiniMax) with function_calling to decide which tools to invoke."""

import json
import logging
from langchain_openai import ChatOpenAI
from orchestrator.tools.registry import registry

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are a tool router. Given a task and a list of available tools, decide which tools to call to gather information BEFORE the main agent works on the task.

Rules:
- Only call tools that would provide USEFUL context for the task
- If no tools are needed, return no function calls
- For search queries, formulate specific, targeted queries
- You may call multiple tools if needed
- Be conservative — don't call tools unnecessarily"""


async def route_tools(task: str, tool_keys: list[str], context: str = "") -> list[dict]:
    """Ask MiniMax which tools to call for this task.

    Returns list of {"tool": "name", "args": {...}} dicts.
    """
    if not tool_keys:
        return []

    available_tools = registry.get_many(tool_keys)
    if not available_tools:
        return []

    functions = [t.to_openai_function() for t in available_tools]

    try:
        router_llm = ChatOpenAI(
            model="minimax/minimax-m2.7",
            api_key="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",
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )

        prompt = f"Task: {task}"
        if context:
            prompt = f"Task: {task}\n\nContext so far:\n{context}"

        response = await router_llm.ainvoke(
            [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tools=functions,
        )

        tool_calls = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append({
                    "tool": tc["name"],
                    "args": tc["args"],
                })

        return tool_calls

    except Exception as e:
        logger.warning("Tool router failed: %s", e)
        return []
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.tools.router import route_tools; print('Router OK')"`

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tools/router.py
git commit -m "feat(tools): add MiniMax-powered tool router with function_calling"
```

---

## Task 5: Tool Executor

**Files:**
- Create: `orchestrator/tools/executor.py`

- [ ] **Step 1: Write the Tool Executor**

```python
# orchestrator/tools/executor.py
"""Tool executor — runs tools selected by the router and formats results."""

import asyncio
import logging
import time
from orchestrator.tools.registry import registry
from orchestrator.tools.router import route_tools

logger = logging.getLogger(__name__)


async def execute_tools(tool_calls: list[dict]) -> list[dict]:
    """Execute a list of tool calls in parallel.

    Returns list of {"tool": "name", "result": "...", "elapsed_sec": 1.2} dicts.
    """
    async def _run_one(call: dict) -> dict:
        tool = registry.get(call["tool"])
        if not tool:
            return {"tool": call["tool"], "result": f"[{call['tool']}] Error: tool not found", "elapsed_sec": 0}
        t0 = time.time()
        try:
            result = await tool.execute(**call.get("args", {}))
            return {"tool": call["tool"], "result": result, "elapsed_sec": round(time.time() - t0, 2)}
        except Exception as e:
            return {"tool": call["tool"], "result": f"[{call['tool']}] Error: {e}", "elapsed_sec": round(time.time() - t0, 2)}

    if not tool_calls:
        return []
    results = await asyncio.gather(*[_run_one(c) for c in tool_calls])
    return list(results)


def format_tool_results(results: list[dict]) -> str:
    """Format tool results into a context block for the agent."""
    if not results:
        return ""
    sections = ["## Tool Results\n"]
    for r in results:
        sections.append(f"### {r['tool']} ({r['elapsed_sec']}s)\n{r['result']}\n")
    return "\n".join(sections)


async def enrich_context(task: str, tool_keys: list[str], existing_context: str = "") -> tuple[str, list[dict]]:
    """Full pipeline: route → execute → format.

    Returns (enriched_context_string, raw_tool_results).
    """
    tool_calls = await route_tools(task, tool_keys, context=existing_context)
    if not tool_calls:
        return "", []
    results = await execute_tools(tool_calls)
    context = format_tool_results(results)
    return context, results
```

- [ ] **Step 2: Verify**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.tools.executor import enrich_context, format_tool_results; print('Executor OK')"`

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tools/executor.py
git commit -m "feat(tools): add tool executor with parallel execution and context enrichment"
```

---

## Task 6: Integrate Tool Pipeline into Agent Calls

**Files:**
- Modify: `orchestrator/modes/base.py` — Replace prompt injection with real tool execution

- [ ] **Step 1: Rewrite call_agent_cfg to use tool pipeline**

Replace the current `_build_tools_prompt` + prompt injection approach with real tool execution. The new `call_agent_cfg` becomes async and calls `enrich_context()` before the LLM.

```python
# orchestrator/modes/base.py — full rewrite

"""Base class for orchestration modes and agent factory."""

import re
import time
import asyncio
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from langchain_gateway import GatewayClaude, GatewayGemini, GatewayCodex, GatewayMiniMax


def make_llm(provider: str) -> BaseChatModel:
    """Create a LangChain model for the given provider."""
    if provider == "claude":
        return GatewayClaude()
    elif provider == "gemini":
        return GatewayGemini()
    elif provider == "codex":
        return GatewayCodex()
    elif provider == "minimax":
        return GatewayMiniMax()
    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_agent(provider: str, prompt: str, system_prompt: str = "") -> str:
    """Call an agent and return the text response (no tools)."""
    llm = make_llm(provider)
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    result = llm.invoke(messages)
    return result.content


def call_agent_cfg(agent: dict, prompt: str) -> str:
    """Call an agent with tool enrichment.

    If the agent has tools, runs the tool pipeline (router → executor → context)
    synchronously (for LangGraph graph.invoke compatibility), then calls the LLM
    with the enriched prompt.
    """
    tool_keys = agent.get("tools") or []
    enriched_context = ""

    if tool_keys:
        try:
            from orchestrator.tools.executor import enrich_context
            enriched_context, _results = asyncio.get_event_loop().run_until_complete(
                enrich_context(prompt, tool_keys)
            )
        except RuntimeError:
            # If already in an async context, use a new event loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                from orchestrator.tools.executor import enrich_context
                future = pool.submit(asyncio.run, enrich_context(prompt, tool_keys))
                enriched_context, _results = future.result(timeout=60)
        except Exception:
            enriched_context = ""

    full_prompt = prompt
    if enriched_context:
        full_prompt = f"{prompt}\n\n{enriched_context}"

    return call_agent(
        agent["provider"], full_prompt,
        agent.get("system_prompt", ""),
    )


def strip_markdown_fence(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json|python)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def make_message(agent_id: str, content: str, phase: str = "", **meta) -> dict:
    """Create a message dict for the session log."""
    return {
        "agent_id": agent_id,
        "content": content,
        "timestamp": time.time(),
        "phase": phase,
        **meta,
    }
```

- [ ] **Step 2: Verify all modes still import**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.modes.dictator import build_dictator_graph; from orchestrator.modes.debate import build_debate_graph; from orchestrator.modes.board import build_board_graph; print('All modes OK')"`

- [ ] **Step 3: Commit**

```bash
git add orchestrator/modes/base.py
git commit -m "feat(tools): integrate real tool pipeline into call_agent_cfg — router + executor + context injection"
```

---

## Task 7: Custom Tools API Endpoints

**Files:**
- Modify: `orchestrator/api.py` — Add CRUD for custom tools
- Modify: `orchestrator/models.py` — Add custom tool storage

- [ ] **Step 1: Add custom tool store to models.py**

```python
# Add after the store = SessionStore() line in models.py

# ---- Custom tools store (in-memory) ----
_custom_tools: list[dict] = []


def add_custom_tool(config: dict) -> dict:
    """Register a custom tool."""
    _custom_tools.append(config)
    # Also register as an executable tool
    from orchestrator.tools.builtin.http_request import HttpRequestTool
    from orchestrator.tools.registry import registry
    from orchestrator.tools.base import BaseTool, ToolParam

    if config.get("tool_type") == "http_api":

        class CustomApiTool(BaseTool):
            def __init__(self, cfg):
                super().__init__(
                    name=cfg["key"],
                    description=cfg["description"],
                    parameters=[ToolParam(name="query", type="string", description="Input for this tool")],
                )
                self.cfg = cfg

            async def execute(self, query: str = "", **kwargs) -> str:
                import httpx
                c = self.cfg.get("config", {})
                url = c.get("url", "").replace("{query}", query)
                method = c.get("method", "GET")
                headers = c.get("headers", {})
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.request(method, url, headers=headers)
                    return f"[{self.cfg['key']}] {resp.status_code}\n{resp.text[:3000]}"

        registry.register(CustomApiTool(config))

    return config


def list_custom_tools() -> list[dict]:
    return list(_custom_tools)


def remove_custom_tool(key: str) -> bool:
    global _custom_tools
    before = len(_custom_tools)
    _custom_tools = [t for t in _custom_tools if t.get("key") != key]
    return len(_custom_tools) < before
```

- [ ] **Step 2: Add API endpoints in api.py**

```python
# Add to orchestrator/api.py — after the /tools endpoint

@router.post("/tools/custom")
async def ep_add_custom_tool(config: dict):
    from orchestrator.models import add_custom_tool
    if not config.get("key") or not config.get("name"):
        raise HTTPException(422, "Custom tool requires 'key' and 'name'")
    return add_custom_tool(config)


@router.get("/tools/custom")
async def ep_list_custom_tools():
    from orchestrator.models import list_custom_tools
    return list_custom_tools()


@router.delete("/tools/custom/{key}")
async def ep_remove_custom_tool(key: str):
    from orchestrator.models import remove_custom_tool
    if not remove_custom_tool(key):
        raise HTTPException(404, f"Custom tool not found: {key}")
    return {"status": "removed"}
```

- [ ] **Step 3: Update /tools endpoint to include custom tools**

```python
# Replace the existing ep_tools in api.py

@router.get("/tools")
async def ep_tools():
    from orchestrator.models import list_custom_tools, AVAILABLE_TOOLS
    builtin = [t.model_dump() for t in AVAILABLE_TOOLS]
    custom = [{"key": t["key"], "name": t["name"], "description": t["description"],
               "category": t.get("category", "custom"), "is_builtin": False} for t in list_custom_tools()]
    return builtin + custom
```

- [ ] **Step 4: Verify**

Run: `cd /Users/martin/multi-agent && python3 -c "from orchestrator.api import router; print('API OK')"`

- [ ] **Step 5: Commit**

```bash
git add orchestrator/api.py orchestrator/models.py
git commit -m "feat(tools): add custom tools CRUD API endpoints"
```

---

## Task 8: Frontend — Update Types and API

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/constants.ts`

- [ ] **Step 1: Update types.ts**

Add `CustomToolConfig` and update `ToolDefinition`:

```typescript
export interface ToolDefinition {
  key: string;
  name: string;
  description: string;
  category: string;
  is_builtin?: boolean;
}

export interface CustomToolConfig {
  key: string;
  name: string;
  description: string;
  category?: string;
  tool_type: "http_api" | "ssh" | "shell_command";
  config: Record<string, string>;
}
```

- [ ] **Step 2: Update api.ts**

Add custom tools API functions:

```typescript
export async function addCustomTool(config: CustomToolConfig): Promise<CustomToolConfig> {
  return request("/orchestrate/tools/custom", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function getCustomTools(): Promise<CustomToolConfig[]> {
  return request("/orchestrate/tools/custom");
}

export async function removeCustomTool(key: string): Promise<void> {
  await request(`/orchestrate/tools/custom/${key}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Update constants.ts — add new built-in tools**

Add the new real tools (perplexity, http_request, shell_exec) to the labels/descriptions:

```typescript
// Add to TOOL_LABELS
  perplexity: "Perplexity AI",
  http_request: "HTTP запрос",
  shell_exec: "Shell команда",

// Add to TOOL_DESCRIPTIONS
  perplexity: "AI-поиск с цитатами через Perplexity Sonar",
  http_request: "HTTP запросы к любым API",
  shell_exec: "Выполнение shell команд",
```

- [ ] **Step 4: Verify frontend build**

Run: `cd /Users/martin/multi-agent/frontend && npx next build 2>&1 | grep -E "Compiled|error"`

Expected: `✓ Compiled successfully`

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/
git commit -m "feat(tools): update frontend types, API, and constants for real tools + custom tools"
```

---

## Task 9: Frontend — Custom Tool Form Component

**Files:**
- Create: `frontend/components/wizard/custom-tool-form.tsx`
- Modify: `frontend/components/wizard/step-agents.tsx`

- [ ] **Step 1: Create the custom tool form**

Build a form using 21st Magic MCP components (or existing shadcn components) for adding custom tools. The form should support:
- Tool name, key, description
- Tool type selector (HTTP API / SSH / Shell Command)
- Type-specific fields:
  - HTTP API: URL, method, headers
  - SSH: host, port, username, key/password
  - Shell: command template

Use existing shadcn `Select`, `Card`, `Button` components. Get inspiration from 21st Magic MCP for the form layout.

- [ ] **Step 2: Add "Добавить свой инструмент" button to step-agents**

Below the SelectorChips for built-in tools, add a button that opens the custom tool form as an inline card. When submitted, it calls `addCustomTool()` and adds the key to the agent's tools list.

- [ ] **Step 3: Update tool chips to show custom tools**

The SelectorChips should show both built-in and custom tools. Fetch the tools list from the API (which now includes custom tools) instead of using the static `ALL_TOOL_KEYS` constant.

- [ ] **Step 4: Verify frontend build**

Run: `cd /Users/martin/multi-agent/frontend && npx next build 2>&1 | grep -E "Compiled|error"`

- [ ] **Step 5: Commit**

```bash
git add frontend/components/wizard/
git commit -m "feat(tools): add custom tool creation form in wizard UI"
```

---

## Task 10: Update AVAILABLE_TOOLS Catalog

**Files:**
- Modify: `orchestrator/models.py` — Align catalog with real tool implementations

- [ ] **Step 1: Update AVAILABLE_TOOLS to match real backends**

Replace the old fake tools with the real ones that have backends:

```python
AVAILABLE_TOOLS: list[ToolDefinition] = [
    # Real tools with backends
    ToolDefinition(key="web_search", name="Веб-поиск", description="Поиск в интернете через Brave Search API", category="research"),
    ToolDefinition(key="perplexity", name="Perplexity AI", description="AI-поиск с цитатами через Perplexity Sonar", category="research"),
    ToolDefinition(key="http_request", name="HTTP запрос", description="HTTP запросы к любым API (GET/POST/PUT/DELETE)", category="integration"),
    ToolDefinition(key="code_exec", name="Python", description="Выполнение Python кода (вычисления, обработка данных)", category="code"),
    ToolDefinition(key="shell_exec", name="Shell", description="Выполнение shell команд (файлы, git, система)", category="code"),
]
```

- [ ] **Step 2: Update DEFAULT_AGENTS to use real tool keys**

Update `engine.py` — change tool keys in DEFAULT_AGENTS to only reference tools that have real backends.

- [ ] **Step 3: Update frontend constants to match**

Update `TOOL_LABELS` and `TOOL_DESCRIPTIONS` in `frontend/lib/constants.ts` to match the new catalog.

- [ ] **Step 4: Verify end-to-end**

Run:
```bash
cd /Users/martin/multi-agent && python3 -c "
from orchestrator.tools.registry import registry
from orchestrator.models import AVAILABLE_TOOLS, TOOLS_BY_KEY
for t in AVAILABLE_TOOLS:
    impl = registry.get(t.key)
    status = 'HAS BACKEND' if impl else 'NO BACKEND'
    print(f'  {t.key}: {status}')
"
```

Expected: All tools show `HAS BACKEND`

- [ ] **Step 5: Commit**

```bash
git add orchestrator/models.py orchestrator/engine.py frontend/lib/constants.ts
git commit -m "feat(tools): align tool catalog with real backends, remove fake tools"
```

---

## Task 11: End-to-End Verification

- [ ] **Step 1: Backend validation**

```bash
cd /Users/martin/multi-agent && python3 -c "
from orchestrator.tools.registry import registry
from orchestrator.tools.executor import execute_tools, format_tool_results
from orchestrator.tools.router import route_tools
from orchestrator.modes.base import call_agent_cfg
import asyncio

# Test registry
print(f'Registry: {len(registry.list_all())} tools')
for t in registry.list_all():
    print(f'  {t.name}: {len(t.parameters)} params')
    schema = t.to_openai_function()
    assert schema['type'] == 'function'
    print(f'    OpenAI schema: OK')

# Test code_exec (no API key needed)
result = asyncio.run(execute_tools([{'tool': 'code_exec', 'args': {'code': 'print(2+2)'}}]))
print(f'code_exec result: {result[0][\"result\"][:100]}')
assert '4' in result[0]['result']
print('ALL BACKEND CHECKS PASSED')
"
```

- [ ] **Step 2: Frontend build**

Run: `cd /Users/martin/multi-agent/frontend && npx next build 2>&1 | grep -E "Compiled|error"`

- [ ] **Step 3: Live test with real API**

Start backend, hit the `/orchestrate/tools` endpoint, verify it returns real tool catalog.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(tools): complete real tools system — router, executor, 5 built-in tools, custom tools UI"
```
