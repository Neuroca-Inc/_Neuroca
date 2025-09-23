"""Legacy compatibility helpers for synchronous integrations."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .base import LOGGER


class MemoryManagerLegacyMixin:
    """Expose historic synchronous entry points for the memory manager."""

    def _legacy_call(
        self,
        coro: Awaitable[Any],
        *,
        transform: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Execute ``coro`` while preserving legacy synchronous semantics."""

        async def _runner() -> Any:
            result = await coro
            return transform(result) if transform is not None else result

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_runner())

        task = loop.create_task(_runner())

        def _log_failure(done: asyncio.Future[Any]) -> None:
            if done.cancelled():
                return
            try:
                done.result()
            except Exception:  # noqa: BLE001
                LOGGER.exception("Legacy memory manager compatibility call failed")

        task.add_done_callback(_log_failure)
        return task

    def store(
        self,
        content: Any,
        *,
        summary: str | None = None,
        importance: float = 0.5,
        metadata: Any | None = None,
        tags: Optional[List[str]] = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        emotional_salience: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Store a memory using the historic synchronous signature."""

        initial_tier = self._normalize_tier_name(tier or memory_type)
        merged_metadata = self._merge_metadata(
            metadata, emotional_salience=emotional_salience
        )

        return self._legacy_call(
            self.add_memory(
                content=content,
                summary=summary,
                importance=importance,
                metadata=merged_metadata,
                tags=tags,
                initial_tier=initial_tier,
                **{k: v for k, v in kwargs.items() if k not in {"memory_type", "tier"}},
            )
        )

    def retrieve(
        self,
        *args: Any,
        query: str | None = None,
        memory_id: str | None = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        limit: int | None = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Retrieve memories using the historic flexible interface."""

        if args and not query and memory_id is None:
            memory_id = str(args[0])

        if memory_id is not None:
            normalized_tier = self._normalize_tier_name(tier)
            return self._legacy_call(
                self.retrieve_memory(memory_id, tier=normalized_tier),
                transform=lambda result: self._wrap_search_results([result])[0]
                if result
                else None,
            )

        normalized_tier = self._normalize_tier_name(tier or memory_type)
        search_kwargs: dict[str, Any] = {
            "query": query or (args[0] if args else None),
            "limit": kwargs.get("top_k", limit),
            "tiers": [normalized_tier] if normalized_tier else None,
        }

        if tags:
            search_kwargs["tags"] = tags
        if metadata_filters:
            search_kwargs["metadata_filters"] = metadata_filters

        return self._legacy_call(
            self.search_memories(**search_kwargs),
            transform=self._wrap_search_results,
        )

    def search(self, query: str | None = None, **kwargs: Any) -> Any:
        """Legacy alias that routed to search APIs."""

        return self.retrieve(query=query, **kwargs)

    def retrieve_relevant(
        self,
        query: str,
        *,
        tier: Any | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Legacy helper used by integration utilities."""

        return self.retrieve(query=query, tier=tier, limit=limit, **kwargs)


__all__ = ["MemoryManagerLegacyMixin"]
