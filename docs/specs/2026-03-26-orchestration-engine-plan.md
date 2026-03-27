# Multi-Agent Orchestration Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-based orchestration engine with 7 modes (dictator, board, democracy, debate, map_reduce, creator_critic, tournament), exposed as FastAPI endpoints, using the existing CLI gateway for agent calls.

**Architecture:** Each orchestration mode is a LangGraph StateGraph with typed state, conditional routing, and parallel fan-out where needed. All agent calls go through `langchain_gateway.py` (GatewayClaude/Gemini/Codex/MiniMax). The orchestrator mounts as a sub-router in the existing `gateway.py` on port 8800.

**Tech Stack:** Python 3.12, LangGraph 1.x, LangChain Core, FastAPI, httpx, langchain-openai (for MiniMax via OpenRouter)

---

### Task 1: Install dependencies and add GatewayMiniMax

**Files:**
- Modify: `/Users/martin/multi-agent/langchain_gateway.py`
- Modify: `/Users/martin/multi-agent/requirements.txt`

- [ ] **Step 1: Install langchain-openai**

Run: `pip3 install --break-system-packages langchain-openai`
Expected: Successfully installed langchain-openai

- [ ] **Step 2: Add GatewayMiniMax class to langchain_gateway.py**

Add at the end of the file, before `if __name__`:

```python
# =========================================================================
#  MiniMax via OpenRouter (API, not CLI)
# =========================================================================

from langchain_openai import ChatOpenAI


class GatewayMiniMax(ChatOpenAI):
    """MiniMax m2.7 via OpenRouter. For lightweight tasks: summaries, formatting, voting."""

    def __init__(self, **kwargs):
        super().__init__(
            model=kwargs.pop("model", "minimax/minimax-m2.7"),
            api_key=kwargs.pop("api_key", os.environ.get("OPENROUTER_API_KEY", "")),
            base_url=kwargs.pop("base_url", "https://openrouter.ai/api/v1"),
            **kwargs,
        )
```

- [ ] **Step 3: Update requirements.txt**

```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
langchain-core>=0.3.0
langgraph>=1.0.0
langchain-openai>=0.3.0
```

- [ ] **Step 4: Test GatewayMiniMax**

Run: `cd ~/multi-agent && python3 -c "from langchain_gateway import GatewayMiniMax; m = GatewayMiniMax(); print(m.invoke('Say hello in one word').content)"`
Expected: A one-word greeting

---

### Task 2: Create orchestrator package and models

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/__init__.py`
- Create: `/Users/martin/multi-agent/orchestrator/models.py`

- [ ] **Step 1: Create package directory**

Run: `mkdir -p ~/multi-agent/orchestrator/modes`

- [ ] **Step 2: Create __init__.py**

```python
"""Multi-agent orchestration engine with 7 modes."""
```

- [ ] **Step 3: Create modes/__init__.py**

```python
"""Orchestration mode implementations."""
```

- [ ] **Step 4: Create models.py**

```python
"""Data models for orchestration sessions."""

import time
import uuid
from typing import Annotated, Optional

import operator
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---- API Request/Response models (Pydantic) ----

class AgentConfig(BaseModel):
    """Agent configuration from API request."""
    role: str                           # "director", "analyst", "critic", etc.
    provider: str                       # "claude" | "gemini" | "codex" | "minimax"
    system_prompt: str = ""             # custom prompt for this role


class RunRequest(BaseModel):
    """POST /orchestrate/run request body."""
    mode: str                           # "dictator" | "board" | etc.
    task: str                           # user's task
    agents: list[AgentConfig] = []      # agent assignments (optional, auto-filled if empty)
    config: dict = {}                   # mode-specific: max_rounds, max_iterations, etc.


class MessageRequest(BaseModel):
    """POST /orchestrate/session/{id}/message request body."""
    content: str


class SessionResponse(BaseModel):
    """GET /orchestrate/session/{id} response."""
    id: str
    mode: str
    task: str
    agents: list[AgentConfig]
    messages: list[dict]
    result: Optional[str] = None
    status: str                         # "running" | "completed" | "failed"
    config: dict = {}
    created_at: float
    elapsed_sec: Optional[float] = None


# ---- LangGraph State (TypedDict for graph nodes) ----

class OrchestratorState(TypedDict):
    """Base state shared by all orchestration modes."""
    session_id: str
    mode: str
    task: str
    agents: list[dict]                                  # list of AgentConfig as dicts
    messages: Annotated[list[dict], operator.add]        # append-only message log
    result: str
    status: str
    config: dict
    user_messages: Annotated[list[str], operator.add]    # user interventions
    created_at: float
    # Mode-specific fields are added by each mode's subclass


# ---- Session store (in-memory) ----

class SessionStore:
    """Simple in-memory session storage. Keeps last 100 sessions."""

    def __init__(self, max_sessions: int = 100):
        self._sessions: dict[str, dict] = {}
        self._max = max_sessions

    def create(self, mode: str, task: str, agents: list[AgentConfig], config: dict) -> str:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
        self._sessions[sid] = {
            "id": sid,
            "mode": mode,
            "task": task,
            "agents": [a.model_dump() for a in agents],
            "messages": [],
            "result": None,
            "status": "running",
            "config": config,
            "created_at": time.time(),
            "elapsed_sec": None,
        }
        # Evict oldest if over limit
        if len(self._sessions) > self._max:
            oldest = min(self._sessions, key=lambda k: self._sessions[k]["created_at"])
            del self._sessions[oldest]
        return sid

    def get(self, sid: str) -> Optional[dict]:
        return self._sessions.get(sid)

    def update(self, sid: str, **kwargs):
        if sid in self._sessions:
            self._sessions[sid].update(kwargs)

    def append_messages(self, sid: str, msgs: list[dict]):
        if sid in self._sessions:
            self._sessions[sid]["messages"].extend(msgs)

    def list_recent(self, limit: int = 50) -> list[dict]:
        sessions = sorted(self._sessions.values(), key=lambda s: s["created_at"], reverse=True)
        return [{"id": s["id"], "mode": s["mode"], "task": s["task"][:100],
                 "status": s["status"], "created_at": s["created_at"]} for s in sessions[:limit]]


