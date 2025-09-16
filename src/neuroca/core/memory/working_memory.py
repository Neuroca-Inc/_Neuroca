"""Synchronous working-memory implementation retained for legacy components."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from neuroca.core.memory.interfaces import MemorySystem


@dataclass
class WorkingMemoryChunk:
    """Discrete item managed by :class:`WorkingMemory`."""

    content: Any
    activation: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_activation(self, value: Optional[float] = None) -> None:
        if value is not None:
            self.activation = max(0.0, min(1.0, float(value)))
        self.last_accessed = datetime.now(UTC)


class WorkingMemory(MemorySystem):
    """Limited-capacity buffer modelling classical working-memory behaviour."""

    def __init__(self, capacity: int = 7, decay_rate: float = 0.1) -> None:
        if capacity <= 0:
            raise ValueError("Working memory capacity must be positive")
        self._name = "working_memory"
        self._capacity = capacity
        self._decay_rate = max(0.0, decay_rate)
        self._last_decay_time = time.time()
        self._chunks: dict[str, WorkingMemoryChunk] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._capacity

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def store(self, content: Any, **metadata: Any) -> str:
        activation = float(metadata.pop("activation", 1.0))
        chunk = WorkingMemoryChunk(content=content, activation=activation, metadata=metadata)

        self._apply_decay()
        if len(self._chunks) >= self._capacity:
            least_active = self._get_least_active_chunk_id()
            if least_active is not None:
                self._chunks.pop(least_active, None)

        self._chunks[chunk.id] = chunk
        return chunk.id

    def retrieve(self, query: Any, limit: int = 10, **parameters: Any) -> list[WorkingMemoryChunk]:
        self._apply_decay()
        query_str = str(query).lower()
        results: list[WorkingMemoryChunk] = []

        for chunk in self._chunks.values():
            content_str = str(chunk.content).lower()
            if query_str in content_str:
                chunk.update_activation(min(1.0, chunk.activation + 0.2))
                results.append(chunk)

        results.sort(key=lambda c: c.activation, reverse=True)
        return results[:limit]

    def retrieve_by_id(self, chunk_id: str) -> Optional[WorkingMemoryChunk]:
        self._apply_decay()
        chunk = self._chunks.get(chunk_id)
        if chunk is not None:
            chunk.update_activation(min(1.0, chunk.activation + 0.1))
        return chunk

    def forget(self, chunk_id: str) -> bool:
        return self._chunks.pop(chunk_id, None) is not None

    def clear(self) -> None:
        self._chunks.clear()

    def retrieve_all(self) -> list[WorkingMemoryChunk]:
        self._apply_decay()
        return list(self._chunks.values())

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def get_metrics(self) -> dict[str, Any]:
        chunks = self.retrieve_all()
        total_items = len(chunks)
        average_activation = sum(chunk.activation for chunk in chunks) / total_items if chunks else 0.0
        low_activation_ratio = (
            sum(1 for chunk in chunks if chunk.activation < 0.3) / total_items if chunks else 0.0
        )
        capacity_ratio = total_items / self._capacity if self._capacity else 0.0

        return {
            "total_items": total_items,
            "average_activation": average_activation,
            "low_activation_ratio": low_activation_ratio,
            "capacity_ratio": capacity_ratio,
        }

    def dump(self) -> list[dict[str, Any]]:
        return [
            {
                "id": chunk.id,
                "content": chunk.content,
                "activation": chunk.activation,
                "metadata": chunk.metadata,
                "created_at": chunk.created_at.isoformat(),
                "last_accessed": chunk.last_accessed.isoformat(),
            }
            for chunk in self.retrieve_all()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _apply_decay(self) -> None:
        if self._decay_rate == 0 or not self._chunks:
            self._last_decay_time = time.time()
            return

        current_time = time.time()
        elapsed = current_time - self._last_decay_time
        if elapsed <= 0:
            return

        decay_factor = min(1.0, self._decay_rate * elapsed)
        expired: list[str] = []

        for chunk_id, chunk in self._chunks.items():
            new_activation = chunk.activation * (1 - decay_factor)
            if new_activation < 0.05:
                expired.append(chunk_id)
            else:
                chunk.update_activation(new_activation)

        for chunk_id in expired:
            self._chunks.pop(chunk_id, None)

        self._last_decay_time = current_time

    def _get_least_active_chunk_id(self) -> Optional[str]:
        if not self._chunks:
            return None
        return min(self._chunks.items(), key=lambda item: item[1].activation)[0]
