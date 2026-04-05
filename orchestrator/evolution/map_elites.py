"""Categorical MAP-Elites archive for startup idea diversity."""

from __future__ import annotations

from collections import Counter
from statistics import fmean
from typing import Sequence

from orchestrator.evolution.archive import (
    ArchiveCheckpointDigest,
    IdeaArchiveCell,
    IdeaArchiveSnapshot,
    IdeaGenome,
    PromptEvolutionProfile,
    cell_key_for_axes,
    total_possible_cells,
)


class MapElitesArchive:
    """Simple categorical MAP-Elites archive over domain / complexity / distribution / buyer."""

    def __init__(self):
        self._cells: dict[str, IdeaArchiveCell] = {}
        self._genomes: list[IdeaGenome] = []

    def insert(self, genome: IdeaGenome) -> bool:
        self._genomes.append(genome)
        key = cell_key_for_axes(
            genome.domain,
            genome.complexity,
            genome.distribution_strategy,
            genome.buyer_type,
        )
        current = self._cells.get(key)
        if current is None or genome.fitness > current.elite.fitness or (
            genome.fitness == current.elite.fitness and genome.novelty_score > current.elite.novelty_score
        ):
            self._cells[key] = IdeaArchiveCell(
                key=key,
                domain=genome.domain,
                complexity=genome.complexity,
                distribution_strategy=genome.distribution_strategy,
                buyer_type=genome.buyer_type,
                elite=genome,
                replaced_genome_id=current.elite.genome_id if current else None,
            )
            return True
        return False

    def bulk_insert(self, genomes: Sequence[IdeaGenome]) -> list[bool]:
        return [self.insert(genome) for genome in genomes]

    def cells(self) -> list[IdeaArchiveCell]:
        return list(self._cells.values())

    def snapshot(
        self,
        *,
        generation: int,
        prompt_profiles: Sequence[PromptEvolutionProfile] = (),
        recommendations=(),
        checkpoints: Sequence[ArchiveCheckpointDigest] = (),
        checkpointed: bool = False,
        limit_cells: int = 24,
    ) -> IdeaArchiveSnapshot:
        cells = sorted(self._cells.values(), key=lambda item: (item.elite.fitness, item.elite.novelty_score), reverse=True)
        top_genomes = [cell.elite for cell in cells[: max(1, min(limit_cells, len(cells) or 1))]]
        filled = len(cells)
        qd_score = round(sum(cell.elite.fitness for cell in cells), 4)
        novelty_mean = round(fmean(cell.elite.novelty_score for cell in cells), 4) if cells else 0.0

        diversity_counter = Counter()
        for cell in cells:
            diversity_counter.update(
                [
                    f"d:{cell.domain}",
                    f"c:{cell.complexity}",
                    f"x:{cell.distribution_strategy}",
                    f"b:{cell.buyer_type}",
                ]
            )
        diversity_score = 0.0
        if diversity_counter:
            unique_axes = len(diversity_counter)
            max_axes = 4 * max(1, len(cells))
            diversity_score = min(unique_axes / max_axes, 1.0)

        return IdeaArchiveSnapshot(
            generation=generation,
            total_possible_cells=total_possible_cells(),
            filled_cells=filled,
            coverage=round(filled / max(total_possible_cells(), 1), 4),
            qd_score=qd_score,
            diversity_score=round(diversity_score, 4),
            novelty_mean=novelty_mean,
            cells=cells[: max(1, min(limit_cells, len(cells) or 1))],
            top_genomes=top_genomes[:10],
            prompt_profiles=list(prompt_profiles),
            recommendations=list(recommendations),
            checkpoints=list(checkpoints),
            checkpointed=checkpointed,
        )