# Global store instance
store = SessionStore()
```

- [ ] **Step 5: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.models import store, RunRequest, OrchestratorState; print('models OK')"`
Expected: `models OK`

---

### Task 3: Create base mode and agent factory

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/base.py`

- [ ] **Step 1: Create base.py**

```python
"""Base class for orchestration modes and agent factory."""

import time
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

import sys
sys.path.insert(0, "/Users/martin/multi-agent")
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
    """Call an agent and return the text response."""
    llm = make_llm(provider)
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    result = llm.invoke(messages)
    return result.content


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

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.base import make_llm, call_agent, make_message; print('base OK')"`
Expected: `base OK`

---

### Task 4: Implement Dictator mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/dictator.py`

- [ ] **Step 1: Create dictator.py**

```python
"""Dictator mode: one director delegates to workers, collects results."""

import asyncio
import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class DictatorState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    subtasks: list[dict]        # [{description, assigned_to}]
    worker_results: Annotated[list[dict], operator.add]
    iteration: int
    max_iterations: int
    result: str


def director_plan(state: DictatorState) -> dict:
    """Director breaks task into subtasks."""
    director = state["agents"][0]
    workers = state["agents"][1:]

    prompt = (
        f"You are the director. Break this task into {len(workers)} subtasks.\n\n"
        f"TASK: {state['task']}\n\n"
        f"Available workers: {json.dumps([w['role'] for w in workers])}\n\n"
        f"Respond with a JSON array of objects: "
        f'[{{"description": "subtask text", "worker_index": 0}}, ...]\n'
        f"worker_index is 0-based index into the workers list.\n"
        f"Return ONLY valid JSON, no markdown."
    )

    response = call_agent(director["provider"], prompt, director.get("system_prompt", ""))

    try:
        subtasks = json.loads(response.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        subtasks = [{"description": state["task"], "worker_index": i}
                    for i in range(len(workers))]

    return {
        "subtasks": subtasks,
        "messages": [make_message(director["role"], f"Plan: {json.dumps(subtasks, ensure_ascii=False)}", "planning")],
    }


def workers_execute(state: DictatorState) -> dict:
    """Workers execute their assigned subtasks."""
    workers = state["agents"][1:]
    results = []
    messages = []

    for st in state["subtasks"]:
        idx = st.get("worker_index", 0) % len(workers)
        worker = workers[idx]

        prompt = (
            f"Complete this subtask:\n{st['description']}\n\n"
            f"Context — overall task: {state['task']}"
        )

        response = call_agent(worker["provider"], prompt, worker.get("system_prompt", ""))
        results.append({"subtask": st["description"], "worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, "executing"))

    return {"worker_results": results, "messages": messages}


def director_synthesize(state: DictatorState) -> dict:
    """Director reviews worker results and synthesizes final answer."""
    director = state["agents"][0]

    results_text = "\n\n".join(
        f"## {r['worker']}: {r['subtask']}\n{r['result']}"
        for r in state["worker_results"]
    )

    prompt = (
        f"You are the director. Your workers completed their subtasks.\n\n"
        f"ORIGINAL TASK: {state['task']}\n\n"
        f"WORKER RESULTS:\n{results_text}\n\n"
        f"Synthesize a comprehensive final answer. "
        f"If results are insufficient, say NEEDS_MORE_WORK and explain what's missing."
    )

    response = call_agent(director["provider"], prompt, director.get("system_prompt", ""))

    return {
        "result": response,
        "iteration": state["iteration"] + 1,
        "messages": [make_message(director["role"], response, "synthesizing")],
    }


def route_after_synthesis(state: DictatorState) -> str:
    """Check if director needs another round."""
    if "NEEDS_MORE_WORK" in state["result"] and state["iteration"] < state["max_iterations"]:
        return "director_plan"
    return END


def build_dictator_graph() -> StateGraph:
    builder = StateGraph(DictatorState)

    builder.add_node("director_plan", director_plan)
    builder.add_node("workers_execute", workers_execute)
    builder.add_node("director_synthesize", director_synthesize)

    builder.add_edge(START, "director_plan")
    builder.add_edge("director_plan", "workers_execute")
    builder.add_edge("workers_execute", "director_synthesize")
    builder.add_conditional_edges("director_synthesize", route_after_synthesis, {
        "director_plan": "director_plan",
        END: END,
    })

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.dictator import build_dictator_graph; g = build_dictator_graph(); print('dictator OK')"`
Expected: `dictator OK`

---

### Task 5: Implement Democracy mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/democracy.py`

- [ ] **Step 1: Create democracy.py**

