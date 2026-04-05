# FounderOS — GitHub Landscape, Killer Features, and Product Roadmap

Snapshot date: `2026-03-31`

## Executive Verdict

`FounderOS` does not have one clean, single direct competitor in open source.

It competes with a stack of products across layers:

- upstream ideation / research systems
- spec / workflow contract systems
- coding-agent orchestration systems
- integration / action platforms

That is good news.

It means `FounderOS` is not just "another Paperclip" or "another coding-agent dashboard" unless we accidentally narrow it down into that.

The strongest FounderOS shape is still:

- `Quorum` decides what to build and why
- `Execution Brief` turns that decision into structured execution intent
- `Autopilot` executes, governs, pauses, resumes, audits, and escalates
- `FounderOS` gives the founder one operating surface across all of that

The market already validates every one of those layers separately.
The opportunity is not to copy one repo.
The opportunity is to unify the layers into one founder-native workflow.

## What FounderOS Already Is

Based on the current internal docs:

- [CURRENT_STATUS.md](/Users/martin/Desktop/Projects/FounderOS/docs/CURRENT_STATUS.md)
- [SYSTEM_ARCHITECTURE.md](/Users/martin/Desktop/Projects/FounderOS/docs/SYSTEM_ARCHITECTURE.md)

FounderOS already has:

- a real upstream intelligence layer in `Quorum`
- a real downstream execution/control plane in `Autopilot`
- a real bridge via `Execution Brief`

That means the remaining gap is mostly:

- product convergence
- shared data model
- unified shell
- clearer mode boundaries
- better external integration surfaces

It is not "invent the whole system from zero."

## Competitive Landscape by Layer

## 1. Upstream Research, Brainstorming, and Deliberation

### BMAD Method

Repo: [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)

What it validates:

- people want structured AI-assisted product planning, not only coding
- multi-persona workflows are valuable
- one-command install matters for OSS adoption
- open-source community around planning frameworks is real

What is interesting:

- "specialized agents"
- "party mode"
- "complete lifecycle"
- `npx bmad-method install`

What to borrow:

- packaging discipline
- one-command installer
- modular workflow packs
- explicit guided next-step UX

What not to copy:

- FounderOS should not become "a prompt framework with personas"
- BMAD is stronger on planning templates than on governed execution

### GPT Researcher

Repo: [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)

What it validates:

- deep-research workflows are a real OSS category
- planner/executor/publisher split works
- users value factual reports with citations, not just chat

What is interesting:

- planner + execution agent pattern
- report generation as first-class output
- citations and source tracking

What to borrow:

- stronger research artifact generation upstream in Quorum
- citation/source-pack output as part of debate/tournament results
- "report as deliverable", not just raw chat transcripts

What not to copy:

- FounderOS is broader than deep research
- GPT Researcher is a layer, not the whole founder workflow

### Open Deep Research

Repo: [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)

What it validates:

- configurable research agents with MCP are a real pattern
- plan-and-execute plus human-in-the-loop planning is still valuable
- parallel researchers + supervisor architecture is practical

What is interesting:

- MCP-aware research stack
- explicit workflow vs multi-agent implementations
- human feedback on report plans

What to borrow:

- founder-facing "approve the research plan before execution" step
- better structured research-plan artifact in Quorum
- configurable provider/tool routing for research modes

What not to copy:

- FounderOS should not collapse into a research app with execution bolted on later

## 2. Spec / Workflow Contract Layer

### OpenAI Symphony

