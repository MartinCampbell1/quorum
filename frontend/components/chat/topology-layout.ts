import { useEffect, useRef, useState } from "react";

import ELK, { type ElkExtendedEdge, type ElkNode } from "elkjs/lib/elk.bundled.js";

import { useLocale } from "@/lib/locale";
import type { Session } from "@/lib/types";

import {
  buildAgentFlowNode,
  buildTaskFlowNode,
  buildTournamentStructure,
  flowNode,
  humanizeRole,
  latestRoundLabel,
  providerLabel,
  resolveNodeDimensions,
  tournamentRoundLabel,
  type FlowCanvasGraph,
  type FlowEdge,
  type LocaleCopy,
  type SessionAgent,
  type TopologyNodeDescriptor,
  type TopologyFlowNodeData,
  type TournamentStructure,
} from "./topology-model";

const elk = new ELK();

type Point = { x: number; y: number };

interface CreatorCriticIntent {
  mode: "creator_critic";
  task: Point;
  creator: Point;
  relay: Point;
  critic: Point;
  feedback: Point;
  stageHeight: number;
}

interface DemocracyIntent {
  mode: "democracy";
  task: Point;
  chamber: Point;
  seats: Point[];
  stageHeight: number;
}

interface MapReduceIntent {
  mode: "map_reduce";
  task: Point;
  planner: Point;
  workers: Point[];
  synthesis: Point;
  stageHeight: number;
}

function spreadPositions(count: number, center: number, spread: number) {
  if (count <= 0) return [];
  if (count === 1) return [center];

  return Array.from({ length: count }, (_, index) =>
    Math.round(center - spread / 2 + (spread / (count - 1)) * index)
  );
}

function distributeY(count: number, top: number, bottom: number) {
  if (count <= 0) return [];
  if (count === 1) return [Math.round((top + bottom) / 2)];

  const step = (bottom - top) / (count - 1);
  return Array.from({ length: count }, (_, index) => Math.round(top + step * index));
}

function arcPositions(
  count: number,
  centerX: number,
  centerY: number,
  radiusX: number,
  radiusY: number,
  startDeg: number,
  endDeg: number
) {
  if (count <= 0) return [];
  if (count === 1) {
    const angle = ((startDeg + endDeg) / 2) * (Math.PI / 180);
    return [{ x: Math.round(centerX + Math.cos(angle) * radiusX), y: Math.round(centerY + Math.sin(angle) * radiusY) }];
  }

  return Array.from({ length: count }, (_, index) => {
    const ratio = index / (count - 1);
    const angle = (startDeg + (endDeg - startDeg) * ratio) * (Math.PI / 180);
    return {
      x: Math.round(centerX + Math.cos(angle) * radiusX),
      y: Math.round(centerY + Math.sin(angle) * radiusY),
    };
  });
}

function gridPositions(
  count: number,
  columns: number,
  startX: number,
  startY: number,
  gapX: number,
  gapY: number
) {
  return Array.from({ length: count }, (_, index) => ({
    x: Math.round(startX + (index % columns) * gapX),
    y: Math.round(startY + Math.floor(index / columns) * gapY),
  }));
}

function centerToTopLeft(
  kind: TopologyFlowNodeData["kind"],
  center: Point,
  density: TopologyFlowNodeData["density"] = "default",
  variant: TopologyFlowNodeData["variant"] = "default"
) {
  const dimensions = resolveNodeDimensions(kind, density, variant);

  return {
    x: Math.round(center.x - dimensions.width / 2),
    y: Math.round(center.y - dimensions.height / 2),
  };
}

function placeTaskNode(session: Session, copy: LocaleCopy, center: Point, density: TopologyFlowNodeData["density"] = "tight") {
  const position = centerToTopLeft("task", center, density);
  return buildTaskFlowNode(session, copy, position.x, position.y, density);
}

function placeAgentNode(
  agent: SessionAgent,
  center: Point,
  options?: Partial<Pick<TopologyFlowNodeData, "density" | "variant" | "eyebrow">>
) {
  const position = centerToTopLeft("agent", center, options?.density, options?.variant);
  return buildAgentFlowNode(agent, position.x, position.y, options);
}

function placeFlowNode(id: string, center: Point, data: TopologyNodeDescriptor) {
  const position = centerToTopLeft(data.kind, center, data.density, data.variant);
  return flowNode(id, position.x, position.y, data);
}

function graphBounds(nodes: FlowCanvasGraph["nodes"]) {
  if (nodes.length === 0) {
    return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
  }

  const left = Math.min(...nodes.map((node) => node.position.x));
  const top = Math.min(...nodes.map((node) => node.position.y));
  const right = Math.max(...nodes.map((node) => node.position.x + node.data.dimensions.width));
  const bottom = Math.max(...nodes.map((node) => node.position.y + node.data.dimensions.height));

  return {
    left,
    top,
    right,
    bottom,
    width: right - left,
    height: bottom - top,
  };
}

