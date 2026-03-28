import type { Edge, Node } from "@xyflow/react";

import { AGENT_COLORS, formatAgentDisplay, formatWorkspaceLabel, PROVIDER_LABELS, type RoleDisplayContext } from "@/lib/constants";
import { useLocale } from "@/lib/locale";
import type { Session, SessionEvent } from "@/lib/types";

export type TopologyDensity = "default" | "compact" | "tight";
export type TopologyVariant = "default" | "ghost" | "chamber";
export type TopologyBackdropVariant = "default" | "loop" | "pipeline" | "chamber" | "bracket";

export interface TopologyNodeDimensions {
  width: number;
  height: number;
}

export interface TopologyNodeDescriptor {
  kind: "task" | "agent" | "hub" | "match";
  label: string;
  subtitle?: string;
  provider?: string;
  active?: boolean;
  density?: TopologyDensity;
  variant?: TopologyVariant;
  eyebrow?: string;
  dimensions?: TopologyNodeDimensions;
}

export type TopologyFlowNodeData = Record<string, unknown> & Omit<TopologyNodeDescriptor, "dimensions"> & {
  dimensions: TopologyNodeDimensions;
};

export type TopologyEdgeData = Record<string, unknown> & {
  routePath?: string;
};

export type FlowEdge = Edge<TopologyEdgeData> & {
  pathOptions?: {
    offset?: number;
    borderRadius?: number;
    stepPosition?: number;
  };
};

export interface FlowCanvasGraph {
  nodes: Node<TopologyFlowNodeData>[];
  edges: FlowEdge[];
  stageHeight?: number;
  fitPadding?: number;
  maxZoom?: number;
  backdrop?: {
    variant?: TopologyBackdropVariant;
    zones?: Array<{
      label: string;
      left: string;
      width: string;
      top?: string;
      height?: string;
    }>;
  };
}

export type LocaleCopy = ReturnType<typeof useLocale>["copy"];
export type SessionAgent = Session["agents"][number];

export type TournamentSlotEntry =
  | {
      slotIndex: number;
      kind: "direct";
      agent: SessionAgent;
    }
  | {
      slotIndex: number;
      kind: "playin";
      pair: [SessionAgent, SessionAgent];
    };

export interface TournamentStructure {
  entrants: SessionAgent[];
  slotCount: number;
  playInMatchCount: number;
  byeCount: number;
  slots: TournamentSlotEntry[];
  mainRoundLabels: string[];
}

const NODE_DIMENSIONS = {
  task: {
    default: { width: 260, height: 84 },
    compact: { width: 220, height: 72 },
    tight: { width: 180, height: 64 },
  },
  agent: {
    default: { width: 172, height: 84 },
    compact: { width: 136, height: 72 },
    tight: { width: 112, height: 64 },
  },
  hub: {
    default: { width: 198, height: 96 },
    compact: { width: 182, height: 88 },
    chamber: { width: 228, height: 108 },
  },
  match: {
    default: { width: 132, height: 68 },
    compact: { width: 112, height: 56 },
    tight: { width: 104, height: 52 },
  },
} as const;

export function providerMark(provider: string) {
  const marks: Record<string, string> = {
    claude: "Cl",
    codex: "Cx",
    gemini: "Ge",
    minimax: "Mm",
  };

  return marks[provider] ?? provider.slice(0, 2).toUpperCase();
}

export function providerAccent(provider: string) {
  return AGENT_COLORS[provider] ?? "#7b8190";
}

export function providerLabel(provider: string) {
  return PROVIDER_LABELS[provider] ?? provider;
}

export function humanizeRole(role: string, context?: RoleDisplayContext) {
  return formatAgentDisplay(role, context);
}

export function latestRoundLabel(events: SessionEvent[] = []) {
  const latestRoundEvent = [...events]
    .reverse()
    .find((event) => event.type === "round_completed" || event.type === "round_started");

  if (!latestRoundEvent) {
    return null;
  }

  if (typeof latestRoundEvent.round === "number" && latestRoundEvent.round > 0) {
    return `Round ${latestRoundEvent.round}`;
  }

  return latestRoundEvent.title;
}

export function resolveNodeDimensions(
  kind: TopologyFlowNodeData["kind"],
  density: TopologyDensity = "default",
  variant: TopologyVariant = "default"
): TopologyNodeDimensions {
  if (kind === "hub" && variant === "chamber") {
    return NODE_DIMENSIONS.hub.chamber;
  }

  if (kind === "hub") {
    return density === "compact" ? NODE_DIMENSIONS.hub.compact : NODE_DIMENSIONS.hub.default;
  }

  if (kind === "task") {
    return NODE_DIMENSIONS.task[density];
  }

  if (kind === "agent") {
    return NODE_DIMENSIONS.agent[density];
  }

  return NODE_DIMENSIONS.match[density];
}

