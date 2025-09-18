"""Utilities for adapting consolidation behaviour under tier pressure."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _TierPressureState:
    """Internal state snapshot for a single tier."""

    ratio: float = 0.0
    pressure: float = 0.0


class TierCapacityPressureAdapter:
    """Track tier saturation and derive adaptive consolidation thresholds."""

    def __init__(
        self,
        *,
        relief_ratio: float = 0.65,
        saturation_ratio: float = 0.95,
        smoothing: float = 0.3,
        log: logging.Logger | None = None,
    ) -> None:
        if saturation_ratio <= relief_ratio:
            raise ValueError("saturation_ratio must be greater than relief_ratio")

        self._relief_ratio = max(0.0, min(1.0, float(relief_ratio)))
        self._saturation_ratio = max(0.0, min(1.0, float(saturation_ratio)))
        self._smoothing = max(0.0, min(1.0, float(smoothing)))
        self._log = log or logger.getChild("capacity")
        self._state: Dict[str, _TierPressureState] = {}

    def observe(self, tier: str, ratio: float | None) -> None:
        """Record a new utilisation ratio for ``tier`` and update pressure."""

        if tier is None:
            return

        try:
            value = float(ratio) if ratio is not None else 0.0
        except (TypeError, ValueError):
            self._log.debug("Ignoring invalid ratio %r for tier %s", ratio, tier)
            return

        value = max(0.0, min(1.0, value))
        span = max(1e-6, self._saturation_ratio - self._relief_ratio)
        if value <= self._relief_ratio:
            target = 0.0
        else:
            target = min(1.0, (value - self._relief_ratio) / span)

        previous = self._state.get(tier)
        prior_pressure = previous.pressure if previous else 0.0

        if self._smoothing == 0:
            updated = target
        else:
            updated = prior_pressure + self._smoothing * (target - prior_pressure)

        updated = max(0.0, min(1.0, updated))
        self._state[tier] = _TierPressureState(ratio=value, pressure=updated)

    def pressure_for(self, tier: str) -> float:
        """Return the current pressure value for ``tier`` in ``[0, 1]``."""

        state = self._state.get(tier)
        return state.pressure if state else 0.0

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Return a serialisable snapshot of the current pressure state."""

        return {
            tier: {"ratio": state.ratio, "pressure": state.pressure}
            for tier, state in self._state.items()
        }

    def stm_priority_threshold(self, base_threshold: float, *, minimum: float = 0.35) -> float:
        """Return the STM priority score threshold adjusted for pressure."""

        base = float(base_threshold)
        floor = float(minimum)
        if base <= floor:
            return base
        pressure = self.pressure_for("stm")
        adjusted = base - (base - floor) * pressure
        return max(floor, adjusted)

    def stm_batch_size(self, base_size: int, *, max_multiplier: float = 3.0) -> int:
        """Return an STM consolidation batch size scaled by pressure."""

        base = int(max(0, base_size))
        if base <= 0:
            return 0

        pressure = self.pressure_for("stm")
        multiplier = 1.0 + pressure * max(0.0, float(max_multiplier) - 1.0)
        return max(1, int(round(base * multiplier)))

    def mtm_batch_size(self, base_size: int, *, max_multiplier: float = 4.0) -> int:
        """Return an MTM promotion batch size scaled by pressure."""

        base = int(max(0, base_size))
        if base <= 0:
            return 0

        pressure = self.pressure_for("mtm")
        multiplier = 1.0 + pressure * max(0.0, float(max_multiplier) - 1.0)
        return max(1, int(round(base * multiplier)))
