"""Lightweight request/response models for Autopilot handoff surfaces."""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_AUTOPILOT_API_BASE = "http://127.0.0.1:8420/api"


class ExecutionBriefExportRequest(BaseModel):
    provider: str | None = None


class AutopilotLaunchProfile(BaseModel):
    preset: str = "fast"
    story_execution_mode: str | None = None
    project_concurrency_mode: str | None = None
    max_parallel_stories: int | None = None


class AutopilotLaunchPreset(BaseModel):
    id: str
    label: str
    description: str = ""
    launch_profile: AutopilotLaunchProfile


class SendExecutionBriefRequest(ExecutionBriefExportRequest):
    autopilot_url: str = DEFAULT_AUTOPILOT_API_BASE
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: AutopilotLaunchProfile | None = None