function zoneFromBounds(
  label: string,
  bounds: { left: number; top: number; right: number; bottom: number },
  layoutWidth: number,
  stageHeight: number
) {
  const padX = 24;
  const padY = 18;
  const width = Math.max(0, bounds.right - bounds.left + padX * 2);
  const height = Math.max(0, bounds.bottom - bounds.top + padY * 2);
  const left = Math.max(0, bounds.left - padX);
  const top = Math.max(0, bounds.top - padY);

  return {
    label,
    left: `${(left / layoutWidth) * 100}%`,
    width: `${(width / layoutWidth) * 100}%`,
    top: `${(top / stageHeight) * 100}%`,
    height: `${(height / stageHeight) * 100}%`,
  };
}

function buildCreatorCriticIntent(): CreatorCriticIntent {
  return {
    mode: "creator_critic",
    task: { x: 210, y: 104 },
    creator: { x: 284, y: 286 },
    relay: { x: 540, y: 126 },
    critic: { x: 816, y: 286 },
    feedback: { x: 540, y: 430 },
    stageHeight: 516,
  };
}

function buildDemocracyIntent(agentCount: number): DemocracyIntent {
  const outerSeatCount = agentCount <= 5 ? agentCount : Math.min(5, agentCount);
  const seats = [
    ...arcPositions(
      outerSeatCount,
      558,
      334,
      agentCount > 6 ? 326 : 296,
      agentCount > 6 ? 166 : 148,
      174,
      6
    ),
    ...(agentCount > outerSeatCount
      ? arcPositions(agentCount - outerSeatCount, 558, 314, 220, 102, 160, 20)
      : []),
  ];

  return {
    mode: "democracy",
    task: { x: 228, y: 104 },
    chamber: { x: 558, y: 172 },
    seats,
    stageHeight: 520,
  };
}

function buildMapReduceIntent(workerCount: number): MapReduceIntent {
  const workers =
    workerCount <= 3
      ? distributeY(workerCount, 164, 356).map((y) => ({ x: 552, y }))
      : gridPositions(workerCount, 2, 472, 164, 152, 108);
  const rowCount = workerCount <= 3 ? workerCount : Math.ceil(workerCount / 2);
  const stageHeight = rowCount >= 3 ? 544 : 492;

  return {
    mode: "map_reduce",
    task: { x: 210, y: 98 },
    planner: { x: 228, y: Math.round(stageHeight / 2) },
    workers,
    synthesis: { x: 816, y: Math.round(stageHeight / 2) },
    stageHeight,
  };
}

function buildBoardFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const agents = session.agents;
  const compact = agents.length > 4;
  const stageHeight = Math.max(392, 232 + Math.max(0, agents.length - 1) * 36);
  const ys = spreadPositions(agents.length, Math.round(stageHeight / 2), Math.min(292, 76 * Math.max(1, agents.length - 1)));

  return {
    nodes: [
      placeTaskNode(session, copy, { x: 176, y: 98 }),
      placeFlowNode("hub", { x: 360, y: Math.round(stageHeight / 2) }, {
        kind: "hub",
        label: copy.monitor.sharedContexts.board,
        subtitle: latestRoundLabel(session.events ?? []) ?? "board",
        density: "compact",
      }),
      ...agents.map((agent, index) =>
        placeAgentNode(agent, { x: 788, y: ys[index] ?? Math.round(stageHeight / 2) }, { density: compact ? "compact" : "default" })
      ),
    ],
    edges: [
      {
        id: "task->hub",
        source: "task",
        target: "hub",
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "smoothstep",
      },
      ...agents.map((agent) => ({
        id: `hub->agent:${agent.role}`,
        source: "hub",
        target: `agent:${agent.role}`,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "smoothstep" as const,
      })),
    ],
    stageHeight,
    fitPadding: 0.04,
    maxZoom: 1.54,
  };
}

function buildDemocracyFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const agents = session.agents;
  const dense = agents.length > 5;
  const intent = buildDemocracyIntent(agents.length);
  const chamber = placeFlowNode("hub", intent.chamber, {
    kind: "hub",
    label: copy.monitor.sharedContexts.democracy,
    subtitle: latestRoundLabel(session.events ?? []) ?? "vote",
    density: dense ? "compact" : "default",
    variant: "chamber",
  });

  return {
    nodes: [
      placeTaskNode(session, copy, intent.task),
      chamber,
      ...agents.map((agent, index) =>
        placeAgentNode(agent, intent.seats[index] ?? intent.chamber, {
          density: dense ? "compact" : "default",
          eyebrow: `seat ${index + 1}`,
        })
      ),
    ],
    edges: [
      {
        id: "task->hub",
        source: "task",
        target: "hub",
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "smoothstep",
      },
      ...agents.map((agent, index) => {
        const seatX = intent.seats[index]?.x ?? intent.chamber.x;
        return {
          id: `agent:${agent.role}->hub`,
          source: `agent:${agent.role}`,
          target: "hub",
          sourceHandle: "st",
          targetHandle: seatX < intent.chamber.x - 46 ? "tl" : seatX > intent.chamber.x + 46 ? "tr" : "tb",
          type: "smoothstep" as const,
          pathOptions: { borderRadius: 40, offset: 22 },
        };
      }),
    ],
    stageHeight: intent.stageHeight,
    fitPadding: 0.03,
    maxZoom: 1.36,
    backdrop: {
      variant: "chamber",
    },
  };
}

function buildDebateFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const proponent = session.agents[0];
  const opponent = session.agents[1];
  const judge = session.agents[2];

  const nodes = [
    placeTaskNode(session, copy, { x: 236, y: 110 }),
    placeFlowNode("hub", { x: 520, y: 190 }, { kind: "hub", label: copy.monitor.sharedContexts.default, subtitle: "arena" }),
  ];

  if (judge) {
    nodes.push(placeAgentNode(judge, { x: 520, y: 74 }, { density: "compact", eyebrow: "judge" }));
  }

  if (proponent) {
    nodes.push(placeAgentNode(proponent, { x: 320, y: 332 }));
  }

  if (opponent) {
    nodes.push(placeAgentNode(opponent, { x: 722, y: 332 }));
  }

  const edges: FlowEdge[] = [
    {
      id: "task->hub",
      source: "task",
      target: "hub",
      sourceHandle: "sr",
      targetHandle: "tl",
      type: "smoothstep",
    },
  ];

  if (judge) {
    edges.push({
      id: "debate:judge",
      source: "hub",
      target: `agent:${judge.role}`,
      sourceHandle: "st",
      targetHandle: "tb",
      type: "smoothstep",
    });
  }

  if (proponent) {
    edges.push({
      id: `hub->agent:${proponent.role}`,
      source: "hub",
      target: `agent:${proponent.role}`,
      sourceHandle: "sb",
      targetHandle: "tt",
      type: "smoothstep",
    });
  }

  if (opponent) {
    edges.push({
      id: `hub->agent:${opponent.role}`,
      source: "hub",
      target: `agent:${opponent.role}`,
      sourceHandle: "sb",
      targetHandle: "tt",
      type: "smoothstep",
    });
  }

  if (proponent && opponent) {
    edges.push({
      id: `agent:${proponent.role}->agent:${opponent.role}`,
      source: `agent:${proponent.role}`,
      target: `agent:${opponent.role}`,
      sourceHandle: "sr",
      targetHandle: "tl",
      type: "smoothstep",
    });
  }

  return { nodes, edges, stageHeight: 436, fitPadding: 0.045, maxZoom: 1.52 };
}

function buildCreatorCriticFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const creator = session.agents[0];
  const critic = session.agents[1];
  const intent = buildCreatorCriticIntent();
  const nodes = [
    placeTaskNode(session, copy, intent.task),
    placeFlowNode("draft", intent.relay, {
      kind: "hub",
      label: copy.monitor.sharedContexts.creator_critic,
      subtitle: "draft relay",
      density: "compact",
    }),
    placeFlowNode("feedback", intent.feedback, {
      kind: "match",
      label: "FEEDBACK",
      subtitle: "critic -> creator",
      density: "compact",
    }),
  ];
  const edges: FlowEdge[] = [];

  if (creator) {
    nodes.push(placeAgentNode(creator, intent.creator, { eyebrow: "author" }));
    edges.push(
      {
        id: `task->agent:${creator.role}`,
        source: "task",
        target: `agent:${creator.role}`,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "smoothstep",
      },
      {
        id: `agent:${creator.role}->draft`,
        source: `agent:${creator.role}`,
        target: "draft",
        sourceHandle: "st",
        targetHandle: "tl",
        type: "smoothstep",
      }
    );
  }

  if (critic) {
    nodes.push(placeAgentNode(critic, intent.critic, { eyebrow: "review" }));
    edges.push(
      {
        id: `draft->agent:${critic.role}`,
        source: "draft",
        target: `agent:${critic.role}`,
        sourceHandle: "sr",
        targetHandle: "tt",
        type: "smoothstep",
      },
      {
        id: `agent:${critic.role}->feedback`,
        source: `agent:${critic.role}`,
        target: "feedback",
        sourceHandle: "sb",
        targetHandle: "tr",
        type: "smoothstep",
      }
    );
  }

  if (creator) {
    edges.push({
      id: `feedback->agent:${creator.role}`,
      source: "feedback",
      target: `agent:${creator.role}`,
      sourceHandle: "sl",
      targetHandle: "tb",
      type: "smoothstep",
      style: { stroke: "#6366f1", strokeDasharray: "8 6", opacity: 0.94 },
    });
  }

  return {
    nodes,
    edges,
    stageHeight: intent.stageHeight,
    fitPadding: 0.028,
    maxZoom: 1.3,
    backdrop: {
      variant: "loop",
    },
  };
}

function buildDictatorFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const dictator = session.agents[0];
  const workers = session.agents.slice(1, 9);
  const nodes = [placeTaskNode(session, copy, { x: 248, y: 118 })];
  const edges: FlowEdge[] = [];

  if (!dictator) {
    return { nodes, edges };
  }

  nodes.push(placeAgentNode(dictator, { x: 520, y: 92 }, { eyebrow: "lead" }));
  edges.push({
    id: `task->agent:${dictator.role}`,
    source: "task",
    target: `agent:${dictator.role}`,
    sourceHandle: "sr",
    targetHandle: "tl",
    type: "smoothstep",
  });

  const topRow = workers.slice(0, Math.ceil(workers.length / 2));
  const bottomRow = workers.slice(Math.ceil(workers.length / 2));
  const topXs = spreadPositions(topRow.length, 520, 420);
  const bottomXs = spreadPositions(bottomRow.length, 520, 420);

  [...topRow, ...bottomRow].forEach((worker, index) => {
    const inTop = index < topRow.length;
    const x = inTop ? topXs[index] : bottomXs[index - topRow.length];
    const y = inTop ? 286 : 394;
    nodes.push(placeAgentNode(worker, { x: x ?? 520, y }, { density: "compact" }));
    edges.push({
      id: `agent:${dictator.role}->agent:${worker.role}`,
      source: `agent:${dictator.role}`,
      target: `agent:${worker.role}`,
      sourceHandle: "sb",
      targetHandle: "tt",
      type: "smoothstep",
    });
  });

  return { nodes, edges, stageHeight: bottomRow.length > 0 ? 504 : 432, fitPadding: 0.05, maxZoom: 1.42 };
}

function buildMapReduceFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const planner = session.agents[0];
  const synthesizer = session.agents.length >= 3 ? session.agents[session.agents.length - 1] : null;
  const workers = session.agents.slice(1, synthesizer ? -1 : undefined).slice(0, 6);
  const denseWorkers = workers.length > 4;
  const intent = buildMapReduceIntent(workers.length);
  const nodes = [placeTaskNode(session, copy, intent.task)];
  const edges: FlowEdge[] = [];

  if (planner) {
    nodes.push(placeAgentNode(planner, intent.planner, { eyebrow: "plan" }));
    edges.push({
      id: `task->agent:${planner.role}`,
      source: "task",
      target: `agent:${planner.role}`,
      sourceHandle: "sr",
      targetHandle: "tl",
      type: "step",
      pathOptions: { offset: 18 },
    });
  }

  workers.forEach((worker, index) => {
    nodes.push(
      placeAgentNode(worker, intent.workers[index] ?? intent.planner, {
        density: denseWorkers ? "compact" : "default",
        eyebrow: "worker",
      })
    );

    if (planner) {
      edges.push({
        id: `agent:${planner.role}->agent:${worker.role}`,
        source: `agent:${planner.role}`,
        target: `agent:${worker.role}`,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "step",
        pathOptions: { offset: 18 },
      });
    }
  });

  if (synthesizer) {
    nodes.push(
      placeFlowNode("synth", intent.synthesis, {
        kind: "hub",
        label: copy.monitor.sharedContexts.map_reduce,
        subtitle: humanizeRole(synthesizer.role),
        eyebrow: providerLabel(synthesizer.provider),
        density: "compact",
      })
    );

    workers.forEach((worker) => {
      edges.push({
        id: `agent:${worker.role}->synth`,
        source: `agent:${worker.role}`,
        target: "synth",
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "step",
        pathOptions: { offset: 18 },
      });
    });
  }

  const layoutWidth = 960;
  return {
    nodes,
    edges,
    stageHeight: intent.stageHeight,
    fitPadding: 0.025,
    maxZoom: 1.28,
    backdrop: {
      variant: "pipeline",
      zones: [
        { label: humanizeRole(planner?.role ?? "planner"), left: `${(118 / layoutWidth) * 100}%`, width: `${(188 / layoutWidth) * 100}%`, top: "16%", height: "68%" },
        { label: copy.monitor.workers, left: `${(350 / layoutWidth) * 100}%`, width: `${(320 / layoutWidth) * 100}%`, top: "12%", height: "76%" },
        { label: copy.monitor.sharedContexts.map_reduce, left: `${(712 / layoutWidth) * 100}%`, width: `${(190 / layoutWidth) * 100}%`, top: "16%", height: "68%" },
      ],
    },
  };
}

function buildDefaultFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const primary = session.agents[0];
  const secondary = session.agents.slice(1, 7);
  const secondaryPositions = arcPositions(
    secondary.length,
    770,
    238,
    secondary.length > 4 ? 238 : 202,
    secondary.length > 4 ? 162 : 132,
    -38,
    38
  );
  const nodes = [placeTaskNode(session, copy, { x: 214, y: 104 })];
  const edges: FlowEdge[] = [];

  if (primary) {
    nodes.push(placeAgentNode(primary, { x: 320, y: 238 }, { eyebrow: "lead" }));
    edges.push({
      id: `task->agent:${primary.role}`,
      source: "task",
      target: `agent:${primary.role}`,
      sourceHandle: "sr",
      targetHandle: "tl",
      type: "smoothstep",
    });
  }

  secondary.forEach((agent, index) => {
    nodes.push(placeAgentNode(agent, secondaryPositions[index] ?? { x: 760, y: 238 }, { density: "compact" }));
    if (primary) {
      edges.push({
        id: `agent:${primary.role}->agent:${agent.role}`,
        source: `agent:${primary.role}`,
        target: `agent:${agent.role}`,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "smoothstep",
        style: { stroke: "#6366f1", strokeDasharray: "6 6", opacity: 0.92 },
      });
    }
  });

  return { nodes, edges, stageHeight: 410, fitPadding: 0.04, maxZoom: 1.48 };
}

