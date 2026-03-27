"""Regression coverage for API boundary validation and honest capability reporting."""

import json
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.api import router
from orchestrator.models import AgentConfig, AVAILABLE_TOOLS, store
from orchestrator.tool_configs import ToolConfig, tool_config_store


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _agent(role: str, provider: str, tools: list[str]) -> dict:
    return {
        "role": role,
        "provider": provider,
        "system_prompt": "",
        "tools": tools,
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
    assert {"repo_audit", "pattern_mining", "news_context", "consensus_vote", "structured_debate", "strategy_review"} == {
        item["id"] for item in payload
    }


def test_scenarios_endpoint_covers_all_primary_wizard_modes():
    response = client.get("/orchestrate/scenarios")

    assert response.status_code == 200
    modes = {item["mode"] for item in response.json()}
    assert {"dictator", "board", "democracy", "debate", "map_reduce", "creator_critic"}.issubset(modes)


def test_custom_tools_are_honestly_disabled():
    response = client.post(
        "/orchestrate/tools/custom",
        json={
            "key": "internal_api",
            "name": "Internal API",
            "description": "Call internal API",
            "tool_type": "http_api",
            "config": {"url": "https://example.com"},
        },
    )

    assert response.status_code == 501
    assert "not supported" in response.json()["detail"]


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
    assert "Pause the run first" in response.json()["detail"]


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
    assert "must be paused or finished" in response.json()["detail"]


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
    assert "runtime is unavailable" in response.json()["detail"]


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
    assert runtime_state["can_branch_from_checkpoint"] is False


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
    assert "runtime is unavailable" in response.json()["detail"]


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
    assert "cannot accept instructions" in response.json()["detail"]


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
