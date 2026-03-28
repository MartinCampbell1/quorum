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
- Refactored the canvas again after visual review to reduce the "spider web" effect:
  - `board` and `democracy` no longer draw peer-to-peer line meshes
  - both now route through a shared hub node (`Совет` / `Голосование`) so the topology reads as a clean structured system instead of random crossing curves
  - the under-canvas area now prioritizes `Живой обмен`, showing the latest packet/message handoff directly below the diagram
  - the old oversized signal cards were compressed into smaller status pills so the live exchange stays visible on first screen
  - this is a better handoff baseline, but the board canvas still needs one more dedicated geometry pass for near-pixel-match quality
- Upgraded the execution trace from a flat text log to a packet-style timeline:
  - timeline now merges runtime events with actual agent messages
  - tool-call rows now show a compact preview of the live query/request payload
  - recent agent exchanges render as structured cards instead of monospaced text spam
- Added a safer native path for `Codex` external MCP on `stdio`:
  - configured external `mcp_server` profiles with `transport=stdio` are now `native` for Codex
  - each Codex run gets an isolated temporary `CODEX_HOME`
  - existing persisted MCP registrations are stripped from the temporary config before the selected run-scoped servers are registered
  - `http`/`sse` external MCP for Codex remain bridged
- Added safer runtime truthfulness and memory bounds for session control:
  - session payloads and session-list cards now expose `runtime_state` flags (`live_runtime_available`, `checkpoint_runtime_available`, control booleans)
  - paused/cancel/instruction control paths now return honest `409` errors when in-memory runtime state is gone instead of generic status failures
  - in-memory checkpoint savers are now capped (`MULTI_AGENT_MAX_CHECKPOINT_RUNTIMES`, default `16`) so completed runs do not accumulate unlimited branch state in RAM
- Closed two backend temp-file / event-ingestion gaps:
  - `Claude` native MCP runs now clean up both the top-level temporary `mcp_*.json` and the nested `configured_tools_*.json` payload files created for configured native tools
  - runtime bridge tool events are now ingested eagerly after each completed graph node, so the canonical session timeline is updated without waiting for a later session/events API read
- Closed an isolated-`Codex` bootstrap cache leak:
  - `BOOTSTRAPPED_MCP_SERVERS` entries tied to per-run temporary `CODEX_HOME` values are now cleared when that isolated home is replaced or deleted
  - this keeps long-lived backend processes from accumulating stale native-MCP bootstrap cache entries across many Codex runs

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
- `python3 -m py_compile gateway.py orchestrator/api.py orchestrator/engine.py orchestrator/models.py`
- `python3 -m pytest tests/test_api_contracts.py tests/test_gateway_mcp_registration.py tests/test_runtime_recovery.py -q`
- `python3 -m py_compile orchestrator/models.py orchestrator/engine.py gateway.py`
- `python3 -m pytest tests/test_interactive_runtime.py tests/test_gateway_mcp_registration.py tests/test_api_contracts.py tests/test_runtime_recovery.py -q`
- `python3 -m py_compile gateway.py`
- `python3 -m pytest tests/test_gateway_mcp_registration.py tests/test_interactive_runtime.py tests/test_api_contracts.py tests/test_runtime_recovery.py -q`
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
- Checkpoint branching is intentionally limited to in-memory checkpoint state:
  - after backend restart, or after a run ages out of the bounded checkpoint-runtime cache, `restart_from_checkpoint` becomes unavailable for that session
  - the API now reports this explicitly via `runtime_state.checkpoint_runtime_available`

## Canvas routing — NEEDS POLISH (2026-03-27)

All 7 orchestration modes now have dedicated canvas layouts with beam animation, arrowheads, and dynamic scaling:

- **Board**: hub "Совет" left-center, agents fan outward right (up to 8 agents)
- **Democracy**: agents fan LEFT, hub "Голосование" RIGHT (reversed from board for visual distinction)
- **Debate**: central arena hub, judge above, proponent/opponent below with VS edge
- **Creator/Critic**: cycle loop — creator ↔ hub "Редакционный цикл" ↔ critic (4 edges forming loop)
- **Map/Reduce**: horizontal pipeline — planner left → workers fan center → synthesizer far right (up to 6 workers)
- **Dictator**: vertical tree — leader top-center → N workers in a row below (up to 8 workers)
- **Tournament**: bracket layout — agent pairs stacked left → hub "Турнир" right (up to 4 pairs)
- **Default/Generic**: primary orchestrator → N secondary agents in fan (up to 6)

Key implementation details:
- `buildCanvasGraph()` uses `fanPositions()`, `rowPositions()`, and `autoEdge()` for dynamic layout
- SVG beam animation: flowing dash (`stroke-dasharray` + `animate`), leading particle with glow filter, trailing particle
- Arrowhead markers (8px, `#94a3b8`) on all non-animated paths for directionality in static/reducedMotion
- Hub nodes styled with gradient border + `border-2` to distinguish from agent nodes
- Compact task node (44px entry badge with ArrowRight icon) — no canvas collision
- Agent role subtitle at 14px `#475569` for legibility
- `DictatorView` and `TournamentView` components added with RU/EN locale strings
- E2E test suite `e2e/canvas-modes.spec.ts` covers all 7 modes with screenshot baselines
- UX review score: **7.125/10 average** (debate scored 8/10)