```python
"""Democracy mode: all agents vote, majority wins, tie → re-vote."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class DemocracyState(TypedDict):
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    votes: list[dict]          # [{agent_id, position, reasoning}]
    round: int
    max_rounds: int
    majority_position: str
    result: str


def collect_votes(state: DemocracyState) -> dict:
    """All agents vote on the task."""
    votes = []
    messages = []
    previous = ""

    if state["round"] > 1 and state["votes"]:
        previous = "\n\nPrevious round votes (no majority reached):\n" + "\n".join(
            f"- {v['agent_id']}: {v['position']}" for v in state["votes"]
        )

    for agent in state["agents"]:
        prompt = (
            f"Vote on this task. Give your position clearly.\n\n"
            f"TASK: {state['task']}\n"
            f"{previous}\n\n"
            f"Respond with JSON: {{\"position\": \"your clear position\", \"reasoning\": \"why\"}}\n"
            f"Return ONLY valid JSON."
        )

        response = call_agent(agent["provider"], prompt, agent.get("system_prompt", ""))

        try:
            vote = json.loads(response.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            vote = {"position": response[:200], "reasoning": ""}

        vote["agent_id"] = agent["role"]
        votes.append(vote)
        messages.append(make_message(agent["role"], f"Vote: {vote['position']}", f"voting_round_{state['round'] + 1}"))

    return {
        "votes": votes,
        "round": state["round"] + 1,
        "messages": messages,
    }


def tally_votes(state: DemocracyState) -> dict:
    """Count votes and determine majority using MiniMax."""
    votes_text = "\n".join(f"- {v['agent_id']}: {v['position']}" for v in state["votes"])

    prompt = (
        f"Analyze these votes and determine if there is a clear majority.\n\n"
        f"VOTES:\n{votes_text}\n\n"
        f"Respond with JSON:\n"
        f'{{"has_majority": true/false, "majority_position": "the winning position or empty", '
        f'"summary": "brief summary of the vote"}}\n'
        f"Return ONLY valid JSON."
    )

    response = call_agent("minimax", prompt)

    try:
        tally = json.loads(response.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        tally = {"has_majority": True, "majority_position": state["votes"][0]["position"], "summary": response}

    messages = [make_message("system", f"Tally: {tally.get('summary', '')}", f"tally_round_{state['round']}")]

    if tally.get("has_majority"):
        return {
            "majority_position": tally.get("majority_position", ""),
            "result": tally.get("majority_position", ""),
            "messages": messages,
        }

    return {
        "majority_position": "",
        "messages": messages,
    }


def route_after_tally(state: DemocracyState) -> str:
    if state["majority_position"]:
        return END
    if state["round"] >= state["max_rounds"]:
        return "force_decision"
    return "collect_votes"


def force_decision(state: DemocracyState) -> dict:
    """No majority after max rounds. MiniMax summarizes both sides."""
    votes_text = "\n".join(f"- {v['agent_id']}: {v['position']}" for v in state["votes"])

    response = call_agent(
        "minimax",
        f"No majority was reached after {state['round']} rounds.\n\nVotes:\n{votes_text}\n\n"
        f"Summarize both positions and pick the most-supported one as the final answer.",
    )

    return {
        "result": response,
        "messages": [make_message("system", response, "forced_decision")],
    }


def build_democracy_graph() -> StateGraph:
    builder = StateGraph(DemocracyState)

    builder.add_node("collect_votes", collect_votes)
    builder.add_node("tally_votes", tally_votes)
    builder.add_node("force_decision", force_decision)

    builder.add_edge(START, "collect_votes")
    builder.add_edge("collect_votes", "tally_votes")
    builder.add_conditional_edges("tally_votes", route_after_tally, {
        END: END,
        "collect_votes": "collect_votes",
        "force_decision": "force_decision",
    })
    builder.add_edge("force_decision", END)

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.democracy import build_democracy_graph; g = build_democracy_graph(); print('democracy OK')"`
Expected: `democracy OK`

---

### Task 6: Implement Debate mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/debate.py`

- [ ] **Step 1: Create debate.py**

```python
"""Debate mode: proponent vs opponent, judge decides."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class DebateState(TypedDict):
    task: str
    agents: list[dict]          # [proponent, opponent, judge]
    messages: Annotated[list[dict], operator.add]
    rounds: list[dict]          # [{round, pro_arg, con_arg}]
    current_round: int
    max_rounds: int
    verdict: str
    result: str


def proponent_argues(state: DebateState) -> dict:
    """Proponent argues FOR."""
    pro = state["agents"][0]
    rnd = state["current_round"]

    history = ""
    if state["rounds"]:
        history = "\n\nPrevious rounds:\n" + "\n".join(
            f"Round {r['round']}:\n  PRO: {r['pro_arg'][:300]}\n  CON: {r['con_arg'][:300]}"
            for r in state["rounds"]
        )

    prompt = (
        f"You are arguing FOR the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n"
        f"{history}\n\n"
        f"Make your strongest argument. Be specific and evidence-based. "
        f"If this is round 2+, rebut the opponent's previous points."
    )

    response = call_agent(pro["provider"], prompt, pro.get("system_prompt", ""))

    return {
        "messages": [make_message(pro["role"], response, f"round_{rnd + 1}_pro")],
        "rounds": [*state["rounds"], {"round": rnd + 1, "pro_arg": response, "con_arg": ""}],
    }


def opponent_argues(state: DebateState) -> dict:
    """Opponent argues AGAINST."""
    opp = state["agents"][1]
    rnd = state["current_round"]

    current_round_data = state["rounds"][-1]
    pro_arg = current_round_data["pro_arg"]

    history = ""
    if len(state["rounds"]) > 1:
        history = "\n\nPrevious rounds:\n" + "\n".join(
            f"Round {r['round']}:\n  PRO: {r['pro_arg'][:300]}\n  CON: {r['con_arg'][:300]}"
            for r in state["rounds"][:-1]
        )

    prompt = (
        f"You are arguing AGAINST the following position. Round {rnd + 1}.\n\n"
        f"TOPIC: {state['task']}\n"
        f"{history}\n\n"
        f"Proponent's argument this round:\n{pro_arg}\n\n"
        f"Counter-argue. Be specific. Attack weak points."
    )

    response = call_agent(opp["provider"], prompt, opp.get("system_prompt", ""))

    updated_rounds = list(state["rounds"])
    updated_rounds[-1] = {**updated_rounds[-1], "con_arg": response}

    return {
        "messages": [make_message(opp["role"], response, f"round_{rnd + 1}_con")],
        "rounds": updated_rounds,
        "current_round": rnd + 1,
    }


def judge_decides(state: DebateState) -> dict:
    """Judge evaluates debate and gives verdict."""
    judge = state["agents"][2]

    debate_text = "\n\n".join(
        f"=== Round {r['round']} ===\nPRO: {r['pro_arg']}\nCON: {r['con_arg']}"
        for r in state["rounds"]
    )

    prompt = (
        f"You are the judge. Evaluate this debate.\n\n"
        f"TOPIC: {state['task']}\n\n"
        f"DEBATE:\n{debate_text}\n\n"
        f"Provide:\n"
        f"1. Your verdict (which side won and why)\n"
        f"2. The strongest argument from each side\n"
        f"3. Your final recommendation\n\n"
        f"If you need one more round of debate, say NEED_MORE_ROUNDS."
    )

    response = call_agent(judge["provider"], prompt, judge.get("system_prompt", ""))

    return {
        "verdict": response,
        "result": response,
        "messages": [make_message(judge["role"], response, "verdict")],
    }


def route_after_judge(state: DebateState) -> str:
    if "NEED_MORE_ROUNDS" in state["verdict"] and state["current_round"] < state["max_rounds"]:
        return "proponent_argues"
    return END


def build_debate_graph() -> StateGraph:
    builder = StateGraph(DebateState)

    builder.add_node("proponent_argues", proponent_argues)
    builder.add_node("opponent_argues", opponent_argues)
    builder.add_node("judge_decides", judge_decides)

    builder.add_edge(START, "proponent_argues")
    builder.add_edge("proponent_argues", "opponent_argues")
    builder.add_edge("opponent_argues", "judge_decides")
    builder.add_conditional_edges("judge_decides", route_after_judge, {
        "proponent_argues": "proponent_argues",
        END: END,
    })

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.debate import build_debate_graph; g = build_debate_graph(); print('debate OK')"`
Expected: `debate OK`

