# Autopilot — Priority Roadmap From Deep Competitive Analysis

Snapshot date: `2026-03-31`

Related docs:

- [2026-03-31-engineering-backlog.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-engineering-backlog.md)
- [CURRENT_STATUS.md](/Users/martin/Desktop/Projects/FounderOS/docs/CURRENT_STATUS.md)
- [SYSTEM_ARCHITECTURE.md](/Users/martin/Desktop/Projects/FounderOS/docs/SYSTEM_ARCHITECTURE.md)
- [autopilot-design.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/autopilot-design.md)
- [phase3-founderos-execution-plane.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/phase3-founderos-execution-plane.md)
- [execution-brief-bridge.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/execution-brief-bridge.md)
- [2026-03-31-founderos-implementation-plan-from-github-research.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-implementation-plan-from-github-research.md)
- [2026-03-31-founderos-detailed-feature-borrowing-map.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-detailed-feature-borrowing-map.md)

## Purpose

This is the `Autopilot`-specific answer to the question:

`from the deep competitive scans, what must actually be added to our plan, what is already present, and what should wait?`

This file is intentionally narrower than the FounderOS-wide docs.
It focuses on the execution/control plane only.

## Baseline: What Autopilot Already Has

These items are already present in meaningful form and should not be re-listed as missing core gaps:

- multi-account provider pool and provider rotation
- escalation chain across providers
- worker -> gates -> critic loop
- typed `ExecutionBrief` ingest and FounderOS-facing execution-plane API
- budget policy + budget usage + auto-pause
- approvals, issues, action runs, orchestrator sessions, control passes
- typed adapter foundation for provider families
- AGENTS.md/project bootstrap behavior
- project/runtime agent exports for FounderOS control-plane UI
- idempotent replay for execution-plane action runs and control-pass reporting

Primary grounding:

- [CURRENT_STATUS.md](/Users/martin/Desktop/Projects/FounderOS/docs/CURRENT_STATUS.md)
- [phase3-founderos-execution-plane.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/phase3-founderos-execution-plane.md)
- [execution_plane.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/execution_plane.py)
- [runtime_budgets.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/runtime_budgets.py)
- [adapters.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/adapters.py)

## The Main Gap Framing

The strongest competitor memo items do **not** say "rewrite Autopilot."

They say Autopilot still needs to finish the production loop around its already-strong runtime:

1. observe cost and behavior
2. accept external feedback from GitHub/CI/review systems
3. run cleanly in headless/server mode
4. support dependency-aware parallel execution
5. become minimally extensible for OSS users

That is the real plan.

## Design Laws Confirmed by the Scans

These are not backlog items. They are constraints the scans reinforced.

### Keep orchestration deterministic

The strongest evidence still supports:

- explicit orchestration state
- explicit gates
- explicit policies
- explicit retries/escalation

over LLM-driven orchestration logic.

### Keep fresh context per task

This is already aligned with the Ralph-style loop in [autopilot-design.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/autopilot-design.md).
Do not regress toward giant persistent conversational context.

### Keep account rotation as core identity

The broader scan validated this as real market need.
It should remain a defining Autopilot differentiator, not a side feature.

## Add To Plan: Mandatory

These should be treated as `must add`, not as optional polish.

### P0. Cost and token accounting

#### Why this is mandatory

Autopilot already has iteration budgets, but not true spend observability.
For overnight runs and open-source credibility, "budget policy" is not enough.
Users need:

- provider/account/model usage
- token counts where available
- estimated cost
- per-run / per-story / per-project rollups

#### Best donors

- `Conclave`
- `Bernstein`
- `tokscale`
- `Helicone` for pricing/reference thinking

#### What to borrow

- command shape like `cost`
- session/run-level breakdowns
- price-table abstraction rather than hardcoded math
- simple accounting-first implementation before any proxy complexity

#### Do not do yet

- full transparent proxy as the first implementation

#### Target files

