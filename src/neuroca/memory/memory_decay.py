"""Time-aware forgetting engine for the legacy memory facades."""

from __future__ import annotations

import asyncio
import enum
import logging
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from neuroca.core.events.handlers import Event, event_bus

try:  # pragma: no cover - exercised indirectly via fallback tests
    from neuroca.core.events.memory import MemoryDecayEvent, MemoryType
except ModuleNotFoundError:  # pragma: no cover - legacy environments without event module
    class MemoryType(str, enum.Enum):
        WORKING = "working"
        EPISODIC = "episodic"
        SEMANTIC = "semantic"
        PROCEDURAL = "procedural"

    class MemoryDecayEvent(Event):
        def __init__(self, *, memory_id: str, memory_type: MemoryType,
                     content: Optional[Dict[str, Any]] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     decay_factor: float = 0.0) -> None:
            super().__init__()
            self.memory_id = memory_id
            self.memory_type = memory_type
            self.content = content
            self.metadata = metadata or {}
            self.decay_factor = decay_factor
from neuroca.core.memory.episodic_memory import EpisodicMemory
from neuroca.core.memory.working_memory import WorkingMemory
from neuroca.memory.semantic_memory import SemanticMemory

logger = logging.getLogger(__name__)
@dataclass
class DecayCounters:
    """Mutable counters collected for each tier during a decay cycle."""

    processed: int = 0
    decayed: int = 0
    removed: int = 0
    events: int = 0

    def as_dict(self) -> Dict[str, int]:
        """Return a serialisable representation of the counters."""

        return {
            "processed": self.processed,
            "decayed": self.decayed,
            "removed": self.removed,
            "events": self.events,
        }


