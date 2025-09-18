"""Utilities for configuring backend operation timeouts and retry policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retrying backend operations."""

    attempts: int = 1
    initial_delay_seconds: float = 0.0
    backoff_multiplier: float = 1.0
    max_delay_seconds: float = 0.0

    def normalized_attempts(self) -> int:
        """Return a minimum of one attempt for safety."""

        return max(1, int(self.attempts))

    def compute_delay(self, attempt: int) -> float:
        """Compute the backoff delay for *attempt* (1-indexed)."""

        if attempt <= 0:
            return 0.0

        if attempt == 1:
            delay = self.initial_delay_seconds
        else:
            delay = self.initial_delay_seconds * (self.backoff_multiplier ** (attempt - 1))

        if self.max_delay_seconds > 0:
            delay = min(delay, self.max_delay_seconds)

        return max(0.0, float(delay))


@dataclass(frozen=True)
class BackendOperationPolicy:
    """Encapsulates timeout and retry behaviour for storage backends."""

    timeout_seconds: Optional[float] = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    @classmethod
    def default(cls) -> "BackendOperationPolicy":
        """Return a policy with a single attempt and no timeout."""

        return cls(timeout_seconds=None, retry=RetryPolicy())

    @classmethod
    def from_mapping(
        cls,
        mapping: Optional[Mapping[str, Any] | "BackendOperationPolicy"],
        *,
        fallback: Optional["BackendOperationPolicy"] = None,
    ) -> "BackendOperationPolicy":
        """Build a policy from an arbitrary mapping or reuse an existing policy."""

        if mapping is None:
            return fallback or cls.default()

        if isinstance(mapping, BackendOperationPolicy):
            return mapping

        if not isinstance(mapping, Mapping):
            return fallback or cls.default()

        base = fallback or cls.default()

        timeout = mapping.get("timeout_seconds", mapping.get("operation_timeout_seconds", base.timeout_seconds))
        timeout_value: Optional[float]
        if timeout is None:
            timeout_value = base.timeout_seconds
        else:
            timeout_value = float(timeout)

        retry_section = mapping.get("retry")

        attempts = mapping.get("retry_attempts")
        initial_delay = mapping.get("retry_backoff_seconds", mapping.get("retry_initial_delay_seconds"))
        multiplier = mapping.get("retry_backoff_multiplier")
        max_delay = mapping.get("retry_max_backoff_seconds")

        if isinstance(retry_section, Mapping):
            attempts = retry_section.get("attempts", retry_section.get("retry_attempts", attempts))
            initial_delay = retry_section.get(
                "initial_delay_seconds",
                retry_section.get("backoff_seconds", initial_delay),
            )
            multiplier = retry_section.get("backoff_multiplier", multiplier)
            max_delay = retry_section.get("max_delay_seconds", max_delay)

        retry_policy = RetryPolicy(
            attempts=max(1, int(attempts)) if attempts is not None else base.retry.normalized_attempts(),
            initial_delay_seconds=float(initial_delay) if initial_delay is not None else base.retry.initial_delay_seconds,
            backoff_multiplier=float(multiplier) if multiplier is not None else base.retry.backoff_multiplier,
            max_delay_seconds=float(max_delay) if max_delay is not None else base.retry.max_delay_seconds,
        )

        return cls(timeout_seconds=timeout_value, retry=retry_policy)


DEFAULT_OPERATION_POLICY: BackendOperationPolicy = BackendOperationPolicy.default()

