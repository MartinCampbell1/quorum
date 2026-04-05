"""Compile reusable bounded protocol blueprints for Quorum workflows."""

from __future__ import annotations

from typing import Any

from orchestrator.debate.blueprints import (
    FieldType,
    GuardPredicate,
    OutputFieldSpec,
    ProtocolBlueprint,
    ShadowValidationResult,
    StateNode,
    TERMINAL_NODE_ID,
    TransitionGuard,
    stable_payload_hash,
)
from orchestrator.debate.protocols import resolve_protocol_for_mode


def _output(name: str, field_type: FieldType, required: bool = True, description: str = "") -> OutputFieldSpec:
    return OutputFieldSpec(name=name, field_type=field_type, required=required, description=description)


def _predicate(field: str, operator: str, value: Any = None) -> GuardPredicate:
    return GuardPredicate(field=field, operator=operator, value=value)


def _guard(
    source_node_id: str,
    target_node_id: str,
    description: str = "",
    predicates: list[GuardPredicate] | None = None,
    predicate_match: str = "all",
) -> TransitionGuard:
    return TransitionGuard(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        description=description,
        predicates=list(predicates or []),
        predicate_match=predicate_match,
    )


def _node(
    node_id: str,
    label: str,
    stage: str,
    purpose: str,
    *,
    role_hints: list[str] | None = None,
    allowed_outputs: list[str] | None = None,
    output_schema: list[OutputFieldSpec] | None = None,
    state_reads: list[str] | None = None,
    state_writes: list[str] | None = None,
) -> StateNode:
    return StateNode(
        node_id=node_id,
        label=label,
        stage=stage,
        purpose=purpose,
        role_hints=list(role_hints or []),
        allowed_outputs=list(allowed_outputs or []),
        output_schema=list(output_schema or []),
        state_reads=list(state_reads or []),
        state_writes=list(state_writes or []),
    )


def _agent_role(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("role", "agent") or "agent")
    return str(getattr(agent, "role", "agent") or "agent")


def _agent_roles(agents: list[Any]) -> list[str]:
    return [role for role in (_agent_role(agent).strip() for agent in agents) if role]


def _resolve_protocol_key(mode: str, config: dict[str, Any]) -> str:
    if mode in {"board", "creator_critic", "debate", "democracy", "tournament", "tournament_match"}:
        return resolve_protocol_for_mode(mode, config).name
    return str(config.get("protocol_family") or mode or "workflow").strip().lower()


def _dictator_template() -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "director_plan",
            "Director Plans",
            "planning",
            "Break the task into worker-safe subtasks.",
            role_hints=["director"],
            allowed_outputs=["subtasks", "messages"],
            output_schema=[_output("subtasks", "array"), _output("messages", "array")],
            state_reads=["task", "agents"],
            state_writes=["subtasks", "messages"],
        ),
        _node(
            "workers_execute",
            "Workers Execute",
            "execution",
            "Workers run delegated subtasks within the bounded plan.",
            role_hints=["worker_1", "worker_2"],
            allowed_outputs=["worker_results", "messages"],
            output_schema=[_output("worker_results", "array"), _output("messages", "array")],
            state_reads=["subtasks", "task"],
            state_writes=["worker_results", "messages"],
        ),
        _node(
            "director_synthesize",
            "Director Synthesizes",
            "synthesis",
            "Review worker outputs and either finalize or request another bounded loop.",
            role_hints=["director"],
            allowed_outputs=["result", "iteration", "messages"],
            output_schema=[_output("result", "string"), _output("iteration", "integer"), _output("messages", "array")],
            state_reads=["worker_results", "iteration", "max_iterations"],
            state_writes=["result", "iteration", "messages"],
        ),
    ]
    transitions = [
        _guard("director_plan", "workers_execute", "Delegated subtasks fan out to workers."),
        _guard("workers_execute", "director_synthesize", "Worker results return to the director."),
        _guard(
            "director_synthesize",
            "director_plan",
            "Another planning loop is allowed only when the director explicitly asks for more work.",
            predicates=[
                _predicate("result", "contains", "NEEDS_MORE_WORK"),
                _predicate("iteration", "lt", {"field": "max_iterations"}),
            ],
        ),
        _guard("director_synthesize", TERMINAL_NODE_ID, "Synthesis can end the run when work is sufficient."),
    ]
    notes = [
        "Bounded delegate/execute/synthesize loop mirrors the existing LangGraph mode.",
        "Shadow validation keeps the loop auditable without blocking execution.",
    ]
    return "workflow", "workflow.dictator.delegate", "director_plan", nodes, transitions, notes


