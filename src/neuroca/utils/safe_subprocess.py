"""Hardened helpers for invoking subprocesses safely."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "UnsafeSubprocessError",
    "normalize_command",
    "run_validated_command",
]


class UnsafeSubprocessError(ValueError):
    """Raised when a subprocess command fails validation."""


def normalize_command(command: Sequence[str]) -> tuple[str, ...]:
    """Return an immutable, sanitized command tuple suitable for ``subprocess``."""

    if not command:
        raise UnsafeSubprocessError("Command must contain at least one component.")

    normalized: list[str] = []
    for index, part in enumerate(command):
        if not isinstance(part, str):
            raise UnsafeSubprocessError(
                f"Command component at position {index} is not a string."
            )
        if not part:
            raise UnsafeSubprocessError(
                f"Command component at position {index} must not be empty."
            )
        if "\x00" in part:
            raise UnsafeSubprocessError(
                f"Command component at position {index} contains NUL bytes."
            )
        if any(control in part for control in ("\r", "\n")):
            raise UnsafeSubprocessError(
                f"Command component at position {index} contains control characters."
            )
        normalized.append(part)

    return tuple(normalized)


def _sanitize_environment(env: Mapping[str, Any] | None) -> dict[str, str] | None:
    if env is None:
        return None

    sanitized: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not key:
            raise UnsafeSubprocessError(
                "Environment variable keys must be non-empty strings."
            )
        if "\x00" in key:
            raise UnsafeSubprocessError(
                "Environment variable keys cannot contain NUL bytes."
            )

        str_value = os.fspath(value) if isinstance(value, os.PathLike) else str(value)
        if "\x00" in str_value:
            raise UnsafeSubprocessError(
                "Environment variable values cannot contain NUL bytes."
            )
        sanitized[key] = str_value

    return sanitized


def run_validated_command(
    command: Sequence[str],
    *,
    check: bool = False,
    capture_output: bool | None = None,
    text: bool | None = None,
    timeout: float | None = None,
    env: Mapping[str, Any] | None = None,
) -> subprocess.CompletedProcess[Any]:
    """Execute a validated command with ``shell=False`` enforced."""

    normalized_command = normalize_command(command)
    sanitized_env = _sanitize_environment(env)

    if timeout is not None and timeout <= 0:
        raise UnsafeSubprocessError("Timeout must be greater than zero when provided.")

    run_kwargs: dict[str, Any] = {
        "check": check,
        "shell": False,
    }
    if capture_output is not None:
        run_kwargs["capture_output"] = capture_output
    if text is not None:
        run_kwargs["text"] = text
    if timeout is not None:
        run_kwargs["timeout"] = timeout
    if sanitized_env is not None:
        run_kwargs["env"] = sanitized_env

    return subprocess.run(normalized_command, **run_kwargs)
