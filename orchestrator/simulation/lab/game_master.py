"""Bounded Game Master for market-sandbox simulations."""

from __future__ import annotations

import random
from collections import Counter

from orchestrator.discovery_models import (
    AgentAction,
    AgentActivityConfig,
    LabAgentState,
    RoundSummary,
    SimulationParameters,
    SimulationRunState,
)
from orchestrator.simulation.lab.world_builder import MarketWorldConfig
from orchestrator.simulation.mvp.personas import stable_seed


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _stage_order(stage: str) -> int:
    order = {
        "unaware": 0,
        "aware": 1,
        "considering": 2,
        "trial": 3,
        "adopted": 4,
        "retained": 5,
        "churned": 2,
    }
    return order.get(stage, 0)


class MarketGameMaster:
    """Runs deterministic market rounds with bounded state transitions."""

    def __init__(
        self,
        parameters: SimulationParameters,
        activity_config: AgentActivityConfig,
        world: MarketWorldConfig,
        agents: list[LabAgentState],
    ):
        self.parameters = parameters
        self.activity_config = activity_config
        self.world = world
        self.agents = agents

    def _fit_score(self, agent: LabAgentState) -> float:
        return _clamp(
            0.26
            + (agent.need_intensity * 0.22)
            + (self.world.evidence_strength * self.parameters.evidence_weight * 0.26)
            + (self.world.social_proof * 0.12)
            + (agent.budget_fit * 0.1)
            - (agent.skepticism * 0.14)
            - (agent.price_sensitivity * 0.12)
            - (self.world.competition_pressure * 0.18)
        )

    def _maybe_advance(self, stage: str, fit_score: float, influence: float) -> tuple[str, str]:
        combined = _clamp(fit_score + influence)
        if stage == "unaware":
            if combined >= 0.3:
                return "aware", "noticed the idea via market exposure"
            return stage, "ignored the signal"
        if stage == "aware":
            if combined >= 0.42:
                return "considering", "started evaluating the wedge"
            return stage, "remained only weakly aware"
        if stage == "considering":
            if combined >= 0.58:
                return "trial", "started a constrained trial"
            return stage, "wanted more proof before trial"
        if stage == "trial":
            if combined >= 0.66:
                return "adopted", "moved from trial to adoption"
            if combined < 0.38:
                return "churned", "trial failed to justify the switch"
            return stage, "kept the trial alive but unresolved"
        if stage == "adopted":
            if combined >= 0.7:
                return "retained", "continued because pain relief felt real"
            if combined < 0.44:
                return "churned", "adoption decayed under workflow friction"
            return stage, "adopted but still vulnerable to churn"
        if stage == "retained":
            return stage, "remained an active retained user"
        if stage == "churned":
            if combined >= 0.67:
                return "considering", "re-entered consideration after new proof"
            return stage, "stayed churned"
        return stage, "held the current state"

    def run(self) -> SimulationRunState:
        state = SimulationRunState(status="running", world_state=dict(self.world.world_state))
        for round_index in range(1, self.parameters.round_count + 1):
            state.current_round = round_index
            actions: list[AgentAction] = []
            objections = Counter()
            channel_delta = Counter()
            retained = 0
            adopted = 0
            aware = 0
            considering = 0
            trials = 0
            virality_total = 0.0
            pain_relief_total = 0.0

            for agent in self.agents:
                rng = random.Random(stable_seed(state.run_id, agent.agent_id, round_index))
                channel_strength = self.world.channel_strength.get(agent.preferred_channel, 0.42)
                influence = _clamp(
                    (channel_strength * 0.12)
                    + (self.world.network_density * agent.network_reach * 0.14)
                    + (self.world.social_proof * 0.1)
                    + (rng.random() * 0.08)
                )
                fit_score = self._fit_score(agent)
                before = agent.adoption_stage
                after, summary = self._maybe_advance(before, fit_score, influence)
                pain_relief_delta = _clamp((fit_score * 0.64) - (agent.skepticism * 0.14))
                if after in {"adopted", "retained"}:
                    virality_total += agent.referral_propensity * self.activity_config.referral_rate
                    pain_relief_total += pain_relief_delta
                if after in {"aware", "considering", "trial", "adopted", "retained"}:
                    aware += 1
                if after in {"considering", "trial", "adopted", "retained"}:
                    considering += 1
                if after == "trial":
                    trials += 1
                if after in {"adopted", "retained"}:
                    adopted += 1
                if after == "retained":
                    retained += 1
                if after == before or _stage_order(after) <= _stage_order(before):
                    objections.update(agent.objections[:1] or ["unclear ROI"])
                channel_delta[agent.preferred_channel] += influence

                agent.adoption_stage = after
                agent.last_action_summary = summary
                agent.memory.append(f"Round {round_index}: {summary}")
                actions.append(
                    AgentAction(
                        round_index=round_index,
                        agent_id=agent.agent_id,
                        segment=agent.segment,
                        action_type=after,
                        channel=agent.preferred_channel,
                        summary=summary,
                        adoption_stage_before=before,
                        adoption_stage_after=after,
                        influence_delta=round(influence, 4),
                        conversion_delta=round(max(0.0, _stage_order(after) - _stage_order(before)) / 5.0, 4),
                        pain_relief_delta=round(pain_relief_delta, 4),
                    )
                )

            population = max(len(self.agents), 1)
            ever_tried = max(sum(1 for agent in self.agents if agent.adoption_stage in {"trial", "adopted", "retained", "churned"}), 1)
            round_summary = RoundSummary(
                round_index=round_index,
                awareness_rate=round(aware / population, 4),
                consideration_rate=round(considering / population, 4),
                trial_rate=round(trials / population, 4),
                adoption_rate=round(adopted / population, 4),
                retention_rate=round(retained / ever_tried, 4),
                virality_score=round(_clamp(virality_total / population * 1.4), 4),
                pain_relief_score=round(_clamp(pain_relief_total / max(adopted or retained, 1)), 4),
                objection_pressure=round(_clamp(sum(objections.values()) / population * 0.45), 4),
                channel_lift={label: round(value / population, 4) for label, value in channel_delta.items()},
                top_objections=[label for label, _ in objections.most_common(4)],
                key_events=[
                    f"Round {round_index} moved adoption to {round(adopted / population * 100)}% of the sandbox.",
                    f"{retained} agents stayed retained after exposure to {max(channel_delta, key=channel_delta.get, default='community')}.",
                ],
            )
            state.round_summaries.append(round_summary)
            state.agent_actions.extend(actions)
            state.completed_rounds = round_index
            state.world_state = {
                **state.world_state,
                "last_adoption_rate": round_summary.adoption_rate,
                "last_retention_rate": round_summary.retention_rate,
                "last_virality_score": round_summary.virality_score,
            }

        state.status = "completed"
        return state
