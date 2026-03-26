# Frontend Remediation Handoff

Branch: `codex/remediation-fixes`

## What changed

- Removed the render-time `setState` path in the wizard and switched mode bootstrap to `useEffect`.
- Stopped overriding backend mode descriptions in the mode cards; UI now displays the backend-provided text.
- Replaced the live chat input with a read-only notice because user interventions are not wired end-to-end yet.
- Removed the fake custom-tool creation flow from the agent step and replaced it with an explicit "not connected" note.
- Kept built-in tool metadata local in the frontend so `getTools()` no longer depends on a nonexistent backend route.

## Intentional behavior

- `addCustomTool`, `removeCustomTool`, and `sendMessage` now throw explicit unsupported errors instead of silently pretending the backend supports them.
- `getCustomTools()` returns an empty list.
- The UI only exposes built-in tools that are actually wired in the current build.

## Verification

- `npm run lint`
- `npx tsc --noEmit`
- `npx next build`

## Rollback

- To undo this pass, revert the frontend files listed above on this branch.
- Keep the unrelated local state files and `.next/` artifacts untouched unless you intentionally want to clean the workspace.
