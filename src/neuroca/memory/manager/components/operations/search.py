"""Memory search helpers for the asynchronous memory manager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from neuroca.memory.exceptions import MemoryManagerOperationError
from neuroca.memory.manager.components.base import LOGGER
from neuroca.memory.manager.scoping import MemoryRetrievalScope

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerSearchMixin(MemoryManagerOperationSupportMixin):
    """Expose metadata-aware search helpers across tiers."""

    async def search_memories(
        self,
        query: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        min_relevance: float = 0.0,
        tiers: Optional[List[str]] = None,
        scope: MemoryRetrievalScope | None = None,
    ) -> List[Dict[str, Any]]:
        """Search for memories across configured tiers."""

        self._ensure_initialized()
        scope_obj = self._normalize_scope(scope)

        try:
            search_tiers = self._determine_search_tiers(tiers)
            filters = self._build_search_filters(tags, metadata_filters)
            aggregated = await self._collect_search_results(
                search_tiers,
                query,
                embedding,
                filters,
                limit,
                scope_obj,
            )
            return self._rank_results(aggregated, min_relevance, limit)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to search memories")
            raise MemoryManagerOperationError(
                f"Failed to search memories: {exc}"
            ) from exc

    def _determine_search_tiers(self, tiers: Optional[List[str]]) -> List[str]:
        """Return the tier list to query."""

        return list(tiers) if tiers else self._tier_iteration_order()

    def _build_search_filters(
        self,
        tags: Optional[List[str]],
        metadata_filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge tag constraints into ``metadata_filters``."""

        filters = dict(metadata_filters or {})
        if tags:
            for tag in tags:
                filters[f"metadata.tags.{tag}"] = True
        return filters

    async def _collect_search_results(
        self,
        search_tiers: List[str],
        query: Optional[str],
        embedding: Optional[List[float]],
        filters: Dict[str, Any],
        limit: int,
        scope: MemoryRetrievalScope,
    ) -> List[Dict[str, Any]]:
        """Gather raw search results across ``search_tiers``."""

        aggregated: List[Dict[str, Any]] = []
        for tier_name in search_tiers:
            try:
                tier_results = await self._search_single_tier(
                    tier_name,
                    query,
                    embedding,
                    filters,
                    limit,
                    scope,
                )
                aggregated.extend(tier_results)
            except Exception as exc:  # noqa: BLE001
                LOGGER.error("Error searching tier %s: %s", tier_name, exc)
        return aggregated

    async def _search_single_tier(
        self,
        tier_name: str,
        query: Optional[str],
        embedding: Optional[List[float]],
        filters: Dict[str, Any],
        limit: int,
        scope: MemoryRetrievalScope,
    ) -> List[Dict[str, Any]]:
        """Search ``tier_name`` and return scoped results."""

        tier_instance = self._get_tier_by_name(tier_name)
        search_results = await tier_instance.search(
            query=query,
            embedding=embedding,
            filters=filters or None,
            limit=limit,
        )

        results: List[Dict[str, Any]] = []
        for search_result in search_results.results:
            if not self._is_memory_visible(search_result.memory, scope):
                continue
            result_dict = search_result.memory.model_dump()
            result_dict["tier"] = tier_name
            result_dict["_relevance"] = search_result.relevance
            results.append(result_dict)
        return results

    def _rank_results(
        self,
        results: List[Dict[str, Any]],
        min_relevance: float,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Deduplicate, filter, and rank ``results``."""

        unique: Dict[str, Dict[str, Any]] = {}
        for result in results:
            memory_id = result.get("id")
            if not memory_id:
                continue
            existing = unique.get(memory_id)
            if existing is None or result.get("_relevance", 0) > existing.get("_relevance", 0):
                unique[memory_id] = result

        sorted_results = sorted(
            unique.values(),
            key=lambda item: item.get("_relevance", 0),
            reverse=True,
        )
        filtered = [
            result
            for result in sorted_results
            if result.get("_relevance", 0) >= min_relevance
        ]
        return filtered[:limit]


__all__ = ["MemoryManagerSearchMixin"]