def _map_reduce_template() -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "plan_chunks",
            "Plan Chunks",
            "planning",
            "Split the task into bounded chunk work.",
            role_hints=["planner"],
            allowed_outputs=["chunks", "messages"],
            output_schema=[_output("chunks", "array"), _output("messages", "array")],
            state_reads=["task", "agents"],
            state_writes=["chunks", "messages"],
        ),
        _node(
            "process_chunks",
            "Process Chunks",
            "execution",
            "Run chunk work in parallel but keep output shape bounded.",
            role_hints=["worker_1", "worker_2"],
            allowed_outputs=["chunk_results", "messages"],
            output_schema=[_output("chunk_results", "array"), _output("messages", "array")],
            state_reads=["chunks", "task"],
            state_writes=["chunk_results", "messages"],
        ),
        _node(
            "synthesize",
            "Synthesize",
            "synthesis",
            "Collapse chunk results into the final answer.",
            role_hints=["synthesizer"],
            allowed_outputs=["synthesis", "result", "messages"],
            output_schema=[_output("synthesis", "string"), _output("result", "string"), _output("messages", "array")],
            state_reads=["chunk_results", "task"],
            state_writes=["synthesis", "result", "messages"],
        ),
    ]
    transitions = [
        _guard("plan_chunks", "process_chunks", "Planned chunks flow into chunk execution."),
        _guard("process_chunks", "synthesize", "Chunk execution converges into a single synthesizer."),
        _guard("synthesize", TERMINAL_NODE_ID, "Synthesis always resolves the mode."),
    ]
    return "workflow", "workflow.map_reduce", "plan_chunks", nodes, transitions, ["Explicit linear chunk pipeline."]


def _moa_template() -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "generate_layer_one",
            "Generate Layer One",
            "generation",
            "Run multiple proposers in parallel to create diverse first-pass candidates.",
            role_hints=["proposer_market", "proposer_builder"],
            allowed_outputs=["layer1_outputs", "trace_artifacts", "messages"],
            output_schema=[
                _output("layer1_outputs", "array"),
                _output("trace_artifacts", "array"),
                _output("messages", "array"),
            ],
            state_reads=["task", "agents", "config"],
            state_writes=["layer1_outputs", "trace_artifacts", "messages", "config"],
        ),
        _node(
            "aggregate_layer_two",
            "Aggregate Layer Two",
            "aggregation",
            "Aggregators inspect all layer-1 outputs and produce stronger candidate syntheses.",
            role_hints=["aggregator_operator", "aggregator_editor"],
            allowed_outputs=["layer2_outputs", "trace_artifacts", "messages"],
            output_schema=[
                _output("layer2_outputs", "array"),
                _output("trace_artifacts", "array"),
                _output("messages", "array"),
            ],
            state_reads=["layer1_outputs", "config"],
            state_writes=["layer2_outputs", "trace_artifacts", "messages", "config"],
        ),
        _node(
            "judge_layer_two",
            "Judge Layer Two",
            "evaluation",
            "A judge pack scores the aggregated candidates before final synthesis.",
            role_hints=["proposer_market", "aggregator_operator"],
            allowed_outputs=["judge_scores", "messages"],
            output_schema=[
                _output("judge_scores", "array"),
                _output("messages", "array"),
            ],
            state_reads=["layer2_outputs", "config"],
            state_writes=["judge_scores", "messages", "config"],
        ),
        _node(
            "finalize_generation",
            "Finalize Generation",
            "synthesis",
            "Use judge-pack signals to select the strongest candidate and produce the final answer.",
            role_hints=["final_synthesizer"],
            allowed_outputs=["selected_candidate_id", "result", "trace_artifacts", "messages"],
            output_schema=[
                _output("selected_candidate_id", "string"),
                _output("result", "string"),
                _output("trace_artifacts", "array"),
                _output("messages", "array"),
            ],
            state_reads=["layer1_outputs", "layer2_outputs", "judge_scores", "config"],
            state_writes=["selected_candidate_id", "result", "trace_artifacts", "messages", "config"],
        ),
    ]
    transitions = [
        _guard("generate_layer_one", "aggregate_layer_two", "Layer-1 proposals fan into the aggregation layer."),
        _guard("aggregate_layer_two", "judge_layer_two", "Aggregated candidates move into judge-pack scoring."),
        _guard("judge_layer_two", "finalize_generation", "Judge-pack signals flow into the final synthesizer."),
        _guard("finalize_generation", TERMINAL_NODE_ID, "The final synthesis resolves the layered generation run."),
    ]
    notes = [
        "Layered generation separates breadth creation from later stress testing.",
        "Per-layer artifacts remain replayable through the shared blueprint and trace system.",
    ]
    return "generation", "generation.moa.layered", "generate_layer_one", nodes, transitions, notes


