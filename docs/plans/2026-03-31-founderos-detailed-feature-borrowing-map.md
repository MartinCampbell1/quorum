# FounderOS — Detailed GitHub Feature Borrowing Map

Snapshot date: `2026-03-31`

Related docs:

- [2026-03-31-founderos-github-landscape-and-feature-roadmap.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-github-landscape-and-feature-roadmap.md)
- [2026-03-31-founderos-implementation-plan-from-github-research.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-implementation-plan-from-github-research.md)
- [CURRENT_STATUS.md](/Users/martin/Desktop/Projects/FounderOS/docs/CURRENT_STATUS.md)
- [SYSTEM_ARCHITECTURE.md](/Users/martin/Desktop/Projects/FounderOS/docs/SYSTEM_ARCHITECTURE.md)

## Purpose

This is the detailed, feature-level borrowing map for `FounderOS`.

It answers the specific implementation question:

`for each important FounderOS feature, which repo is the best donor, which exact files matter, what should be copied vs rewritten, and where should it land in our system?`

The product target remains:

`idea -> research -> tournament -> brief -> execution -> governance -> feedback`

inside one founder-facing operating system.

## Method

This pass used:

- direct repo inspection from local shallow clones under `/tmp/founderos-research`
- direct license checks
- direct file/dir inspection for the candidate donor repos
- prior verified GitHub research from the previous passes

This file intentionally avoids random repo dumping.
If a repo is here, it is here because it contributes to a concrete FounderOS feature.

## Reuse Legend

- `copy-safe`: permissive license and low enough coupling that code or templates can be transplanted with adaptation
- `selective`: permissive license, but only specific patterns/files should be adapted; do not transplant whole subsystems
- `architecture-only`: valuable model/pattern, but either too coupled or not safe/wise to transplant directly
- `reject`: do not use as a donor base

## Why `Dorothy`, `agtx`, `Untether`, and `slavingia/skills` Were Not All Elevated Earlier

This changed after deeper verification.

- `Dorothy`
  - now promoted
  - reason: verified MIT license and concrete value for founder/operator shell, remote control, and kanban-driven orchestration
- `agtx`
  - now promoted
  - reason: verified Apache-2.0 license and concrete value for worktree bootstrap, phase artifacts, MCP task control, and stuck-task nudging
- `Untether`
  - now promoted
  - reason: verified MIT license and strongest Telegram operator bridge found so far
- `slavingia/skills`
  - still not promoted to copy-safe
  - reason: useful conceptually, but it did not surface as a strong code donor and is weaker than the other verified founder-skill packs for direct borrowing

## Primary Build Principle

Do not assemble FounderOS by “gluing whole repos together”.

Do this instead:

1. Keep the FounderOS identity:
   - `Quorum` decides
   - `Execution Brief` contracts
   - `Autopilot` executes and governs
   - `FounderOS shell` presents the whole lifecycle
2. Borrow only the most leverage-heavy patterns and files.
3. Prefer thin integration seams and typed artifacts over giant framework adoption.

## Feature Map At A Glance

| Priority | Feature | Primary Donors | Lands In |
|---|---|---|---|
| P0 | `Execution Brief v2` | `spec-kit`, `symphony`, `PRD-MCP-Server`, `startup-skill`, `agent.md` | Quorum + Autopilot bridge |
| P0 | Reaction bus + approvals | `agent-orchestrator`, `trigger.dev`, `inngestgo`, `samples-go`, `untether` | Autopilot |
| P0 | Proof-of-work bundles | `symphony`, `dagster`, `kestra`, `OpenHands`, `sleepless-agent` | Autopilot + FounderOS shell |
| P0 | Durable state + inspect/edit/resume | `langgraph`, `trigger.dev`, `temporal`, `untether`, `takopi` | Autopilot + shell |
| P0 | Unified FounderOS shell | `Dorothy`, `get-shit-done`, `gstack`, `OpenHands` | FounderOS UI |
| P0 | One-command install + onboarding | `BMAD-METHOD`, `spec-kit`, `startup-skill`, `OpenHands` | FounderOS OSS packaging |
| P1 | Research + validation artifacts | `gpt-researcher`, `open_deep_research`, `VettIQ`, `startup-skill`, `DebateLLM` | Quorum |
| P1 | Tracker ingest + repo workflows | `symphony`, `agent-orchestrator`, `OpenHands` | Autopilot |
| P1 | Telegram / Slack operator bridge | `Untether`, `Takopi`, `Dorothy`, `sleepless-agent` | FounderOS shell + Autopilot |
| P1 | Worktree/runtime safety | `git-worktree-runner`, `agtx`, `agent-orchestrator`, `ccmanager`, `agentree`, `par` | Autopilot |
| P1 | Skill/context packs | `startup-founder-skills`, `startup-skill`, `BMAD-METHOD`, `agent.md`, `get-shit-done` | FounderOS shell + Quorum |
| P2 | Multi-model per story phase routing | `get-shit-done`, `agtx`, `OpenHands` | Autopilot |
| P2 | Distributed/remote worker execution | `symphony`, `OpenHands`, `Temporal samples` | Autopilot |
| P2 | Optional connector-hub provider | `Composio`, `Pica` | FounderOS Cloud / optional connectors |
| P2 | Recurring maintenance and scheduled runs | `Untether`, `Dorothy`, `trigger.dev`, `Kestra` | Autopilot + FounderOS shell |
| P3 | Multi-repo workspaces and control center | `par`, `agentree`, `Dorothy`, `GitButler` | FounderOS shell |
| P3 | Hosted/cloud convenience layer | `OpenHands`, `Composio`, `Pica` | FounderOS Cloud |
| P3 | Org/collaboration/security hardening | `OpenHands`, `Temporal`, `gitbutler` | FounderOS Cloud / enterprise-facing later layer |

## P0 — `Execution Brief v2`

### Why this is core

This is the single most important artifact in FounderOS.
It is the bridge between:

- founder intent
- Quorum’s research/tournament output
- Autopilot’s execution contract

### Primary donor repos

- `github/spec-kit` — `copy-safe`
- `openai/symphony` — `selective`
- `Saml1211/PRD-MCP-Server` — `selective`
- `ferdinandobons/startup-skill` — `selective`
- `agentmd/agent.md` — `copy-safe`
- `nanagajui/agentic_prd` — `architecture-only`

### Exact files to inspect and borrow from

From `spec-kit`:

- [/tmp/founderos-research/spec-kit/templates/spec-template.md](/tmp/founderos-research/spec-kit/templates/spec-template.md)
- [/tmp/founderos-research/spec-kit/templates/plan-template.md](/tmp/founderos-research/spec-kit/templates/plan-template.md)
- [/tmp/founderos-research/spec-kit/templates/tasks-template.md](/tmp/founderos-research/spec-kit/templates/tasks-template.md)
- [/tmp/founderos-research/spec-kit/templates/commands/clarify.md](/tmp/founderos-research/spec-kit/templates/commands/clarify.md)
- [/tmp/founderos-research/spec-kit/scripts/bash/create-new-feature.sh](/tmp/founderos-research/spec-kit/scripts/bash/create-new-feature.sh)
- [/tmp/founderos-research/spec-kit/scripts/bash/setup-plan.sh](/tmp/founderos-research/spec-kit/scripts/bash/setup-plan.sh)

Borrow:

- independent user-story slices
- explicit assumptions section
- measurable success criteria
- clarify loop before execution
- `spec -> plan -> tasks` decomposition discipline

From `symphony`:

- [/tmp/founderos-research/symphony/SPEC.md](/tmp/founderos-research/symphony/SPEC.md)
- [/tmp/founderos-research/symphony/elixir/WORKFLOW.md](/tmp/founderos-research/symphony/elixir/WORKFLOW.md)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workflow.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workflow.ex)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workflow_store.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workflow_store.ex)

Borrow:

- repo-owned workflow contract
- YAML front matter + human-readable Markdown body
- hot-reload of contract with “keep last known good” behavior

From `PRD-MCP-Server`:

