"""Semantic summarization utilities for tier consolidation."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence


try:  # pragma: no cover - optional dependency for richer defaults
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as _SKLEARN_STOP_WORDS
except ImportError:  # pragma: no cover - fallback when sklearn unavailable
    _SKLEARN_STOP_WORDS = frozenset()


def _normalise_scalar(value: Any) -> str:
    """Convert primitive values to their string representation."""

    if value is None:
        return ""
    if isinstance(value, (str, bytes)):
        return value.decode() if isinstance(value, bytes) else value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _flatten_content(value: Any, *, max_depth: int = 4, _depth: int = 0) -> str:
    """Best-effort conversion of arbitrary content structures into text."""

    if _depth >= max_depth:
        return ""

    scalar = _normalise_scalar(value)
    if scalar:
        return scalar

    if isinstance(value, Mapping):
        parts: List[str] = []
        for item in value.values():
            flattened = _flatten_content(item, max_depth=max_depth, _depth=_depth + 1)
            if flattened:
                parts.append(flattened)
        return " ".join(parts)

    if isinstance(value, (list, tuple, set, frozenset)):
        parts = [
            _flatten_content(item, max_depth=max_depth, _depth=_depth + 1)
            for item in value
        ]
        return " ".join(part for part in parts if part)

    return str(value) if value is not None else ""


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences while keeping punctuation."""

    text = (text or "").strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _tokenise(text: str) -> List[str]:
    """Tokenise text into lowercase word tokens."""

    return re.findall(r"\b[\w']+\b", text.lower())


_BASE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}

DEFAULT_STOP_WORDS = frozenset({*_BASE_STOP_WORDS, *_SKLEARN_STOP_WORDS})


@dataclass
class SummarizationOptions:
    """Tunable knobs for controlling summarisation output."""

    max_batch_summary_sentences: int = 3
    max_item_summary_sentences: int = 2
    max_keywords: int = 6

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, Any]]) -> "SummarizationOptions":
        if not config:
            return cls()

        def _clamped_int(key: str, default: int, minimum: int = 1) -> int:
            value = int(config.get(key, default))
            return max(minimum, value)

        return cls(
            max_batch_summary_sentences=_clamped_int("max_batch_summary_sentences", 3),
            max_item_summary_sentences=_clamped_int("max_item_summary_sentences", 2),
            max_keywords=_clamped_int("max_keywords", 6),
        )


@dataclass
class SummarizationPayload:
    """Normalised input for summarisation backends."""

    memory_id: str
    text: str
    importance: float = 0.5
    tags: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def importance_weight(self) -> float:
        """Return a bounded importance weight for scoring."""

        return max(0.0, min(1.0, float(self.importance or 0.0))) + 0.5


@dataclass
class BatchSummary:
    """Container describing aggregated summarisation results."""

    aggregated_summary: str
    per_item: Dict[str, str]
    keywords: List[str]
    highlights: Dict[str, List[str]] = field(default_factory=dict)
    batch_metadata: Dict[str, Any] = field(default_factory=dict)


class SummarizationBackend:
    """Interface implemented by summarisation backends."""

    def summarize_batch(
        self,
        payloads: Sequence[SummarizationPayload],
        *,
        options: SummarizationOptions,
    ) -> BatchSummary:
        raise NotImplementedError


