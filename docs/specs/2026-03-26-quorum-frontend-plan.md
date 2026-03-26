# Quorum Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js web frontend ("Quorum") for the multi-agent orchestration engine with 3-step wizard, real-time chat, session history, and dark/light theme.

**Architecture:** Next.js 15 App Router with Tailwind CSS. SWR for API polling. Three-column layout: icon nav + sessions list + main area. Backend at localhost:8800.

**Tech Stack:** Next.js 15, React 19, Tailwind CSS 4, SWR, Lucide React, Fira Sans + Fira Code fonts

---

### Task 1: Scaffold Next.js project

**Files:**
- Create: `/Users/martin/multi-agent/frontend/package.json`
- Create: `/Users/martin/multi-agent/frontend/next.config.js`
- Create: `/Users/martin/multi-agent/frontend/tailwind.config.js`
- Create: `/Users/martin/multi-agent/frontend/app/globals.css`
- Create: `/Users/martin/multi-agent/frontend/app/layout.tsx`
- Create: `/Users/martin/multi-agent/frontend/app/page.tsx`

- [ ] **Step 1: Create Next.js project**

```bash
cd ~/multi-agent && npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-npm --no-turbopack
```

Expected: Project created at `~/multi-agent/frontend/`

- [ ] **Step 2: Install dependencies**

```bash
cd ~/multi-agent/frontend && npm install swr lucide-react
```

- [ ] **Step 3: Add Fira Sans + Fira Code fonts to layout.tsx**

Replace `/Users/martin/multi-agent/frontend/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Fira_Sans, Fira_Code } from "next/font/google";
import "./globals.css";

const firaSans = Fira_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Quorum — Multi-Agent Orchestration",
  description: "Orchestrate AI agents with different collaboration modes",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${firaSans.variable} ${firaCode.variable} font-sans antialiased bg-primary text-primary`}
      >
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Replace globals.css with design system tokens**

Replace `/Users/martin/multi-agent/frontend/app/globals.css` with:

```css
@import "tailwindcss";

@theme {
  --font-sans: var(--font-sans), ui-sans-serif, system-ui, sans-serif;
  --font-mono: var(--font-mono), ui-monospace, monospace;

  --color-bg-primary: #09090B;
  --color-bg-secondary: #0C0C0E;
  --color-bg-card: #12121A;
  --color-border: #1C1C1F;
  --color-border-hover: #3F3F46;
  --color-text-primary: #FAFAFA;
  --color-text-secondary: #A1A1AA;
  --color-text-muted: #52525B;
  --color-accent: #2563EB;
  --color-accent-hover: #3B82F6;
  --color-cta: #F97316;
  --color-success: #4ADE80;
  --color-error: #EF4444;

  --color-agent-claude: #2563EB;
  --color-agent-codex: #F97316;
  --color-agent-gemini: #8B5CF6;
  --color-agent-minimax: #6B7280;
  --color-agent-system: #52525B;
  --color-agent-user: #4ADE80;
}

html.light {
  --color-bg-primary: #FAFAFA;
  --color-bg-secondary: #F4F4F5;
  --color-bg-card: #FFFFFF;
  --color-border: #E4E4E7;
  --color-border-hover: #A1A1AA;
  --color-text-primary: #09090B;
  --color-text-secondary: #52525B;
  --color-text-muted: #A1A1AA;
  --color-accent: #2563EB;
  --color-accent-hover: #1D4ED8;
  --color-cta: #EA580C;
  --color-success: #16A34A;
  --color-error: #DC2626;
}

body {
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
}
```

- [ ] **Step 5: Create placeholder page.tsx**

Replace `/Users/martin/multi-agent/frontend/app/page.tsx` with:

```tsx
export default function Home() {
  return (
    <div className="flex h-screen items-center justify-center">
      <h1 className="text-2xl font-semibold tracking-tight">Quorum</h1>
    </div>
  );
}
```

- [ ] **Step 6: Verify dev server starts**

```bash
cd ~/multi-agent/frontend && npm run dev
```

Expected: Server at http://localhost:3000, shows "Quorum" centered

- [ ] **Step 7: Commit**

```bash
cd ~/multi-agent && git add frontend/ && git commit -m "feat(frontend): scaffold Next.js project with design system tokens"
```

