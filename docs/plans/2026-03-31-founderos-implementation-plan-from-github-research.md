# FounderOS — Implementation Plan From GitHub Research

Snapshot date: `2026-03-31`

Related docs:

- [2026-03-31-founderos-github-landscape-and-feature-roadmap.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-github-landscape-and-feature-roadmap.md)
- [2026-03-31-founderos-detailed-feature-borrowing-map.md](/Users/martin/multi-agent/docs/plans/2026-03-31-founderos-detailed-feature-borrowing-map.md)
- [2026-03-31-autopilot-priority-roadmap.md](/Users/martin/multi-agent/docs/plans/2026-03-31-autopilot-priority-roadmap.md)
- [CURRENT_STATUS.md](/Users/martin/Desktop/Projects/FounderOS/docs/CURRENT_STATUS.md)
- [SYSTEM_ARCHITECTURE.md](/Users/martin/Desktop/Projects/FounderOS/docs/SYSTEM_ARCHITECTURE.md)

## Goal

Turn `Quorum + Autopilot` into a real `FounderOS` product that feels complete on first open-source release.

The target is not:

- "yet another agent runner"
- "yet another issue bot"
- "yet another prompt framework"

The target is:

`idea -> research -> tournament -> brief -> execution -> governance -> feedback`

inside one founder-native system.

## Planning Rules

This implementation plan assumes:

- keep `Autopilot` execution-first architecture
- keep multi-account pool and provider rotation
- keep Quorum as upstream intelligence layer
- do not rewrite core in TypeScript
- do not make the system depend on a cloud integration hub
- do not ship raw, obviously incomplete OSS if a few focused phases can make it meaningfully stronger

## Verification Notes

This plan mixes:

- verified references from direct repo review
- candidate ideas surfaced by prior research notes

Use this confidence split:

- `Verified`: directly confirmed from repo/docs during current research
- `Candidate`: useful direction from prior research notes; validate before implementing

## Priority Table

| Priority | Initiative | Why It Matters | FounderOS Layer | Confidence |
|---|---|---|---|---|
| P0 | Strengthen `Execution Brief` into versioned contract | This is the bridge between Quorum and Autopilot and the most unique artifact in the system | Shared core | Verified |
| P0 | Add top-level product modes: Explore / Decide / Brief / Execute / Govern | Gives FounderOS a real product boundary instead of "two systems glued together" | Shared core/UI | Verified |
| P0 | Add reaction bus / event routing | Closes the loop from CI/reviews/approvals back into the right agent/run | Autopilot | Verified |
| P0 | Add proof-of-work bundles | Gives trust, auditability, and crisp operator review | Autopilot + UI | Verified |
| P0 | Add one-command local-first install | Critical for open-source adoption | Shared product | Verified |
| P1 | Add tracker ingestion (GitHub Issues / Linear) | Lets external work enter execution without changing identity | Autopilot | Verified |
| P1 | Upgrade Quorum research artifacts with citations/source packs | Makes founder decisions more reusable and trustworthy | Quorum | Verified |
| P1 | Add remote operator bridge (Telegram/Slack) | Enables real "sleep while it works" behavior | Autopilot + FounderOS | Verified |
| P1 | Add typed provider/plugin slots | Makes system extensible without giant rewrites | Shared core | Verified |
| P1 | Add validation/scoring pipelines for startup ideas | Improves tournament quality and founder-facing value | Quorum | Mixed |
| P2 | Add multi-model per story phase routing | Improves cost/performance and specialization | Autopilot | Candidate |
| P2 | Add distributed remote workers | Useful for heavy parallelism later | Autopilot | Verified |
| P2 | Add optional connector-hub provider | Useful later for hosted/cloud convenience | FounderOS Cloud | Verified |
| P2 | Add recurring maintenance / scheduled runs | Valuable but not core to first FounderOS release | Autopilot | Candidate |

## Phase 0 — Product Convergence Spec

This is the phase to do before more feature sprawl.

### Deliverables

- define the five FounderOS modes:
  - `Explore`
  - `Decide`
  - `Brief`
  - `Execute`
  - `Govern`
