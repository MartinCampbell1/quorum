# Quorum Monitor UI Handoff

## Status

As of 2026-03-29, the broken monitor frontend experiment has been rolled back to the previous baseline for the main monitor files.

Frontend files restored to the pre-regression baseline:

- `/Users/martin/multi-agent/frontend/components/chat/chat-view.tsx`
- `/Users/martin/multi-agent/frontend/components/chat/input-bar.tsx`
- `/Users/martin/multi-agent/frontend/components/chat/event-timeline.tsx`
- `/Users/martin/multi-agent/frontend/lib/locale.tsx`

Important: backend/runtime logic was **not** rolled back.

Keep these changes:

- `/Users/martin/multi-agent/orchestrator/engine.py`
- `/Users/martin/multi-agent/orchestrator/api.py`
- `/Users/martin/multi-agent/tests/test_api_contracts.py`
- `/Users/martin/multi-agent/tests/test_interactive_runtime.py`
- `/Users/martin/multi-agent/frontend/lib/types.ts`

Those backend changes preserve the ability to continue discussion after completion by avoiding forks from terminal-only checkpoints and by exposing runtime-state reasons.

## Product Context

This UI is not a random chat screen. It is part of the broader FounderOS direction:

- `Quorum / FounderOS` is the research, debate, tournament, selection, and control-plane layer.
- `Autopilot` is the execution engine for PRD -> stories -> workers -> gates -> critic -> retries.
- The long-term direction is to converge them into a stronger `FounderOS / entrepreneur OS` style system:
  - Quorum handles thinking, debate, project selection, and strategic control.
  - Autopilot handles execution and shipping.
  - The monitor should therefore feel like an operator console, not a debug dump.

## What Went Wrong

The failed frontend pass broke the monitor UX in four ways:

1. It hid the topology canvas behind tabs instead of keeping it visible by default.
2. It weakened or effectively removed the right sidebar as a first-class part of the composition.
3. It turned the page into a giant text wall.
4. It allowed raw tool-calling payloads to dominate the primary reading flow.

The result no longer felt like a premium monitor/control-room UI. It felt like logs rendered as a page.

## What the User Actually Wants

The user does **not** want a big redesign that changes the nature of the page.

The user wants the older composition back, but refined:

- Keep the beautiful canvas at the top of the page.
- Keep the right sidebar with checkpoints, branches, connections, and actions.
- Keep the bottom composer flow close to how it used to behave.
- Remove noisy garbage from the primary reading flow.
- Separate clean final answer from logs/tool-calls.
- Keep logs available, but compressed and visually secondary.

The page should feel like a session monitor again.

## Baseline Layout to Preserve

Use the restored monitor layout as the baseline.

That means:

1. Header and task block at the top.
2. Topology canvas near the top of the main content.
3. Final answer below the canvas.
4. Conversation and execution trace below that.
5. Right rail always visible on desktop:
   - checkpoints / branches
   - active connections
   - action buttons
6. Continue discussion composer near the bottom in the natural page flow.

Do **not** hide the canvas behind tabs by default.

Do **not** remove the right rail from desktop layout.

## Required Improvements

### 1. Final Answer Must Be Clean

The final answer block must become a human-readable result card.

Requirements:

- No raw `<tool_call>`, `<tool_result>`, XML-ish wrappers, JSON payloads, or raw tool arguments in the visible final answer.
- If the final answer message contains both human prose and tool-call dump, render only the human prose.
- If only raw tool-calling content exists, show a compact fallback such as:
  - "No clean final answer was produced; open execution trace for raw runtime details."
- The final answer should be visually distinct from logs and conversation.

This is the most important content-cleaning requirement.

### 2. Last Instruction Status Must Stay, But Be Compact

We do want a small block answering:

- Did it answer my last instruction?

But this block must be compact and secondary.

Requirements:

- Show only:
  - answered / not answered
  - one short explanation
  - optional short preview of the last instruction
- Do **not** show the full long instruction by default.
- If full instruction text is shown, it must be truncated with explicit expand.

### 3. Execution Trace Must Behave Like Logs

Execution trace is a log view, not the main story.