---

### Task 7: Implement Board mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/board.py`

- [ ] **Step 1: Create board.py**

```python
"""Board mode: council of directors discuss, vote, then delegate."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class BoardState(TypedDict):
    task: str
    agents: list[dict]          # first 3 = directors, rest = workers
    messages: Annotated[list[dict], operator.add]
    positions: list[dict]       # [{director, position, reasoning}]
    vote_round: int
    max_rounds: int
    consensus_reached: bool
    decision: str
    worker_results: Annotated[list[dict], operator.add]
    result: str


def directors_analyze(state: BoardState) -> dict:
    """Each director analyzes independently."""
    directors = state["agents"][:3]
    positions = []
    messages = []

    previous = ""
    if state["positions"]:
        previous = "\n\nPrevious round positions (no consensus):\n" + "\n".join(
            f"- {p['director']}: {p['position']}" for p in state["positions"]
        )

    for d in directors:
        prompt = (
            f"You are on a board of directors. Analyze this task and give your position.\n\n"
            f"TASK: {state['task']}\n"
            f"{previous}\n\n"
            f"Respond with JSON: {{\"position\": \"your stance\", \"reasoning\": \"why\", "
            f"\"action_items\": [\"what to delegate to workers\"]}}\n"
            f"Return ONLY valid JSON."
        )

        response = call_agent(d["provider"], prompt, d.get("system_prompt", ""))

        try:
            pos = json.loads(response.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            pos = {"position": response[:300], "reasoning": "", "action_items": []}

        pos["director"] = d["role"]
        positions.append(pos)
        messages.append(make_message(d["role"], f"Position: {pos['position']}", f"board_round_{state['vote_round'] + 1}"))

    return {
        "positions": positions,
        "vote_round": state["vote_round"] + 1,
        "messages": messages,
    }


def check_consensus(state: BoardState) -> dict:
    """MiniMax checks if directors agree."""
    positions_text = "\n".join(
        f"- {p['director']}: {p['position']}" for p in state["positions"]
    )

    response = call_agent(
        "minimax",
        f"Do these board members agree? Analyze their positions.\n\n"
        f"{positions_text}\n\n"
        f"Respond with JSON: {{\"consensus\": true/false, \"unified_decision\": \"the agreed position or best compromise\"}}\n"
        f"Return ONLY valid JSON.",
    )

    try:
        result = json.loads(response.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        result = {"consensus": True, "unified_decision": state["positions"][0]["position"]}

    return {
        "consensus_reached": result.get("consensus", False),
        "decision": result.get("unified_decision", ""),
        "messages": [make_message("system", f"Consensus: {result.get('consensus')}", "consensus_check")],
    }


def route_after_consensus(state: BoardState) -> str:
    if state["consensus_reached"]:
        if len(state["agents"]) > 3:
            return "delegate_to_workers"
        return "finalize"
    if state["vote_round"] >= state["max_rounds"]:
        return "chairman_decides"
    return "directors_analyze"


def chairman_decides(state: BoardState) -> dict:
    """No consensus — chairman (first director) makes final call."""
    chairman = state["agents"][0]

    positions_text = "\n".join(
        f"- {p['director']}: {p['position']}\n  Reasoning: {p['reasoning']}"
        for p in state["positions"]
    )

    response = call_agent(
        chairman["provider"],
        f"As chairman, no consensus was reached after {state['vote_round']} rounds.\n\n"
        f"Positions:\n{positions_text}\n\n"
        f"Make the final decision. Explain your reasoning.",
        chairman.get("system_prompt", ""),
    )

    return {
        "decision": response,
        "messages": [make_message(chairman["role"], response, "chairman_decision")],
    }


def delegate_to_workers(state: BoardState) -> dict:
    """Delegate decision to workers for execution."""
    workers = state["agents"][3:]
    results = []
    messages = []

    for worker in workers:
        response = call_agent(
            worker["provider"],
            f"The board has decided:\n{state['decision']}\n\n"
            f"Execute your part of this decision.\nOriginal task: {state['task']}",
            worker.get("system_prompt", ""),
        )
        results.append({"worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, "worker_execution"))

    return {"worker_results": results, "messages": messages}


def finalize(state: BoardState) -> dict:
    """Produce final result."""
    if state["worker_results"]:
        combined = "\n\n".join(f"{r['worker']}: {r['result']}" for r in state["worker_results"])
        result = f"Board decision: {state['decision']}\n\nExecution:\n{combined}"
    else:
        result = state["decision"]

    return {"result": result, "messages": [make_message("system", "Session complete", "done")]}


def build_board_graph() -> StateGraph:
    builder = StateGraph(BoardState)

    builder.add_node("directors_analyze", directors_analyze)
    builder.add_node("check_consensus", check_consensus)
    builder.add_node("chairman_decides", chairman_decides)
    builder.add_node("delegate_to_workers", delegate_to_workers)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "directors_analyze")
    builder.add_edge("directors_analyze", "check_consensus")
    builder.add_conditional_edges("check_consensus", route_after_consensus, {
        "delegate_to_workers": "delegate_to_workers",
        "finalize": "finalize",
        "chairman_decides": "chairman_decides",
        "directors_analyze": "directors_analyze",
    })
    builder.add_edge("chairman_decides", "delegate_to_workers")
    builder.add_edge("delegate_to_workers", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.board import build_board_graph; g = build_board_graph(); print('board OK')"`
