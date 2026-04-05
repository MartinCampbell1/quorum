"""Lightweight discovery -> Autopilot handoff bridge helpers."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from fastapi import HTTPException

from orchestrator.brief_v2_adapter import shared_brief_to_v2
from orchestrator.execution_brief import DEFAULT_AUTOPILOT_API_BASE, SendExecutionBriefRequest
from orchestrator.shared_contracts import ExecutionBrief as SharedExecutionBrief
from orchestrator.shared_contracts import from_jsonable, to_jsonable


BriefKind = Literal["internal", "shared"]


def _brief_payload(brief: object) -> dict[str, Any]:
    if hasattr(brief, "model_dump"):
        payload = brief.model_dump()
    else:
        payload = to_jsonable(brief)
    if not isinstance(payload, dict):
        raise HTTPException(500, "Execution brief payload is malformed.")
    return payload


def _infer_brief_kind(payload: dict[str, Any]) -> BriefKind:
    """Detect whether a brief payload is shared cross-plane or internal."""

    shared_markers = {"brief_id", "idea_id", "prd_summary"}
    internal_markers = {"title", "thesis", "version"}
    if shared_markers.issubset(payload.keys()):
        return "shared"
    if internal_markers.issubset(payload.keys()):
        return "internal"
    raise ValueError(
        f"Unknown execution brief contract. "
        f"Expected shared markers {shared_markers} or internal markers {internal_markers}, "
        f"got keys: {sorted(payload.keys())}"
    )


def _resolve_shared_brief_candidate(
    discovery_store: Any,
    *,
    idea_id: str,
    brief_id: str,
) -> Any | None:
    if discovery_store is None:
        return None
    dossier = discovery_store.get_dossier(idea_id)
    if dossier is None:
        return None
    candidate = getattr(dossier, "execution_brief_candidate", None)
    if candidate is None:
        return None
    if str(getattr(candidate, "brief_id", "") or "").strip() != brief_id:
        return None
    return candidate


async def _send_brief_to_autopilot(
    brief: object,
    request: SendExecutionBriefRequest,
    *,
    discovery_store: Any = None,
) -> dict[str, Any]:
    brief_dict = _brief_payload(brief)
    kind = _infer_brief_kind(brief_dict)
    base = str(request.autopilot_url or DEFAULT_AUTOPILOT_API_BASE).rstrip("/")

    if kind == "shared":
        shared_brief = from_jsonable(SharedExecutionBrief, brief_dict)
        candidate = _resolve_shared_brief_candidate(
            discovery_store,
            idea_id=shared_brief.idea_id,
            brief_id=shared_brief.brief_id,
        )
        founder_approval_required = bool(
            getattr(candidate, "founder_approval_required", True)
        )
        approval_status = str(
            getattr(candidate, "brief_approval_status", "pending") or "pending"
        ).strip() or "pending"
        if request.launch and founder_approval_required and approval_status != "approved":
            raise HTTPException(
                409,
                "Brief must be approved by founder before launch. "
                f"Current status: {approval_status}",
            )

        v2 = shared_brief_to_v2(
            shared_brief,
            initiative_id=shared_brief.idea_id,
            revision_id=getattr(candidate, "revision_id", None),
            option_id=None,
            decision_id=None,
            founder_approval_required=founder_approval_required,
            brief_approval_status=approval_status,
            approved_at=getattr(candidate, "approved_at", None),
            approved_by=getattr(candidate, "approved_by", None),
        )

        payload = {
            "brief": v2.model_dump(mode="json"),
            "project_name": request.project_name,
            "project_path": request.project_path,
            "priority": request.priority,
            "launch": request.launch,
            "launch_profile": request.launch_profile.model_dump() if request.launch_profile else None,
        }
        url = f"{base}/projects/from-brief-v2"
    else:
        payload = {
            "brief": brief_dict,
            "project_name": request.project_name,
            "project_path": request.project_path,
            "priority": request.priority,
            "launch": request.launch,
            "launch_profile": request.launch_profile.model_dump() if request.launch_profile else None,
        }
        url = f"{base}/execution-plane/projects/from-brief"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to reach Autopilot bridge: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        if response.status_code in {400, 409, 422, 503}:
            raise HTTPException(response.status_code, detail)
        raise HTTPException(502, f"Autopilot rejected execution brief: {detail}")
    return data
