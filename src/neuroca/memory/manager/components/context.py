"""Context management helpers for working-memory coordination."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from neuroca.memory.exceptions import MemoryManagerOperationError
from neuroca.memory.models.memory_item import MemoryItem
from neuroca.memory.models.working_memory import WorkingMemoryItem

from .base import LOGGER


class MemoryManagerContextMixin:
    """Manage active context and prompt memory extraction."""

    async def update_context(
        self,
        context_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Update the current context to trigger relevant memory retrieval."""

        self._ensure_initialized()

        try:
            self._current_context = context_data
            self._current_context_embedding = embedding

            query_text = None
            if not embedding:
                for key in ("text", "query", "input", "message"):
                    if key in context_data:
                        query_text = context_data[key]
                        break

            self._working_memory.clear()

            relevant_memories = await self.search_memories(
                query=query_text,
                embedding=embedding,
                limit=20,
                min_relevance=0.3,
            )

            for memory in relevant_memories:
                memory_id = memory.get("id")
                tier = memory.get("tier")
                relevance = memory.get("_relevance", 0.5)

                if memory_id and tier:
                    payload = memory.get("memory")
                    memory_item = (
                        payload if isinstance(payload, MemoryItem) else MemoryItem.model_validate(memory)
                    )

                    self._working_memory.add_item(
                        WorkingMemoryItem(
                            memory=memory_item,
                            source_tier=tier,
                            relevance=relevance,
                        )
                    )

            LOGGER.debug(
                "Updated context and working memory with %d relevant memories",
                len(relevant_memories),
            )
        except Exception as exc:
            LOGGER.exception("Failed to update context")
            raise MemoryManagerOperationError(
                f"Failed to update context: {exc}"
            ) from exc

    async def get_prompt_context_memories(
        self,
        max_memories: int = 5,
        max_tokens_per_memory: int = 150,
    ) -> List[Dict[str, Any]]:
        """Get the most relevant memories for prompt injection."""

        self._ensure_initialized()

        try:
            working_memory_items = self._working_memory.get_most_relevant_items(
                max_memories
            )

            formatted_memories: List[Dict[str, Any]] = []

            for item in working_memory_items:
                memory_data = item.memory.model_dump()

                formatted_memory = {
                    "id": memory_data.get("id"),
                    "content": memory_data.get("content", {}).get("text")
                    or "[Structured Data]",
                    "summary": memory_data.get("content", {}).get("summary") or None,
                    "importance": memory_data.get("metadata", {}).get("importance", 0.5),
                    "created_at": memory_data.get("metadata", {}).get("created_at"),
                    "relevance": item.relevance,
                    "tier": item.source_tier,
                }

                text = formatted_memory["content"]
                if text and isinstance(text, str):
                    words = text.split()
                    if len(words) > max_tokens_per_memory / 0.75:
                        formatted_memory["content"] = " ".join(
                            words[: int(max_tokens_per_memory / 0.75)]
                        ) + "..."

                formatted_memories.append(formatted_memory)

            return formatted_memories
        except Exception as exc:
            LOGGER.exception("Failed to prepare prompt context memories")
            raise MemoryManagerOperationError(
                f"Failed to prepare prompt context memories: {exc}"
            ) from exc

    async def clear_context(self) -> None:
        """Clear the current context and working memory."""

        self._ensure_initialized()

        try:
            self._current_context = {}
            self._current_context_embedding = None
            self._working_memory.clear()
        except Exception as exc:
            LOGGER.exception("Failed to clear context")
            raise MemoryManagerOperationError(
                f"Failed to clear context: {exc}"
            ) from exc


__all__ = ["MemoryManagerContextMixin"]