- [/tmp/founderos-research/PRD-MCP-Server/src/tools/prd-generator.ts](/tmp/founderos-research/PRD-MCP-Server/src/tools/prd-generator.ts)
- [/tmp/founderos-research/PRD-MCP-Server/src/tools/prd-validator.ts](/tmp/founderos-research/PRD-MCP-Server/src/tools/prd-validator.ts)
- [/tmp/founderos-research/PRD-MCP-Server/src/resources/templates.ts](/tmp/founderos-research/PRD-MCP-Server/src/resources/templates.ts)
- [/tmp/founderos-research/PRD-MCP-Server/src/templates/standard.md](/tmp/founderos-research/PRD-MCP-Server/src/templates/standard.md)
- [/tmp/founderos-research/PRD-MCP-Server/src/templates/comprehensive.md](/tmp/founderos-research/PRD-MCP-Server/src/templates/comprehensive.md)

Borrow:

- generator/validator split
- template registry
- multi-template fallback path

From `startup-skill`:

- [/tmp/founderos-research/startup-skill/startup-design/SKILL.md](/tmp/founderos-research/startup-skill/startup-design/SKILL.md)
- [/tmp/founderos-research/startup-skill/startup-design/references/output-guidelines.md](/tmp/founderos-research/startup-skill/startup-design/references/output-guidelines.md)
- [/tmp/founderos-research/startup-skill/startup-design/references/research-scaling.md](/tmp/founderos-research/startup-skill/startup-design/references/research-scaling.md)
- [/tmp/founderos-research/startup-skill/startup-design/references/verification-agent.md](/tmp/founderos-research/startup-skill/startup-design/references/verification-agent.md)

Borrow:

- brutally honest validation sections
- phased research-to-decision structure
- explicit verification pass before final recommendation

From `agent.md`:

- [/tmp/founderos-research/agent.md/README.md](/tmp/founderos-research/agent.md/README.md)

Borrow:

- hierarchical repo-local instructions
- root + subtree instruction merge model
- `AGENT.md` standardization support

From `agentic_prd`:

- [/tmp/founderos-research/agentic_prd/src/agent_cli/crew.py](/tmp/founderos-research/agentic_prd/src/agent_cli/crew.py)
- [/tmp/founderos-research/agentic_prd/src/agent_cli/config/agents.yaml](/tmp/founderos-research/agentic_prd/src/agent_cli/config/agents.yaml)
- [/tmp/founderos-research/agentic_prd/src/agent_cli/config/tasks.yaml](/tmp/founderos-research/agentic_prd/src/agent_cli/config/tasks.yaml)
- [/tmp/founderos-research/agentic_prd/knowledge/rules.txt](/tmp/founderos-research/agentic_prd/knowledge/rules.txt)
- [/tmp/founderos-research/agentic_prd/output/product_requirements_document.md](/tmp/founderos-research/agentic_prd/output/product_requirements_document.md)

Borrow:

- only the architecture: multi-role PRD crew layout
- explicit task/agent split
- simple guardrails for agent-ready PRD generation

### What `Execution Brief v2` should contain

- initiative summary
- option winner rationale
- research summary with citations
- constraints and budgets
- approval policy
- story breakdown
- success criteria
- risk register
- attached evidence/source pack
- repo-local instruction references

### Reuse classification

- `spec-kit`: `copy-safe`
- `symphony`: `selective`
- `PRD-MCP-Server`: `selective`
- `startup-skill`: `selective`
- `agent.md`: `copy-safe`
- `agentic_prd`: `architecture-only`

### Lands in our codebase

- [orchestrator/execution_brief.py](/Users/martin/multi-agent/orchestrator/execution_brief.py)
- [orchestrator/models.py](/Users/martin/multi-agent/orchestrator/models.py)
- [orchestrator/engine.py](/Users/martin/multi-agent/orchestrator/engine.py)
- [frontend/components/founder-os/founder-os-board.tsx](/Users/martin/multi-agent/frontend/components/founder-os/founder-os-board.tsx)
- [frontend/lib/types.ts](/Users/martin/multi-agent/frontend/lib/types.ts)

## P0 — Reaction Bus, Approvals, and Resume Loops

### Why this matters

Without this, FounderOS still behaves like “agent runs until it stops”.
With this, it becomes:

- governable
- resumable
- review-aware
- budget-aware

### Primary donor repos

- `ComposioHQ/agent-orchestrator` — `copy-safe/selective`
- `triggerdotdev/trigger.dev` — `architecture-only`
- `inngest/inngestgo` — `selective`
- `temporalio/samples-go` — `copy-safe`
- `littlebearapps/untether` — `selective`
- `dagster-io/dagster` — `architecture-only`

### Exact files to inspect and borrow from

From `agent-orchestrator`:

- [/tmp/founderos-research/agent-orchestrator/packages/core/src/lifecycle-manager.ts](/tmp/founderos-research/agent-orchestrator/packages/core/src/lifecycle-manager.ts)
- [/tmp/founderos-research/agent-orchestrator/packages/core/src/feedback-tools.ts](/tmp/founderos-research/agent-orchestrator/packages/core/src/feedback-tools.ts)
- [/tmp/founderos-research/agent-orchestrator/packages/core/src/observability.ts](/tmp/founderos-research/agent-orchestrator/packages/core/src/observability.ts)
- [/tmp/founderos-research/agent-orchestrator/packages/core/src/session-manager.ts](/tmp/founderos-research/agent-orchestrator/packages/core/src/session-manager.ts)

Borrow:

- status -> event -> reaction map
- persisted feedback items keyed by session/run/reviewer
- explicit `ci-failed`, `changes-requested`, `agent-stuck` event taxonomy

From `trigger.dev`:

- [/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/eventBus.ts](/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/eventBus.ts)
- [/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/waitpointSystem.ts](/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/waitpointSystem.ts)
- [/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/checkpointSystem.ts](/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/checkpointSystem.ts)
- [/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/executionSnapshotSystem.ts](/tmp/founderos-research/trigger.dev/internal-packages/run-engine/src/engine/systems/executionSnapshotSystem.ts)

Borrow:

- typed run event bus semantics
- waitpoints as first-class runtime objects
- snapshot/checkpoint separation

From `inngestgo`:

- [/tmp/founderos-research/inngestgo/step/wait_for_event.go](/tmp/founderos-research/inngestgo/step/wait_for_event.go)
- [/tmp/founderos-research/inngestgo/step/wait_for_signal.go](/tmp/founderos-research/inngestgo/step/wait_for_signal.go)
- [/tmp/founderos-research/inngestgo/step/sleep.go](/tmp/founderos-research/inngestgo/step/sleep.go)
- [/tmp/founderos-research/inngestgo/step/run.go](/tmp/founderos-research/inngestgo/step/run.go)

Borrow:

- correlated wait-for-external-event primitives
- time-based sleeps without losing run identity

From `samples-go`:

- [/tmp/founderos-research/samples-go/update/update.go](/tmp/founderos-research/samples-go/update/update.go)
- [/tmp/founderos-research/samples-go/reqrespupdate/workflow.go](/tmp/founderos-research/samples-go/reqrespupdate/workflow.go)
- [/tmp/founderos-research/samples-go/await-signals/await_signals_workflow.go](/tmp/founderos-research/samples-go/await-signals/await_signals_workflow.go)
- [/tmp/founderos-research/samples-go/query/query_workflow.go](/tmp/founderos-research/samples-go/query/query_workflow.go)

Borrow:

- request/response approval flow
- signal wait and query surfaces
- safe update validation

From `untether`:

- [/tmp/founderos-research/untether/src/untether/triggers/dispatcher.py](/tmp/founderos-research/untether/src/untether/triggers/dispatcher.py)
- [/tmp/founderos-research/untether/src/untether/telegram/commands/ask_question.py](/tmp/founderos-research/untether/src/untether/telegram/commands/ask_question.py)

Borrow:

- human approval question UX
- authenticated trigger dispatch from chat surface

From `dagster`:

- [/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/run_status_sensor_definition.py](/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/run_status_sensor_definition.py)
- [/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/declarative_automation/automation_condition.py](/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/declarative_automation/automation_condition.py)

Borrow:

- status sensors and declarative automation thinking

### First event set FounderOS should support

- `ci_failed`
- `tests_failed`
- `review_comment_received`
- `changes_requested`
- `approval_requested`
- `approval_granted`
- `approval_denied`
- `budget_exhausted`
- `run_stalled`
- `worker_crashed`

