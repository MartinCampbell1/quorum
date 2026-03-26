# Multi-Agent Orchestration Engine Design

## Overview

LangGraph-based orchestration engine with 7 modes, integrated into the existing
CLI gateway (localhost:8800). All agent communication goes through gateway
(Claude/Gemini/Codex via CLI subscriptions) + MiniMax via OpenRouter API.

## Models / Providers

| Provider | Accounts | Via | Best for |
|----------|----------|-----|----------|
| Claude | 1 | gateway CLI | Deep analysis, orchestration |
| Gemini | 2 (rotation) | gateway CLI | Large context, pattern matching |
| Codex/ChatGPT | 4 (rotation) | gateway CLI | Coding, review, synthesis |
| MiniMax m2.7 | API key | OpenRouter API | Summaries, formatting, light tasks |

## Data Models

### Agent
```python
class Agent(BaseModel):
    id: str                    # "claude-1", "gemini-1", "codex-2", "minimax"
    role: str                  # "director", "analyst", "critic", user-defined
    provider: str              # "claude" | "gemini" | "codex" | "minimax"
    system_prompt: str         # editable per-session
```

### Message
```python
class Message(BaseModel):
    agent_id: str              # who sent it
    content: str               # what was said
    timestamp: float
    phase: str                 # "planning", "voting", "round_2", "verdict"
    metadata: dict = {}        # mode-specific (vote value, match_id, etc.)
```

### Session
```python
class Session(BaseModel):
    id: str
    mode: str                  # "dictator" | "board" | "democracy" | "debate" |
                               # "map_reduce" | "creator_critic" | "tournament"
    task: str                  # user's task description
    agents: list[Agent]
    messages: list[Message]    # full conversation history (append-only)
    result: str | None         # final output
    status: str                # "running" | "completed" | "failed"
    config: dict               # mode-specific settings (max_rounds, etc.)
    created_at: float
    elapsed_sec: float | None
```

## Orchestration Modes

### 1. Dictator

One director agent controls everything. Workers execute subtasks.

```
START -> director (breaks task into subtasks)
      -> [worker_1, worker_2, worker_3] (parallel)
      -> director (evaluates results, decides: done or re-assign)
      -> END
```

State: `subtasks[]`, `worker_results[]`, `final_answer`
Router: director decides — enough data or send workers again (max 3 iterations).

### 2. Board (Council of Directors)

3 equal directors analyze, vote, then delegate to workers.

```
START -> [director_1, director_2, director_3] (parallel analysis)
      -> voting node (compare positions)
      -> consensus?
          YES -> delegate to workers -> END
          NO  -> another discussion round (max 3)
          STILL NO -> chairman (first in list) decides
```

State: `positions[]`, `vote_round`, `consensus_reached`

### 3. Democracy

All agents equal. Everyone votes. Tie-breaking via re-vote.

```
START -> ALL agents respond in parallel
      -> tally node (group similar positions)
      -> majority?
          YES -> accepted -> END
          NO (tie) -> agents see others' answers -> re-vote
          STILL NO -> MiniMax summarizes both positions,
                      system picks most-supported or returns both
```

State: `votes[]`, `round`, `majority_position`

### 4. Debate

Adversarial argumentation with a judge.

```
START -> moderator frames the thesis
      -> round 1: proponent argues FOR
      -> round 1: opponent argues AGAINST
      -> round 2: proponent rebuts
      -> round 2: opponent rebuts
      -> (up to N rounds, default 3)
      -> judge: verdict + reasoning
      -> END
```

State: `rounds[]`, `current_round`, `pro_args[]`, `con_args[]`, `verdict`
Router: judge can request "one more round" (up to max N).

### 5. Map-Reduce

Split task into chunks, process in parallel, synthesize.

```
START -> planner splits task into K chunks
      -> [chunk_1 -> agent_1]
         [chunk_2 -> agent_2] (parallel)
         [chunk_3 -> agent_3]
      -> synthesizer combines K results into one
      -> END
```

State: `chunks[]`, `chunk_results[]`, `synthesis`
Router: if a chunk fails -> retry with different agent (rotation).