Expected: `board OK`

---

### Task 8: Implement Map-Reduce mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/map_reduce.py`

- [ ] **Step 1: Create map_reduce.py**

```python
"""Map-Reduce mode: split task into chunks, process in parallel, synthesize."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class MapReduceState(TypedDict):
    task: str
    agents: list[dict]          # [planner, worker1..N, synthesizer]
    messages: Annotated[list[dict], operator.add]
    chunks: list[str]
    chunk_results: Annotated[list[dict], operator.add]
    synthesis: str
    result: str


def plan_chunks(state: MapReduceState) -> dict:
    """Planner splits task into chunks."""
    planner = state["agents"][0]
    num_workers = len(state["agents"]) - 2  # minus planner and synthesizer
    if num_workers < 1:
        num_workers = 1

    prompt = (
        f"Split this task into {num_workers} independent sub-tasks that can be worked on in parallel.\n\n"
        f"TASK: {state['task']}\n\n"
        f"Respond with a JSON array of strings, each describing one sub-task.\n"
        f"Return ONLY valid JSON."
    )

    response = call_agent(planner["provider"], prompt, planner.get("system_prompt", ""))

    try:
        chunks = json.loads(response.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        chunks = [state["task"]]

    return {
        "chunks": chunks,
        "messages": [make_message(planner["role"], f"Split into {len(chunks)} chunks", "planning")],
    }


def process_chunks(state: MapReduceState) -> dict:
    """Workers process chunks (sequentially for now, gateway handles rotation)."""
    workers = state["agents"][1:-1]
    if not workers:
        workers = [state["agents"][0]]

    results = []
    messages = []

    for i, chunk in enumerate(state["chunks"]):
        worker = workers[i % len(workers)]

        response = call_agent(
            worker["provider"],
            f"Process this sub-task:\n{chunk}\n\nOverall context: {state['task']}",
            worker.get("system_prompt", ""),
        )

        results.append({"chunk": chunk, "worker": worker["role"], "result": response})
        messages.append(make_message(worker["role"], response, f"chunk_{i}"))

    return {"chunk_results": results, "messages": messages}


def synthesize(state: MapReduceState) -> dict:
    """Synthesizer combines all chunk results."""
    synth = state["agents"][-1]

    chunks_text = "\n\n".join(
        f"## Chunk: {r['chunk']}\nResult: {r['result']}"
        for r in state["chunk_results"]
    )

    prompt = (
        f"Synthesize these partial results into one comprehensive answer.\n\n"
        f"ORIGINAL TASK: {state['task']}\n\n"
        f"PARTIAL RESULTS:\n{chunks_text}\n\n"
        f"Produce a unified, coherent final answer."
    )

    response = call_agent(synth["provider"], prompt, synth.get("system_prompt", ""))

    return {
        "synthesis": response,
        "result": response,
        "messages": [make_message(synth["role"], response, "synthesis")],
    }


def build_map_reduce_graph() -> StateGraph:
    builder = StateGraph(MapReduceState)

    builder.add_node("plan_chunks", plan_chunks)
    builder.add_node("process_chunks", process_chunks)
    builder.add_node("synthesize", synthesize)

    builder.add_edge(START, "plan_chunks")
    builder.add_edge("plan_chunks", "process_chunks")
    builder.add_edge("process_chunks", "synthesize")
    builder.add_edge("synthesize", END)

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.map_reduce import build_map_reduce_graph; g = build_map_reduce_graph(); print('map_reduce OK')"`
Expected: `map_reduce OK`

---

### Task 9: Implement Creator-Critic mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/creator_critic.py`

- [ ] **Step 1: Create creator_critic.py**

```python
"""Creator-Critic mode: iterative refinement loop."""

import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class CreatorCriticState(TypedDict):
    task: str
    agents: list[dict]          # [creator, critic]
    messages: Annotated[list[dict], operator.add]
    versions: list[str]
    critiques: list[str]
    iteration: int
    max_iterations: int
    approved: bool
    result: str


def creator_produces(state: CreatorCriticState) -> dict:
    """Creator produces or revises work."""
    creator = state["agents"][0]

    if state["iteration"] == 0:
        prompt = f"Complete this task:\n\n{state['task']}"
    else:
        last_critique = state["critiques"][-1] if state["critiques"] else ""
        last_version = state["versions"][-1] if state["versions"] else ""
        prompt = (
            f"Revise your work based on the critic's feedback.\n\n"
            f"ORIGINAL TASK: {state['task']}\n\n"
            f"YOUR PREVIOUS VERSION:\n{last_version}\n\n"
            f"CRITIC'S FEEDBACK:\n{last_critique}\n\n"
            f"Produce an improved version addressing all feedback."
        )

    response = call_agent(creator["provider"], prompt, creator.get("system_prompt", ""))

    return {
        "versions": [*state["versions"], response],
        "messages": [make_message(creator["role"], response, f"version_{state['iteration'] + 1}")],
    }


def critic_evaluates(state: CreatorCriticState) -> dict:
    """Critic evaluates the latest version."""
    critic = state["agents"][1]
    latest_version = state["versions"][-1]

    prompt = (
        f"Evaluate this work critically.\n\n"
        f"TASK: {state['task']}\n\n"
        f"WORK (version {state['iteration'] + 1}):\n{latest_version}\n\n"
        f"Rate: APPROVED (if good enough) or NEEDS_WORK (with specific feedback).\n"
        f"If NEEDS_WORK, list exactly what needs to change."
    )

    response = call_agent(critic["provider"], prompt, critic.get("system_prompt", ""))

    approved = "APPROVED" in response.upper() and "NEEDS_WORK" not in response.upper()

    return {
        "critiques": [*state["critiques"], response],
        "iteration": state["iteration"] + 1,
        "approved": approved,
        "result": latest_version if approved else "",
        "messages": [make_message(critic["role"], response, f"critique_{state['iteration'] + 1}")],
    }


def route_after_critique(state: CreatorCriticState) -> str:
    if state["approved"]:
        return END
    if state["iteration"] >= state["max_iterations"]:
        return "final_version"
    return "creator_produces"


def final_version(state: CreatorCriticState) -> dict:
    """Max iterations reached. Return last version."""
    return {
        "result": state["versions"][-1] if state["versions"] else "",
        "messages": [make_message("system", f"Max iterations ({state['max_iterations']}) reached. Returning last version.", "max_iterations")],
    }


def build_creator_critic_graph() -> StateGraph:
    builder = StateGraph(CreatorCriticState)

    builder.add_node("creator_produces", creator_produces)
    builder.add_node("critic_evaluates", critic_evaluates)
    builder.add_node("final_version", final_version)

    builder.add_edge(START, "creator_produces")
    builder.add_edge("creator_produces", "critic_evaluates")
    builder.add_conditional_edges("critic_evaluates", route_after_critique, {
        "creator_produces": "creator_produces",
        "final_version": "final_version",
        END: END,
    })
    builder.add_edge("final_version", END)

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.creator_critic import build_creator_critic_graph; g = build_creator_critic_graph(); print('creator_critic OK')"`
Expected: `creator_critic OK`