function fallbackTournamentCenters(structure: TournamentStructure, dense: boolean) {
  const stageTop = dense ? 118 : structure.slotCount <= 2 ? 184 : 138;
  const stageBottom = dense ? 468 : structure.slotCount <= 2 ? 318 : 414;
  const slotYs = distributeY(structure.slotCount, stageTop, stageBottom);
  const entrantX = 250;
  const playInX = structure.playInMatchCount > 0 ? 410 : null;
  const mainStartX = structure.playInMatchCount > 0 ? 570 : structure.slotCount >= 8 ? 438 : structure.slotCount <= 2 ? 600 : 500;
  const roundGap = structure.slotCount >= 8 ? 154 : structure.slotCount <= 2 ? 182 : 164;

  return { slotYs, entrantX, playInX, mainStartX, roundGap };
}

function buildTournamentFallbackFlowGraph(session: Session, copy: LocaleCopy): FlowCanvasGraph {
  const structure = buildTournamentStructure(session.agents);
  const entrants = structure.entrants;

  if (entrants.length === 0) {
    return { nodes: [], edges: [], stageHeight: 420, fitPadding: 0.04, maxZoom: 1.3 };
  }

  if (entrants.length === 1) {
    const onlyEntrant = entrants[0];
    return {
      nodes: [
        placeTaskNode(session, copy, { x: 228, y: 118 }),
        placeAgentNode(onlyEntrant, { x: 370, y: 210 }, { eyebrow: "seeded" }),
        placeFlowNode("hub", { x: 720, y: 210 }, {
          kind: "hub",
          label: copy.monitor.sharedContexts.tournament,
          subtitle: "winner",
          density: "compact",
        }),
      ],
      edges: [
        {
          id: `task->agent:${onlyEntrant.role}`,
          source: "task",
          target: `agent:${onlyEntrant.role}`,
          sourceHandle: "sr",
          targetHandle: "tl",
          type: "step",
          pathOptions: { offset: 20 },
        },
        {
          id: `agent:${onlyEntrant.role}->hub`,
          source: `agent:${onlyEntrant.role}`,
          target: "hub",
          sourceHandle: "sr",
          targetHandle: "tl",
          type: "step",
          pathOptions: { offset: 20 },
        },
      ],
      stageHeight: 420,
      fitPadding: 0.04,
      maxZoom: 1.36,
      backdrop: {
        variant: "bracket",
        zones: [
          { label: "ENTRANT", left: "18%", width: "18%", top: "20%", height: "56%" },
          { label: "WINNER", left: "58%", width: "18%", top: "20%", height: "56%" },
        ],
      },
    };
  }

  const dense = entrants.length >= 6;
  const stageHeight = dense ? 588 : structure.playInMatchCount > 0 ? 536 : 492;
  const entrantDensity: TopologyFlowNodeData["density"] = dense ? "compact" : "default";
  const { slotYs, entrantX, playInX, mainStartX, roundGap } = fallbackTournamentCenters(structure, dense);
  const nodes = [placeTaskNode(session, copy, { x: 224, y: 110 })];
  const edges: FlowEdge[] = [];
  const pairGap = dense ? 56 : structure.slotCount <= 2 ? 66 : 60;

  type BracketEntry = { id: string; y: number };
  const roundEntries: BracketEntry[] = [];
  let playInIndex = 0;

  structure.slots.forEach((slot) => {
    const slotY = slotYs[slot.slotIndex] ?? Math.round(stageHeight / 2);

    if (slot.kind === "direct") {
      nodes.push(
        placeAgentNode(slot.agent, { x: entrantX, y: slotY }, {
          density: entrantDensity,
          eyebrow: structure.playInMatchCount > 0 ? "seeded" : undefined,
        })
      );
      roundEntries.push({ id: `agent:${slot.agent.role}`, y: slotY });
      return;
    }

    const matchIndex = playInIndex;
    const playInId = `playin:${matchIndex}`;
    const [topEntrant, bottomEntrant] = slot.pair;
    const topY = slotY - pairGap;
    const bottomY = slotY + pairGap;

    nodes.push(
      placeAgentNode(topEntrant, { x: entrantX, y: topY }, { density: entrantDensity, eyebrow: "play-in" }),
      placeAgentNode(bottomEntrant, { x: entrantX, y: bottomY }, { density: entrantDensity, eyebrow: "play-in" }),
      placeFlowNode(playInId, { x: playInX ?? 438, y: slotY }, {
        kind: "match",
        label: "PLAY-IN",
        subtitle: `match ${matchIndex + 1}`,
        density: "compact",
      })
    );

    edges.push(
      {
        id: `agent:${topEntrant.role}->${playInId}`,
        source: `agent:${topEntrant.role}`,
        target: playInId,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "step",
        pathOptions: { offset: 24 },
      },
      {
        id: `agent:${bottomEntrant.role}->${playInId}`,
        source: `agent:${bottomEntrant.role}`,
        target: playInId,
        sourceHandle: "sr",
        targetHandle: "tl",
        type: "step",
        pathOptions: { offset: 24 },
      }
    );

    roundEntries.push({ id: playInId, y: slotY });
    playInIndex += 1;
  });

  let currentRoundEntries = roundEntries;
  for (let roundIndex = 0; roundIndex < structure.mainRoundLabels.length; roundIndex += 1) {
    const matchX = mainStartX + roundIndex * roundGap;
    const roundLabel = structure.mainRoundLabels[roundIndex] ?? tournamentRoundLabel(currentRoundEntries.length);
    const nextRound: BracketEntry[] = [];

    for (let entryIndex = 0; entryIndex < currentRoundEntries.length; entryIndex += 2) {
      const top = currentRoundEntries[entryIndex];
      const bottom = currentRoundEntries[entryIndex + 1];
      if (!top || !bottom) {
        continue;
      }

      const matchId = `match:${roundIndex}:${Math.floor(entryIndex / 2)}`;
      const matchY = Math.round((top.y + bottom.y) / 2);

      nodes.push(
        placeFlowNode(matchId, { x: matchX, y: matchY }, {
          kind: "match",
          label: roundLabel,
          subtitle: `match ${Math.floor(entryIndex / 2) + 1}`,
          density: "compact",
        })
      );

      edges.push(
        {
          id: `${top.id}->${matchId}`,
          source: top.id,
          target: matchId,
          sourceHandle: "sr",
          targetHandle: "tl",
          type: "step",
          pathOptions: { offset: 24 },
        },
        {
          id: `${bottom.id}->${matchId}`,
          source: bottom.id,
          target: matchId,
          sourceHandle: "sr",
          targetHandle: "tl",
          type: "step",
          pathOptions: { offset: 24 },
        }
      );

      nextRound.push({ id: matchId, y: matchY });
    }

    currentRoundEntries = nextRound;
  }

  const champion = currentRoundEntries[0];
  nodes.push(
    placeFlowNode("hub", { x: mainStartX + Math.max(0, structure.mainRoundLabels.length - 1) * roundGap + 220, y: champion?.y ?? Math.round(stageHeight / 2) }, {
      kind: "hub",
      label: copy.monitor.sharedContexts.tournament,
      subtitle: latestRoundLabel(session.events ?? []) ?? "winner",
      density: "compact",
    })
  );

  if (champion) {
    edges.push({
      id: `${champion.id}->hub`,
      source: champion.id,
      target: "hub",
      sourceHandle: "sr",
      targetHandle: "tl",
      type: "step",
      pathOptions: { offset: 24 },
    });
  }

  const bounds = graphBounds(nodes);
  const layoutWidth = bounds.right + 32;
  const zone = (label: string, leftPx: number, widthPx: number, top: string, height: string) => ({
    label,
    left: `${(leftPx / layoutWidth) * 100}%`,
    width: `${(widthPx / layoutWidth) * 100}%`,
    top,
    height,
  });

  return {
    nodes,
    edges,
    stageHeight,
    fitPadding: dense ? 0.025 : 0.03,
    maxZoom: dense ? 1.18 : 1.28,
    backdrop: {
      variant: "bracket",
      zones: [
        zone("ENTRANTS", 170, 160, "14%", "72%"),
        ...(playInX ? [zone("PLAY-IN", playInX - 74, 148, "18%", "64%")] : []),
        ...Array.from({ length: structure.mainRoundLabels.length }, (_, index) =>
          zone(structure.mainRoundLabels[index] ?? tournamentRoundLabel(Math.max(2, structure.slotCount / 2 ** index)), mainStartX + index * roundGap - 70, 140, "16%", "68%")
        ),
        zone("WINNER", bounds.right - 170, 160, "18%", "60%"),
      ],
    },
  };
}

