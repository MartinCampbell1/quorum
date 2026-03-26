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

- External arbitrary `mcp_server` profiles are still `Claude native` only.
- `Gemini` and `Codex` now have a truthful bridge path for configured/custom tools, but not every external MCP server can be bridged safely.
- Tool-call-level event tracing (`tool_call_started` / `tool_call_finished`) is still not emitted from the runtime yet.

## Still not done

- Full screenshot regression automation / locked baselines
- True “any MCP server on any provider” parity
- Tool-call event streaming and deeper execution trace semantics
- A more explicit topology canvas for the session monitor right/center split
- Workspace preset editing UX beyond create/delete

## Notes for the next agent

- Do not assume `frontend/package.json`, `frontend/package-lock.json`, `.omc/`, or `.next/` belong to this pass. They were already dirty in the worktree.
- The highest-value next backend slice is provider-aware custom tool support beyond `Claude`.
- The highest-value next product slice is richer scenario-specific visualization and a checkpoint picker in the timeline.
