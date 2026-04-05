"""Regression coverage for pairwise ranking, archive, and finals routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.models import SessionStore
from orchestrator.ranking import clear_ranking_service_cache


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_ranking_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_ranking_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()
    clear_ranking_service_cache()


def test_ranking_api_tracks_pairwise_votes_and_resolves_finals():
    ideas = [
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Approval workflow copilot",
                "summary": "Turn repository evidence into approval-routing opportunities.",
                "source": "github",
                "topic_tags": ["workflow-automation", "developer-tools", "b2b", "ai"],
                "latest_scorecard": {"rank_score": 0.84, "belief_score": 0.78},
            },
        ).json(),
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Compliance inbox for repos",
                "summary": "Rank and route repo compliance gaps before they become customer pain.",
                "source": "research",
                "topic_tags": ["compliance", "workflow-automation", "b2b"],
                "latest_scorecard": {"rank_score": 0.74, "belief_score": 0.69},
            },
        ).json(),
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Family trip planner",
                "summary": "A lighter consumer planning product for travel logistics.",
                "source": "manual",
                "topic_tags": ["consumer", "b2c"],
                "latest_scorecard": {"rank_score": 0.31, "belief_score": 0.28},
            },
        ).json(),
    ]

    initial_board = client.get("/orchestrate/ranking/leaderboard?limit=10")
    assert initial_board.status_code == 200
    initial_payload = initial_board.json()
    assert len(initial_payload["items"]) == 3
    assert initial_payload["metrics"]["comparisons_count"] == 0

    next_pair = client.get("/orchestrate/ranking/next-pair")
    assert next_pair.status_code == 200
    pair_payload = next_pair.json()["pair"]
    assert pair_payload is not None

    compare = client.post(
        "/orchestrate/ranking/compare",
        json={
            "left_idea_id": pair_payload["left"]["idea"]["idea_id"],
            "right_idea_id": pair_payload["right"]["idea"]["idea_id"],
            "verdict": "left",
            "rationale": "The left idea is materially closer to revenue and better aligned with the founder stack.",
            "judge_source": "human",
            "domain_key": "founder-fit",
            "judge_confidence": 0.9,
            "evidence_weight": 1.2,
            "agent_importance_score": 1.1,
        },
    )
    assert compare.status_code == 200
    compare_payload = compare.json()
    assert compare_payload["comparison"]["comparison_weight"] > 0
    assert compare_payload["comparison"]["winner_idea_id"] == pair_payload["left"]["idea"]["idea_id"]
    assert compare_payload["leaderboard"]["metrics"]["comparisons_count"] == 1
    assert compare_payload["leaderboard"]["judges"][0]["judge_source"] == "human"
    assert compare_payload["leaderboard"]["metrics"]["unique_pairs"] == 1

    promoted_idea = client.get(
        f"/orchestrate/discovery/ideas/{pair_payload['left']['idea']['idea_id']}"
    )
    assert promoted_idea.status_code == 200
    promoted_payload = promoted_idea.json()
    assert promoted_payload["latest_stage"] == "ranked"
    assert "pairwise_rating" in promoted_payload["latest_scorecard"]
    assert "pairwise_stability" in promoted_payload["latest_scorecard"]
    assert "evolution_archive_fitness" in promoted_payload["latest_scorecard"]
    assert promoted_payload["provenance"]["evolution_archive"]["cell_key"]
    assert promoted_payload["provenance"]["evolution_archive"]["prompt_profile_id"]

    refreshed_board = client.get("/orchestrate/ranking/leaderboard?limit=10")
    assert refreshed_board.status_code == 200
    board_payload = refreshed_board.json()
    assert board_payload["metrics"]["comparisons_count"] == 1
    assert -1 <= board_payload["metrics"]["rank_stability"] <= 1
    assert board_payload["metrics"]["average_ci_width"] > 0

    archive = client.get("/orchestrate/ranking/archive?limit_cells=10")
    assert archive.status_code == 200
    archive_payload = archive.json()
    assert archive_payload["generation"] == 1
    assert archive_payload["filled_cells"] >= 2
    assert archive_payload["coverage"] > 0
    assert archive_payload["cells"]
    assert archive_payload["prompt_profiles"]
    assert archive_payload["checkpoints"]
    assert archive_payload["checkpoints"][0]["generation"] == 1

    ranked_ids = [item["idea"]["idea_id"] for item in board_payload["items"][:3]]
    finals = client.post(
        "/orchestrate/ranking/finals/resolve",
        json={
            "candidate_idea_ids": ranked_ids,
            "ballots": [
                {
                    "voter_id": "founder",
                    "ranked_idea_ids": ranked_ids,
                    "weight": 1.4,
                    "judge_source": "human",
                    "confidence": 0.9,
                    "agent_importance_score": 1.0,
                },
                {
                    "voter_id": "research-council",
                    "ranked_idea_ids": [ranked_ids[0], ranked_ids[2], ranked_ids[1]],
                    "weight": 1.1,
                    "judge_source": "council",
                    "confidence": 0.78,
                    "agent_importance_score": 1.05,
                },
                {
                    "voter_id": "ops-agent",
                    "ranked_idea_ids": [ranked_ids[1], ranked_ids[0], ranked_ids[2]],
                    "weight": 0.8,
                    "judge_source": "agent",
                    "judge_agent_id": "ops-agent",
                    "confidence": 0.66,
                    "agent_importance_score": 1.0,
                },
            ],
        },
    )
    assert finals.status_code == 200
    finals_payload = finals.json()
    assert finals_payload["winner_idea_id"] == ranked_ids[0]
    assert finals_payload["rounds"]
    assert len(finals_payload["aggregate_rankings"]) == 3

    invalid_compare = client.post(
        "/orchestrate/ranking/compare",
        json={
            "left_idea_id": ideas[0]["idea_id"],
            "right_idea_id": "idea_missing",
            "verdict": "left",
        },
    )
    assert invalid_compare.status_code == 404


def test_ranking_archive_tracks_checkpoint_history():
    ideas = [
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Repo ops copilot",
                "summary": "Turns repository patterns into workflow fixes.",
                "source": "github",
                "topic_tags": ["developer-tools", "ops", "ai"],
                "latest_scorecard": {"rank_score": 0.86, "belief_score": 0.8},
            },
        ).json(),
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Security drift watcher",
                "summary": "Spots configuration and policy drift before audits fail.",
                "source": "research",
                "topic_tags": ["security", "compliance", "b2b"],
                "latest_scorecard": {"rank_score": 0.76, "belief_score": 0.72},
            },
        ).json(),
        client.post(
            "/orchestrate/discovery/ideas",
            json={
                "title": "Content ops planner",
                "summary": "Automates inbound content experiments for niche operators.",
                "source": "manual",
                "topic_tags": ["marketing", "content", "smb"],
                "latest_scorecard": {"rank_score": 0.61, "belief_score": 0.57},
            },
        ).json(),
    ]

    comparisons = [
        (ideas[0]["idea_id"], ideas[1]["idea_id"], "left"),
        (ideas[1]["idea_id"], ideas[2]["idea_id"], "left"),
        (ideas[0]["idea_id"], ideas[2]["idea_id"], "left"),
        (ideas[1]["idea_id"], ideas[0]["idea_id"], "right"),
        (ideas[2]["idea_id"], ideas[0]["idea_id"], "right"),
    ]
    for left_id, right_id, verdict in comparisons:
        response = client.post(
            "/orchestrate/ranking/compare",
            json={
                "left_idea_id": left_id,
                "right_idea_id": right_id,
                "verdict": verdict,
                "judge_source": "human",
                "judge_confidence": 0.82,
            },
        )
        assert response.status_code == 200

    archive = client.get("/orchestrate/ranking/archive?limit_cells=12")
    assert archive.status_code == 200
    payload = archive.json()
    assert payload["generation"] == 5
    checkpoint_generations = {item["generation"] for item in payload["checkpoints"]}
    assert {1, 5}.issubset(checkpoint_generations)
    assert payload["filled_cells"] >= 2
