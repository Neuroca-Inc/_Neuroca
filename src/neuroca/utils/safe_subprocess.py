"""Hardened helpers for invoking subprocesses safely."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from subprocess import CompletedProcess

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


def _normalize_allowed_executables(
    allowed_executables: Collection[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return canonical allow-lists for absolute paths and executable basenames."""

    allowed_paths: set[str] = set()
    allowed_names: set[str] = set()

    for entry in allowed_executables:
        if not isinstance(entry, str) or not entry:
            raise UnsafeSubprocessError(
                "Allowed executables must be provided as non-empty strings."
            )
        if "\x00" in entry or any(control in entry for control in ("\r", "\n")):
            raise UnsafeSubprocessError(
                "Allowed executable definitions cannot contain control characters."
            )

        candidate = Path(entry)
        if candidate.is_absolute():
            allowed_paths.add(os.fspath(candidate))
            continue

        if os.sep in entry or (os.altsep and os.altsep in entry):
            raise UnsafeSubprocessError(
                "Allowed executable names must not contain path separators."
            )
        allowed_names.add(entry.lower())

    if not allowed_paths and not allowed_names:
        raise UnsafeSubprocessError(
            "At least one executable must be explicitly allow-listed before execution."
        )

    return frozenset(allowed_paths), frozenset(allowed_names)


def _ensure_allowed_executable(
    command: tuple[str, ...], allowed_executables: Collection[str]
) -> tuple[str, ...]:
    """Validate that the command's executable is explicitly allow-listed."""

    if not command:
        raise UnsafeSubprocessError("Validated command must not be empty.")

    executable_component = command[0]
    executable_path = Path(executable_component)

    if not executable_path.is_absolute():
        raise UnsafeSubprocessError("Executable path must be absolute.")
    if not executable_path.exists():
        raise UnsafeSubprocessError("Executable path does not exist.")
    if not executable_path.is_file():
        raise UnsafeSubprocessError("Executable path must reference a file.")

    allowed_paths, allowed_names = _normalize_allowed_executables(allowed_executables)
    sanitized_executable = os.fspath(executable_path)
    canonical_name = executable_path.name.lower()

    if sanitized_executable not in allowed_paths and canonical_name not in allowed_names:
        raise UnsafeSubprocessError(
            f"Executable '{sanitized_executable}' is not permitted for execution."
        )

    if sanitized_executable == executable_component:
        return command

    sanitized_command = list(command)
    sanitized_command[0] = sanitized_executable
    return tuple(sanitized_command)


def _invoke_subprocess(
    command: tuple[str, ...],
    run_kwargs: Mapping[str, Any],
) -> CompletedProcess[Any]:
    """Invoke ``subprocess.run`` using the sanitized command and options."""

    options = dict(run_kwargs)
    options["args"] = command
    return subprocess.run(**options)


def run_validated_command(
    command: Sequence[str],
    *,
    allowed_executables: Collection[str],
    check: bool = False,
    capture_output: bool | None = None,
    text: bool | None = None,
    timeout: float | None = None,
    env: Mapping[str, Any] | None = None,
) -> CompletedProcess[Any]:
    """Execute a validated command with ``shell=False`` enforced.

    Args:
        command: Candidate command sequence to execute.
        allowed_executables: Explicit allow-list of absolute paths or executable
            basenames permitted for execution.
        check: Propagate ``CalledProcessError`` on non-zero exit when true.
        capture_output: Capture stdout/stderr when set.
        text: Request text-mode streams when set.
        timeout: Maximum duration to wait for the process to finish.
        env: Optional environment overrides to provide the subprocess.
    """

    normalized_command = normalize_command(command)
    normalized_command = _ensure_allowed_executable(normalized_command, allowed_executables)
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

    return _invoke_subprocess(normalized_command, run_kwargs)
