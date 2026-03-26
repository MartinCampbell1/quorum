"""Regression coverage for checkpoint-safe pause/resume control."""

import asyncio
import time

import orchestrator.modes.creator_critic as creator_critic
from orchestrator.engine import inject_instruction, request_pause, request_resume, run
from orchestrator.models import AgentConfig, store


async def _wait_for_status(session_id: str, expected: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = store.get(session_id)
        if session and session["status"] == expected:
            return session
        await asyncio.sleep(0.02)
    session = store.get(session_id)
    raise AssertionError(f"Session {session_id} did not reach status '{expected}'. Last session: {session}")


def test_creator_critic_supports_pause_resume_and_instruction_injection(monkeypatch):
    prompts: list[tuple[str, str]] = []

    def fake_call_agent_cfg(agent: dict, prompt: str) -> str:
        prompts.append((agent["role"], prompt))
        if agent["role"] == "creator":
            return "Draft analysis"
        return "APPROVED"

    monkeypatch.setattr(creator_critic, "call_agent_cfg", fake_call_agent_cfg)

    async def scenario() -> None:
        session_id = await run(
            mode="creator_critic",
            task="Review the BTC trading plan",
            agents=[
                AgentConfig(role="creator", provider="claude", tools=[]),
                AgentConfig(role="critic", provider="claude", tools=[]),
            ],
            config={"max_iterations": 2},
        )

        assert request_pause(session_id) is True

        paused = await _wait_for_status(session_id, "paused")
        assert paused["current_checkpoint_id"] == "cp_1"
        assert paused["checkpoints"][0]["next_node"] == "critic_evaluates"

        queued = inject_instruction(session_id, "Pay extra attention to recent Bitcoin news and volatility.")
        assert queued == 1
        assert store.get(session_id)["pending_instructions"] == 1

        assert request_resume(session_id) is True

        completed = await _wait_for_status(session_id, "completed")
        assert completed["pending_instructions"] == 0
        assert len(completed["checkpoints"]) >= 2
        assert any(message["agent_id"] == "user" for message in completed["messages"])
        assert "Pay extra attention to recent Bitcoin news and volatility." in prompts[-1][1]

    asyncio.run(scenario())