def _debate_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "proponent_argues",
            "Proponent Argues",
            "argument",
            "Produce the opening or iterative supporting argument.",
            role_hints=["proponent"],
            allowed_outputs=["messages", "rounds", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[
                _output("messages", "array"),
                _output("rounds", "array"),
                _output("protocol_name", "string"),
            ],
            state_reads=["task", "current_round", "rounds", "max_rounds"],
            state_writes=["messages", "rounds", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "opponent_argues",
            "Opponent Argues",
            "argument",
            "Stress-test the current thesis with an opposing argument.",
            role_hints=["opponent"],
            allowed_outputs=["messages", "rounds", "current_round", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[
                _output("messages", "array"),
                _output("rounds", "array"),
                _output("current_round", "integer"),
                _output("protocol_name", "string"),
            ],
            state_reads=["task", "current_round", "rounds", "max_rounds"],
            state_writes=["messages", "rounds", "current_round", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "judge_decides",
            "Judge Decides",
            "judging",
            "Judge whether the debate needs another bounded round or can conclude.",
            role_hints=["judge"],
            allowed_outputs=["result", "verdict", "judge_action", "protocol_telemetry", "protocol_name"],
            output_schema=[
                _output("result", "string"),
                _output("verdict", "string"),
                _output("judge_action", "string"),
                _output("protocol_telemetry", "object"),
                _output("protocol_name", "string"),
            ],
            state_reads=["rounds", "current_round", "max_rounds"],
            state_writes=["result", "verdict", "judge_action", "protocol_telemetry", "protocol_name"],
        ),
    ]
    transitions = [
        _guard("proponent_argues", "opponent_argues", "The opponent can respond only after the proposer speaks."),
        _guard("opponent_argues", "judge_decides", "Both sides must speak before the judge decides."),
        _guard(
            "judge_decides",
            "proponent_argues",
            "Another round is allowed only when the judge requests continuation within the max round cap.",
            predicates=[
                _predicate("judge_action", "eq", "continue"),
                _predicate("current_round", "lt", {"field": "max_rounds"}),
            ],
        ),
        _guard("judge_decides", TERMINAL_NODE_ID, "The debate can terminate after a final verdict."),
    ]
    notes = [
        f"Compiled from the {protocol_key} debate protocol.",
        "This blueprint keeps pro/con/judge steps explicit so follower models can stay inside the allowed topology.",
    ]
    return "debate", f"debate.protocol.{protocol_key}", "proponent_argues", nodes, transitions, notes


def _creator_critic_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "creator_produces",
            "Creator Produces",
            "generation",
            "Produce the next candidate version.",
            role_hints=["creator"],
            allowed_outputs=["versions", "messages", "protocol_name"],
            output_schema=[_output("versions", "array"), _output("messages", "array"), _output("protocol_name", "string")],
            state_reads=["task", "iteration", "critiques"],
            state_writes=["versions", "messages", "protocol_name"],
        ),
        _node(
            "critic_evaluates",
            "Critic Evaluates",
            "critique",
            "Evaluate the latest version and decide whether to continue or stop.",
            role_hints=["critic"],
            allowed_outputs=["critiques", "iteration", "approved", "protocol_name", "protocol_telemetry", "result", "messages"],
            output_schema=[
                _output("critiques", "array"),
                _output("iteration", "integer"),
                _output("approved", "boolean"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["versions", "iteration", "max_iterations"],
            state_writes=["critiques", "iteration", "approved", "protocol_name", "protocol_telemetry", "result", "messages"],
        ),
        _node(
            "final_version",
            "Final Version",
            "finalize",
            "Emit the bounded fallback version once the critique budget is exhausted.",
            role_hints=["system"],
            allowed_outputs=["result", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("result", "string"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["versions", "iteration", "max_iterations"],
            state_writes=["result", "protocol_name", "protocol_telemetry", "messages"],
        ),
    ]
    transitions = [
        _guard("creator_produces", "critic_evaluates", "Every new version must be critiqued."),
        _guard(
            "critic_evaluates",
            "creator_produces",
            "Loop back only while the work is not approved and the iteration budget remains.",
            predicates=[
                _predicate("approved", "falsy"),
                _predicate("iteration", "lt", {"field": "max_iterations"}),
            ],
        ),
        _guard(
            "critic_evaluates",
            "final_version",
            "Fallback finalization is allowed when approval is still missing after the iteration budget is exhausted.",
            predicates=[
                _predicate("approved", "falsy"),
                _predicate("iteration", "gte", {"field": "max_iterations"}),
            ],
        ),
        _guard(
            "critic_evaluates",
            TERMINAL_NODE_ID,
            "The critique loop can end immediately when the work is approved.",
            predicates=[_predicate("approved", "truthy")],
        ),
        _guard("final_version", TERMINAL_NODE_ID, "Final fallback version ends the loop."),
    ]
    return "debate", f"debate.creator_critic.{protocol_key}", "creator_produces", nodes, transitions, ["Bounded creator/critic refinement loop."]


def _board_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "directors_analyze",
            "Directors Analyze",
            "deliberation",
            "Collect board positions as bounded JSON recommendations.",
            role_hints=["director_1", "director_2", "director_3"],
            allowed_outputs=["positions", "vote_round", "messages"],
            output_schema=[_output("positions", "array"), _output("vote_round", "integer"), _output("messages", "array")],
            state_reads=["task", "vote_round", "max_rounds"],
            state_writes=["positions", "vote_round", "messages"],
        ),
        _node(
            "check_consensus",
            "Check Consensus",
            "consensus",
            "Check for consensus or route to scrutiny / chairman / another board round.",
            role_hints=["system"],
            allowed_outputs=["consensus_reached", "decision", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("consensus_reached", "boolean"),
                _output("decision", "string"),
                _output("scrutiny_requested", "boolean"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["positions", "vote_round", "max_rounds"],
            state_writes=["consensus_reached", "decision", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "scrutinize_consensus",
            "Scrutinize Consensus",
            "scrutiny",
            "Stress-test unanimous consensus before worker handoff or finalization.",
            role_hints=["system"],
            allowed_outputs=["scrutiny_requested", "scrutiny_passed", "consensus_reached", "decision", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("scrutiny_requested", "boolean"),
                _output("consensus_reached", "boolean"),
                _output("decision", "string"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["positions", "vote_round", "max_rounds"],
            state_writes=["scrutiny_requested", "scrutiny_passed", "consensus_reached", "decision", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "chairman_decides",
            "Chairman Decides",
            "tie_break",
            "The chairman resolves deadlock once the board round budget is exhausted.",
            role_hints=["director_1"],
            allowed_outputs=["decision", "messages"],
            output_schema=[_output("decision", "string"), _output("messages", "array")],
            state_reads=["positions", "vote_round", "max_rounds"],
            state_writes=["decision", "messages"],
        ),
        _node(
            "delegate_to_workers",
            "Delegate To Workers",
            "handoff",
            "Turn the board decision into bounded worker execution.",
            role_hints=["worker"],
            allowed_outputs=["worker_results", "messages"],
            output_schema=[_output("worker_results", "array"), _output("messages", "array")],
            state_reads=["decision", "agents"],
            state_writes=["worker_results", "messages"],
        ),
        _node(
            "finalize",
            "Finalize",
            "finalize",
            "Emit the final board outcome or combined worker execution output.",
            role_hints=["system"],
            allowed_outputs=["result", "messages"],
            output_schema=[_output("result", "string"), _output("messages", "array")],
            state_reads=["decision", "worker_results"],
            state_writes=["result", "messages"],
        ),
    ]
    transitions = [
        _guard("directors_analyze", "check_consensus", "Board positions move into the consensus step."),
        _guard("check_consensus", "scrutinize_consensus", "Unanimous consensus is routed into scrutiny when required.", predicates=[_predicate("scrutiny_requested", "truthy")]),
        _guard("check_consensus", "delegate_to_workers", "Consensus can hand off to workers when extra agents are available."),
        _guard("check_consensus", "finalize", "Consensus can finalize directly when no worker handoff is needed."),
        _guard("check_consensus", "chairman_decides", "Deadlock escalates to the chairman after the round cap."),
        _guard("check_consensus", "directors_analyze", "Otherwise the board enters another deliberation round."),
        _guard("scrutinize_consensus", "delegate_to_workers", "Scrutiny can still permit worker handoff."),
        _guard("scrutinize_consensus", "finalize", "Scrutiny can finalize directly."),
        _guard("scrutinize_consensus", "chairman_decides", "Failed scrutiny can still escalate to the chairman."),
        _guard("scrutinize_consensus", "directors_analyze", "Failed scrutiny can send the board back for another round."),
        _guard("chairman_decides", "delegate_to_workers", "The chairman's decision becomes the worker handoff."),
        _guard("delegate_to_workers", "finalize", "Worker execution always converges into finalization."),
        _guard("finalize", TERMINAL_NODE_ID, "Finalization ends the run."),
    ]
    return "handoff", f"handoff.board.{protocol_key}", "directors_analyze", nodes, transitions, ["Consensus and scrutiny are compiled into explicit handoff states."]


def _democracy_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "collect_votes",
            "Collect Votes",
            "deliberation",
            "Collect bounded votes from each voter.",
            role_hints=["voter"],
            allowed_outputs=["votes", "round", "messages", "protocol_name"],
            output_schema=[
                _output("votes", "array"),
                _output("round", "integer"),
                _output("messages", "array"),
                _output("protocol_name", "string"),
            ],
            state_reads=["task", "round", "max_rounds"],
            state_writes=["votes", "round", "messages", "protocol_name"],
        ),
        _node(
            "tally_votes",
            "Tally Votes",
            "consensus",
            "Resolve majority, possible scrutiny, or decide whether another round is needed.",
            role_hints=["system"],
            allowed_outputs=["majority_position", "majority_candidate", "result", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("majority_position", "string"),
                _output("majority_candidate", "string"),
                _output("result", "string"),
                _output("scrutiny_requested", "boolean"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["votes", "round", "max_rounds"],
            state_writes=["majority_position", "majority_candidate", "result", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "scrutinize_majority",
            "Scrutinize Majority",
            "scrutiny",
            "Stress-test unanimous majority before finalization.",
            role_hints=["system"],
            allowed_outputs=["majority_position", "majority_candidate", "result", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("majority_position", "string"),
                _output("result", "string"),
                _output("scrutiny_requested", "boolean"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["votes", "round", "max_rounds"],
            state_writes=["majority_position", "result", "scrutiny_requested", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "force_decision",
            "Force Decision",
            "finalize",
            "Use deterministic fallback once the vote budget is exhausted.",
            role_hints=["system"],
            allowed_outputs=["majority_position", "result", "messages"],
            output_schema=[_output("majority_position", "string"), _output("result", "string"), _output("messages", "array")],
            state_reads=["votes", "round", "max_rounds"],
            state_writes=["majority_position", "result", "messages"],
        ),
    ]
    transitions = [
        _guard("collect_votes", "tally_votes", "Votes always flow into tallying."),
        _guard("tally_votes", "scrutinize_majority", "Unanimous outcomes route through scrutiny.", predicates=[_predicate("scrutiny_requested", "truthy")]),
        _guard("tally_votes", "collect_votes", "No majority means another voting round."),
        _guard("tally_votes", "force_decision", "The round budget can force a deterministic fallback."),
        _guard("tally_votes", TERMINAL_NODE_ID, "A majority can finalize immediately."),
        _guard("scrutinize_majority", "collect_votes", "Failed scrutiny can send the vote back for another round."),
        _guard("scrutinize_majority", "force_decision", "Failed scrutiny can still fall back to a forced decision."),
        _guard("scrutinize_majority", TERMINAL_NODE_ID, "Passed scrutiny finalizes the democracy run."),
        _guard("force_decision", TERMINAL_NODE_ID, "Forced decision always terminates the run."),
    ]
    return "handoff", f"handoff.democracy.{protocol_key}", "collect_votes", nodes, transitions, ["Democracy is compiled as collect/tally/scrutiny/fallback graph."]


def _tournament_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "seed_contestants",
            "Seed Contestants",
            "planning",
            "Build the initial bracket or ranking field from submissions.",
            role_hints=["contestant"],
            allowed_outputs=["submissions", "messages"],
            output_schema=[_output("submissions", "array"), _output("messages", "array")],
            state_reads=["agents"],
            state_writes=["submissions", "messages"],
        ),
        _node(
            "start_round",
            "Start Round",
            "routing",
            "Prepare the next round and decide whether to go parallel, sequential, or crown a champion.",
            role_hints=["system"],
            allowed_outputs=["bracket", "winners", "current_round", "current_match_index", "current_match_round", "current_match", "advance_target", "messages", "result"],
            output_schema=[
                _output("bracket", "array"),
                _output("winners", "array"),
                _output("current_round", "integer"),
                _output("advance_target", "string"),
                _output("messages", "array"),
            ],
            state_reads=["submissions", "winners", "config"],
            state_writes=["bracket", "winners", "current_round", "current_match_index", "current_match_round", "current_match", "advance_target", "messages", "result"],
        ),
        _node(
            "run_parallel_stage",
            "Run Parallel Stage",
            "ranking",
            "Execute a bounded batch of parallel matches and aggregate the winners.",
            role_hints=["judge", "contestant"],
            allowed_outputs=["winners", "match_history", "parallel_stage_children", "parallel_stage_group_id", "advance_target", "messages", "result"],
            output_schema=[
                _output("winners", "array"),
                _output("match_history", "array"),
                _output("advance_target", "string"),
                _output("messages", "array"),
            ],
            state_reads=["bracket", "current_round", "config"],
            state_writes=["winners", "match_history", "parallel_stage_children", "parallel_stage_group_id", "advance_target", "messages", "result"],
        ),
        _node(
            "contestant_a_argues",
            "Contestant A Argues",
            "argument",
            "Let contestant A make the first bounded case.",
            role_hints=["contestant_1"],
            allowed_outputs=["current_match", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[_output("current_match", "object"), _output("messages", "array"), _output("protocol_name", "string")],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "contestant_b_argues",
            "Contestant B Argues",
            "argument",
            "Let contestant B answer the current round.",
            role_hints=["contestant_2"],
            allowed_outputs=["current_match", "current_match_round", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[
                _output("current_match", "object"),
                _output("current_match_round", "integer"),
                _output("messages", "array"),
                _output("protocol_name", "string"),
            ],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "current_match_round", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "judge_match",
            "Judge Match",
            "judging",
            "Judge the current match or ask for another bounded round.",
            role_hints=["judge"],
            allowed_outputs=["current_match", "judge_action", "match_winner", "match_verdict", "result", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("current_match", "object"),
                _output("judge_action", "string"),
                _output("match_winner", "string"),
                _output("match_verdict", "string"),
                _output("result", "string"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "judge_action", "match_winner", "match_verdict", "result", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "advance_match",
            "Advance Match",
            "ranking",
            "Update bracket winners and decide the next ranking step.",
            role_hints=["system"],
            allowed_outputs=["winners", "match_history", "current_match_index", "current_match_round", "current_match", "advance_target", "messages", "result"],
            output_schema=[
                _output("winners", "array"),
                _output("match_history", "array"),
                _output("advance_target", "string"),
                _output("messages", "array"),
            ],
            state_reads=["current_match", "match_history", "winners"],
            state_writes=["winners", "match_history", "current_match_index", "current_match_round", "current_match", "advance_target", "messages", "result"],
        ),
        _node(
            "crown_champion",
            "Crown Champion",
            "finalize",
            "Emit the final ranking champion or winner.",
            role_hints=["system"],
            allowed_outputs=["champion", "result", "messages"],
            output_schema=[_output("champion", "object"), _output("result", "string"), _output("messages", "array")],
            state_reads=["winners", "submissions", "match_history"],
            state_writes=["champion", "result", "messages"],
        ),
    ]
    transitions = [
        _guard("seed_contestants", "start_round", "Seeding always leads into round setup."),
        _guard("start_round", "run_parallel_stage", "Parallel execution path for batch stages.", predicates=[_predicate("advance_target", "eq", "run_parallel_stage")]),
        _guard("start_round", "contestant_a_argues", "Sequential execution path starts the first argument.", predicates=[_predicate("advance_target", "eq", "contestant_a_argues")]),
        _guard("start_round", "crown_champion", "Single entrant shortcut crowns the champion.", predicates=[_predicate("advance_target", "eq", "crown_champion")]),
        _guard("run_parallel_stage", "start_round", "Parallel stages can advance into another round.", predicates=[_predicate("advance_target", "eq", "start_round")]),
        _guard("run_parallel_stage", "crown_champion", "Parallel stages can also finish the tournament.", predicates=[_predicate("advance_target", "eq", "crown_champion")]),
        _guard("contestant_a_argues", "contestant_b_argues", "Contestant B follows contestant A."),
        _guard("contestant_b_argues", "judge_match", "The judge can act only after both contestants speak."),
        _guard(
            "judge_match",
            "contestant_a_argues",
            "The judge can request another bounded round.",
            predicates=[_predicate("judge_action", "eq", "continue"), _predicate("current_match_round", "lt", {"field": "max_rounds"})],
        ),
        _guard("judge_match", "advance_match", "Otherwise the match advances."),
        _guard("advance_match", "contestant_a_argues", "Advance directly into the next sequential match.", predicates=[_predicate("advance_target", "eq", "contestant_a_argues")]),
        _guard("advance_match", "start_round", "Advance into the next bracket round.", predicates=[_predicate("advance_target", "eq", "start_round")]),
        _guard("advance_match", "crown_champion", "Final advancement can crown the champion.", predicates=[_predicate("advance_target", "eq", "crown_champion")]),
        _guard("crown_champion", TERMINAL_NODE_ID, "Champion output terminates the ranking run."),
    ]
    return "ranking", f"ranking.tournament.{protocol_key}", "seed_contestants", nodes, transitions, ["Tournament ranking is compiled into a bounded bracket graph."]


def _tournament_match_template(protocol_key: str) -> tuple[str, str, str, list[StateNode], list[TransitionGuard], list[str]]:
    nodes = [
        _node(
            "init_match",
            "Init Match",
            "planning",
            "Prepare a bounded two-contestant match shell.",
            role_hints=["system"],
            allowed_outputs=["current_match", "messages", "result"],
            output_schema=[_output("current_match", "object"), _output("messages", "array"), _output("result", "string")],
            state_reads=["agents", "current_stage_label"],
            state_writes=["current_match", "messages", "result"],
        ),
        _node(
            "contestant_a_argues",
            "Contestant A Argues",
            "argument",
            "Emit contestant A's argument for the current match round.",
            role_hints=["contestant_1"],
            allowed_outputs=["current_match", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[_output("current_match", "object"), _output("messages", "array"), _output("protocol_name", "string")],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "contestant_b_argues",
            "Contestant B Argues",
            "argument",
            "Emit contestant B's argument for the current match round.",
            role_hints=["contestant_2"],
            allowed_outputs=["current_match", "current_match_round", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
            output_schema=[
                _output("current_match", "object"),
                _output("current_match_round", "integer"),
                _output("messages", "array"),
                _output("protocol_name", "string"),
            ],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "current_match_round", "messages", "protocol_name", "fact_check_failures", "disqualified_role"],
        ),
        _node(
            "judge_match",
            "Judge Match",
            "judging",
            "Choose whether to continue the match or finalize it.",
            role_hints=["judge"],
            allowed_outputs=["current_match", "judge_action", "match_winner", "match_verdict", "result", "protocol_name", "protocol_telemetry", "messages"],
            output_schema=[
                _output("current_match", "object"),
                _output("judge_action", "string"),
                _output("match_winner", "string"),
                _output("match_verdict", "string"),
                _output("result", "string"),
                _output("protocol_name", "string"),
                _output("protocol_telemetry", "object"),
                _output("messages", "array"),
            ],
            state_reads=["current_match", "current_match_round", "max_rounds"],
            state_writes=["current_match", "judge_action", "match_winner", "match_verdict", "result", "protocol_name", "protocol_telemetry", "messages"],
        ),
        _node(
            "finalize_match",
            "Finalize Match",
            "finalize",
            "Emit the final match result for the parent tournament lane.",
            role_hints=["system"],
            allowed_outputs=["champion", "config", "result", "messages"],
            output_schema=[_output("champion", "object"), _output("config", "object"), _output("result", "string"), _output("messages", "array")],
            state_reads=["current_match", "match_winner", "match_verdict"],
            state_writes=["champion", "config", "result", "messages"],
        ),
    ]
    transitions = [
        _guard("init_match", "contestant_a_argues", "Initialized matches start with contestant A."),
        _guard("contestant_a_argues", "contestant_b_argues", "Contestant B follows contestant A."),
        _guard("contestant_b_argues", "judge_match", "Both contestants must speak before the judge."),
        _guard(
            "judge_match",
            "contestant_a_argues",
            "The judge can request another bounded round within the round cap.",
            predicates=[_predicate("judge_action", "eq", "continue"), _predicate("current_match_round", "lt", {"field": "max_rounds"})],
        ),
        _guard("judge_match", "finalize_match", "Finalized matches flow into a bounded handoff payload."),
        _guard("finalize_match", TERMINAL_NODE_ID, "Finalized matches terminate the child lane."),
    ]
    return "ranking", f"ranking.tournament_match.{protocol_key}", "init_match", nodes, transitions, ["Child tournament matches remain replayable and bounded."]


_MODE_TEMPLATE_BUILDERS = {
    "board": _board_template,
    "creator_critic": _creator_critic_template,
    "debate": _debate_template,
    "democracy": _democracy_template,
    "dictator": lambda _protocol_key: _dictator_template(),
    "moa": lambda _protocol_key: _moa_template(),
    "map_reduce": lambda _protocol_key: _map_reduce_template(),
    "tournament": _tournament_template,
    "tournament_match": _tournament_match_template,
}

_TRACE_VALUE_FIELDS = (
    "selected_candidate_id",
    "advance_target",
    "approved",
    "current_round",
    "current_match_round",
    "decision",
    "disqualified_role",
    "judge_action",
    "majority_position",
    "match_winner",
    "protocol_name",
    "result",
    "scrutiny_requested",
    "vote_round",
)
_TRACE_LENGTH_FIELDS = (
    "chunk_results",
    "critiques",
    "judge_scores",
    "layer1_outputs",
    "layer2_outputs",
    "match_history",
    "messages",
    "positions",
    "rounds",
    "submissions",
    "trace_artifacts",
    "versions",
    "votes",
    "winners",
    "worker_results",
)


def compile_protocol_blueprint(
    mode: str,
    agents: list[Any],
    config: dict[str, Any] | None = None,
    *,
    task: str = "",
    scenario_id: str | None = None,
) -> ProtocolBlueprint:
    normalized_mode = str(mode or "dictator").strip().lower()
    normalized_config = dict(config or {})
    protocol_key = _resolve_protocol_key(normalized_mode, normalized_config)
    template_builder = _MODE_TEMPLATE_BUILDERS.get(normalized_mode)
    if template_builder is None:
        template_builder = lambda _protocol_key: _dictator_template()
        normalized_mode = "dictator"

    mode_family, blueprint_class, entry_node_id, nodes, transitions, notes = template_builder(protocol_key)
    cache_payload = {
        "mode": normalized_mode,
        "mode_family": mode_family,
        "protocol_key": protocol_key,
        "blueprint_class": blueprint_class,
        "agent_roles": _agent_roles(agents),
        "execution_mode": str(normalized_config.get("execution_mode") or "sequential"),
        "max_rounds": int(normalized_config.get("max_rounds") or 0),
        "max_iterations": int(normalized_config.get("max_iterations") or 0),
    }
    cache_key = f"pb_{stable_payload_hash(cache_payload)[:16]}"
    return ProtocolBlueprint(
        cache_key=cache_key,
        mode=normalized_mode,
        mode_family=mode_family,
        protocol_key=protocol_key,
        blueprint_class=blueprint_class,
        entry_node_id=entry_node_id,
        nodes=nodes,
        transitions=transitions,
        notes=notes,
        compiled_from={
            "task_preview": str(task or "")[:160],
            "scenario_id": scenario_id,
            "agent_roles": _agent_roles(agents),
            "config": {
                key: normalized_config.get(key)
                for key in ("execution_mode", "max_rounds", "max_iterations", "protocol")
                if key in normalized_config
            },
        },
        planner_hints={
            "planner_model_tier": "expensive_once",
            "executor_model_tier": "cheap_follower",
            "shadow_validation": True,
            "replayable_traces": True,
            "cache_scope": "workflow_class",
        },
    )


def _value_at_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in str(path or "").split("."):
        if isinstance(value, dict):
            value = value.get(part)
            continue
        return None
    return value


def _coerce_comparison_value(payload: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and set(value.keys()) == {"field"}:
        return _value_at_path(payload, str(value["field"]))
    return value


def _matches_type(value: Any, field_type: FieldType) -> bool:
    if field_type == "string":
        return isinstance(value, str)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "boolean":
        return isinstance(value, bool)
    if field_type == "array":
        return isinstance(value, list)
    if field_type == "object":
        return isinstance(value, dict)
    return value is None


def _evaluate_predicate(payload: dict[str, Any], predicate: GuardPredicate) -> bool:
    current_value = _value_at_path(payload, predicate.field)
    expected = _coerce_comparison_value(payload, predicate.value)
    operator = predicate.operator
    try:
        if operator == "eq":
            return current_value == expected
        if operator == "ne":
            return current_value != expected
        if operator == "lt":
            return current_value is not None and expected is not None and current_value < expected
        if operator == "lte":
            return current_value is not None and expected is not None and current_value <= expected
        if operator == "gt":
            return current_value is not None and expected is not None and current_value > expected
        if operator == "gte":
            return current_value is not None and expected is not None and current_value >= expected
        if operator == "truthy":
            return bool(current_value)
        if operator == "falsy":
            return not bool(current_value)
        if operator == "nonempty":
            return current_value not in (None, "", [], {})
        if operator == "in":
            return current_value in expected if isinstance(expected, (list, tuple, set)) else False
        if operator == "contains":
            if isinstance(current_value, str):
                return str(expected) in current_value
            if isinstance(current_value, (list, tuple, set)):
                return expected in current_value
            return False
        if operator == "not_contains":
            if isinstance(current_value, str):
                return str(expected) not in current_value
            if isinstance(current_value, (list, tuple, set)):
                return expected not in current_value
            return True
    except TypeError:
        return False
    return False


def _matching_guard(
    blueprint: ProtocolBlueprint,
    from_node_id: str,
    to_node_id: str,
    payload: dict[str, Any],
) -> tuple[TransitionGuard | None, list[TransitionGuard]]:
    candidates = [
        guard
        for guard in blueprint.transitions
        if guard.source_node_id == from_node_id and guard.target_node_id == to_node_id
    ]
    if not candidates:
        return None, []
    for guard in candidates:
        if not guard.predicates:
            return guard, candidates
        results = [_evaluate_predicate(payload, predicate) for predicate in guard.predicates]
        if guard.predicate_match == "any" and any(results):
            return guard, candidates
        if guard.predicate_match == "all" and all(results):
            return guard, candidates
    return None, candidates


def shadow_validate_transition(
    blueprint: ProtocolBlueprint,
    from_node_id: str,
    to_node_id: str | None,
    payload: dict[str, Any] | None = None,
) -> ShadowValidationResult:
    normalized_payload = dict(payload or {})
    normalized_to_node = str(to_node_id or TERMINAL_NODE_ID)
    result = ShadowValidationResult(
        blueprint_id=blueprint.blueprint_id,
        from_node_id=str(from_node_id or blueprint.entry_node_id),
        to_node_id=normalized_to_node,
    )

    matched_guard, candidates = _matching_guard(blueprint, result.from_node_id, normalized_to_node, normalized_payload)
    if matched_guard is None:
        if candidates:
            result.errors.append(
                f"Transition {result.from_node_id} -> {normalized_to_node} exists but its guard predicates did not match the current state."
            )
        else:
            result.errors.append(f"Transition {result.from_node_id} -> {normalized_to_node} is not part of blueprint {blueprint.blueprint_class}.")
    else:
        result.guard_id = matched_guard.guard_id

    node_by_id = {node.node_id: node for node in blueprint.nodes}
    node = node_by_id.get(result.from_node_id)
    if node is None:
        result.warnings.append(f"Node {result.from_node_id} is missing from blueprint node definitions.")
    else:
        for field in node.output_schema:
            current_value = _value_at_path(normalized_payload, field.name)
            if current_value is None:
                if field.required:
                    result.errors.append(f"Node {node.node_id} did not populate required field '{field.name}'.")
                continue
            if not _matches_type(current_value, field.field_type):
                result.errors.append(
                    f"Field '{field.name}' on node {node.node_id} expected {field.field_type}, got {type(current_value).__name__}."
                )

    result.ok = not result.errors
    return result


def build_trace_state_excerpt(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized_payload = dict(payload or {})
    excerpt: dict[str, Any] = {}
    for key in _TRACE_VALUE_FIELDS:
        value = normalized_payload.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            excerpt[key] = value[:240]
        else:
            excerpt[key] = value
    for key in _TRACE_LENGTH_FIELDS:
        value = normalized_payload.get(key)
        if isinstance(value, list):
            excerpt[f"{key}_count"] = len(value)
    return excerpt
