"""Regression coverage for protocol blueprints, cache reuse, and shadow validation."""

from orchestrator.debate.blueprints import TERMINAL_NODE_ID
from orchestrator.models import AgentConfig, SessionStore
from orchestrator.topology.protocol_compiler import compile_protocol_blueprint, shadow_validate_transition


def _agent(role: str, provider: str = "claude") -> AgentConfig:
    return AgentConfig(role=role, provider=provider, tools=[])


def test_compile_protocol_blueprint_for_debate_mode():
    blueprint = compile_protocol_blueprint(
        "debate",
        [_agent("proponent"), _agent("opponent", "codex"), _agent("judge", "gemini")],
        {"max_rounds": 3},
        task="Debate whether Quorum should prioritize repo-derived discovery first.",
    )

    assert blueprint.mode == "debate"
    assert blueprint.mode_family == "debate"
    assert blueprint.protocol_key == "standard_debate"
    assert blueprint.entry_node_id == "proponent_argues"
    assert blueprint.cache_key.startswith("pb_")
    assert any(
        guard.source_node_id == "judge_decides" and guard.target_node_id == TERMINAL_NODE_ID
        for guard in blueprint.transitions
    )


def test_compile_protocol_blueprint_for_moa_mode():
    blueprint = compile_protocol_blueprint(
        "moa",
        [
            _agent("proposer_market"),
            _agent("proposer_builder", "codex"),
            _agent("aggregator_operator", "gemini"),
            _agent("aggregator_editor"),
            _agent("final_synthesizer", "codex"),
        ],
        {"aggregator_count": 2},
        task="Generate breadth-first startup directions from founder repo history.",
    )

    assert blueprint.mode == "moa"
    assert blueprint.mode_family == "generation"
    assert blueprint.entry_node_id == "generate_layer_one"
    assert any(
        guard.source_node_id == "finalize_generation" and guard.target_node_id == TERMINAL_NODE_ID
        for guard in blueprint.transitions
    )


def test_shadow_validation_rejects_transition_outside_creator_critic_blueprint():
    blueprint = compile_protocol_blueprint(
        "creator_critic",
        [_agent("creator", "codex"), _agent("critic")],
        {"max_iterations": 2},
        task="Refine a discovery memo.",
    )

    valid = shadow_validate_transition(
        blueprint,
        "creator_produces",
        "critic_evaluates",
        {
            "versions": ["Draft v1"],
            "messages": [{"agent_id": "creator", "content": "Draft v1"}],
            "protocol_name": "creator_critic",
        },
    )
    invalid = shadow_validate_transition(
        blueprint,
        "creator_produces",
        "final_version",
        {
            "versions": ["Draft v1"],
            "messages": [{"agent_id": "creator", "content": "Draft v1"}],
            "protocol_name": "creator_critic",
        },
    )

    assert valid.ok is True
    assert invalid.ok is False
    assert any("not part of blueprint" in error for error in invalid.errors)


def test_session_store_caches_protocol_blueprints(tmp_path):
    db = SessionStore(db_path=str(tmp_path / "state.db"))
    blueprint = compile_protocol_blueprint(
        "tournament",
        [
            _agent("contestant_1"),
            _agent("contestant_2", "codex"),
            _agent("judge", "gemini"),
        ],
        {"execution_mode": "parallel", "max_rounds": 2},
        task="Rank discovery opportunities.",
    )

    db.put_cached_protocol_blueprint(blueprint.cache_key, blueprint.model_dump())
    cached = db.get_cached_protocol_blueprint(blueprint.cache_key)

    assert cached is not None
    assert cached["cache_key"] == blueprint.cache_key
    assert cached["entry_node_id"] == "seed_contestants"
