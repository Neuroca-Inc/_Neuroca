"""Strength and decay balancing utilities for memory tiers."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class StrengthState:
    """Mutable strength state tracked for a memory item."""

    strength: float
    importance: float
    reinforcement_level: float
    reinforcement_count: int
    last_decay_at: datetime
    last_reinforced_at: datetime


class StrengthDecayModel:
    """Encapsulates bounded reinforcement with passive exponential decay."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "min_strength": 0.02,
        "max_strength": 1.0,
        "baseline_strength": 0.05,
        "importance_weight": 0.25,
        "default_importance": 0.5,
        "passive_half_life_seconds": 1800.0,
        "reinforcement_half_life_seconds": 900.0,
        "staleness_half_life_seconds": 7200.0,
        "reinforcement_unit": 1.0,
        "reinforcement_importance_weight": 0.6,
        "reinforcement_scale": 3.0,
        "max_reinforcement_level": 12.0,
        "max_reinforcement_step": 0.25,
        "max_decay_per_cycle": 0.3,
        "manual_decay_multiplier": 3.0,
        "forgetting_threshold": 0.1,
        "forgetting_importance_weight": 0.08,
        "decay_floor": 0.02,
    }

    TIER_OVERRIDES: Dict[str, Dict[str, Any]] = {
        "mtm": {
            "baseline_strength": 0.06,
            "passive_half_life_seconds": 2400.0,
            "reinforcement_half_life_seconds": 1200.0,
            "forgetting_threshold": 0.12,
            "max_decay_per_cycle": 0.25,
            "reinforcement_unit": 1.2,
        },
        "ltm": {
            "baseline_strength": 0.08,
            "passive_half_life_seconds": 43200.0,
            "reinforcement_half_life_seconds": 14400.0,
            "forgetting_threshold": 0.08,
            "max_decay_per_cycle": 0.15,
            "manual_decay_multiplier": 2.0,
            "reinforcement_unit": 0.9,
        },
    }

    def __init__(self, tier: str, *, overrides: Optional[Dict[str, Any]] = None) -> None:
        self.tier = tier
        self.config = self._build_config(overrides or {})
        self.min_strength = float(self.config["min_strength"])
        self.max_strength = float(self.config["max_strength"])
        self.baseline_strength = float(self.config["baseline_strength"])
        self.importance_weight = float(self.config["importance_weight"])
        self.default_importance = float(self.config["default_importance"])
        self.decay_floor = float(self.config["decay_floor"])
        self.reinforcement_unit = float(self.config["reinforcement_unit"])
        self.reinforcement_importance_weight = float(
            self.config["reinforcement_importance_weight"]
        )
        self.reinforcement_scale = max(0.01, float(self.config["reinforcement_scale"]))
        self.max_reinforcement_level = max(
            self.reinforcement_scale,
            float(self.config["max_reinforcement_level"]),
        )
        self.max_reinforcement_step = float(self.config["max_reinforcement_step"])
        self.max_decay_per_cycle = float(self.config["max_decay_per_cycle"])
        self.manual_decay_multiplier = max(1.0, float(self.config["manual_decay_multiplier"]))
        self.forgetting_threshold = float(self.config["forgetting_threshold"])
        self.forgetting_importance_weight = float(
            self.config["forgetting_importance_weight"]
        )
        self._passive_decay_constant = self._half_life_to_constant(
            self.config.get("passive_half_life_seconds", 0.0)
        )
        self._reinforcement_decay_constant = self._half_life_to_constant(
            self.config.get("reinforcement_half_life_seconds", 0.0)
        )
        self._staleness_decay_constant = self._half_life_to_constant(
            self.config.get("staleness_half_life_seconds", 0.0)
        )

    @staticmethod
    def _half_life_to_constant(half_life_seconds: float) -> float:
        half_life = float(half_life_seconds)
        if half_life <= 0:
            return 0.0
        return math.log(2.0) / half_life

    def _build_config(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        config.update(self.DEFAULT_CONFIG)
        tier_overrides = self.TIER_OVERRIDES.get(self.tier)
        if tier_overrides:
            config.update(tier_overrides)
        config.update(overrides)
        return config

    def state_from_metadata(
        self,
        metadata: Optional[Dict[str, Any]],
        *,
        now: Optional[datetime] = None,
        importance: Optional[float] = None,
    ) -> StrengthState:
        """Build strength state from persisted metadata."""

        now = now or datetime.now(UTC)
        metadata = metadata or {}

        importance_value = self._clamp_unit(
            importance if importance is not None else metadata.get("importance", self.default_importance)
        )
        strength = self._clamp_strength(float(metadata.get("strength", self.baseline_strength)))
        reinforcement_level = metadata.get("reinforcement_level")
        reinforcement_count = int(metadata.get("reinforcement_count", 0) or 0)
        last_decay_at = self._parse_timestamp(metadata.get("last_decay_at"), now)
        last_reinforced_at = self._parse_timestamp(
            metadata.get("last_reinforced_at"), last_decay_at
        )

        if reinforcement_level is None:
            reinforcement_level = self._derive_reinforcement_level(strength, importance_value)
        else:
            try:
                reinforcement_level = float(reinforcement_level)
            except (TypeError, ValueError):
                reinforcement_level = self._derive_reinforcement_level(strength, importance_value)

        reinforcement_level = self._clamp_reinforcement(reinforcement_level)

        state = StrengthState(
            strength=self._clamp_strength(strength),
            importance=importance_value,
            reinforcement_level=reinforcement_level,
            reinforcement_count=max(0, reinforcement_count),
            last_decay_at=last_decay_at,
            last_reinforced_at=last_reinforced_at,
        )

        # Ensure strength is aligned with reinforcement level for consistency.
        state.strength = self._compute_strength(state)
        return state

    def state_to_metadata(self, state: StrengthState) -> Dict[str, Any]:
        """Serialize strength state into metadata fields."""

        return {
            "strength": round(self._clamp_strength(state.strength), 6),
            "importance": round(self._clamp_unit(state.importance), 6),
            "reinforcement_level": round(self._clamp_reinforcement(state.reinforcement_level), 6),
            "reinforcement_count": int(max(0, state.reinforcement_count)),
            "last_decay_at": state.last_decay_at.astimezone(UTC).isoformat(),
            "last_reinforced_at": state.last_reinforced_at.astimezone(UTC).isoformat(),
        }

    def apply_passive_decay(
        self,
        state: StrengthState,
        *,
        now: Optional[datetime] = None,
        staleness_seconds: Optional[float] = None,
    ) -> StrengthState:
        """Apply passive exponential decay towards the importance baseline."""

        now = now or datetime.now(UTC)
        if now <= state.last_decay_at:
            return state

        elapsed = (now - state.last_decay_at).total_seconds()
        baseline = self._importance_baseline(state.importance)

        decay_factor = self._decay_fraction(elapsed, self._reinforcement_decay_constant)
        state.reinforcement_level = self._clamp_reinforcement(state.reinforcement_level * decay_factor)

        if staleness_seconds and staleness_seconds > 0 and self._staleness_decay_constant > 0:
            staleness_factor = self._decay_fraction(staleness_seconds, self._staleness_decay_constant)
            state.reinforcement_level = self._clamp_reinforcement(
                state.reinforcement_level * staleness_factor
            )

        target_strength = self._compute_strength(state, baseline=baseline)
        previous_strength = state.strength

        if target_strength < previous_strength:
            decay_share = 1.0 - self._decay_fraction(elapsed, self._passive_decay_constant)
            new_strength = previous_strength - (previous_strength - target_strength) * decay_share
            drop = previous_strength - new_strength
            if drop > self.max_decay_per_cycle:
                new_strength = previous_strength - self.max_decay_per_cycle
            state.strength = max(target_strength, new_strength)
        else:
            increase = target_strength - previous_strength
            if increase > self.max_reinforcement_step:
                state.strength = previous_strength + self.max_reinforcement_step
            else:
                state.strength = target_strength

        state.strength = self._clamp_strength(state.strength)
        state.last_decay_at = now
        return state

    def apply_reinforcement(
        self,
        state: StrengthState,
        strengthen_amount: float,
        *,
        now: Optional[datetime] = None,
    ) -> StrengthState:
        """Apply reinforcement input with bounded growth."""

        now = now or datetime.now(UTC)
        state = self.apply_passive_decay(state, now=now)

        delta = max(0.0, float(strengthen_amount))
        baseline = self._importance_baseline(state.importance)

        importance_scale = 1.0 + (state.importance - 0.5) * self.reinforcement_importance_weight
        importance_scale = max(0.2, importance_scale)
        reinforcement_delta = delta * self.reinforcement_unit * importance_scale
        state.reinforcement_level = self._clamp_reinforcement(
            state.reinforcement_level + reinforcement_delta
        )

        state.reinforcement_count += 1
        state.last_reinforced_at = now

        target_strength = self._compute_strength(state, baseline=baseline)
        increase = target_strength - state.strength
        if increase > self.max_reinforcement_step:
            state.strength = state.strength + self.max_reinforcement_step
        else:
            state.strength = target_strength

        state.strength = self._clamp_strength(state.strength)
        return state

    def apply_manual_decay(
        self,
        state: StrengthState,
        decay_amount: float,
        *,
        now: Optional[datetime] = None,
    ) -> StrengthState:
        """Apply explicit decay input (e.g., via user command)."""

        now = now or datetime.now(UTC)
        state = self.apply_passive_decay(state, now=now)

        delta = max(0.0, float(decay_amount)) * self.reinforcement_unit
        state.reinforcement_level = self._clamp_reinforcement(state.reinforcement_level - delta)

        baseline = self._importance_baseline(state.importance)
        target_strength = self._compute_strength(state, baseline=baseline)
        drop = state.strength - target_strength
        max_drop = self.max_decay_per_cycle * self.manual_decay_multiplier
        if drop > max_drop:
            state.strength = state.strength - max_drop
        else:
            state.strength = target_strength

        state.strength = max(self.decay_floor, self._clamp_strength(state.strength))
        state.last_decay_at = now
        return state

    def should_forget(self, state: StrengthState) -> bool:
        """Determine if the memory should be removed based on strength."""

        threshold = self.forgetting_threshold_for(state.importance)
        return state.strength <= threshold

    def forgetting_threshold_for(self, importance: float) -> float:
        importance_value = self._clamp_unit(importance)
        adjustment = (0.5 - importance_value) * self.forgetting_importance_weight
        threshold = self.forgetting_threshold + adjustment
        return max(self.decay_floor, min(self.max_strength, threshold))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _importance_baseline(self, importance: float) -> float:
        importance_value = self._clamp_unit(importance)
        baseline = self.baseline_strength + importance_value * self.importance_weight
        return self._clamp_strength(baseline)

    def _compute_strength(
        self,
        state: StrengthState,
        *,
        baseline: Optional[float] = None,
    ) -> float:
        baseline_value = baseline if baseline is not None else self._importance_baseline(state.importance)
        ratio = 1.0 - math.exp(-self._clamp_reinforcement(state.reinforcement_level) / self.reinforcement_scale)
        strength = baseline_value + (self.max_strength - baseline_value) * ratio
        return self._clamp_strength(strength)

    def _derive_reinforcement_level(self, strength: float, importance: float) -> float:
        baseline = self._importance_baseline(importance)
        strength = self._clamp_strength(strength)
        if strength <= baseline:
            return 0.0
        if baseline >= self.max_strength:
            return 0.0
        ratio = (strength - baseline) / max(self.max_strength - baseline, 1e-6)
        ratio = min(max(ratio, 0.0), 0.999999)
        level = -math.log(1.0 - ratio) * self.reinforcement_scale
        return self._clamp_reinforcement(level)

    def _clamp_strength(self, value: float) -> float:
        return max(self.min_strength, min(self.max_strength, float(value)))

    @staticmethod
    def _clamp_unit(value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, numeric))

    def _clamp_reinforcement(self, value: float) -> float:
        return max(0.0, min(self.max_reinforcement_level, float(value)))

    @staticmethod
    def _parse_timestamp(value: Any, default: datetime) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo:
                return value.astimezone(UTC)
            return value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return default
            if parsed.tzinfo:
                return parsed.astimezone(UTC)
            return parsed.replace(tzinfo=UTC)
        return default

    @staticmethod
    def _decay_fraction(elapsed_seconds: float, constant: float) -> float:
        if constant <= 0 or elapsed_seconds <= 0:
            return 1.0
        return math.exp(-constant * elapsed_seconds)


__all__ = ["StrengthDecayModel", "StrengthState"]
