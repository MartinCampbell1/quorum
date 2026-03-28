"""Coverage for account management endpoints exposed by the gateway."""

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import gateway
from provider_sessions import set_account_label


def _create_profile_tree(base: Path) -> None:
    codex = base / "codex" / "acc1"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
    (codex / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}), encoding="utf-8")

    gemini = base / "gemini" / "acc1" / "home" / ".gemini"
    gemini.mkdir(parents=True)
    (gemini / "settings.json").write_text("{}", encoding="utf-8")


def test_accounts_endpoint_returns_profiles_and_labels(tmp_path: Path):
    profiles_dir = tmp_path / ".cli-profiles"
    _create_profile_tree(profiles_dir)
    set_account_label(profiles_dir, "codex", "acc1", "main@company.com")

    with patch.object(gateway, "PROFILES_DIR", profiles_dir):
        with TestClient(gateway.app) as client:
            response = client.get("/accounts")

    assert response.status_code == 200
    payload = response.json()["accounts"]
    assert payload["codex"][0]["name"] == "acc1"
    assert payload["codex"][0]["label"] == "main@company.com"
    assert payload["codex"][0]["display_name"] == "main@company.com"
    assert payload["gemini"][0]["name"] == "acc1"
    assert payload["claude"] == []


def test_accounts_label_endpoint_updates_metadata(tmp_path: Path):
    profiles_dir = tmp_path / ".cli-profiles"
    _create_profile_tree(profiles_dir)

    with patch.object(gateway, "PROFILES_DIR", profiles_dir):
        with TestClient(gateway.app) as client:
            response = client.patch("/accounts/codex/acc1", json={"label": "backup login"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "backup login"
    assert payload["accounts"][0]["display_name"] == "backup login"


def test_accounts_open_login_endpoint_returns_command():
    with patch("gateway.open_login_terminal", return_value="codex login"):
        with TestClient(gateway.app) as client:
            response = client.post("/accounts/codex/open-login")

    assert response.status_code == 200
    assert response.json()["command"] == "codex login"


def test_accounts_import_endpoint_reports_new_account():
    with (
        patch("gateway.import_current_session", return_value="acc3"),
        patch("gateway._accounts_payload", return_value={"codex": [{"name": "acc3", "display_name": "acc3", "available": True, "requests_made": 0, "cooldown_remaining_sec": 0}], "claude": [], "gemini": []}),
    ):
        with TestClient(gateway.app) as client:
            response = client.post("/accounts/codex/import")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_name"] == "acc3"
    assert payload["accounts"][0]["name"] == "acc3"


def test_accounts_reauthorize_endpoint_requires_existing_account(tmp_path: Path):
    profiles_dir = tmp_path / ".cli-profiles"
    _create_profile_tree(profiles_dir)

    with patch.object(gateway, "PROFILES_DIR", profiles_dir):
        with TestClient(gateway.app) as client:
            response = client.post("/accounts/codex/acc9/reauthorize")

    assert response.status_code == 404


def test_accounts_reauthorize_opens_profile_specific_terminal(tmp_path: Path):
    profiles_dir = tmp_path / ".cli-profiles"
    _create_profile_tree(profiles_dir)

    with (
        patch.object(gateway, "PROFILES_DIR", profiles_dir),
        patch("gateway.open_login_terminal_for_profile", return_value="gemini") as mock_open,
    ):
        with TestClient(gateway.app) as client:
            response = client.post("/accounts/gemini/acc1/reauthorize")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_name"] == "acc1"
    assert "Complete login there" in payload["message"]
    mock_open.assert_called_once()


def test_accounts_reload_probes_auth_state(tmp_path: Path):
    profiles_dir = tmp_path / ".cli-profiles"
    _create_profile_tree(profiles_dir)
    claude_home = profiles_dir / "claude" / "acc1" / "home" / ".claude"
    claude_home.mkdir(parents=True)
    (claude_home / "settings.json").write_text("{}", encoding="utf-8")

    async def fake_run_cli(cmd, workdir, timeout, env):
        if cmd[:3] == ["codex", "login", "status"]:
            return ("Logged in using ChatGPT", "", 0)
        if cmd[:3] == ["claude", "auth", "status"]:
            return (json.dumps({"loggedIn": True, "email": "user@example.com"}), "", 0)
        if cmd and cmd[0] == "gemini":
            return (
                json.dumps(
                    {
                        "session_id": "sess",
                        "error": {
                            "message": "Please set an Auth method in settings.json",
                            "code": 41,
                        },
                    }
                ),
                "",
                41,
            )
        raise AssertionError(cmd)

    with (
        patch.object(gateway, "PROFILES_DIR", profiles_dir),
        patch("gateway.run_cli", side_effect=fake_run_cli),
    ):
        with TestClient(gateway.app) as client:
            response = client.post("/accounts/reload")

    assert response.status_code == 200
    payload = response.json()["accounts"]
    assert payload["codex"][0]["available"] is True
    assert payload["codex"][0]["auth_state"] == "verified"
    assert payload["claude"][0]["available"] is True
    assert payload["claude"][0]["identity"] == "user@example.com"
    assert payload["gemini"][0]["available"] is False
    assert payload["gemini"][0]["auth_state"] == "error"
    assert "Auth method" in payload["gemini"][0]["last_error"]
