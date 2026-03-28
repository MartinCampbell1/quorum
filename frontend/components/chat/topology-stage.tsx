import { useEffect, useState } from "react";

import {
  Background,
  BackgroundVariant,
  MarkerType,
  ReactFlow,
  type Node,
} from "@xyflow/react";

import { cn } from "@/lib/utils";

import { flowEdgeTypes, flowNodeTypes } from "./topology-nodes";
import type { FlowCanvasGraph, FlowEdge, TopologyFlowNodeData } from "./topology-model";

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

function StageBackdrop({ backdrop }: { backdrop?: FlowCanvasGraph["backdrop"] }) {
  if (!backdrop || backdrop.variant === "default") {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0">
      {backdrop.variant === "loop" ? (
        <>
          <div className="absolute left-[15%] top-[10%] h-[72%] w-[70%] rounded-[140px] border border-dashed border-slate-300/80 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.08),rgba(255,255,255,0))] dark:border-slate-700/80 dark:bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.16),rgba(2,6,23,0))]" />
          <div className="absolute left-[30%] top-[14%] h-[19%] w-[40%] rounded-[40px] bg-white/45 blur-xl dark:bg-slate-900/35" />
        </>
      ) : null}

      {backdrop.variant === "chamber" ? (
        <>
          <div className="absolute left-1/2 top-[14%] h-[62%] w-[70%] -translate-x-1/2 rounded-[999px] border border-slate-200/80 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.92),rgba(233,239,252,0.75),rgba(255,255,255,0))] dark:border-slate-800 dark:bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.16),rgba(15,23,42,0.2),rgba(2,6,23,0))]" />
          <div className="absolute left-1/2 top-[42%] h-[30%] w-[80%] -translate-x-1/2 rounded-[999px] border border-slate-200/70 bg-white/35 dark:border-slate-800 dark:bg-slate-900/20" />
        </>
      ) : null}

      {(backdrop.variant === "pipeline" || backdrop.variant === "bracket") && backdrop.zones?.length
        ? backdrop.zones.map((zone) => (
            <div
              key={`${zone.label}-${zone.left}`}
              className={cn(
                "absolute rounded-[28px] border border-slate-200/75 bg-white/52 backdrop-blur-sm dark:border-slate-800 dark:bg-slate-950/22",
                backdrop.variant === "bracket" ? "rounded-[32px]" : ""
              )}
              style={{
                left: zone.left,
                width: zone.width,
                top: zone.top ?? "14%",
                height: zone.height ?? "70%",
              }}
            >
              <div className="px-4 pt-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                {zone.label}
              </div>
            </div>
          ))
        : null}
    </div>
  );
}

export function TopologyFlowStage({
  graph,
  viewKey,
  activeAgentId,
  activeEdgeIds,
}: {
  graph: FlowCanvasGraph;
  viewKey: string;
  activeAgentId?: string;
  activeEdgeIds: Set<string>;
}) {
  const reduceMotion = useReducedMotion();
  const fitPadding = graph.fitPadding ?? 0.05;
  const maxZoom = graph.maxZoom ?? 1.7;
  const stageHeight = graph.stageHeight ?? 380;
  const themedNodes = graph.nodes.map((node) => {
    if (node.data.kind !== "agent") {
      return node;
    }

    return {
      ...node,
      data: {
        ...node.data,
        active: node.id === `agent:${activeAgentId}`,
      },
    };
  });

  const themedEdges = graph.edges.map((edge) => {
    const active = activeEdgeIds.has(edge.id);

    return {
      ...edge,
      animated: active && !reduceMotion,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: active ? "#4f46e5" : "#94a3b8",
      },
      style: {
        ...(edge.style ?? {}),
        stroke: active ? "#4f46e5" : (typeof edge.style?.stroke === "string" ? edge.style.stroke : "#94a3b8"),
        strokeWidth: active ? 2.6 : (typeof edge.style?.strokeWidth === "number" ? edge.style.strokeWidth : 1.8),
      },
    };
  });

  return (
    <div
      className="relative bg-[radial-gradient(circle_at_top,rgba(226,231,247,0.58),rgba(255,255,255,0))] dark:bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.16),rgba(2,6,23,0))]"
      style={{ height: stageHeight }}
    >
      <StageBackdrop backdrop={graph.backdrop} />
      {/* Keep stage read-only, but allow zoom to recover from fitView misses without exposing node editing. */}
      <ReactFlow<Node<TopologyFlowNodeData>, FlowEdge>
        key={viewKey}
        nodes={themedNodes}
        edges={themedEdges}
        nodeTypes={flowNodeTypes}
        edgeTypes={flowEdgeTypes}
        fitView
        fitViewOptions={{ padding: fitPadding, duration: reduceMotion ? 0 : 320 }}
        minZoom={0.58}
        maxZoom={maxZoom}
        zoomOnScroll
        zoomOnPinch
        zoomOnDoubleClick={false}
        panOnDrag={false}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        edgesFocusable={false}
        nodesFocusable={false}
        onlyRenderVisibleElements
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
        className="!bg-transparent"
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="rgba(148,163,184,0.22)" />
      </ReactFlow>
    </div>
  );
}
