"""Legacy decay helpers that wrap the strength balancing model."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from neuroca.memory.backends import MemoryTier
from neuroca.memory.manager.strength_decay import StrengthDecayModel

logger = logging.getLogger(__name__)


async def decay_mtm_memories(mtm_storage, config: Dict[str, Any]) -> Dict[str, int]:
    """Apply passive decay and forgetting to MTM memories and return counts."""

    model = _resolve_model("mtm", config)
    now = datetime.now(UTC)
    logger.debug("Starting MTM memory decay at %s", now.isoformat())

    try:
        memories = await mtm_storage.list_all()
    except Exception:  # pragma: no cover - backend specific failures
        logger.exception("Failed to enumerate MTM memories during decay cycle")
        return {"processed": 0, "decayed": 0, "removed": 0}

    if not memories:
        return {"processed": 0, "decayed": 0, "removed": 0}

    summary = {"processed": 0, "decayed": 0, "removed": 0}

    for memory in memories:
        memory_id = getattr(memory, "id", None)
        if not memory_id:
            continue

        summary["processed"] += 1

        try:
            metadata = _metadata_dict(getattr(memory, "metadata", None))
            importance = metadata.get("importance", 0.5)
            state = model.state_from_metadata(metadata, now=now, importance=importance)

            last_accessed = getattr(memory, "last_accessed", None)
            staleness_seconds = None
            if last_accessed:
                last_accessed_dt = _coerce_datetime(last_accessed, now)
                staleness_seconds = max(0.0, (now - last_accessed_dt).total_seconds())

            state = model.apply_passive_decay(
                state,
                now=now,
                staleness_seconds=staleness_seconds,
            )

            if model.should_forget(state):
                await mtm_storage.forget_memory(memory_id)
                logger.info(
                    "MTM memory %s decayed below threshold (%.3f)",
                    memory_id,
                    state.strength,
                )
                summary["removed"] += 1
                continue

            metadata.update(model.state_to_metadata(state))
            if hasattr(memory, "activation"):
                memory.activation = state.strength

            await mtm_storage.update(memory_id, metadata=metadata)
            summary["decayed"] += 1
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Error applying decay to MTM memory %s", memory_id)

    return summary


async def decay_ltm_memories(ltm_storage, config: Dict[str, Any]) -> Dict[str, int]:
    """Apply passive decay to LTM memories when possible and return counts."""

    model = _resolve_model("ltm", config)
    now = datetime.now(UTC)
    logger.debug("Starting LTM memory decay at %s", now.isoformat())

    memories = await _iter_ltm_candidates(ltm_storage)
    if not memories:
        return {"processed": 0, "decayed": 0, "removed": 0}

    summary = {"processed": 0, "decayed": 0, "removed": 0}

    for memory in memories:
        memory_id = getattr(memory, "id", None)
        if not memory_id:
            continue

        summary["processed"] += 1

        try:
            raw_metadata = getattr(memory, "metadata", None)
            metadata = _metadata_dict(raw_metadata.dict() if hasattr(raw_metadata, "dict") else raw_metadata)
            importance = metadata.get("importance", 0.5)
            state = model.state_from_metadata(metadata, now=now, importance=importance)

            last_accessed = metadata.get("last_accessed_at") or getattr(memory, "last_accessed", None)
            staleness_seconds = None
            if last_accessed:
                last_accessed_dt = _coerce_datetime(last_accessed, now)
                staleness_seconds = max(0.0, (now - last_accessed_dt).total_seconds())

            state = model.apply_passive_decay(
                state,
                now=now,
                staleness_seconds=staleness_seconds,
            )

            if model.should_forget(state):
                await _forget_ltm_memory(ltm_storage, memory_id)
                logger.info(
                    "LTM memory %s decayed below threshold (%.3f)",
                    memory_id,
                    state.strength,
                )
                summary["removed"] += 1
                continue

            metadata.update(model.state_to_metadata(state))
            await _update_ltm_metadata(ltm_storage, memory, metadata)
            summary["decayed"] += 1
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Error applying decay to LTM memory %s", memory_id)

    return summary


async def strengthen_memory(
    memory_id: str,
    tier: MemoryTier,
    mtm_storage=None,
    ltm_storage=None,
    strengthen_amount: float = 0.1,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Strengthen a memory by feeding the reinforcement model."""

    if not memory_id:
        return

    now = datetime.now(UTC)

    try:
        if tier == MemoryTier.MTM:
            if not mtm_storage:
                logger.error("MTM storage not provided for strengthening MTM memory")
                return

            memory = await mtm_storage.retrieve(memory_id)
            if not memory:
                return

            metadata = _metadata_dict(getattr(memory, "metadata", None))
            importance = metadata.get("importance", 0.5)
            model = _resolve_model("mtm", config or {})
            state = model.state_from_metadata(metadata, now=now, importance=importance)
            state = model.apply_reinforcement(
                state,
                strengthen_amount,
                now=now,
            )

            metadata.update(model.state_to_metadata(state))
            if hasattr(memory, "activation"):
                memory.activation = state.strength

            await mtm_storage.update(memory_id, metadata=metadata)
            logger.debug("Strengthened MTM memory %s to %.3f", memory_id, state.strength)

        elif tier == MemoryTier.LTM:
            if not ltm_storage:
                logger.error("LTM storage not provided for strengthening LTM memory")
                return

            memory = await _retrieve_ltm_memory(ltm_storage, memory_id)
            if not memory:
                return

            raw_metadata = getattr(memory, "metadata", None)
            metadata = _metadata_dict(raw_metadata.dict() if hasattr(raw_metadata, "dict") else raw_metadata)
            importance = metadata.get("importance", 0.5)
            model = _resolve_model("ltm", config or {})
            state = model.state_from_metadata(metadata, now=now, importance=importance)
            state = model.apply_reinforcement(state, strengthen_amount, now=now)

            metadata.update(model.state_to_metadata(state))
            await _update_ltm_metadata(ltm_storage, memory, metadata)
            logger.debug("Strengthened LTM memory %s to %.3f", memory_id, state.strength)

    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Error strengthening memory %s", memory_id)


