"use client";

import { useEffect, useState } from "react";

import { ArrowRight, Folder, Globe, HardDrive, Sparkles, TerminalSquare, type LucideIcon } from "lucide-react";

import { AGENT_COLORS, PROVIDER_LABELS } from "@/lib/constants";
import { useLocale } from "@/lib/locale";
import type { AttachedToolDetail, Message, Session, SessionEvent } from "@/lib/types";

interface TopologyPanelProps {
  session: Session;
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return reduced;
}

function humanizeTool(tool: string) {
  return tool
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function resolveToolIcon(tool: string, detail?: AttachedToolDetail): LucideIcon {
  if (detail?.icon === "🔍" || tool.includes("search")) return Globe;
  if (detail?.icon === "🧠" || tool.includes("perplexity")) return Sparkles;
  if (detail?.icon === "⚡" || detail?.icon === "🐍" || tool.includes("shell") || tool.includes("code")) return TerminalSquare;
  if (detail?.icon === "📊") return HardDrive;
  return Folder;
}

function latestMessage(messages: Message[], agentId: string, phasePrefix?: string) {
  return [...messages]
    .reverse()
    .find((message) => message.agent_id === agentId && (!phasePrefix || message.phase.startsWith(phasePrefix)));
}

function latestEvent(
  events: SessionEvent[],
  type: string,
  predicate?: (event: SessionEvent) => boolean
) {
  return [...events].reverse().find((event) => event.type === type && (!predicate || predicate(event)));
}

function recentEvents(events: SessionEvent[], type: string, limit: number = 3) {
  return events.filter((event) => event.type === type).slice(-limit).reverse();
}

function latestRoundLabel(events: SessionEvent[]) {
  const latestRoundEvent = [...events]
    .reverse()
    .find((event) => event.type === "round_completed" || event.type === "round_started");
  if (!latestRoundEvent) return null;
  if (typeof latestRoundEvent.round === "number" && latestRoundEvent.round > 0) {
    return `Round ${latestRoundEvent.round}`;
  }
  return latestRoundEvent.title;
}

function shellTitle(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  if (session.mode === "board") return copy.monitor.topologyTitles.board;
  if (session.mode === "democracy") return copy.monitor.topologyTitles.democracy;
  if (session.mode === "debate") return copy.monitor.topologyTitles.debate;
  if (session.mode === "creator_critic") return copy.monitor.topologyTitles.creator_critic;
  if (session.mode === "map_reduce") return copy.monitor.topologyTitles.map_reduce;
  return copy.monitor.topologyTitles.default;
}

function providerMark(provider: string) {
  const marks: Record<string, string> = {
    claude: "Cl",
    codex: "Cx",
    gemini: "Ge",
    minimax: "Mm",
  };
  return marks[provider] ?? provider.slice(0, 2).toUpperCase();
}

function providerAccent(provider: string) {
  return AGENT_COLORS[provider] ?? "#7b8190";
}

function fallbackToolDetail(toolId: string): AttachedToolDetail {
  return {
    id: toolId,
    name: humanizeTool(toolId),
    tool_type: null,
    transport: "unknown",
    subtitle: "MCP",
    icon: "folder",
    capability: "native",
  };
}

interface CanvasNode {
  id: string;
  kind: "task" | "agent" | "tool" | "hub";
  x: number;
  y: number;
  size: number;
  label: string;
  subtitle?: string;
  provider?: string;
  tool?: AttachedToolDetail;
}

interface CanvasEdge {
  id: string;
  path: string;
  reversePath?: string;
  active?: boolean;
}

function mirrorPath(path: string): string {
  const points = path.match(/-?\d+(?:\.\d+)?/g)?.map(Number);
  if (!points || points.length < 8) {
    return path;
  }
  const [sx, sy, c1x, c1y, c2x, c2y, ex, ey] = points;
  return `M ${ex} ${ey} C ${c2x} ${c2y}, ${c1x} ${c1y}, ${sx} ${sy}`;
}

function connectionPath(
  start: [number, number],
  c1: [number, number],
  c2: [number, number],
  end: [number, number]
) {
  return `M ${start[0]} ${start[1]} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${end[0]} ${end[1]}`;
}

function buildToolNodes(session: Session, x: number, tops: number[]) {
  const detailMap = new Map((session.attached_tools ?? []).map((tool) => [tool.id, tool]));
  const visibleToolIds = Array.from(
    new Set(
      (session.attached_tool_ids?.length
        ? session.attached_tool_ids
        : session.agents.flatMap((agent) => agent.tools ?? [])
      ).filter(Boolean)
    )
  ).slice(0, tops.length);

  return visibleToolIds.map((toolId, index) => ({
    id: `tool:${toolId}`,
    kind: "tool" as const,
    x,
    y: tops[index] ?? tops[tops.length - 1],
    size: 64,
    label: (detailMap.get(toolId) ?? fallbackToolDetail(toolId)).name,
    subtitle: (detailMap.get(toolId) ?? fallbackToolDetail(toolId)).subtitle,
    tool: detailMap.get(toolId) ?? fallbackToolDetail(toolId),
  }));
}

function latestSignal(session: Session) {
  return [...(session.events ?? [])]
    .reverse()
    .find((event) =>
      [
        "tool_call_started",
        "tool_call_finished",
        "vote_recorded",
        "round_started",
        "round_completed",
        "chunk_completed",
      ].includes(event.type)
    );
}

function resolveActiveEdgeIds(session: Session, edges: CanvasEdge[]): Set<string> {
  const signal = latestSignal(session);
  if (!signal) {
    return new Set();
  }

  if ((signal.type === "tool_call_started" || signal.type === "tool_call_finished") && signal.agent_id) {
    const direct = edges.find((edge) => edge.id.endsWith(`->agent:${signal.agent_id}`) || edge.id.startsWith(`hub->agent:${signal.agent_id}`));
    if (direct) {
      return new Set([direct.id + (signal.type === "tool_call_finished" ? ":reverse" : "")]);
    }
  }

  if (signal.type === "vote_recorded" && signal.agent_id) {
    return new Set([`hub->agent:${signal.agent_id}`]);
  }

  if (signal.type === "chunk_completed" && signal.agent_id) {
    return new Set([`agent:${signal.agent_id}->synth`]);
  }

  if (signal.type === "round_started" || signal.type === "round_completed") {
    if (session.mode === "board") {
      return new Set(
        session.agents.slice(0, 3).map((agent) => `hub->agent:${agent.role}`)
      );
    }
    if (session.mode === "democracy") {
      return new Set(session.agents.map((agent) => `agent:${agent.role}->hub`));
    }
    if (session.mode === "debate") {
      return new Set(["debate:judge:pro", "debate:judge:opp"]);
    }
  }

  return new Set();
}

function signalCards(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const latestToolEvent =
    latestEvent(session.events ?? [], "tool_call_finished") ??
    latestEvent(session.events ?? [], "tool_call_started");
  return [
    {
      label: copy.monitor.signalLabels.activeNode,
      value: session.active_node || copy.monitor.idle,
    },
    {
      label: copy.monitor.signalLabels.checkpoint,
      value: session.current_checkpoint_id || copy.monitor.pending,
    },
    {
      label: copy.monitor.signalLabels.liveTool,
      value: latestToolEvent?.tool_name || latestToolEvent?.detail || copy.monitor.noToolActivity,
    },
  ];
}

function inferMessageTarget(session: Session, message: Message, copy: ReturnType<typeof useLocale>["copy"]) {
  if (session.mode === "creator_critic") {
    return message.phase.startsWith("critique_")
      ? session.agents[0]?.role ?? copy.monitor.sharedContexts.creator_critic
      : session.agents[1]?.role ?? copy.monitor.sharedContexts.creator_critic;
  }
  if (session.mode === "map_reduce") {
    const synthesizer = session.agents[session.agents.length - 1];
    if (message.agent_id === session.agents[0]?.role) {
      return copy.monitor.workers;
    }
    return synthesizer?.role ?? copy.monitor.sharedContexts.map_reduce;
  }
  if (session.mode === "debate") {
    if (message.agent_id === session.agents[0]?.role) return session.agents[1]?.role ?? copy.monitor.sharedContexts.default;
    if (message.agent_id === session.agents[1]?.role) return session.agents[2]?.role ?? copy.monitor.sharedContexts.default;
    return copy.monitor.sharedContexts.default;
  }
  if (session.mode === "board") return copy.monitor.sharedContexts.board;
  if (session.mode === "democracy") return copy.monitor.sharedContexts.democracy;
  return copy.monitor.sharedContexts.default;
}

function buildLiveExchange(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const eventItems = (session.events ?? [])
    .filter((event) => ["tool_call_started", "tool_call_finished", "vote_recorded", "round_completed", "chunk_completed"].includes(event.type))
    .map((event) => ({
      id: `event-${event.id}`,
      timestamp: event.timestamp,
      from: event.agent_id ?? copy.monitor.sharedContexts.default,
      to: event.tool_name ?? copy.monitor.sharedContexts.default,
      title: event.type === "tool_call_started" ? copy.monitor.toolCall : event.type === "tool_call_finished" ? copy.monitor.toolResult : event.title,
      preview: (event.detail || event.tool_name || event.title).replace(/\s+/g, " ").slice(0, 132),
    }));

  const messageItems = session.messages.map((message) => ({
    id: `message-${message.agent_id}-${message.timestamp}`,
    timestamp: message.timestamp,
    from: message.agent_id,
    to: inferMessageTarget(session, message, copy),
    title: copy.monitor.agentMessage,
    preview: message.content.replace(/\s+/g, " ").slice(0, 132),
  }));

  return [...eventItems, ...messageItems]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 3);
}

