"""Regression coverage for API boundary validation and honest capability reporting."""

import json
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.execution_brief import (
    AutopilotLaunchPreset,
    AutopilotLaunchProfile,
    ExecutionBrief,
    TournamentPreparation,
    TournamentCandidate,
)
from orchestrator.models import AgentConfig, AVAILABLE_TOOLS, SessionStore, store
from orchestrator.tool_configs import ToolConfig, tool_config_store


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_session_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    monkeypatch.setattr(sys.modules[__name__], "store", isolated)
    yield isolated


def _agent(role: str, provider: str, tools: list[str]) -> dict:
    return {
        "role": role,
        "provider": provider,
        "system_prompt": "",
        "tools": tools,
        "workspace_paths": [],
    }


def test_run_rejects_invalid_debate_topology():
    response = client.post(
        "/orchestrate/run",
        json={
            "mode": "debate",
            "task": "Debate a database migration strategy",
            "agents": [
                _agent("proponent", "claude", ["web_search"]),
                _agent("opponent", "codex", ["web_search"]),
            ],
        },
    )

    assert response.status_code == 422
    payload = response.json()["detail"]
    assert "Invalid agent topology" in payload["message"]
    assert any("exactly 3 agents" in error for error in payload["errors"])


def test_run_accepts_bridged_provider_tool_combo():
    with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_bridge")) as mock_run:
        response = client.post(
            "/orchestrate/run",
            json={
                "mode": "dictator",
                "task": "Investigate an internal API",
                "agents": [
                    _agent("director", "claude", ["web_search"]),
                    _agent("worker", "codex", ["http_request"]),
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "sess_bridge"
    assert payload["provider_capabilities_snapshot"]["worker"]["tools"]["http_request"]["capability"] == "bridged"
    mock_run.assert_awaited_once()


def test_run_accepts_valid_default_tournament_topology():
    with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_test")) as mock_run:
        response = client.post(
            "/orchestrate/run",
            json={
                "mode": "tournament",
                "task": "Compare implementation approaches",
            },
        )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess_test"
    mock_run.assert_awaited_once()


def test_run_accepts_parallel_execution_mode_for_tournament():
    with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_parallel")) as mock_run:
        response = client.post(
            "/orchestrate/run",
            json={
                "mode": "tournament",
                "task": "Compare implementation approaches",
                "config": {"execution_mode": "parallel"},
            },
        )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess_parallel"
    assert mock_run.await_args.kwargs["config"]["execution_mode"] == "parallel"


def test_run_rejects_parallel_execution_mode_for_non_tournament():
    response = client.post(
        "/orchestrate/run",
        json={
            "mode": "debate",
            "task": "Debate architecture tradeoffs",
            "config": {"execution_mode": "parallel"},
        },
    )

    assert response.status_code == 422
    assert "currently supported only for tournament" in response.json()["detail"]


def test_run_rejects_tournament_without_last_judge():
    response = client.post(
        "/orchestrate/run",
        json={
            "mode": "tournament",
            "task": "Compare implementation approaches",
            "agents": [
                _agent("judge", "claude", ["perplexity"]),
                _agent("contestant_1", "codex", ["code_exec"]),
                _agent("contestant_2", "gemini", ["web_search"]),
            ],
        },
    )

    assert response.status_code == 422
    payload = response.json()["detail"]
    assert any("judge" in error for error in payload["errors"])


def test_tools_endpoint_returns_builtin_catalog():
    response = client.get("/orchestrate/tools")

    assert response.status_code == 200
    payload = response.json()
    assert {"code_exec", "shell_exec"}.issubset({item["key"] for item in payload})


def test_provider_capabilities_endpoint_reports_native_and_bridged_support():
    response = client.get("/orchestrate/settings/providers/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tools"]["web_search"]["codex"] == "native"
    assert payload["tools"]["http_request"]["codex"] == "bridged"


def test_scenarios_endpoint_returns_personal_catalog():
    response = client.get("/orchestrate/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert {"repo_audit", "pattern_mining", "news_context", "portfolio_pivot_lab", "project_strengthening_lab", "consensus_vote", "structured_debate", "strategy_review", "project_tournament"} == {
        item["id"] for item in payload
    }


def test_scenarios_endpoint_allows_multiple_presets_per_mode():
    response = client.get("/orchestrate/scenarios")

    assert response.status_code == 200
    board_scenarios = [item["id"] for item in response.json() if item["mode"] == "board"]
    assert {"news_context", "portfolio_pivot_lab", "project_strengthening_lab"}.issubset(set(board_scenarios))


def test_scenarios_endpoint_covers_all_primary_wizard_modes():
    response = client.get("/orchestrate/scenarios")

    assert response.status_code == 200
    modes = {item["mode"] for item in response.json()}
    assert {"dictator", "board", "democracy", "debate", "map_reduce", "creator_critic", "tournament"}.issubset(modes)


def test_run_accepts_agent_specific_workspace_paths():
    with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_paths")) as mock_run:
        response = client.post(
            "/orchestrate/run",
            json={
                "mode": "tournament",
                "task": "Compare local repos",
                "agents": [
                    {
                        "role": "contestant_1",
                        "provider": "claude",
                        "system_prompt": "",
                        "tools": ["code_exec"],
                        "workspace_paths": [str(store._db_path.parent)],
                    },
                    {
                        "role": "contestant_2",
                        "provider": "codex",
                        "system_prompt": "",
                        "tools": ["code_exec"],
                        "workspace_paths": [str(store._db_path.parent)],
                    },
                    {
                        "role": "judge",
                        "provider": "gemini",
                        "system_prompt": "",
                        "tools": ["perplexity"],
                        "workspace_paths": [],
                    },
                ],
            },
        )

    assert response.status_code == 200
    forwarded_agents = mock_run.await_args.kwargs["agents"]
    assert forwarded_agents[0].workspace_paths == [str(store._db_path.parent)]
    assert forwarded_agents[1].workspace_paths == [str(store._db_path.parent)]


def test_session_store_hides_parallel_children_from_recent_list(tmp_path):
    db = SessionStore(db_path=str(tmp_path / "state.db"))
    agents = [AgentConfig(role="contestant_1", provider="claude"), AgentConfig(role="judge", provider="gemini")]
    parent_id = db.create("tournament", "Parent run", agents, {"execution_mode": "parallel"})
    child_id = db.create(
        "tournament_match",
        "QF match 1",
        agents,
        {"match_result": {"winner_label": "contestant_1"}},
        parallel_parent_id=parent_id,
        parallel_group_id="pg_test",
        parallel_slot_key="qf-1",
        parallel_stage="QF",
        parallel_label="QF match 1",
    )

    recent_ids = [item["id"] for item in db.list_recent()]
    assert parent_id in recent_ids
    assert child_id not in recent_ids

    session = db.get(parent_id)
    assert session is not None
    assert session["parallel_children"][0]["id"] == child_id


def test_custom_tools_compat_layer_round_trips_http_api():
    try:
        response = client.post(
            "/orchestrate/tools/custom",
            json={
                "key": "internal_api",
                "name": "Internal API",
                "description": "Call internal API",
                "tool_type": "http_api",
                "config": {
                    "url": "https://example.com/api",
                    "method": "POST",
                    "headers": "{\"Authorization\": \"Bearer secret\", \"X-Trace\": \"1\"}",
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["tool_type"] == "http_api"
        assert payload["config"]["url"] == "https://example.com/api"

        stored = tool_config_store.get("internal_api")
        assert stored is not None
        assert stored.tool_type == "http_api"
        assert stored.config["base_url"] == "https://example.com/api"
        assert stored.config["auth_header"] == "Bearer secret"
        assert json.loads(stored.config["headers_json"]) == {"X-Trace": "1"}

        listing = client.get("/orchestrate/tools/custom")
        assert listing.status_code == 200
        listed = next(item for item in listing.json() if item["key"] == "internal_api")
        assert listed["description"] == "Call internal API"
        assert json.loads(listed["config"]["headers"]) == {
            "Authorization": "Bearer secret",
            "X-Trace": "1",
        }

        delete = client.delete("/orchestrate/tools/custom/internal_api")
        assert delete.status_code == 200
        assert tool_config_store.get("internal_api") is None
    finally:
        tool_config_store.delete("internal_api")


def test_custom_tools_compat_layer_supports_shell_command():
    try:
        response = client.post(
            "/orchestrate/tools/custom",
            json={
                "key": "local_probe",
                "name": "Local Probe",
                "description": "Run a reusable local shell probe.",
                "tool_type": "shell_command",
                "config": {"command": "curl -s http://127.0.0.1:8800/health"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["tool_type"] == "shell_command"
        assert payload["config"]["command"] == "curl -s http://127.0.0.1:8800/health"

        settings_listing = client.get("/orchestrate/settings/tools")
        assert settings_listing.status_code == 200
        tool_row = next(item for item in settings_listing.json() if item["id"] == "local_probe")
        assert tool_row["tool_type"] == "shell"
        assert tool_row["transport"] == "bridge"
    finally:
        tool_config_store.delete("local_probe")


def test_settings_tools_api_rejects_builtin_tool_override():
    response = client.post(
        "/orchestrate/settings/tools",
        json={
            "id": "code_exec",
            "name": "Overridden Python",
            "tool_type": "code_exec",
            "icon": "🐍",
            "config": {},
            "enabled": True,
        },
    )

    assert response.status_code == 409
    assert "cannot be replaced" in response.json()["detail"]


def test_run_rejects_scenario_mode_mismatch():
    response = client.post(
        "/orchestrate/run",
        json={
            "scenario_id": "repo_audit",
            "mode": "board",
            "task": "Inspect the repo",
        },
    )

    assert response.status_code == 422
    assert "bound to mode 'dictator'" in response.json()["detail"]


def test_live_messages_endpoint_reports_read_only_session():
    session_id = store.create(
        "dictator",
        "Draft a plan",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )

    response = client.post(
        f"/orchestrate/session/{session_id}/message",
        json={"content": "Please incorporate user feedback"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "status_not_messageable"
    assert "Pause the run first" in detail["message"]


def test_session_events_endpoint_streams_backlog_once():
    session_id = store.create(
        "dictator",
        "Draft a plan",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    store.append_event(session_id, "run_started", "Сессия запущена", "Draft a plan")
    store.append_event(session_id, "checkpoint_created", "Checkpoint cp_1", "Следующий узел: workers")

    response = client.get(f"/orchestrate/session/{session_id}/events?once=true")

    assert response.status_code == 200
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [payload["type"] for payload in payloads] == ["run_started", "checkpoint_created"]


def test_checkpoint_restart_requires_non_running_session():
    session_id = store.create(
        "dictator",
        "Draft a plan",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )

    response = client.post(
        f"/orchestrate/session/{session_id}/control",
        json={"action": "restart_from_checkpoint"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "status_not_branchable"
    assert "must be paused or finished" in detail["message"]


def test_resume_reports_missing_runtime_state_after_restart():
    session_id = store.create(
        "creator_critic",
        "Resume after restart",
        [
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="paused")

    response = client.post(
        f"/orchestrate/session/{session_id}/control",
        json={"action": "resume"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "runtime_unavailable_after_restart"
    assert "runtime is unavailable" in detail["message"]


def test_session_endpoint_exposes_runtime_state_flags():
    session_id = store.create(
        "creator_critic",
        "Paused session snapshot",
        [
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="paused")
    store.add_checkpoint(
        session_id,
        {
            "id": "cp_1",
            "timestamp": 1.0,
            "next_node": "critic_reviews",
            "status": "ready",
            "result_preview": "",
            "graph_checkpoint_id": "graph_cp_1",
        },
    )

    response = client.get(f"/orchestrate/session/{session_id}")

    assert response.status_code == 200
    runtime_state = response.json()["runtime_state"]
    assert runtime_state["live_runtime_available"] is False
    assert runtime_state["checkpoint_runtime_available"] is False
    assert runtime_state["has_checkpoints"] is True
    assert runtime_state["can_resume"] is False
    assert runtime_state["can_continue_conversation"] is False
    assert runtime_state["can_branch_from_checkpoint"] is False
    assert runtime_state["reasons"]["resume"]["code"] == "runtime_unavailable_after_restart"
    assert runtime_state["reasons"]["branch_from_checkpoint"]["code"] == "checkpoint_runtime_unavailable"


def test_sessions_list_exposes_runtime_state_flags():
    session_id = store.create(
        "dictator",
        "Recent session card",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="failed", current_checkpoint_id="cp_last")

    response = client.get("/orchestrate/sessions")

    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == session_id)
    assert payload["runtime_state"]["has_checkpoints"] is True
    assert payload["runtime_state"]["can_branch_from_checkpoint"] is False


def test_cancel_reports_missing_runtime_for_paused_session():
    session_id = store.create(
        "creator_critic",
        "Cancel after restart",
        [
            AgentConfig(role="creator", provider="claude", tools=[]),
            AgentConfig(role="critic", provider="claude", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="paused")

    response = client.post(
        f"/orchestrate/session/{session_id}/control",
        json={"action": "cancel"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "runtime_unavailable_after_restart"
    assert "runtime is unavailable" in detail["message"]


def test_continue_endpoint_creates_branch_from_current_checkpoint():
    session_id = store.create(
        "debate",
        "Continue the discussion",
        [
            AgentConfig(role="proponent", provider="claude", tools=[]),
            AgentConfig(role="opponent", provider="codex", tools=[]),
            AgentConfig(role="judge", provider="gemini", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="completed", current_checkpoint_id="cp_3")
    store.add_checkpoint(
        session_id,
        {
            "id": "cp_3",
            "timestamp": 1.0,
            "next_node": "judge_decides",
            "status": "terminal",
            "result_preview": "Judge verdict",
            "graph_checkpoint_id": "graph_cp_3",
        },
    )

    with patch("orchestrator.api.has_checkpoint_runtime", return_value=True), patch(
        "orchestrator.api.fork_from_checkpoint", return_value="sess_followup"
    ) as mock_fork:
        response = client.post(
            f"/orchestrate/session/{session_id}/continue",
            json={"content": "Push the team on operational risks."},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "running", "new_session_id": "sess_followup"}
    mock_fork.assert_called_once_with(session_id, "cp_3", "Push the team on operational risks.")


def test_execution_brief_schema_route_exposes_contract():
    response = client.get("/orchestrate/execution-brief/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "ExecutionBrief"
    assert "properties" in payload
    assert "founder" in payload["properties"]


def test_execution_brief_endpoint_exports_brief_from_session():
    session_id = store.create(
        "tournament",
        "Choose the best product to build next.",
        [
            AgentConfig(role="contestant_1", provider="codex", tools=[]),
            AgentConfig(role="contestant_2", provider="claude", tools=[]),
            AgentConfig(role="judge", provider="gemini", tools=[]),
        ],
        {},
        scenario_id="project_tournament",
    )
    store.update(
        session_id,
        status="completed",
        result="Champion: graphrag-affiliate",
        messages=[{"agent_id": "judge", "phase": "verdict", "content": "GraphRAG should win and be productized next."}],
        workspace_paths=["/Users/example/Desktop/Projects/graphrag-affiliate"],
    )

    exported = ExecutionBrief(
        title="GraphRAG Affiliate",
        thesis="Build the GraphRAG affiliate product first.",
        summary="It is the strongest candidate from the tournament.",
    )

    with patch("orchestrator.api.generate_session_execution_brief", return_value=exported) as mock_export:
        response = client.post(f"/orchestrate/session/{session_id}/execution-brief", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["brief"]["title"] == "GraphRAG Affiliate"
    mock_export.assert_called_once()


def test_send_to_autopilot_endpoint_forwards_brief():
    session_id = store.create(
        "debate",
        "Decide which product should become the next execution candidate.",
        [
            AgentConfig(role="proponent", provider="codex", tools=[]),
            AgentConfig(role="opponent", provider="claude", tools=[]),
            AgentConfig(role="judge", provider="gemini", tools=[]),
        ],
        {},
        scenario_id="structured_debate",
    )
    store.update(session_id, status="completed", result="Autopilot should be executed next.")

    exported = ExecutionBrief(
        title="Autopilot",
        thesis="Push Autopilot into multi-agent execution and self-improvement.",
        summary="The debate recommended Autopilot as the best next execution candidate.",
    )

    with patch("orchestrator.api.generate_session_execution_brief", return_value=exported) as mock_export, patch(
        "orchestrator.api._send_brief_to_autopilot",
        new=AsyncMock(return_value={"project_id": "proj_123", "status": "ok", "launched": False}),
    ) as mock_send:
        response = client.post(
            f"/orchestrate/session/{session_id}/send-to-autopilot",
            json={
                "project_path": "/Users/example/Desktop/autopilot/projects/autopilot-child",
                "priority": "high",
                "launch": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["brief"]["title"] == "Autopilot"
    assert payload["autopilot"]["project_id"] == "proj_123"
    mock_export.assert_called_once()
    assert mock_send.await_count == 1


def test_tournament_preparation_endpoint_returns_wizard_ready_payload():
    session_id = store.create(
        "board",
        "Generate pivots for my current portfolio.",
        [
            AgentConfig(role="portfolio_strategist", provider="claude", tools=[]),
            AgentConfig(role="market_scout", provider="gemini", tools=[]),
            AgentConfig(role="pivot_critic", provider="codex", tools=[]),
        ],
        {},
        scenario_id="portfolio_pivot_lab",
    )
    store.update(
        session_id,
        status="completed",
        result="Shortlist prepared.",
        workspace_paths=[
            "/Users/example/Desktop/Projects/graphrag-affiliate",
            "/Users/example/Desktop/autopilot",
        ],
    )

    preparation = TournamentPreparation(
        title="FounderOS shortlist",
        task="Run a tournament between the strongest pivots.",
        contestants=[
            TournamentCandidate(
                label="GraphRAG Affiliate -> paid intelligence terminal",
                thesis="Sell the graph-backed corpus as a subscription tool.",
                rationale="Fastest path to first money.",
                source_workspace_path="/Users/example/Desktop/Projects/graphrag-affiliate",
            ),
            TournamentCandidate(
                label="Autopilot -> execution OS for solo founders",
                thesis="Package Autopilot as a high-value execution engine.",
                rationale="Strongest AI-edge.",
                source_workspace_path="/Users/example/Desktop/autopilot",
            ),
        ],
        agents=[
            AgentConfig(role="contestant_1", provider="claude", tools=["web_search"], workspace_paths=["/Users/example/Desktop/Projects/graphrag-affiliate"]),
            AgentConfig(role="contestant_2", provider="codex", tools=["code_exec"], workspace_paths=["/Users/example/Desktop/autopilot"]),
            AgentConfig(role="judge", provider="gemini", tools=["perplexity"]),
        ],
        workspace_paths=[
            "/Users/example/Desktop/Projects/graphrag-affiliate",
            "/Users/example/Desktop/autopilot",
        ],
    )

    with patch("orchestrator.api.generate_session_tournament_preparation", return_value=preparation) as mock_prepare:
        response = client.post(f"/orchestrate/session/{session_id}/tournament-preparation", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["tournament"]["scenario_id"] == "project_tournament"
    assert len(payload["tournament"]["contestants"]) == 2
    assert payload["tournament"]["agents"][-1]["role"] == "judge"
    mock_prepare.assert_called_once()


def test_autopilot_launch_presets_route_proxies_presets():
    with patch(
        "orchestrator.api._fetch_autopilot_launch_presets",
        new=AsyncMock(
            return_value=[
                AutopilotLaunchPreset(
                    id="team",
                    label="Team",
                    description="Primary worker plus critic.",
                    launch_profile=AutopilotLaunchProfile(
                        preset="team",
                        story_execution_mode="team",
                        project_concurrency_mode="sequential",
                        max_parallel_stories=1,
                    ),
                )
            ]
        ),
    ):
        response = client.get("/orchestrate/autopilot/launch-presets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["launch_presets"][0]["id"] == "team"


def test_autopilot_projects_route_proxies_project_list():
    with patch(
        "orchestrator.api._fetch_autopilot_projects",
        new=AsyncMock(
            return_value=[
                {
                    "id": "proj_123",
                    "name": "Autopilot Winner",
                    "path": "/Users/example/.autopilot/projects/autopilot-winner",
                    "priority": "high",
                    "archived": False,
                    "status": "paused",
                    "paused": True,
                    "stories_done": 2,
                    "stories_total": 5,
                    "current_story_id": 3,
                    "current_story_title": "Refine execution loop",
                    "last_activity_at": "2026-03-29T01:00:00+00:00",
                    "last_message": "Project paused by user.",
                    "pid": None,
                    "launch_profile": {"preset": "team"},
                }
            ]
        ),
    ) as mock_projects:
        response = client.get("/orchestrate/autopilot/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projects"][0]["id"] == "proj_123"
    assert mock_projects.await_count == 1


def test_autopilot_project_pause_route_proxies_action():
    with patch(
        "orchestrator.api._post_autopilot_project_action",
        new=AsyncMock(return_value={"status": "ok", "message": "Paused Autopilot Winner"}),
    ) as mock_action:
        response = client.post("/orchestrate/autopilot/projects/proj_123/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_action.assert_awaited_once_with("proj_123", "pause")


def test_continue_endpoint_rejects_non_terminal_session():
    session_id = store.create(
        "debate",
        "Still running",
        [
            AgentConfig(role="proponent", provider="claude", tools=[]),
            AgentConfig(role="opponent", provider="codex", tools=[]),
            AgentConfig(role="judge", provider="gemini", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="running")

    response = client.post(
        f"/orchestrate/session/{session_id}/continue",
        json={"content": "Continue the conversation"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "status_not_continuable"


def test_inject_instruction_rejects_terminal_session_status():
    session_id = store.create(
        "dictator",
        "Finished run",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="completed")

    response = client.post(
        f"/orchestrate/session/{session_id}/control",
        json={"action": "inject_instruction", "content": "Continue with more detail"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "status_not_instructionable"
    assert "cannot accept instructions" in detail["message"]


def test_checkpoint_restart_surfaces_checkpoint_not_found_reason():
    session_id = store.create(
        "dictator",
        "Missing checkpoint branch",
        [
            AgentConfig(role="director", provider="claude", tools=[]),
            AgentConfig(role="worker", provider="codex", tools=[]),
        ],
        {},
    )
    store.update(session_id, status="paused", current_checkpoint_id="cp_missing")

    with patch("orchestrator.api.has_checkpoint_runtime", return_value=True), patch(
        "orchestrator.api.fork_from_checkpoint", return_value=None
    ):
        response = client.post(
            f"/orchestrate/session/{session_id}/control",
            json={"action": "restart_from_checkpoint", "checkpoint_id": "cp_missing"},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["reason"]["code"] == "checkpoint_not_found"
    assert detail["checkpoint_id"] == "cp_missing"


def test_run_accepts_configured_tool_for_claude():
    tool = ToolConfig(
        id="market_api",
        name="Market API",
        tool_type="custom_api",
        icon="🔧",
        config={"base_url": "https://api.example.com/v1"},
        enabled=True,
    )
    tool_config_store.add(tool)
    try:
        with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_cfg")) as mock_run:
            response = client.post(
                "/orchestrate/run",
                json={
                    "mode": "creator_critic",
                    "task": "Research market signals",
                    "agents": [
                        _agent("creator", "claude", ["market_api"]),
                        _agent("critic", "codex", ["code_exec"]),
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json()["session_id"] == "sess_cfg"
        mock_run.assert_awaited_once()
    finally:
        tool_config_store.delete("market_api")


def test_run_accepts_configured_stdio_mcp_tool_for_codex_natively():
    tool = ToolConfig(
        id="github_mcp",
        name="GitHub MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "stdio", "command": "npx -y @modelcontextprotocol/server-github"},
        enabled=True,
    )
    tool_config_store.add(tool)
    try:
        with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_mcp_bridge")) as mock_run:
            response = client.post(
                "/orchestrate/run",
                json={
                    "mode": "creator_critic",
                    "task": "Open issue triage",
                    "agents": [
                        _agent("creator", "codex", ["github_mcp"]),
                        _agent("critic", "claude", []),
                    ],
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == "sess_mcp_bridge"
        assert (
            payload["provider_capabilities_snapshot"]["creator"]["tools"]["github_mcp"]["capability"]
            == "native"
        )
        mock_run.assert_awaited_once()
    finally:
        tool_config_store.delete("github_mcp")


def test_provider_capabilities_report_external_mcp_native_for_gemini_and_bridged_for_codex():
    tool = ToolConfig(
        id="stitch_mcp",
        name="Stitch MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "http", "url": "https://stitch.googleapis.com/mcp", "headers": "{\"Authorization\": \"Bearer token\"}"},
        enabled=True,
    )
    tool_config_store.add(tool)
    try:
        response = client.get("/orchestrate/settings/providers/capabilities")
        assert response.status_code == 200
        payload = response.json()
        assert payload["tools"]["stitch_mcp"]["claude"] == "native"
        assert payload["tools"]["stitch_mcp"]["gemini"] == "native"
        assert payload["tools"]["stitch_mcp"]["codex"] == "native"
    finally:
        tool_config_store.delete("stitch_mcp")


def test_provider_capabilities_keep_codex_http_mcp_bridged_for_non_bearer_headers():
    tool = ToolConfig(
        id="custom_header_mcp",
        name="Custom Header MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "http", "url": "https://example.com/mcp", "headers": "{\"X-Api-Key\": \"token\"}"},
        enabled=True,
    )
    tool_config_store.add(tool)
    try:
        response = client.get("/orchestrate/settings/providers/capabilities")
        assert response.status_code == 200
        payload = response.json()
        assert payload["tools"]["custom_header_mcp"]["codex"] == "bridged"
    finally:
        tool_config_store.delete("custom_header_mcp")


def test_run_accepts_configured_http_mcp_tool_for_codex_natively_when_bearer_only():
    tool = ToolConfig(
        id="bearer_http_mcp",
        name="Bearer HTTP MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "http", "url": "https://example.com/mcp", "headers": "{\"Authorization\": \"Bearer token\"}"},
        enabled=True,
    )
    tool_config_store.add(tool)
    try:
        with patch("orchestrator.api.run", new=AsyncMock(return_value="sess_http_mcp_native")) as mock_run:
            response = client.post(
                "/orchestrate/run",
                json={
                    "mode": "creator_critic",
                    "task": "Use remote MCP over HTTP",
                    "agents": [
                        _agent("creator", "codex", ["bearer_http_mcp"]),
                        _agent("critic", "claude", []),
                    ],
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == "sess_http_mcp_native"
        assert (
            payload["provider_capabilities_snapshot"]["creator"]["tools"]["bearer_http_mcp"]["capability"]
            == "native"
        )
        mock_run.assert_awaited_once()
    finally:
        tool_config_store.delete("bearer_http_mcp")


def test_workspace_preset_crud_round_trip(tmp_path):
    workspace_dir = tmp_path / "market-data"
    workspace_dir.mkdir()

    create = client.post(
        "/orchestrate/settings/workspaces",
        json={
            "id": "ws_market",
            "name": "Market data",
            "paths": [str(workspace_dir)],
            "description": "Trading datasets",
        },
    )
    assert create.status_code == 200
    assert create.json()["paths"] == [str(workspace_dir)]

    listing = client.get("/orchestrate/settings/workspaces")
    assert listing.status_code == 200
    assert any(item["id"] == "ws_market" for item in listing.json())

    update = client.put(
        "/orchestrate/settings/workspaces/ws_market",
        json={"description": "Updated"},
    )
    assert update.status_code == 200
    assert update.json()["description"] == "Updated"

    delete = client.delete("/orchestrate/settings/workspaces/ws_market")
    assert delete.status_code == 200
