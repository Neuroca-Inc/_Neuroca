"""Regression coverage for soak-test audit behaviour under load."""

from __future__ import annotations

import pytest

from tests.performance.memory.soak import run_soak_test


@pytest.mark.asyncio
async def test_soak_reports_unique_audit_ids_and_no_errors() -> None:
    """Run a short soak-test sample and assert audit events remain stable.

    The harness is exercised for a brief interval to simulate production
    traffic while remaining CI friendly. The resulting report must indicate
    that:

    * the exporter recorded at least one audit event,
    * no duplicate identifiers were emitted (idempotency holds), and
    * the workload finished without surfacing runtime errors.
    """

    report = await run_soak_test(duration_seconds=5.0, batch_size=8, seed=2025)

    assert report.audit_event_count > 0
    assert report.duplicate_event_ids == 0
    assert report.errors == []
    assert report.restore_valid is True