export function flowNode(
  id: string,
  x: number,
  y: number,
  data: TopologyNodeDescriptor
): Node<TopologyFlowNodeData> {
  const dimensions = data.dimensions ?? resolveNodeDimensions(data.kind, data.density, data.variant);

  return {
    id,
    type: "topology",
    position: { x, y },
    width: dimensions.width,
    height: dimensions.height,
    initialWidth: dimensions.width,
    initialHeight: dimensions.height,
    data: {
      ...data,
      dimensions,
    },
  };
}

export function buildTaskFlowNode(
  session: Session,
  copy: LocaleCopy,
  x: number,
  y: number,
  density: TopologyDensity = "compact"
) {
  return flowNode("task", x, y, {
    kind: "task",
    label: copy.monitor.sessionTask,
    subtitle: session.task.slice(0, density === "tight" ? 28 : 48),
    density,
  });
}

export function buildAgentFlowNode(
  agent: SessionAgent,
  x: number,
  y: number,
  options?: Partial<Pick<TopologyFlowNodeData, "density" | "variant" | "eyebrow">> & {
    roleContext?: RoleDisplayContext;
  }
) {
  const projectLabel = formatWorkspaceLabel(agent.workspace_paths);
  return flowNode(`agent:${agent.role}`, x, y, {
    kind: "agent",
    label: formatAgentDisplay(agent.role, {
      ...options?.roleContext,
      projectLabel,
    }),
    subtitle: projectLabel ? `${projectLabel} - ${providerLabel(agent.provider)}` : providerLabel(agent.provider),
    provider: agent.provider,
    density: options?.density,
    variant: options?.variant,
    eyebrow: options?.eyebrow,
  });
}

function largestPowerOfTwoAtMost(value: number) {
  let power = 1;
  while (power * 2 <= value) {
    power *= 2;
  }
  return power;
}

export function tournamentRoundLabel(participants: number) {
  if (participants <= 2) return "FINAL";
  if (participants === 4) return "SF";
  if (participants === 8) return "QF";
  return "R1";
}

function distributeBracketSlots(count: number, total: number) {
  const slots: number[] = [];

  for (let index = 0; index < total && slots.length < count; index += 2) {
    slots.push(index);
  }

  const oddStart = total % 2 === 0 ? total - 1 : total - 2;
  for (let index = oddStart; index >= 0 && slots.length < count; index -= 2) {
    if (!slots.includes(index)) {
      slots.push(index);
    }
  }

  return slots.sort((left, right) => left - right);
}

export function buildTournamentStructure(agents: Session["agents"]): TournamentStructure {
  const entrants = agents.slice(0, 8);

  if (entrants.length === 0) {
    return { entrants, slotCount: 0, playInMatchCount: 0, byeCount: 0, slots: [], mainRoundLabels: [] };
  }

  if (entrants.length === 1) {
    return {
      entrants,
      slotCount: 1,
      playInMatchCount: 0,
      byeCount: 1,
      slots: [{ slotIndex: 0, kind: "direct", agent: entrants[0] }],
      mainRoundLabels: [],
    };
  }

  const slotCount = entrants.length <= 2 ? 2 : largestPowerOfTwoAtMost(entrants.length);
  const playInMatchCount = entrants.length <= 2 ? 0 : entrants.length - slotCount;
  const byeCount = entrants.length - playInMatchCount * 2;
  const directEntrants = entrants.slice(0, byeCount);
  const playInEntrants = entrants.slice(byeCount);
  const directSlots = new Set(distributeBracketSlots(directEntrants.length, slotCount));

  const slots: TournamentSlotEntry[] = [];
  let directIndex = 0;
  let playInIndex = 0;

  for (let slotIndex = 0; slotIndex < slotCount; slotIndex += 1) {
    if (directSlots.has(slotIndex) && directEntrants[directIndex]) {
      slots.push({ slotIndex, kind: "direct", agent: directEntrants[directIndex] });
      directIndex += 1;
      continue;
    }

    const top = playInEntrants[playInIndex];
    const bottom = playInEntrants[playInIndex + 1];
    if (top && bottom) {
      slots.push({ slotIndex, kind: "playin", pair: [top, bottom] });
      playInIndex += 2;
    }
  }

  const mainRoundLabels: string[] = [];
  for (let participants = slotCount; participants >= 2; participants /= 2) {
    mainRoundLabels.push(tournamentRoundLabel(participants));
  }

  return {
    entrants,
    slotCount,
    playInMatchCount,
    byeCount,
    slots,
    mainRoundLabels,
  };
}