---

### Task 2: Types and API client

**Files:**
- Create: `/Users/martin/multi-agent/frontend/lib/types.ts`
- Create: `/Users/martin/multi-agent/frontend/lib/api.ts`
- Create: `/Users/martin/multi-agent/frontend/lib/constants.ts`

- [ ] **Step 1: Create types.ts**

```typescript
// /Users/martin/multi-agent/frontend/lib/types.ts

export interface AgentConfig {
  role: string;
  provider: "claude" | "gemini" | "codex" | "minimax";
  system_prompt: string;
}

export interface RunRequest {
  mode: string;
  task: string;
  agents?: AgentConfig[];
  config?: Record<string, unknown>;
}

export interface Message {
  agent_id: string;
  content: string;
  timestamp: number;
  phase: string;
}

export interface Session {
  id: string;
  mode: string;
  task: string;
  agents: AgentConfig[];
  messages: Message[];
  result: string | null;
  status: "running" | "completed" | "failed";
  config: Record<string, unknown>;
  created_at: number;
  elapsed_sec: number | null;
}

export interface SessionSummary {
  id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
}

export interface ModeInfo {
  description: string;
  default_agents: AgentConfig[];
}
```

- [ ] **Step 2: Create constants.ts**

```typescript
// /Users/martin/multi-agent/frontend/lib/constants.ts

import {
  Crown,
  Users,
  Vote,
  Swords,
  LayoutGrid,
  RefreshCw,
  Trophy,
  type LucideIcon,
} from "lucide-react";

export const AGENT_COLORS: Record<string, string> = {
  claude: "var(--color-agent-claude)",
  codex: "var(--color-agent-codex)",
  gemini: "var(--color-agent-gemini)",
  minimax: "var(--color-agent-minimax)",
  system: "var(--color-agent-system)",
  user: "var(--color-agent-user)",
};

export const MODE_ICONS: Record<string, LucideIcon> = {
  dictator: Crown,
  board: Users,
  democracy: Vote,
  debate: Swords,
  map_reduce: LayoutGrid,
  creator_critic: RefreshCw,
  tournament: Trophy,
};

export const MODE_LABELS: Record<string, string> = {
  dictator: "Dictator",
  board: "Board",
  democracy: "Democracy",
  debate: "Debate",
  map_reduce: "Map-Reduce",
  creator_critic: "Creator-Critic",
  tournament: "Tournament",
};

export const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  codex: "Codex",
  gemini: "Gemini",
  minimax: "MiniMax",
};
```

- [ ] **Step 3: Create api.ts**

```typescript
// /Users/martin/multi-agent/frontend/lib/api.ts

import type { Session, SessionSummary, ModeInfo, RunRequest } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8800";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getModes(): Promise<Record<string, ModeInfo>> {
  return request("/orchestrate/modes");
}

export async function getSessions(): Promise<SessionSummary[]> {
  return request("/orchestrate/sessions");
}

export async function getSession(id: string): Promise<Session> {
  return request(`/orchestrate/session/${id}`);
}

export async function runSession(body: RunRequest): Promise<{ session_id: string }> {
  return request("/orchestrate/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function sendMessage(sessionId: string, content: string): Promise<void> {
  await request(`/orchestrate/session/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/multi-agent && git add frontend/lib/ && git commit -m "feat(frontend): add types, API client, and constants"
```

---

### Task 3: SWR hooks

**Files:**
- Create: `/Users/martin/multi-agent/frontend/hooks/use-modes.ts`
- Create: `/Users/martin/multi-agent/frontend/hooks/use-sessions.ts`
- Create: `/Users/martin/multi-agent/frontend/hooks/use-session.ts`
- Create: `/Users/martin/multi-agent/frontend/hooks/use-theme.ts`

- [ ] **Step 1: Create use-modes.ts**

```typescript
// /Users/martin/multi-agent/frontend/hooks/use-modes.ts

import useSWR from "swr";
import { getModes } from "@/lib/api";
import type { ModeInfo } from "@/lib/types";

