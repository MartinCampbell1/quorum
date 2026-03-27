"use client";

import { ArrowRight, Folder, Globe, HardDrive, Sparkles, TerminalSquare, type LucideIcon } from "lucide-react";

import { PROVIDER_LABELS } from "@/lib/constants";
import type { AttachedToolDetail, Message, Session, SessionEvent } from "@/lib/types";

interface TopologyPanelProps {
  session: Session;
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

function shellTitle(session: Session) {
  if (session.mode === "board") return "Board Consensus Canvas";
  if (session.mode === "democracy") return "Voting Chamber";
  if (session.mode === "debate") return "Debate Arena";
  if (session.mode === "creator_critic") return "Iteration Stack";
  if (session.mode === "map_reduce") return "Planner / Workers / Synthesis";
  return "Agent & MCP Server Topology";
}

function providerMark(provider: string) {
  return PROVIDER_LABELS[provider]?.[0] ?? provider.slice(0, 1).toUpperCase();
}

function fallbackToolDetail(toolId: string): AttachedToolDetail {
  return {
    id: toolId,
    name: humanizeTool(toolId),
    tool_type: null,
    transport: "unknown",
    subtitle: "MCP connection",
    icon: "folder",
    capability: "native",
  };
}

function ConnectionCanvas({ session }: { session: Session }) {
  const detailMap = new Map((session.attached_tools ?? []).map((tool) => [tool.id, tool]));
  const agents = session.agents.slice(0, 3);
  const toolNodes = (session.attached_tools ?? []).slice(0, 4);
  const latestToolEvent = latestEvent(session.events ?? [], "tool_call_finished") ?? latestEvent(session.events ?? [], "tool_call_started");
  const signalCards = [
    {
      label: "Active Node",
      value: session.active_node || "idle",
    },
    {
      label: "Checkpoint",
      value: session.current_checkpoint_id || "pending",
    },
    {
      label: "Live Tool",
      value: latestToolEvent?.tool_name || latestToolEvent?.detail || "No tool activity yet",
    },
  ];

  const agentY = agents.length === 1
    ? [150]
    : agents.length === 2
      ? [92, 228]
      : [42, 150, 258];
  const toolY = toolNodes.length <= 1
    ? [142]
    : toolNodes.length === 2
      ? [82, 210]
      : toolNodes.length === 3
        ? [36, 146, 254]
        : [18, 110, 202, 294];

  return (
    <div className="relative min-h-[438px] overflow-hidden rounded-[20px] border border-[#d6dbe6] bg-white">
      <div className="absolute inset-x-0 top-0 h-[96px] bg-[radial-gradient(circle_at_top,rgba(226,231,247,0.58),rgba(255,255,255,0))]" />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 940 438" preserveAspectRatio="none">
        {agents.map((_, index) => (
          <path
            key={`input-agent-${index}`}
            d={`M130 168 C 220 168, 250 ${agentY[index] + 35}, 332 ${agentY[index] + 35}`}
            fill="none"
            stroke="#a8b0c2"
            strokeWidth="2"
          />
        ))}
        {agents.map((agent, index) => {
          const toolId = agent.tools?.[0];
          const toolIndex = toolId
            ? toolNodes.findIndex((tool) => tool.id === toolId)
            : Math.min(index, toolNodes.length - 1);
          if (toolIndex < 0) return null;
          return (
            <path
              key={`agent-tool-${agent.role}`}
              d={`M462 ${agentY[index] + 35} C 552 ${agentY[index] + 35}, 608 ${toolY[toolIndex] + 31}, 706 ${toolY[toolIndex] + 31}`}
              fill="none"
              stroke="#a8b0c2"
              strokeWidth="2"
            />
          );
        })}
      </svg>

      <div className="absolute left-[34px] top-[132px] flex w-[108px] flex-col items-center">
        <div className="flex h-[78px] w-[78px] items-center justify-center rounded-[18px] border border-[#d1d5db] bg-white shadow-[0_12px_32px_-24px_rgba(17,48,105,0.35)]">
          <Folder className="h-8 w-8 text-[#7b8190]" />
        </div>
        <div className="mt-3 text-center text-[22px] leading-tight tracking-[-0.04em] text-[#111111]">
          Session
          <br />
          Task
        </div>
        <div className="mt-1 text-center text-[12px] leading-5 text-[#7b8190]">
          {session.task.slice(0, 46)}
        </div>
      </div>

      {agents.map((agent, index) => (
        <div
          key={agent.role}
          className="absolute left-[332px] flex w-[132px] flex-col items-center"
          style={{ top: `${agentY[index]}px` }}
        >
          <div className="flex h-[78px] w-[78px] items-center justify-center rounded-[18px] border border-[#d1d5db] bg-white text-[40px] font-semibold text-[#6b7280] shadow-[0_12px_32px_-24px_rgba(17,48,105,0.35)]">
            {providerMark(agent.provider)}
          </div>
          <div className="mt-3 text-center text-[22px] leading-tight tracking-[-0.04em] text-[#111111]">
            {PROVIDER_LABELS[agent.provider] ?? agent.provider}
          </div>
          <div className="mt-1 text-center text-[13px] leading-5 text-[#6b7280]">
            {agent.role}
          </div>
        </div>
      ))}

      {toolNodes.map((tool, index) => {
        const Icon = resolveToolIcon(tool.id, tool);
        return (
          <div
            key={tool.id}
            className="absolute left-[706px] flex w-[178px] items-start gap-3 rounded-[18px] border border-[#d6dbe6] bg-white px-4 py-4 shadow-[0_12px_32px_-24px_rgba(17,48,105,0.28)]"
            style={{ top: `${toolY[index]}px` }}
          >
            <div className="flex h-[58px] w-[58px] shrink-0 items-center justify-center rounded-[16px] border border-[#d6dbe6] bg-[#fafbff]">
              <Icon className="h-7 w-7 text-[#7b8190]" />
            </div>
            <div className="min-w-0">
              <div className="text-[17px] font-medium tracking-[-0.03em] text-[#111111]">{tool.name}</div>
              <div className="mt-1 text-[12px] leading-5 text-[#6b7280]">{tool.subtitle}</div>
              <div className="mt-2 inline-flex rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
                {tool.capability}
              </div>
            </div>
          </div>
        );
      })}

      <div className="absolute inset-x-4 bottom-4 grid gap-3 md:grid-cols-3">
        {signalCards.map((card) => (
          <div key={card.label} className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">{card.label}</div>
            <div className="mt-1 text-[15px] font-medium tracking-[-0.03em] text-[#111111]">{card.value}</div>
          </div>
        ))}
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
          Task
          <br />
          Input
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
            "Waiting for board position…"
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">Consensus state</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestDecision?.detail || session.result || "Board is still discussing and aligning positions."}
        </div>
      </div>
    </div>
  );
}

function DemocracyView({ session }: { session: Session }) {
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
            "Waiting for vote…"
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">Majority state</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestMajority?.detail || session.result || "No majority yet. Additional rounds may be required."}
        </div>
      </div>
    </div>
  );
}

