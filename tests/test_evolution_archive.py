"""Unit coverage for MAP-Elites archive and prompt evolution helpers."""

from orchestrator.discovery_store import DiscoveryStore
from orchestrator.evolution.archive import IdeaArchiveSnapshot, IdeaGenome
from orchestrator.evolution.map_elites import MapElitesArchive
from orchestrator.evolution.prompt_evolution import evolve_prompt_profiles
from orchestrator.ranking import RankingIndex, RankingService


def _genome(
    idea_id: str,
    *,
    title: str,
    domain: str,
    complexity: str,
    distribution_strategy: str,
    buyer_type: str,
    fitness: float,
    novelty: float,
    prompt_profile_id: str | None = None,
) -> IdeaGenome:
    return IdeaGenome(
        idea_id=idea_id,
        title=title,
        lineage_idea_ids=[],
        domain=domain,
        complexity=complexity,
        distribution_strategy=distribution_strategy,
        buyer_type=buyer_type,
        fitness=fitness,
        novelty_score=novelty,
        rating=1200.0,
        merit_score=0.7,
        stability_score=0.7,
        prompt_profile_id=prompt_profile_id,
    )


def test_map_elites_keeps_best_genome_per_cell():
    archive = MapElitesArchive()
    weaker = _genome(
        "idea_a",
        title="Repo approvals",
        domain="developer_tooling",
        complexity="low",
        distribution_strategy="github",
        buyer_type="developer",
        fitness=0.62,
        novelty=0.54,
    )
    stronger = _genome(
        "idea_b",
        title="Repo approvals plus analytics",
        domain="developer_tooling",
        complexity="low",
        distribution_strategy="github",
        buyer_type="developer",
        fitness=0.81,
        novelty=0.58,
    )
    distinct = _genome(
        "idea_c",
        title="Security drift watcher",
        domain="security",
        complexity="medium",
        distribution_strategy="integration",
        buyer_type="compliance",
        fitness=0.75,
        novelty=0.71,
    )

    results = archive.bulk_insert([weaker, stronger, distinct])
    snapshot = archive.snapshot(generation=2, limit_cells=8)

    assert results == [True, True, True]
    assert snapshot.filled_cells == 2
    cell_lookup = {cell.key: cell for cell in snapshot.cells}
    assert cell_lookup[stronger.cell_key].elite.idea_id == "idea_b"
    assert snapshot.qd_score == round(stronger.fitness + distinct.fitness, 4)


def test_prompt_evolution_updates_profile_ratings_from_outcomes():
    left = _genome(
        "idea_left",
        title="Founder exploit",
        domain="operations",
        complexity="medium",
        distribution_strategy="sales_led",
        buyer_type="founder",
        fitness=0.77,
        novelty=0.51,
        prompt_profile_id="deevo_founder_fit",
    )
    right = _genome(
        "idea_right",
        title="Cross-domain bet",
        domain="security",
        complexity="high",
        distribution_strategy="community",
        buyer_type="developer",
        fitness=0.73,
        novelty=0.78,
        prompt_profile_id="deevo_cross_domain",
    )

    profiles = evolve_prompt_profiles(
        [left, right],
        [
            {
                "left_idea_id": "idea_left",
                "right_idea_id": "idea_right",
                "verdict": "left",
                "comparison_weight": 1.4,
                "judge_source": "council",
            }
        ],
    )
    by_id = {profile.profile_id: profile for profile in profiles}

    assert by_id["deevo_founder_fit"].wins == 1
    assert by_id["deevo_cross_domain"].losses == 1
    assert by_id["deevo_founder_fit"].elo_rating > by_id["deevo_cross_domain"].elo_rating
    assert by_id["deevo_founder_fit"].debate_influence > 0


def test_ranking_checkpoint_policy_saves_first_and_every_fifth_generation(tmp_path):
    service = RankingService(
        RankingIndex(str(tmp_path / "ranking.db")),
        DiscoveryStore(str(tmp_path / "discovery.db")),
    )
    generation_one = IdeaArchiveSnapshot(generation=1, filled_cells=1, coverage=0.01, qd_score=0.7)
    generation_two = IdeaArchiveSnapshot(generation=2, filled_cells=2, coverage=0.02, qd_score=1.4)
    generation_five = IdeaArchiveSnapshot(generation=5, filled_cells=3, coverage=0.03, qd_score=2.1)

    assert service._should_checkpoint_snapshot(generation_one) is True
    service._index.save_archive_snapshot(generation_one)
    assert service._should_checkpoint_snapshot(generation_two) is False
    assert service._should_checkpoint_snapshot(generation_five) is True
