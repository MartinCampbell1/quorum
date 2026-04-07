"""Regression coverage for the research sensing pipeline."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import orchestrator.api as orchestrator_api
from orchestrator.api import router
from orchestrator.models import SessionStore
from orchestrator.research.pipeline import ResearchPipeline
from orchestrator.research.search_index import ResearchIndex, clear_research_index_cache
from orchestrator.research.source_models import ResearchObservation
from orchestrator.shared_contracts import Confidence


app = FastAPI()
app.include_router(router)
client = TestClient(app)


class FakeGitHubScanner:
    source = "github"

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24):
        items = [
            ResearchObservation(
                source="github",
                entity="coderamp-labs/gitingest",
                query=query,
                url="https://github.com/coderamp-labs/gitingest",
                raw_text="Prompt-friendly repo digest with strong recent momentum.",
                topic_tags=["repo", "digest", "github"],
                pain_score=0.35,
                trend_score=0.81,
                evidence_confidence=Confidence.HIGH,
                metadata={"stars": 1200, "forks": 88},
            ),
            ResearchObservation(
                source="github",
                entity="pingcap/ossinsight",
                query=query,
                url="https://github.com/pingcap/ossinsight",
                raw_text="Open source analytics and trending repo insight surface.",
                topic_tags=["analytics", "github", "trending"],
                pain_score=0.24,
                trend_score=0.74,
                evidence_confidence=Confidence.MEDIUM,
                metadata={"stars": 950, "forks": 54},
            ),
        ]
        return items[:max_items]


@pytest.fixture(autouse=True)
def isolated_research_pipeline(tmp_path, monkeypatch):
    isolated_store = SessionStore(db_path=str(tmp_path / "state.db"))
    index = ResearchIndex(str(tmp_path / "research.db"))
    pipeline = ResearchPipeline(index=index, scanners={"github": FakeGitHubScanner()})
    clear_research_index_cache()
    monkeypatch.setattr(orchestrator_api, "store", isolated_store)
    monkeypatch.setattr(orchestrator_api, "_research_index", lambda: index)
    monkeypatch.setattr(orchestrator_api, "_research_pipeline", lambda: pipeline)
    yield index, pipeline
    clear_research_index_cache()


def test_research_scan_observations_queue_and_exports_work():
    run_response = client.post(
        "/orchestrate/research/scan",
        json={"query": "repo digest", "sources": ["github"], "max_items_per_source": 2},
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["observation_count"] == 2

    observations_response = client.get("/orchestrate/research/observations?limit=10")
    assert observations_response.status_code == 200
    observations = observations_response.json()["items"]
    assert len(observations) == 2

    search_response = client.get("/orchestrate/research/search?q=analytics")
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1

    queue_response = client.get("/orchestrate/research/queue/daily?limit=10")
    assert queue_response.status_code == 200
    queue = queue_response.json()["items"]
    assert len(queue) == 2
    assert queue[0]["priority_score"] >= queue[1]["priority_score"]

    runs_response = client.get("/orchestrate/research/runs")
    assert runs_response.status_code == 200
    assert len(runs_response.json()["items"]) == 1

    export_jsonl = client.get("/orchestrate/research/exports/jsonl?limit=10")
    assert export_jsonl.status_code == 200
    assert "coderamp-labs/gitingest" in export_jsonl.text

    export_md = client.get("/orchestrate/research/exports/daily-queue.md?limit=10")
    assert export_md.status_code == 200
    assert "# Research Daily Queue" in export_md.text
