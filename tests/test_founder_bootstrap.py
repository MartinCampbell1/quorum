"""Tests for the founder GitHub bootstrap models and pipeline."""
from __future__ import annotations

import pytest

from orchestrator.models_bootstrap import (
    FounderBootstrapRequest,
    FounderBootstrapResponse,
    FounderProfileSynthesis,
    InterestCluster,
    OpportunityHypothesis,
)
from orchestrator.founder_bootstrap import FounderBootstrapPipeline


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_bootstrap_request_defaults():
    req = FounderBootstrapRequest(github_username="alice")
    assert req.max_repos == 100
    assert req.deep_scan_top_n == 8
    assert req.include_forks is False
    assert req.include_archived is False
    assert req.portfolio_id == "founder_default"


def test_interest_cluster_model():
    cluster = InterestCluster(
        cluster_id="c1",
        label="devtools",
        repos=["repo-a", "repo-b"],
        topics=["devtools"],
        languages=["Python"],
        strength=0.4,
    )
    assert cluster.label == "devtools"
    assert len(cluster.repos) == 2
    assert cluster.strength == 0.4


def test_opportunity_hypothesis_model():
    hyp = OpportunityHypothesis(
        hypothesis_id="h1",
        title="Build devtools SaaS",
        description="Founders keep shipping devtools.",
        source_clusters=["c1"],
        unfair_advantages=["Python", "Go"],
        likely_icps=["platform engineers"],
        confidence=0.7,
    )
    assert hyp.provenance == "github_portfolio"
    assert hyp.confidence == 0.7
    assert "c1" in hyp.source_clusters


def test_bootstrap_response_contains_all_sections():
    response = FounderBootstrapResponse(
        github_username="alice",
        repos_scanned=10,
        repos_deep_scanned=3,
        profile=FounderProfileSynthesis(interests=["cli", "devtools"]),
        clusters=[
            InterestCluster(
                cluster_id="c1",
                label="devtools",
                repos=["r1"],
                strength=0.1,
            )
        ],
        hypotheses=[
            OpportunityHypothesis(
                hypothesis_id="h1",
                title="devtools SaaS",
            )
        ],
    )
    assert response.repos_scanned == 10
    assert response.repos_deep_scanned == 3
    assert len(response.clusters) == 1
    assert len(response.hypotheses) == 1
    assert response.profile.interests == ["cli", "devtools"]


# ---------------------------------------------------------------------------
# Pipeline unit tests
# ---------------------------------------------------------------------------


def test_bootstrap_pipeline_inventory_step():
    pipeline = FounderBootstrapPipeline()
    raw = [
        {
            "name": "my-cli",
            "full_name": "alice/my-cli",
            "description": "A CLI tool",
            "topics": ["cli", "devtools"],
            "language": "Python",
            "stargazers_count": 42,
            "fork": False,
            "archived": False,
        }
    ]
    inventory = pipeline._build_inventory(raw)
    assert len(inventory) == 1
    item = inventory[0]
    assert item["name"] == "my-cli"
    assert item["language"] == "Python"
    assert item["stargazers_count"] == 42
    assert "cli" in item["topics"]


def test_bootstrap_pipeline_clustering():
    pipeline = FounderBootstrapPipeline()
    inventory = [
        {"name": "tool-a", "topics": ["devtools", "cli"], "language": "Go", "stargazers_count": 5},
        {"name": "tool-b", "topics": ["devtools"], "language": "Python", "stargazers_count": 3},
        {"name": "tool-c", "topics": ["ml", "data"], "language": "Python", "stargazers_count": 1},
    ]
    clusters = pipeline._cluster_by_theme(inventory)
    labels = [c.label for c in clusters]
    # "devtools" has 2 repos — should be the first cluster
    assert labels[0] == "devtools"
    # "ml" or "cli" should also appear
    assert len(clusters) >= 2


def test_bootstrap_pipeline_clustering_strength():
    pipeline = FounderBootstrapPipeline()
    inventory = [
        {"name": f"repo-{i}", "topics": ["topic-a"], "language": "Python", "stargazers_count": i}
        for i in range(4)
    ] + [
        {"name": "other", "topics": ["topic-b"], "language": "Go", "stargazers_count": 0}
    ]
    clusters = pipeline._cluster_by_theme(inventory)
    topic_a_cluster = next(c for c in clusters if c.label == "topic-a")
    # 4 repos out of 5 total → strength == 0.8
    assert abs(topic_a_cluster.strength - 0.8) < 1e-9


def test_bootstrap_pipeline_empty_repos():
    pipeline = FounderBootstrapPipeline()
    inventory = pipeline._build_inventory([])
    assert inventory == []
    clusters = pipeline._cluster_by_theme([])
    assert clusters == []


@pytest.mark.asyncio
async def test_bootstrap_pipeline_run_no_client():
    """run() without a GitHub client fails fast with a clear configuration error."""
    pipeline = FounderBootstrapPipeline()
    request = FounderBootstrapRequest(github_username="ghost")
    with pytest.raises(ValueError, match="github_client is required"):
        await pipeline.run(request)