Validation:
- `cd frontend && npx next build --webpack` — passed
- `cd frontend && npx tsc --noEmit` — passed (after build generates `.next/types`)
- `cd frontend && npx playwright test e2e/canvas-modes.spec.ts e2e/premium-ui.spec.ts` — 10/10 passed

## Still not done

- ~~Final geometry polish for the premium monitor canvas~~ — DONE (see above)
- A denser topology canvas/right rail closer to the approved premium monitor spacing
- Optional native external MCP path for `Codex` HTTP servers with bearer-token-only flows
- A richer packet inspector below the canvas:
  - the latest live exchange is already visible
  - a fuller per-hop payload viewer for JSON/Cypher/tool packets is still not implemented
- Canvas beam animation is beautiful live but not visible in reducedMotion screenshots — live preview at `http://localhost:3737` with backend running shows the flowing beams

## Notes for the next agent

- `frontend/package.json` and `frontend/package-lock.json` now intentionally belong to this pass because Playwright screenshot regression is part of the repo.
- `.omc/`, `.next/`, and `frontend/test-results/` are generated/local state and should not be committed.
- The highest-value next product slice is polishing the monitor right-rail spacing and building the richer packet inspector.
- Canvas routing infrastructure is in place (7 modes, beam animation, dynamic helpers) but the LIVE result has quality issues. See "Canvas routing issues" below.

## Canvas routing issues — MUST FIX

The canvas passed Playwright screenshot tests with mock data but has visible problems with real session data:

1. **Nodes escape canvas bounds**: Fan-positioned agents can clip outside the `h-[326px]` canvas area. The `fanPositions()` Y-clamping was added but needs verification with real data (4+ agents in board/democracy/default). The viewBox is `0 0 760 364` — all node centers must stay within y: 60..300 to prevent label clipping.

2. **Not truly scalable**: With 5+ agents, nodes crowd together and labels overlap. The fan radius (210) and spread angle need to adapt better to agent count. Test with 1, 2, 3, 5, and 8 agents in each mode.

3. **Labels clip and overlap**: Agent role subtitles (14px) can extend beyond the canvas container. The bottom agent (e.g., Codex at y≈590 in the old version) overlaps with the "Живой обмен" section below.

4. **Edge routing not clean enough**: The `autoEdge()` S-curve function produces acceptable curves for horizontal/vertical paths but diagonal paths can look awkward. Real sessions with hub at x=220 and agents at varying y positions show uneven curve shapes.

## CRITICAL: Site may be broken after this session

The previous agent's curl requests to localhost:3737 caused the frontend dev server to hang/crash. The next agent MUST:
1. Kill any hanging node/next processes: `lsof -ti:3737 | xargs kill -9` then restart `cd frontend && npm run dev`
2. Verify both backend (port 8800) and frontend (port 3737) respond before doing anything else
3. If the site still doesn't load, check `git stash` or `git diff` for broken changes and revert if needed

**What the next agent must do (canvas):**
- Open the live app with real backend sessions (not just Playwright mocks)
- Visually verify ALL 7 modes with the actual agent counts from real sessions
- Fix any remaining overflow: ensure NO node or label extends outside the canvas container
- Test scaling: create mock sessions with 1, 2, 3, 5, 8 agents and verify the layout adapts gracefully
- The "Живой обмен" block MUST NOT be overlapped by canvas nodes — it sits directly below the SVG area
- Key file: `frontend/components/chat/topology-panel.tsx` — functions `fanPositions()`, `rowPositions()`, `autoEdge()`, and per-mode layout code in `buildCanvasGraph()`
- `tsc --noEmit` depends on `.next/types`; run `npx next build --webpack` first in this repo before treating bare `tsc` failures as real regressions.
- Key files changed in canvas pass:
  - `frontend/components/chat/topology-panel.tsx` — canvas layouts, beam animation, DictatorView, TournamentView
  - `frontend/lib/locale.tsx` — added dictator/tournament locale strings (RU + EN)
  - `frontend/e2e/canvas-modes.spec.ts` — E2E test for all 7 canvas modes
  - `frontend/e2e/canvas-modes.spec.ts-snapshots/` — screenshot baselines

## Gray background cosmetic fix — DONE (2026-03-27)

Removed all gray/muted background fills from wizard and settings forms to match the white premium design language:

- `frontend/components/wizard/step-task.tsx` — replaced `bg-muted/20` with `bg-white` on textarea, rounds/iterations, workspace, and summary sections
- `frontend/components/wizard/step-agents.tsx` — replaced `bg-muted/30` with `bg-white` on system prompt textarea and add-worker button
- `frontend/components/wizard/custom-tool-form.tsx` — replaced `bg-muted/30` with `bg-white` on all form inputs
- `frontend/components/settings-view.tsx`:
  - Tool Registry section: `bg-[#f8f9fc]` → `bg-white`
  - INPUT_CLASS: `bg-white/85 shadow-inner` → `bg-white` (no shadow-inner)
  - Prompt template pre blocks: `bg-muted/30` → `bg-[#fafbfc] border border-[#e6e8ee]`
  - Tool validation log: `bg-[#f6f7fa]` → `bg-[#fafbfc]`
  - Active tool row: `bg-[#f3f4f7]` → `bg-[#f8f9fb]`

Also fixed canvas overflow where fan-positioned nodes escaped the viewBox:
- Reduced fan radius from 280 to 210 for board/democracy/map_reduce/default
- Added Y-clamping in `fanPositions()` to keep nodes within safe zone (y: 46..318)
