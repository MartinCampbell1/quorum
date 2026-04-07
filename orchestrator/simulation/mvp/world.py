"""World configuration for cheap, bounded focus-group simulations."""

from __future__ import annotations

from pydantic import BaseModel, Field

from orchestrator.discovery_models import IdeaDossier, SimulationRunRequest


class SimulationWorld(BaseModel):
    world_id: str = Field(default="world_focus_group")
    name: str
    research_goal: str
    discussion_prompts: list[str] = Field(default_factory=list)
    decision_lens: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    timebox_minutes: int = 45


def build_focus_group_world(dossier: IdeaDossier, request: SimulationRunRequest) -> SimulationWorld:
    idea = dossier.idea
    evidence_highlights = [item.summary for item in (dossier.evidence_bundle.items if dossier.evidence_bundle else [])[:3]]
    evidence_highlights.extend(observation.raw_text[:140] for observation in dossier.observations[:2])
    evidence_highlights.extend(report.summary[:140] for report in dossier.validation_reports[:2])

    prompts = [
        f"What problem does '{idea.title}' solve for you immediately, if any?",
        f"What would block a real trial of '{idea.title}' in the next 30 days?",
        f"What evidence or capability would make you recommend or buy '{idea.title}'?",
        f"If the product shipped this quarter, how would it need to fit your workflow to stay?",
    ]

    return SimulationWorld(
        name=f"{idea.title} focus group",
        research_goal=f"Synthetic validation of whether {idea.title} creates believable early pull before build-out.",
        discussion_prompts=prompts[: request.max_rounds],
        decision_lens=[
            "pain intensity",
            "switching friction",
            "proof required",
            "budget willingness",
            "retention hook",
        ],
        evidence_highlights=evidence_highlights[:6],
        timebox_minutes=request.max_rounds * 15,
    )