- [runtime_budgets.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/runtime_budgets.py)
- [execution_plane.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/execution_plane.py)
- [run.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/run.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/cost_accounting.py`

### P0. Structured trace and forensic replay

#### Why this is mandatory

Autopilot already records action runs and session/control-pass history, but it does **not** yet expose a real worker-loop trace that answers:

- what prompt was sent
- what provider/account handled it
- what diff changed
- which gate failed
- what critic said
- why escalation happened

Without this, debugging failed overnight runs remains too opaque.

#### Best donors

- `Bernstein`
- `OpenHands`
- `Trigger.dev`

#### What to borrow

- `trace <story|run>` viewing model
- replay as forensic playback first, deterministic rerun later
- structured event journal instead of free-form logs

#### Important distinction

Current execution-plane idempotent replay is useful, but it is **not** the same as worker-run trace/replay.

#### Target files

- [loop_runner.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/loop_runner.py)
- [critic.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/critic.py)
- [execution_plane.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/execution_plane.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/run_trace.py`
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/trace.py`

### P0. GitHub PR integration and reaction bus

#### Why this is mandatory

This is the biggest real competitive gap.
Autopilot is already a serious execution plane internally, but it still under-connects to the external software delivery loop.

Needed first:

- story -> branch -> PR
- CI failed -> route logs back to owning worker
- review comments / changes requested -> route back to critic/worker
- approved and green -> advance/close automatically where policy allows

#### Best donors

- `Agent Orchestrator`
- `Open SWE`
- `OpenHands`
- `Symphony`

#### What to borrow

- explicit event taxonomy
- issue/PR/review comment routing model
- conservative auto-fix / auto-resume policy

#### Target files

- [execution_plane.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/execution_plane.py)
- [execution_plane.py routes](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/api/routes/execution_plane.py)
- [control_plane_issues.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/control_plane_issues.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/github_reactions.py`
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/github_prs.py`

### P0. Headless / non-interactive mode

#### Why this is mandatory

Autopilot should run as a server-grade tool, not just as an attended terminal workflow.
This is needed for:

- CI
- cron
- remote boxes
- cloud workers later
- operator bridges

#### Best donors

- `Conclave`
- `Bernstein`

#### What to borrow

- explicit `--headless`
- JSON result surface
- meaningful exit codes
- no-TTY safe behavior

#### Target files

- [run.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/run.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/headless.py`

### P0. `autopilot doctor`

#### Why this is mandatory

For OSS adoption this is disproportionately important.
People will fail on:

- missing auth profiles
- broken git config
- stale locks
- missing binaries
- invalid runtime homes
- disk pressure

#### Best donors

- `Agent Orchestrator`
- `Bernstein`

#### What to borrow

- environment diagnostics
- actionable fix suggestions
- optional `--fix` only for safe cases later

#### Target files

- [provider_sessions.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/provider_sessions.py)
- [adapters.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/adapters.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/doctor.py`

### P0. Story dependencies and auto-unblock

#### Why this is mandatory

This is already described in the design notes, but not implemented as a real runtime data model.
It gives Autopilot much better parallelism without increasing chaos.

Needed:

- `blocked_by` on stories
- dispatcher skips blocked stories
- completion unblocks downstream stories automatically
- stuck story can escalate without freezing unrelated work

#### Best donors

- `ClawTeam`
- your own existing design note in [autopilot-design.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/autopilot-design.md)

#### Target files

- [execution-brief-bridge.md](/Users/martin/Desktop/Projects/FounderOS/autopilot/docs/execution-brief-bridge.md)
- [loop_runner.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/loop_runner.py)
- [execution_plane.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/execution_plane.py)

## Add To Plan: Strong P1

These are not as mandatory as P0, but they are the right next layer.

### P1. Minimal provider/plugin interface

Do this, but smaller than the 8-slot `Agent Orchestrator` design.

Start with:

- `AgentProvider`
- `Runtime`
- `Tracker`
- `Notifier`

Reason:

- current adapter layer is useful but still too hardcoded to the current provider families
- OSS users will want `aider`, `opencode`, `pi`, future CLI agents

Target files:

- [adapters.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/adapters.py)
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/plugins.py`

### P1. Multi-agent pipeline per story

Add a configurable phase pipeline:

- research
- implement
- review

This is better than sending one worker to do everything, but it should land **after** trace/cost/headless.

Best donors:

- `agtx`
- `MassGen`

Target files:

- [loop_runner.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/loop_runner.py)
- [critic.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/critic.py)

### P1. Configurable notifications

Telegram is already in the design, but needs to become a formal notifier surface:

- Telegram
- Slack webhook
- email
- custom script/webhook

Best donors:

- `ralphex`
- `Untether`

Target files:

- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/notifiers.py`

### P1. Multi-phase review, but narrower than the memo

The full "5 reviewer agents in parallel" idea is good, but should be trimmed for the first version.

Start with:

- security
- architecture
- tests

Then aggregate into one verdict surface.

Best donors:

- `ralphex`
- `Conclave`

### P1. Discovery board / context sharing

Useful once trace exists.
Not before.

Best donors:

- `Conclave`

Use it for:

- warnings
- discovered API constraints
- package/version pitfalls
- intent markers for active areas of change

### P1. Quality ratcheting

This is one of the best high-ROI additions from the later scans.

Required behavior:

- record baseline gate status before iteration
- if a previously green required gate turns red, fail the iteration hard
- later, optionally auto-revert or quarantine the attempt

Start conservative:

- detect and block first
- auto-revert second

Best donors:

- `toryo`
- existing Autopilot gate model

Target files:

- [loop_runner.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/loop_runner.py)
- [critic.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/critic.py)

### P1. Auto-detect tech stack on `autopilot init`

This is an OSS usability feature that should be in the plan explicitly.

Detect:

- framework/runtime
- test runner
- linting tools
- likely build command
- package manager

Best donors:

- `Wiggum CLI`

Target files:

- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/init.py`
- [adapters.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/core/adapters.py)

### P1. Daemon mode

Headless mode is the first step.
Daemon/service mode is the next practical one.

Needed:

- systemd/launchd units
- restart on failure
- log rotation/output discipline
- safe long-running service behavior

Best donors:

- `sleepless-agent`
- `Symphony`

Target files:

- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/deploy/systemd/`
- new: `/Users/martin/Desktop/Projects/FounderOS/autopilot/deploy/launchd/`
- [run.py](/Users/martin/Desktop/Projects/FounderOS/autopilot/autopilot/cli/run.py)

## Add To Plan: P2 / Later

### P2. Compounding memory

Good idea, not core to first hardening pass.
Do not build embeddings memory before trace + review artifacts are good.

Best donors:

- `Agent Swarm`
- `swarm-tools`

### P2. TUI dashboard

Useful, but not before:

- headless mode
- web dashboard cleanup
- trace surfaces

Best donors:

- `Bernstein`
- `agtx`

### P2. Docker sandbox mode

Strong safety feature, but expensive.
Only worth it after the current host-based execution loop is observable and governable.

Best donors:

- `OpenHands`
- `Open SWE`

### P2. Tracker triggers

Good after GitHub PR/reactions are in place.

- GitHub Issues
- Linear
- Jira
- Slack-triggered task creation

Best donors:

- `Open SWE`
- `Operum`
- `Agent Orchestrator`

### P2. Mid-run steering

Very good operator UX.
Not first-wave mandatory, but worth doing after headless + trace.

Best donors:

- `ralphex`

### P2. Multi-attempt per task

Useful when escalation is too serial and one task deserves bounded parallel attempts.

Possible model:

- run 2-3 bounded attempts
- compare gate and critic outcomes
- keep the best result

Best donors:

- `Forge`

### P2. Guided interview -> spec flow

This overlaps with the FounderOS/Quorum side, but it is still useful as a local Autopilot bootstrap.

Use it for:

- standalone repo onboarding
- local "I just want Autopilot to start" flow

Best donors:

- `Wiggum CLI`

### P2. Optional proxy-backed accounting/provider layer

Not first-wave, but valid later.

Use cases:

- team quotas
- central usage accounting
- API-compatible provider bridges

Best donors:

- `codex-lb`
- `CLIProxyAPI`

### P2. Scheduled/recurring maintenance runs

Useful for "overnight maintenance crew" workflows.
Not core to first OSS release.

Best donors:

- `Untether`
- `Trigger.dev`

## Add To Plan: P3 / Parking Lot

These are still useful enough to preserve in the plan, but they are later and more conditional.

### P3. Day/night quota scheduling

Once daemon mode and cost accounting exist, scheduling becomes a real lever.

Best donors:

- `sleepless-agent`

### P3. File reservation system

Cheaper and simpler than symbol-level locks.
Useful only if worktree isolation plus dependencies still leave too many collisions.

Best donors:

- `swarm-tools`

### P3. Symbol-level locks

Very interesting, but only if conflict rates justify the complexity.

Best donors:

- `wit`

### P3. Git-backed task tracking

Viable as an optional mode, not the core path.
Keep as an interoperability/storage experiment, not as the primary execution-plane model.

Best donors:

- `GNAP`
- `swarm-tools`

### P3. Sandbox hardening beyond Docker

If Autopilot broadens into a more general local agent platform, stronger host protection becomes more important.

Potential directions:

- learning mode for filesystem policy discovery
- deny-by-default profiles
- proxy-based API key protection

Best donors:

- `Greywall`
- `nono`
- `Anthropic sandbox-runtime`

### P3. Visual workflow editor

Useful later for FounderOS shell and power users, but not needed for the first strong OSS release.

Best donors:

- `VibeGrid`

### P3. GitHub label pipeline mode

Useful once tracker integration is mature.
This is a workflow mode, not a core architectural need.

Best donors:

- `Operum`

### P3. Handoff / assign / send-message orchestration vocabulary

Useful as a future subagent orchestration API vocabulary.
Not a first implementation target.

Reference donors:

- AWS CLI Agent Orchestrator patterns

### P3. Compounding identity/persona experiments

Keep as a very-late experiment only if it proves useful for non-coding operator agents.
Not for the core coding loop.

Potential donors:

- `Agent Swarm`

## Do Not Add Now

These should stay out of the near-term plan.

### Full 8-slot plugin ecosystem as a first move

Reason:

- too much architecture before enough usage signal
- minimal slots are enough first

### Self-evolution mode

Reason:

- dangerous before strong traces, review artifacts, and cost visibility

### Pica-style universal integration hub

Reason:

- wrong dependency shape for local-first OSS Autopilot
- curated local connector catalog is better

### Complex networking/protocol layers

Reason:

- interesting research surface
- wrong level of complexity for current Autopilot maturity

Examples:

- `Pilot Protocol`
- `AOP`
- heavy agent-over-agent mesh networking

## Net-New Items From the v2 Memo That Should Be Explicitly Added

Compared with the prior FounderOS-wide plan, the memo surfaced these items that should now be explicit in the Autopilot roadmap:

- cost and token accounting
- worker-loop trace and replay
- headless mode
- `autopilot doctor`
- story dependency graph + auto-unblock
- multi-phase review as a later upgrade
- configurable notifications as a real subsystem
- mid-run steering as a later operator UX upgrade

## Additional Useful Items Surfaced by Later Scans

These are now explicitly preserved in the roadmap instead of being silently dropped:

- quality ratcheting
- auto-detect tech stack on init
- daemon mode
- tracker triggers and label-driven workflows
- multi-attempt per task
- optional proxy-backed accounting/provider layer
- day/night quota scheduling
- file reservations
- Git-backed task tracking as an optional mode
- sandbox hardening beyond Docker
- visual workflow editor as a far-later shell feature

## Final Priority Order

### Immediate

1. cost and token accounting
2. story dependency graph + auto-unblock
3. headless mode
4. `autopilot doctor`
5. GitHub PR integration + reactions engine
6. structured trace and forensic replay
7. quality ratcheting

### After that

1. minimal provider/plugin interface
2. configurable notifications
3. multi-agent pipeline per story
4. narrower multi-phase review
5. discovery board/context sharing
6. auto-detect tech stack on init
7. daemon mode

### Later

1. TUI
2. Docker sandbox
3. tracker triggers
4. mid-run steering
5. compounding memory
6. scheduled runs
7. multi-attempt per task
8. optional proxy-backed accounting/provider layer
9. file reservations
10. symbol-level locks
11. Git-backed task tracking
12. visual workflow editor
13. deeper sandbox hardening
14. GitHub label pipeline mode
15. day/night quota scheduling

## The Short Version

From the v2 memo, the things that **must** enter the plan are not the flashy swarm ideas.

They are:

- `cost visibility`
- `real traceability`
- `GitHub/CI/review feedback closure`
- `headless execution`
- `doctor`
- `dependency-aware parallelism`

Those six changes, plus `quality ratcheting`, would move Autopilot much more than copying another orchestrator's full architecture.