function DebateView({ session }: { session: Session }) {
  const [proponent, opponent, judge] = session.agents;
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestVerdict = latestEvent(events, "round_completed");
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)]">
      <AgentPill
        label={proponent?.role ?? "proponent"}
        subtitle={proponent ? latestMessage(session.messages, proponent.role)?.content?.slice(0, 180) || "Awaiting argument…" : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="flex items-center justify-center text-[#9ca3af]">
        <ArrowRight className="h-6 w-6" />
      </div>
      <AgentPill
        label={opponent?.role ?? "opponent"}
        subtitle={opponent ? latestMessage(session.messages, opponent.role)?.content?.slice(0, 180) || "Awaiting rebuttal…" : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">Judge verdict</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111]">
          {latestVerdict?.detail || (judge ? latestMessage(session.messages, judge.role)?.content || session.result || "Judge has not ruled yet." : session.result)}
        </div>
      </div>
    </div>
  );
}

function CreatorCriticView({ session }: { session: Session }) {
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
            Iterations will appear once creator and critic exchange drafts.
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MapReduceView({ session }: { session: Session }) {
  const planner = session.agents[0];
  const workers = session.agents.slice(1, -1);
  const synthesizer = session.agents[session.agents.length - 1];
  const chunkEvents = recentEvents(session.events ?? [], "chunk_completed", 4);
  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
      <AgentPill
        label={planner?.role ?? "planner"}
        subtitle={planner ? latestMessage(session.messages, planner.role)?.content || "Planner preparing chunks…" : "—"}
      />
      <div className="space-y-3 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">Workers</div>
        {workers.map((worker) => (
          <div key={worker.role} className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3">
            <div className="text-[14px] font-medium text-[#111111]">{worker.role}</div>
            <div className="mt-1 text-[12px] leading-5 text-[#6b7280]">
              {latestEvent(session.events ?? [], "chunk_completed", (event) => event.agent_id === worker.role)?.detail ||
                latestMessage(session.messages, worker.role)?.content?.slice(0, 120) ||
                "Waiting for chunk output…"}
            </div>
          </div>
        ))}
        {chunkEvents.length > 0 ? (
          <div className="space-y-2 rounded-[14px] border border-dashed border-[#d6dbe6] bg-white px-3 py-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190]">Recent chunks</div>
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
        subtitle={synthesizer ? latestMessage(session.messages, synthesizer.role)?.content || session.result || "Synthesis pending…" : "—"}
      />
    </div>
  );
}

export function TopologyPanel({ session }: TopologyPanelProps) {
  let content = <GenericView session={session} />;
  if (session.mode === "board") content = <BoardView session={session} />;
  else if (session.mode === "democracy") content = <DemocracyView session={session} />;
  else if (session.mode === "debate") content = <DebateView session={session} />;
  else if (session.mode === "creator_critic") content = <CreatorCriticView session={session} />;
  else if (session.mode === "map_reduce") content = <MapReduceView session={session} />;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)]">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111]">
        {shellTitle(session)}
      </h2>
      <div className="mt-5 space-y-4">
        <ConnectionCanvas session={session} />
        {session.mode === "dictator" || session.mode === "tournament" ? null : content}
      </div>
    </section>
  );
}
