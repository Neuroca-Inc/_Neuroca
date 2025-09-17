"""Helper utilities for bridging synchronous and asynchronous cognitive-control integrations."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Sequence
from typing import Any

from neuroca.core.enums import MemoryTier

logger = logging.getLogger(__name__)


async def call_async_or_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Invoke ``func`` whether it is synchronous or asynchronous."""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    result = await asyncio.to_thread(func, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _normalize_tiers(
    tiers: Sequence[MemoryTier | str] | None,
) -> tuple[list[str], list[str]]:
    storage_keys: list[str] = []
    canonical_labels: list[str] = []

    if not tiers:
        return storage_keys, canonical_labels

    for tier in tiers:
        if isinstance(tier, MemoryTier):
            storage_keys.append(tier.storage_key)
            canonical_labels.append(tier.canonical_label)
            continue

        try:
            resolved = MemoryTier.from_string(str(tier))
        except ValueError:
            normalized = str(tier)
            storage_keys.append(normalized)
            canonical_labels.append(normalized)
        else:
            storage_keys.append(resolved.storage_key)
            canonical_labels.append(resolved.canonical_label)

    return storage_keys, canonical_labels


async def search_memories(
    manager: Any,
    *,
    query: str,
    limit: int | None = None,
    tiers: Sequence[MemoryTier | str] | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[Any]:
    """Search the memory manager using whichever API it exposes."""
    if manager is None:
        return []

    storage_keys, canonical_labels = _normalize_tiers(tiers)

    search_method = getattr(manager, "search_memories", None)
    if search_method is not None:
        kwargs = {"query": query}
        if limit is not None:
            kwargs["limit"] = limit
        if metadata_filters:
            kwargs["metadata_filters"] = metadata_filters
        if storage_keys:
            kwargs["tiers"] = storage_keys

        try:
            results = await call_async_or_sync(search_method, **kwargs)
        except TypeError as exc:
            logger.debug("search_memories signature mismatch: %s", exc)
            if "metadata_filters" in kwargs:
                fallback_kwargs = dict(kwargs)
                fallback_kwargs.pop("metadata_filters", None)
                results = await call_async_or_sync(search_method, **fallback_kwargs)
            else:
                raise
        if not results:
            return []
        if isinstance(results, list):
            return results
        return list(results)

    retrieve_method = getattr(manager, "retrieve", None)
    if retrieve_method is not None:
        base_kwargs: dict[str, Any] = {"query": query}
        if limit is not None:
            base_kwargs["limit"] = limit

        candidate_kwargs: list[dict[str, Any]] = []
        if canonical_labels:
            candidate_kwargs.append({**base_kwargs, "memory_type": canonical_labels[0]})
        if storage_keys:
            candidate_kwargs.append({**base_kwargs, "tier": storage_keys[0]})
        if tiers:
            candidate_kwargs.append({**base_kwargs, "memory_type": tiers[0]})
        if not candidate_kwargs:
            candidate_kwargs.append(base_kwargs)

        for candidate in candidate_kwargs:
            try:
                results = await call_async_or_sync(retrieve_method, **candidate)
            except TypeError:
                continue
            if not results:
                continue
            if isinstance(results, list):
                return results
            return [results]

        logger.debug("retrieve method did not accept provided arguments for query '%s'", query)

    return []


def _coerce_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()  # type: ignore[call-arg]
        except Exception:  # noqa: BLE001
            logger.debug("Failed to model_dump metadata of %s", type(value).__name__, exc_info=True)
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(value, "dict"):
        try:
            dumped = value.dict()  # type: ignore[call-arg]
        except Exception:  # noqa: BLE001
            logger.debug("Failed to dict() metadata of %s", type(value).__name__, exc_info=True)
        else:
            if isinstance(dumped, dict):
                return dumped
    if hasattr(value, "__dict__"):
        try:
            return {k: v for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:  # noqa: BLE001
            logger.debug("Failed to coerce __dict__ for %s", type(value).__name__, exc_info=True)
    return {}


def extract_metadata(item: Any) -> dict[str, Any]:
    """Extract metadata from a memory item regardless of representation."""
    if hasattr(item, "metadata"):
        return _coerce_dict(getattr(item, "metadata"))
    if isinstance(item, dict):
        return _coerce_dict(item.get("metadata"))
    return {}


def extract_content(item: Any) -> Any:
    """Return the stored content from a memory search result."""
    if hasattr(item, "content"):
        return getattr(item, "content")
    if isinstance(item, dict):
        return item.get("content")
    return None
