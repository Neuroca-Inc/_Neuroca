"""Confidence estimation helpers for metacognitive evaluations."""

from __future__ import annotations

import logging
from typing import Any

from neuroca.memory.models.memory_item import MemoryItem


class ConfidenceEstimator:
    """Estimate confidence levels given the data source and health context."""

    _SOURCE_BASE = {
        "semantic_memory": 0.85,
        "episodic_memory": 0.70,
        "working_memory": 0.65,
        "llm_prediction": 0.60,
        "direct_input": 0.90,
    }

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def estimate(self, data: Any, source: str, health_status: str) -> float:
        """Estimate a confidence score between 0.0 and 1.0."""

        base = self._SOURCE_BASE.get(source, 0.75)
        memory_confidence = self._memory_confidence(data)
        if memory_confidence is not None:
            base = (base + memory_confidence) / 2

        health_factor = self._health_factor(health_status)
        final = max(0.0, min(1.0, base * health_factor))

        self._logger.debug(
            "Estimated confidence for data from '%s': %.2f (Base: %.2f, HealthFactor: %.2f)",
            source,
            final,
            base,
            health_factor,
        )
        return final

    def _memory_confidence(self, data: Any) -> float | None:
        if not isinstance(data, MemoryItem):
            return None

        activation_value = self._memory_activation(data)
        confidence = max(0.1, min(1.0, activation_value * 0.8 + 0.1))

        metadata_confidence = (getattr(data, "metadata", {}) or {}).get("confidence")
        if metadata_confidence is not None:
            try:
                confidence = (confidence + float(metadata_confidence)) / 2
            except (TypeError, ValueError):
                pass
        return confidence

    @staticmethod
    def _memory_activation(memory: MemoryItem) -> float:
        activation_fn = getattr(memory, "calculate_activation", None)
        if callable(activation_fn):
            try:
                return float(activation_fn())
            except Exception:  # noqa: BLE001 - activation implementations vary
                return 0.5
        embedding = getattr(memory, "embedding", None)
        if embedding and isinstance(embedding, list) and embedding:
            return min(1.0, max(0.0, sum(abs(value) for value in embedding) / len(embedding)))
        return 0.5

    @staticmethod
    def _health_factor(status: str) -> float:
        status_lower = (status or "").lower()
        if status_lower == "degraded":
            return 0.9
        if status_lower in {"unhealthy", "critical"}:
            return 0.7
        return 1.0
