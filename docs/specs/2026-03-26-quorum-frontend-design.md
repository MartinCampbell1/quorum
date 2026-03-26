# Quorum — Frontend Design Spec

## Overview

Web frontend for the multi-agent orchestration engine. Connects to the existing
backend API at localhost:8800/orchestrate/*. Users create orchestration sessions
through a 3-step wizard, watch agents interact in real-time chat, and can
intervene at any point.

## Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS 4
- **Icons:** Lucide React (SVG, no emoji)
- **Fonts:** Fira Sans (UI) + Fira Code (monospace/code)
- **State:** React hooks + SWR for API polling
- **Theme:** Dark (OLED) + Light mode with toggle

## Design System

### Colors

| Token | Dark | Light |
|-------|------|-------|
| bg-primary | #09090B | #FAFAFA |
| bg-secondary | #0C0C0E | #F4F4F5 |
| bg-card | #12121A | #FFFFFF |
| border | #1C1C1F | #E4E4E7 |
| border-hover | #3F3F46 | #A1A1AA |
| text-primary | #FAFAFA | #09090B |
| text-secondary | #A1A1AA | #52525B |
| text-muted | #52525B | #A1A1AA |
| accent | #2563EB | #2563EB |
| accent-hover | #3B82F6 | #1D4ED8 |
| cta | #F97316 | #EA580C |
| success | #4ADE80 | #16A34A |
| error | #EF4444 | #DC2626 |

All colors as semantic CSS variables. Dark mode default, Light mode via
`data-theme="light"` on html element.

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Page title | Fira Sans | 24px | 600 |
| Section heading | Fira Sans | 16px | 600 |
| Body text | Fira Sans | 14px | 400 |
| Small text | Fira Sans | 12px | 400 |
| Code/mono | Fira Code | 12px | 400 |
| Agent label | Fira Code | 11px | 500 |
| Badge | Fira Code | 10px | 500 |

### Spacing

4px base grid. Standard gaps: 4, 8, 12, 16, 20, 24, 32, 48px.

### Border Radius

- Cards, panels: 12px
- Buttons, inputs: 8px
- Badges, tags: 4px
- Avatars: 50%

### Shadows (Light mode only)

- Card: 0 1px 3px rgba(0,0,0,0.08)
- Dropdown: 0 4px 12px rgba(0,0,0,0.1)
- Modal: 0 8px 24px rgba(0,0,0,0.12)

Dark mode uses border instead of shadow.

## Layout

Three-column layout:

```
┌──────┬──────────────┬─────────────────────────────┐
│ 52px │   240px      │         flex: 1              │
│      │              │                              │
│ Icon │  Sessions    │   Main Area                  │
│ Nav  │  List        │   (wizard / chat / settings) │
│      │              │                              │
│      │              │                              │
│      │              │                              │
│ ──── │              │                              │
│theme │              │                              │
│toggle│              │                              │
└──────┴──────────────┴─────────────────────────────┘
```

### Left Icon Bar (52px)

Vertical icon navigation:
- Chat (message-square) — active: accent bg
- History (clock) — session history
- Settings (sliders) — role prompts, preferences
- Bottom: theme toggle (sun/moon)

### Sessions Panel (240px)

- Header: "Sessions" label + "New" button
- List of sessions: title, mode badge, timestamp, status indicator
- Active session highlighted with accent left border
- Click to switch between sessions

### Main Area (flex)

Content depends on current view:
- **New Session Wizard** — 3-step flow
- **Active Chat** — message list + input
- **Session History** — past sessions browser
- **Settings** — role prompts editor

## Screens

### Screen 1: New Session Wizard

Three steps with a horizontal stepper at top.

**Step 1 — Choose Mode:**
Grid of 7 mode cards (2 columns on narrow, 3 on wide).
Each card:
- SVG icon (top)
- Mode name (bold)
- One-line description
- Click to select, accent border appears
- "Next" button at bottom

**Step 2 — Configure Agents:**
List of agent slots for the selected mode.
Each slot:
- Role label (e.g. "Director", "Worker 1")
- Provider dropdown: Claude / Gemini / Codex / MiniMax
- Optional: expand to edit system prompt (textarea)
- Default agents pre-filled from backend /orchestrate/modes

**Step 3 — Task & Launch:**
- Large textarea: "Describe your task"
- Config options (collapsible):
  - max_rounds / max_iterations (number input)
- "Launch" button (CTA color #F97316)
- Summary sidebar: selected mode + agents

### Screen 2: Chat View

Header:
- Session title (editable inline)
- Mode badge
- Status badge (running / completed / failed)
- Elapsed time (Fira Code)

Message list:
- Each message is a card with:
  - Agent color dot + name + role (Fira Code, 11px)
  - Phase label (e.g. "round_1_pro", "voting_round_2")
  - Message content (Fira Sans, 14px)
  - Timestamp (Fira Code, muted)
- Agent colors:
  - Claude: #2563EB (blue)
  - Codex: #F97316 (orange)
  - Gemini: #8B5CF6 (purple)
  - MiniMax: #6B7280 (gray)
  - System: #52525B (muted)
  - User: #4ADE80 (green)
- Left border colored by agent

Input bar (bottom, fixed):
- Text input: "Intervene in conversation..."
- Send button
- Disabled when session is completed/failed

### Screen 3: Session History

Table/list view of past sessions:
- Mode icon + title
- Status badge
- Duration
- Agent count
- Timestamp
- Click to open chat view (read-only)

### Screen 4: Settings

Sections:
- **Default Prompts per Role** — list of role names with editable textareas
- **Theme** — dark/light toggle (also in sidebar)
- **Gateway** — URL (default localhost:8800), connection status indicator

## API Integration

All calls to `http://localhost:8800/orchestrate/*`:

| Endpoint | Usage |
|----------|-------|
| GET /orchestrate/modes | Populate wizard step 1 |
| POST /orchestrate/run | Launch session from wizard |
| GET /orchestrate/session/{id} | Poll session status + messages (SWR, 2s interval while running) |
| GET /orchestrate/sessions | Session history list |
| POST /orchestrate/session/{id}/message | Send user intervention |
| GET /orchestrate/agents | Show available providers + pool status |

Polling strategy:
- While status="running": poll every 2 seconds
- When status="completed" or "failed": stop polling
- SWR with refreshInterval for automatic revalidation

## File Structure

```
~/multi-agent/frontend/
  package.json
  next.config.js
  tailwind.config.js

  app/
    layout.tsx              # Root layout, font loading, theme provider
    page.tsx                # Main app (3-column layout)
    globals.css             # CSS variables, Tailwind imports

  components/
    sidebar/
      icon-bar.tsx          # Left icon navigation
      session-list.tsx      # Sessions panel
      session-item.tsx      # Individual session entry
    wizard/
      wizard.tsx            # 3-step wizard container
      step-mode.tsx         # Step 1: mode selection
      step-agents.tsx       # Step 2: agent configuration
      step-task.tsx         # Step 3: task input + launch
      mode-card.tsx         # Individual mode card
    chat/
      chat-view.tsx         # Chat container
      message.tsx           # Single message component
      input-bar.tsx         # Intervention input
      chat-header.tsx       # Session title + badges
    settings/
      settings-view.tsx     # Settings page
    common/
      badge.tsx             # Status/mode badges
      button.tsx            # Button variants
      theme-toggle.tsx      # Dark/light switch

  hooks/
    use-session.ts          # SWR hook for session polling
    use-sessions.ts         # SWR hook for session list
    use-modes.ts            # SWR hook for available modes
    use-theme.ts            # Theme state + localStorage

  lib/
    api.ts                  # API client (fetch wrapper)
    types.ts                # TypeScript types matching backend models
    constants.ts            # Agent colors, mode icons mapping
```

## Accessibility

- All interactive elements: min 44x44px touch target
- Focus rings: 2px accent color outline
- Color contrast: 4.5:1 minimum (both themes)
- Keyboard navigation: tab order matches visual order
- aria-labels on icon-only buttons
- prefers-reduced-motion respected
- Screen reader: message agent names announced

## Responsive Behavior

- Desktop (>1024px): full 3-column layout
- Tablet (768-1024px): collapsible sessions panel (hamburger)
- Mobile (<768px): single column, bottom tab bar replaces icon sidebar

## Performance

- SWR for data fetching with stale-while-revalidate
- Virtualized message list for sessions with 50+ messages
- Code-split wizard/settings (dynamic imports)
- Font preload for Fira Sans 400/600 and Fira Code 400

## Anti-Patterns to Avoid

- No emoji as icons (Lucide SVG only)
- No placeholder-only labels on inputs
- No color-only status indicators (always icon + text)
- No horizontal scroll
- No layout shift on theme toggle
- No blocking animations