export function useModes() {
  const { data, error, isLoading } = useSWR<Record<string, ModeInfo>>(
    "/orchestrate/modes",
    getModes,
    { revalidateOnFocus: false }
  );
  return { modes: data, error, isLoading };
}
```

- [ ] **Step 2: Create use-sessions.ts**

```typescript
// /Users/martin/multi-agent/frontend/hooks/use-sessions.ts

import useSWR from "swr";
import { getSessions } from "@/lib/api";
import type { SessionSummary } from "@/lib/types";

export function useSessions() {
  const { data, error, isLoading, mutate } = useSWR<SessionSummary[]>(
    "/orchestrate/sessions",
    getSessions,
    { refreshInterval: 5000 }
  );
  return { sessions: data ?? [], error, isLoading, refresh: mutate };
}
```

- [ ] **Step 3: Create use-session.ts**

```typescript
// /Users/martin/multi-agent/frontend/hooks/use-session.ts

import useSWR from "swr";
import { getSession } from "@/lib/api";
import type { Session } from "@/lib/types";

export function useSession(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Session>(
    id ? `/orchestrate/session/${id}` : null,
    id ? () => getSession(id) : null,
    {
      refreshInterval: (data) =>
        data?.status === "running" ? 2000 : 0,
    }
  );
  return { session: data ?? null, error, isLoading, refresh: mutate };
}
```

- [ ] **Step 4: Create use-theme.ts**

```typescript
// /Users/martin/multi-agent/frontend/hooks/use-theme.ts

import { useCallback, useEffect, useState } from "react";

type Theme = "dark" | "light";

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const stored = localStorage.getItem("quorum-theme") as Theme | null;
    const initial = stored ?? "dark";
    setThemeState(initial);
    document.documentElement.classList.toggle("light", initial === "light");
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    localStorage.setItem("quorum-theme", t);
    document.documentElement.classList.toggle("light", t === "light");
    document.documentElement.classList.toggle("dark", t === "dark");
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggle };
}
```

- [ ] **Step 5: Commit**

```bash
cd ~/multi-agent && git add frontend/hooks/ && git commit -m "feat(frontend): add SWR hooks for modes, sessions, and theme"
```

---

### Task 4: Common components (Badge, Button, ThemeToggle)

**Files:**
- Create: `/Users/martin/multi-agent/frontend/components/common/badge.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/common/button.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/common/theme-toggle.tsx`

- [ ] **Step 1: Create badge.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/common/badge.tsx

interface BadgeProps {
  label: string;
  variant?: "default" | "success" | "error" | "accent";
}

const variants: Record<string, string> = {
  default: "bg-bg-card text-text-secondary border-border",
  success: "bg-green-950 text-success border-green-900",
  error: "bg-red-950 text-error border-red-900",
  accent: "bg-blue-950 text-accent border-blue-900",
};

export function Badge({ label, variant = "default" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-medium border ${variants[variant]}`}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 2: Create button.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/common/button.tsx

import { type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "cta" | "ghost";
  size?: "sm" | "md";
}

const base =
  "inline-flex items-center justify-center rounded-lg font-medium transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg-primary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer";

const variantStyles: Record<string, string> = {
  primary: "bg-accent hover:bg-accent-hover text-white",
  cta: "bg-cta hover:brightness-110 text-white",
  ghost: "bg-transparent hover:bg-bg-card text-text-secondary",
};

const sizeStyles: Record<string, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${base} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    />
  );
}
```

- [ ] **Step 3: Create theme-toggle.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/common/theme-toggle.tsx

import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-text-muted hover:bg-bg-card hover:text-text-secondary transition-colors cursor-pointer"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/multi-agent && git add frontend/components/ && git commit -m "feat(frontend): add Badge, Button, ThemeToggle components"
```

---

### Task 5: Sidebar (IconBar + SessionList)

**Files:**
- Create: `/Users/martin/multi-agent/frontend/components/sidebar/icon-bar.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/sidebar/session-list.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/sidebar/session-item.tsx`

- [ ] **Step 1: Create icon-bar.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/sidebar/icon-bar.tsx

import { MessageSquare, Clock, Sliders } from "lucide-react";
import { ThemeToggle } from "@/components/common/theme-toggle";

type View = "chat" | "history" | "settings";

interface IconBarProps {
  activeView: View;
  onViewChange: (view: View) => void;
}