- define shared top-level entities:
  - `initiative`
  - `option`
  - `decision`
  - `execution_brief`
  - `execution_project`
  - `run`
  - `issue`
  - `approval`
- define handoff lifecycle:
  - idea created
  - options researched
  - winner selected
  - brief approved
  - execution started
  - issues surfaced
  - proof bundle emitted

### What To Borrow

- `WORKFLOW.md` / workflow contract idea from Symphony
- spec discipline from Spec Kit
- repo-local instruction hierarchy from `agent.md`

### What To Build

- `Execution Brief v2`
- shared entity map across Quorum and Autopilot
- explicit UI mode map

### Acceptance Criteria

- one document defines the canonical FounderOS lifecycle
- every feature added after this phase maps to one of the five modes
- no new feature lands without a clear place in that lifecycle

## Phase 1 — FounderOS Core Contract and Artifacts

## 1. Execution Brief v2

### Why

Right now this is the most valuable system bridge and the cleanest place to differentiate.

### Add

- stable schema
- human-readable Markdown form
- machine-readable structured form
- revision history
- research summary
- winner rationale
- assumptions
- constraints
- budgets
- approval policy
- success criteria
- recommended story breakdown
- attached source packs / evidence

### Borrow From

- Symphony `WORKFLOW.md`
- Spec Kit
- PRD-oriented open-source projects

### Deliverable

- one canonical `Execution Brief` artifact that Quorum emits and Autopilot consumes

## 2. Proof-of-Work Bundle

### Why

Autonomous systems without proof feel fake and unsafe.

### Add

- run summary
- changed files
- tests executed
- CI outcome
- review outcome
- unresolved risks
- operator notes
- links to relevant issues/approvals

### Borrow From

- Symphony proof-of-work pattern

### Deliverable

- every completed story/run generates a compact proof artifact

## 3. Research Artifact Upgrade

### Why

Quorum outputs need to be more than chat logs.

### Add

- citations
- source packs
- comparison matrices
- scoring rubrics
- recommendation summaries

### Borrow From

- GPT Researcher
- Open Deep Research

### Deliverable

- Quorum outputs reusable research artifacts that support downstream decisions

## Phase 2 — Execution Feedback Loop Hardening

## 4. Reaction Bus

### Why

This is the clearest gap versus stronger execution-plane repos.

### Events To Support First

- CI failed
- test failed
- review comment received
- approval granted
- approval denied
- budget exhausted
- run stalled
- worker crashed

### Required Behavior

- attach correct context
- route back to owning story/worker/run
- create/update issue when needed
- resume or pause automatically where policy allows

### Borrow From

- Agent Orchestrator reaction-driven development

### Deliverable

- event routing layer that closes loops automatically

## 5. Tracker Ingestion

### Why

FounderOS should stay brief-first, but also accept real external work sources.

### Add

- GitHub Issues ingest
- Linear ingest
- later Jira ingest

### Rules

- tracker items can become:
  - options for Quorum
  - execution inputs for Autopilot
  - linked issues inside an existing execution project

### Borrow From

- Symphony
- Agent Orchestrator
- OpenHands

### Deliverable

- external issues can start or update FounderOS execution without losing the FounderOS flow

## 6. Stall Watchdog and Escalation

### Why

Parallel agent systems die on silent stalls.

### Add

- idle/stuck detection upgrades
- auto-nudge
- escalation policy
- optional auto-approval for low-risk prompts
- safe retry categories

### Borrow From

- existing Autopilot stuck detection
- candidate patterns from agtx / ccmanager notes

### Deliverable

- fewer dead runs, less human babysitting

## Phase 3 — Founder-Facing Product UX

## 7. Five-Mode FounderOS Shell

### Why

This is what makes the product feel like FounderOS rather than two repos.

### UI Structure

- `Explore`: idea capture, repo/context intake, interest areas
- `Decide`: research, debate, tournaments, comparisons
- `Brief`: winning option, constraints, execution brief approval
- `Execute`: stories, runs, workers, worktrees, status
- `Govern`: approvals, issues, budgets, proof bundles, interventions