function buildElkRoutePath(edge: ElkExtendedEdge, offsetX: number, offsetY: number) {
  const section = edge.sections?.[0];
  if (!section) {
    return undefined;
  }

  const points = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint];
  return `M ${Math.round(points[0].x + offsetX)} ${Math.round(points[0].y + offsetY)}${points
    .slice(1)
    .map((point) => ` L ${Math.round(point.x + offsetX)} ${Math.round(point.y + offsetY)}`)
    .join("")}`;
}

function groupBounds(nodes: FlowCanvasGraph["nodes"], predicate: (nodeId: string) => boolean) {
  const scoped = nodes.filter((node) => predicate(node.id));
  if (scoped.length === 0) {
    return null;
  }

  return {
    left: Math.min(...scoped.map((node) => node.position.x)),
    top: Math.min(...scoped.map((node) => node.position.y)),
    right: Math.max(...scoped.map((node) => node.position.x + node.data.dimensions.width)),
    bottom: Math.max(...scoped.map((node) => node.position.y + node.data.dimensions.height)),
  };
}

async function buildTournamentElkFlowGraph(session: Session, copy: LocaleCopy): Promise<FlowCanvasGraph> {
  const structure = buildTournamentStructure(session.agents);
  const entrants = structure.entrants;

  if (entrants.length <= 1) {
    return buildTournamentFallbackFlowGraph(session, copy);
  }

  const dense = entrants.length >= 6;
  const entrantDensity: TopologyFlowNodeData["density"] = dense ? "compact" : "default";
  const descriptors = new Map<string, TopologyFlowNodeData>();
  const children: ElkNode[] = [];
  const edges: Array<{ id: string; sources: string[]; targets: string[] }> = [];
  const roundOrder = new Map<string, number>();

  const registerNode = (nodeId: string, data: TopologyFlowNodeData) => {
    descriptors.set(nodeId, data);
    children.push({
      id: nodeId,
      width: data.dimensions.width,
      height: data.dimensions.height,
    });
  };

  structure.slots.forEach((slot, slotIndex) => {
    if (slot.kind === "direct") {
      const directNode = buildAgentFlowNode(slot.agent, 0, 0, {
        density: entrantDensity,
        eyebrow: structure.playInMatchCount > 0 ? "seeded" : undefined,
      });
      registerNode(directNode.id, directNode.data);
      roundOrder.set(directNode.id, slotIndex);
      return;
    }

    const [top, bottom] = slot.pair;
    const topNode = buildAgentFlowNode(top, 0, 0, { density: entrantDensity, eyebrow: "play-in" });
    const bottomNode = buildAgentFlowNode(bottom, 0, 0, { density: entrantDensity, eyebrow: "play-in" });
    const playInId = `playin:${slotIndex}`;
    const playInNode = flowNode(playInId, 0, 0, {
      kind: "match",
      label: "PLAY-IN",
      subtitle: `match ${slotIndex + 1}`,
      density: "compact",
    });

    registerNode(topNode.id, topNode.data);
    registerNode(bottomNode.id, bottomNode.data);
    registerNode(playInNode.id, playInNode.data);
    roundOrder.set(topNode.id, slotIndex * 2);
    roundOrder.set(bottomNode.id, slotIndex * 2 + 1);
    roundOrder.set(playInId, slotIndex);

    edges.push(
      { id: `${topNode.id}->${playInId}`, sources: [topNode.id], targets: [playInId] },
      { id: `${bottomNode.id}->${playInId}`, sources: [bottomNode.id], targets: [playInId] }
    );
  });

  type BracketEntry = { id: string; order: number };
  let currentRound: BracketEntry[] = structure.slots.map((slot, index) => ({
    id: slot.kind === "direct" ? `agent:${slot.agent.role}` : `playin:${slot.slotIndex}`,
    order: index,
  }));

  for (let roundIndex = 0; roundIndex < structure.mainRoundLabels.length; roundIndex += 1) {
    const nextRound: BracketEntry[] = [];
    for (let entryIndex = 0; entryIndex < currentRound.length; entryIndex += 2) {
      const top = currentRound[entryIndex];
      const bottom = currentRound[entryIndex + 1];
      if (!top || !bottom) {
        continue;
      }

      const matchId = `match:${roundIndex}:${Math.floor(entryIndex / 2)}`;
      const matchNode = flowNode(matchId, 0, 0, {
        kind: "match",
        label: structure.mainRoundLabels[roundIndex] ?? tournamentRoundLabel(currentRound.length),
        subtitle: `match ${Math.floor(entryIndex / 2) + 1}`,
        density: "compact",
      });

      registerNode(matchId, matchNode.data);
      roundOrder.set(matchId, top.order);
      edges.push(
        { id: `${top.id}->${matchId}`, sources: [top.id], targets: [matchId] },
        { id: `${bottom.id}->${matchId}`, sources: [bottom.id], targets: [matchId] }
      );
      nextRound.push({ id: matchId, order: top.order });
    }
    currentRound = nextRound;
  }

  const champion = currentRound[0];
  const hubNode = flowNode("hub", 0, 0, {
    kind: "hub",
    label: copy.monitor.sharedContexts.tournament,
    subtitle: latestRoundLabel(session.events ?? []) ?? "winner",
    density: "compact",
  });
  registerNode("hub", hubNode.data);
  roundOrder.set("hub", structure.slotCount + 1);

  if (champion) {
    edges.push({ id: `${champion.id}->hub`, sources: [champion.id], targets: ["hub"] });
  }

  const layout = await elk.layout({
    id: "tournament-root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "org.eclipse.elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "org.eclipse.elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "org.eclipse.elk.spacing.nodeNode": dense ? "18" : "22",
      "org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers": dense ? "38" : "46",
      "elk.padding": "[top=28,left=16,bottom=28,right=16]",
    },
    children,
    edges,
  });

  const laidOutChildren = layout.children ?? [];
  const minX = Math.min(...laidOutChildren.map((node) => node.x ?? 0));
  const minY = Math.min(...laidOutChildren.map((node) => node.y ?? 0));
  const maxY = Math.max(...laidOutChildren.map((node) => (node.y ?? 0) + (node.height ?? 0)));
  const bracketHeight = maxY - minY;
  const stageHeight = Math.max(496, Math.ceil(bracketHeight + 112));
  const offsetX = 286 - minX;
  const offsetY = Math.max(36, Math.round((stageHeight - bracketHeight) / 2 - minY));

  const nodes = [
    buildTaskFlowNode(session, copy, 164, 42, "tight"),
    ...laidOutChildren
      .sort((left, right) => (roundOrder.get(left.id) ?? 0) - (roundOrder.get(right.id) ?? 0))
      .map((node) =>
        flowNode(node.id, Math.round((node.x ?? 0) + offsetX), Math.round((node.y ?? 0) + offsetY), descriptors.get(node.id)!)
      ),
  ];

  const routedEdges: FlowEdge[] = ((layout.edges ?? []) as ElkExtendedEdge[]).map((edge) => ({
    id: edge.id,
    source: edge.sources?.[0] ?? "",
    target: edge.targets?.[0] ?? "",
    type: edge.sections?.length ? "topologyRouted" : "step",
    data: {
      routePath: buildElkRoutePath(edge, offsetX, offsetY),
    },
  }));

  const bounds = graphBounds(nodes);
  const layoutWidth = bounds.right + 32;
  const entrantBounds = groupBounds(nodes, (id) => id.startsWith("agent:"));
  const playInBounds = groupBounds(nodes, (id) => id.startsWith("playin:"));
  const winnerBounds = groupBounds(nodes, (id) => id === "hub");
  const roundZones = structure.mainRoundLabels
    .map((label, index) => {
      const roundBounds = groupBounds(nodes, (id) => id.startsWith(`match:${index}:`));
      return roundBounds ? zoneFromBounds(label, roundBounds, layoutWidth, stageHeight) : null;
    })
    .filter((zone): zone is NonNullable<typeof zone> => Boolean(zone));

  return {
    nodes,
    edges: routedEdges,
    stageHeight,
    fitPadding: dense ? 0.02 : 0.028,
    maxZoom: dense ? 1.16 : 1.24,
    backdrop: {
      variant: "bracket",
      zones: [
        ...(entrantBounds ? [zoneFromBounds("ENTRANTS", entrantBounds, layoutWidth, stageHeight)] : []),
        ...(playInBounds ? [zoneFromBounds("PLAY-IN", playInBounds, layoutWidth, stageHeight)] : []),
        ...roundZones,
        ...(winnerBounds ? [zoneFromBounds("WINNER", winnerBounds, layoutWidth, stageHeight)] : []),
      ],
    },
  };
}