### Lands in our codebase

- [orchestrator/engine.py](/Users/martin/multi-agent/orchestrator/engine.py)
- [orchestrator/api.py](/Users/martin/multi-agent/orchestrator/api.py)
- [orchestrator/models.py](/Users/martin/multi-agent/orchestrator/models.py)
- [gateway.py](/Users/martin/multi-agent/gateway.py)
- [frontend/components/chat/event-timeline.tsx](/Users/martin/multi-agent/frontend/components/chat/event-timeline.tsx)
- [frontend/components/founder-os/founder-os-board.tsx](/Users/martin/multi-agent/frontend/components/founder-os/founder-os-board.tsx)

## P0 — Proof-of-Work Bundles and Evidence Graph

### Why this matters

FounderOS must prove work, not just claim work.

### Primary donor repos

- `openai/symphony` — `selective`
- `dagster-io/dagster` — `architecture-only`
- `kestra-io/kestra` — `architecture-only`
- `OpenHands/OpenHands` — `selective`
- `context-machine-lab/sleepless-agent` — `selective`

### Exact files to inspect and borrow from

From `symphony`:

- [/tmp/founderos-research/symphony/SPEC.md](/tmp/founderos-research/symphony/SPEC.md)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir_web/controllers/observability_api_controller.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir_web/controllers/observability_api_controller.ex)

Borrow:

- proof-of-work expectation as a first-class deliverable
- light observability API around run state

From `dagster`:

- [/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/assets/graph/asset_graph.py](/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/definitions/assets/graph/asset_graph.py)
- [/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/asset_graph_view/asset_graph_view.py](/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/asset_graph_view/asset_graph_view.py)
- [/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/storage/event_log/base.py](/tmp/founderos-research/dagster/python_modules/dagster/dagster/_core/storage/event_log/base.py)

Borrow:

- evidence graph mental model
- event-log-backed observations/checks
- “what changed and why” lineage

From `kestra`:

- [/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/models/executions/Execution.java](/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/models/executions/Execution.java)
- [/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/models/executions/TaskRun.java](/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/models/executions/TaskRun.java)
- [/tmp/founderos-research/kestra/ui/src/components/onboarding/flows/manual-approval.yaml](/tmp/founderos-research/kestra/ui/src/components/onboarding/flows/manual-approval.yaml)
- [/tmp/founderos-research/kestra/ui/src/components/executions/Topology.vue](/tmp/founderos-research/kestra/ui/src/components/executions/Topology.vue)

Borrow:

- explicit execution/task-run modeling
- approval node concept
- topology view

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/.github/workflows/pr-artifacts.yml](/tmp/founderos-research/OpenHands/.github/workflows/pr-artifacts.yml)

Borrow:

- explicit distinction between PR-only artifacts and durable artifacts
- cleanup rules after approval

From `sleepless-agent`:

- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/monitoring/report_generator.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/monitoring/report_generator.py)
- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/workspace.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/workspace.py)

Borrow:

- report generation from durable task state
- workspace-bound result packaging

### FounderOS proof bundle should contain

- what was attempted
- what changed
- tests and CI outcomes
- approvals and review outcomes
- unresolved risks
- linked evidence artifacts
- attached diffs/logs/screenshots when relevant

### Lands in our codebase

- [orchestrator/models.py](/Users/martin/multi-agent/orchestrator/models.py)
- [orchestrator/api.py](/Users/martin/multi-agent/orchestrator/api.py)
- [frontend/components/chat/event-timeline.tsx](/Users/martin/multi-agent/frontend/components/chat/event-timeline.tsx)
- [frontend/components/founder-os/founder-os-board.tsx](/Users/martin/multi-agent/frontend/components/founder-os/founder-os-board.tsx)

## P0 — Durable State, Checkpoints, and Inspect/Edit/Resume

### Primary donor repos

- `langchain-ai/langgraph` — `architecture-only`
- `triggerdotdev/trigger.dev` — `architecture-only`
- `temporalio/temporal` — `architecture-only`
- `temporalio/samples-go` — `copy-safe`
- `littlebearapps/untether` — `selective`
- `banteg/takopi` — `copy-safe`
- `context-machine-lab/sleepless-agent` — `selective`

### Exact files to inspect and borrow from

From `langgraph`:

- [/tmp/founderos-research/langgraph/libs/langgraph/langgraph/graph/state.py](/tmp/founderos-research/langgraph/libs/langgraph/langgraph/graph/state.py)
- [/tmp/founderos-research/langgraph/libs/langgraph/langgraph/types.py](/tmp/founderos-research/langgraph/libs/langgraph/langgraph/types.py)
- [/tmp/founderos-research/langgraph/libs/checkpoint/README.md](/tmp/founderos-research/langgraph/libs/checkpoint/README.md)
- [/tmp/founderos-research/langgraph/libs/checkpoint/langgraph/checkpoint/base/__init__.py](/tmp/founderos-research/langgraph/libs/checkpoint/langgraph/checkpoint/base/__init__.py)
- [/tmp/founderos-research/langgraph/libs/prebuilt/langgraph/prebuilt/interrupt.py](/tmp/founderos-research/langgraph/libs/prebuilt/langgraph/prebuilt/interrupt.py)

Borrow:

- checkpoint thread model
- pending writes model
- interrupt/command semantics

From `temporal`:

- [/tmp/founderos-research/temporal/docs/architecture/workflow-update.md](/tmp/founderos-research/temporal/docs/architecture/workflow-update.md)
- [/tmp/founderos-research/temporal/docs/architecture/message-protocol.md](/tmp/founderos-research/temporal/docs/architecture/message-protocol.md)
- [/tmp/founderos-research/temporal/service/history/workflow/update/state.go](/tmp/founderos-research/temporal/service/history/workflow/update/state.go)
- [/tmp/founderos-research/temporal/service/history/hsm/tree.go](/tmp/founderos-research/temporal/service/history/hsm/tree.go)

Borrow:

- hierarchical state machines
- persisted update registry ideas
- mutation via messages, not ad hoc side effects

From `samples-go`:

- [/tmp/founderos-research/samples-go/query/query_workflow.go](/tmp/founderos-research/samples-go/query/query_workflow.go)
- [/tmp/founderos-research/samples-go/searchattributes/searchattributes_workflow.go](/tmp/founderos-research/samples-go/searchattributes/searchattributes_workflow.go)

Borrow:

- queryable live workflow state
- searchable run metadata

From `untether` and `takopi`:

- [/tmp/founderos-research/untether/src/untether/telegram/chat_sessions.py](/tmp/founderos-research/untether/src/untether/telegram/chat_sessions.py)
- [/tmp/founderos-research/untether/src/untether/telegram/state_store.py](/tmp/founderos-research/untether/src/untether/telegram/state_store.py)
- [/tmp/founderos-research/untether/src/untether/telegram/progress_persistence.py](/tmp/founderos-research/untether/src/untether/telegram/progress_persistence.py)
- [/tmp/founderos-research/takopi/src/takopi/telegram/chat_sessions.py](/tmp/founderos-research/takopi/src/takopi/telegram/chat_sessions.py)
- [/tmp/founderos-research/takopi/src/takopi/telegram/state_store.py](/tmp/founderos-research/takopi/src/takopi/telegram/state_store.py)

Borrow:

- per-session persistent chat state
- progress message persistence/cleanup
- easy resume behavior from a remote surface

From `sleepless-agent`:

- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/core/queue.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/core/queue.py)
- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/sqlite.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/sqlite.py)
- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/workspace.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/storage/workspace.py)

Borrow:

- SQLite-backed durable queue
- workspace persistence pattern

### Lands in our codebase

- [orchestrator/engine.py](/Users/martin/multi-agent/orchestrator/engine.py)
- [orchestrator/models.py](/Users/martin/multi-agent/orchestrator/models.py)
- [provider_sessions.py](/Users/martin/multi-agent/provider_sessions.py)
- [gateway.py](/Users/martin/multi-agent/gateway.py)

## P0 — Unified FounderOS Shell

### What this means

The shell is the founder-facing operating surface, not just a debug dashboard.

It needs:

- mode clarity
- live status
- readable artifacts
- clear intervention points
- real operator confidence

### Primary donor repos