### Deliverable

- one coherent founder-native UX shell

## 8. Operator Bridge

### Why

Real founders need mobile/lightweight control surfaces.

### Add

- Telegram first
- later Slack
- approve/reject buttons
- pause/resume
- escalation digests
- concise proof notifications

### Borrow From

- your existing Telegram notifier
- candidate ideas from Untether-style bridge pattern

### Deliverable

- founder can govern the system without sitting in the dashboard all day

## 9. One-Command Install and Guided Bootstrap

### Why

Open-source adoption is mostly blocked by setup pain.

### Add

- one-command install
- BYOK onboarding
- guided provider setup
- example workspace/project
- sample founder flow

### Borrow From

- BMAD packaging discipline
- OpenHands OSS bootstrap clarity

### Deliverable

- FounderOS is easy to try locally without reading a book

## Phase 4 — Smart Quorum Upgrades

## 10. Idea Validation and Scoring Pipelines

### Why

To make the upstream layer genuinely useful, not just clever.

### Add

- startup idea scoring dimensions
- founder fit scoring
- market/problem severity scoring
- experiment recommendations
- cheap validation playbooks

### Candidate Sources

- startup-skill
- founder-skill repos
- idea-evaluation prompt systems
- validation pipelines like VettIQ

### Deliverable

- Quorum can do founder-quality screening, not only generic debate

## 11. Structured Tournament Improvements

### Why

Tournament quality is one of the signature FounderOS differentiators.

### Add

- explicit rubrics
- critique-improve rounds
- hybrid synthesis option
- side-by-side scorecards
- confidence / disagreement indicators

### Candidate Sources

- llm-tournament
- DebateLLM
- academic debate/tournament protocols

### Deliverable

- better decision quality and more legible winner selection

## Phase 5 — Extensibility and Cloud Readiness

## 12. Typed Provider / Plugin Slots

### Why

Extensibility matters, but only after the core workflow is stable.

### Recommended Slots

- research provider
- debate/tournament strategy provider
- execution agent provider
- runtime provider
- tracker provider
- notifier provider
- integration/action provider
- artifact/storage provider

### Borrow From

- Agent Orchestrator plugin-slot clarity

### Deliverable

- enough extensibility to evolve without giant rewrites

## 13. Optional Connector Hub

### Why

Helpful for hosted/cloud convenience later, not for core OSS identity.

### Candidates

- Composio-style provider
- Pica-style provider

### Rules

- optional only
- never required for local-first OSS mode
- never the identity of FounderOS

### Deliverable

- FounderOS Cloud can act in more systems without bloating core OSS

## 14. Distributed Workers

### Why

Useful later when teams want more parallelism.

### Borrow From

- Symphony SSH workers

### Deliverable

- remote execution pool for bigger workloads

## Suggested Order of Actual Build Work

| Step | Initiative | Why first |
|---|---|---|
| 1 | FounderOS lifecycle spec + entity map | Prevents feature sprawl |
| 2 | Execution Brief v2 | Core bridge artifact |
| 3 | Proof-of-work bundle | Immediate trust win |
| 4 | Reaction bus | Biggest Autopilot execution gap |
| 5 | Five-mode product shell | Makes it feel like one product |
| 6 | Quorum research artifact upgrade | Better decisions, better demos |
| 7 | One-command install | Required for OSS launch |
| 8 | Tracker ingest | Adoption and workflow expansion |
| 9 | Telegram operator bridge | High practical leverage |
| 10 | Plugin slots | Extensibility after identity is clear |

## What To Defer

Do not front-load these:

- giant plugin marketplace
- Electron desktop app
- full cloud product
- hundreds of third-party integrations
- generalized enterprise RBAC layer
- remote worker fleet management

They are not what makes FounderOS win early.

## What Makes FounderOS Best-In-Class

If this plan is executed well, FounderOS becomes strongest at:

- starting before the issue exists
- turning vague founder intent into structured execution
- preserving reasoning, evidence, and governance across the entire loop
- combining deep exploration with real execution

