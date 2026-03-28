import pytest

from langchain_gateway import GatewayInvocationError, _coerce_gateway_output


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