---

### Task 10: Implement Tournament mode

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/modes/tournament.py`

- [ ] **Step 1: Create tournament.py**

```python
"""Tournament mode: bracket-style competition with judge."""

import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from orchestrator.modes.base import call_agent, make_message


class TournamentState(TypedDict):
    task: str
    agents: list[dict]          # competitors + last one is judge
    messages: Annotated[list[dict], operator.add]
    submissions: list[dict]     # [{agent_id, solution}]
    bracket: list[list[dict]]   # rounds of matchups
    current_round: int
    winners: list[dict]         # current round winners
    champion: dict
    result: str


def all_compete(state: TournamentState) -> dict:
    """All competitors solve the task independently."""
    competitors = state["agents"][:-1]  # last is judge
    submissions = []
    messages = []

    for agent in competitors:
        response = call_agent(
            agent["provider"],
            f"Solve this task. Give your best answer.\n\n{state['task']}",
            agent.get("system_prompt", ""),
        )

        sub = {"agent_id": agent["role"], "provider": agent["provider"], "solution": response}
        submissions.append(sub)
        messages.append(make_message(agent["role"], response, "submission"))

    return {"submissions": submissions, "messages": messages}


def setup_bracket(state: TournamentState) -> dict:
    """Create first round matchups from submissions."""
    subs = list(state["submissions"])
    matchups = []

    # Pair up submissions
    while len(subs) >= 2:
        matchups.append({"a": subs.pop(0), "b": subs.pop(0)})

    # Odd one out gets a bye
    byes = subs  # 0 or 1 remaining

    bracket = [matchups]

    messages = [make_message("system",
        f"Tournament bracket: {len(matchups)} matches, {len(byes)} byes",
        "bracket_setup")]

    winners = [{"agent_id": b["agent_id"], "provider": b["provider"], "solution": b["solution"]} for b in byes]

    return {
        "bracket": bracket,
        "winners": winners,
        "current_round": 1,
        "messages": messages,
    }


