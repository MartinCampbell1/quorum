"""Replay payloads for session-level debate and generation traces."""

from __future__ import annotations

from orchestrator.discovery_models import (
    DebateReplaySession,
    DebateReplayStep,
    ReplayParticipant,
)
from orchestrator.models import SessionStore


def _clip(value: str, limit: int = 200) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


class DebateReplayService:
    def __init__(self, session_store: SessionStore):
        self._session_store = session_store

    def build_replay(self, session_id: str) -> DebateReplaySession | None:
        session = self._session_store.get(session_id)
        if session is None:
            return None

        timeline: list[DebateReplayStep] = []
        for event in session.get("events") or []:
            timeline.append(
                DebateReplayStep(
                    timestamp=float(event.get("timestamp") or 0.0),
                    kind="session_event",
                    title=str(event.get("title") or event.get("type") or "Event"),
                    detail=_clip(str(event.get("detail") or "")),
                    agent_id=str(event.get("agent_id") or "") or None,
                    checkpoint_id=str(event.get("checkpoint_id") or "") or None,
                    status=str(event.get("status") or "") or None,
                    metadata={key: value for key, value in event.items() if key not in {"title", "detail"}},
                )
            )
        for checkpoint in session.get("checkpoints") or []:
            timeline.append(
                DebateReplayStep(
                    timestamp=float(checkpoint.get("timestamp") or 0.0),
                    kind="checkpoint",
                    title=f"Checkpoint {checkpoint.get('id')}",
                    detail=_clip(str(checkpoint.get("result_preview") or checkpoint.get("status") or "")),
                    checkpoint_id=str(checkpoint.get("id") or "") or None,
                    node_id=str(checkpoint.get("next_node") or "") or None,
                    status=str(checkpoint.get("status") or "") or None,
                    metadata={"graph_checkpoint_id": checkpoint.get("graph_checkpoint_id")},
                )
            )
        for item in session.get("protocol_trace") or []:
            timeline.append(
                DebateReplayStep(
                    timestamp=float(item.get("timestamp") or 0.0),
                    kind="protocol_transition",
                    title=f"{item.get('from_node_id')} -> {item.get('to_node_id')}",
                    detail=_clip("; ".join([*(item.get("warnings") or []), *(item.get("errors") or [])]) or "Transition validated"),
                    checkpoint_id=str(item.get("checkpoint_id") or "") or None,
                    node_id=str(item.get("to_node_id") or "") or None,
                    status="ok" if item.get("ok") else "invalid",
                    metadata={"guard_id": item.get("guard_id"), "state_excerpt": item.get("state_excerpt")},
                )
            )

        generation_trace = dict((session.get("config") or {}).get("generation_trace") or {})
        artifacts = list(generation_trace.get("trace_artifacts") or [])
        if generation_trace.get("final_artifact"):
            artifacts.append(generation_trace["final_artifact"])
        for artifact in artifacts:
            timeline.append(
                DebateReplayStep(
                    timestamp=float(artifact.get("generated_at") or session.get("created_at") or 0.0),
                    kind="generation_artifact",
                    title=f"{artifact.get('layer', 'layer')} · {artifact.get('agent_role', 'agent')}",
                    detail=_clip(str(artifact.get("summary") or artifact.get("content") or "")),
                    agent_id=str(artifact.get("agent_role") or "") or None,
                    metadata={
                        "provider": artifact.get("provider"),
                        "candidate_id": artifact.get("candidate_id"),
                    },
                )
            )

        timeline.sort(key=lambda item: (item.timestamp, item.title))
        topology_state = dict((session.get("config") or {}).get("topology_state") or {})
        shadow = dict(session.get("protocol_shadow_validation") or {})
        return DebateReplaySession(
            session_id=str(session.get("id") or session_id),
            mode=str(session.get("mode") or ""),
            task=str(session.get("task") or ""),
            status=str(session.get("status") or ""),
            created_at=float(session.get("created_at") or 0.0),
            elapsed_sec=session.get("elapsed_sec"),
            result=session.get("result"),
            selected_template=str(topology_state.get("selected_template") or "") or None,
            execution_mode=str((session.get("config") or {}).get("execution_mode") or "") or None,
            participants=[
                ReplayParticipant(
                    role=str(agent.get("role") or "agent"),
                    provider=str(agent.get("provider") or "unknown"),
                    tools=list(agent.get("tools") or []),
                )
                for agent in session.get("agents") or []
            ],
            event_count=len(session.get("events") or []),
            checkpoint_count=len(session.get("checkpoints") or []),
            invalid_transition_count=int(shadow.get("invalid_transitions") or 0),
            generation_artifact_count=len(artifacts),
            timeline=timeline,
            protocol_trace=list(session.get("protocol_trace") or []),
        )