const navItems: { id: View; icon: typeof MessageSquare; label: string }[] = [
  { id: "chat", icon: MessageSquare, label: "Chat" },
  { id: "history", icon: Clock, label: "History" },
  { id: "settings", icon: Sliders, label: "Settings" },
];

export function IconBar({ activeView, onViewChange }: IconBarProps) {
  return (
    <div className="flex h-full w-[52px] flex-col items-center border-r border-border bg-bg-secondary py-3">
      <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
        <span className="font-mono text-xs font-bold text-white">Q</span>
      </div>
      <nav className="flex flex-col gap-1.5">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            aria-label={label}
            className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors cursor-pointer ${
              activeView === id
                ? "bg-accent text-white"
                : "text-text-muted hover:bg-bg-card hover:text-text-secondary"
            }`}
          >
            <Icon size={16} />
          </button>
        ))}
      </nav>
      <div className="mt-auto">
        <ThemeToggle />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create session-item.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/sidebar/session-item.tsx

import { Badge } from "@/components/common/badge";
import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  const Icon = MODE_ICONS[session.mode];
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors cursor-pointer ${
        isActive
          ? "bg-bg-card border-l-2 border-l-accent"
          : "hover:bg-bg-card/50"
      }`}
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon size={12} className="text-text-muted flex-shrink-0" />}
        <span className="truncate text-xs font-medium text-text-primary">
          {session.task.slice(0, 40)}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="font-mono text-[10px] text-text-muted">
          {timeAgo(session.created_at)}
        </span>
        <Badge
          label={session.status}
          variant={
            session.status === "completed"
              ? "success"
              : session.status === "failed"
                ? "error"
                : "accent"
          }
        />
      </div>
    </button>
  );
}
```

- [ ] **Step 3: Create session-list.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/sidebar/session-list.tsx

import { Plus } from "lucide-react";
import { useSessions } from "@/hooks/use-sessions";
import { SessionItem } from "./session-item";

interface SessionListProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

export function SessionList({
  activeSessionId,
  onSelectSession,
  onNewSession,
}: SessionListProps) {
  const { sessions, isLoading } = useSessions();

  return (
    <div className="flex h-full w-60 flex-col border-r border-border bg-bg-secondary">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
          Sessions
        </span>
        <button
          onClick={onNewSession}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-bg-card text-text-muted hover:bg-accent hover:text-white transition-colors cursor-pointer"
          aria-label="New session"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoading && (
          <div className="px-3 py-4 text-xs text-text-muted">Loading...</div>
        )}
        {sessions.map((s) => (
          <SessionItem
            key={s.id}
            session={s}
            isActive={s.id === activeSessionId}
            onClick={() => onSelectSession(s.id)}
          />
        ))}
        {!isLoading && sessions.length === 0 && (
          <div className="px-3 py-8 text-center text-xs text-text-muted">
            No sessions yet
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/multi-agent && git add frontend/components/sidebar/ && git commit -m "feat(frontend): add IconBar and SessionList sidebar components"
```

---

### Task 6: Wizard (3-step session creation)

**Files:**
- Create: `/Users/martin/multi-agent/frontend/components/wizard/wizard.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/wizard/step-mode.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/wizard/step-agents.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/wizard/step-task.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/wizard/mode-card.tsx`

- [ ] **Step 1: Create mode-card.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/wizard/mode-card.tsx

import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import type { ModeInfo } from "@/lib/types";

interface ModeCardProps {
  modeKey: string;
  info: ModeInfo;
  isSelected: boolean;
  onClick: () => void;
}

