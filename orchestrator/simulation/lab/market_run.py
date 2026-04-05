"""Top-level market-lab orchestration for Quorum."""

from __future__ import annotations

from orchestrator.discovery_models import (
    AgentActivityConfig,
    IdeaDossier,
    MarketSimulationReport,
    MarketSimulationRunRequest,
    SimulationParameters,
)
from orchestrator.simulation.lab.agent_state import build_market_population
from orchestrator.simulation.lab.game_master import MarketGameMaster
from orchestrator.simulation.lab.reporting import compile_market_report
from orchestrator.simulation.lab.world_builder import build_market_world


class MarketLabRunner:
    """Runs a bounded market sandbox and compiles a dossier-attached report."""

    def run(self, dossier: IdeaDossier, request: MarketSimulationRunRequest) -> MarketSimulationReport:
        parameters = SimulationParameters(
            population_size=request.population_size,
            round_count=request.round_count,
            seed=request.seed,
            target_market=request.target_market,
            competition_pressure=request.competition_pressure,
            network_density=request.network_density,
            evidence_weight=request.evidence_weight,
        )
        activity_config = AgentActivityConfig(
            evaluation_rate=min(0.82, 0.42 + parameters.evidence_weight * 0.24),
            discussion_rate=min(0.76, 0.3 + parameters.network_density * 0.34),
            trial_rate=min(0.68, 0.18 + parameters.evidence_weight * 0.2),
            referral_rate=min(0.64, 0.14 + parameters.network_density * 0.2),
            churn_sensitivity=min(0.72, 0.2 + parameters.competition_pressure * 0.3),
        )
        world = build_market_world(dossier, parameters)
        agents = build_market_population(dossier, parameters, world)
        run_state = MarketGameMaster(parameters, activity_config, world, agents).run()
        return compile_market_report(dossier.idea.idea_id, parameters, activity_config, run_state, agents)
