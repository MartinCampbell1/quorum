"""Regression coverage for the fast RepoDNA digest path."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.models import SessionStore
from orchestrator.repodna import clear_repo_dna_service_cache


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_repo_dna_service(tmp_path, monkeypatch):
    isolated_store = SessionStore(db_path=str(tmp_path / "state.db"))
    clear_repo_dna_service_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated_store)
    yield isolated_store
    clear_repo_dna_service_cache()


def test_repo_digest_extracts_profile_and_uses_cache(tmp_path):
    repo_root = tmp_path / "sample_repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text(
        "\n".join(
            [
                "# Sample Repo",
                "",
                "Build a repo-aware workflow tool for operators who need compact context fast.",
                "",
                "- Automates research queue triage and repository digestion.",
                "- Provides a typed API for workflow evidence and approvals.",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "sample-repo",
                "dependencies": {
                    "next": "^15.0.0",
                    "react": "^19.0.0",
                    "langchain": "^1.0.0",
                },
                "devDependencies": {
                    "tailwindcss": "^4.0.0",
                    "vitest": "^3.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "src").mkdir()
    (repo_root / "src" / "index.ts").write_text(
        "\n".join(
            [
                "import { createQueue } from './pipeline';",
                "import { buildDigest } from './repo';",
                "",
                "export function bootstrapWorkflow() {",
                "  // TODO: retry failed connector syncs before surfacing alerts",
                "  return createQueue(buildDigest());",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "src" / "pipeline.ts").write_text(
        "\n".join(
            [
                "import { gatherSignals } from './signals';",
                "import { scoreQueue } from './scoring';",
                "import { persistEvidence } from './storage';",
                "",
                "export function createQueue(seed: unknown) {",
                "  return { seed, items: [gatherSignals(), scoreQueue(), persistEvidence()] };",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "pipeline.test.ts").write_text(
        "import { describe, expect, it } from 'vitest';\n",
        encoding="utf-8",
    )

    payload = {
        "source": str(repo_root),
        "issue_texts": [
            "GitHub connector sync fails during OAuth callback and needs better retries.",
            "Docs do not explain local setup for new contributors.",
        ],
        "max_files": 50,
        "hot_file_limit": 4,
    }

    first = client.post("/orchestrate/repo-digest/analyze", json=payload)
    assert first.status_code == 200
    result = first.json()
    assert result["cache_hit"] is False
    assert result["digest"]["repo_name"] == "sample_repo"
    assert "next.js" in result["digest"]["tech_stack"]
    assert "langchain" in result["digest"]["tech_stack"]
    assert "developer-tools" in result["digest"]["dominant_domains"]
    assert "workflow-automation" in result["digest"]["dominant_domains"]
    assert result["digest"]["readme_claims"]
    assert any(item["path"] == "src/index.ts" for item in result["digest"]["hot_files"])
    assert any(theme["label"] == "integration-friction" for theme in result["digest"]["issue_themes"])
    assert result["profile"]["ranking_priors"]
    assert "Repeated builds:" in result["profile"]["idea_generation_context"]
    assert "Hot files:" in result["profile"]["idea_generation_context"]

    profile_id = result["profile"]["profile_id"]

    listed = client.get("/orchestrate/repo-digest/profiles?limit=10")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["profile_id"] == profile_id

    profile = client.get(f"/orchestrate/repo-digest/profiles/{profile_id}")
    assert profile.status_code == 200
    assert profile.json()["repo_name"] == "sample_repo"

    full_result = client.get(f"/orchestrate/repo-digest/results/{profile_id}")
    assert full_result.status_code == 200
    assert full_result.json()["digest"]["repo_name"] == "sample_repo"

    cached = client.post("/orchestrate/repo-digest/analyze", json=payload)
    assert cached.status_code == 200
    assert cached.json()["cache_hit"] is True