Requirements:

- Strongly collapsed by default.
- Small vertical footprint.
- Can be expanded if the operator wants it.
- Raw tool payloads should stay behind item-level expansion where possible.
- It must not consume most of the page height.

### 4. Team Conversation Must Also Be De-Noised

The conversation panel should emphasize readable agent content.

Requirements:

- Human-readable agent reasoning is primary.
- Raw tool-calling noise must not dominate the panel.
- For completed sessions, default conversation should be compact.
- Keep access to raw runtime detail, but not as the default reading mode.

### 5. Composer Should Not Break the Viewport

The bottom continue-discussion block should stay near the bottom as part of the normal page flow.

Requirements:

- No sticky/fixed composer that steals viewport height.
- No giant composer card that visually outranks the canvas.
- It should remain usable, but visually secondary.

## Explicit Anti-Requirements

Do not do any of the following:

- Do not replace the canvas-first monitor with a text-first page.
- Do not make tabs the primary information architecture.
- Do not show raw tool-calling markup in the final answer block.
- Do not make execution logs dominate the page.
- Do not remove or visually demote the right sidebar on desktop.
- Do not ship without real browser validation.

## Files To Modify

Primary frontend files:

- `/Users/martin/multi-agent/frontend/components/chat/chat-view.tsx`
- `/Users/martin/multi-agent/frontend/components/chat/input-bar.tsx`
- `/Users/martin/multi-agent/frontend/components/chat/event-timeline.tsx`
- `/Users/martin/multi-agent/frontend/components/chat/topology-panel.tsx`
- `/Users/martin/multi-agent/frontend/lib/locale.tsx`

Potential support files if needed:

- `/Users/martin/multi-agent/frontend/components/chat/rich-text.tsx`
- `/Users/martin/multi-agent/frontend/lib/constants.ts`
- `/Users/martin/multi-agent/frontend/lib/types.ts`

Files that must be treated as preserved logic, not rollback targets:

- `/Users/martin/multi-agent/orchestrator/api.py`
- `/Users/martin/multi-agent/orchestrator/engine.py`
- `/Users/martin/multi-agent/tests/test_api_contracts.py`
- `/Users/martin/multi-agent/tests/test_interactive_runtime.py`

## Backend Logic Already Achieved

This logic is already working and must remain intact:

1. Completed sessions can continue discussion meaningfully.
2. Forking from terminal-only checkpoints now falls back to the latest resumable checkpoint.
3. Runtime state now reports when a session only has terminal checkpoints.

This work is already in backend/tests and should not be removed just because the frontend experiment failed.

## Acceptance Criteria

The work is acceptable only if all of the following are true:

1. The first screen looks like a premium session monitor again.
2. The topology canvas is visible without switching tabs.
3. The right rail is visible on desktop and feels intentional.
4. The final answer card contains clean human-readable text, not tool-call dump.
5. The "did it answer my last instruction" block is clear and compact.
6. Execution trace is visually secondary and collapsed by default.
7. Conversation does not flood the page with raw tool-call markup.
8. Continue discussion remains usable and does not damage layout.

## Required Validation

Before handoff, the next agent must validate in Chrome DevTools on the live UI.

Minimum validation checklist:

1. Open the problem session view on desktop width.
2. Check the first screen composition:
   - header
   - task
   - canvas
   - right rail
3. Scroll to final answer and verify it is clean.
4. Verify last-instruction status is compact.
5. Verify execution trace is collapsed and does not dominate the page.
6. Verify continue discussion block remains usable at the bottom.
7. Take screenshots before final signoff.

Do not claim success based only on code reading.

## Suggested Implementation Order

1. Keep the restored baseline layout.
2. Clean final-answer rendering.
3. Add compact last-instruction status.
4. Compress trace and conversation noise.
5. Validate visually in Chrome DevTools.

## Notes for the Next Agent

Do not reinterpret the request into a new UX concept.

The user already provided the direction:

- restore the old monitor feel
- keep canvas
- keep right rail
- keep composer in natural bottom flow
- clean final answer
- compress logs

The task is refinement, not reinvention.
