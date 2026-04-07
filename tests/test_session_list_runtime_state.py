from fastapi.testclient import TestClient

from gateway import app
from orchestrator.models import AgentConfig, store


client = TestClient(app)


def test_sessions_list_omits_runtime_state_reason_details():
    session_id = store.create(
        "dictator",
        "Lean list payload",
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
    assert "reasons" not in payload["runtime_state"]
