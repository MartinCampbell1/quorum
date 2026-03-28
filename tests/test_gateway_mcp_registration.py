"""Regression coverage for MCP registration details in the gateway."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import gateway
from orchestrator.tool_configs import ToolConfig, tool_config_store


def test_codex_http_mcp_registration_uses_bearer_env_var_for_native_flow():
    tool = ToolConfig(
        id="stitch_mcp",
        name="Stitch MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "http", "url": "https://stitch.googleapis.com/mcp", "headers": "{\"Authorization\": \"Bearer secret-token\"}"},
        enabled=True,
    )
    tool_config_store.add(tool)
    gateway.BOOTSTRAPPED_MCP_SERVERS.clear()
    env = {"CODEX_HOME": "/tmp/codex_native_http_test"}

    try:
        with patch("gateway.run_cli", new=AsyncMock(return_value=("", "", 0))) as mock_run:
            asyncio.run(gateway.ensure_registered_mcp_servers("codex", env, ["stitch_mcp"]))

        cmd = mock_run.await_args.args[0]
        assert cmd[:5] == ["codex", "mcp", "add", "stitch_mcp", "--url"]
        assert "--bearer-token-env-var" in cmd
        env_var_name = cmd[cmd.index("--bearer-token-env-var") + 1]
        assert env_var_name.startswith("CODEX_MCP_BEARER_STITCH_MCP")
        assert env[env_var_name] == "secret-token"
    finally:
        tool_config_store.delete("stitch_mcp")
        gateway.BOOTSTRAPPED_MCP_SERVERS.clear()


def test_call_agent_cleans_claude_temp_mcp_files_for_native_configured_tools(tmp_path):
    tool = ToolConfig(
        id="market_api",
        name="Market API",
        tool_type="custom_api",
        icon="🔧",
        config={"base_url": "https://api.example.com/v1"},
        enabled=True,
    )
    tool_config_store.add(tool)
    created_paths = []

    def fake_write_temp_json(payload: dict, prefix: str) -> str:
        path = tmp_path / f"{prefix}{len(created_paths)}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        created_paths.append(path)
        return str(path)

    try:
        with (
            patch("gateway._write_temp_json", side_effect=fake_write_temp_json),
            patch("gateway.run_cli", new=AsyncMock(return_value=('{"result":"ok"}', "", 0))),
            patch.dict(gateway.pools, {}, clear=True),
        ):
            result = asyncio.run(
                gateway.call_agent(
                    "claude",
                    "Inspect the configured tool cleanup path",
                    mcp_tools=["market_api"],
                )
            )

        assert result["success"] is True
        assert created_paths
        assert all(
            path.name.startswith("configured_tools_") or path.name.startswith("mcp_")
            for path in created_paths
        )
        assert all(not path.exists() for path in created_paths)
    finally:
        tool_config_store.delete("market_api")


def test_call_agent_clears_codex_bootstrap_cache_for_isolated_home(tmp_path):
    source_home = tmp_path / "codex_source"
    source_home.mkdir()
    (source_home / "config.toml").write_text('cli_auth_credentials_store = "file"\n', encoding="utf-8")

    tool = ToolConfig(
        id="codex_native_mcp",
        name="Codex Native MCP",
        tool_type="mcp_server",
        icon="🔌",
        config={"transport": "http", "url": "https://example.com/mcp", "headers": "{\"Authorization\": \"Bearer token\"}"},
        enabled=True,
    )
    tool_config_store.add(tool)
    gateway.BOOTSTRAPPED_MCP_SERVERS.clear()

    try:
        with (
            patch("gateway.default_env", return_value={"CODEX_HOME": str(source_home)}),
            patch("gateway.run_cli", new=AsyncMock(side_effect=[("", "", 0), ("ok", "", 0)])),
            patch.dict(gateway.pools, {}, clear=True),
        ):
            result = asyncio.run(
                gateway.call_agent(
                    "codex",
                    "Run through native MCP bootstrap cleanup",
                    mcp_tools=["codex_native_mcp"],
                )
            )

        assert result["success"] is True
        assert gateway.BOOTSTRAPPED_MCP_SERVERS == set()
    finally:
        tool_config_store.delete("codex_native_mcp")
        gateway.BOOTSTRAPPED_MCP_SERVERS.clear()


def test_custom_shell_tool_routes_through_configured_tools_server(tmp_path):
    tool = ToolConfig(
        id="local_probe",
        name="Local Probe",
        tool_type="shell",
        icon="⚡",
        config={"command_template": "curl -s http://127.0.0.1:8800/health", "description": "Run a local probe"},
        enabled=True,
    )
    tool_config_store.add(tool)
    created_paths = []

    def fake_write_temp_json(payload: dict, prefix: str) -> str:
        path = tmp_path / f"{prefix}{len(created_paths)}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        created_paths.append(path)
        return str(path)

    try:
        with patch("gateway._write_temp_json", side_effect=fake_write_temp_json):
            config_path, temp_paths = gateway.build_mcp_config(["local_probe"])

        assert config_path is not None
        assert temp_paths
        rendered = json.loads(next(path.read_text(encoding="utf-8") for path in created_paths if path.name.startswith("mcp_")))
        assert "configured-tools" in rendered["mcpServers"]

        payload = json.loads(next(path.read_text(encoding="utf-8") for path in created_paths if path.name.startswith("configured_tools_")))
        assert payload["tools"][0]["id"] == "local_probe"
        assert payload["tools"][0]["tool_type"] == "shell"
    finally:
        tool_config_store.delete("local_probe")


def test_call_agent_marks_empty_output_as_failed_even_with_zero_exit_code():
    with (
        patch("gateway.run_cli", new=AsyncMock(return_value=("", "no visible response", 0))),
        patch.dict(gateway.pools, {}, clear=True),
    ):
        result = asyncio.run(
            gateway.call_agent(
                "codex",
                "Produce a final verdict",
            )
        )

    assert result["success"] is False
    assert result["usable_output"] is False
    assert "no visible response" in result["error"]