function renderNode(node: CanvasNode, activeAgentId?: string) {
  const isActiveAgent = node.kind === "agent" && activeAgentId === node.id.replace(/^agent:/, "");
  const left = `calc(${(node.x / 760) * 100}% - ${node.kind === "task" ? 61 : node.kind === "tool" ? 55 : node.kind === "hub" ? 66 : 59}px)`;
  const top = `calc(${(node.y / 364) * 100}% - ${node.kind === "tool" ? 32 : node.kind === "hub" ? 48 : 40}px)`;
  if (node.kind === "task") {
    return (
      <div
        key={node.id}
        className="absolute flex w-[122px] flex-col items-center"
        style={{ left, top }}
      >
        <div className="flex h-[78px] w-[78px] items-center justify-center rounded-[18px] border border-[#d1d5db] bg-white shadow-[0_12px_32px_-24px_rgba(17,48,105,0.35)]">
          <Folder className="h-8 w-8 text-[#7b8190]" />
        </div>
        <div className="mt-3 text-center text-[18px] leading-tight tracking-[-0.03em] text-[#111111]">
          {node.label}
        </div>
        <div className="mt-1 text-center text-[12px] leading-5 text-[#7b8190]">{node.subtitle}</div>
      </div>
    );
  }

  if (node.kind === "tool") {
    const Icon = resolveToolIcon(node.tool?.id ?? node.id, node.tool);
    return (
      <div
        key={node.id}
        className="absolute flex w-[110px] flex-col items-center"
        style={{ left, top }}
      >
        <div className="flex h-[64px] w-[64px] items-center justify-center rounded-[16px] border border-[#d6dbe6] bg-white shadow-[0_12px_32px_-24px_rgba(17,48,105,0.25)]">
          <Icon className="h-7 w-7 text-[#7b8190]" />
        </div>
        <div className="mt-2 text-center text-[14px] font-medium tracking-[-0.02em] text-[#111111]">
          {node.label}
        </div>
      </div>
    );
  }

  if (node.kind === "hub") {
    return (
      <div
        key={node.id}
        className="absolute flex w-[132px] flex-col items-center"
        style={{ left, top }}
      >
        <div className="flex h-[96px] w-[96px] items-center justify-center rounded-[26px] border border-[#d6dbe6] bg-[#fbfcff] px-3 text-center shadow-[0_12px_30px_-26px_rgba(17,48,105,0.22)]">
          <div className="text-[18px] font-medium tracking-[-0.03em] text-[#111111]">{node.label}</div>
        </div>
        {node.subtitle ? (
          <div className="mt-2 text-center text-[11px] uppercase tracking-[0.12em] text-[#7b8190]">{node.subtitle}</div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      key={node.id}
      className="absolute flex w-[118px] flex-col items-center"
      style={{ left, top }}
    >
      <div
        className="flex h-[78px] w-[78px] items-center justify-center rounded-[18px] border bg-white text-[34px] font-semibold shadow-[0_12px_32px_-24px_rgba(17,48,105,0.35)]"
        style={{
          borderColor: isActiveAgent ? providerAccent(node.provider ?? "") : "#d1d5db",
          boxShadow: isActiveAgent
            ? `0 14px 36px -24px ${providerAccent(node.provider ?? "")}`
            : "0 12px 32px -24px rgba(17,48,105,0.35)",
          color: "#6b7280",
        }}
      >
        {providerMark(node.provider ?? "")}
      </div>
      <div className="mt-3 text-center text-[18px] leading-tight tracking-[-0.03em] text-[#111111]">
        {node.label}
      </div>
      <div className="mt-1 text-center text-[12px] leading-5 text-[#6b7280]">{node.subtitle}</div>
    </div>
  );
}

function buildCanvasGraph(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const agents = session.agents.slice(0, 4);
  const taskNode: CanvasNode = {
    id: "task",
    kind: "task",
    x: 104,
    y: 176,
    size: 78,
    label: copy.monitor.sessionTask,
    subtitle: session.task.slice(0, 44),
  };
  const getAgent = (index: number, x: number, y: number): CanvasNode | null => {
    const agent = agents[index];
    if (!agent) return null;
    return {
      id: `agent:${agent.role}`,
      kind: "agent",
      x,
      y,
      size: 78,
      label: PROVIDER_LABELS[agent.provider] ?? agent.provider,
      subtitle: agent.role,
      provider: agent.provider,
    };
  };

  if (session.mode === "board") {
    const hubNode: CanvasNode = {
      id: "hub",
      kind: "hub",
      x: 318,
      y: 184,
      size: 96,
      label: copy.monitor.sharedContexts.board,
    };
    const boardAgents = [
      getAgent(0, 528, 84),
      getAgent(1, 648, 196),
      getAgent(2, 528, 296),
    ].filter((node): node is CanvasNode => Boolean(node));
    const edges: CanvasEdge[] = [
      {
        id: "task->hub",
        path: connectionPath([144, 176], [212, 176], [240, 182], [270, 182]),
      },
      ...boardAgents.map((node, index) => ({
        id: `hub->${node.id}`,
        path: index === 0
          ? connectionPath([366, 152], [418, 128], [458, 110], [node.x - 42, node.y])
          : index === 1
            ? connectionPath([366, 184], [430, 184], [492, 184], [node.x - 42, node.y])
            : connectionPath([366, 216], [418, 240], [458, 260], [node.x - 42, node.y]),
      })),
    ];
    return { nodes: [taskNode, hubNode, ...boardAgents], edges };
  }

  if (session.mode === "democracy") {
    const hubNode: CanvasNode = {
      id: "hub",
      kind: "hub",
      x: 366,
      y: 184,
      size: 96,
      label: copy.monitor.sharedContexts.democracy,
    };
    const voteAgents = [
      getAgent(0, 548, 92),
      getAgent(1, 612, 184),
      getAgent(2, 548, 276),
    ].filter((node): node is CanvasNode => Boolean(node));
    const edges: CanvasEdge[] = [
      {
        id: "task->hub",
        path: connectionPath([144, 176], [224, 176], [258, 184], [318, 184]),
      },
      ...voteAgents.map((node, index) => ({
        id: `agent:${node.subtitle}->hub`,
        path: index === 0
          ? connectionPath([node.x - 42, node.y], [492, 110], [446, 140], [414, 152])
          : index === 1
            ? connectionPath([node.x - 42, node.y], [548, 184], [472, 184], [414, 184])
            : connectionPath([node.x - 42, node.y], [492, 258], [446, 226], [414, 216]),
      })),
    ];
    return { nodes: [taskNode, hubNode, ...voteAgents], edges };
  }

  if (session.mode === "debate") {
    const proponent = getAgent(0, 250, 228);
    const opponent = getAgent(1, 518, 228);
    const judge = getAgent(2, 384, 82);
    const nodes = [taskNode, proponent, opponent, judge].filter((node): node is CanvasNode => Boolean(node));
    const edges: CanvasEdge[] = [];
    if (proponent) {
      edges.push({
        id: `task->${proponent.id}`,
        path: connectionPath([144, 176], [194, 176], [212, 228], [proponent.x - 42, proponent.y]),
      });
    }
    if (opponent) {
      edges.push({
        id: `task->${opponent.id}`,
        path: connectionPath([144, 176], [230, 176], [328, 228], [opponent.x - 42, opponent.y]),
      });
    }
    if (proponent && judge) {
      edges.push({
        id: "debate:judge:pro",
        path: connectionPath([proponent.x + 18, proponent.y - 40], [284, 164], [326, 112], [judge.x - 18, judge.y + 40]),
      });
    }
    if (opponent && judge) {
      edges.push({
        id: "debate:judge:opp",
        path: connectionPath([opponent.x - 18, opponent.y - 40], [486, 164], [446, 112], [judge.x + 18, judge.y + 40]),
      });
    }
    if (proponent && opponent) {
      edges.push({
        id: `${proponent.id}->${opponent.id}`,
        path: connectionPath([proponent.x + 42, proponent.y], [334, 228], [434, 228], [opponent.x - 42, opponent.y]),
      });
    }
    return { nodes, edges };
  }

  if (session.mode === "creator_critic") {
    const creator = getAgent(0, 286, 182);
    const critic = getAgent(1, 498, 182);
    const nodes = [taskNode, creator, critic].filter((node): node is CanvasNode => Boolean(node));
    const edges: CanvasEdge[] = [];
    if (creator) {
      edges.push({
        id: `task->${creator.id}`,
        path: connectionPath([144, 176], [194, 176], [222, 182], [creator.x - 42, creator.y]),
      });
    }
    if (creator && critic) {
      const forward = connectionPath([creator.x + 42, creator.y - 10], [356, 124], [432, 124], [critic.x - 42, critic.y - 10]);
      const backward = connectionPath([critic.x - 42, critic.y + 10], [434, 248], [354, 248], [creator.x + 42, creator.y + 10]);
      edges.push({
        id: `${creator.id}->${critic.id}`,
        path: forward,
        reversePath: backward,
      });
    }
    return { nodes, edges };
  }

  if (session.mode === "map_reduce") {
    const planner = getAgent(0, 272, 88);
    const workers = agents.slice(1, -1).slice(0, 3).map((agent, index) => ({
      id: `agent:${agent.role}`,
      kind: "agent" as const,
      x: 264 + index * 150,
      y: 238,
      size: 78,
      label: PROVIDER_LABELS[agent.provider] ?? agent.provider,
      subtitle: agent.role,
      provider: agent.provider,
    }));
    const synthAgent = agents[agents.length - 1];
    const synth = synthAgent
      ? {
          id: "synth",
          kind: "agent" as const,
          x: 652,
          y: 160,
          size: 78,
          label: PROVIDER_LABELS[synthAgent.provider] ?? synthAgent.provider,
          subtitle: synthAgent.role,
          provider: synthAgent.provider,
        }
      : null;
    const nodes = [taskNode, planner, ...workers, synth].filter((node): node is CanvasNode => Boolean(node));
    const edges: CanvasEdge[] = [];
    if (planner) {
      edges.push({
        id: `task->${planner.id}`,
        path: connectionPath([144, 176], [194, 164], [214, 106], [planner.x - 42, planner.y]),
      });
      workers.forEach((worker, index) => {
        edges.push({
          id: `${planner.id}->${worker.id}`,
          path: connectionPath([planner.x, planner.y + 40], [planner.x, 152], [worker.x, 162], [worker.x, worker.y - 40]),
        });
        if (synth) {
          edges.push({
            id: `${worker.id}->synth`,
            path: connectionPath([worker.x + 42, worker.y], [worker.x + 96, worker.y], [synth.x - 92, synth.y + (index - 1) * 10], [synth.x - 42, synth.y]),
          });
        }
      });
    }
    return { nodes, edges };
  }

  const primaryAgent = getAgent(0, 286, 176);
  const upperAgent = getAgent(1, 492, 88);
  const lowerAgent = getAgent(2, 492, 264);
  const nodes = [taskNode, primaryAgent, upperAgent, lowerAgent].filter((node): node is CanvasNode => Boolean(node));
  const edges: CanvasEdge[] = [];
  if (primaryAgent) {
    edges.push({
      id: `task->${primaryAgent.id}`,
      path: connectionPath([144, 176], [194, 176], [220, 176], [primaryAgent.x - 42, primaryAgent.y]),
    });
  }
  if (primaryAgent && upperAgent) {
    edges.push({
      id: `${primaryAgent.id}->${upperAgent.id}`,
      path: connectionPath([primaryAgent.x + 40, primaryAgent.y - 16], [360, 150], [404, 88], [upperAgent.x - 42, upperAgent.y]),
    });
  }
  if (primaryAgent && lowerAgent) {
    edges.push({
      id: `${primaryAgent.id}->${lowerAgent.id}`,
      path: connectionPath([primaryAgent.x + 40, primaryAgent.y + 16], [360, 204], [404, 264], [lowerAgent.x - 42, lowerAgent.y]),
    });
  }
  return { nodes, edges };
}

function ConnectionCanvas({ session }: { session: Session }) {
  const { copy } = useLocale();
  const reduceMotion = useReducedMotion();
  const graph = buildCanvasGraph(session, copy);
  const activeEdgeIds = resolveActiveEdgeIds(session, graph.edges);
  const activeSignal = latestSignal(session);
  const activeAgentId = activeSignal?.agent_id;
  const cards = signalCards(session, copy);
  const exchanges = buildLiveExchange(session, copy);

  return (
    <div className="overflow-hidden rounded-[20px] border border-[#d6dbe6] bg-white">
      <div className="absolute inset-x-0 top-0 h-[96px] bg-[radial-gradient(circle_at_top,rgba(226,231,247,0.58),rgba(255,255,255,0))]" />
      <div className="relative h-[326px] bg-[radial-gradient(circle_at_top,rgba(226,231,247,0.58),rgba(255,255,255,0))]">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 760 364" preserveAspectRatio="none">
          {graph.edges.map((edge) => {
            const reverse = activeEdgeIds.has(`${edge.id}:reverse`);
            const active = edge.active || activeEdgeIds.has(edge.id) || reverse;
            return (
              <g key={edge.id}>
                <path
                  d={edge.path}
                  fill="none"
                  stroke={active ? "#6a7692" : "#a8b0c2"}
                  strokeWidth={active ? "2.4" : "2"}
                  className={active && !reduceMotion ? "flow-path-active" : undefined}
                />
                {active && !reduceMotion ? (
                  <>
                    <circle r="4.5" fill="#94a3b8" opacity="0.8">
                      <animateMotion
                        dur="2.2s"
                        repeatCount="indefinite"
                        path={reverse ? edge.reversePath ?? mirrorPath(edge.path) : edge.path}
                      />
                    </circle>
                    <circle r="3.2" fill="#111111" opacity="0.35">
                      <animateMotion
                        dur="2.2s"
                        begin="0.45s"
                        repeatCount="indefinite"
                        path={reverse ? edge.reversePath ?? mirrorPath(edge.path) : edge.path}
                      />
                    </circle>
                  </>
                ) : null}
              </g>
            );
          })}
        </svg>

        {graph.nodes.map((node) => renderNode(node, activeAgentId))}
      </div>

      <div className="border-t border-[#e6e8ee] bg-white p-4">
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fafbff] p-4">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.liveExchange}</div>
          {exchanges[0] ? (
            <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7b8190]">{exchanges[0].title}</div>
                <div className="text-[10px] text-[#9aa3b2]">
                  {new Date(exchanges[0].timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
              <div className="mt-2 text-[13px] font-medium tracking-[-0.02em] text-[#111111]">
                {exchanges[0].from} <span className="text-[#9aa3b2]">→</span> {exchanges[0].to}
              </div>
              <div className="mt-2 rounded-[12px] border border-[#e5e7eb] bg-[#fbfcff] px-3 py-2 font-mono text-[11px] leading-5 text-[#344054]">
                {exchanges[0].preview}
              </div>
            </div>
          ) : (
            <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-4 text-[13px] text-[#6b7280]">
              {copy.monitor.noExchangeYet}
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {cards.map((card) => (
            <div key={card.label} className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1.5">
              <span className="text-[10px] uppercase tracking-[0.14em] text-[#7b8190]">{card.label}</span>
              <span className="ml-2 text-[12px] font-medium tracking-[-0.02em] text-[#111111]">{card.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentPill({
  label,
  subtitle,
  accent,
}: {
  label: string;
  subtitle: string;
  accent?: string;
}) {
  return (
    <div className="rounded-[16px] border border-[#d6dbe6] bg-white px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[16px] font-medium tracking-[-0.03em] text-[#111111]">{label}</div>
        {accent ? (
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
            {accent}
          </div>
        ) : null}
      </div>
      <div className="mt-1 text-[13px] leading-5 text-[#6b7280]">{subtitle}</div>
    </div>
  );
}

function GenericView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const orchestrator = session.agents[0] ?? null;
  const workers = session.agents.slice(1, 3);
  const upperWorker = workers[0] ?? null;
  const lowerWorker = workers[1] ?? null;
  const upperTools = (upperWorker?.tools ?? []).slice(0, 2);
  const lowerTools = (lowerWorker?.tools ?? []).slice(0, 1);
  const attachedDetails = new Map((session.attached_tools ?? []).map((tool) => [tool.id, tool]));

  return (
    <div className="relative min-h-[360px] rounded-[18px] border border-[#d6dbe6] bg-white">
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 940 360" preserveAspectRatio="none">
        <path d="M110 180 C 180 180, 210 180, 270 180" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M328 180 C 430 180, 470 80, 620 80" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M328 180 C 430 180, 470 260, 620 260" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 88 C 740 88, 760 48, 810 48" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 108 C 740 108, 760 148, 810 148" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 268 C 740 268, 760 268, 810 268" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
      </svg>

      <div className="absolute left-[46px] top-[150px] flex flex-col items-center">
        <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
          <Folder className="h-9 w-9 text-[#9ca3af]" />
        </div>
        <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
          {copy.monitor.taskInput}
        </div>
      </div>

      {orchestrator ? (
        <div className="absolute left-[184px] top-[150px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {PROVIDER_LABELS[orchestrator.provider]?.[0] ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {PROVIDER_LABELS[orchestrator.provider] ?? orchestrator.provider}
            <br />
            ({orchestrator.role})
          </div>
        </div>
      ) : null}

      {upperWorker ? (
        <div className="absolute left-[590px] top-[28px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {PROVIDER_LABELS[upperWorker.provider]?.[0] ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {PROVIDER_LABELS[upperWorker.provider] ?? upperWorker.provider}
            <br />
            ({upperWorker.role})
          </div>
        </div>
      ) : null}

      {lowerWorker ? (
        <div className="absolute left-[590px] top-[232px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {PROVIDER_LABELS[lowerWorker.provider]?.[0] ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {PROVIDER_LABELS[lowerWorker.provider] ?? lowerWorker.provider}
            <br />
            ({lowerWorker.role})
          </div>
        </div>
      ) : null}

      {upperTools.map((tool, index) => {
        const detail = attachedDetails.get(tool);
        const Icon = resolveToolIcon(tool, detail);
        return (
          <div
            key={`upper-${tool}-${index}`}
            className="absolute flex flex-col items-center"
            style={{ left: "804px", top: `${index === 0 ? 16 : 132}px` }}
          >
            <div className="flex h-[68px] w-[68px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
              <Icon className="h-8 w-8 text-[#7b8190]" />
            </div>
            <div className="mt-2 text-center text-[18px] leading-tight text-[#111111]">
              {detail?.name ?? humanizeTool(tool)}
            </div>
          </div>
        );
      })}

      {lowerTools.map((tool, index) => {
        const detail = attachedDetails.get(tool);
        const Icon = resolveToolIcon(tool, detail);
        return (
          <div
            key={`lower-${tool}-${index}`}
            className="absolute flex flex-col items-center"
            style={{ left: "804px", top: `${index === 0 ? 236 : 152}px` }}
          >
            <div className="flex h-[68px] w-[68px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
              <Icon className="h-8 w-8 text-[#7b8190]" />
            </div>
            <div className="mt-2 text-center text-[18px] leading-tight text-[#111111]">
              {detail?.name ?? humanizeTool(tool)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BoardView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const directors = session.agents.slice(0, 3);
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestDecision = latestEvent(events, "round_completed");
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
      {directors.map((director) => (
        <AgentPill
          key={director.role}
          label={director.role}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === director.role)?.detail ||
            latestMessage(session.messages, director.role)?.content?.slice(0, 160) ||
            copy.monitor.waitingBoardPosition
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.consensusState}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestDecision?.detail || session.result || copy.monitor.waitingBoardPosition}
        </div>
      </div>
    </div>
  );
}

function DemocracyView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestMajority = latestEvent(events, "round_completed");
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
      {session.agents.map((agent) => (
        <AgentPill
          key={agent.role}
          label={agent.role}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === agent.role)?.detail ||
            latestMessage(session.messages, agent.role)?.content?.replace(/^Vote:\s*/i, "").slice(0, 140) ||
            copy.monitor.waitingVote
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.majorityState}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestMajority?.detail || session.result || copy.monitor.noMajorityYet}
        </div>
      </div>
    </div>
  );
}

function DebateView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const [proponent, opponent, judge] = session.agents;
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestVerdict = latestEvent(events, "round_completed");
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)]">
      <AgentPill
        label={proponent?.role ?? "proponent"}
        subtitle={proponent ? latestMessage(session.messages, proponent.role)?.content?.slice(0, 180) || copy.monitor.awaitingArgument : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="flex items-center justify-center text-[#9ca3af]">
        <ArrowRight className="h-6 w-6" />
      </div>
      <AgentPill
        label={opponent?.role ?? "opponent"}
        subtitle={opponent ? latestMessage(session.messages, opponent.role)?.content?.slice(0, 180) || copy.monitor.awaitingRebuttal : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.judgeVerdict}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestVerdict?.detail || (judge ? latestMessage(session.messages, judge.role)?.content || session.result || copy.monitor.noVerdictYet : session.result)}
        </div>
      </div>
    </div>
  );
}

function CreatorCriticView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const iterations = session.messages.filter(
    (message) => message.phase.startsWith("version_") || message.phase.startsWith("critique_")
  );
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-white p-5">
      <div className="space-y-3">
        {iterations.map((message) => (
          <div key={`${message.agent_id}-${message.timestamp}`} className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">
              {message.agent_id} · {message.phase.replace(/_/g, " ")}
            </div>
            <div className="mt-2 text-[14px] leading-6 text-[#111111]">{message.content}</div>
          </div>
        ))}
        {iterations.length === 0 ? (
          <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 text-[14px] text-[#6b7280]">
            {copy.monitor.iterationsHint}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MapReduceView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const planner = session.agents[0];
  const workers = session.agents.slice(1, -1);
  const synthesizer = session.agents[session.agents.length - 1];
  const chunkEvents = recentEvents(session.events ?? [], "chunk_completed", 4);
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
      <AgentPill
        label={planner?.role ?? "planner"}
        subtitle={planner ? latestMessage(session.messages, planner.role)?.content || copy.monitor.plannerPreparing : "—"}
      />
      <div className="space-y-3 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.workers}</div>
        {workers.map((worker) => (
          <div key={worker.role} className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3">
            <div className="text-[14px] font-medium text-[#111111]">{worker.role}</div>
            <div className="mt-1 text-[12px] leading-5 text-[#6b7280]">
              {latestEvent(session.events ?? [], "chunk_completed", (event) => event.agent_id === worker.role)?.detail ||
                latestMessage(session.messages, worker.role)?.content?.slice(0, 120) ||
                copy.monitor.waitingChunkOutput}
            </div>
          </div>
        ))}
        {chunkEvents.length > 0 ? (
          <div className="space-y-2 rounded-[14px] border border-dashed border-[#d6dbe6] bg-white px-3 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{copy.monitor.recentChunks}</div>
            {chunkEvents.map((event) => (
              <div key={event.id} className="text-[12px] leading-5 text-[#6b7280]">
                <span className="font-medium text-[#111111]">{event.agent_id || "worker"}</span>
                {" · "}
                {event.detail}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <AgentPill
        label={synthesizer?.role ?? "synthesizer"}
        subtitle={synthesizer ? latestMessage(session.messages, synthesizer.role)?.content || session.result || copy.monitor.synthesisPending : "—"}
      />
    </div>
  );
}

export function TopologyPanel({ session }: TopologyPanelProps) {
  const { copy } = useLocale();
  let content = <GenericView session={session} />;
  if (session.mode === "board") content = <BoardView session={session} />;
  else if (session.mode === "democracy") content = <DemocracyView session={session} />;
  else if (session.mode === "debate") content = <DebateView session={session} />;
  else if (session.mode === "creator_critic") content = <CreatorCriticView session={session} />;
  else if (session.mode === "map_reduce") content = <MapReduceView session={session} />;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)]">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111]">
        {shellTitle(session, copy)}
      </h2>
      <div className="mt-5 space-y-4">
        <ConnectionCanvas session={session} />
        {session.mode === "dictator" || session.mode === "tournament" ? null : content}
      </div>
    </section>
  );
}
