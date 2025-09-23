"""Cross-tier retrieval helpers for the legacy memory facade.

The modern Neuroca memory manager exposes an extensive asynchronous interface,
however several integration points – notably documentation snippets and legacy
health checks – still rely on the synchronous ``MemorySystem`` façade.  The
original implementation exposed a stub that always returned an empty list which
meant those integrations could not surface real memory data.  The implementation
provided here performs lightweight retrievals against the tiered memory
components so the legacy façade remains functional without depending on the
full manager stack.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from neuroca.memory.episodic_memory import EpisodicMemory
from neuroca.memory.semantic_memory import SemanticMemory
from neuroca.memory.working_memory import WorkingMemory
from neuroca.memory.models import (
    MemoryContent,
    MemoryItem,
    MemoryMetadata,
    MemoryQuery,
    MemoryRetrievalResult,
)

logger = logging.getLogger(__name__)


class MemoryRetrieval:
    """Provide convenience search utilities across legacy memory tiers."""

    DEFAULT_TIERS: Tuple[str, str, str] = ("working", "episodic", "semantic")

    def __init__(
        self,
        working_memory: Optional[WorkingMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store memory tier references and retrieval configuration."""

        self.working_memory = working_memory
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.config = config or {}
        self._default_limit = max(1, int(self.config.get("default_limit", 10)))
        self._tier_handlers: Dict[str, Callable[[str, int, float, Dict[str, Any]], List[MemoryRetrievalResult]]] = {
            "working": self._search_working,
            "episodic": self._search_episodic,
            "semantic": self._search_semantic,
        }

    def search(
        self,
        query: Any,
        tiers: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.0,
    ) -> List[MemoryRetrievalResult]:
        """Search across the requested tiers and return unified results."""

        tiers = self._normalize_tiers(tiers)
        query_text, filters = self._parse_query(query)
        per_tier_limit = limit or self._default_limit
        threshold = max(0.0, min(1.0, threshold))

        logger.debug(
            "Executing MemoryRetrieval.search query=%s tiers=%s limit=%s threshold=%s",
            query_text,
            tiers,
            per_tier_limit,
            threshold,
        )

        results: List[MemoryRetrievalResult] = []
        for tier in tiers:
            handler = self._tier_handlers.get(tier)
            if handler is None:
                logger.debug("Skipping unsupported tier: %s", tier)
                continue
            tier_results = handler(query_text, per_tier_limit, threshold, filters)
            results.extend(tier_results)

        results.sort(key=lambda result: result.relevance_score, reverse=True)
        overall_limit = per_tier_limit * len(tiers)
        return results[:overall_limit]

    def _normalize_tiers(self, tiers: Optional[Iterable[str]]) -> List[str]:
        """Return a validated list of tiers preserving caller order."""

        if tiers is None:
            return list(self.DEFAULT_TIERS)
        normalized: List[str] = []
        for tier in tiers:
            tier_name = str(tier).lower()
            if tier_name not in self._tier_handlers:
                raise ValueError(
                    f"Invalid memory tier specified: {tier_name}. Valid tiers are: {list(self._tier_handlers)}"
                )
            if tier_name not in normalized:
                normalized.append(tier_name)
        return normalized

    def _parse_query(self, query: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract a query string and filter payload from arbitrary inputs."""

        if query is None:
            return "", {}
        if isinstance(query, MemoryQuery):  # pragma: no branch - optional dependency
            return str(getattr(query, "query", "") or ""), dict(getattr(query, "filters", {}) or {})
        if isinstance(query, dict):
            filters = dict(query)
            base_query = str(filters.pop("query", filters.pop("text", "")) or "")
            return base_query, filters
        return str(query), {}

    def _search_working(
        self,
        query_text: str,
        limit: int,
        threshold: float,
        filters: Dict[str, Any],
    ) -> List[MemoryRetrievalResult]:
        """Search the working-memory tier using substring matching."""

        if self.working_memory is None:
            return []

        raw_chunks = self.working_memory.retrieve(query_text, limit=limit)
        results: List[MemoryRetrievalResult] = []
        for chunk in raw_chunks:
            metadata_dict = dict(getattr(chunk, "metadata", {}))
            metadata_dict.setdefault("tier", "working")
            metadata_dict.setdefault("created_at", getattr(chunk, "created_at", datetime.now(UTC)))
            metadata_dict.setdefault("last_accessed", getattr(chunk, "last_accessed", datetime.now(UTC)))
            metadata_dict.setdefault("strength", getattr(chunk, "activation", 0.5))
            metadata_dict.setdefault("importance", metadata_dict.get("strength", 0.5))
            metadata_dict.setdefault("relevance", metadata_dict.get("strength", 0.5))
            if not self._passes_filters(metadata_dict, filters):
                continue
            relevance = float(metadata_dict.get("relevance", 0.0))
            if relevance < threshold:
                continue
            item = self._build_item(
                identifier=str(getattr(chunk, "id", "")),
                content=getattr(chunk, "content", None),
                summary=metadata_dict.get("summary"),
                tier="working",
                metadata_dict=metadata_dict,
                created_at=metadata_dict["created_at"],
                last_accessed=metadata_dict["last_accessed"],
                importance=float(metadata_dict.get("importance", relevance)),
                strength=float(metadata_dict.get("strength", relevance)),
            )
            results.append(
                MemoryRetrievalResult(
                    memory=item,
                    tier="working",
                    relevance_score=min(1.0, max(0.0, relevance)),
                    metadata=metadata_dict,
                    summary=item.summary,
                )
            )
        return results

    def _search_episodic(
        self,
        query_text: str,
        limit: int,
        threshold: float,
        filters: Dict[str, Any],
    ) -> List[MemoryRetrievalResult]:
        """Search episodic memory using emotional salience as relevance."""

        if self.episodic_memory is None:
            return []

        raw_chunks = self.episodic_memory.retrieve(query_text, limit=limit)
        results: List[MemoryRetrievalResult] = []
        for chunk in raw_chunks:
            metadata_dict = dict(getattr(chunk, "metadata", {}))
            metadata_dict.setdefault("tier", "episodic")
            metadata_dict.setdefault("created_at", getattr(chunk, "created_at", datetime.now(UTC)))
            metadata_dict.setdefault("last_accessed", getattr(chunk, "last_accessed", datetime.now(UTC)))
            metadata_dict.setdefault("emotional_salience", getattr(chunk, "emotional_salience", 0.5))
            metadata_dict.setdefault("strength", getattr(chunk, "activation", 0.5))
            if not self._passes_filters(metadata_dict, filters):
                continue
            emotional = float(metadata_dict.get("emotional_salience", 0.0))
            activation = float(metadata_dict.get("strength", 0.0))
            relevance = max(0.0, min(1.0, (emotional + activation) / 2))
            if relevance < threshold:
                continue
            item = self._build_item(
                identifier=str(getattr(chunk, "id", "")),
                content=getattr(chunk, "content", None),
                summary=metadata_dict.get("summary"),
                tier="episodic",
                metadata_dict=metadata_dict,
                created_at=metadata_dict["created_at"],
                last_accessed=metadata_dict["last_accessed"],
                importance=float(metadata_dict.get("importance", emotional)),
                strength=activation,
            )
            results.append(
                MemoryRetrievalResult(
                    memory=item,
                    tier="episodic",
                    relevance_score=relevance,
                    metadata=metadata_dict,
                    summary=item.summary,
                )
            )
        return results

    def _search_semantic(
        self,
        query_text: str,
        limit: int,
        threshold: float,
        filters: Dict[str, Any],
    ) -> List[MemoryRetrievalResult]:
        """Search semantic memory by matching concept metadata."""

        if self.semantic_memory is None:
            return []

        concepts = self.semantic_memory.retrieve_all_concepts()
        results: List[MemoryRetrievalResult] = []
        for concept in concepts:
            text_parts = [concept.name or "", concept.description or ""]
            text_parts.extend(str(value) for value in concept.properties.values())
            aggregated_text = " \n".join(text_parts)
            relevance = self._text_similarity(query_text, aggregated_text)
            if relevance < threshold:
                continue
            metadata_dict: Dict[str, Any] = {
                "tier": "semantic",
                "concept_name": concept.name,
                "properties": dict(concept.properties),
                "created_at": datetime.now(UTC),
                "last_accessed": datetime.now(UTC),
                "importance": relevance,
                "strength": relevance,
            }
            if not self._passes_filters(metadata_dict, filters):
                continue
            item = self._build_item(
                identifier=concept.id,
                content={
                    "text": concept.description or concept.name,
                    "summary": concept.description or concept.name,
                },
                summary=concept.description or concept.name,
                tier="semantic",
                metadata_dict=metadata_dict,
                created_at=metadata_dict["created_at"],
                last_accessed=metadata_dict["last_accessed"],
                importance=relevance,
                strength=relevance,
            )
            results.append(
                MemoryRetrievalResult(
                    memory=item,
                    tier="semantic",
                    relevance_score=relevance,
                    metadata=metadata_dict,
                    summary=item.summary,
                )
            )
        results.sort(key=lambda result: result.relevance_score, reverse=True)
        return results[:limit]

    def _build_item(
        self,
        *,
        identifier: str,
        content: Any,
        summary: Optional[str],
        tier: str,
        metadata_dict: Dict[str, Any],
        created_at: datetime,
        last_accessed: datetime,
        importance: float,
        strength: float,
    ) -> MemoryItem:
        """Construct a :class:`MemoryItem` instance for the retrieval result."""

        metadata = self._build_metadata(
            tier=tier,
            metadata_dict=metadata_dict,
            created_at=created_at,
            last_accessed=last_accessed,
            importance=importance,
            strength=strength,
        )
        content_model = self._build_content(content)
        return MemoryItem(id=identifier, content=content_model, metadata=metadata, summary=summary)

    def _build_metadata(
        self,
        *,
        tier: str,
        metadata_dict: Dict[str, Any],
        created_at: datetime,
        last_accessed: datetime,
        importance: float,
        strength: float,
    ) -> MemoryMetadata:
        """Create :class:`MemoryMetadata` with additional metadata preserved."""

        payload = dict(metadata_dict)
        tags = self._coerce_tags(payload.pop("tags", {}))
        metadata = MemoryMetadata(
            created_at=payload.pop("created_at", created_at),
            last_accessed=payload.pop("last_accessed", last_accessed),
            importance=float(payload.pop("importance", importance)),
            strength=float(payload.pop("strength", strength)),
            tags=tags,
        )
        metadata.tier = payload.pop("tier", tier)
        metadata.user_id = payload.pop("user_id", metadata.user_id)
        metadata.session_id = payload.pop("session_id", metadata.session_id)
        metadata.tenant_id = payload.pop("tenant_id", metadata.tenant_id)
        metadata.shared_with = payload.pop("shared_with", metadata.shared_with)
        metadata.source = payload.pop("source", metadata.source)
        metadata.status = payload.pop("status", metadata.status)
        metadata.embedding_model = payload.pop("embedding_model", metadata.embedding_model)
        metadata.embedding_dimensions = payload.pop("embedding_dimensions", metadata.embedding_dimensions)
        metadata.expires_at = payload.pop("expires_at", metadata.expires_at)
        metadata.priority = payload.pop("priority", metadata.priority)
        metadata.consolidated_from = payload.pop("consolidated_from", metadata.consolidated_from)
        metadata.consolidated_at = payload.pop("consolidated_at", metadata.consolidated_at)
        additional = payload.pop("additional_metadata", {})
        if isinstance(additional, dict):
            metadata.additional_metadata.update(additional)
        metadata.additional_metadata.update(payload)
        return metadata

    def _build_content(self, value: Any) -> MemoryContent:
        """Coerce arbitrary content values into :class:`MemoryContent`."""

        if isinstance(value, MemoryContent):
            return value
        if isinstance(value, dict):
            return MemoryContent(**value)
        return MemoryContent(text=str(value))

    def _coerce_tags(self, value: Any) -> Dict[str, Any]:
        """Return a dictionary representation for tag payloads."""

        if value is None:
            return {}
        if isinstance(value, dict):
            return {str(key): tag for key, tag in value.items()}
        if isinstance(value, (list, set, tuple)):
            return {str(tag): True for tag in value}
        return {str(value): True}

    def _passes_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Return ``True`` when metadata satisfies the provided filters."""

        if not filters:
            return True
        meta_filters = filters.get("metadata", {})
        for key, expected in meta_filters.items():
            if metadata.get(key) != expected:
                return False
        tags_filter = filters.get("tags")
        if tags_filter:
            tags = self._coerce_tags(metadata.get("tags"))
            required = {str(tag) for tag in tags_filter}
            if not required.issubset(set(tags)):
                return False
        for key, expected in filters.items():
            if key in {"metadata", "tags"}:
                continue
            if metadata.get(key) != expected:
                return False
        return True

    def _text_similarity(self, query_text: str, candidate_text: str) -> float:
        """Return a normalised similarity score between two strings."""

        if not query_text:
            return 1.0
        score = SequenceMatcher(None, query_text.lower(), candidate_text.lower()).ratio()
        return max(0.0, min(1.0, float(score)))


__all__ = ["MemoryRetrieval"]

