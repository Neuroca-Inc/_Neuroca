"""Circuit breaker logic for maintenance consolidation workloads."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Optional

logger = logging.getLogger(__name__)


def _coerce_positive_int(value: Any) -> int | None:
    """Return ``value`` coerced to a positive integer when possible."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None

    return candidate if candidate > 0 else None


def _coerce_positive_float(value: Any, *, default: float) -> float:
    """Return ``value`` coerced to a positive float, falling back to ``default``."""

    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return max(0.0, default)

    return max(0.0, candidate)


def _extract_consecutive_failures(telemetry: Any) -> int:
    """Best-effort extraction of the consecutive failure count from ``telemetry``."""

    if telemetry is None:
        return 0

    # Support both dataclass-style attributes and mapping-style access used in tests
    candidate: Any
    if hasattr(telemetry, "consecutive_failures"):
        candidate = getattr(telemetry, "consecutive_failures")
    elif isinstance(telemetry, Mapping):
        candidate = telemetry.get("consecutive_failures")
    else:
        candidate = None

    try:
        return int(candidate)
    except (TypeError, ValueError):
        return 0


def _extract_max_queue(snapshot: Mapping[str, Mapping[str, Any]] | None) -> int:
    """Return the largest queued writer count across all tiers in ``snapshot``."""

    if not snapshot:
        return 0

    max_queued = 0
    for tier_snapshot in snapshot.values():
        if not isinstance(tier_snapshot, Mapping):
            continue
        try:
            queued = int(tier_snapshot.get("queued", 0))
        except (TypeError, ValueError):
            queued = 0
        if queued > max_queued:
            max_queued = queued
    return max_queued


