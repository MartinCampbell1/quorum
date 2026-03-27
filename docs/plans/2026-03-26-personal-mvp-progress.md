# Personal MVP Progress — 2026-03-26

Branch: `codex/personal-mvp-refine`

## What changed

- Replaced the in-memory session store with SQLite-backed persistence at `~/.multi-agent/state.db`.
  - runs, checkpoints, events, branch relationships, pending instruction counts, and workspace presets now survive backend restart
  - session payloads now include:
    - `workspace_preset_ids`
    - `workspace_paths`
    - `attached_tool_ids`
    - `provider_capabilities_snapshot`
    - `branch_children`
- Added a first-class provider/tool capability matrix:
  - capability levels are now `native`, `bridged`, `unavailable`
  - `/orchestrate/run` validation now accepts truthful bridged combinations instead of blanket-Claude-only rules
  - new backend endpoint: `GET /orchestrate/settings/providers/capabilities`
- Added workspace preset APIs:
  - `GET /orchestrate/settings/workspaces`
  - `POST /orchestrate/settings/workspaces`
  - `PUT /orchestrate/settings/workspaces/{id}`
  - `DELETE /orchestrate/settings/workspaces/{id}`
- Added tool profile validation:
  - new endpoint: `POST /orchestrate/settings/tools/{id}/validate`
  - stores `validation_status` and `last_validation_result` alongside the tool profile
  - validates:
    - `mcp_server` stdio/http handshakes using the MCP client library
    - `neo4j` connectivity
    - `ssh` local client availability
    - `http/custom_api` config sanity
- Extended the stable bridge runtime for `Gemini` and `Codex`:
  - `gateway.py` now distinguishes `native` vs `bridged` tools per provider
  - bridge payloads are written per run and injected through `CONFIGURED_TOOLS_PAYLOAD`
  - stable MCP bootstrap support was added for:
    - `search-server`
    - `exec-server`
    - `configured-tools`
  - `configured_tools_server.py` now supports bridge adapters for:
    - built-in `code_exec`
    - built-in `shell_exec`
    - built-in `http_request`
    - plus the existing configured search/API/SSH/Neo4j tools
    - plus bridged proxying for external `mcp_server` tool profiles
- Added workspace attachment to the actual CLI runtime:
  - `Claude` uses `--add-dir`
  - `Gemini` uses `--include-directories`
  - `Codex` uses `--add-dir`
  - workspace paths now travel from wizard -> API -> engine -> gateway -> provider CLI
- Updated the wizard and settings UI to match the new runtime contracts:
  - launch step now supports:
    - selecting saved workspace presets
    - adding one-off extra paths
  - agent tool chips now show `native` / `bridged` per provider
  - settings tool rows now show:
    - provider compatibility chips
    - validation action/status
    - last validation log/error summary
  - settings now has a dedicated `Workspace Presets` section
- Added historical checkpoint UI in the premium session monitor:
  - new checkpoint panel with:
    - checkpoint selection
    - branch creation from any historical checkpoint
    - parent/child branch ancestry
  - branch badges now appear in session list/header
- Replaced the generic monitor center panel with mode-aware views:
  - `board`
  - `democracy`
  - `debate`
  - `creator_critic`
  - `map_reduce`
  - a generic fallback remains for the other monitor states

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
- Added screenshot regression baselines for the three approved premium screens using Playwright with mocked API data:
  - mode selection
  - connect MCP server
  - session monitor
- Added richer runtime event coverage in the engine:
  - `vote_recorded`
  - `round_started`
  - `round_completed`
  - `chunk_completed`
  - current live monitor trace now reflects board/democracy/debate/map-reduce progress more explicitly instead of only checkpoints and messages
- Added bridge-observable tool-call tracing:
  - gateway now passes `session_id` and `agent_role` into provider requests
  - the configured-tools MCP bridge writes runtime `tool_call_started` / `tool_call_finished` events to a per-session event stream under `~/.multi-agent/runtime_events/`
  - the SQLite session store ingests those runtime event files lazily and merges them into the canonical event timeline
  - the premium monitor trace now renders tool-call rows with tool name, elapsed time, and failure state
- Added workspace preset editing in Settings:
  - workspace presets now support create, edit, cancel/reset, and delete from the same surface
  - deleting an actively edited preset resets the form cleanly
- Removed guessed tool labels from the premium monitor:
  - session payloads now include `attached_tools` with runtime-safe metadata
  - monitor/right-rail cards now use real tool name, transport, subtitle, icon, and capability from backend data instead of inferring from tool ids
- Upgraded mode-specific premium monitor panels to read real session events:
  - `board` and `democracy` now surface latest recorded positions/votes and round summaries from runtime events
  - `debate` now shows current round context and verdict detail from round events
  - `map_reduce` now shows chunk-completion activity directly in the worker lane
  - screenshot baseline for the premium session monitor was refreshed to match the richer center panel