That is the unique category.

Not:

- just a coding-agent orchestrator
- just a research agent
- just a startup prompt kit

## Final Recommendation

For the next serious build push:

Focus on:

1. `Execution Brief v2`
2. `reaction bus`
3. `proof-of-work bundles`
4. `five-mode FounderOS shell`
5. `one-command OSS bootstrap`

That combination will do more to make FounderOS feel real than ten extra integrations.

## Coverage of the Prior Agent's "Must Add" List

This maps the concrete items from the earlier research pass into this plan.

| Prior suggestion | Included in this plan? | Where | Main reference |
|---|---|---|---|
| Telegram bridge | Yes | Phase 3, item 8 | Existing Autopilot Telegram notifier plus `remote-agentic-coding-system`; Untether remains a candidate lead |
| Reactions system | Yes | Phase 2, item 4 | Agent Orchestrator |
| Plugin architecture | Yes | Phase 5, item 12 | Agent Orchestrator |
| GitHub / Linear issue integration | Yes | Phase 2, item 5 | Symphony, Agent Orchestrator, OpenHands, `remote-agentic-coding-system` |
| Multi-agent per story with model specialization | Yes | Priority table `P2`; later execution refinement | `agtx` plus other execution repos |
| Auto-approval / stall watchdog | Yes | Phase 2, item 6 | Existing stuck detection plus ccmanager-style ideas |
| Proof of work | Yes | Phase 1, item 2 | Symphony |

So the ideas from the prior pass were not dropped.
What was missing in the earlier version was:

- explicit repo-by-repo borrowing notes
- license and copyability guidance
- lower-confidence repo leads called out separately

## Repo Borrow Matrix

This is the practical matrix for "what can we actually take".

- `Copy-safe`: MIT / Apache repo and conceptually safe to lift prompts, schemas, workflow shapes, or focused utility code
- `Selective copy`: open-source, but borrow bounded parts only; inspect for provider coupling or hidden assumptions
- `Architecture only`: use as design reference, not as code to pull into core