Repo: [openai/symphony](https://github.com/openai/symphony)

This is one of the most relevant references.

What it validates:

- issue-driven orchestration is real
- a repo-local workflow contract is powerful
- proof-of-work artifacts are becoming expected
- local plus distributed worker execution matters

Important ideas:

- `WORKFLOW.md` as the workflow contract
- YAML front matter + Markdown body
- tracker-driven runs
- local worker + SSH worker modes
- optional dashboard / observability server

What to borrow:

- a stronger `Execution Brief` file format
- proof-of-work bundle per completed story/run
- optional remote worker support later
- repo-local workflow contract stored with the codebase

What not to copy:

- FounderOS should not become Linear-first or tracker-first
- Symphony starts later in the funnel than FounderOS should

### GitHub Spec Kit

Repo: [github/spec-kit](https://github.com/github/spec-kit)

What it validates:

- spec-driven development is now mainstream enough to matter
- the market wants reproducible product-building workflows instead of pure vibe coding

What to borrow:

- stronger spec lifecycle
- project constitution / principles
- explicit spec generation before code execution
- clean installer / bootstrap flow

What not to copy:

- FounderOS already has `Execution Brief`; do not replace it with generic spec-kit vocabulary
- instead, strengthen your own artifact into a richer founder-native contract

### agent.md

Repo: [agentmd/agent.md](https://github.com/agentmd/agent.md)

What it validates:

- repo-local agent instructions need standardization
- hierarchical project guidance for agents is valuable

What to borrow:

- support for repo-level founder/agent operating instructions
- hierarchical guidance model
- merge of global + local + subsystem instructions

What not to copy:

- do not let `AGENT.md` become the whole contract
- it should complement FounderOS, not define it

## 3. Execution and Control Plane

### Composio Agent Orchestrator

Repo: [ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator)

This is the strongest direct `Autopilot` competitor/reference found in GitHub for the execution layer.

What it validates:

- parallel git-worktree agent orchestration is a real category
- dashboard-first orchestration with autonomous feedback routing is valuable
- plugin slots are a practical architecture, not just theory

What is strong:

- reaction-driven development
- CI/review feedback routing
- eight plugin slots
- tracker/runtime/agent agnosticism
- one-command startup

What to borrow:

- reaction bus
- tracker adapters
- notifier adapters
- plugin-slot clarity
- better auto-generated project config

What not to copy:

- do not let FounderOS identity collapse into "parallel coding agents in worktrees"
- Autopilot is one layer of FounderOS, not the whole product

### OpenHands

Repo: [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands)

What it validates:

- the market understands the split between SDK, CLI, local GUI, cloud, enterprise
- cloud and local can coexist
- integrations and collaboration features become source-available upsell layers

What to borrow:

- explicit product surface split:
  - engine/SDK
  - local CLI
  - local GUI
  - hosted cloud
- clearer path from OSS core to hosted convenience layer

What not to copy:

- FounderOS should not present itself only as "AI-driven development"
- that undersells the upstream founder decision layer

## 4. Integration and Action Layer

### Composio

Repo: [ComposioHQ/composio](https://github.com/ComposioHQ/composio)

What it validates:

- integration hubs are becoming a real infrastructure layer for agent systems
- users do not want to hand-build every connector

What is interesting:

- large toolkit/integration surface
- authentication
- context management
- Rube MCP server

What to borrow:

- the idea of an optional integration backend
- search/action abstraction over many tools
- auth/connectors as pluggable provider layer

What not to copy:

- do not make FounderOS dependent on a huge external integration platform in core OSS mode

### Pica

Repo: [withoneai/pica](https://github.com/withoneai/pica)

What it validates:

- there is demand for one integration hub for agent actions

But the important warning is explicit in their own README:

- the community edition is no longer actively maintained
- latest product is private and cloud-hosted
- the repo is GPL-3.0

What to borrow:

- architecture ideas only
- optional connector-hub model for hosted FounderOS later

What not to copy:

- do not build FounderOS core on top of this repo
- do not casually copy GPL code into your core without deliberate licensing choice

## The Real FounderOS Differentiator

If you copy too much from the execution repos, FounderOS becomes:

- another coding-agent orchestrator
- another issue runner
- another control plane

That would be a mistake.

The real differentiator is:

`FounderOS begins before the issue exists.`

It owns the founder workflow:

1. explore options
2. research
3. debate
4. compare
5. select a winner
6. convert it into execution intent
7. execute with guardrails
8. govern and intervene
9. loop back into strategy

That upstream half is what separates you from:

- Paperclip
- Symphony
- OpenHands
- Agent Orchestrator

Those systems mostly start after "what should we build?" is already settled.

FounderOS should own that earlier decision boundary.

## What the Market Has That FounderOS Still Needs

Below is the gap list that came out of the research.

## P0: Must-Have to Become a Serious FounderOS Product

### 1. Clear top-level mode separation

FounderOS needs explicit product modes:

- Explore
- Decide
- Brief
- Execute
- Govern

Right now the architecture implies this, but the product boundary is still too fuzzy.

Why it matters:

- prevents FounderOS from feeling like "Quorum glued to Autopilot"
- gives users a mental model
- keeps the ideation layer from disappearing behind orchestration screens

### 2. `Execution Brief` must become a stronger versioned contract

Borrow from `WORKFLOW.md`, `spec-kit`, and `AGENT.md`, but do not replace your concept.

Needed upgrades:

- stable schema
- repo-local persisted artifact
- revision history
- principles / constraints / budgets / approvals policy / success criteria
- optional generated story set

Why it matters:

- this becomes the founder-to-execution handshake
- it is the most unique artifact in your system

### 3. Reaction bus / event routing

This is the clearest missing execution-plane feature relative to Agent Orchestrator.

Examples:

- CI failed -> attach logs and route to responsible story/agent
- PR review requested changes -> route exact comments back to story owner
- approval granted -> resume relevant run automatically
- budget exhausted -> auto-pause and escalate

Why it matters:

- closes the loop between work and reality
- removes the need for human forwarding
- makes execution genuinely autonomous instead of "autonomous until external feedback appears"

### 4. Proof-of-work bundle

Every finished run/story should emit a compact, structured bundle:

- what changed
- tests run
- CI status
- artifacts produced
- open risks
- operator summary

Why it matters:

- better trust
- better dashboard visibility
- easier human-in-the-loop review
- stronger audit trail

### 5. Issue/tracker ingestion

FounderOS should stay `brief-first`, but it should also ingest:

- GitHub Issues
- Linear
- later Jira

Why it matters:

- external work should be able to enter the execution plane
- this expands adoption without changing the core identity

### 6. One-command install and clean bootstrap

This is non-negotiable for OSS adoption.

BMAD, OpenHands, Spec Kit, and Agent Orchestrator all validate this.

FounderOS needs:

- one-command install
- local-first boot
- BYOK flow
- minimal guided setup

Why it matters:

- if install is painful, stars and trials die
- this matters more than another architecture refactor

## P1: High-Value Features After P0

### 7. Typed plugin/provider slots

Not a giant plugin marketplace yet.
Just clear typed slots.

Recommended slots:

- research provider
- execution agent provider
- runtime provider
- tracker provider
- notifier provider
- integration/action provider
- artifact/storage provider

Why it matters:

- keeps FounderOS extensible
- avoids hardcoding every external dependency

### 8. Remote operator bridge

Not just one-way notifications.

Needed:

- Telegram or Slack bridge
- approve / reject / resume / pause
- short status digests
- escalation requests

Why it matters:

- strong "sleep while the system works" experience
- high leverage for founders

### 9. Research artifact quality upgrade in Quorum

Borrow from GPT Researcher / Open Deep Research.

Needed:

- citations
- source packs
- better condensed executive outputs
- clearer comparison between options

Why it matters:

- founder decisions need confidence signals
- makes Quorum outputs more reusable than chats

### 10. Shared initiative/company/project data model

This is the convergence layer.

Needed:

- one persistent initiative object
- one project/workspace object
- one execution history across Quorum and Autopilot

Why it matters:

- removes product split
- enables true FounderOS continuity

## P2: Strategic Features Later

### 11. Distributed / remote worker support

Borrow from Symphony's SSH-worker idea.

Useful later for:

- heavier parallelism
- team environments
- dedicated worker machines

Not urgent for first FounderOS OSS release.

### 12. Hosted convenience layer

Pattern validated by OpenHands:

- OSS local mode
- cloud convenience mode
- later enterprise/self-host mode

Why it matters:

- clean business model path without corrupting OSS core

### 13. Optional integration hub backend

Composio/Pica-style action layer as optional provider, not core dependency.

Why it matters:

- faster external actions later
- lets hosted FounderOS become more powerful without forcing SaaS dependency in OSS mode

## What Not To Do

## 1. Do not turn FounderOS into a Paperclip clone

If you over-focus on:

- budgets
- approvals
- roles
- guardrails
- issue execution only

you lose the upstream founder-decision advantage.

## 2. Do not rewrite the product around a generic integration hub

Connector platforms are useful, but they are not your identity.

## 3. Do not overbuild a plugin system before the core modes are clean

If the core founder workflow is unclear, plugins only create more surface area and confusion.

## 4. Do not market FounderOS as only a coding-agent tool

That puts you in a crowded category where the strongest identity belongs to:

- OpenHands
- Agent Orchestrator
- Symphony

FounderOS should market the higher-level workflow:

- idea -> decision -> brief -> execution -> governance

## 5. Do not hide the big visual founder shell

FounderOS should have:

- a strong dashboard
- visible workflow state
- decision artifacts
- execution status
- intervention controls

CLI and Telegram are support surfaces, not the whole product.

## Recommended FounderOS Product Shape

The best shape after this research is:

### FounderOS core

- visual founder operating system
- local-first
- open-source
- BYOK

### Main workflow

1. founder enters ideas, repos, constraints, or opportunity space
2. Quorum researches / debates / tournaments / compares
3. winner becomes `Execution Brief`
4. Founder approves or edits the brief
5. Autopilot ingests and executes
6. Founder governs through approvals, issues, budgets, sessions, artifacts
7. outputs feed back into strategic layer

### Secondary surfaces

- CLI for power users
- Telegram/Slack for approvals and status
- optional hosted cloud later

## Priority Roadmap

## Phase 1: FounderOS product convergence

- define the top-level modes
- harden `Execution Brief` schema
- unify initiative/project/run identifiers across Quorum and Autopilot
- build cleaner artifact cards for research, brief, and execution proof

## Phase 2: Execution feedback loop hardening

- add reaction bus
- add tracker ingestion
- add proof-of-work bundles
- add operator escalation workflows

## Phase 3: OSS launch quality

- one-command install
- local-first bootstrap
- clean README and landing
- example project flows
- BYOK setup

## Phase 4: ecosystem and convenience

- typed provider/plugin slots
- remote operator bridge
- optional integration backends
- optional hosted convenience layer

## Best Verified Repos to Study Closely

These are the strongest verified references from this pass:

- [ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator)
- [openai/symphony](https://github.com/openai/symphony)
- [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands)
- [github/spec-kit](https://github.com/github/spec-kit)
- [agentmd/agent.md](https://github.com/agentmd/agent.md)
- [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)
- [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- [ComposioHQ/composio](https://github.com/ComposioHQ/composio)
- [withoneai/pica](https://github.com/withoneai/pica)

## Bottom Line

The research does not suggest "FounderOS is too broad, kill it."

It suggests something more useful:

`FounderOS is directionally right, but it now needs convergence, reaction loops, artifact discipline, and install/UX polish more than it needs another giant architectural rewrite.`

The winning move is:

- preserve the founder-decision layer as the identity
- steal the best execution-plane mechanics from orchestration repos
- strengthen `Execution Brief` into the core contract
- launch local-first OSS with a clean install and a strong visual shell

That is how FounderOS becomes a real product instead of just an ambitious architecture diagram.