@dataclass(slots=True)
class CircuitBreakerDecision:
    """Decision returned after evaluating the maintenance circuit breaker."""

    skip: bool
    reason: str | None = None
    opened_at: float | None = None
    cooldown_expires_at: float | None = None
    details: MutableMapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation of the decision."""

        return {
            "skip": self.skip,
            "reason": self.reason,
            "opened_at": self.opened_at,
            "cooldown_expires_at": self.cooldown_expires_at,
            "details": dict(self.details or {}),
        }


class MaintenanceCircuitBreaker:
    """Trip-and-hold guard that skips consolidation during severe degradation."""

    def __init__(
        self,
        *,
        backlog_threshold: int | None,
        failure_threshold: int | None,
        cooldown_seconds: float,
        log: logging.Logger | None = None,
    ) -> None:
        self._backlog_threshold = backlog_threshold
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = max(0.0, cooldown_seconds)
        self._log = log or logger.getChild("maintenance_breaker")

        self._opened_at: float | None = None
        self._cooldown_expires_at: float | None = None
        self._last_reason: str | None = None

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any] | None,
        *,
        log: logging.Logger | None = None,
    ) -> "MaintenanceCircuitBreaker" | None:
        """Construct a breaker from configuration.

        The breaker is disabled when both thresholds are missing or when the
        configuration explicitly sets ``enabled`` to ``False``.
        """

        config = config or {}
        if isinstance(config, Mapping) and config.get("enabled") is False:
            return None

        backlog_threshold = _coerce_positive_int(config.get("queued_backlog_threshold"))
        failure_threshold = _coerce_positive_int(config.get("failure_threshold"))
        cooldown_seconds = _coerce_positive_float(
            config.get("cooldown_seconds"),
            default=120.0,
        )

        # Provide conservative defaults when at least one guard is enabled.
        if backlog_threshold is None and failure_threshold is None:
            backlog_threshold = _coerce_positive_int(config.get("max_queue"))
            failure_threshold = _coerce_positive_int(config.get("max_failures"))

        if backlog_threshold is None and failure_threshold is None:
            return None

        if backlog_threshold is None:
            backlog_threshold = 0
        if failure_threshold is None:
            failure_threshold = 0

        return cls(
            backlog_threshold=backlog_threshold,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
            log=log,
        )

    @property
    def is_open(self) -> bool:
        """Return ``True`` when the circuit breaker is currently open."""

        return self._cooldown_expires_at is not None and time.time() < self._cooldown_expires_at

    def status(self) -> dict[str, Any]:
        """Expose the breaker status for diagnostics."""

        return {
            "state": "open" if self.is_open else "closed",
            "reason": self._last_reason,
            "opened_at": self._opened_at,
            "cooldown_expires_at": self._cooldown_expires_at,
            "queued_backlog_threshold": self._backlog_threshold,
            "failure_threshold": self._failure_threshold,
            "cooldown_seconds": self._cooldown_seconds,
        }

    def evaluate(
        self,
        *,
        backlog_snapshot: Mapping[str, Mapping[str, Any]] | None,
        telemetry: Any,
        now: Optional[float] = None,
    ) -> CircuitBreakerDecision:
        """Evaluate the breaker state and return the action for this cycle."""

        now = now if now is not None else time.time()
        queued = _extract_max_queue(backlog_snapshot)
        consecutive_failures = _extract_consecutive_failures(telemetry)

        backlog_triggered = bool(self._backlog_threshold and queued >= self._backlog_threshold)
        failure_triggered = bool(
            self._failure_threshold and consecutive_failures >= self._failure_threshold
        )
        triggered = backlog_triggered or failure_triggered

        details: MutableMapping[str, Any] = {
            "queued_backlog": queued,
            "consecutive_failures": consecutive_failures,
        }

        reason_parts: list[str] = []
        if backlog_triggered:
            reason_parts.append(
                f"queued backlog {queued} >= threshold {self._backlog_threshold}"
            )
        if failure_triggered:
            reason_parts.append(
                f"consecutive failures {consecutive_failures} >= threshold {self._failure_threshold}"
            )
        reason = " and ".join(reason_parts) if reason_parts else None

        if self._cooldown_expires_at is not None:
            if triggered:
                # Extend the cooldown window when conditions are still degraded.
                if self._cooldown_seconds > 0:
                    self._cooldown_expires_at = max(
                        self._cooldown_expires_at,
                        now + self._cooldown_seconds,
                    )
                if reason:
                    self._last_reason = reason
                self._log.debug(
                    "Maintenance circuit breaker remains open for %.2fs (%s)",
                    max(0.0, (self._cooldown_expires_at or now) - now),
                    self._last_reason,
                )
                return CircuitBreakerDecision(
                    skip=True,
                    reason=self._last_reason,
                    opened_at=self._opened_at,
                    cooldown_expires_at=self._cooldown_expires_at,
                    details=details,
                )

            if self._cooldown_expires_at <= now:
                self._log.info("Maintenance circuit breaker closed after cooldown")
                self._cooldown_expires_at = None
                self._opened_at = None
                self._last_reason = None
            else:
                return CircuitBreakerDecision(
                    skip=True,
                    reason=self._last_reason,
                    opened_at=self._opened_at,
                    cooldown_expires_at=self._cooldown_expires_at,
                    details=details,
                )

        if triggered:
            self._opened_at = now
            self._last_reason = reason
            self._cooldown_expires_at = now + self._cooldown_seconds if self._cooldown_seconds else now
            self._log.warning(
                "Opening maintenance circuit breaker for consolidation: %s", self._last_reason
            )
            return CircuitBreakerDecision(
                skip=True,
                reason=self._last_reason,
                opened_at=self._opened_at,
                cooldown_expires_at=self._cooldown_expires_at,
                details=details,
            )

        return CircuitBreakerDecision(
            skip=False,
            reason=None,
            opened_at=None,
            cooldown_expires_at=self._cooldown_expires_at,
            details=details,
        )


__all__ = ["CircuitBreakerDecision", "MaintenanceCircuitBreaker"]
