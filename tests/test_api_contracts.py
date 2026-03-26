"""Regression coverage for API boundary validation and honest capability reporting."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.api import router
from orchestrator.models import AgentConfig, AVAILABLE_TOOLS, store


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


def test_run_rejects_provider_tool_mismatch():
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

    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("cannot use codex" in error for error in errors)


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
    assert {item["key"] for item in payload} == {tool.key for tool in AVAILABLE_TOOLS}


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
    assert "not wired" in response.json()["detail"]
