"""Regression coverage for Mixture-of-Agents layered generation."""

import asyncio
import time

import orchestrator.generation.moa as moa


def _agents() -> list[dict]:
    return [
        {"role": "proposer_market", "provider": "claude", "system_prompt": "", "tools": []},
        {"role": "proposer_builder", "provider": "codex", "system_prompt": "", "tools": []},
        {"role": "aggregator_operator", "provider": "gemini", "system_prompt": "", "tools": []},
        {"role": "aggregator_editor", "provider": "claude", "system_prompt": "", "tools": []},
        {"role": "final_synthesizer", "provider": "codex", "system_prompt": "", "tools": []},
    ]


def _base_state() -> dict:
    return {
        "task": "Generate strong startup directions from the founder's local repos.",
        "agents": _agents(),
        "messages": [],
        "user_messages": [],
        "config": {"aggregator_count": 2},
        "layer1_outputs": [],
        "layer2_outputs": [],
        "judge_scores": [],
        "trace_artifacts": [],
        "selected_candidate_id": "",
        "result": "",
    }


def test_generate_layer_one_runs_proposers_concurrently(monkeypatch):
    def slow_call(agent: dict, prompt: str) -> str:
        time.sleep(0.2)
        return f"{agent['role']} proposal"

    monkeypatch.setattr(moa, "call_agent_cfg", slow_call)

    started = time.perf_counter()
    result = asyncio.run(moa.generate_layer_one(_base_state()))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.35
    assert len(result["layer1_outputs"]) == 2
    assert result["layer1_outputs"][0]["candidate_id"] == "proposal_1"
    assert result["config"]["generation_trace"]["layer1_outputs"][1]["candidate_id"] == "proposal_2"
    assert result["config"]["generation_trace"]["novelty_context"]["noise_seeds"]
    assert "novelty_assessment" in result["layer1_outputs"][0]["metadata"]


def test_moa_pipeline_scores_candidates_and_selects_winner(monkeypatch):
    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        role = agent["role"]
        if "judge pack" in prompt.lower():
            return (
                '{"winner_candidate_id":"aggregate_2","summary":"aggregate_2 is stronger",'
                '"scores":['
                '{"candidate_id":"aggregate_1","overall_score":6.5,"criteria":{"problem_sharpness":6},"rationale":"too generic"},'
                '{"candidate_id":"aggregate_2","overall_score":9.1,"criteria":{"problem_sharpness":9},"rationale":"more concrete"}'
                "]}"
            )
        if role.startswith("proposer"):
            return f"{role} candidate"
        if role == "aggregator_operator":
            return "Operator aggregate candidate"
        if role == "aggregator_editor":
            return "Editor aggregate candidate"
        if role == "final_synthesizer":
            return "Final MoA synthesis"
        raise AssertionError(f"Unexpected agent call: {role}")

    monkeypatch.setattr(moa, "call_agent_cfg", fake_call_agent_cfg)

    state = _base_state()
    layer1 = asyncio.run(moa.generate_layer_one(state))
    layer2 = asyncio.run(moa.aggregate_layer_two({**state, **layer1}))
    judged = asyncio.run(moa.judge_layer_two({**state, **layer1, **layer2}))
    final = moa.finalize_generation({**state, **layer1, **layer2, **judged})

    assert len(layer2["layer2_outputs"]) == 2
    assert len(judged["judge_scores"]) == 8
    assert final["selected_candidate_id"] == "aggregate_2"
    assert final["result"] == "Final MoA synthesis"
    assert final["config"]["generation_trace"]["selected_candidate_id"] == "aggregate_2"
    assert final["config"]["generation_trace"]["final_artifact"]["layer"] == "final"
    assert final["config"]["generation_trace"]["novelty_context"]["trisociation_blends"]


def test_moa_selection_penalizes_banal_candidates():
    winner, leaderboard = moa._select_best_candidate(
        [
            {
                "candidate_id": "aggregate_1",
                "metadata": {"novelty_assessment": {"penalty": 0.9, "banned": True}},
            },
            {
                "candidate_id": "aggregate_2",
                "metadata": {"novelty_assessment": {"penalty": 0.1, "banned": False}},
            },
        ],
        [
            {"candidate_id": "aggregate_1", "overall_score": 8.9, "judge_role": "judge_a"},
            {"candidate_id": "aggregate_2", "overall_score": 8.2, "judge_role": "judge_a"},
        ],
    )

    assert winner == "aggregate_2"
    assert leaderboard[0]["candidate_id"] == "aggregate_2"
    assert leaderboard[1]["novelty_blocked"] is True


def test_moa_prompts_include_improvement_profile_notes():
    state = _base_state()
    state["config"] = {
        "aggregator_count": 2,
        "prompt_profile_id": "improv_founder_rigor",
        "prompt_profile_label": "Founder rigor",
        "prompt_profile_overrides": {
            "generator_prefix": "Name one buyer and one wedge.",
            "judge_prefix": "Penalize unsupported claims.",
            "critic_prefix": "Surface one execution trap.",
            "tactics": ["buyer_clarity"],
        },
    }

    layer1_prompt = moa._layer1_prompt(state, _agents()[0], 0, 2)
    judge_prompt = moa._judge_prompt(
        state,
        _agents()[0],
        [{"candidate_id": "aggregate_1", "agent_role": "aggregator_operator", "provider": "gemini", "content": "Candidate", "metadata": {}}],
    )

    assert "IMPROVEMENT PROFILE (Founder rigor / generator)" in layer1_prompt
    assert "Name one buyer and one wedge." in layer1_prompt
    assert "IMPROVEMENT PROFILE (Founder rigor / judge)" in judge_prompt
