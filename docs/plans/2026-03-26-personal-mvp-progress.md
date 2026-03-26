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
- Added a user-facing scenario layer on top of raw modes:
  - backend exposes `GET /orchestrate/scenarios`
  - wizard now starts from personal-ready scenarios instead of raw orchestration terms
  - current shipped presets: `Repo Audit`, `Pattern Mining`, `News + Context`, `Strategy Review`
- Added checkpoint branching for paused/finished sessions:
  - backend supports `restart_from_checkpoint`
  - a paused session can now fork into a new branch with an optional instruction
  - branch sessions preserve `forked_from` and `forked_checkpoint_id`
  - the paused-state composer can spawn a new run and automatically switch the UI to it

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
- Added a 21st.dev-inspired control-center pass:
  - validated the local `magic21st` MCP server connection and tool catalog
  - used the 21st.dev MCP flow as a design reference source for dashboard/sidebar composition
  - aligned the chat header, message cards, paused-state composer, and settings forms with the same premium dashboard language as the scenario shell
  - latest UI commit for this pass: `d9ddd9f`
- Added a second approved-design pass based on the white premium reference set and `DESIGN.md`:
  - shifted the shell toward the approved `Precision Blueprint` language: lighter surfaces, toned borders, editorial spacing
  - restyled the left rail, sessions column, top app bar, scenario grid, and execution trace toward the approved white minimal layout
  - upgraded `MCP Server` settings to support both `stdio` and `http` transports in the model and gateway runtime
  - MCP forms now expose transport-aware fields and a clean handshake log panel matching the approved reference

## Validation

- `python3 -m py_compile gateway.py orchestrator/api.py orchestrator/models.py orchestrator/tool_configs.py mcp_servers/configured_tools_server.py`
- `python3 -m py_compile orchestrator/engine.py orchestrator/api.py orchestrator/models.py orchestrator/modes/*.py`
- `python3 -m py_compile orchestrator/engine.py orchestrator/api.py orchestrator/models.py orchestrator/scenarios.py orchestrator/modes/*.py`
- `python3 -m pytest tests/test_api_contracts.py tests/test_modes.py tests/test_interactive_runtime.py -q`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd frontend && npx next build --webpack`

All of the above passed during this pass.

Note:
- Plain `cd frontend && npm run build` can still fail in this sandbox when Turbopack tries to create an internal process/socket. The webpack build above passed and is the reliable validation method in this environment.

## Important current limitation

- Configured/custom tools are now honest and executable for `Claude` runs through per-run MCP config.
- Configured/custom tools are **not** fully implemented yet for:
  - `Gemini`
  - `Codex`
- The current validation intentionally blocks unsupported configured tool/provider combinations instead of pretending they work.

## Still not done

- Real per-run MCP injection for `Gemini` and `Codex`
- True “any MCP server on any provider” support
- Choosing an arbitrary historical checkpoint from the UI (backend supports checkpoint branching, current UI forks the active checkpoint)
- Rich mode-specific visualizations beyond the general timeline rail
- True session-topology visualization like the approved premium monitor reference (the current session screen is stylistically aligned, but it does not yet render a real topology graph)

## Notes for the next agent

- Do not assume `frontend/package.json`, `frontend/package-lock.json`, `.omc/`, or `.next/` belong to this pass. They were already dirty in the worktree.
- The highest-value next backend slice is provider-aware custom tool support beyond `Claude`.
- The highest-value next product slice is richer scenario-specific visualization and a checkpoint picker in the timeline.