### 6. Creator-Critic

Iterative refinement loop.

```
START -> creator produces v1
      -> critic evaluates (APPROVED | NEEDS_WORK + feedback)
      -> NEEDS_WORK? -> creator revises (sees feedback)
      -> critic evaluates v2
      -> (up to N iterations, default 3)
      -> APPROVED or max iterations -> END
```

State: `versions[]`, `critiques[]`, `iteration`, `approved`

### 7. Tournament

Bracket-style competition.

```
START -> all agents (4-8) solve task in parallel
      -> form pairs
      -> judge evaluates each pair -> picks winner
      -> winners -> next round
      -> final: 2 solutions -> judge picks champion
      -> END
```

State: `bracket[]`, `current_round`, `matchups[]`, `winners[]`, `champion`
Note: odd number of agents -> one gets a bye (auto-advances).

## Common Rules (All Modes)

- Session timeout: configurable (default 10 minutes)
- Max rounds/iterations: per-mode limit to prevent infinite loops
- All messages appended to `messages[]` for full transparency
- Rate limits: gateway handles rotation automatically
- MiniMax used for lightweight internal tasks (summarization, vote counting, formatting)
- Failed agent calls: retry with next account via gateway rotation

## API Endpoints

All mounted under `/orchestrate` prefix in gateway.py.

### POST /orchestrate/run
Start a new orchestration session.
```json
{
  "mode": "debate",
  "task": "Should we use Redis or Memcached for caching?",
  "agents": [
    {"role": "proponent", "provider": "claude"},
    {"role": "opponent", "provider": "codex"},
    {"role": "judge", "provider": "gemini"}
  ],
  "config": {"max_rounds": 3}
}
```
Returns: `{"session_id": "sess_xxx"}` immediately. Graph runs in background.

### GET /orchestrate/session/{id}
Poll session status.
Returns: full Session object with messages[] and result.

### GET /orchestrate/sessions
List recent sessions (last 50).

### POST /orchestrate/session/{id}/message
User intervention during execution.
```json
{"content": "Focus on latency, not throughput"}
```
Injected as a user message into the graph state. Director/moderator sees it.

### GET /orchestrate/modes
List available modes with descriptions and agent slot schemas.

### GET /orchestrate/agents
Available providers with current pool status (from gateway /pool).

### PUT /orchestrate/agents/{id}/prompt
Update system prompt for an agent role.

## SMG Integration

Existing SMG multi-agent system (~/Desktop/multi-agent-system) migrates:

1. Replace `ChatVertexAI` imports with `GatewayClaude/Gemini/Codex`
2. `scheduler.py` calls `engine.run(mode="dictator", ...)` instead of raw graph
3. `tools.py`, `agents.py`, `verifier.py` unchanged
4. Remove Vertex AI / OpenRouter API key dependencies

## File Structure

```
~/multi-agent/
  gateway.py                    # existing, add orchestrator router mount
  langchain_gateway.py          # existing, add GatewayMiniMax class
  graph_recipes.py              # existing, unchanged
  safety_layer.py               # existing, unchanged
  mcp_server.py                 # existing, unchanged
  requirements.txt              # update with new deps

  orchestrator/
    __init__.py
    engine.py                   # run(mode, task, agents, config) -> session_id
    models.py                   # Session, Agent, Message, configs
    api.py                      # FastAPI router
    modes/
      __init__.py
      base.py                   # BaseMode interface
      dictator.py               # LangGraph graph
      board.py
      democracy.py
      debate.py
      map_reduce.py
      creator_critic.py
      tournament.py
```

## Dependencies

Already installed: langchain-core, langgraph, fastapi, uvicorn, httpx
Need to install: openai (for MiniMax via OpenRouter)

## MiniMax Integration

MiniMax does NOT go through CLI gateway. It uses OpenRouter API directly
via OpenAI-compatible endpoint.

```
API key: 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
Model: minimax/minimax-m2.7
Base URL: https://openrouter.ai/api/v1
```

Implemented as `GatewayMiniMax` in langchain_gateway.py using ChatOpenAI
with custom base_url pointing to OpenRouter.