- Added a denser session wiring canvas to the premium monitor:
  - the monitor now renders a shared `Session Task -> Agents -> MCP/Tool connections` graph above the mode-specific intelligence panel
  - the canvas shows real attached-tool cards with capability badges instead of generic placeholders
  - a small live-signal strip now surfaces active node, checkpoint, and latest tool activity inside the canvas
  - premium monitor screenshot baseline was refreshed again to match the new topology-first center layout
- Reintegrated the monitor into the main application shell:
  - session monitor no longer renders as a standalone premium demo screen detached from the rest of the app
  - the standard top header and left-side navigation now remain visible while monitoring a live run
  - the session list can now be collapsed from the left icon rail, closer to the ChatGPT/Gemini shell model
- Added `RU/EN` locale switching with Russian as the default:
  - introduced a frontend locale provider with persisted shell language preference
  - shell, monitor, checkpoints, trace, history, and paused-state control copy now switch between Russian and English
  - premium screenshot baselines were refreshed to match the new RU-first shell
- Tightened the session monitor geometry after UX review:
  - replaced the cramped vertical stack with a wider layered canvas: `task -> primary agent -> secondary agents`
  - pulled clipped right-side nodes back into the usable canvas area
  - removed the old standalone monitor header language (`Premium Session Monitor - White Edition`) entirely
- Reworked the premium monitor canvas into mode-aware communication diagrams:
  - `board` now renders as a real peer triangle instead of a boss-worker stack
  - `debate`, `creator_critic`, `map_reduce`, and default orchestration states now use distinct flow geometries
  - active communication edges now pulse with subtle directional signal markers during live runs
  - the monitor respects `prefers-reduced-motion`, so screenshot regression stays stable while the live UI still feels alive
- Upgraded the execution trace from a flat text log to a packet-style timeline:
  - timeline now merges runtime events with actual agent messages
  - tool-call rows now show a compact preview of the live query/request payload
  - recent agent exchanges render as structured cards instead of monospaced text spam
- Added a safer native path for `Codex` external MCP on `stdio`:
  - configured external `mcp_server` profiles with `transport=stdio` are now `native` for Codex
  - each Codex run gets an isolated temporary `CODEX_HOME`
  - existing persisted MCP registrations are stripped from the temporary config before the selected run-scoped servers are registered
  - `http`/`sse` external MCP for Codex remain bridged

## Validation

- `python3 -m py_compile gateway.py orchestrator/api.py orchestrator/models.py orchestrator/tool_configs.py mcp_servers/configured_tools_server.py`
- `python3 -m py_compile orchestrator/engine.py orchestrator/api.py orchestrator/models.py orchestrator/modes/*.py`
- `python3 -m py_compile orchestrator/engine.py orchestrator/api.py orchestrator/models.py orchestrator/scenarios.py orchestrator/modes/*.py`
- `python3 -m pytest tests/test_api_contracts.py tests/test_modes.py tests/test_interactive_runtime.py -q`
- `python3 -m pytest -q`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd frontend && npx next build --webpack`
- `cd frontend && npx playwright test e2e/premium-ui.spec.ts`
- `python3 -m py_compile orchestrator/models.py orchestrator/engine.py orchestrator/modes/base.py langchain_gateway.py gateway.py mcp_servers/configured_tools_server.py`
- `python3 -m pytest tests/test_interactive_runtime.py tests/test_api_contracts.py -q`
- `cd frontend && npx tsc --noEmit` (after `next build --webpack`, because `.next/types` are generated there in this setup)

All of the above passed during this pass.

Note:
- Plain `cd frontend && npm run build` can still fail in this sandbox when Turbopack tries to create an internal process/socket. The webpack build above passed and is the reliable validation method in this environment.

## Important current limitation

- External arbitrary `mcp_server` profiles are now:
  - `Claude`: native
  - `Gemini`: native
  - `Codex`: native for `stdio`, bridged for `http`/`sse`
- `Codex` still does not have native per-run arbitrary-header HTTP MCP parity here; the honest fallback for those transports remains the bridge path.

## Still not done

- A denser topology canvas/right rail closer to the approved premium monitor spacing
- Optional native external MCP path for `Codex` HTTP servers with bearer-token-only flows

## Notes for the next agent

- `frontend/package.json` and `frontend/package-lock.json` now intentionally belong to this pass because Playwright screenshot regression is part of the repo.
- `.omc/`, `.next/`, and `frontend/test-results/` are generated/local state and should not be committed.
- The highest-value next product slice is polishing the monitor toward an even closer pixel match with the approved mockups, especially spacing, micro-typography, and the right-side MCP/tool card density.
- `tsc --noEmit` depends on `.next/types`; run `npx next build --webpack` first in this repo before treating bare `tsc` failures as real regressions.