def judge_matches(state: TournamentState) -> dict:
    """Judge evaluates current round matchups."""
    judge = state["agents"][-1]
    current_matchups = state["bracket"][-1]
    new_winners = list(state["winners"])
    messages = []

    for i, match in enumerate(current_matchups):
        prompt = (
            f"Judge this match (round {state['current_round']}, match {i + 1}).\n\n"
            f"TASK: {state['task']}\n\n"
            f"CONTESTANT A ({match['a']['agent_id']}):\n{match['a']['solution']}\n\n"
            f"CONTESTANT B ({match['b']['agent_id']}):\n{match['b']['solution']}\n\n"
            f"Which solution is better? Respond with JSON:\n"
            f'{{\"winner\": \"A\" or \"B\", \"reasoning\": \"why\"}}\n'
            f"Return ONLY valid JSON."
        )

        response = call_agent(judge["provider"], prompt, judge.get("system_prompt", ""))

        try:
            verdict = json.loads(response.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            verdict = {"winner": "A", "reasoning": response}

        winner_entry = match["a"] if verdict.get("winner", "A").upper() == "A" else match["b"]
        loser_entry = match["b"] if verdict.get("winner", "A").upper() == "A" else match["a"]

        new_winners.append(winner_entry)
        messages.append(make_message(judge["role"],
            f"Match {i+1}: {winner_entry['agent_id']} beats {loser_entry['agent_id']}. {verdict.get('reasoning', '')}",
            f"round_{state['current_round']}_match_{i+1}"))

    return {"winners": new_winners, "messages": messages}


def route_after_judging(state: TournamentState) -> str:
    if len(state["winners"]) <= 1:
        return "crown_champion"
    if len(state["winners"]) == 1:
        return "crown_champion"
    return "next_round"


def next_round(state: TournamentState) -> dict:
    """Set up next round from winners."""
    subs = list(state["winners"])
    matchups = []

    while len(subs) >= 2:
        matchups.append({"a": subs.pop(0), "b": subs.pop(0)})

    byes = subs
    new_bracket = [*state["bracket"], matchups]

    winners = [{"agent_id": b["agent_id"], "provider": b["provider"], "solution": b["solution"]} for b in byes]

    return {
        "bracket": new_bracket,
        "winners": winners,
        "current_round": state["current_round"] + 1,
        "messages": [make_message("system", f"Round {state['current_round'] + 1}: {len(matchups)} matches", "next_round")],
    }


def crown_champion(state: TournamentState) -> dict:
    """Declare the winner."""
    if state["winners"]:
        champ = state["winners"][0]
    elif state["submissions"]:
        champ = state["submissions"][0]
    else:
        champ = {"agent_id": "none", "solution": "No submissions"}

    return {
        "champion": champ,
        "result": f"Champion: {champ['agent_id']}\n\nSolution:\n{champ['solution']}",
        "messages": [make_message("system", f"Champion: {champ['agent_id']}", "champion")],
    }


def build_tournament_graph() -> StateGraph:
    builder = StateGraph(TournamentState)

    builder.add_node("all_compete", all_compete)
    builder.add_node("setup_bracket", setup_bracket)
    builder.add_node("judge_matches", judge_matches)
    builder.add_node("next_round", next_round)
    builder.add_node("crown_champion", crown_champion)

    builder.add_edge(START, "all_compete")
    builder.add_edge("all_compete", "setup_bracket")
    builder.add_edge("setup_bracket", "judge_matches")
    builder.add_conditional_edges("judge_matches", route_after_judging, {
        "next_round": "next_round",
        "crown_champion": "crown_champion",
    })
    builder.add_edge("next_round", "judge_matches")
    builder.add_edge("crown_champion", END)

    return builder.compile()
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.modes.tournament import build_tournament_graph; g = build_tournament_graph(); print('tournament OK')"`
Expected: `tournament OK`

---

### Task 11: Create engine.py (mode router)

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/engine.py`

- [ ] **Step 1: Create engine.py**

```python
"""Orchestration engine — routes tasks to the correct LangGraph mode."""

import asyncio
import time
import traceback

from orchestrator.models import store, AgentConfig
from orchestrator.modes.dictator import build_dictator_graph, DictatorState
from orchestrator.modes.democracy import build_democracy_graph, DemocracyState
from orchestrator.modes.debate import build_debate_graph, DebateState
from orchestrator.modes.board import build_board_graph, BoardState
from orchestrator.modes.map_reduce import build_map_reduce_graph, MapReduceState
from orchestrator.modes.creator_critic import build_creator_critic_graph, CreatorCriticState
from orchestrator.modes.tournament import build_tournament_graph, TournamentState


# Default agent configurations per mode
DEFAULT_AGENTS = {
    "dictator": [
        AgentConfig(role="director", provider="claude"),
        AgentConfig(role="worker_1", provider="codex"),
        AgentConfig(role="worker_2", provider="gemini"),
    ],
    "board": [
        AgentConfig(role="director_1", provider="claude"),
        AgentConfig(role="director_2", provider="codex"),
        AgentConfig(role="director_3", provider="gemini"),
    ],
    "democracy": [
        AgentConfig(role="voter_claude", provider="claude"),
        AgentConfig(role="voter_gemini", provider="gemini"),
        AgentConfig(role="voter_codex", provider="codex"),
    ],
    "debate": [
        AgentConfig(role="proponent", provider="claude"),
        AgentConfig(role="opponent", provider="codex"),
        AgentConfig(role="judge", provider="gemini"),
    ],
    "map_reduce": [
        AgentConfig(role="planner", provider="claude"),
        AgentConfig(role="worker_1", provider="codex"),
        AgentConfig(role="worker_2", provider="gemini"),
        AgentConfig(role="synthesizer", provider="claude"),
    ],
    "creator_critic": [
        AgentConfig(role="creator", provider="codex"),
        AgentConfig(role="critic", provider="claude"),
    ],
    "tournament": [
        AgentConfig(role="contestant_1", provider="claude"),
        AgentConfig(role="contestant_2", provider="codex"),
        AgentConfig(role="contestant_3", provider="gemini"),
        AgentConfig(role="contestant_4", provider="codex"),
        AgentConfig(role="judge", provider="claude"),
    ],
}


AVAILABLE_MODES = {
    "dictator": "One director delegates to workers, collects and synthesizes results",
    "board": "Council of 3 directors discuss and vote, then delegate to workers",
    "democracy": "All agents vote equally, majority wins, ties trigger re-vote",
    "debate": "Proponent vs opponent argue in rounds, judge decides winner",
    "map_reduce": "Split task into chunks, process in parallel, synthesize results",
    "creator_critic": "Creator produces work, critic reviews, iterate until approved",
    "tournament": "All agents compete, bracket elimination, judge picks champion",
}


def _build_initial_state(mode: str, task: str, agents: list[AgentConfig], config: dict) -> dict:
    """Build mode-specific initial state."""
    agents_dicts = [a.model_dump() for a in agents]

    base = {
        "task": task,
        "agents": agents_dicts,
        "messages": [],
        "result": "",
    }

    if mode == "dictator":
        return {**base, "subtasks": [], "worker_results": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3)}

    elif mode == "democracy":
        return {**base, "votes": [], "round": 0,
                "max_rounds": config.get("max_rounds", 3), "majority_position": ""}

    elif mode == "debate":
        return {**base, "rounds": [], "current_round": 0,
                "max_rounds": config.get("max_rounds", 3), "verdict": ""}

    elif mode == "board":
        return {**base, "positions": [], "vote_round": 0,
                "max_rounds": config.get("max_rounds", 3),
                "consensus_reached": False, "decision": "", "worker_results": []}

    elif mode == "map_reduce":
        return {**base, "chunks": [], "chunk_results": [], "synthesis": ""}

    elif mode == "creator_critic":
        return {**base, "versions": [], "critiques": [],
                "iteration": 0, "max_iterations": config.get("max_iterations", 3),
                "approved": False}

    elif mode == "tournament":
        return {**base, "submissions": [], "bracket": [],
                "current_round": 0, "winners": [], "champion": {}}

    raise ValueError(f"Unknown mode: {mode}")