- `Charlie85270/Dorothy` — `selective`
- `gsd-build/get-shit-done` — `selective`
- `garrytan/gstack` — `selective`
- `OpenHands/OpenHands` — `selective`
- `bmad-code-org/BMAD-METHOD` — `selective`

### Exact files to inspect and borrow from

From `Dorothy`:

- [/tmp/founderos-research/Dorothy/src/app/agents/page.tsx](/tmp/founderos-research/Dorothy/src/app/agents/page.tsx)
- [/tmp/founderos-research/Dorothy/src/app/kanban/page.tsx](/tmp/founderos-research/Dorothy/src/app/kanban/page.tsx)
- [/tmp/founderos-research/Dorothy/src/app/automations/page.tsx](/tmp/founderos-research/Dorothy/src/app/automations/page.tsx)
- [/tmp/founderos-research/Dorothy/src/components/CanvasView](/tmp/founderos-research/Dorothy/src/components/CanvasView)
- [/tmp/founderos-research/Dorothy/src/components/KanbanBoard](/tmp/founderos-research/Dorothy/src/components/KanbanBoard)
- [/tmp/founderos-research/Dorothy/src/hooks/useSuperAgent.ts](/tmp/founderos-research/Dorothy/src/hooks/useSuperAgent.ts)

Borrow:

- control-room composition
- operator-oriented canvas
- kanban + agent assignment views
- super-agent surface as a shell pattern

From `get-shit-done`:

- [/tmp/founderos-research/get-shit-done/get-shit-done/workflows/new-project.md](/tmp/founderos-research/get-shit-done/get-shit-done/workflows/new-project.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/workflows/discuss-phase.md](/tmp/founderos-research/get-shit-done/get-shit-done/workflows/discuss-phase.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/workflows/plan-phase.md](/tmp/founderos-research/get-shit-done/get-shit-done/workflows/plan-phase.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/workflows/execute-phase.md](/tmp/founderos-research/get-shit-done/get-shit-done/workflows/execute-phase.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/workflows/verify-phase.md](/tmp/founderos-research/get-shit-done/get-shit-done/workflows/verify-phase.md)
- [/tmp/founderos-research/get-shit-done/hooks/gsd-statusline.js](/tmp/founderos-research/get-shit-done/hooks/gsd-statusline.js)
- [/tmp/founderos-research/get-shit-done/hooks/gsd-context-monitor.js](/tmp/founderos-research/get-shit-done/hooks/gsd-context-monitor.js)
- [/tmp/founderos-research/get-shit-done/hooks/gsd-prompt-guard.js](/tmp/founderos-research/get-shit-done/hooks/gsd-prompt-guard.js)
- [/tmp/founderos-research/get-shit-done/hooks/gsd-workflow-guard.js](/tmp/founderos-research/get-shit-done/hooks/gsd-workflow-guard.js)

Borrow:

- lifecycle shell language: discuss / plan / execute / verify
- status line and context guard patterns
- workflow guard idea

From `gstack`:

- [/tmp/founderos-research/gstack/ARCHITECTURE.md](/tmp/founderos-research/gstack/ARCHITECTURE.md)
- [/tmp/founderos-research/gstack/office-hours/SKILL.md](/tmp/founderos-research/gstack/office-hours/SKILL.md)
- [/tmp/founderos-research/gstack/plan-ceo-review/SKILL.md](/tmp/founderos-research/gstack/plan-ceo-review/SKILL.md)
- [/tmp/founderos-research/gstack/plan-eng-review/SKILL.md](/tmp/founderos-research/gstack/plan-eng-review/SKILL.md)
- [/tmp/founderos-research/gstack/lib/worktree.ts](/tmp/founderos-research/gstack/lib/worktree.ts)

Borrow:

- CEO/ENG review loop pattern
- durable helper binaries and generated skills docs
- operator review workflow naming

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/openhands/app_server/app_conversation/live_status_app_conversation_service.py](/tmp/founderos-research/OpenHands/openhands/app_server/app_conversation/live_status_app_conversation_service.py)
- [/tmp/founderos-research/OpenHands/frontend/src/api/event-service/event-service.api.ts](/tmp/founderos-research/OpenHands/frontend/src/api/event-service/event-service.api.ts)
- [/tmp/founderos-research/OpenHands/frontend/src/hooks/query/use-task-polling.ts](/tmp/founderos-research/OpenHands/frontend/src/hooks/query/use-task-polling.ts)
- [/tmp/founderos-research/OpenHands/frontend/src/hooks/query/use-conversation-history.ts](/tmp/founderos-research/OpenHands/frontend/src/hooks/query/use-conversation-history.ts)

Borrow:

- live status polling/subscription pattern
- split APIs for conversation, event, git, sandbox data

From `BMAD-METHOD`:

- [/tmp/founderos-research/BMAD-METHOD/docs/reference/workflow-map.md](/tmp/founderos-research/BMAD-METHOD/docs/reference/workflow-map.md)
- [/tmp/founderos-research/BMAD-METHOD/docs/explanation/party-mode.md](/tmp/founderos-research/BMAD-METHOD/docs/explanation/party-mode.md)

Borrow:

- guided next-step UX
- explicit workflow map

### Lands in our codebase

- [frontend/components/founder-os/founder-os-board.tsx](/Users/martin/multi-agent/frontend/components/founder-os/founder-os-board.tsx)
- [frontend/app/page.tsx](/Users/martin/multi-agent/frontend/app/page.tsx)
- [frontend/lib/api.ts](/Users/martin/multi-agent/frontend/lib/api.ts)
- [frontend/lib/types.ts](/Users/martin/multi-agent/frontend/lib/types.ts)

## P0 — One-Command Install and Guided OSS Onboarding

### Primary donor repos

- `BMAD-METHOD` — `copy-safe/selective`
- `spec-kit` — `copy-safe`
- `startup-skill` — `copy-safe/selective`
- `OpenHands` — `selective`

### Exact files to inspect and borrow from

From `BMAD-METHOD`:

- [/tmp/founderos-research/BMAD-METHOD/tools/installer/bmad-cli.js](/tmp/founderos-research/BMAD-METHOD/tools/installer/bmad-cli.js)
- [/tmp/founderos-research/BMAD-METHOD/tools/installer/prompts.js](/tmp/founderos-research/BMAD-METHOD/tools/installer/prompts.js)
- [/tmp/founderos-research/BMAD-METHOD/tools/installer/file-ops.js](/tmp/founderos-research/BMAD-METHOD/tools/installer/file-ops.js)
- [/tmp/founderos-research/BMAD-METHOD/tools/installer/project-root.js](/tmp/founderos-research/BMAD-METHOD/tools/installer/project-root.js)
- [/tmp/founderos-research/BMAD-METHOD/tools/installer/README.md](/tmp/founderos-research/BMAD-METHOD/tools/installer/README.md)
- [/tmp/founderos-research/BMAD-METHOD/src/core-skills/module.yaml](/tmp/founderos-research/BMAD-METHOD/src/core-skills/module.yaml)

Borrow:

- interactive installer flow
- non-interactive installer mode
- module registration structure
- post-install guidance

From `spec-kit`:

- [/tmp/founderos-research/spec-kit/src/specify_cli](/tmp/founderos-research/spec-kit/src/specify_cli)

Borrow:

- clean CLI bootstrap flow

From `startup-skill`:

- [/tmp/founderos-research/startup-skill/.claude-plugin/marketplace.json](/tmp/founderos-research/startup-skill/.claude-plugin/marketplace.json)

Borrow:

- plugin/skill packaging shape

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/.devcontainer/setup.sh](/tmp/founderos-research/OpenHands/.devcontainer/setup.sh)
- [/tmp/founderos-research/OpenHands/containers/dev/compose.yml](/tmp/founderos-research/OpenHands/containers/dev/compose.yml)

Borrow:

- local setup friendliness
- container-based fallback install path

### FounderOS OSS target

- one command install
- optional interactive setup
- BYOK support
- local-first default
- clear “what next” after install

## P1 — Quorum Research and Validation Upgrade

### Primary donor repos

