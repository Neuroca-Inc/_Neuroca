"""Command-line entry point for the memory soak-test harness."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional, Sequence

if __package__ is None:
    import sys

    current_dir = Path(__file__).resolve().parent
    package_root = current_dir
    if str(package_root) not in sys.path:
        sys.path.append(str(package_root))
    from soak import SoakTestReport, run_soak_test
else:
    from .soak import SoakTestReport, run_soak_test


def _configure_logging(*, verbose: bool) -> None:
    """Configure logging verbosity for soak-test execution.

    Args:
        verbose: When ``True``, keep soak/audit logs at INFO; otherwise clamp
            them to WARNING to reduce console noise.
    """

    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level)
    for logger_name in (
        'tests.performance.memory.soak.audit',
        'neuroca.memory',
    ):
        logging.getLogger(logger_name).setLevel(level)

def _format_report(report: SoakTestReport) -> str:
    """Render a human-readable summary for ``report``.

    Args:
        report: Soak-test report produced by :func:`run_soak_test`.

    Returns:
        Multi-line string summarising the most relevant metrics.
    """

    decay_summary = ", ".join(f"{tier}:{count}" for tier, count in report.decay_events.items())
    error_summary = "; ".join(report.errors) if report.errors else "none"
    backup_note = (
        f"snapshot saved to {report.backup_path}" if report.backup_path else "snapshot used temporary directory"
    )
    return (
        "Soak Test Report\n"
        f"  duration ............. {report.duration_seconds:.2f}s\n"
        f"  operations ........... {report.operations_performed}\n"
        f"  cycles ............... {report.maintenance_cycles}\n"
        f"  promotions ........... {report.promotions} ({report.promotions_per_second:.3f}/s)\n"
        f"  decay events ......... {decay_summary or 'none'}\n"
        f"  backlog age .......... {report.backlog_age_seconds:.2f}s\n"
        f"  audit events ......... {report.audit_event_count}\n"
        f"  duplicate ids ........ {report.duplicate_event_ids}\n"
        f"  backup/restore ....... {'ok' if report.restore_valid else 'failed'} ({backup_note})\n"
        f"  errors ............... {error_summary}"
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the soak-test script.

    Args:
        argv: Optional sequence overriding :data:`sys.argv` for testing.

    Returns:
        Namespace containing parsed command-line options.
    """

    parser = argparse.ArgumentParser(description="Run the NeuroCA memory soak test harness")
    parser.add_argument("--duration", type=float, default=30.0, help="Runtime in seconds for the soak test")
    parser.add_argument("--batch-size", type=int, default=12, help="Number of memories to create per batch")
    parser.add_argument("--seed", type=int, default=1337, help="Random seed for deterministic workloads")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Optional directory where the JSON snapshot will be preserved",
    )
    parser.add_argument(
        "--verbose-logs",
        action="store_true",
        help="Emit verbose audit logs during the run",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point for executing the soak harness.

    Args:
        argv: Optional argument list supplied by tests.

    Returns:
        Zero on success and one on failure.
    """

    args = _parse_args(argv)
    _configure_logging(verbose=args.verbose_logs)
    try:
        report = asyncio.run(
            run_soak_test(
                duration_seconds=max(0.0, args.duration),
                batch_size=max(1, args.batch_size),
                seed=args.seed,
                backup_dir=args.backup_dir,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Soak test failed: {exc}")
        return 1

    print(_format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