export function ModeCard({ modeKey, info, isSelected, onClick }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center rounded-xl border p-5 text-center transition-all duration-150 cursor-pointer ${
        isSelected
          ? "border-accent bg-blue-950/30 shadow-[0_0_24px_rgba(37,99,235,0.08)]"
          : "border-border bg-bg-card hover:border-border-hover"
      }`}
    >
      <div
        className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${
          isSelected ? "bg-accent text-white" : "bg-bg-secondary text-text-muted"
        }`}
      >
        {Icon && <Icon size={20} />}
      </div>
      <div className="text-sm font-semibold text-text-primary">
        {MODE_LABELS[modeKey] ?? modeKey}
      </div>
      <div className="mt-1 text-xs text-text-muted leading-relaxed">
        {info.description}
      </div>
    </button>
  );
}
```

- [ ] **Step 2: Create step-mode.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/wizard/step-mode.tsx

import { ModeCard } from "./mode-card";
import { Button } from "@/components/common/button";
import type { ModeInfo } from "@/lib/types";

interface StepModeProps {
  modes: Record<string, ModeInfo>;
  selected: string | null;
  onSelect: (mode: string) => void;
  onNext: () => void;
}

export function StepMode({ modes, selected, onSelect, onNext }: StepModeProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Choose orchestration mode
        </h2>
        <p className="text-sm text-text-muted mb-8">
          How should the agents collaborate?
        </p>
        <div className="grid grid-cols-2 gap-3 max-w-2xl lg:grid-cols-3">
          {Object.entries(modes).map(([key, info]) => (
            <ModeCard
              key={key}
              modeKey={key}
              info={info}
              isSelected={selected === key}
              onClick={() => onSelect(key)}
            />
          ))}
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-end">
        <Button onClick={onNext} disabled={!selected}>
          Next
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create step-agents.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/wizard/step-agents.tsx

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/common/button";
import { PROVIDER_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";

interface StepAgentsProps {
  agents: AgentConfig[];
  onChange: (agents: AgentConfig[]) => void;
  onNext: () => void;
  onBack: () => void;
}

const providers = ["claude", "gemini", "codex", "minimax"] as const;

export function StepAgents({ agents, onChange, onNext, onBack }: StepAgentsProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  function updateAgent(index: number, updates: Partial<AgentConfig>) {
    const next = agents.map((a, i) =>
      i === index ? { ...a, ...updates } : a
    );
    onChange(next);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Configure agents
        </h2>
        <p className="text-sm text-text-muted mb-8">
          Assign providers to each role. Expand to set custom prompts.
        </p>
        <div className="flex flex-col gap-3 max-w-xl">
          {agents.map((agent, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-bg-card overflow-hidden"
            >
              <div className="flex items-center gap-3 px-4 py-3">
                <span className="font-mono text-xs font-medium text-text-secondary w-28 truncate">
                  {agent.role}
                </span>
                <select
                  value={agent.provider}
                  onChange={(e) =>
                    updateAgent(i, {
                      provider: e.target.value as AgentConfig["provider"],
                    })
                  }
                  className="rounded-lg border border-border bg-bg-secondary px-3 py-1.5 text-xs text-text-primary cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  {providers.map((p) => (
                    <option key={p} value={p}>
                      {PROVIDER_LABELS[p]}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() =>
                    setExpandedIdx(expandedIdx === i ? null : i)
                  }
                  className="ml-auto text-text-muted hover:text-text-secondary cursor-pointer"
                  aria-label="Toggle prompt editor"
                >
                  {expandedIdx === i ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                </button>
              </div>
              {expandedIdx === i && (
                <div className="border-t border-border px-4 py-3">
                  <label className="text-[10px] uppercase tracking-widest text-text-muted mb-1 block">
                    System prompt
                  </label>
                  <textarea
                    value={agent.system_prompt}
                    onChange={(e) =>
                      updateAgent(i, { system_prompt: e.target.value })
                    }
                    placeholder="Optional custom instructions for this agent..."
                    rows={3}
                    className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-xs text-text-primary placeholder-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext}>Next</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create step-task.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/wizard/step-task.tsx

import { useState } from "react";
import { Button } from "@/components/common/button";
import { MODE_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";

interface StepTaskProps {
  mode: string;
  agents: AgentConfig[];
  onLaunch: (task: string, config: Record<string, number>) => void;
  onBack: () => void;
  isLaunching: boolean;
}

export function StepTask({
  mode,
  agents,
  onLaunch,
  onBack,
  isLaunching,
}: StepTaskProps) {
  const [task, setTask] = useState("");
  const [maxRounds, setMaxRounds] = useState(3);

  const needsRounds = ["debate", "democracy", "board"].includes(mode);
  const needsIterations = ["dictator", "creator_critic"].includes(mode);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Describe your task
        </h2>
        <p className="text-sm text-text-muted mb-8">
          What should the {MODE_LABELS[mode]} team work on?
        </p>

        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Enter your task or question..."
          rows={5}
          className="w-full max-w-xl rounded-xl border border-border bg-bg-card px-4 py-3 text-sm text-text-primary placeholder-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent"
          autoFocus
        />

        {(needsRounds || needsIterations) && (
          <div className="mt-6 max-w-xl">
            <label className="text-[10px] uppercase tracking-widest text-text-muted mb-2 block">
              {needsRounds ? "Max rounds" : "Max iterations"}
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
              className="w-20 rounded-lg border border-border bg-bg-secondary px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        )}

        <div className="mt-8 max-w-xl rounded-xl border border-border bg-bg-secondary p-4">
          <div className="text-[10px] uppercase tracking-widest text-text-muted mb-3">
            Summary
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-text-secondary">Mode:</span>
            <span className="font-medium text-text-primary">
              {MODE_LABELS[mode]}
            </span>
          </div>
          <div className="flex flex-wrap gap-1 mt-2 text-xs">
            <span className="text-text-secondary">Agents:</span>
            {agents.map((a, i) => (
              <span
                key={i}
                className="rounded bg-bg-card px-1.5 py-0.5 font-mono text-[10px] text-text-muted"
              >
                {a.role}({a.provider})
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button
          variant="cta"
          onClick={() => {
            const config: Record<string, number> = {};
            if (needsRounds) config.max_rounds = maxRounds;
            if (needsIterations) config.max_iterations = maxRounds;
            onLaunch(task, config);
          }}
          disabled={!task.trim() || isLaunching}
        >
          {isLaunching ? "Launching..." : "Launch"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create wizard.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/wizard/wizard.tsx

import { useState } from "react";
import { useModes } from "@/hooks/use-modes";
import { runSession } from "@/lib/api";
import { StepMode } from "./step-mode";
import { StepAgents } from "./step-agents";
import { StepTask } from "./step-task";
import type { AgentConfig } from "@/lib/types";

interface WizardProps {
  onSessionCreated: (sessionId: string) => void;
}

export function Wizard({ onSessionCreated }: WizardProps) {
  const { modes, isLoading } = useModes();
  const [step, setStep] = useState(0);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [isLaunching, setIsLaunching] = useState(false);

  function handleModeSelect(mode: string) {
    setSelectedMode(mode);
    if (modes?.[mode]) {
      setAgents(modes[mode].default_agents);
    }
  }

  async function handleLaunch(task: string, config: Record<string, number>) {
    if (!selectedMode) return;
    setIsLaunching(true);
    try {
      const result = await runSession({
        mode: selectedMode,
        task,
        agents,
        config,
      });
      onSessionCreated(result.session_id);
    } catch (err) {
      console.error("Launch failed:", err);
    } finally {
      setIsLaunching(false);
    }
  }

  if (isLoading || !modes) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text-muted">
        Loading modes...
      </div>
    );
  }

  const steps = [
    <StepMode
      key="mode"
      modes={modes}
      selected={selectedMode}
      onSelect={handleModeSelect}
      onNext={() => setStep(1)}
    />,
    <StepAgents
      key="agents"
      agents={agents}
      onChange={setAgents}
      onNext={() => setStep(2)}
      onBack={() => setStep(0)}
    />,
    <StepTask
      key="task"
      mode={selectedMode ?? ""}
      agents={agents}
      onLaunch={handleLaunch}
      onBack={() => setStep(1)}
      isLaunching={isLaunching}
    />,
  ];

  const stepLabels = ["Mode", "Agents", "Task"];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 border-b border-border px-8 py-3">
        {stepLabels.map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
                i === step
                  ? "bg-accent text-white"
                  : i < step
                    ? "bg-green-950 text-success"
                    : "bg-bg-card text-text-muted"
              }`}
            >
              {i < step ? "✓" : i + 1}
            </div>
            <span
              className={`text-xs font-medium ${
                i === step ? "text-text-primary" : "text-text-muted"
              }`}
            >
              {label}
            </span>
            {i < stepLabels.length - 1 && (
              <div className="mx-2 h-px w-8 bg-border" />
            )}
          </div>
        ))}
      </div>
      {steps[step]}
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
cd ~/multi-agent && git add frontend/components/wizard/ && git commit -m "feat(frontend): add 3-step session creation wizard"
```

---

### Task 7: Chat view (messages + input)

**Files:**
- Create: `/Users/martin/multi-agent/frontend/components/chat/chat-header.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/chat/message.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/chat/input-bar.tsx`
- Create: `/Users/martin/multi-agent/frontend/components/chat/chat-view.tsx`

- [ ] **Step 1: Create chat-header.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/chat/chat-header.tsx

import { Badge } from "@/components/common/badge";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
}

export function ChatHeader({ session }: ChatHeaderProps) {
  const Icon = MODE_ICONS[session.mode];
  const statusVariant =
    session.status === "completed"
      ? "success"
      : session.status === "failed"
        ? "error"
        : "accent";

  return (
    <div className="flex items-center gap-3 border-b border-border px-5 py-3">
      {Icon && <Icon size={14} className="text-text-muted" />}
      <span className="text-sm font-semibold text-text-primary truncate">
        {session.task.slice(0, 60)}
      </span>
      <Badge label={MODE_LABELS[session.mode] ?? session.mode} />
      <Badge label={session.status} variant={statusVariant} />
      {session.elapsed_sec !== null && (
        <span className="ml-auto font-mono text-[10px] text-text-muted">
          {session.elapsed_sec}s
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create message.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/chat/message.tsx

import { AGENT_COLORS } from "@/lib/constants";
import type { Message as MessageType } from "@/lib/types";

interface MessageProps {
  message: MessageType;
}

function getProvider(agentId: string): string {
  const lower = agentId.toLowerCase();
  if (lower.includes("claude") || lower === "critic" || lower === "director" || lower === "proponent" || lower === "planner" || lower === "synthesizer")
    return "claude";
  if (lower.includes("codex") || lower === "creator" || lower === "opponent") return "codex";
  if (lower.includes("gemini") || lower === "judge") return "gemini";
  if (lower.includes("minimax")) return "minimax";
  if (lower === "user") return "user";
  return "system";
}

export function Message({ message }: MessageProps) {
  const provider = getProvider(message.agent_id);
  const color = AGENT_COLORS[provider] ?? AGENT_COLORS.system;

  return (
    <div
      className="rounded-xl bg-bg-card border border-border px-4 py-3 mb-3"
      style={{ borderLeftWidth: "2px", borderLeftColor: color }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <div
          className="h-1.5 w-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <span
          className="font-mono text-[11px] font-medium"
          style={{ color }}
        >
          {message.agent_id}
        </span>
        {message.phase && (
          <span className="font-mono text-[10px] text-text-muted">
            {message.phase}
          </span>
        )}
      </div>
      <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
        {message.content}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create input-bar.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/chat/input-bar.tsx

import { useState } from "react";
import { Send } from "lucide-react";
import { sendMessage } from "@/lib/api";

interface InputBarProps {
  sessionId: string;
  disabled: boolean;
}

export function InputBar({ sessionId, disabled }: InputBarProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      await sendMessage(sessionId, text.trim());
      setText("");
    } catch (err) {
      console.error("Failed to send:", err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="border-t border-border px-4 py-3">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={
            disabled
              ? "Session ended"
              : "Intervene in conversation..."
          }
          disabled={disabled || sending}
          className="flex-1 rounded-lg border border-border bg-bg-card px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-40"
        />
        <button
          onClick={handleSend}
          disabled={disabled || sending || !text.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-40 cursor-pointer"
          aria-label="Send message"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create chat-view.tsx**

```tsx
// /Users/martin/multi-agent/frontend/components/chat/chat-view.tsx