- `assafelovic/gpt-researcher` — `selective`
- `langchain-ai/open_deep_research` — `copy-safe/selective`
- `Nirikshan95/VettIQ` — `copy-safe`
- `ferdinandobons/startup-skill` — `selective`
- `instadeepai/DebateLLM` — `selective`
- `shawnpang/startup-founder-skills` — `selective`

### Exact files to inspect and borrow from

From `gpt-researcher`:

- [/tmp/founderos-research/gpt-researcher/gpt_researcher/agent.py](/tmp/founderos-research/gpt-researcher/gpt_researcher/agent.py)
- [/tmp/founderos-research/gpt-researcher/gpt_researcher/context/compression.py](/tmp/founderos-research/gpt-researcher/gpt_researcher/context/compression.py)
- [/tmp/founderos-research/gpt-researcher/gpt_researcher/mcp/client.py](/tmp/founderos-research/gpt-researcher/gpt_researcher/mcp/client.py)
- [/tmp/founderos-research/gpt-researcher/multi_agents/agents](/tmp/founderos-research/gpt-researcher/multi_agents/agents)

Borrow:

- planner/executor/writer split
- context compression
- MCP-assisted research tool routing

From `open_deep_research`:

- [/tmp/founderos-research/open_deep_research/src/open_deep_research/deep_researcher.py](/tmp/founderos-research/open_deep_research/src/open_deep_research/deep_researcher.py)
- [/tmp/founderos-research/open_deep_research/src/open_deep_research/configuration.py](/tmp/founderos-research/open_deep_research/src/open_deep_research/configuration.py)
- [/tmp/founderos-research/open_deep_research/src/open_deep_research/prompts.py](/tmp/founderos-research/open_deep_research/src/open_deep_research/prompts.py)
- [/tmp/founderos-research/open_deep_research/src/open_deep_research/state.py](/tmp/founderos-research/open_deep_research/src/open_deep_research/state.py)
- [/tmp/founderos-research/open_deep_research/src/legacy/multi_agent.py](/tmp/founderos-research/open_deep_research/src/legacy/multi_agent.py)

Borrow:

- supervisor/researcher split
- research plan approval pattern
- stateful research pipeline

From `VettIQ`:

- [/tmp/founderos-research/VettIQ/graphs/workflow.py](/tmp/founderos-research/VettIQ/graphs/workflow.py)
- [/tmp/founderos-research/VettIQ/state/agent_state.py](/tmp/founderos-research/VettIQ/state/agent_state.py)
- [/tmp/founderos-research/VettIQ/nodes/market_analyst.py](/tmp/founderos-research/VettIQ/nodes/market_analyst.py)
- [/tmp/founderos-research/VettIQ/nodes/competitor_analysis.py](/tmp/founderos-research/VettIQ/nodes/competitor_analysis.py)
- [/tmp/founderos-research/VettIQ/nodes/risk_assessor.py](/tmp/founderos-research/VettIQ/nodes/risk_assessor.py)
- [/tmp/founderos-research/VettIQ/nodes/advisor.py](/tmp/founderos-research/VettIQ/nodes/advisor.py)

Borrow:

- compact startup validation pipeline
- explicit `market -> competitors -> risk -> advisor` path

From `startup-skill`:

- [/tmp/founderos-research/startup-skill/startup-competitors/SKILL.md](/tmp/founderos-research/startup-skill/startup-competitors/SKILL.md)
- [/tmp/founderos-research/startup-skill/startup-positioning/SKILL.md](/tmp/founderos-research/startup-skill/startup-positioning/SKILL.md)
- [/tmp/founderos-research/startup-skill/startup-pitch/SKILL.md](/tmp/founderos-research/startup-skill/startup-pitch/SKILL.md)

Borrow:

- battle-card output forms
- positioning outputs
- pitch/readout packaging after decision

From `DebateLLM`:

- [/tmp/founderos-research/DebateLLM/debatellm/systems.py](/tmp/founderos-research/DebateLLM/debatellm/systems.py)
- [/tmp/founderos-research/DebateLLM/debatellm/agents.py](/tmp/founderos-research/DebateLLM/debatellm/agents.py)
- [/tmp/founderos-research/DebateLLM/debatellm/utils/debate.py](/tmp/founderos-research/DebateLLM/debatellm/utils/debate.py)
- [/tmp/founderos-research/DebateLLM/experiments/conf/config.yaml](/tmp/founderos-research/DebateLLM/experiments/conf/config.yaml)

Borrow:

- protocol switching by config
- agreement/intensity tuning
- multiple debate system archetypes instead of one fixed protocol

From `startup-founder-skills`:

- [/tmp/founderos-research/startup-founder-skills/skills/startup-context/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/startup-context/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/market-research/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/market-research/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/competitive-analysis/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/competitive-analysis/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/mvp-scoping/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/mvp-scoping/SKILL.md)

Borrow:

- founder context document
- cross-skill context dependency
- post-decision scoping helpers

### Lands in our codebase

- [orchestrator/modes/tournament.py](/Users/martin/multi-agent/orchestrator/modes/tournament.py)
- [orchestrator/modes/board.py](/Users/martin/multi-agent/orchestrator/modes/board.py)
- [orchestrator/scenarios.py](/Users/martin/multi-agent/orchestrator/scenarios.py)
- [frontend/components/founder-os/founder-os-board.tsx](/Users/martin/multi-agent/frontend/components/founder-os/founder-os-board.tsx)

## P1 — Tracker Ingest and Repo Workflow Inputs

### Primary donor repos

- `openai/symphony` — `selective`
- `ComposioHQ/agent-orchestrator` — `copy-safe/selective`
- `OpenHands/OpenHands` — `selective`

### Exact files to inspect and borrow from

From `symphony`:

- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/tracker.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/tracker.ex)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/orchestrator.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/orchestrator.ex)

Borrow:

- tracker abstraction boundary
- single poll/claim/execute loop

From `agent-orchestrator`:

- [/tmp/founderos-research/agent-orchestrator/examples/linear-team.yaml](/tmp/founderos-research/agent-orchestrator/examples/linear-team.yaml)
- [/tmp/founderos-research/agent-orchestrator/packages/plugins](/tmp/founderos-research/agent-orchestrator/packages/plugins)

Borrow:

- tracker plugin seam
- issue/review routing back to runs

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/openhands/integrations/github/github_service.py](/tmp/founderos-research/OpenHands/openhands/integrations/github/github_service.py)
- [/tmp/founderos-research/OpenHands/openhands/integrations/github/queries.py](/tmp/founderos-research/OpenHands/openhands/integrations/github/queries.py)

Borrow:

- real Git provider API surface
- integration service layering

## P1 — Telegram / Slack Operator Bridge

### Primary donor repos

- `littlebearapps/untether` — `selective`
- `banteg/takopi` — `copy-safe`
- `Charlie85270/Dorothy` — `selective`
- `context-machine-lab/sleepless-agent` — `selective`

### Exact files to inspect and borrow from

From `untether`:

- [/tmp/founderos-research/untether/src/untether/telegram/bridge.py](/tmp/founderos-research/untether/src/untether/telegram/bridge.py)
- [/tmp/founderos-research/untether/src/untether/telegram/backend.py](/tmp/founderos-research/untether/src/untether/telegram/backend.py)
- [/tmp/founderos-research/untether/src/untether/telegram/topic_state.py](/tmp/founderos-research/untether/src/untether/telegram/topic_state.py)
- [/tmp/founderos-research/untether/src/untether/cost_tracker.py](/tmp/founderos-research/untether/src/untether/cost_tracker.py)

Borrow:

- full Telegram bridge
- topic/session state
- cost tracking surface

From `takopi`:

- [/tmp/founderos-research/takopi/src/takopi/telegram/bridge.py](/tmp/founderos-research/takopi/src/takopi/telegram/bridge.py)
- [/tmp/founderos-research/takopi/src/takopi/telegram/outbox.py](/tmp/founderos-research/takopi/src/takopi/telegram/outbox.py)
- [/tmp/founderos-research/takopi/src/takopi/runner_bridge.py](/tmp/founderos-research/takopi/src/takopi/runner_bridge.py)

Borrow:

- lean bridge if Untether feels too heavy
- artifact outbox model

From `Dorothy`:

