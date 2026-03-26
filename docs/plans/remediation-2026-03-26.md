# Remediation Handoff — 2026-03-26

Branch: `codex/remediation-fixes`
Base rollback point: `350c639`

## Scope

This pass focuses on the unresolved review findings after `350c639`:

- P0: invalid mode topologies, dead message endpoint, broken tools API contract, gateway exposure defaults, MCP scoping gaps
- P1: hidden arbitrator semantics in `board`/`democracy`, serial `map_reduce` mismatch, raw tool-log leakage
- P2: frontend honesty/cleanup, hardcoded project path, dead router wiring, tests

## Coordination

- This branch is isolated from the current mainline state for easy rollback.
- Changes in this pass should stay surgical and avoid unrelated UI work.
- If another agent needs to inspect what changed, use this file plus `git log --oneline --decorate`.
- Mode-semantics changes were landed first as `02c96b6` to keep that slice independently revertible.

## Completed changes

- P0 backend contract:
  - Added topology/provider/tool validation at the `/orchestrate/run` boundary.
  - Marked live user messages as unsupported instead of pretending they reach a running graph.
  - Restored honest tools endpoints for the built-in catalog and explicit `501` responses for custom tools.
  - Tightened gateway defaults to localhost-only host/CORS and added stricter MCP flags where supported.
- P1 behavior and logging:
  - Removed hidden `minimax` arbitration from `board` and `democracy`.
  - Made `map_reduce` actually process chunks concurrently.
  - Redacted raw tool arguments and results before writing `.tool_logs`.
- P2 cleanup:
  - Removed the hardcoded machine path from `orchestrator/modes/base.py`.
  - Wired the tool-visibility router into runtime selection, with safe fallback when no router key is present.
  - Frontend now reflects backend reality: no fake custom-tool flow and no fake live-message input.
  - Added regression tests for mode semantics and API boundary behavior.

## Verification

- `python3 -m py_compile gateway.py orchestrator/api.py orchestrator/models.py orchestrator/engine.py orchestrator/modes/base.py orchestrator/modes/board.py orchestrator/modes/democracy.py orchestrator/modes/map_reduce.py orchestrator/tools/router.py mcp_servers/exec_server.py mcp_servers/search_server.py mcp_servers/logging_utils.py tests/test_api_contracts.py tests/test_modes.py`
- `python3 -m pytest tests/test_api_contracts.py tests/test_modes.py -q`
- `npm --prefix frontend run lint`
- `cd frontend && npx tsc --noEmit`
- `npm --prefix frontend run build`

## Rollback

- Full branch rollback: switch away from `codex/remediation-fixes` back to the base branch at `350c639`.
- Partial rollback on this branch:
  - `git revert 02c96b6` reverts the mode-semantics slice only.
  - `git revert 4662a34` reverts the backend/frontend contract and cleanup slice.

## Status

- [x] P0 backend contract fixes
- [x] P1 mode semantics fixes
- [x] P2 cleanup fixes
- [x] Tests and verification
- [x] Final remediation commit (`4662a34`)