class MemoryDecay:
    """Apply exponential decay and forgetting rules across legacy memory tiers."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "working": {
            "half_life_seconds": 180.0,
            "min_activation": 0.05,
            "max_decay_per_run": 0.9,
            "importance_penalty": 0.5,
        },
        "episodic": {
            "half_life_seconds": 900.0,
            "min_activation": 0.05,
            "max_decay_per_run": 0.85,
            "salience_weight": 0.6,
            "importance_penalty": 0.35,
        },
        "semantic": {
            "concept_half_life_seconds": 43200.0,
            "relationship_half_life_seconds": 21600.0,
            "min_concept_strength": 0.1,
            "min_relationship_strength": 0.05,
            "max_decay_per_run": 0.8,
            "importance_penalty": 0.4,
        },
        "events": {"enabled": True},
    }
    def __init__(
        self,
        working_memory: Optional[WorkingMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        config: Optional[Dict[str, Any]] = None,
        *,
        event_publisher=None,
    ) -> None:
        self.working_memory = working_memory
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.config = self._merge_config(config or {})
        self._event_publisher = event_publisher or event_bus.publish
        self._last_run_at = datetime.now(UTC)

    def process(self) -> Dict[str, Any]:
        """Synchronously execute a decay cycle and emit events."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "MemoryDecay.process() cannot be used while an event loop is running. "
                "Use `await MemoryDecay.process_async()` instead."
            )

        stats, events = self._run_decay_cycle()
        if events:
            asyncio.run(self._publish_events_async(events))
        return stats

    async def process_async(self) -> Dict[str, Any]:
        """Asynchronously execute a decay cycle and await event publication."""

        stats, events = self._run_decay_cycle()
        if events:
            await self._publish_events_async(events)
        return stats

    def _run_decay_cycle(self) -> Tuple[Dict[str, Any], List[MemoryDecayEvent]]:
        now = datetime.now(UTC)
        logger.debug("Starting decay cycle at %s", now.isoformat())

        summary = {
            "timestamp": now.isoformat(),
            "total_processed": 0,
            "total_decayed": 0,
            "total_removed": 0,
            "events_emitted": 0,
            "per_tier": {},
        }
        all_events: List[MemoryDecayEvent] = []

        for tier_name, handler in (
            ("working", self._decay_working_memory),
            ("episodic", self._decay_episodic_memory),
            ("semantic", self._decay_semantic_memory),
        ):
            stats, events = handler(now)
            summary["per_tier"][tier_name] = stats
            summary["total_processed"] += stats["processed"]
            summary["total_decayed"] += stats["decayed"]
            summary["total_removed"] += stats["removed"]
            summary["events_emitted"] += stats["events"]
            all_events.extend(events)

        self._last_run_at = now
        logger.debug("Decay cycle completed with summary: %s", summary)
        return summary, all_events

    def _decay_working_memory(self, now: datetime) -> Tuple[Dict[str, int], List[MemoryDecayEvent]]:
        counters = DecayCounters()
        events: List[MemoryDecayEvent] = []
        if not self.working_memory:
            return counters.as_dict(), events

        config = self.config["working"]
        chunks = list(self.working_memory.retrieve_all())
        counters.processed = len(chunks)

        for chunk in chunks:
            metadata = chunk.metadata if isinstance(chunk.metadata, dict) else {}
            last_accessed = self._coerce_datetime(getattr(chunk, "last_accessed", now), now)
            age_seconds = max(0.0, (now - last_accessed).total_seconds())
            strength = float(getattr(chunk, "activation", 0.0))

            importance = float(metadata.get("importance", 0.5))
            weight = 1.0 + (1.0 - importance) * config.get("importance_penalty", 0.0)
            decay_ratio = self._compute_decay_ratio(
                age_seconds,
                config["half_life_seconds"],
                max_ratio=config.get("max_decay_per_run", 1.0),
                weight=weight,
            )

            if decay_ratio <= 0.0 and strength >= config["min_activation"]:
                continue

            new_strength = max(0.0, strength * (1.0 - decay_ratio))
            status = "decayed"

            if new_strength < config["min_activation"]:
                status = "removed"
                counters.removed += 1
                new_strength = 0.0
                self.working_memory.forget(chunk.id)
            else:
                counters.decayed += 1
                chunk.activation = new_strength
                metadata.setdefault("strength", new_strength)
                metadata["strength"] = new_strength
                metadata["last_decay_at"] = now.isoformat()

            event = self._build_decay_event(
                memory_id=chunk.id,
                memory_type=MemoryType.WORKING,
                previous_strength=strength,
                new_strength=new_strength,
                decay_ratio=decay_ratio if strength > 0 else 0.0,
                age_seconds=age_seconds,
                last_accessed=last_accessed,
                tier="working",
                status=status,
                metadata_source=metadata,
                content={"text": self._safe_text(getattr(chunk, "content", ""))},
            )
            if event:
                events.append(event)

        counters.events = len(events) if self.config["events"]["enabled"] else 0
        return counters.as_dict(), events if self.config["events"]["enabled"] else []

    def _decay_episodic_memory(self, now: datetime) -> Tuple[Dict[str, int], List[MemoryDecayEvent]]:
        counters = DecayCounters()
        events: List[MemoryDecayEvent] = []
        if not self.episodic_memory:
            return counters.as_dict(), events

        config = self.config["episodic"]
        episodes = list(self.episodic_memory.retrieve_all())
        counters.processed = len(episodes)

        for episode in episodes:
            metadata = episode.metadata if isinstance(episode.metadata, dict) else {}
            last_accessed = self._coerce_datetime(getattr(episode, "last_accessed", now), now)
            age_seconds = max(0.0, (now - last_accessed).total_seconds())
            strength = float(getattr(episode, "activation", 0.0))
            salience = float(metadata.get("emotional_salience", episode.emotional_salience))
            importance = float(metadata.get("importance", salience))

            weight = 1.0
            weight += (1.0 - salience) * config.get("salience_weight", 0.0)
            weight += (1.0 - importance) * config.get("importance_penalty", 0.0)

            decay_ratio = self._compute_decay_ratio(
                age_seconds,
                config["half_life_seconds"],
                max_ratio=config.get("max_decay_per_run", 1.0),
                weight=weight,
            )

            if decay_ratio <= 0.0 and strength >= config["min_activation"]:
                continue

            new_strength = max(0.0, strength * (1.0 - decay_ratio))
            status = "decayed"

            if new_strength < config["min_activation"]:
                status = "removed"
                counters.removed += 1
                new_strength = 0.0
                self.episodic_memory.forget(episode.id)
            else:
                counters.decayed += 1
                episode.activation = new_strength
                metadata.setdefault("strength", new_strength)
                metadata["strength"] = new_strength
                metadata["last_decay_at"] = now.isoformat()

            event = self._build_decay_event(
                memory_id=episode.id,
                memory_type=MemoryType.EPISODIC,
                previous_strength=strength,
                new_strength=new_strength,
                decay_ratio=decay_ratio if strength > 0 else 0.0,
                age_seconds=age_seconds,
                last_accessed=last_accessed,
                tier="episodic",
                status=status,
                metadata_source=metadata,
                content={"text": self._safe_text(getattr(episode, "content", ""))},
            )
            if event:
                events.append(event)

        counters.events = len(events) if self.config["events"]["enabled"] else 0
        return counters.as_dict(), events if self.config["events"]["enabled"] else []

    def _decay_semantic_memory(self, now: datetime) -> Tuple[Dict[str, int], List[MemoryDecayEvent]]:
        counters = DecayCounters()
        events: List[MemoryDecayEvent] = []
        if not self.semantic_memory:
            return counters.as_dict(), events

        config = self.config["semantic"]
        concepts = list(self.semantic_memory.retrieve_all_concepts())
        relationships = list(self.semantic_memory.retrieve_all_relationships())
        counters.processed = len(concepts) + len(relationships)

        for concept in concepts:
            properties = concept.properties if isinstance(concept.properties, dict) else {}
            last_seen = properties.get("last_accessed_at") or properties.get("last_updated_at")
            last_accessed = self._coerce_datetime(last_seen, now)
            age_seconds = max(0.0, (now - last_accessed).total_seconds())
            strength = float(properties.get("stability", 1.0))
            importance = float(properties.get("importance", 0.5))

            weight = 1.0 + (1.0 - importance) * config.get("importance_penalty", 0.0)
            decay_ratio = self._compute_decay_ratio(
                age_seconds,
                config["concept_half_life_seconds"],
                max_ratio=config.get("max_decay_per_run", 1.0),
                weight=weight,
            )

            if decay_ratio <= 0.0 and strength >= config["min_concept_strength"]:
                continue

            new_strength = max(0.0, strength * (1.0 - decay_ratio))
            status = "decayed"

            if new_strength < config["min_concept_strength"]:
                status = "removed"
                counters.removed += 1
                new_strength = 0.0
                self.semantic_memory.forget_concept(concept.id)
            else:
                counters.decayed += 1
                properties["stability"] = new_strength
                properties["last_accessed_at"] = now.isoformat()

            event = self._build_decay_event(
                memory_id=concept.id,
                memory_type=MemoryType.SEMANTIC,
                previous_strength=strength,
                new_strength=new_strength,
                decay_ratio=decay_ratio if strength > 0 else 0.0,
                age_seconds=age_seconds,
                last_accessed=last_accessed,
                tier="semantic",
                status=status,
                metadata_source=properties,
                content={"concept": concept.name, "type": "concept"},
            )
            if event:
                events.append(event)

        for relationship in relationships:
            metadata = relationship.metadata if isinstance(relationship.metadata, dict) else {}
            last_seen = metadata.get("last_accessed_at") or metadata.get("last_updated_at")
            last_accessed = self._coerce_datetime(last_seen, now)
            age_seconds = max(0.0, (now - last_accessed).total_seconds())
            strength = float(getattr(relationship, "strength", 0.0))
            importance = float(metadata.get("importance", 0.5))

            weight = 1.0 + (1.0 - importance) * config.get("importance_penalty", 0.0)
            decay_ratio = self._compute_decay_ratio(
                age_seconds,
                config["relationship_half_life_seconds"],
                max_ratio=config.get("max_decay_per_run", 1.0),
                weight=weight,
            )

            if decay_ratio <= 0.0 and strength >= config["min_relationship_strength"]:
                continue

            new_strength = max(0.0, strength * (1.0 - decay_ratio))
            status = "decayed"

            if new_strength < config["min_relationship_strength"]:
                status = "removed"
                counters.removed += 1
                new_strength = 0.0
                self.semantic_memory._remove_relationship(relationship.id)
            else:
                counters.decayed += 1
                relationship.strength = new_strength
                metadata["strength"] = new_strength
                metadata["last_accessed_at"] = now.isoformat()

            event = self._build_decay_event(
                memory_id=relationship.id,
                memory_type=MemoryType.SEMANTIC,
                previous_strength=strength,
                new_strength=new_strength,
                decay_ratio=decay_ratio if strength > 0 else 0.0,
                age_seconds=age_seconds,
                last_accessed=last_accessed,
                tier="semantic",
                status=status,
                metadata_source=metadata,
                content={
                    "type": "relationship",
                    "relationship_type": relationship.relationship_type,
                    "source_id": relationship.source_id,
                    "target_id": relationship.target_id,
                },
            )
            if event:
                events.append(event)

        counters.events = len(events) if self.config["events"]["enabled"] else 0
        return counters.as_dict(), events if self.config["events"]["enabled"] else []

    async def _publish_events_async(self, events: Iterable[MemoryDecayEvent]) -> None:
        if not self.config["events"]["enabled"]:
            return
        for event in events:
            await self._event_publisher(event)

    def _compute_decay_ratio(
        self,
        age_seconds: float,
        half_life_seconds: float,
        *,
        max_ratio: float,
        weight: float = 1.0,
    ) -> float:
        if age_seconds <= 0 or half_life_seconds <= 0:
            return 0.0

        decay_constant = math.log(2.0) / half_life_seconds
        ratio = 1.0 - math.exp(-decay_constant * age_seconds)
        ratio *= max(weight, 0.0)
        ratio = min(max_ratio, ratio)
        return max(0.0, min(1.0, ratio))

    def _build_decay_event(
        self,
        *,
        memory_id: str,
        memory_type: MemoryType,
        previous_strength: float,
        new_strength: float,
        decay_ratio: float,
        age_seconds: float,
        last_accessed: datetime,
        tier: str,
        status: str,
        metadata_source: Optional[Dict[str, Any]] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryDecayEvent]:
        if not self.config["events"]["enabled"]:
            return None

        metadata = {
            "tier": tier,
            "status": status,
            "previous_strength": previous_strength,
            "new_strength": new_strength,
            "age_seconds": age_seconds,
            "last_accessed_at": last_accessed.isoformat(),
        }

        if metadata_source:
            for key in ("importance", "strength", "emotional_salience", "tags"):
                if key in metadata_source:
                    metadata[key] = metadata_source[key]

        try:
            event = MemoryDecayEvent(
                memory_id=memory_id,
                memory_type=memory_type,
                content=content,
                metadata=metadata,
                decay_factor=min(1.0, max(0.0, decay_ratio)),
            )
        except Exception:  # pragma: no cover - safety net for malformed payloads
            logger.exception("Failed to build MemoryDecayEvent for %s", memory_id)
            return None

        return event

    def _merge_config(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        base = deepcopy(self.DEFAULT_CONFIG)
        for key, value in overrides.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                base[key].update(value)
            else:
                base[key] = value
        return base

    def _coerce_datetime(self, value: Any, default: datetime) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return default
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return default

    def _safe_text(self, value: Any) -> str:
        text = str(value) if value is not None else ""
        return text[:512]


__all__ = ["MemoryDecay"]

