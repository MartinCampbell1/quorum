"""Route-level tests for founder GitHub bootstrap."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Pre-mock heavy dependencies to avoid requiring langgraph for route tests
for mod in [
    "langgraph", "langgraph.graph", "langgraph.graph.state",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    sys.modules.setdefault(mod, MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.discovery_store import clear_discovery_store_cache
from orchestrator.models import SessionStore


class FakeGitHubClient:
    def __init__(self, repos: list[dict] | None = None):
        self.repos = repos or _FAKE_REPOS

    async def list_repos(self, username, *, max_repos=100, include_forks=False, include_archived=False):
        return self.repos


_FAKE_REPOS = [
    {
        "name": "cli-tool-a",
        "full_name": "martin/cli-tool-a",
        "html_url": "https://github.com/martin/cli-tool-a",
        "description": "A CLI tool for developer workflows",
        "topics": ["cli", "developer-tools", "automation"],
        "language": "Python",
        "stargazers_count": 42,
        "fork": False,
        "archived": False,
    },
    {
        "name": "web-dashboard",
        "full_name": "martin/web-dashboard",
        "html_url": "https://github.com/martin/web-dashboard",
        "description": "Dashboard for monitoring",
        "topics": ["dashboard", "monitoring", "react"],
        "language": "TypeScript",
        "stargazers_count": 25,
        "fork": False,
        "archived": False,
    },
]


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_discovery_store(tmp_path, monkeypatch):
    isolated = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_discovery_store_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated)
    yield isolated
    clear_discovery_store_cache()


def test_founder_bootstrap_route_returns_503_without_github_client(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.founder_bootstrap.get_github_portfolio_client_or_none",
        lambda: None,
    )

    response = client.post(
        "/orchestrate/founder/bootstrap/github",
        json={"github_username": "martin"},
    )

    assert response.status_code == 503
    assert "github_token" in response.json()["detail"].lower()


def test_founder_bootstrap_route_runs_pipeline_and_seeds_discovery(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.founder_bootstrap.get_github_portfolio_client_or_none",
        lambda: FakeGitHubClient(),
    )

    response = client.post(
        "/orchestrate/founder/bootstrap/github",
        json={"github_username": "martin"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["github_username"] == "martin"
    assert payload["repos_scanned"] == 2
    assert len(payload["clusters"]) > 0
    assert len(payload["hypotheses"]) > 0

    ideas = client.get("/orchestrate/discovery/ideas").json()["ideas"]
    assert len(ideas) > 0
