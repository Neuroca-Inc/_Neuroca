"""Legacy synchronous episodic-memory implementation."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from neuroca.core.memory.interfaces import MemorySystem


@dataclass
class EpisodicMemoryChunk:
    """Container describing a single episodic memory."""

    content: Any
    emotional_salience: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    activation: float = 1.0

    def __post_init__(self) -> None:
        if "timestamp" in self.metadata and self.metadata["timestamp"] is None:
            self.metadata.pop("timestamp")
        self.metadata.setdefault("emotional_salience", float(self.emotional_salience))

    def update_activation(self, value: Optional[float] = None) -> None:
        if value is not None:
            self.activation = max(0.0, min(1.0, float(value)))
        self.last_accessed = datetime.now(UTC)


class EpisodicMemory(MemorySystem):
    """In-memory episodic store retaining temporal and emotional metadata."""

    def __init__(self, decay_rate: float = 0.01) -> None:
        self._name = "episodic_memory"
        self._decay_rate = max(0.0, decay_rate)
        self._last_decay_time = time.time()
        self._chunks: dict[str, EpisodicMemoryChunk] = {}
        self._sequence_index: dict[int, list[str]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> None:
        return None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def store(
        self,
        content: Any,
        *,
        emotional_salience: float = 0.5,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        metadata = metadata.copy() if metadata else {}
        chunk = EpisodicMemoryChunk(content=content, emotional_salience=emotional_salience, metadata=metadata)
        self._apply_decay()

        self._chunks[chunk.id] = chunk
        sequence_id = int(chunk.metadata.get("sequence_id", chunk.metadata.get("timestamp", chunk.created_at.timestamp())))
        self._sequence_index.setdefault(sequence_id, []).append(chunk.id)
        return chunk.id

    def retrieve(
        self,
        query: Any,
        limit: int = 10,
        *,
        min_emotional_salience: float = 0.0,
        temporal_range: tuple[Optional[float], Optional[float]] = (None, None),
        **parameters: Any,
    ) -> list[EpisodicMemoryChunk]:
        self._apply_decay()
        query_str = str(query).lower()
        start_ts, end_ts = temporal_range
        results: list[EpisodicMemoryChunk] = []

        for chunk in self._chunks.values():
            metadata = chunk.metadata
            timestamp = float(metadata.get("timestamp", chunk.created_at.timestamp()))
            if start_ts is not None and timestamp < start_ts:
                continue
            if end_ts is not None and timestamp > end_ts:
                continue
            if chunk.emotional_salience < min_emotional_salience:
                continue
            if query_str in str(chunk.content).lower():
                chunk.update_activation(min(1.0, chunk.activation + 0.1))
                results.append(chunk)

        results.sort(key=lambda c: (c.emotional_salience, c.activation), reverse=True)
        return results[:limit]

    def retrieve_by_id(self, chunk_id: str) -> Optional[EpisodicMemoryChunk]:
        self._apply_decay()
        chunk = self._chunks.get(chunk_id)
        if chunk is not None:
            chunk.update_activation(min(1.0, chunk.activation + 0.05))
        return chunk

    def forget(self, chunk_id: str) -> bool:
        chunk = self._chunks.pop(chunk_id, None)
        if chunk is None:
            return False
        for ids in self._sequence_index.values():
            if chunk_id in ids:
                ids.remove(chunk_id)
        return True

    def clear(self) -> None:
        self._chunks.clear()
        self._sequence_index.clear()

    def retrieve_all(self) -> list[EpisodicMemoryChunk]:
        self._apply_decay()
        return list(self._chunks.values())

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def get_all_items(self) -> list[EpisodicMemoryChunk]:
        return self.retrieve_all()

    def get_metrics(self) -> dict[str, Any]:
        chunks = self.retrieve_all()
        total_items = len(chunks)
        timestamps = [
            chunk.metadata.get("timestamp")
            for chunk in chunks
            if "timestamp" in chunk.metadata and chunk.metadata.get("timestamp") is not None
        ]
        timestamp_ratio = len(timestamps) / total_items if total_items else 0.0
        emotional_values = [chunk.metadata.get("emotional_salience", 0.0) for chunk in chunks]
        average_emotion = sum(emotional_values) / total_items if total_items else 0.0
        high_emotion_count = sum(value >= 0.7 for value in emotional_values)
        sequence_item_ratio = sum(len(ids) for ids in self._sequence_index.values()) / total_items if total_items else 0.0

        return {
            "total_items": total_items,
            "timestamp_ratio": timestamp_ratio,
            "avg_emotional_salience": average_emotion,
            "high_emotion_count": high_emotion_count,
            "sequence_item_ratio": sequence_item_ratio,
        }

    def dump(self) -> list[dict[str, Any]]:
        return [
            {
                "id": chunk.id,
                "content": chunk.content,
                "emotional_salience": chunk.emotional_salience,
                "metadata": chunk.metadata,
                "activation": chunk.activation,
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

        for chunk in list(self._chunks.values()):
            salience = max(0.1, chunk.metadata.get("emotional_salience", chunk.emotional_salience))
            decay_factor = self._decay_rate * elapsed * (1.0 - salience)
            new_activation = chunk.activation * (1 - decay_factor)
            if new_activation < 0.02:
                self.forget(chunk.id)
            else:
                chunk.update_activation(new_activation)

        self._last_decay_time = current_time
