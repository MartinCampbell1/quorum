"""Regression coverage for idea graph and institutional memory."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.idea_graph import clear_idea_graph_service_cache
from orchestrator.memory_graph import clear_memory_graph_service_cache
from orchestrator.models import SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_discovery_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_idea_graph_service_cache()
    clear_memory_graph_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()
    clear_idea_graph_service_cache()
    clear_memory_graph_service_cache()


def test_idea_graph_and_memory_become_queryable_across_time():
    base_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Operator repo control tower",
            "summary": "Turn repo activity into ranked workflow opportunities for operator teams.",
            "description": "A control plane for founders who repeatedly triage repo pain and productize the next wedge.",
            "source": "github",
            "topic_tags": ["ops", "repo", "workflow", "automation"],
        },
    ).json()
    base_idea_id = base_idea["idea_id"]

    follow_up_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Workflow proof engine for engineering leads",
            "summary": "Reuse the same repo signal loop but focus on engineering-lead proof and handoff.",
            "description": "A narrower wedge that grows out of the operator control tower pattern.",
            "source": "research",
            "topic_tags": ["ops", "workflow", "proof", "handoff"],
            "lineage_parent_ids": [base_idea_id],
            "evolved_from": [base_idea_id],
        },
    ).json()
    follow_up_idea_id = follow_up_idea["idea_id"]

    client.post(
        f"/orchestrate/discovery/ideas/{base_idea_id}/observations",
        json={
            "source": "github",
            "entity": "repo",
            "url": "https://github.com/getzep/graphiti",
            "raw_text": "Operator teams keep asking for cumulative repo memory instead of re-triaging the same evidence every week.",
            "topic_tags": ["ops", "repo", "memory"],
            "pain_score": 0.77,
            "trend_score": 0.64,
            "evidence_confidence": "high",
        },
    )
    client.post(
        f"/orchestrate/discovery/ideas/{follow_up_idea_id}/observations",
        json={
            "source": "reddit",
            "entity": "discussion",
            "url": "https://reddit.com/r/startups/example",
            "raw_text": "Engineering leads want proof, objections, and reusable buyer patterns attached to every workflow idea.",
            "topic_tags": ["ops", "workflow", "buyer"],
            "pain_score": 0.69,
            "trend_score": 0.61,
            "evidence_confidence": "medium",
        },
    )
    client.post(
        f"/orchestrate/discovery/ideas/{follow_up_idea_id}/validation-reports",
        json={
            "summary": "The wedge is promising, but ROI is still unclear for teams without a clear buyer champion.",
            "verdict": "partial",
            "findings": ["ROI is unclear for solo dev teams", "Buyer champion needs clearer proof"],
            "confidence": "medium",
        },
    )
    client.post(
        f"/orchestrate/discovery/ideas/{base_idea_id}/decisions",
        json={
            "decision_type": "yes",
            "rationale": "The base operator workflow keeps resurfacing and has enough evidence to keep pushing.",
            "actor": "founder",
        },
    )
    client.put(
        f"/orchestrate/discovery/ideas/{base_idea_id}/execution-brief-candidate",
        json={
            "title": "Operator repo control tower",
            "prd_summary": "Carry cumulative proof and objections into every repo-backed discovery candidate.",
            "acceptance_criteria": ["Persist cumulative memory", "Query reusable proof patterns"],
            "confidence": "medium",
            "effort": "small",
            "urgency": "this_week",
            "budget_tier": "low",
        },
    )

    graph_response = client.post("/orchestrate/discovery/idea-graph/rebuild")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["idea_count"] == 2
    assert graph_payload["node_count"] >= 8
    assert graph_payload["edge_count"] >= 8
    assert any(node["kind"] == "idea" for node in graph_payload["nodes"])
    assert any(edge["kind"] == "evolved_from" for edge in graph_payload["edges"])
    assert any(community["title"] == "ops" for community in graph_payload["communities"])
    listed_graphs = client.get("/orchestrate/discovery/idea-graph/snapshots?limit=5")
    assert listed_graphs.status_code == 200
    assert listed_graphs.json()["items"][0]["graph_id"] == graph_payload["graph_id"]
    fetched_graph = client.get(f"/orchestrate/discovery/idea-graph/snapshots/{graph_payload['graph_id']}")
    assert fetched_graph.status_code == 200
    assert fetched_graph.json()["graph_id"] == graph_payload["graph_id"]

    idea_context_response = client.get(f"/orchestrate/discovery/ideas/{follow_up_idea_id}/idea-graph")
    assert idea_context_response.status_code == 200
    idea_context = idea_context_response.json()
    assert base_idea_id in idea_context["lineage_idea_ids"]

    memory_response = client.post("/orchestrate/discovery/memory/rebuild")
    assert memory_response.status_code == 200
    memory_payload = memory_response.json()
    assert memory_payload["episode_count"] >= 5
    assert memory_payload["semantic_memory_count"] >= 1
    assert memory_payload["skill_count"] >= 1
    assert any("ops" in item["summary"].lower() or item["key"].lower() == "ops" for item in memory_payload["semantic_memories"])
    listed_memories = client.get("/orchestrate/discovery/memory/snapshots?limit=5")
    assert listed_memories.status_code == 200
    assert listed_memories.json()["items"][0]["snapshot_id"] == memory_payload["snapshot_id"]
    fetched_memory = client.get(f"/orchestrate/discovery/memory/snapshots/{memory_payload['snapshot_id']}")
    assert fetched_memory.status_code == 200
    assert fetched_memory.json()["snapshot_id"] == memory_payload["snapshot_id"]

    query_response = client.post(
        "/orchestrate/discovery/memory/query",
        json={"query": "ops repo workflow buyer proof", "limit": 6},
    )
    assert query_response.status_code == 200
    query_payload = query_response.json()
    assert len(query_payload["matches"]) >= 1
    assert any(match["kind"] in {"semantic_memory", "skill"} for match in query_payload["matches"])
    assert base_idea_id in query_payload["related_idea_ids"] or follow_up_idea_id in query_payload["related_idea_ids"]

    dossier_response = client.get(f"/orchestrate/discovery/ideas/{base_idea_id}/dossier")
    assert dossier_response.status_code == 200
    dossier = dossier_response.json()
    assert follow_up_idea_id in dossier["idea_graph_context"]["related_idea_ids"]
    assert len(dossier["memory_context"]["semantic_highlights"]) >= 1
    assert len(dossier["memory_context"]["skill_hits"]) >= 1

    memory_context_response = client.get(f"/orchestrate/discovery/ideas/{base_idea_id}/memory")
    assert memory_context_response.status_code == 200
    assert memory_context_response.json()["snapshot_id"] == memory_payload["snapshot_id"]
