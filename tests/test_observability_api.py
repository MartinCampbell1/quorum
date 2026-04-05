"""Regression coverage for observability, replay, and dossier explainability."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.idea_graph import clear_idea_graph_service_cache
from orchestrator.memory_graph import clear_memory_graph_service_cache
from orchestrator.models import AgentConfig, SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    clear_idea_graph_service_cache()
    clear_memory_graph_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()
    clear_idea_graph_service_cache()
    clear_memory_graph_service_cache()


def test_observability_surfaces_scoreboard_traces_replay_and_explainability(isolated_state: SessionStore):
    strong_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "Repo-native founder control tower",
            "summary": "Continuously rank workflow pain from repo behavior and turn it into execution-ready wedges.",
            "description": "A founder workflow for evidence, ranking, validation, and build handoff.",
            "source": "github",
            "topic_tags": ["repo", "ops", "workflow", "ranking"],
            "latest_scorecard": {"rank_score": 0.74, "belief_score": 0.69, "evidence_quality": 0.72},
        },
    ).json()
    strong_idea_id = strong_idea["idea_id"]

    weak_idea = client.post(
        "/orchestrate/discovery/ideas",
        json={
            "title": "AI copilot for everyone",
            "summary": "A generic AI platform for all teams.",
            "description": "Broad assistant without a tight buyer or distribution wedge.",
            "source": "manual",
            "topic_tags": ["ai", "platform"],
            "latest_scorecard": {"rank_score": 0.22, "belief_score": 0.19},
        },
    ).json()

    client.post(
        f"/orchestrate/discovery/ideas/{strong_idea_id}/observations",
        json={
            "source": "github",
            "entity": "issue",
            "url": "https://github.com/truera/trulens",
            "raw_text": "Operators keep revisiting the same repo signals and want an explainable ranked dossier instead of ad-hoc triage.",
            "topic_tags": ["repo", "ops", "explainability"],
            "pain_score": 0.82,
            "trend_score": 0.68,
            "evidence_confidence": "high",
        },
    )
    client.post(
        f"/orchestrate/discovery/ideas/{strong_idea_id}/validation-reports",
        json={
            "summary": "The wedge is sharp because buyer pain and repo-native distribution are both plausible.",
            "verdict": "pass",
            "findings": ["Buyer is explicit", "Evidence is already repo-native", "Distribution path starts from GitHub history"],
            "confidence": "high",
        },
    )
    swipe = client.post(
        f"/orchestrate/discovery/ideas/{strong_idea_id}/swipe",
        json={"action": "yes", "rationale": "This is concrete enough to keep ranking upward."},
    )
    assert swipe.status_code == 200

    simulation = client.post(
        f"/orchestrate/discovery/ideas/{strong_idea_id}/simulation",
        json={"persona_count": 10, "max_rounds": 2, "seed": 7},
    )
    assert simulation.status_code == 200
    market_simulation = client.post(
        f"/orchestrate/discovery/ideas/{strong_idea_id}/simulation/lab",
        json={"population_size": 24, "round_count": 2, "seed": 11},
    )
    assert market_simulation.status_code == 200

    created_at = time.time()
    session_id = isolated_state.create(
        mode="debate",
        task="Debate the repo-native founder control tower wedge",
        agents=[
            AgentConfig(role="proponent", provider="claude", tools=["web_search"]),
            AgentConfig(role="opponent", provider="codex", tools=["code_exec"]),
            AgentConfig(role="judge", provider="gemini", tools=["perplexity"]),
        ],
        config={
            "execution_mode": "parallel",
            "topology_state": {"selected_template": "branch_merge"},
            "generation_trace": {
                "trace_artifacts": [
                    {
                        "artifact_id": "artifact_1",
                        "layer": "layer1",
                        "agent_role": "proponent",
                        "provider": "claude",
                        "content": "Repo-native control tower candidate",
                        "summary": "Sharper repo-native wedge",
                        "generated_at": created_at + 1.0,
                    }
                ],
                "final_artifact": {
                    "artifact_id": "artifact_final",
                    "layer": "final",
                    "agent_role": "judge_pack",
                    "provider": "gemini",
                    "content": "Control tower wins because the buyer and distribution path are clearer.",
                    "summary": "Control tower wins",
                    "generated_at": created_at + 3.0,
                },
            },
        },
        protocol_blueprint={
            "blueprint_id": "blueprint_obs",
            "protocol_key": "crossfire",
            "cache_key": "debate::crossfire",
            "planner_hints": {"topology": {"selected_template": "branch_merge"}},
        },
        protocol_trace=[
            {
                "trace_id": "trace_1",
                "blueprint_id": "blueprint_obs",
                "step_index": 1,
                "from_node_id": "open",
                "to_node_id": "crossfire",
                "checkpoint_id": "cp_1",
                "ok": True,
                "timestamp": created_at + 0.5,
                "errors": [],
                "warnings": [],
                "state_excerpt": {"stance": "proponent"},
            },
            {
                "trace_id": "trace_2",
                "blueprint_id": "blueprint_obs",
                "step_index": 2,
                "from_node_id": "crossfire",
                "to_node_id": "judge",
                "checkpoint_id": "cp_2",
                "ok": False,
                "timestamp": created_at + 2.5,
                "errors": ["judge retry"],
                "warnings": [],
                "state_excerpt": {"stance": "judge"},
            },
        ],
        protocol_shadow_validation={
            "validated_transitions": 1,
            "invalid_transitions": 1,
            "cache_hit": True,
        },
    )
    isolated_state.append_event(session_id, "run_started", "Run started", "Debate kicked off.")
    isolated_state.add_checkpoint(
        session_id,
        {
            "id": "cp_1",
            "timestamp": created_at + 0.6,
            "next_node": "crossfire",
            "status": "ready",
            "result_preview": "Opening arguments ready.",
        },
    )
    isolated_state.append_event(session_id, "agent_message", "Opening argument", "Repo-native evidence sharpens the wedge.", agent_id="proponent")
    isolated_state.append_event(session_id, "run_completed", "Run completed", "Control tower wins.")
    isolated_state.update(session_id, status="completed", elapsed_sec=13.4, result="Control tower wins.")

    evals_response = client.get("/orchestrate/observability/evals/discovery?limit=10")
    assert evals_response.status_code == 200
    evals_payload = evals_response.json()
    assert evals_payload["items"][0]["idea_id"] == strong_idea_id
    assert evals_payload["averages"]["overall_health"] > 0

    scoreboard_response = client.get("/orchestrate/observability/scoreboards/discovery")
    assert scoreboard_response.status_code == 200
    scoreboard = scoreboard_response.json()
    assert scoreboard["idea_count"] == 2
    metric_keys = {item["key"] for item in scoreboard["metrics"]}
    assert {"swipe_acceptance_rate", "evidence_hit_rate", "avg_session_latency_sec"}.issubset(metric_keys)
    assert scoreboard["protocol_regressions"][0]["protocol_key"] == "crossfire"

    traces_response = client.get("/orchestrate/observability/traces/discovery?limit=10")
    assert traces_response.status_code == 200
    traces_payload = traces_response.json()
    assert traces_payload["idea_count"] == 2
    assert traces_payload["session_count"] >= 1
    assert any(item["session_id"] == session_id for item in traces_payload["recent_sessions"])

    idea_trace_response = client.get(f"/orchestrate/observability/traces/discovery/{strong_idea_id}")
    assert idea_trace_response.status_code == 200
    idea_trace = idea_trace_response.json()
    kinds = {item["trace_kind"] for item in idea_trace["steps"]}
    assert {"evidence", "validation", "simulation", "swipe"}.issubset(kinds)

    replay_response = client.get(f"/orchestrate/observability/debate-replay/sessions/{session_id}")
    assert replay_response.status_code == 200
    replay = replay_response.json()
    replay_kinds = {item["kind"] for item in replay["timeline"]}
    assert {"session_event", "checkpoint", "protocol_transition", "generation_artifact"}.issubset(replay_kinds)
    assert replay["invalid_transition_count"] == 1

    explainability_response = client.get(f"/orchestrate/discovery/ideas/{strong_idea_id}/explainability")
    assert explainability_response.status_code == 200
    explainability = explainability_response.json()
    assert "rank score" in explainability["ranking_summary"].lower()
    assert len(explainability["evidence_changes"]) >= 1
    assert "simulation" in explainability["simulation_summary"].lower() or explainability["simulation_summary"]

    dossier_response = client.get(f"/orchestrate/discovery/ideas/{strong_idea_id}/dossier")
    assert dossier_response.status_code == 200
    dossier = dossier_response.json()
    assert dossier["explainability_context"]["idea_id"] == strong_idea_id
    assert len(dossier["explainability_context"]["ranking_drivers"]) >= 1
