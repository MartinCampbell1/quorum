import pytest
import httpx

from langchain_core.messages import HumanMessage

from langchain_gateway import (
    GatewayClaude,
    GatewayInvocationError,
    GatewayMiniMax,
    _coerce_gateway_output,
)


def test_gateway_contract_raises_for_unsuccessful_response():
    with pytest.raises(GatewayInvocationError) as excinfo:
        _coerce_gateway_output(
            "codex",
            "critic",
            {
                "success": False,
                "output": "",
                "error": "Provider failed upstream",
                "profile_used": "acc2",
                "retries": 1,
            },
        )

    message = str(excinfo.value)
    assert "[codex:critic]" in message
    assert "Provider failed upstream" in message
    assert "profile=acc2" in message


def test_gateway_contract_rejects_empty_or_scaffold_only_output():
    with pytest.raises(GatewayInvocationError) as excinfo:
        _coerce_gateway_output(
            "codex",
            "critic",
            {
                "success": True,
                "output": "<tool_call><tool_name>Bash</tool_name></tool_call>",
                "profile_used": "default",
                "retries": 0,
            },
        )

    assert "no usable text output" in str(excinfo.value)


def test_minimax_without_openrouter_key_does_not_fall_back_to_claude(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    model = GatewayMiniMax()

    with pytest.raises(GatewayInvocationError) as excinfo:
        model._generate([HumanMessage(content="Say hi")])

    assert "[minimax:agent]" in str(excinfo.value)
    assert "OpenRouter API key is not configured for minimax" in str(excinfo.value)


def test_gateway_model_wraps_transport_timeout_as_gateway_invocation_error(monkeypatch):
    model = GatewayClaude(agent_role="judge")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "Client", FakeClient)

    with pytest.raises(GatewayInvocationError) as excinfo:
        model._generate([HumanMessage(content="Say hi")])

    message = str(excinfo.value)
    assert "[claude:judge]" in message
    assert "Gateway request timed out" in message