class KeywordFrequencyBackend(SummarizationBackend):
    """Heuristic backend that performs weighted keyword extraction."""

    def __init__(
        self,
        *,
        stop_words: Optional[Iterable[str]] = None,
    ) -> None:
        self._stop_words = set(stop_words or DEFAULT_STOP_WORDS)

    def summarize_batch(
        self,
        payloads: Sequence[SummarizationPayload],
        *,
        options: SummarizationOptions,
    ) -> BatchSummary:
        if not payloads:
            return BatchSummary(
                aggregated_summary="",
                per_item={},
                keywords=[],
                highlights={},
                batch_metadata={"sources": []},
            )

        per_item_sentences: Dict[str, List[tuple[int, str]]] = {}
        combined_sentences: List[tuple[str, int, str, float]] = []
        token_weights: Dict[str, float] = {}
        tag_weights: Dict[str, float] = {}
        order_lookup = {payload.memory_id: index for index, payload in enumerate(payloads)}

        for payload in payloads:
            sentences = _split_sentences(payload.text)
            if not sentences and payload.text:
                sentences = [payload.text.strip()]

            per_item_sentences[payload.memory_id] = list(enumerate(sentences))
            weight = payload.importance_weight()

            for _, sentence in per_item_sentences[payload.memory_id]:
                tokens = _tokenise(sentence)
                if not tokens:
                    continue
                score = 0.0
                for token in tokens:
                    if token in self._stop_words:
                        continue
                    token_weights[token] = token_weights.get(token, 0.0) + weight
                    score += token_weights[token]
                if score:
                    combined_sentences.append(
                        (payload.memory_id, len(combined_sentences), sentence, score)
                    )

            for tag in payload.tags:
                tokens = _tokenise(str(tag))
                for token in tokens:
                    if token in self._stop_words:
                        continue
                    tag_weights[token] = tag_weights.get(token, 0.0) + weight * 1.2

        ranked_sentences = sorted(
            combined_sentences,
            key=lambda item: (item[3], -order_lookup.get(item[0], 0), -item[1]),
            reverse=True,
        )

        batch_selection = ranked_sentences[: options.max_batch_summary_sentences]
        batch_selection.sort(key=lambda item: (order_lookup.get(item[0], 0), item[1]))
        aggregated_summary = " ".join(sentence for _, _, sentence, _ in batch_selection).strip()

        per_item: Dict[str, str] = {}
        highlights: Dict[str, List[str]] = {}
        for payload in payloads:
            sentences = per_item_sentences.get(payload.memory_id, [])
            if not sentences:
                per_item[payload.memory_id] = ""
                highlights[payload.memory_id] = []
                continue

            scored = []
            for index, sentence in sentences:
                tokens = _tokenise(sentence)
                if not tokens:
                    continue
                score = 0.0
                for token in tokens:
                    if token in self._stop_words:
                        continue
                    # Prefer tokens boosted by tags and global frequency
                    score += token_weights.get(token, 0.0) + tag_weights.get(token, 0.0)
                if score:
                    scored.append((score, index, sentence))

            scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
            top = scored[: options.max_item_summary_sentences]
            top.sort(key=lambda item: item[1])
            selected_sentences = [sentence for _, _, sentence in top]

            if not selected_sentences and sentences:
                selected_sentences = [sentences[0][1]]

            per_item[payload.memory_id] = " ".join(selected_sentences).strip()
            highlights[payload.memory_id] = selected_sentences

        combined_weights: Dict[str, float] = {}
        for token, weight in token_weights.items():
            combined_weights[token] = weight
        for token, weight in tag_weights.items():
            combined_weights[token] = combined_weights.get(token, 0.0) + weight

        sorted_keywords = sorted(
            combined_weights.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        keywords = [token for token, _ in sorted_keywords[: options.max_keywords]]

        importance_values = [payload.importance for payload in payloads if payload.importance is not None]
        metadata: Dict[str, Any] = {
            "sources": [payload.memory_id for payload in payloads],
        }
        if importance_values:
            metadata["importance"] = {
                "min": round(min(importance_values), 3),
                "max": round(max(importance_values), 3),
                "mean": round(statistics.fmean(importance_values), 3),
            }

        return BatchSummary(
            aggregated_summary=aggregated_summary,
            per_item=per_item,
            keywords=keywords,
            highlights=highlights,
            batch_metadata=metadata,
        )


class MemorySummarizer:
    """Coordinator that routes summarisation to registered backends."""

    _backend_registry: Dict[str, Callable[..., SummarizationBackend]] = {}

    def __init__(
        self,
        backend: SummarizationBackend,
        *,
        options: Optional[SummarizationOptions] = None,
    ) -> None:
        self._backend = backend
        self._options = options or SummarizationOptions()

    @classmethod
    def register_backend(
        cls,
        name: str,
        factory: Callable[..., SummarizationBackend],
    ) -> None:
        cls._backend_registry[name] = factory

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, Any]]) -> "MemorySummarizer":
        config = config or {}
        if not config.get("enabled", True):
            backend = KeywordFrequencyBackend()
            return cls(backend, options=SummarizationOptions())

        backend_name = config.get("backend", "keyword_frequency")
        try:
            backend_factory = cls._backend_registry[backend_name]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown summarization backend '{backend_name}'") from exc

        backend_options = config.get("backend_options", {})
        backend = backend_factory(**backend_options)
        options = SummarizationOptions.from_config(config.get("options"))
        return cls(backend, options=options)

    def summarize_payloads(
        self, payloads: Sequence[SummarizationPayload]
    ) -> BatchSummary:
        return self._backend.summarize_batch(payloads, options=self._options)

    def summarize_memories(self, memories: Sequence[Any]) -> BatchSummary:
        payloads = [self._build_payload(index, memory) for index, memory in enumerate(memories)]
        return self.summarize_payloads(payloads)

    def _build_payload(self, index: int, memory: Any) -> SummarizationPayload:
        memory_id = self._resolve_memory_id(index, memory)
        text = self._extract_text(memory)
        metadata = self._extract_metadata(memory)
        tags = self._extract_tags(memory, metadata)
        importance = self._extract_importance(memory, metadata)
        created_at = self._extract_created_at(memory, metadata)

        return SummarizationPayload(
            memory_id=memory_id,
            text=text,
            importance=importance,
            tags=tuple(tags),
            metadata=metadata,
            created_at=created_at,
        )

    @staticmethod
    def _resolve_memory_id(index: int, memory: Any) -> str:
        for attr in ("id", "memory_id"):
            value = getattr(memory, attr, None)
            if value:
                return str(value)
        return f"memory-{index}"

    @staticmethod
    def _extract_text(memory: Any) -> str:
        if hasattr(memory, "get_text"):
            try:
                text = memory.get_text()
                if text:
                    return text
            except Exception:  # pragma: no cover - defensive
                pass

        content = getattr(memory, "content", None)
        if hasattr(content, "primary_text"):
            text = content.primary_text
            if text:
                return text

        flattened = _flatten_content(content)
        if flattened:
            return flattened

        summary = getattr(memory, "summary", None)
        if summary:
            return str(summary)

        metadata = getattr(memory, "metadata", None)
        return _flatten_content(metadata)

    @staticmethod
    def _extract_metadata(memory: Any) -> MutableMapping[str, Any]:
        metadata = getattr(memory, "metadata", None)
        if metadata is None:
            return {}
        if isinstance(metadata, MutableMapping):
            return dict(metadata)
        if hasattr(metadata, "dict"):
            try:
                return dict(metadata.dict())
            except TypeError:  # pragma: no cover - fallback for unexpected signatures
                return dict(metadata)
        if hasattr(metadata, "model_dump"):
            return dict(metadata.model_dump())  # type: ignore[attr-defined]
        return dict(vars(metadata)) if hasattr(metadata, "__dict__") else {}

    @staticmethod
    def _extract_tags(memory: Any, metadata: Mapping[str, Any]) -> List[str]:
        tags: Any = getattr(memory, "tags", None)
        if not tags and metadata:
            tags = metadata.get("tags")

        if isinstance(tags, Mapping):
            return [str(key) for key in tags.keys()]
        if isinstance(tags, (list, tuple, set, frozenset)):
            return [str(tag) for tag in tags]
        if tags:
            return [str(tags)]
        return []

    @staticmethod
    def _extract_importance(memory: Any, metadata: Mapping[str, Any]) -> float:
        for attr in ("importance", "priority"):
            if hasattr(memory, attr):
                value = getattr(memory, attr)
                if isinstance(value, (int, float)):
                    return float(value)
        if metadata:
            importance = metadata.get("importance")
            if isinstance(importance, (int, float)):
                return float(importance)
        return 0.5

    @staticmethod
    def _extract_created_at(memory: Any, metadata: Mapping[str, Any]) -> Optional[datetime]:
        created_at = getattr(memory, "created_at", None)
        if isinstance(created_at, datetime):
            return created_at
        if metadata:
            meta_created = metadata.get("created_at")
            if isinstance(meta_created, datetime):
                return meta_created
        return None


MemorySummarizer.register_backend("keyword_frequency", lambda **kwargs: KeywordFrequencyBackend(**kwargs))


__all__ = [
    "BatchSummary",
    "KeywordFrequencyBackend",
    "MemorySummarizer",
    "SummarizationBackend",
    "SummarizationOptions",
    "SummarizationPayload",
]

