"""Regression coverage for anti-banality novelty helpers."""

from orchestrator.debate.judge_pack import aggregate_founder_scorecards, parse_founder_scorecard
from orchestrator.novelty.breeding import generate_trisociation_blends
from orchestrator.novelty.noise_seed import generate_noise_seeds
from orchestrator.novelty.semantic_tabu import assess_semantic_tabu


def test_semantic_tabu_flags_cliche_and_duplicate_ideas():
    assessment = assess_semantic_tabu(
        "AI copilot for HR teams that automates recruiting workflow.",
        prior_candidates=["AI copilot for recruiting teams that automates hiring workflow."],
    )

    assert assessment.penalty > 0.45
    assert assessment.cliche_hits
    assert assessment.reasons


def test_noise_seed_generation_is_deterministic():
    first = generate_noise_seeds("Turn repo history into startup directions", count=3)
    second = generate_noise_seeds("Turn repo history into startup directions", count=3)

    assert [item.seed_text for item in first] == [item.seed_text for item in second]
    assert len({item.seed_id for item in first}) == 3


def test_trisociation_blends_fuse_distant_domains():
    blends = generate_trisociation_blends(
        "Find startup territory from repo history",
        domain_candidates=["developer tooling", "supply chain", "compliance ops", "embedded finance"],
        seed_texts=["Use operational exhaust as the moat."],
        count=2,
    )

    assert len(blends) == 2
    assert all(len(item.domains) == 3 for item in blends)
    assert all(item.distance_score > 0 for item in blends)


def test_founder_scorecard_parsing_and_aggregation_work():
    scorecard = parse_founder_scorecard(
        {
            "scorecard": {
                "problem_sharpness": 9,
                "icp_clarity": 8,
                "distribution_plausibility": 7,
                "ai_necessity": 9,
            }
        }
    )

    aggregate = aggregate_founder_scorecards([scorecard, scorecard])

    assert scorecard["problem_sharpness"] == 9.0
    assert aggregate["icp_clarity"] == 8.0
