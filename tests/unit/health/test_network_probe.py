from __future__ import annotations

from pathlib import Path

import pytest

from neuroca.monitoring.health import probes
from neuroca.monitoring.health.probes import NetworkHealthProbe


def test_sanitize_ping_target_accepts_ip():
    assert NetworkHealthProbe._sanitize_ping_target("127.0.0.1") == "127.0.0.1"


def test_sanitize_ping_target_rejects_whitespace():
    with pytest.raises(ValueError):
        NetworkHealthProbe._sanitize_ping_target("bad host")


def test_ping_target_rejects_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = NetworkHealthProbe(targets=[])

    def fail_execute(cls, command, *, timeout):  # pragma: no cover
        raise AssertionError("ping execution should not be attempted for invalid targets")

    monkeypatch.setattr(NetworkHealthProbe, "_execute_ping", classmethod(fail_execute))

    result = probe._ping_target("example.com && rm -rf /")

    assert result["reachable"] is False
    assert result["avg_latency_ms"] is None
    assert result["packet_loss_percent"] == 100.0
    assert "error" in result


def test_ping_target_builds_safe_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    probe = NetworkHealthProbe(targets=[], timeout_seconds=2.0, packet_count=4)

    recorded: dict[str, list[str]] = {}

    def fake_execute(cls, command, *, timeout):
        recorded["command"] = list(command)

        class Result:
            stdout = "4 packets received, 0% packet loss\naverage =10ms"

        return Result()

    ping_executable = tmp_path / "ping"
    ping_executable.touch()

    monkeypatch.setattr(NetworkHealthProbe, "_execute_ping", classmethod(fake_execute))
    monkeypatch.setattr(probes.platform, "system", lambda: "Linux")
    monkeypatch.setattr(probes.shutil, "which", lambda _: ping_executable.as_posix())

    result = probe._ping_target("example.com")

    expected_timeout = str(max(1, int(probe.timeout_seconds)))
    assert recorded["command"] == [
        ping_executable.as_posix(),
        "-c",
        str(probe.packet_count),
        "-W",
        expected_timeout,
        "example.com",
    ]
    assert result["reachable"] is True
    assert result["avg_latency_ms"] == 10.0
    assert result["packet_loss_percent"] == 0.0


def test_validate_prepared_ping_command_sanitizes_arguments(tmp_path: Path) -> None:
    ping_executable = tmp_path / "ping"
    ping_executable.touch()

    sanitized = NetworkHealthProbe._validate_prepared_ping_command(
        [
            ping_executable.as_posix(),
            "-c",
            "4",
            "-W",
            "5",
            "example.com",
        ]
    )

    assert sanitized == [
        ping_executable.as_posix(),
        "-c",
        "4",
        "-W",
        "5",
        "example.com",
    ]


def test_validate_prepared_ping_command_rejects_invalid_count(tmp_path: Path) -> None:
    ping_executable = tmp_path / "ping"
    ping_executable.touch()

    with pytest.raises(ValueError):
        NetworkHealthProbe._validate_prepared_ping_command(
            [
                ping_executable.as_posix(),
                "-c",
                "not-a-number",
                "-W",
                "5",
                "example.com",
            ]
        )


def test_validate_prepared_ping_command_rejects_short_command(tmp_path: Path) -> None:
    ping_executable = tmp_path / "ping"
    ping_executable.touch()

    with pytest.raises(ValueError):
        NetworkHealthProbe._validate_prepared_ping_command([ping_executable.as_posix()])
