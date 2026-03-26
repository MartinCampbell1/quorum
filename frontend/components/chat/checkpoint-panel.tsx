"use client";

import { useMemo, useState } from "react";
import { GitBranch, Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { controlSession } from "@/lib/api";
import type { Session } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CheckpointPanelProps {
  session: Session;
  selectedCheckpointId?: string | null;
  onSelectCheckpoint: (checkpointId: string) => void;
  onForkSession?: (sessionId: string) => void;
  onRefresh?: () => void;
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function CheckpointPanel({
  session,
  selectedCheckpointId,
  onSelectCheckpoint,
  onForkSession,
  onRefresh,
}: CheckpointPanelProps) {
  const [branchingCheckpointId, setBranchingCheckpointId] = useState<string | null>(null);

  const checkpoints = useMemo(
    () => [...(session.checkpoints ?? [])].sort((a, b) => b.timestamp - a.timestamp),
    [session.checkpoints]
  );

  async function branchFromCheckpoint(checkpointId: string) {
    setBranchingCheckpointId(checkpointId);
    try {
      const result = await controlSession(
        session.id,
        "restart_from_checkpoint",
        undefined,
        checkpointId
      );
      await onRefresh?.();
      if (result.new_session_id) {
        onForkSession?.(result.new_session_id);
      }
    } finally {
      setBranchingCheckpointId(null);
    }
  }

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)]">
      <div className="flex items-center justify-between">
        <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111]">
          Checkpoints & Branches
        </h2>
        {session.forked_from ? (
          <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
            branch
          </span>
        ) : null}
      </div>

      <div className="mt-4 space-y-3">
        {session.forked_from ? (
          <div className="rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-3 py-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Parent session</div>
            <div className="mt-1 font-mono text-[12px] text-[#111111]">{session.forked_from}</div>
            {session.forked_checkpoint_id ? (
              <div className="mt-1 text-[11px] text-[#6b7280]">
                from checkpoint {session.forked_checkpoint_id}
              </div>
            ) : null}
          </div>
        ) : null}

        {session.branch_children && session.branch_children.length > 0 ? (
          <div className="rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-3 py-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Child branches</div>
            <div className="mt-2 space-y-1.5">
              {session.branch_children.map((child) => (
                <div key={child.id} className="flex items-center justify-between text-[11px] text-[#111111]">
                  <span className="font-mono">{child.id}</span>
                  <span className="text-[#6b7280]">{child.forked_checkpoint_id ?? "checkpoint"}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="space-y-2">
          {checkpoints.map((checkpoint) => {
            const isSelected = selectedCheckpointId === checkpoint.id;
            const isCurrent = session.current_checkpoint_id === checkpoint.id;
            const isBranching = branchingCheckpointId === checkpoint.id;
            return (
              <div
                key={checkpoint.id}
                className={cn(
                  "rounded-[14px] border px-3 py-3 transition-colors",
                  isSelected ? "border-[#111111] bg-white" : "border-[#d6dbe6] bg-white"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => onSelectCheckpoint(checkpoint.id)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[12px] text-[#111111]">{checkpoint.id}</span>
                      {isCurrent ? (
                        <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
                          current
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1 text-[11px] text-[#6b7280]">
                      {formatTimestamp(checkpoint.timestamp)} · {checkpoint.next_node ?? "terminal"}
                    </div>
                    {checkpoint.result_preview ? (
                      <div className="mt-2 text-[12px] leading-5 text-[#111111]/80">
                        {checkpoint.result_preview}
                      </div>
                    ) : null}
                  </button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="rounded-[10px] border-[#d6dbe6] bg-white text-[11px]"
                    onClick={() => branchFromCheckpoint(checkpoint.id)}
                    disabled={isBranching || ["running", "pause_requested", "cancel_requested"].includes(session.status)}
                  >
                    {isBranching ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <GitBranch className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    Fork
                  </Button>
                </div>
              </div>
            );
          })}

          {checkpoints.length === 0 ? (
            <div className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-4 text-[12px] text-[#6b7280]">
              Checkpoints появятся после первых graph transitions.
            </div>
          ) : null}
        </div>

        {selectedCheckpointId && selectedCheckpointId !== session.current_checkpoint_id ? (
          <div className="flex items-center gap-2 rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-3 py-3 text-[12px] text-[#6b7280]">
            <RotateCcw className="h-4 w-4" />
            Выбран исторический checkpoint {selectedCheckpointId}. Resume всегда идёт с текущего checkpoint, branch — с выбранного.
          </div>
        ) : null}
      </div>
    </section>
  );
}
