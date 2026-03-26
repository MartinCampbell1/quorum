# Personal MVP Progress — 2026-03-26

Branch: `codex/personal-mvp-refine`

## What changed

- Validated the recent Settings/tools work and fixed the broken runtime contract between:
  - `frontend Settings/Wizard`
  - `orchestrator/api.py`
  - `orchestrator/models.py`
  - `gateway.py`
- Normalized tool ids so UI aliases like `code-exec` and `shell` resolve to canonical runtime ids:
  - `code_exec`
  - `shell_exec`
- Added dynamic validation for configured tool instances. A configured tool can now be selected in the UI and pass `/orchestrate/run` validation when the provider actually supports it.
- Added a real dynamic MCP bridge:
  - `mcp_servers/configured_tools_server.py`
  - Supports configured `Brave Search`, `Perplexity`, `HTTP API`, `Custom API`, `SSH`, and `Neo4j` tools
  - `gateway.py` now injects this MCP server per run when needed
- Added local persistence for Settings tools:
  - Saved outside the repo at `~/.multi-agent/tool_configs.json`
  - Prevents secrets/configs from being accidentally committed
- Fixed the Settings schema mismatch (`field.key` vs `field.name`) and added proper `select`/`textarea` rendering in the UI.
- Fixed frontend API typing for settings/tool payloads.
- Fixed local frontend/backend integration for dev/preview ports by expanding gateway CORS defaults used in this workflow.
- Added checkpoint-safe interactive control for orchestration runs:
  - LangGraph runs now execute one node per checkpoint using `MemorySaver` + `interrupt_after="*"`
  - backend supports `pause`, `resume`, `inject_instruction`, and `cancel`
  - queued instructions are injected into graph state at the next safe checkpoint
  - sessions now expose `current_checkpoint_id`, `checkpoints`, `pending_instructions`, and `active_node`
- Wired pause/resume UI into the chat view:
  - pause/cancel actions in the header
  - paused-state instruction composer in the bottom bar
  - session/history views now reflect paused and cancelling states
- Added regression coverage for interactive runtime control in `tests/test_interactive_runtime.py`
- Added live event timeline plumbing:
  - backend sessions now accumulate typed runtime events in the in-memory store
  - `GET /orchestrate/session/{id}/events` streams those events over SSE
  - frontend chat now renders a live timeline rail from `EventSource` without waiting for snapshot polling
  - event coverage includes session start/completion, checkpoints, user instructions, pause/resume/cancel, and agent messages

## UX pass

- Ran an external UX/UI review subagent on real screenshots.
- Rating progression:
  - initial first screen: `4/10`
  - after first pass: `6.5/10`
  - current first screen: `8.1/10`
- Implemented:
  - labeled left navigation
  - stronger first-run empty state in the sessions panel
  - clearer first-step copy
  - more decision-ready mode cards
  - less technical/noisy card content
  - denser desktop layout for easier comparison

## Validation

- `python3 -m py_compile gateway.py orchestrator/api.py orchestrator/models.py orchestrator/tool_configs.py mcp_servers/configured_tools_server.py`
- `python3 -m py_compile orchestrator/engine.py orchestrator/api.py orchestrator/models.py orchestrator/modes/*.py`
- `python3 -m pytest tests/test_api_contracts.py tests/test_modes.py tests/test_interactive_runtime.py -q`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`

All of the above passed during this pass.

## Important current limitation

- Configured/custom tools are now honest and executable for `Claude` runs through per-run MCP config.
- Configured/custom tools are **not** fully implemented yet for:
  - `Gemini`
  - `Codex`
- The current validation intentionally blocks unsupported configured tool/provider combinations instead of pretending they work.

## Still not done

- Restart from checkpoint / branch-from-checkpoint
- Full scenario layer on top of raw modes
- Real per-run MCP injection for `Gemini` and `Codex`
- True “any MCP server on any provider” support

## Notes for the next agent

- Do not assume `frontend/components/wizard/step-task.tsx`, `frontend/package.json`, `frontend/package-lock.json`, `.omc/`, or `.next/` belong to this pass. They were already dirty in the worktree.
- The highest-value next backend slice is provider-aware custom tool support beyond `Claude`.
- The highest-value next product slice is `restart from checkpoint` plus a scenario layer on top of the new runner.
