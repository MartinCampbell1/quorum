"""Regression coverage for tool-config store guardrails."""

import json

import pytest

import orchestrator.tool_configs as tool_configs
from orchestrator.tool_configs import ToolConfig, tool_config_store


def test_tool_config_store_rejects_builtin_override_outside_api():
    original = tool_config_store.get("code_exec")
    assert original is not None

    with pytest.raises(ValueError, match="cannot be replaced"):
        tool_config_store.add(
            ToolConfig(
                id="code_exec",
                name="Overridden Python",
                tool_type="code_exec",
                icon="🐍",
                config={"unsafe": True},
                enabled=False,
            )
        )

    with pytest.raises(ValueError, match="cannot be modified"):
        tool_config_store.update("code_exec", {"name": "Not Allowed"})

    updated = tool_config_store.update(
        "code_exec",
        {
            "validation_status": "valid",
            "last_validation_result": {"ok": True},
        },
    )

    assert updated is not None
    assert updated.validation_status == "valid"
    assert updated.last_validation_result == {"ok": True}

    tool_config_store.update(
        "code_exec",
        {
            "validation_status": original.validation_status,
            "last_validation_result": original.last_validation_result,
        },
    )


def test_tool_config_store_ignores_persisted_builtin_override(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    store_dir = fake_home / ".multi-agent"
    store_dir.mkdir()
    (store_dir / "tool_configs.json").write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "id": "code_exec",
                        "name": "Overridden Python",
                        "tool_type": "code_exec",
                        "icon": "x",
                        "config": {"unsafe": True},
                        "enabled": False,
                    },
                    {
                        "id": "local_probe",
                        "name": "Local Probe",
                        "tool_type": "shell",
                        "icon": "⚡",
                        "config": {"command_template": "echo hi"},
                        "enabled": True,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(tool_configs.Path, "home", classmethod(lambda cls: fake_home))
    isolated_store = tool_configs.ToolConfigStore()

    builtin = isolated_store.get("code_exec")
    assert builtin is not None
    assert builtin.name == "Python"
    assert builtin.enabled is True
    assert builtin.config == {}

    custom = isolated_store.get("local_probe")
    assert custom is not None
    assert custom.tool_type == "shell"
