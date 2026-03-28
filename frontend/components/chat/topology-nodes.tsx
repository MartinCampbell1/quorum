import {
  BaseEdge,
  Handle,
  Position,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";

import {
  providerAccent,
  providerMark,
  type FlowEdge,
  type TopologyFlowNodeData,
} from "./topology-model";

function FlowHandles() {
  const handleClass = "!h-2 !w-2 !border-0 !bg-transparent opacity-0 pointer-events-none";

  return (
    <>
      <Handle id="tl" type="target" position={Position.Left} className={handleClass} />
      <Handle id="tr" type="target" position={Position.Right} className={handleClass} />
      <Handle id="tt" type="target" position={Position.Top} className={handleClass} />
      <Handle id="tb" type="target" position={Position.Bottom} className={handleClass} />
      <Handle id="sl" type="source" position={Position.Left} className={handleClass} />
      <Handle id="sr" type="source" position={Position.Right} className={handleClass} />
      <Handle id="st" type="source" position={Position.Top} className={handleClass} />
      <Handle id="sb" type="source" position={Position.Bottom} className={handleClass} />
    </>
  );
}

export function TopologyFlowNode({ data }: NodeProps<Node<TopologyFlowNodeData>>) {
  const density = data.density ?? "default";
  const { width, height } = data.dimensions;

  if (data.kind === "task") {
    return (
      <div
        className={cn(
          "border border-slate-200/90 bg-white/94 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.38)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/84",
          density === "tight" ? "rounded-[16px] px-3 py-2" : density === "compact" ? "rounded-[18px] px-3.5 py-2.5" : "rounded-[22px] px-4 py-3"
        )}
        style={{ width, minHeight: height }}
      >
        <FlowHandles />
        <div className="flex h-full items-center gap-3">
          <div
            className={cn(
              "flex items-center justify-center rounded-[14px] border border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
              density === "tight" ? "h-8 w-8" : density === "compact" ? "h-9 w-9" : "h-10 w-10"
            )}
          >
            <ArrowRight className={density === "tight" ? "h-3.5 w-3.5" : "h-4 w-4"} />
          </div>
          <div className="min-w-0">
            <div className={cn("font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400", density === "tight" ? "text-[10px]" : "text-[11px]")}>
              {data.eyebrow ?? data.label}
            </div>
            <div className={cn("truncate font-medium tracking-[-0.02em] text-slate-900 dark:text-slate-100", density === "tight" ? "text-[12px]" : density === "compact" ? "text-[12px]" : "text-[13px]")}>
              {data.subtitle ?? data.label}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (data.kind === "match") {
    const ghost = data.variant === "ghost";
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-[18px] border px-3 py-2 text-center shadow-[0_12px_28px_-22px_rgba(30,41,59,0.35)] backdrop-blur",
          ghost
            ? "border-dashed border-slate-300/90 bg-white/70 dark:border-slate-700 dark:bg-slate-950/55"
            : "border-slate-200 bg-slate-50/92 dark:border-slate-700 dark:bg-slate-900/90"
        )}
        style={{ width, minHeight: height }}
      >
        <FlowHandles />
        <div className="w-full">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            {data.label}
          </div>
          {data.subtitle ? (
            <div className="mt-1 text-[11px] font-medium text-slate-700 dark:text-slate-200">
              {data.subtitle}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  if (data.kind === "hub") {
    return (
      <div
        className={cn(
          "flex items-center justify-center border shadow-[0_24px_56px_-36px_rgba(15,23,42,0.54)] backdrop-blur",
          data.variant === "chamber"
            ? "rounded-[999px] border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,255,0.95))] px-5 py-5 dark:border-slate-700 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.95),rgba(2,6,23,0.94))]"
            : density === "compact"
              ? "rounded-[24px] border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-3.5 dark:border-slate-700 dark:from-slate-900 dark:to-slate-950"
              : "rounded-[28px] border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100 px-5 py-4 dark:border-slate-700 dark:from-slate-900 dark:to-slate-950"
        )}
        style={{ width, minHeight: height }}
      >
        <FlowHandles />
        <div className="w-full text-center">
          <div className={cn("font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400", density === "compact" ? "text-[10px]" : "text-[11px]")}>
            {data.eyebrow ?? data.subtitle ?? "orchestrator"}
          </div>
          <div className={cn("font-semibold tracking-[-0.035em] text-slate-900 dark:text-slate-100", density === "compact" ? "mt-1.5 text-[16px]" : "mt-2 text-[19px]")}>
            {data.label}
          </div>
          {data.subtitle && data.eyebrow ? (
            <div className="mt-1.5 text-[12px] text-slate-500 dark:text-slate-400">
              {data.subtitle}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  const ghost = data.variant === "ghost";

  return (
    <div
      className={cn(
        "border bg-white/95 shadow-[0_18px_34px_-26px_rgba(15,23,42,0.4)] backdrop-blur dark:bg-slate-950/88",
        density === "tight" ? "rounded-[17px] px-2.5 py-2" : density === "compact" ? "rounded-[20px] px-3 py-2.5" : "rounded-[24px] px-3.5 py-3",
        ghost
          ? "border-dashed border-slate-300/90 bg-white/72 opacity-88 dark:border-slate-700 dark:bg-slate-950/60"
          : data.active
            ? "border-[var(--node-accent)] ring-1 ring-[var(--node-accent)]/30"
            : "border-slate-200 dark:border-slate-800"
      )}
      style={{
        width,
        minHeight: height,
        ["--node-accent" as string]: providerAccent(data.provider ?? ""),
      }}
    >
      <FlowHandles />
      <div className="flex h-full items-center gap-3">
        <div
          className={cn(
            "flex shrink-0 items-center justify-center rounded-[14px] border font-semibold tracking-[-0.04em]",
            density === "tight" ? "h-8 w-8 text-[13px]" : density === "compact" ? "h-9 w-9 text-[15px]" : "h-11 w-11 text-[18px]",
            ghost
              ? "border-slate-200 bg-slate-50 text-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-500"
              : data.active
                ? "border-[var(--node-accent)] bg-[color-mix(in_oklab,var(--node-accent)_12%,white)] text-slate-900"
                : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
          )}
          style={{ ["--node-accent" as string]: providerAccent(data.provider ?? "") }}
        >
          {ghost ? "•" : providerMark(data.provider ?? "")}
        </div>
        <div className="min-w-0">
          {data.eyebrow ? (
            <div className="truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              {data.eyebrow}
            </div>
          ) : null}
          <div className={cn("truncate font-semibold tracking-[-0.03em] text-slate-900 dark:text-slate-100", density === "tight" ? "text-[12px]" : density === "compact" ? "text-[13px]" : "text-[15px]")}>
            {data.label}
          </div>
          {data.subtitle ? (
            <div className={cn("truncate text-slate-500 dark:text-slate-400", density === "tight" ? "text-[10px]" : density === "compact" ? "text-[11px]" : "text-[12px]")}>
              {data.subtitle}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function polylineFallbackPath(sourceX: number, sourceY: number, targetX: number, targetY: number) {
  return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
}

export function TopologyRoutedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  style,
  markerStart,
  markerEnd,
  label,
  labelStyle,
  labelShowBg,
  labelBgStyle,
  labelBgPadding,
  labelBgBorderRadius,
  interactionWidth,
}: EdgeProps<FlowEdge>) {
  return (
    <BaseEdge
      id={id}
      path={data?.routePath ?? polylineFallbackPath(sourceX, sourceY, targetX, targetY)}
      style={style}
      markerStart={markerStart}
      markerEnd={markerEnd}
      label={label}
      labelStyle={labelStyle}
      labelShowBg={labelShowBg}
      labelBgStyle={labelBgStyle}
      labelBgPadding={labelBgPadding}
      labelBgBorderRadius={labelBgBorderRadius}
      interactionWidth={interactionWidth}
    />
  );
}

export const flowNodeTypes = {
  topology: TopologyFlowNode,
};

export const flowEdgeTypes = {
  topologyRouted: TopologyRoutedEdge,
};
