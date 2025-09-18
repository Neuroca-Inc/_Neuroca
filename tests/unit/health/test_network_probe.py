import pytest

from neuroca.monitoring.health import probes
from neuroca.monitoring.health.probes import NetworkHealthProbe


def test_sanitize_ping_target_accepts_ip():
    assert NetworkHealthProbe._sanitize_ping_target("127.0.0.1") == "127.0.0.1"


def test_sanitize_ping_target_rejects_whitespace():
    with pytest.raises(ValueError):
        NetworkHealthProbe._sanitize_ping_target("bad host")


def test_ping_target_rejects_injection(monkeypatch):
    probe = NetworkHealthProbe(targets=[])

    def fail_run(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("subprocess.run should not be called for invalid targets")

    monkeypatch.setattr(probes.subprocess, "run", fail_run)

    result = probe._ping_target("example.com && rm -rf /")

    assert result["reachable"] is False
    assert result["avg_latency_ms"] is None
    assert result["packet_loss_percent"] == 100.0
    assert "error" in result


def test_ping_target_builds_safe_command(monkeypatch):
    probe = NetworkHealthProbe(targets=[], timeout_seconds=2.0, packet_count=4)

    recorded = {}

    def fake_run(command, capture_output, text, timeout):
        recorded["command"] = command

        class Result:
            stdout = "4 packets received, 0% packet loss\naverage =10ms"

        return Result()

    monkeypatch.setattr(probes.subprocess, "run", fake_run)
    monkeypatch.setattr(probes.platform, "system", lambda: "Linux")

    result = probe._ping_target("example.com")

    assert recorded["command"] == ["ping", "-c", "4", "-W", "2000", "example.com"]
    assert result["reachable"] is True
    assert result["avg_latency_ms"] == 10.0
    assert result["packet_loss_percent"] == 0.0
