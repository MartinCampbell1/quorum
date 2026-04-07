"""Evolutionary operator recommendations for idea search."""

from __future__ import annotations

from itertools import combinations
from statistics import fmean
from typing import Sequence

from orchestrator.evolution.archive import EvolutionRecommendation, IdeaArchiveCell, IdeaGenome


def _distance(left: IdeaGenome, right: IdeaGenome) -> float:
    axes = [
        left.domain != right.domain,
        left.complexity != right.complexity,
        left.distribution_strategy != right.distribution_strategy,
        left.buyer_type != right.buyer_type,
    ]
    return sum(1 for changed in axes if changed) / len(axes)


def _mutation_target(genome: IdeaGenome, cells: Sequence[IdeaArchiveCell]) -> dict[str, str]:
    occupied_domains = {cell.domain for cell in cells}
    occupied_distribution = {cell.distribution_strategy for cell in cells}
    target = {
        "domain": genome.domain,
        "complexity": genome.complexity,
        "distribution_strategy": genome.distribution_strategy,
        "buyer_type": genome.buyer_type,
    }
    if genome.novelty_score < 0.58:
        for domain in ("research_data", "compliance", "security", "developer_tooling", "operations"):
            if domain not in occupied_domains:
                target["domain"] = domain
                break
    if genome.stability_score < 0.55:
        for strategy in ("integration", "github", "outbound", "community", "ecosystem"):
            if strategy != genome.distribution_strategy and strategy not in occupied_distribution:
                target["distribution_strategy"] = strategy
                break
    if genome.complexity == "frontier":
        target["complexity"] = "high"
    elif genome.complexity == "high":
        target["complexity"] = "medium"
    return target


def build_recommendations(
    genomes: Sequence[IdeaGenome],
    cells: Sequence[IdeaArchiveCell],
    *,
    limit: int = 6,
) -> list[EvolutionRecommendation]:
    if not genomes:
        return []

    ranked = sorted(genomes, key=lambda item: (item.fitness, item.novelty_score), reverse=True)
    recommendations: list[EvolutionRecommendation] = []

    for genome in ranked[: min(3, len(ranked))]:
        target_axes = _mutation_target(genome, cells)
        if any(target_axes[key] != getattr(genome, key) for key in target_axes):
            recommendations.append(
                EvolutionRecommendation(
                    operator_kind="mutate",
                    headline=f"Mutate {genome.title}",
                    description=(
                        f"Keep the core pain from '{genome.title}' but mutate one axis toward "
                        f"{target_axes['domain']} / {target_axes['distribution_strategy']} to open a new niche."
                    ),
                    source_genome_ids=[genome.genome_id],
                    target_axes=target_axes,
                    prompt_profile_id=genome.prompt_profile_id,
                )
            )

    crossover_pairs = []
    for left, right in combinations(ranked[: min(5, len(ranked))], 2):
        distance = _distance(left, right)
        if distance < 0.5:
            continue
        score = (left.fitness + right.fitness) / 2.0 + (distance * 0.25)
        crossover_pairs.append((score, distance, left, right))
    crossover_pairs.sort(key=lambda item: (-item[0], -item[1]))
    for _, distance, left, right in crossover_pairs[: max(1, limit - len(recommendations))]:
        recommendations.append(
            EvolutionRecommendation(
                operator_kind="crossover",
                headline=f"Crossover {left.title} x {right.title}",
                description=(
                    f"Fuse {left.domain} pain from '{left.title}' with {right.distribution_strategy} distribution "
                    f"from '{right.title}'. Axes distance={distance:.2f}, so this is a real cross-niche experiment."
                ),
                source_genome_ids=[left.genome_id, right.genome_id],
                target_axes={
                    "domain": left.domain,
                    "complexity": "medium" if "medium" in {left.complexity, right.complexity} else left.complexity,
                    "distribution_strategy": right.distribution_strategy,
                    "buyer_type": left.buyer_type if left.buyer_type != "consumer" else right.buyer_type,
                },
                prompt_profile_id=left.prompt_profile_id or right.prompt_profile_id,
            )
        )

    if ranked:
        average_fitness = fmean(item.fitness for item in ranked)
        if average_fitness < 0.62:
            anchor = ranked[0]
            recommendations.append(
                EvolutionRecommendation(
                    operator_kind="exploit",
                    headline="Exploit the current winner harder",
                    description=(
                        f"The population fitness is still shallow ({average_fitness:.2f}). "
                        f"Double down on '{anchor.title}' and sharpen ICP + distribution before widening the search."
                    ),
                    source_genome_ids=[anchor.genome_id],
                    target_axes={
                        "domain": anchor.domain,
                        "complexity": anchor.complexity,
                        "distribution_strategy": anchor.distribution_strategy,
                        "buyer_type": anchor.buyer_type,
                    },
                    prompt_profile_id=anchor.prompt_profile_id,
                )
            )

    return recommendations[:limit]