import { useEffect, useRef } from "react";
import { useSession } from "@/hooks/use-session";
import { ChatHeader } from "./chat-header";
import { Message } from "./message";
import { InputBar } from "./input-bar";

interface ChatViewProps {
  sessionId: string;
}

export function ChatView({ sessionId }: ChatViewProps) {
  const { session, isLoading } = useSession(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages.length]);

  if (isLoading || !session) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text-muted">
        Loading session...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ChatHeader session={session} />
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {session.messages.length === 0 && session.status === "running" && (
          <div className="flex h-full items-center justify-center text-sm text-text-muted">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-accent animate-pulse" />
              Agents are working...
            </div>
          </div>
        )}
        {session.messages.map((msg, i) => (
          <Message key={i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
      <InputBar
        sessionId={sessionId}
        disabled={session.status !== "running"}
      />
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd ~/multi-agent && git add frontend/components/chat/ && git commit -m "feat(frontend): add chat view with messages and input bar"
```

---

### Task 8: Main page (wire everything together)

**Files:**
- Modify: `/Users/martin/multi-agent/frontend/app/page.tsx`
- Modify: `/Users/martin/multi-agent/frontend/next.config.js`

- [ ] **Step 1: Update next.config.js to allow API proxy**

Replace `/Users/martin/multi-agent/frontend/next.config.js` (or `next.config.ts`) with:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8800/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
```

Then update `/Users/martin/multi-agent/frontend/lib/api.ts` line 3 to use relative path:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL || "";
```

And update all API paths to include `/api` prefix:

```typescript
export async function getModes(): Promise<Record<string, ModeInfo>> {
  return request("/api/orchestrate/modes");
}

export async function getSessions(): Promise<SessionSummary[]> {
  return request("/api/orchestrate/sessions");
}

export async function getSession(id: string): Promise<Session> {
  return request(`/api/orchestrate/session/${id}`);
}

export async function runSession(body: RunRequest): Promise<{ session_id: string }> {
  return request("/api/orchestrate/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function sendMessage(sessionId: string, content: string): Promise<void> {
  await request(`/api/orchestrate/session/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
```

Also update SWR keys in hooks to match:

In `use-modes.ts`: key `"/api/orchestrate/modes"`
In `use-sessions.ts`: key `"/api/orchestrate/sessions"`
In `use-session.ts`: key `` `/api/orchestrate/session/${id}` ``

- [ ] **Step 2: Replace page.tsx with main app**

```tsx
// /Users/martin/multi-agent/frontend/app/page.tsx

"use client";

import { useState } from "react";
import { IconBar } from "@/components/sidebar/icon-bar";
import { SessionList } from "@/components/sidebar/session-list";
import { Wizard } from "@/components/wizard/wizard";
import { ChatView } from "@/components/chat/chat-view";

type View = "chat" | "history" | "settings";

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);

  function handleSessionCreated(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
  }

  function handleNewSession() {
    setShowWizard(true);
    setActiveSessionId(null);
  }

  function handleSelectSession(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <IconBar activeView={view} onViewChange={setView} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <main className="flex-1 flex flex-col min-w-0">
        {showWizard ? (
          <Wizard onSessionCreated={handleSessionCreated} />
        ) : activeSessionId ? (
          <ChatView sessionId={activeSessionId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-text-muted">
            Select a session or create a new one
          </div>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Verify the app builds**

```bash
cd ~/multi-agent/frontend && npm run build
```

Expected: Build succeeds without errors.

- [ ] **Step 4: Verify dev server with gateway running**

```bash
cd ~/multi-agent/frontend && npm run dev
```

Open http://localhost:3000. Should show 3-column layout with wizard.

- [ ] **Step 5: Commit**

```bash
cd ~/multi-agent && git add frontend/ && git commit -m "feat(frontend): wire main page with sidebar, wizard, and chat view"
```

---

### Task 9: CORS fix on gateway

**Files:**
- Verify: `/Users/martin/multi-agent/gateway.py` (CORS already has `allow_origins=["*"]`)

- [ ] **Step 1: Verify CORS is configured**

Check that `gateway.py` already has:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

If present, no changes needed. This allows the Next.js frontend (port 3000) to call the gateway (port 8800) directly or via rewrite proxy.

- [ ] **Step 2: End-to-end test**

1. Ensure gateway is running: `python3 ~/multi-agent/gateway.py`
2. Start frontend: `cd ~/multi-agent/frontend && npm run dev`
3. Open http://localhost:3000
4. Select a mode → configure agents → write task → Launch
5. Verify session appears in left sidebar
6. Verify messages appear in chat as agents respond

- [ ] **Step 3: Final commit**

```bash
cd ~/multi-agent && git add -A && git commit -m "feat(frontend): Quorum v1 — complete frontend with wizard, chat, sessions"
```
