"""Utilities for tracking metacognitive errors and performance metrics."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Mapping


class ErrorTracker:
    """Manage recent error records and persist them to episodic memory."""

    def __init__(
        self,
        memory_manager: Any | None,
        *,
        max_entries: int = 20,
        logger: logging.Logger | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._log: Deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._logger = logger or logging.getLogger(__name__)

    def set_memory_manager(self, memory_manager: Any | None) -> None:
        """Update the memory manager used for persistence."""

        self._memory_manager = memory_manager

    def record(self, error_details: Mapping[str, Any]) -> dict[str, Any]:
        """Normalise and store an error entry."""

        normalised = dict(error_details)
        normalised.setdefault("timestamp", time.time())
        normalised.setdefault("type", "Unknown")
        normalised.setdefault("message", "")
        self._log.append(normalised)
        return normalised

    def persist(self, error_details: Mapping[str, Any]) -> None:
        """Persist the error details via the configured memory manager."""

        if not self._memory_manager:
            return

        content = {
            "type": "error",
            "error_type": error_details.get("type", "Unknown"),
            "message": error_details.get("message", ""),
            "details": dict(error_details),
        }
        metadata: dict[str, Any] = {
            "error_source": error_details.get("source", "unknown_component"),
            "component": error_details.get("component", "system"),
            "severity": error_details.get("severity", "warning"),
            "tags": ["error", error_details.get("type", "unknown_error")],
        }
        for key in ("task", "action"):
            if key in error_details:
                metadata[key] = error_details[key]

        try:
            self._memory_manager.store(
                content=content,
                memory_type="episodic",
                metadata=metadata,
                emotional_salience=0.8,
            )
            self._logger.debug(
                "Error stored in episodic memory: %s",
                error_details.get("type", "Unknown"),
            )
        except Exception as error:  # noqa: BLE001 - defensive log
            self._logger.error("Failed to store error in memory: %s", error)

    def recent(self) -> list[dict[str, Any]]:
        """Return a copy of the recent errors buffer."""

        return list(self._log)


    def set_max_entries(self, max_entries: int) -> None:
        """Update the maximum number of stored error entries."""

        max_entries = max(1, int(max_entries))
        self._log = deque(self._log, maxlen=max_entries)

    @property
    def max_entries(self) -> int:
        """Return the configured maximum buffer length."""

        return self._log.maxlen or len(self._log)

    def clear(self) -> None:
        """Reset the tracked error history."""

        self._log.clear()

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._log)


@dataclass(slots=True)
class PerformanceTracker:
    """Track performance counters required for metacognitive summaries."""

    total_actions_completed: int = 0
    total_energy_consumed: float = 0.0

    def record_completion(self, action_cost: float) -> None:
        """Record the completion of an action with the associated cost."""

        self.total_actions_completed += 1
        self.total_energy_consumed += action_cost

    @property
    def average_action_cost(self) -> float:
        """Return the average cost of completed actions."""

        if not self.total_actions_completed:
            return 0.0
        return self.total_energy_consumed / self.total_actions_completed

    def snapshot(self) -> dict[str, float]:
        """Return a serialisable snapshot of the tracked metrics."""

        return {
            "total_actions_completed": self.total_actions_completed,
            "total_energy_consumed": self.total_energy_consumed,
            "avg_action_cost": self.average_action_cost,
        }