- [/tmp/founderos-research/Dorothy/electron/services/telegram-bot.ts](/tmp/founderos-research/Dorothy/electron/services/telegram-bot.ts)
- [/tmp/founderos-research/Dorothy/electron/services/slack-bot.ts](/tmp/founderos-research/Dorothy/electron/services/slack-bot.ts)
- [/tmp/founderos-research/Dorothy/mcp-telegram/src/index.ts](/tmp/founderos-research/Dorothy/mcp-telegram/src/index.ts)

Borrow:

- multi-surface operator control
- MCP-wrapped messaging surface

From `sleepless-agent`:

- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/interfaces/bot.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/interfaces/bot.py)
- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/chat/session.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/chat/session.py)
- [/tmp/founderos-research/sleepless-agent/src/sleepless_agent/monitoring/report_generator.py](/tmp/founderos-research/sleepless-agent/src/sleepless_agent/monitoring/report_generator.py)

Borrow:

- Slack thread intake
- report generation from durable state

## P1 — Worktree and Runtime Safety

### Primary donor repos

- `coderabbitai/git-worktree-runner` — `copy-safe/selective`
- `fynnfluegge/agtx` — `selective`
- `ComposioHQ/agent-orchestrator` — `copy-safe/selective`
- `kbwo/ccmanager` — `selective`
- `AryaLabsHQ/agentree` — `copy-safe`
- `coplane/par` — `selective`
- `gitbutlerapp/gitbutler` — `architecture-only`

### Exact files to inspect and borrow from

From `git-worktree-runner`:

- [/tmp/founderos-research/git-worktree-runner/lib/commands/create.sh](/tmp/founderos-research/git-worktree-runner/lib/commands/create.sh)
- [/tmp/founderos-research/git-worktree-runner/lib/config.sh](/tmp/founderos-research/git-worktree-runner/lib/config.sh)
- [/tmp/founderos-research/git-worktree-runner/lib/hooks.sh](/tmp/founderos-research/git-worktree-runner/lib/hooks.sh)
- [/tmp/founderos-research/git-worktree-runner/lib/copy.sh](/tmp/founderos-research/git-worktree-runner/lib/copy.sh)
- [/tmp/founderos-research/git-worktree-runner/lib/provider.sh](/tmp/founderos-research/git-worktree-runner/lib/provider.sh)
- [/tmp/founderos-research/git-worktree-runner/lib/commands/clean.sh](/tmp/founderos-research/git-worktree-runner/lib/commands/clean.sh)

Borrow:

- layered config precedence
- include/exclude copying
- hook phases
- provider launch abstraction
- cleanup discipline

From `agtx`:

- [/tmp/founderos-research/agtx/src/git/worktree.rs](/tmp/founderos-research/agtx/src/git/worktree.rs)
- [/tmp/founderos-research/agtx/src/mcp/server.rs](/tmp/founderos-research/agtx/src/mcp/server.rs)
- [/tmp/founderos-research/agtx/plugins/agtx/plugin.toml](/tmp/founderos-research/agtx/plugins/agtx/plugin.toml)
- [/tmp/founderos-research/agtx/plugins/agtx/skills/orchestrate.md](/tmp/founderos-research/agtx/plugins/agtx/skills/orchestrate.md)

Borrow:

- worktree bootstrap with config copy
- MCP task-control surface
- phase/artifact slots
- stuck-task nudge protocol

From `agent-orchestrator`:

- [/tmp/founderos-research/agent-orchestrator/packages/plugins/workspace-worktree/src/index.ts](/tmp/founderos-research/agent-orchestrator/packages/plugins/workspace-worktree/src/index.ts)
- [/tmp/founderos-research/agent-orchestrator/packages/core/src/plugin-registry.ts](/tmp/founderos-research/agent-orchestrator/packages/core/src/plugin-registry.ts)

Borrow:

- typed workspace plugin seam

From `ccmanager`:

- [/tmp/founderos-research/ccmanager/src/services/worktreeService.ts](/tmp/founderos-research/ccmanager/src/services/worktreeService.ts)
- [/tmp/founderos-research/ccmanager/src/services/sessionManager.ts](/tmp/founderos-research/ccmanager/src/services/sessionManager.ts)
- [/tmp/founderos-research/ccmanager/src/services/stateDetector/codex.ts](/tmp/founderos-research/ccmanager/src/services/stateDetector/codex.ts)
- [/tmp/founderos-research/ccmanager/src/utils/hookExecutor.ts](/tmp/founderos-research/ccmanager/src/utils/hookExecutor.ts)

Borrow:

- provider terminal-state detectors
- pre/post worktree hook executor
- project-local session manager pattern

From `agentree`:

- [/tmp/founderos-research/agentree/cmd/create.go](/tmp/founderos-research/agentree/cmd/create.go)
- [/tmp/founderos-research/agentree/internal/env/env.go](/tmp/founderos-research/agentree/internal/env/env.go)
- [/tmp/founderos-research/agentree/internal/env/gitignore.go](/tmp/founderos-research/agentree/internal/env/gitignore.go)
- [/tmp/founderos-research/agentree/internal/detector/detector.go](/tmp/founderos-research/agentree/internal/detector/detector.go)
- [/tmp/founderos-research/agentree/internal/scripts/scripts.go](/tmp/founderos-research/agentree/internal/scripts/scripts.go)

Borrow:

- auto env file copying
- repo setup detection
- post-create setup scripts

From `par`:

- [/tmp/founderos-research/par/par/core.py](/tmp/founderos-research/par/par/core.py)
- [/tmp/founderos-research/par/par/operations.py](/tmp/founderos-research/par/par/operations.py)
- [/tmp/founderos-research/par/par/workspace.py](/tmp/founderos-research/par/par/workspace.py)
- [/tmp/founderos-research/par/par/checkout.py](/tmp/founderos-research/par/par/checkout.py)

Borrow:

- global session label model
- worktree + tmux global management
- multi-repo workspace concept

From `gitbutler`:

- [/tmp/founderos-research/gitbutler/crates/gitbutler-oplog/src/oplog.rs](/tmp/founderos-research/gitbutler/crates/gitbutler-oplog/src/oplog.rs)
- [/tmp/founderos-research/gitbutler/crates/gitbutler-oplog/src/snapshot.rs](/tmp/founderos-research/gitbutler/crates/gitbutler-oplog/src/snapshot.rs)
- [/tmp/founderos-research/gitbutler/crates/but-worktrees/src/new.rs](/tmp/founderos-research/gitbutler/crates/but-worktrees/src/new.rs)

Borrow:

- only the architecture: oplog/snapshot mental model, not code

### Reuse classification notes

- `gitbutler` stays `architecture-only` because the repo uses `FSL-1.1-MIT` with competing-use restrictions

## P1 — Skill Packs, Context Packs, and Founder-Facing Workflow Content

### Primary donor repos

- `shawnpang/startup-founder-skills` — `selective`
- `ferdinandobons/startup-skill` — `selective`
- `BMAD-METHOD` — `selective`
- `agentmd/agent.md` — `copy-safe`
- `get-shit-done` — `selective`

### Exact files to inspect and borrow from

From `startup-founder-skills`:

- [/tmp/founderos-research/startup-founder-skills/skills/startup-context/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/startup-context/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/prd-writing/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/prd-writing/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/roadmap-planning/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/roadmap-planning/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/mvp-scoping/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/mvp-scoping/SKILL.md)
- [/tmp/founderos-research/startup-founder-skills/skills/competitive-analysis/SKILL.md](/tmp/founderos-research/startup-founder-skills/skills/competitive-analysis/SKILL.md)

Borrow:

- shared founder context file
- cross-skill dependency structure
- founder tasks beyond coding

From `BMAD-METHOD`:

- [/tmp/founderos-research/BMAD-METHOD/src/core-skills/module.yaml](/tmp/founderos-research/BMAD-METHOD/src/core-skills/module.yaml)
- [/tmp/founderos-research/BMAD-METHOD/src/bmm-skills/module.yaml](/tmp/founderos-research/BMAD-METHOD/src/bmm-skills/module.yaml)
- [/tmp/founderos-research/BMAD-METHOD/docs/reference/agents.md](/tmp/founderos-research/BMAD-METHOD/docs/reference/agents.md)
- [/tmp/founderos-research/BMAD-METHOD/docs/reference/commands.md](/tmp/founderos-research/BMAD-METHOD/docs/reference/commands.md)