def _build_graph(mode: str):
    """Build the LangGraph graph for a mode."""
    builders = {
        "dictator": build_dictator_graph,
        "democracy": build_democracy_graph,
        "debate": build_debate_graph,
        "board": build_board_graph,
        "map_reduce": build_map_reduce_graph,
        "creator_critic": build_creator_critic_graph,
        "tournament": build_tournament_graph,
    }

    builder = builders.get(mode)
    if not builder:
        raise ValueError(f"Unknown mode: {mode}")

    return builder()


async def run(mode: str, task: str, agents: list[AgentConfig] = None, config: dict = None) -> str:
    """
    Run an orchestration session. Returns session_id.

    The graph runs in a background task. Poll /orchestrate/session/{id} for results.
    """
    config = config or {}
    agents = agents or DEFAULT_AGENTS.get(mode, [])

    session_id = store.create(mode, task, agents, config)

    async def _execute():
        t0 = time.time()
        try:
            graph = _build_graph(mode)
            initial_state = _build_initial_state(mode, task, agents, config)
            final_state = graph.invoke(initial_state)

            store.update(session_id,
                status="completed",
                result=final_state.get("result", ""),
                elapsed_sec=round(time.time() - t0, 2),
            )
            store.append_messages(session_id, final_state.get("messages", []))

        except Exception as e:
            store.update(session_id,
                status="failed",
                result=f"Error: {type(e).__name__}: {e}\n{traceback.format_exc()}",
                elapsed_sec=round(time.time() - t0, 2),
            )

    asyncio.create_task(_execute())
    return session_id
```

- [ ] **Step 2: Verify import**

Run: `cd ~/multi-agent && python3 -c "from orchestrator.engine import run, AVAILABLE_MODES; print('engine OK, modes:', list(AVAILABLE_MODES.keys()))"`
Expected: `engine OK, modes: ['dictator', 'board', 'democracy', 'debate', 'map_reduce', 'creator_critic', 'tournament']`

---

### Task 12: Create API router and mount in gateway

**Files:**
- Create: `/Users/martin/multi-agent/orchestrator/api.py`
- Modify: `/Users/martin/multi-agent/gateway.py`

- [ ] **Step 1: Create api.py**

```python
"""FastAPI router for orchestration endpoints."""

from fastapi import APIRouter, HTTPException

from orchestrator.models import store, RunRequest, MessageRequest
from orchestrator.engine import run, AVAILABLE_MODES, DEFAULT_AGENTS

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])


@router.post("/run")
async def ep_run(req: RunRequest):
    if req.mode not in AVAILABLE_MODES:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(AVAILABLE_MODES.keys())}")

    session_id = await run(
        mode=req.mode,
        task=req.task,
        agents=req.agents if req.agents else None,
        config=req.config,
    )
    return {"session_id": session_id, "mode": req.mode, "status": "running"}


@router.get("/session/{session_id}")
async def ep_session(session_id: str):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.get("/sessions")
async def ep_sessions():
    return store.list_recent()


@router.post("/session/{session_id}/message")
async def ep_user_message(session_id: str, req: MessageRequest):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    if session["status"] != "running":
        raise HTTPException(400, f"Session is {session['status']}, cannot send messages")

    store.append_messages(session_id, [{
        "agent_id": "user",
        "content": req.content,
        "timestamp": __import__("time").time(),
        "phase": "user_intervention",
    }])
    return {"status": "message_sent"}


@router.get("/modes")
async def ep_modes():
    return {
        mode: {
            "description": desc,
            "default_agents": [a.model_dump() for a in DEFAULT_AGENTS.get(mode, [])],
        }
        for mode, desc in AVAILABLE_MODES.items()
    }


@router.get("/agents")
async def ep_agents():
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8800/pool")
            pool = resp.json()
    except Exception:
        pool = {}

    return {
        "providers": ["claude", "gemini", "codex", "minimax"],
        "pool_status": pool,
        "minimax": {"model": "minimax/minimax-m2.7", "via": "OpenRouter API"},
    }
```

- [ ] **Step 2: Mount router in gateway.py**

Add these two lines at the end of gateway.py, just BEFORE `if __name__ == "__main__":`:

```python
# Mount orchestrator
from orchestrator.api import router as orchestrate_router
app.include_router(orchestrate_router)
```

- [ ] **Step 3: Restart gateway and verify**

Run: Restart `python3 ~/multi-agent/gateway.py` in the gateway terminal, then:

```bash
curl -s http://localhost:8800/orchestrate/modes | python3 -m json.tool
```

Expected: JSON with all 7 modes and their descriptions.

---

### Task 13: Smoke test — run a real session

- [ ] **Step 1: Run a debate session**

```bash
curl -s -X POST http://localhost:8800/orchestrate/run \
  -H "Content-Type: application/json" \
  -d '{"mode": "debate", "task": "Is Python better than JavaScript for backend development?", "config": {"max_rounds": 2}}' \
  | python3 -m json.tool
```

Expected: `{"session_id": "sess_xxx", "mode": "debate", "status": "running"}`

- [ ] **Step 2: Poll for results (wait ~60 seconds)**

```bash
curl -s http://localhost:8800/orchestrate/session/SESSION_ID | python3 -m json.tool
```

Replace SESSION_ID with the actual ID from step 1.
Expected: status "completed", messages array with pro/con arguments and verdict.

- [ ] **Step 3: Test democracy mode**

```bash
curl -s -X POST http://localhost:8800/orchestrate/run \
  -H "Content-Type: application/json" \
  -d '{"mode": "democracy", "task": "What is the best database for a real-time analytics dashboard?"}' \
  | python3 -m json.tool
```

- [ ] **Step 4: Test dictator mode**

```bash
curl -s -X POST http://localhost:8800/orchestrate/run \
  -H "Content-Type: application/json" \
  -d '{"mode": "dictator", "task": "Analyze the pros and cons of microservices vs monolith for a startup"}' \
  | python3 -m json.tool
```

- [ ] **Step 5: Verify session list**

```bash
curl -s http://localhost:8800/orchestrate/sessions | python3 -m json.tool
```

Expected: list of all sessions with their statuses.
