"""Tests for password helpers used by test factories."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Generator

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "factories" / "passwords.py"
MODULE_SPEC = importlib.util.spec_from_file_location("tests.factories.passwords", MODULE_PATH)

if MODULE_SPEC is None or MODULE_SPEC.loader is None:  # pragma: no cover - defensive
    raise RuntimeError("Unable to load password helpers module")

passwords = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules.setdefault("tests.factories.passwords", passwords)
MODULE_SPEC.loader.exec_module(passwords)


@pytest.fixture(autouse=True)
def clear_password_cache(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure each test starts with a clean password cache."""

    monkeypatch.delenv(passwords.DEFAULT_PASSWORD_ENV_VAR, raising=False)
    passwords.reset_default_user_password_cache()
    yield
    passwords.reset_default_user_password_cache()


def test_get_default_user_password_returns_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should take precedence over generated passwords."""

    expected_password = "EnvSecret!123"
    monkeypatch.setenv(passwords.DEFAULT_PASSWORD_ENV_VAR, expected_password)

    assert passwords.get_default_user_password() == expected_password


def test_get_default_user_password_generates_random_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A secure random password should be generated when no environment variable is set."""

    generated_passwords = []

    def fake_token_urlsafe(length: int = 32) -> str:  # pragma: no cover - length unused in branch
        generated_passwords.append(length)
        return "GeneratedPasswordValue"

    monkeypatch.setattr(passwords.secrets, "token_urlsafe", fake_token_urlsafe)

    assert passwords.get_default_user_password() == "GeneratedPasswordValue"
    # Ensure the value is cached and the generator is not called again.
    assert passwords.get_default_user_password() == "GeneratedPasswordValue"
    assert generated_passwords == [32]