def _resolve_model(tier: str, config: Optional[Dict[str, Any]]) -> StrengthDecayModel:
    overrides: Dict[str, Any] = {}
    if config:
        strength_config = config.get("strength_model") if isinstance(config, dict) else None
        if isinstance(strength_config, dict):
            tier_specific = strength_config.get(tier)
            if isinstance(tier_specific, dict):
                overrides = tier_specific
            else:
                overrides = strength_config
    return StrengthDecayModel(tier, overrides=overrides)


def _metadata_dict(metadata: Any) -> Dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    if hasattr(metadata, "dict") and callable(metadata.dict):
        try:
            return dict(metadata.dict())
        except Exception:  # pragma: no cover - safety net for custom metadata objects
            logger.debug("Failed to serialise metadata object", exc_info=True)
    return {}


def _coerce_datetime(value: Any, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return default
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return default


async def _iter_ltm_candidates(ltm_storage) -> Iterable[Any]:
    try:
        if hasattr(ltm_storage, "list_all"):
            result = await ltm_storage.list_all()
        elif hasattr(ltm_storage, "retrieve_all"):
            result = await ltm_storage.retrieve_all()
        elif hasattr(ltm_storage, "list"):
            result = await ltm_storage.list()
        else:
            logger.debug("LTM storage does not expose bulk retrieval; skipping decay run")
            return []
    except Exception:  # pragma: no cover - backend specific failures
        logger.exception("Failed to gather LTM memories for decay")
        return []

    if result is None:
        return []
    if isinstance(result, (list, tuple, set)):
        return list(result)
    if hasattr(result, "__aiter__"):
        return [item async for item in result]  # type: ignore[misc]
    if isinstance(result, Iterable):
        return list(result)
    if isinstance(result, Sequence):
        return list(result)
    return []


async def _forget_ltm_memory(ltm_storage, memory_id: str) -> None:
    if hasattr(ltm_storage, "delete"):
        await ltm_storage.delete(memory_id)
    elif hasattr(ltm_storage, "forget_memory"):
        await ltm_storage.forget_memory(memory_id)


async def _update_ltm_metadata(ltm_storage, memory: Any, metadata: Dict[str, Any]) -> None:
    if hasattr(memory, "metadata") and hasattr(memory.metadata, "__class__") and hasattr(memory.metadata, "dict"):
        metadata_cls = memory.metadata.__class__
        memory.metadata = metadata_cls(**metadata)
    else:
        memory.metadata = metadata

    if hasattr(memory, "strength"):
        memory.strength = metadata.get("strength", getattr(memory, "strength", 0.0))

    if hasattr(ltm_storage, "update"):
        try:
            if callable(getattr(ltm_storage, "update")):
                await ltm_storage.update(memory)
                return
        except TypeError:
            # Some backends expect keyword arguments
            await ltm_storage.update(memory.id, metadata=metadata)
            return
    if hasattr(ltm_storage, "store"):
        await ltm_storage.store(memory)


async def _retrieve_ltm_memory(ltm_storage, memory_id: str) -> Any:
    if hasattr(ltm_storage, "get"):
        return await ltm_storage.get(memory_id)
    if hasattr(ltm_storage, "retrieve"):
        return await ltm_storage.retrieve(memory_id)
    return None


__all__ = [
    "decay_mtm_memories",
    "decay_ltm_memories",
    "strengthen_memory",
]
