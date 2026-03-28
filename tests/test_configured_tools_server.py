"""Regression coverage for configured-tools MCP server behavior."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

_ORIGINAL_ARGV = list(sys.argv)
os.environ.setdefault("CONFIGURED_TOOLS_PAYLOAD", "")
sys.argv = [sys.argv[0]]
import mcp_servers.configured_tools_server as configured_tools_server
sys.argv = _ORIGINAL_ARGV


def test_shell_tool_uses_configured_command_template_when_no_command_argument():
    tool_cfg = {
        "id": "local_probe",
        "name": "Local Probe",
        "tool_type": "shell",
        "config": {
            "command_template": "curl -s https://example.com?q={input}",
            "description": "Run a probe",
        },
    }

    with patch.object(
        configured_tools_server.shell_exec,
        "execute",
        new=AsyncMock(return_value="[shell] ok"),
    ) as mock_execute:
        result = asyncio.run(
            configured_tools_server._call_shell(
                tool_cfg,
                {"input": "health", "workdir": "/tmp/probe"},
            )
        )

    mock_execute.assert_awaited_once_with(
        command="curl -s https://example.com?q=health",
        workdir="/tmp/probe",
    )
    assert result == "[local_probe] ok"