Borrow:

- skill/module registration pattern
- guided “what to do next” documentation

From `get-shit-done`:

- [/tmp/founderos-research/get-shit-done/get-shit-done/templates/project.md](/tmp/founderos-research/get-shit-done/get-shit-done/templates/project.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/templates/requirements.md](/tmp/founderos-research/get-shit-done/get-shit-done/templates/requirements.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/templates/roadmap.md](/tmp/founderos-research/get-shit-done/get-shit-done/templates/roadmap.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/templates/state.md](/tmp/founderos-research/get-shit-done/get-shit-done/templates/state.md)

Borrow:

- stateful project-memory template set

## P2 — Multi-Model Per Story Phase Routing

### Why this is P2, not P0

This improves cost/throughput and specialization, but FounderOS does not need it to feel coherent on first OSS release.

### Primary donor repos

- `gsd-build/get-shit-done` — `selective`
- `fynnfluegge/agtx` — `selective`
- `OpenHands/OpenHands` — `architecture-only`

### Exact files to inspect and borrow from

From `get-shit-done`:

- [/tmp/founderos-research/get-shit-done/get-shit-done/references/model-profiles.md](/tmp/founderos-research/get-shit-done/get-shit-done/references/model-profiles.md)
- [/tmp/founderos-research/get-shit-done/get-shit-done/references/model-profile-resolution.md](/tmp/founderos-research/get-shit-done/get-shit-done/references/model-profile-resolution.md)

Borrow:

- profile tiers like `quality / balanced / budget / inherit`
- per-agent model overrides
- runtime-friendly “inherit current session model” behavior

From `agtx`:

- [/tmp/founderos-research/agtx/plugins/agtx/plugin.toml](/tmp/founderos-research/agtx/plugins/agtx/plugin.toml)
- [/tmp/founderos-research/agtx/plugins/agtx/skills/orchestrate.md](/tmp/founderos-research/agtx/plugins/agtx/skills/orchestrate.md)

Borrow:

- phase-specific agent selection
- per-phase artifact/command expectations

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/openhands/core/config/model_routing_config.py](/tmp/founderos-research/OpenHands/openhands/core/config/model_routing_config.py)

Borrow:

- only the architecture: dedicated model-routing config object
- note: this file is explicitly marked legacy in OpenHands, so do not transplant code

### FounderOS shape for this feature

- `research/planning` phases can use cheaper or reasoning-heavy models differently from `implementation` and `verification`
- model routing must remain subordinate to `Execution Brief` policy and budget policy

## P2 — Distributed and Remote Worker Execution

### Why this is P2

Parallel local worktrees already get FounderOS a long way.
Remote/distributed execution becomes important once concurrency, isolation, or heavy parallelism grows.

### Primary donor repos

- `openai/symphony` — `selective`
- `OpenHands/OpenHands` — `selective`
- `temporalio/samples-go` — `copy-safe`

### Exact files to inspect and borrow from

From `symphony`:

- [/tmp/founderos-research/symphony/SPEC.md](/tmp/founderos-research/symphony/SPEC.md)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workspace.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/workspace.ex)
- [/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/codex/app_server.ex](/tmp/founderos-research/symphony/elixir/lib/symphony_elixir/codex/app_server.ex)

Borrow:

- worker/workspace split
- remote worker concept over SSH/app-server boundary

From `OpenHands`:

- [/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/remote_sandbox_service.py](/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/remote_sandbox_service.py)
- [/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/remote_sandbox_spec_service.py](/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/remote_sandbox_spec_service.py)
- [/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/sandbox_models.py](/tmp/founderos-research/OpenHands/openhands/app_server/sandbox/sandbox_models.py)

Borrow:

- remote runtime service boundary
- exposed worker ports / runtime metadata model
- sandbox abstraction between local and remote execution

From `samples-go`:

- [/tmp/founderos-research/samples-go/worker-specific-task-queues/README.md](/tmp/founderos-research/samples-go/worker-specific-task-queues/README.md)
- [/tmp/founderos-research/samples-go/worker-versioning/README.md](/tmp/founderos-research/samples-go/worker-versioning/README.md)

Borrow:

- worker-specific queue/lanes concept
- versioned rollout model for worker fleets

## P2 — Optional Connector-Hub Provider

### Why this is P2

FounderOS should not depend on a cloud connector hub for OSS core value.
But an optional connector provider can later accelerate hosted/cloud convenience.

### Primary donor repos

- `ComposioHQ/composio` — `selective`
- `withoneai/pica` — `architecture-only`

### Exact files to inspect and borrow from

From `Composio`:

- [/tmp/founderos-research/composio/python/examples/tools.py](/tmp/founderos-research/composio/python/examples/tools.py)
- [/tmp/founderos-research/composio/python/examples/toolkits.py](/tmp/founderos-research/composio/python/examples/toolkits.py)
- [/tmp/founderos-research/composio/python/providers/langgraph/README.md](/tmp/founderos-research/composio/python/providers/langgraph/README.md)
- [/tmp/founderos-research/composio/python/composio/utils/schema_converter.py](/tmp/founderos-research/composio/python/composio/utils/schema_converter.py)
- [/tmp/founderos-research/composio/ts/docs/providers/custom.md](/tmp/founderos-research/composio/ts/docs/providers/custom.md)
- [/tmp/founderos-research/composio/ts/docs/api/tools.md](/tmp/founderos-research/composio/ts/docs/api/tools.md)
- [/tmp/founderos-research/composio/ts/docs/api/toolkits.md](/tmp/founderos-research/composio/ts/docs/api/toolkits.md)

Borrow:

- provider abstraction for many toolkits
- schema conversion and typed tool exposure
- optional provider adapter model

From `Pica`:

- [/tmp/founderos-research/pica/README.md](/tmp/founderos-research/pica/README.md)
- [/tmp/founderos-research/pica/core/oauth/README.md](/tmp/founderos-research/pica/core/oauth/README.md)
- [/tmp/founderos-research/pica/core/oauth/src/index.ts](/tmp/founderos-research/pica/core/oauth/src/index.ts)
- [/tmp/founderos-research/pica/core/unified/README.md](/tmp/founderos-research/pica/core/unified/README.md)
- [/tmp/founderos-research/pica/core/unified/src/unified.rs](/tmp/founderos-research/pica/core/unified/src/unified.rs)
- [/tmp/founderos-research/pica/core/unified/src/client.rs](/tmp/founderos-research/pica/core/unified/src/client.rs)

Borrow:

- only the architecture: unified connector/action layer and OAuth service split
- do not make FounderOS core depend on it; community edition is explicitly deprecated

### FounderOS rule for this feature

- no connector hub in OSS core critical path
- if added, it should appear as an optional connector type in the capability layer

## P2 — Recurring Maintenance and Scheduled Runs

### Why this is P2

Useful for real operator workflows, but not required for FounderOS’s first coherent release.

### Primary donor repos

- `littlebearapps/untether` — `selective`
- `Charlie85270/Dorothy` — `selective`
- `triggerdotdev/trigger.dev` — `architecture-only`
- `kestra-io/kestra` — `architecture-only`

### Exact files to inspect and borrow from

From `untether`:

- [/tmp/founderos-research/untether/src/untether/scheduler.py](/tmp/founderos-research/untether/src/untether/scheduler.py)
- [/tmp/founderos-research/untether/src/untether/triggers/cron.py](/tmp/founderos-research/untether/src/untether/triggers/cron.py)
- [/tmp/founderos-research/untether/src/untether/telegram/commands/trigger.py](/tmp/founderos-research/untether/src/untether/telegram/commands/trigger.py)

Borrow:

- scheduled trigger layer tied to chat/operator surfaces

From `Dorothy`:

- [/tmp/founderos-research/Dorothy/mcp-orchestrator/src/tools/automations.ts](/tmp/founderos-research/Dorothy/mcp-orchestrator/src/tools/automations.ts)
- [/tmp/founderos-research/Dorothy/mcp-orchestrator/src/tools/scheduler.ts](/tmp/founderos-research/Dorothy/mcp-orchestrator/src/tools/scheduler.ts)
- [/tmp/founderos-research/Dorothy/src/app/recurring-tasks/page.tsx](/tmp/founderos-research/Dorothy/src/app/recurring-tasks/page.tsx)

