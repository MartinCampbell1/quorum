"""Regression coverage for provider login/import helpers."""

import json
from pathlib import Path

from provider_sessions import (
    get_account_label,
    import_current_session,
    profile_login_environment,
    provider_login_command,
    set_account_label,
)


def test_import_current_codex_session(tmp_path: Path) -> None:
    home = tmp_path / "home"
    source = home / ".codex"
    source.mkdir(parents=True)
    (source / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}), encoding="utf-8")
    (source / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    name = import_current_session("codex", profiles_dir=profiles_dir, home=home)

    assert name == "acc1"
    assert (profiles_dir / "codex" / "acc1" / "auth.json").exists()


def test_import_current_claude_session(tmp_path: Path) -> None:
    home = tmp_path / "home"
    source = home / ".claude"
    source.mkdir(parents=True)
    (source / "settings.json").write_text("{}", encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    name = import_current_session("claude", profiles_dir=profiles_dir, home=home)

    assert name == "acc1"
    assert (profiles_dir / "claude" / "acc1" / "home" / ".claude" / "settings.json").exists()


def test_import_current_session_can_reauthorize_existing_account(tmp_path: Path) -> None:
    home = tmp_path / "home"
    source = home / ".codex"
    source.mkdir(parents=True)
    (source / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}), encoding="utf-8")
    (source / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    provider_dir = profiles_dir / "codex" / "acc1"
    provider_dir.mkdir(parents=True)
    (provider_dir / "config.toml").write_text('model = "old"\n', encoding="utf-8")

    name = import_current_session("codex", profiles_dir=profiles_dir, home=home, account_name="acc1")

    assert name == "acc1"
    assert (profiles_dir / "codex" / "acc1" / "auth.json").exists()
    assert 'gpt-5.4' in (profiles_dir / "codex" / "acc1" / "config.toml").read_text(encoding="utf-8")


def test_account_labels_round_trip(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "profiles"

    saved = set_account_label(profiles_dir, "codex", "acc2", "main@company.com")
    assert saved == "main@company.com"
    assert get_account_label(profiles_dir, "codex", "acc2") == "main@company.com"

    cleared = set_account_label(profiles_dir, "codex", "acc2", "")
    assert cleared == ""
    assert get_account_label(profiles_dir, "codex", "acc2") == ""


def test_provider_login_command() -> None:
    assert provider_login_command("codex") == ["codex", "login"]
    assert provider_login_command("claude") == ["claude", "auth", "login"]
    assert provider_login_command("gemini") == ["gemini"]


def test_profile_login_environment_targets_specific_profile(tmp_path: Path) -> None:
    codex_profile = tmp_path / "profiles" / "codex" / "acc2"
    codex_profile.mkdir(parents=True)
    codex_env = profile_login_environment("codex", codex_profile, real_home=tmp_path / "real-home")
    assert codex_env["CODEX_HOME"] == str(codex_profile)

    gemini_profile = tmp_path / "profiles" / "gemini" / "acc1"
    gemini_profile.mkdir(parents=True)
    gemini_env = profile_login_environment("gemini", gemini_profile, real_home=tmp_path / "real-home")
    assert gemini_env["HOME"] == str(gemini_profile / "home")
    assert "PATH" in gemini_env
