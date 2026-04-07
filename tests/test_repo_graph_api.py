"""Regression coverage for the deep repo graph intelligence lane."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.models import SessionStore
from orchestrator.repo_graph import clear_repo_graph_service_cache


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_repo_graph_service(tmp_path, monkeypatch):
    isolated_store = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_repo_graph_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated_store)
    yield isolated_store
    clear_repo_graph_service_cache()


def test_repo_graph_builds_deep_dive_and_caches_results(tmp_path):
    repo_root = tmp_path / "graph_repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text(
        "\n".join(
            [
                "# Graph Repo",
                "",
                "Build a workflow orchestration platform that turns repository evidence into ranked opportunities.",
                "",
                "- Provides FastAPI endpoints for repo graph deep dives.",
                "- Automates GitHub connector ingestion and approval routing.",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "graph-repo"',
                'version = "0.1.0"',
                "dependencies = [",
                '  "fastapi>=0.110.0",',
                '  "pydantic>=2.0.0",',
                '  "langgraph>=1.0.0",',
                "]",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "app").mkdir()
    (repo_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "app" / "service.py").write_text(
        "\n".join(
            [
                "from .connectors.github import sync_repo",
                "",
                "def build_graph_snapshot() -> dict:",
                '    return {"status": "ok", "source": sync_repo()}',
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "app" / "api.py").write_text(
        "\n".join(
            [
                "from fastapi import APIRouter",
                "from .service import build_graph_snapshot",
                "",
                "router = APIRouter()",
                "",
                '@router.get("/repo-graph/deep-dive")',
                "def read_graph():",
                "    # TODO: add retry telemetry for connector failures",
                "    return build_graph_snapshot()",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "app" / "connectors").mkdir()
    (repo_root / "app" / "connectors" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "app" / "connectors" / "github.py").write_text(
        "\n".join(
            [
                "def sync_repo() -> str:",
                '    return "github"',
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "test_api.py").write_text(
        "from app.api import read_graph\n",
        encoding="utf-8",
    )
    (repo_root / ".git").mkdir()

    payload = {
        "source": str(repo_root),
        "trigger": "promoted",
        "issue_texts": [
            "GitHub connector sync fails after OAuth callback and breaks ingest reliability.",
            "Setup docs do not explain how to run the repo graph locally.",
        ],
        "max_files": 40,
    }

    response = client.post("/orchestrate/repo-graph/analyze", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["cache_hit"] is False
    assert result["trigger"] == "promoted"
    assert result["stats"]["node_count"] > 0
    assert result["stats"]["edge_count"] > 0
    assert result["stats"]["community_count"] > 0
    assert result["repo_dna_profile"]["adjacent_product_opportunities"]
    kinds = {node["kind"] for node in result["nodes"]}
    assert {"repo", "package", "file", "domain", "problem", "claim", "founder_interest"} <= kinds
    assert any(edge["kind"] == "imports" for edge in result["edges"])
    assert any(edge["kind"] == "defines_api" for edge in result["edges"])
    assert any(community["title"] == "workflow-automation" for community in result["communities"])
    assert result["deep_dive"]["startup_territories"]
    assert result["deep_dive"]["evidence_trails"]
    assert any("Pain cluster visible" in item for item in result["deep_dive"]["why_now"])

    graph_id = result["graph_id"]
    listed = client.get("/orchestrate/repo-graph/results?limit=10")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["graph_id"] == graph_id

    fetched = client.get(f"/orchestrate/repo-graph/results/{graph_id}")
    assert fetched.status_code == 200
    assert fetched.json()["repo_name"] == "graph_repo"

    cached = client.post("/orchestrate/repo-graph/analyze", json=payload)
    assert cached.status_code == 200
    assert cached.json()["cache_hit"] is True
