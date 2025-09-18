"""Tests for hardened editor launch logic in the LLM CLI commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from neuroca.cli.commands import llm


def _touch_executable(path: Path) -> str:
    path.touch()
    return path.as_posix()


def test_build_editor_command_allows_whitelisted_editor(tmp_path: Path) -> None:
    editor_path = _touch_executable(tmp_path / "nano")
    config_path = tmp_path / "config.yaml"

    command = llm._build_editor_command([editor_path, "+12"], config_path)

    assert command == [editor_path, "+12", os.path.abspath(os.fspath(config_path))]


def test_build_editor_command_rejects_unknown_editor(tmp_path: Path) -> None:
    editor_path = _touch_executable(tmp_path / "custom")
    config_path = tmp_path / "config.yaml"

    with pytest.raises(ValueError):
        llm._build_editor_command([editor_path], config_path)


def test_launch_editor_rejects_missing_config_argument(tmp_path: Path) -> None:
    editor_path = _touch_executable(tmp_path / "nano")

    with pytest.raises(ValueError):
        llm._launch_editor([editor_path])


def test_launch_editor_sanitizes_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    editor_path = _touch_executable(tmp_path / "nano")
    config_path = tmp_path / "llm config.yaml"
    sanitized_command = [editor_path, "+1", os.fspath(config_path)]
    recorded: dict[str, object] = {}

    def fake_run(
        command, *, check, capture_output=None, text=None, timeout=None, env=None
    ):  # type: ignore[no-untyped-def]
        recorded["command"] = command
        recorded["kwargs"] = {
            "capture_output": capture_output,
            "text": text,
            "timeout": timeout,
            "env": env,
        }
        assert check is True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(llm, "run_validated_command", fake_run)

    llm._launch_editor(sanitized_command)

    expected_path = os.path.abspath(os.fspath(config_path))
    assert recorded["command"] == (editor_path, "+1", expected_path)
    assert recorded["kwargs"] == {
        "capture_output": None,
        "text": None,
        "timeout": None,
        "env": None,
    }


def test_launch_editor_rejects_unsafe_argument(tmp_path: Path) -> None:
    editor_path = _touch_executable(tmp_path / "nano")
    config_path = tmp_path / "config.yaml"

    with pytest.raises(ValueError):
        llm._build_editor_command([editor_path, "--foo"], config_path)