Borrow:

- recurring-task UI and orchestration concepts

From `trigger.dev`:

- [/tmp/founderos-research/trigger.dev/internal-packages/schedule-engine/src](/tmp/founderos-research/trigger.dev/internal-packages/schedule-engine/src)
- [/tmp/founderos-research/trigger.dev/docs/wait-for.mdx](/tmp/founderos-research/trigger.dev/docs/wait-for.mdx)

Borrow:

- scheduler semantics, replay model, wait-until logic

From `kestra`:

- [/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/scheduler/events/TriggerEvent.java](/tmp/founderos-research/kestra/core/src/main/java/io/kestra/core/scheduler/events/TriggerEvent.java)

Borrow:

- trigger event taxonomy

## P3 — Multi-Repo Workspaces and Control Center

### Why this is P3

This is valuable, but it is a shell/convenience expansion rather than a core FounderOS differentiator.

### Primary donor repos

- `coplane/par` — `selective`
- `AryaLabsHQ/agentree` — `selective`
- `Charlie85270/Dorothy` — `selective`
- `gitbutlerapp/gitbutler` — `architecture-only`

### Exact files to inspect and borrow from

From `par`:

- [/tmp/founderos-research/par/par/workspace.py](/tmp/founderos-research/par/par/workspace.py)
- [/tmp/founderos-research/par/par/operations.py](/tmp/founderos-research/par/par/operations.py)
- [/tmp/founderos-research/par/par/checkout.py](/tmp/founderos-research/par/par/checkout.py)

Borrow:

- multi-repo workspace idea
- global control-center semantics

From `agentree`:

- [/tmp/founderos-research/agentree/internal/tui/wizard.go](/tmp/founderos-research/agentree/internal/tui/wizard.go)
- [/tmp/founderos-research/agentree/cmd/create.go](/tmp/founderos-research/agentree/cmd/create.go)

Borrow:

- fast TUI/bootstrap ergonomics for worktree creation

From `Dorothy`:

- [/tmp/founderos-research/Dorothy/src/components/AgentWorld](/tmp/founderos-research/Dorothy/src/components/AgentWorld)

Borrow:

- only if desired later: richer control-center world view

## P3 — Hosted/Cloud Convenience Layer

### Why this is P3

This matters for monetization and convenience, but it should not drive the OSS-core architecture.

### Primary donor repos

- `OpenHands/OpenHands` — `selective`
- `ComposioHQ/composio` — `selective`
- `withoneai/pica` — `architecture-only`

### What to borrow

From `OpenHands`:

- app-server/service separation
- sandbox abstractions
- hosted GUI/service layering

From `Composio`:

- optional managed provider integration layer
- typed provider/toolkit exposure

From `Pica`:

- only the architecture for hosted OAuth/unified action services

### Rule

- do not let hosted convenience drive FounderOS core shape too early

## P3 — Org/Collaboration/Security Hardening

### Why this is P3

Important later, especially if FounderOS becomes hosted/team-based, but it is not the first-order differentiator for the OSS release.

### Primary donor repos

- `OpenHands/OpenHands` — `architecture-only/selective`
- `temporalio/temporal` — `architecture-only`
- `gitbutlerapp/gitbutler` — `architecture-only`

### What to borrow

From `OpenHands`:

- org/service/storage layering concepts from hosted/server split
- collaboration boundaries at the service layer

From `Temporal`:

- update validation, state machine rigor, worker versioning concepts

From `GitButler`:

- safer timeline/undo/oplog mental model for higher-stakes operations

## Coverage Status and Confidence

### What is covered well in this pass

I am confident that the main relevant GitHub surface has been covered across these layers:

- research / brainstorming / validation
- debate / tournament mechanics
- PRD / spec / contract generation
- execution orchestration and reaction loops
- worktree/runtime/session management
- proof/evidence/audit patterns
- founder/operator shell UX
- Telegram/Slack remote-control bridges
- OSS onboarding/install

That is enough to say:

- the current donor set is strong
- the major obvious categories are covered
- the important borrowable patterns are now mapped feature-by-feature

### What I would **not** claim

I would **not** claim this is “100% every useful repo on GitHub”.

That would be dishonest for two reasons:

1. GitHub is too large and moving too fast to make that guarantee.
2. There is always a long tail of niche repos that may contain one good idea, but are not worth treating as primary donors.

### What I can claim honestly

I can claim this:

- the research is now **materially complete enough to guide implementation**
- the major donor classes are covered
- the strongest reusable repositories have been inspected directly
- the later-phase uncertainty is explicitly marked instead of being smuggled in as fake certainty

### Remaining uncertainty

The remaining uncertainty is mostly in these areas:

- later-phase hosted/cloud layers
- niche founder-workflow repos that may contain one-off UX ideas
- new repos that could appear after this research snapshot

That is why:

- `P0/P1` should be treated as high-confidence implementation guidance
- `P2` is solid but somewhat more optional
- `P3` is intentionally lower-certainty and more architecture-driven

## Additional Repos Added In This Pass

These were not in the earlier matrix as primary anchors, but are useful and now verified.

### `BMAD-METHOD`

- License: MIT
- Role: installer, module packaging, workflow-map UX
- Status: strong secondary donor

### `agent.md`

- License: MIT
- Role: repo-local instruction standard
- Status: strong secondary donor, especially for `Execution Brief v2` + hierarchical instructions

### `OpenHands`

- License: MIT outside `enterprise/`
- Role: local GUI + app server + event/conversation separation
- Status: secondary donor, especially for local GUI/service boundaries and PR artifact cleanup

### `agentree`

- License: MIT
- Role: lean worktree bootstrap donor
- Status: secondary donor

### `par`

- License: MIT
- Role: global worktree/session management donor
- Status: secondary donor

## Repos That Stay Restricted Or Non-Core

### `gitbutler`

- license is not plain MIT
- keep for architecture only

### `remote-agentic-coding-system`

- `CC BY-NC-SA 4.0`
- reject as a code donor for core FounderOS work

### `slavingia/skills`

- useful inspiration
- not needed as a primary donor after the stronger verified founder-skill repos were inspected

### `ncklrs/startup-os-skills`

- no strong license/borrow signal surfaced in the earlier pass
- keep as secondary inspiration only

## Recommended Build Order

1. `Execution Brief v2`
2. Reaction bus + approval loop
3. Proof-of-work bundle + evidence graph
4. Durable state / resume semantics
5. Unified FounderOS shell
6. One-command install
7. Quorum research artifact upgrade
8. Tracker ingest
9. Telegram/Slack bridge
10. Worktree/runtime hardening
11. Founder context + skill packs

## Best Borrow Set Per Major Area

### Best donors for Quorum

- `gpt-researcher`
- `open_deep_research`
- `VettIQ`
- `startup-skill`
- `DebateLLM`

### Best donors for Autopilot

- `agent-orchestrator`
- `trigger.dev`
- `inngestgo`
- `samples-go`
- `git-worktree-runner`
- `agtx`
- `ccmanager`

### Best donors for FounderOS shell

- `Dorothy`
- `get-shit-done`
- `gstack`
- `OpenHands`
- `Untether`

### Best donors for OSS packaging

- `BMAD-METHOD`
- `spec-kit`
- `startup-skill`
- `agent.md`

## Final Verdict

FounderOS does not need one magical donor repo.

It needs a disciplined combination of:

- `spec-kit + symphony + PRD-MCP-Server` for the contract layer
- `agent-orchestrator + trigger.dev + inngestgo + Temporal samples` for the reaction/resume layer
- `Dagster + Kestra + Symphony + OpenHands + Sleepless Agent` for evidence/proof
- `Dorothy + get-shit-done + gstack + OpenHands` for the shell
- `Untether + Takopi + Sleepless Agent` for remote operator control
- `git-worktree-runner + agtx + ccmanager + agentree + par` for runtime/worktree safety
- `gpt-researcher + open_deep_research + VettIQ + startup-skill + DebateLLM` for Quorum
- `BMAD + spec-kit + agent.md` for OSS productization

That combination is enough to make FounderOS feel like a real product on first open-source release, without turning it into a clone of any single repo.
