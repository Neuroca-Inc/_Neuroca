from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

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

    def fake_run(cmd: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["cmd"] = cmd
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    env = {"HOME": Path("/tmp/sandbox"), "FLAG": "1"}
    result = run_validated_command(
        ["/bin/echo", "hello"],
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
    assert isinstance(result, subprocess.CompletedProcess)


def test_run_validated_command_rejects_non_positive_timeout() -> None:
    with pytest.raises(UnsafeSubprocessError):
        run_validated_command(["/bin/echo", "hello"], timeout=0)
