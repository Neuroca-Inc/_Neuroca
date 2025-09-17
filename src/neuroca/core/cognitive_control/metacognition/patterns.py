"""Error pattern detection helpers."""

from __future__ import annotations

import logging
from typing import Any


class ErrorPatternAnalyser:
    """Analyse stored error memories for recurring signals."""

    def __init__(self, memory_manager: Any | None, logger: logging.Logger | None = None) -> None:
        self._memory_manager = memory_manager
        self._logger = logger or logging.getLogger(__name__)

    def set_memory_manager(self, memory_manager: Any | None) -> None:
        self._memory_manager = memory_manager

    def detect(self, error_type: str | None = None) -> dict[str, Any]:
        if not self._memory_manager:
            self._logger.warning("Cannot detect error patterns: Memory manager not available")
            return {"patterns_detected": False, "reason": "memory_unavailable"}

        try:
            memories = self._retrieve_error_memories(error_type)
        except Exception as error:  # noqa: BLE001 - backends may raise custom errors
            self._logger.error("Error during pattern detection: %s", error)
            return {"patterns_detected": False, "reason": f"analysis_error: {error}"}

        if not memories:
            return {"patterns_detected": False, "reason": "no_errors_found"}

        patterns = self._initialise_summary(memories)
        for memory in memories:
            self._update_counts(patterns, memory)
        self._finalise_summary(patterns)
        return patterns

    def _retrieve_error_memories(self, error_type: str | None) -> list[Any]:
        query = "type:error"
        if error_type:
            query += f" error_type:{error_type}"

        return self._memory_manager.retrieve(
            query=query,
            memory_type="episodic",
            limit=20,
            sort_by="timestamp",
            sort_order="descending",
        )

    @staticmethod
    def _initialise_summary(memories: list[Any]) -> dict[str, Any]:
        return {
            "total_errors": len(memories),
            "by_type": {},
            "by_component": {},
            "by_source": {},
            "recent_errors": [],
        }

    @staticmethod
    def _update_counts(patterns: dict[str, Any], memory: Any) -> None:
        content = getattr(memory, "content", {}) or {}
        metadata = getattr(memory, "metadata", {}) or {}
        error_type = content.get("error_type", "unknown")
        component = metadata.get("component", "unknown")
        source = metadata.get("error_source", "unknown")

        patterns["by_type"][error_type] = patterns["by_type"].get(error_type, 0) + 1
        patterns["by_component"][component] = patterns["by_component"].get(component, 0) + 1
        patterns["by_source"][source] = patterns["by_source"].get(source, 0) + 1

        recent = patterns["recent_errors"]
        if len(recent) < 5:
            recent.append(
                {
                    "type": error_type,
                    "message": content.get("message", ""),
                    "component": component,
                    "timestamp": metadata.get("timestamp", 0),
                }
            )

    @staticmethod
    def _finalise_summary(patterns: dict[str, Any]) -> None:
        by_type = patterns.get("by_type", {})
        by_component = patterns.get("by_component", {})
        patterns["most_common_type"] = max(by_type, key=by_type.get, default=None)
        patterns["most_common_component"] = max(by_component, key=by_component.get, default=None)
        patterns["patterns_detected"] = True
