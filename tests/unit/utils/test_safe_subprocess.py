from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from neuroca.utils import safe_subprocess
from neuroca.utils.safe_subprocess import (
    UnsafeSubprocessError,
    normalize_command,
    run_validated_command,
)


def test_normalize_command_returns_tuple() -> None:
    command = ["/usr/bin/env", "python"]
    normalized = normalize_command(command)
    assert isinstance(normalized, tuple)
    assert normalized == tuple(command)


@pytest.mark.parametrize(
    "command",
    (
        [],
        [""],
        ["valid", ""],
        ["valid", "bad\x00value"],
    ),
)
def test_normalize_command_rejects_invalid(command: list[str]) -> None:
    with pytest.raises(UnsafeSubprocessError):
        normalize_command(command)


def test_run_validated_command_validates_and_executes(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    class _StubCompletedProcess:
        def __init__(self, args, returncode, stdout=None, stderr=None):
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_invoke(cmd: tuple[str, ...], kwargs: Mapping[str, Any]) -> _StubCompletedProcess:
        observed["cmd"] = cmd
        observed["kwargs"] = dict(kwargs)
        return _StubCompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(safe_subprocess, "_invoke_subprocess", fake_invoke)

    env = {"HOME": Path("/tmp/sandbox"), "FLAG": "1"}
    result = run_validated_command(
        ["/bin/echo", "hello"],
        allowed_executables={"echo"},
        check=True,
        capture_output=True,
        text=True,
        timeout=1.5,
        env=env,
    )

    assert observed["cmd"] == ("/bin/echo", "hello")
    kwargs = observed["kwargs"]
    assert kwargs["shell"] is False
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 1.5
    assert kwargs["env"] == {"HOME": os.fspath(env["HOME"]), "FLAG": "1"}
    assert result.returncode == 0


def test_run_validated_command_rejects_non_positive_timeout() -> None:
    with pytest.raises(UnsafeSubprocessError):
        run_validated_command(
            ["/bin/echo", "hello"],
            allowed_executables={"echo"},
            timeout=0,
        )


def test_run_validated_command_rejects_unlisted_executable() -> None:
    with pytest.raises(UnsafeSubprocessError):
        run_validated_command(
            ["/bin/echo", "hello"],
            allowed_executables={"/usr/bin/python"},
        )


def test_run_validated_command_rejects_relative_executable() -> None:
    with pytest.raises(UnsafeSubprocessError):
        run_validated_command(
            ["echo", "hello"],
            allowed_executables={"echo"},
        )
