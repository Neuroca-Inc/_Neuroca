# Memory Decay & Reinforcement Mathematics

The decay subsystem couples exponential half-life curves with bounded reinforcement to
stabilise the strength of memories stored in MTM and LTM. This note documents the key
formulas implemented by `StrengthDecayModel` so operators can reason about decay tuning.

## State variables

Each memory tracked by MTM/LTM carries a `StrengthState` with the following fields:

- `strength` – normalized [0, 1] activation used for promotion decisions.
- `importance` – caller-supplied salience weight influencing both baselines and thresholds.
- `reinforcement_level` – accumulated reinforcement energy.
- `reinforcement_count` – audit counter for reinforcement events.
- `last_decay_at` / `last_reinforced_at` – UTC timestamps for decay bookkeeping.

## Baseline computation

Every decay pass starts by computing the baseline strength for the memory given its
importance:

```
baseline = clamp(min_strength, max_strength, baseline_strength + importance * importance_weight)
```

The baseline gently increases with importance while staying inside the `[min_strength,
max_strength]` envelope.

## Reinforcement mapping

Reinforcement behaves like a saturating exponential curve that never exceeds
`max_strength`:

```
ratio = 1 - exp(-clamp_reinforcement(reinforcement_level) / reinforcement_scale)
strength = baseline + (max_strength - baseline) * ratio
```

Reinforcement level itself is bounded by `max_reinforcement_level`. Each reinforcement
invocation increases the level by:

```
reinforcement_delta = strengthen_amount * reinforcement_unit * importance_scale
importance_scale = max(0.2, 1 + (importance - 0.5) * reinforcement_importance_weight)
```

The resulting strength gain per pass is capped by `max_reinforcement_step` so abrupt spikes
cannot occur even if large reinforcement requests are issued.

## Passive decay

Decay reduces reinforcement and strength over time using exponential half-life constants:

```
reinforcement_level *= exp(-elapsed_seconds / reinforcement_half_life)
if staleness_seconds:
    reinforcement_level *= exp(-staleness_seconds / staleness_half_life)
```

The strength target for the current pass becomes `compute_strength(state)` with the updated
reinforcement level. Strength converges towards that target using a capped decrement so a
single decay pass cannot drop more than `max_decay_per_cycle`.

## Manual decay

Operators can trigger explicit decay (via maintenance or tooling) which subtracts additional
reinforcement energy and accelerates convergence. The manual path multiplies
`max_decay_per_cycle` by `manual_decay_multiplier` to bound the drop per call.

## Forgetting threshold

Memories fall out of MTM/LTM when their strength slips below an importance-weighted
threshold:

```
adjustment = (0.5 - importance) * forgetting_importance_weight
threshold = clamp(decay_floor, max_strength, forgetting_threshold + adjustment)
should_forget = strength <= threshold
```

Higher-importance memories effectively receive lower thresholds, whereas low-importance
memories decay out sooner.

## Default configuration overview

| Parameter | Default | MTM override | LTM override | Purpose |
| --- | --- | --- | --- | --- |
| `baseline_strength` | 0.05 | 0.06 | 0.08 | Starting strength before reinforcement. |
| `passive_half_life_seconds` | 1800 | 2400 | 43200 | Half-life used for passive decay of strength. |
| `reinforcement_half_life_seconds` | 900 | 1200 | 14400 | Half-life for reinforcement energy decay. |
| `staleness_half_life_seconds` | 7200 | – | – | Optional penalty for unused memories. |
| `max_decay_per_cycle` | 0.3 | 0.25 | 0.15 | Upper bound on strength drop per decay pass. |
| `manual_decay_multiplier` | 3.0 | 3.0 | 2.0 | Scales manual decay drop allowance. |
| `reinforcement_unit` | 1.0 | 1.2 | 0.9 | Multiplier applied to reinforcement requests. |
| `forgetting_threshold` | 0.1 | 0.12 | 0.08 | Base threshold for purging memories. |

## Practical implications

- **Stable baselines** – Without reinforcement, memories converge to an importance-weighted
  baseline rather than immediately expiring.
- **Bounded reinforcement** – Importance weighting and level caps prevent runaway strength
  increases even when hot paths reinforce frequently.
- **Configurable forgetting** – Adjusting `forgetting_threshold` and `importance_weight`
  controls how aggressively the system prunes stale items.
- **Predictable operations** – Half-life constants make decay behaviour linearizable for SREs;
  halving a constant doubles the rate at which reinforcement energy dissipates.

See `tests/unit/memory/manager/test_strength_decay_model.py` and
`tests/unit/memory/manager/test_decay_lifecycle.py` for executable examples of these formulas in
practice.
