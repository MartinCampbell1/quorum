"""Regression coverage for the shared debate protocol layer."""

from orchestrator.debate.factcheck import validate_with_retry
from orchestrator.debate.judges import aggregate_panel_decisions, parse_judge_response
from orchestrator.debate.moderators import build_improvement_prompt_context
from orchestrator.debate.protocols import list_protocols, resolve_protocol_for_mode
import orchestrator.modes.democracy as democracy


def test_protocol_registry_exposes_expected_q05_protocols():
    protocol_names = {item.name for item in list_protocols()}
    assert {
        "standard_debate",
        "dag_debate",
        "crossfire",
        "panel_judging",
        "creator_critic",
        "council_vote",
    } <= protocol_names

    assert resolve_protocol_for_mode("debate", {}).name == "standard_debate"
    assert resolve_protocol_for_mode("tournament", {}).name == "panel_judging"
    assert resolve_protocol_for_mode("board", {}).name == "council_vote"


def test_factcheck_gate_uses_retry_then_disqualify():
    outcome = validate_with_retry(
        response="Studies show a 91% win rate and guarantee demand.",
        responder=lambda note: "Research proves 87% of founders buy immediately.",
    )

    assert outcome.retried is True
    assert outcome.disqualified is True
    assert outcome.report.ok is False
    assert "Disqualified after retry" in outcome.disqualification_note


def test_panel_judging_aggregates_dissent_instead_of_hiding_it():
    left = parse_judge_response(
        "FINAL_VERDICT: A\nWinner: A because the repo evidence is more concrete.\nConfidence: 0.81",
        protocol_name="panel_judging",
        final_marker="FINAL_VERDICT",
        continue_marker="NEED_MORE_ROUNDS",
        allowed_winners=("A", "B"),
    )
    right = parse_judge_response(
        "FINAL_VERDICT: B\nWinner: B because the monetization path is shorter.\nConfidence: 0.72",
        protocol_name="panel_judging",
        final_marker="FINAL_VERDICT",
        continue_marker="NEED_MORE_ROUNDS",
        allowed_winners=("A", "B"),
    )
    tie_break = parse_judge_response(
        "FINAL_VERDICT: A\nWinner: A because the evidence is stronger.\nConfidence: 0.77",
        protocol_name="panel_judging",
        final_marker="FINAL_VERDICT",
        continue_marker="NEED_MORE_ROUNDS",
        allowed_winners=("A", "B"),
    )

    panel = aggregate_panel_decisions([left, right, tie_break])

    assert panel.action == "final"
    assert panel.winner_token == "A"
    assert panel.dissent > 0
    assert 0.7 < panel.confidence < 0.8


def test_parse_judge_response_extracts_founder_scorecard():
    decision = parse_judge_response(
        (
            "FINAL_VERDICT: A\n"
            "A wins because the buyer and distribution wedge are clearer.\n"
            '{"action":"final","winner_token":"A","confidence":0.82,"rationale":"A is sharper.",'
            '"scorecard":{"problem_sharpness":9,"icp_clarity":8,"distribution_plausibility":8,'
            '"moat":6,"buildability":7,"ai_necessity":8,"evidence_quality":7,"risk_profile":6}}'
        ),
        protocol_name="panel_judging",
        final_marker="FINAL_VERDICT",
        continue_marker="NEED_MORE_ROUNDS",
        allowed_winners=("A", "B"),
    )

    assert decision.action == "final"
    assert decision.scorecard["problem_sharpness"] == 9.0
    assert decision.scorecard["ai_necessity"] == 8.0

    panel = aggregate_panel_decisions([decision, decision])
    assert panel.scorecard["distribution_plausibility"] == 8.0


def test_democracy_unanimous_majority_triggers_scrutiny():
    state = {
        "task": "Choose the launch direction",
        "agents": [],
        "messages": [],
        "user_messages": [],
        "config": {},
        "votes": [
            {"agent_id": "a", "position": "Sell the repo diagnostic first", "reasoning": "Fastest path to revenue with existing stack."},
            {"agent_id": "b", "position": "Sell the repo diagnostic first", "reasoning": "Evidence from prior projects points to workflow pain."},
            {"agent_id": "c", "position": "Sell the repo diagnostic first", "reasoning": "Lower distribution risk than a broad platform bet."},
        ],
        "round": 1,
        "max_rounds": 2,
        "majority_position": "",
        "majority_candidate": "",
        "result": "",
    }

    tallied = democracy.tally_votes(state)

    assert tallied["majority_position"] == ""
    assert tallied["scrutiny_requested"] is True
    scrutinized = democracy.scrutinize_majority({**state, **tallied})
    assert scrutinized["majority_position"] == "Sell the repo diagnostic first"


def test_build_improvement_prompt_context_renders_profile_notes():
    context = build_improvement_prompt_context(
        {
            "prompt_profile_id": "improv_founder_rigor",
            "prompt_profile_label": "Founder rigor",
            "prompt_profile_overrides": {"judge_prefix": "Discount unsupported claims aggressively."},
        },
        "judge",
    )

    assert "IMPROVEMENT PROFILE (Founder rigor / judge)" in context
    assert "Discount unsupported claims aggressively." in context
