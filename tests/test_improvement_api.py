"""Regression coverage for the Q18 prompt-improvement lab."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.improvement.prompt_evolution import clear_improvement_lab_cache
from orchestrator.models import AgentConfig, SessionStore


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _agent(role: str, provider: str = "codex") -> AgentConfig:
    return AgentConfig(role=role, provider=provider, system_prompt="", tools=[], workspace_paths=[])


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_improvement_lab_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_improvement_lab_cache()


def test_improvement_reflect_from_session_persists_failure_tags(isolated_store: SessionStore):
    session_id = isolated_store.create(
        "moa",
        "Generate startup directions from repo history.",
        [
            _agent("proposer_market", "claude"),
            _agent("proposer_builder", "codex"),
            _agent("aggregator_operator", "gemini"),
            _agent("aggregator_editor", "claude"),
            _agent("final_synthesizer", "codex"),
        ],
        {
            "generation_trace": {
                "layer1_outputs": [
                    {
                        "artifact_id": "moa_artifact_1",
                        "layer": "layer1",
                        "agent_role": "proposer_market",
                        "provider": "claude",
                        "candidate_id": "proposal_1",
                        "content": "Generic AI platform for every founder with lots of automation.",
                        "summary": "Generic AI platform",
                        "metadata": {},
                        "generated_at": 0.0,
                    }
                ],
                "judge_scores": [
                    {
                        "judge_role": "judge_pack",
                        "candidate_id": "aggregate_1",
                        "overall_score": 9.1,
                        "criteria": {"problem_sharpness": 6},
                        "rationale": "Strong polish, but unsupported claims remain and evidence is thin.",
                    }
                ],
                "final_artifact": {
                    "artifact_id": "moa_artifact_final",
                    "layer": "final",
                    "agent_role": "final_synthesizer",
                    "provider": "codex",
                    "candidate_id": "aggregate_1",
                    "content": "Broad AI platform direction with no named buyer or clear channel.",
                    "summary": "Broad platform",
                    "metadata": {},
                    "generated_at": 0.0,
                },
            }
        },
    )
    isolated_store.update(
        session_id,
        status="completed",
        messages=[
            {
                "agent_id": "judge_pack",
                "phase": "judge",
                "content": "Unsupported claims were discounted, but the memo still lacks evidence and a concrete ICP.",
            }
        ],
    )

    response = client.post(
        "/orchestrate/improvement/reflect",
        json={"session_id": session_id, "source_kind": "session"},
    )

    assert response.status_code == 200
    payload = response.json()["reflection"]
    assert payload["source_id"] == session_id
    assert "genericity" in payload["failure_tags"]
    assert "evidence_gaps" in payload["failure_tags"]
    assert payload["signals"]

    listed = client.get("/orchestrate/improvement/reflections").json()["items"]
    assert listed[0]["reflection_id"] == payload["reflection_id"]


def test_improvement_self_play_prefers_evidence_hardliner_for_evidence_pressure():
    reflection = client.post(
        "/orchestrate/improvement/reflect",
        json={
            "task": "Harden judge behavior against unsupported claims.",
            "source_kind": "manual",
            "role_focus": ["judge"],
            "failure_tags": ["evidence_gaps", "judge_leniency"],
            "notes": ["Judges still score high when claims are not evidenced."],
        },
    ).json()["reflection"]

    response = client.post(
        "/orchestrate/improvement/self-play",
        json={
            "left_profile_id": "improv_evidence_hardliner",
            "right_profile_id": "improv_founder_rigor",
            "reflection_ids": [reflection["reflection_id"]],
            "task": "Judge founder-facing idea memos strictly.",
            "role_focus": ["judge"],
            "challenge_count": 1,
        },
    )

    assert response.status_code == 200
    match = response.json()["match"]
    assert match["winner_profile_id"] == "improv_evidence_hardliner"
    assert len(match["case_results"]) == 1


def test_improvement_evolution_generates_mutants_and_can_activate_best():
    reflection = client.post(
        "/orchestrate/improvement/reflect",
        json={
            "task": "Reduce overbuilt platform drift.",
            "source_kind": "manual",
            "failure_tags": ["overbuild", "risk_blindness"],
            "role_focus": ["generator", "critic"],
            "notes": ["The current prompts drift into platform ambition without a thin MVP slice."],
        },
    ).json()["reflection"]

    response = client.post(
        "/orchestrate/improvement/evolve",
        json={
            "seed_profile_id": "improv_founder_rigor",
            "reflection_ids": [reflection["reflection_id"]],
            "mutation_budget": 2,
            "challenge_count": 2,
            "activate_best": True,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["seed_profile"]["profile_id"] == "improv_founder_rigor"
    assert len(result["generated_profiles"]) == 2
    assert result["activated_profile_id"]
    assert all(profile["metadata"]["parent_profile_id"] == "improv_founder_rigor" for profile in result["generated_profiles"])

    profiles = client.get("/orchestrate/improvement/prompt-profiles").json()["items"]
    assert any(profile["metadata"].get("active") for profile in profiles)


def test_run_injects_active_improvement_profile_into_moa_sessions():
    with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_improve")) as mock_run:
        response = client.post(
            "/orchestrate/run",
            json={
                "mode": "moa",
                "task": "Generate founder-calibrated startup directions.",
                "agents": [
                    {"role": "proposer_market", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": []},
                    {"role": "proposer_builder", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": []},
                    {"role": "aggregator_operator", "provider": "gemini", "system_prompt": "", "tools": [], "workspace_paths": []},
                    {"role": "aggregator_editor", "provider": "claude", "system_prompt": "", "tools": [], "workspace_paths": []},
                    {"role": "final_synthesizer", "provider": "codex", "system_prompt": "", "tools": [], "workspace_paths": []},
                ],
                "config": {},
            },
        )

    assert response.status_code == 200
    run_config = mock_run.await_args.kwargs["config"]
    assert run_config["prompt_profile_id"] == "improv_founder_rigor"
    assert run_config["prompt_profile_label"] == "Founder rigor"
    assert "generator_prefix" in run_config["prompt_profile_overrides"]