| Repo | URL | License | What to borrow | Copyability | Best fit |
|---|---|---|---|---|---|
| GPT Researcher | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | planner/executor/report flow, citation-first artifacts | Copy-safe | Quorum research artifacts |
| Open Deep Research | [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | MIT | supervisor/researcher pattern, MCP-aware research flow, human plan approval | Copy-safe | Quorum research engine |
| deep-research | [dzhng/deep-research](https://github.com/dzhng/deep-research) | MIT | very small iterative deep-research loop, recursive refinement pattern | Copy-safe | Quorum lightweight research mode |
| VettIQ | [Nirikshan95/VettIQ](https://github.com/Nirikshan95/VettIQ) | MIT | startup validation graph, market/competition/risk/advisor nodes, tool fallback routing | Selective copy | Quorum validation scenario |
| Startup Skill | [ferdinandobons/startup-skill](https://github.com/ferdinandobons/startup-skill) | MIT | startup-design, competitors, positioning, pitch skill packs and deliverable shape | Copy-safe | Quorum founder workflows |
| claude-skills-founder | [emotixco/claude-skills-founder](https://github.com/emotixco/claude-skills-founder) | MIT | 7-dimension idea scoring, product-brief and competitor-matrix prompts | Copy-safe | Quorum scoring and briefs |
| startup-founder-skills | [shawnpang/startup-founder-skills](https://github.com/shawnpang/startup-founder-skills) | MIT | founder-task skill library across product/growth/fundraising/ops | Copy-safe | FounderOS founder utility packs |
| startup-os-skills | [ncklrs/startup-os-skills](https://github.com/ncklrs/startup-os-skills) | MIT | modular startup skill taxonomy, install pattern | Copy-safe | FounderOS skill ecosystem |
| The Agentic Startup | [rsmdt/the-startup](https://github.com/rsmdt/the-startup) | MIT | `specify -> build` flow, startup-oriented command structure | Selective copy | Quorum -> Brief UX and OSS packaging |
| agentic_prd | [nanagajui/agentic_prd](https://github.com/nanagajui/agentic_prd) | MIT | multi-agent PRD generation flow | Copy-safe | Execution Brief generation |
| PRD-MCP-Server | [Saml1211/PRD-MCP-Server](https://github.com/Saml1211/PRD-MCP-Server) | MIT | MCP shape for PRD generation, CLI/Docker bootstrap patterns | Selective copy | Brief tooling, optional MCP |
| DebateLLM | [instadeepai/DebateLLM](https://github.com/instadeepai/DebateLLM) | Apache-2.0 | debate protocols, experiment structure, strategy variants | Copy-safe | Quorum debate/tournament upgrades |
| llm-tournament | [Dicklesworthstone/llm-tournament](https://github.com/Dicklesworthstone/llm-tournament) | MIT with provider rider | multi-round critique/improve/synthesize mechanics, tournament metrics | Selective copy | Quorum tournament refinement |
| AI Product Development Toolkit | [TechNomadCode/AI-Product-Development-Toolkit](https://github.com/TechNomadCode/AI-Product-Development-Toolkit) | MIT | phase-by-phase prompt structure: PRD, UX, MVP, testing | Copy-safe | FounderOS templates and guided flows |
| Agent Orchestrator | [ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) | MIT | reaction bus, plugin-slot model, tracker/runtime abstraction | Selective copy | Autopilot execution plane |
| agtx | [fynnfluegge/agtx](https://github.com/fynnfluegge/agtx) | Apache-2.0 | multi-session kanban TUI, per-phase agent routing, plugin TOML model, worktree + tmux orchestration, artifact polling | Selective copy | Autopilot runtime UX and multi-agent phase routing |
| Symphony | [openai/symphony](https://github.com/openai/symphony) | Apache-2.0 | `WORKFLOW.md`, proof-of-work bundle, tracker-driven run contract | Selective copy | Autopilot plus Execution Brief v2 |
| OpenHands | [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | MIT core, source-available enterprise dir | OSS/local/cloud packaging, SDK/CLI/GUI split | Architecture only | FounderOS product packaging |
| CCManager | [kbwo/ccmanager](https://github.com/kbwo/ccmanager) | MIT | session state detection, worktree hooks, session copying, auto-approval ideas | Selective copy | Autopilot operator/runtime UX |
| MassGen | [massgen/MassGen](https://github.com/massgen/MassGen) | Apache-2.0 | plan-and-execute flow, two-tier workspaces, AGENTS/CLAUDE discovery, hooks, execution traces | Selective copy | Autopilot runtime and workspace evolution |
| Remote Agentic Coding System | [coleam00/remote-agentic-coding-system](https://github.com/coleam00/remote-agentic-coding-system) | CC BY-NC-SA 4.0 | Telegram/GitHub remote control, persistent sessions, conversation/session table model, remote interaction flows | Reject for core borrowing | Telegram/GitHub operator bridge reference only |
| slavingia/skills | [slavingia/skills](https://github.com/slavingia/skills) | No clear license surfaced in visible repo page during this pass | founder journey skill structure, Minimalist Entrepreneur progression, command taxonomy | Architecture only | FounderOS founder guidance and skill taxonomy |
| Composio | [ComposioHQ/composio](https://github.com/ComposioHQ/composio) | Open-source repo, but provider-centric | search/action abstraction, auth/provider ideas | Architecture only | Optional future integration layer |
| Pica | [withoneai/pica](https://github.com/withoneai/pica) | GPL-3.0, deprecated community edition | connector-hub architecture only | Architecture only | Optional future cloud connector provider |

## Second-Pass Verified Additions

These repos were verified in the second research pass and are strong enough to add explicitly.

| Repo | URL | License | What to borrow | Copyability | Best fit |
|---|---|---|---|---|---|
| Dorothy | [Charlie85270/Dorothy](https://github.com/Charlie85270/Dorothy) | MIT | desktop operator console, Super Agent coordination, Kanban auto-assignment, Telegram/Slack/GitHub/JIRA control surfaces, MCP-based orchestration | Selective copy | FounderOS shell and operator UX |
| Untether | [littlebearapps/untether](https://github.com/littlebearapps/untether) | MIT | Telegram bridge, inline approvals, live progress streaming, plan mode, budgets/cost tracking, file transfer, plugin system | Selective copy | Telegram operator bridge |
| Takopi | [banteg/takopi](https://github.com/banteg/takopi) | MIT | lean Telegram bridge core, stateless resume, voice notes, scheduled messages, plugin entry points, parallel runs | Selective copy | Telegram bridge core |
| Sleepless Agent | [context-machine-lab/sleepless-agent](https://github.com/context-machine-lab/sleepless-agent) | MIT | Slack ChatOps, persistent task queue, isolated workspaces, 24/7 daemon patterns | Selective copy | Slack operator bridge |
| LangGraph | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | MIT | durable execution, state inspection/editing, persistent memory, resumable graphs | Architecture plus bounded copy | Quorum and Autopilot state model |
| Temporal | [temporalio/temporal](https://github.com/temporalio/temporal) | MIT | signals, queries, task queues, versioning, workflow durability patterns | Architecture only | Autopilot control-plane semantics |
| Inngest Go SDK | [inngest/inngestgo](https://github.com/inngest/inngestgo) | MIT | `WaitForEvent` semantics, debounce, batching, rate limiting, event correlation patterns | Architecture plus bounded copy | Reaction bus |
| Trigger.dev | [triggerdotdev/trigger.dev](https://github.com/triggerdotdev/trigger.dev) | Apache-2.0 | idempotent run model, metadata/tags, realtime updates, waits/schedules | Architecture plus bounded copy | Run/event system |
| Kestra | [kestra-io/kestra](https://github.com/kestra-io/kestra) | Apache-2.0 | typed outputs/artifacts, trigger definitions, Git-backed workflow versioning | Architecture only | Proof bundles and workflow artifacts |
| Dagster | [dagster-io/dagster](https://github.com/dagster-io/dagster) | Apache-2.0 | metadata graph, lineage, centralized observability | Architecture only | FounderOS evidence graph |
| GitButler | [gitbutlerapp/gitbutler](https://github.com/gitbutlerapp/gitbutler) | MIT | reversible branch timeline, parallel branch workflows, review-aware branch handling | Selective copy | Worktree/attempt timeline safety |
| git-worktree-runner | [coderabbitai/git-worktree-runner](https://github.com/coderabbitai/git-worktree-runner) | MIT | worktree bootstrap, env/config copying, post-create hooks, machine-readable status | Selective copy | Repo/worktree adapters |
| gstack | [garrytan/gstack](https://github.com/garrytan/gstack) | MIT | founder-operator shell commands, sprint rhythm `Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect` | Copy-safe | FounderOS shell |
| get-shit-done | [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) | MIT | codebase mapping, roadmap/context/state artifacts, phase capture from idea to plan | Copy-safe | Brief and founder workflow |

## Secondary Leads Worth Validating Further

These came from earlier notes or looser scans and are directionally interesting, but I have not elevated them to the main build plan with the same confidence as the matrix above:

- `ncklrs/startup-os-skills`
- `some Dorothy-adjacent desktop UX variants not yet verified beyond the primary Dorothy repo`

They may still contain useful UX or workflow ideas, but I would not use them as primary implementation anchors until they are reviewed directly.

## Practical Copying Rules

If the goal is "not just inspiration, but actual code reuse", use this rule set:

### Green light

- MIT / Apache skill packs
- prompt templates
- workflow schemas
- bounded orchestration utilities
- CLI/bootstrap scripts
- report/spec generators

### Yellow light

- repos with provider-specific riders
- repos tightly coupled to one backend
- code that assumes a different runtime model
- orchestration layers that embed foreign identity into the product

### Red light

- GPL code into FounderOS core without deliberate licensing choice
- large copied subsystems that drag foreign architecture into core
- cloud-hosted product shells copied into local-first OSS