function buildStaticFlowGraph(session: Session, copy: LocaleCopy) {
  if (session.mode === "debate" || session.mode === "tournament_match") {
    return buildDebateFlowGraph(session, copy);
  }

  if (session.mode === "board") {
    return buildBoardFlowGraph(session, copy);
  }

  if (session.mode === "democracy") {
    return buildDemocracyFlowGraph(session, copy);
  }

  if (session.mode === "creator_critic") {
    return buildCreatorCriticFlowGraph(session, copy);
  }

  if (session.mode === "dictator") {
    return buildDictatorFlowGraph(session, copy);
  }

  if (session.mode === "map_reduce") {
    return buildMapReduceFlowGraph(session, copy);
  }

  if (session.mode === "tournament") {
    return buildTournamentFallbackFlowGraph(session, copy);
  }

  return buildDefaultFlowGraph(session, copy);
}

export function useTopologyFlowGraph(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const layoutKey = `${session.id}:${session.mode}:${session.task}:${session.agents.map((agent) => `${agent.role}:${agent.provider}`).join("|")}:${latestRoundLabel(session.events ?? []) ?? ""}`;
  const tournamentLayoutKey = `${layoutKey}:${copy.monitor.vsLabel}:${copy.monitor.noMatchYet}`;
  const [tournamentGraph, setTournamentGraph] = useState<{ key: string; graph: FlowCanvasGraph } | null>(null);
  const latestSessionRef = useRef(session);
  const latestCopyRef = useRef(copy);
  const fallbackGraph = session.mode === "tournament" ? buildTournamentFallbackFlowGraph(session, copy) : buildStaticFlowGraph(session, copy);

  useEffect(() => {
    latestSessionRef.current = session;
    latestCopyRef.current = copy;
  }, [copy, session]);

  useEffect(() => {
    let cancelled = false;

    if (session.mode !== "tournament") {
      return () => {
        cancelled = true;
      };
    }

    const latestSession = latestSessionRef.current;
    const latestCopy = latestCopyRef.current;

    void buildTournamentElkFlowGraph(latestSession, latestCopy)
      .then((graph) => {
        if (!cancelled) {
          setTournamentGraph((current) => {
            if (current?.key === tournamentLayoutKey) {
              return current;
            }
            return { key: tournamentLayoutKey, graph };
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTournamentGraph((current) =>
            current?.key === tournamentLayoutKey
              ? current
              : { key: tournamentLayoutKey, graph: buildTournamentFallbackFlowGraph(latestSession, latestCopy) }
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [session.mode, tournamentLayoutKey]);

  if (session.mode === "tournament" && tournamentGraph?.key === tournamentLayoutKey) {
    return tournamentGraph.graph;
  }

  return fallbackGraph;
}
