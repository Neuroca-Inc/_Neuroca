"""Asynchronous helper functions used by cognitive control components."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, List


logger = logging.getLogger(__name__)


async def search_memories(
    searchers: Iterable[Callable[..., Awaitable[List[Any]]]],
    *,
    query: str,
    limit: int = 10,
    **kwargs: Any,
) -> List[Any]:
    """Run the provided asynchronous search callables and merge the results."""

    tasks = [asyncio.create_task(searcher(query=query, limit=limit, **kwargs)) for searcher in searchers]
    if not tasks:
        return []

    results: List[Any] = []
    for response in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(response, Exception):  # pragma: no cover - defensive logging
            logger.warning("Memory search failed: %s", response)
            continue
        results.extend(response or [])
        if len(results) >= limit:
            break

    return results[:limit]
