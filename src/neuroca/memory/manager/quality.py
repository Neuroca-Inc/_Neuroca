"""Memory quality monitoring primitives."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _QualitySample:
    memory_id: str
    text: str
    tags: Mapping[str, Any]
    last_accessed: datetime
    embedding: Optional[Sequence[float]]


def _normalise_datetime(value: Any, *, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return default
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return default


def _extract_text(payload: Any) -> str:
    if isinstance(payload, MemoryItem):
        return payload.content.primary_text
    if isinstance(payload, Mapping):
        content = payload.get("content")
        if isinstance(content, MemoryContent):
            return content.primary_text
        if isinstance(content, Mapping):
            for key in ("text", "summary", "raw_content"):
                value = content.get(key)
                if isinstance(value, str):
                    return value
                if value is not None and key == "raw_content":
                    return str(value)
    return ""


def _extract_tags(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, MemoryItem):
        tags = payload.metadata.tags
    elif isinstance(payload, Mapping):
        metadata = payload.get("metadata")
        if isinstance(metadata, MemoryMetadata):
            tags = metadata.tags
        elif isinstance(metadata, Mapping):
            tags = metadata.get("tags", {})
        else:
            tags = {}
    else:
        tags = {}
    return tags if isinstance(tags, Mapping) else {}


def _extract_last_accessed(payload: Any, *, fallback: datetime) -> datetime:
    if isinstance(payload, MemoryItem):
        return _normalise_datetime(payload.metadata.last_accessed, default=fallback)
    if isinstance(payload, Mapping):
        metadata = payload.get("metadata")
        if isinstance(metadata, MemoryMetadata):
            return _normalise_datetime(metadata.last_accessed, default=fallback)
        if isinstance(metadata, Mapping):
            return _normalise_datetime(metadata.get("last_accessed"), default=fallback)
    return fallback


def _extract_embedding(payload: Any) -> Optional[Sequence[float]]:
    if isinstance(payload, MemoryItem):
        candidate = payload.embedding
    elif isinstance(payload, Mapping):
        candidate = payload.get("embedding")
        if candidate is None and isinstance(payload.get("metadata"), Mapping):
            candidate = payload["metadata"].get("embedding")  # type: ignore[index]
    else:
        candidate = None
    return candidate if isinstance(candidate, Sequence) else None


class MemoryQualityAnalyzer:
    DEFAULT_STALE_AFTER = timedelta(days=30)
    DEFAULT_REDUNDANCY_THRESHOLD = 0.9
    DEFAULT_CLUSTER_SIZE = 3
    DEFAULT_DRIFT_TOLERANCE = 0.35
    DEFAULT_DRIFT_ALERT_THRESHOLD = 0.45
    DEFAULT_MIN_EMBEDDINGS = 3

    def __init__(
        self,
        *,
        stale_after_seconds: Optional[float] = None,
        redundancy_similarity_threshold: Optional[float] = None,
        min_cluster_size: Optional[int] = None,
        drift_tolerance: Optional[float] = None,
        drift_alert_threshold: Optional[float] = None,
        min_embeddings_for_drift: Optional[int] = None,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self._stale_after = self._coerce_positive_timedelta(stale_after_seconds) or self.DEFAULT_STALE_AFTER
        self._redundancy_threshold = self._coerce_ratio(redundancy_similarity_threshold) or self.DEFAULT_REDUNDANCY_THRESHOLD
        self._min_cluster_size = max(1, min_cluster_size or self.DEFAULT_CLUSTER_SIZE)
        self._drift_tolerance = self._coerce_positive_float(drift_tolerance) or self.DEFAULT_DRIFT_TOLERANCE
        self._drift_alert_threshold = self._coerce_positive_float(drift_alert_threshold) or self.DEFAULT_DRIFT_ALERT_THRESHOLD
        self._min_embeddings_for_drift = max(2, min_embeddings_for_drift or self.DEFAULT_MIN_EMBEDDINGS)
        self._log = log or logger

    @staticmethod
    def _coerce_positive_float(value: Optional[float]) -> Optional[float]:
        try:
            candidate = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        return candidate if candidate and candidate > 0 else None

    def _coerce_positive_timedelta(self, seconds: Optional[float]) -> Optional[timedelta]:
        positive = self._coerce_positive_float(seconds)
        return timedelta(seconds=positive) if positive else None

    @staticmethod
    def _coerce_ratio(value: Optional[float]) -> Optional[float]:
        try:
            candidate = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        return candidate if candidate and 0.0 < candidate <= 1.0 else None

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, Any]], *, log: Optional[logging.Logger] = None) -> "MemoryQualityAnalyzer":
        if not isinstance(config, Mapping):
            config = {}
        return cls(
            stale_after_seconds=config.get("stale_after_seconds"),
            redundancy_similarity_threshold=config.get("redundancy_similarity_threshold"),
            min_cluster_size=config.get("min_cluster_size"),
            drift_tolerance=config.get("drift_tolerance"),
            drift_alert_threshold=config.get("drift_alert_threshold"),
            min_embeddings_for_drift=config.get("min_embeddings_for_drift"),
            log=log,
        )

    def evaluate(self, memories: Sequence[Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        samples = self._build_samples(memories, default_ts=now)
        if not samples:
            return self._empty_report(now)

        total = len(samples)
        stale_cutoff = now - self._stale_after
        stale_ids = [sample.memory_id for sample in samples if sample.last_accessed <= stale_cutoff]
        redundancy_pairs = self._calculate_redundancy(samples)
        redundant_ids = {mid for pair in redundancy_pairs for mid in pair.get("memory_ids", [])}
        stale_clusters = self._detect_stale_clusters(samples, stale_cutoff)
        drift_alerts, drift_score = self._detect_embedding_drift(samples)

        redundancy_ratio = len(redundant_ids) / total
        stale_ratio = len(stale_ids) / total
        score = self._calculate_score(
            redundancy_ratio=redundancy_ratio,
            stale_ratio=stale_ratio,
            drift_score=drift_score,
        )

        alerts: List[Dict[str, Any]] = []
        if redundancy_pairs:
            alerts.append(
                {
                    "type": "redundancy",
                    "severity": "warning" if redundancy_ratio < 0.5 else "critical",
                    "message": f"{len(redundant_ids)} memories share highly similar content",
                    "memory_ids": sorted(redundant_ids),
                    "metadata": {"pairs": redundancy_pairs},
                }
            )
        if stale_ids:
            alerts.append(
                {
                    "type": "stale_cluster" if stale_clusters else "stale",
                    "severity": "warning" if stale_ratio < 0.5 else "critical",
                    "message": f"{len(stale_ids)} memories have not been accessed recently",
                    "memory_ids": sorted(stale_ids),
                    "metadata": {"clusters": stale_clusters},
                }
            )
        if drift_alerts:
            alerts.append(
                {
                    "type": "embedding_drift",
                    "severity": "warning" if drift_score < 0.75 else "critical",
                    "message": "Embedding distribution shows significant drift",
                    "memory_ids": [alert["memory_id"] for alert in drift_alerts if alert.get("memory_id")],
                    "metadata": {"alerts": drift_alerts},
                }
            )

        flagged = set(stale_ids)
        for pair in redundancy_pairs:
            flagged.update(pair.get("memory_ids", ()))
        for alert in drift_alerts:
            memory_id = alert.get("memory_id")
            if memory_id:
                flagged.add(memory_id)

        return {
            "score": round(score, 4),
            "total_memories": total,
            "metrics": {
                "redundancy_ratio": redundancy_ratio,
                "stale_ratio": stale_ratio,
                "drift_score": drift_score,
            },
            "redundancy": {"ratio": redundancy_ratio, "pairs": redundancy_pairs},
            "stale": {"ratio": stale_ratio, "memory_ids": stale_ids, "clusters": stale_clusters},
            "drift": {"score": drift_score, "alerts": drift_alerts},
            "flagged_memory_ids": sorted(flagged),
            "alerts": alerts,
            "evaluated_at": now.isoformat(),
        }

    def _empty_report(self, now: datetime) -> Dict[str, Any]:
        iso = now.isoformat()
        return {
            "score": 1.0,
            "total_memories": 0,
            "metrics": {"redundancy_ratio": 0.0, "stale_ratio": 0.0, "drift_score": 0.0},
            "redundancy": {"ratio": 0.0, "pairs": []},
            "stale": {"ratio": 0.0, "memory_ids": [], "clusters": []},
            "drift": {"score": 0.0, "alerts": []},
            "flagged_memory_ids": [],
            "alerts": [],
            "evaluated_at": iso,
        }

    def _build_samples(self, memories: Sequence[Any], *, default_ts: datetime) -> List[_QualitySample]:
        samples: List[_QualitySample] = []
        for memory in memories:
            memory_id = self._resolve_memory_id(memory)
            if not memory_id:
                continue
            samples.append(
                _QualitySample(
                    memory_id=memory_id,
                    text=_extract_text(memory),
                    tags=_extract_tags(memory),
                    last_accessed=_extract_last_accessed(memory, fallback=default_ts),
                    embedding=_extract_embedding(memory),
                )
            )
        return samples

    @staticmethod
    def _resolve_memory_id(memory: Any) -> Optional[str]:
        if isinstance(memory, MemoryItem):
            return memory.id
        if isinstance(memory, Mapping):
            candidate = memory.get("id")
            if isinstance(candidate, str):
                return candidate
        return None

    def _calculate_redundancy(self, samples: Sequence[_QualitySample]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for idx, current in enumerate(samples):
            if not current.text:
                continue
            for sibling in samples[idx + 1 :]:
                if not sibling.text:
                    continue
                similarity = SequenceMatcher(None, current.text, sibling.text).ratio()
                if similarity >= self._redundancy_threshold:
                    results.append({"memory_ids": [current.memory_id, sibling.memory_id], "similarity": round(similarity, 3)})
        return results

    def _detect_stale_clusters(self, samples: Sequence[_QualitySample], cutoff: datetime) -> List[Dict[str, Any]]:
        clusters: MutableMapping[str, List[_QualitySample]] = {}
        for sample in samples:
            cluster_key = self._resolve_cluster_key(sample.tags)
            if cluster_key:
                clusters.setdefault(cluster_key, []).append(sample)
        stale_clusters: List[Dict[str, Any]] = []
        for cluster_key, members in clusters.items():
            if len(members) < self._min_cluster_size:
                continue
            if all(member.last_accessed <= cutoff for member in members):
                stale_clusters.append({
                    "cluster": cluster_key,
                    "memory_ids": [member.memory_id for member in members],
                    "size": len(members),
                })
        return stale_clusters

    @staticmethod
    def _resolve_cluster_key(tags: Mapping[str, Any]) -> Optional[str]:
        if not tags:
            return None
        for key in ("cluster", "cluster_id", "topic", "category"):
            value = tags.get(key)
            if isinstance(value, str) and value:
                return f"{key}:{value.lower()}"
        return None

    def _detect_embedding_drift(self, samples: Sequence[_QualitySample]) -> tuple[List[Dict[str, Any]], float]:
        embeddings = [sample.embedding for sample in samples if sample.embedding is not None]
        embeddings = [emb for emb in embeddings if emb is not None]
        if len(embeddings) < self._min_embeddings_for_drift:
            return [], 0.0
        dimension = len(embeddings[0])
        filtered = [emb for emb in embeddings if len(emb) == dimension]
        if len(filtered) < self._min_embeddings_for_drift:
            return [], 0.0
        centroid = [sum(vector[idx] for vector in filtered) / len(filtered) for idx in range(dimension)]
        alerts: List[Dict[str, Any]] = []
        deviations: List[tuple[_QualitySample, float]] = []
        for sample in samples:
            embedding = sample.embedding
            if embedding is None or len(embedding) != dimension:
                continue
            distance = self._cosine_distance(centroid, embedding)
            deviations.append((sample, distance))
            if distance >= self._drift_alert_threshold:
                alerts.append({"memory_id": sample.memory_id, "distance": round(distance, 4)})
        if not deviations:
            return [], 0.0
        average_distance = sum(distance for _, distance in deviations) / len(deviations)
        drift_score = min(1.0, average_distance / self._drift_tolerance)
        if not alerts and drift_score >= 0.6:
            outlier_sample, outlier_distance = max(deviations, key=lambda item: item[1])
            alerts.append({
                "memory_id": outlier_sample.memory_id,
                "distance": round(outlier_distance, 4),
                "mode": "aggregate_outlier",
            })
        return alerts, drift_score

    @staticmethod
    def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
        return 1.0 - similarity

    @staticmethod
    def _calculate_score(*, redundancy_ratio: float, stale_ratio: float, drift_score: float) -> float:
        weighted_penalty = (redundancy_ratio * 0.4) + (stale_ratio * 0.4) + (drift_score * 0.2)
        return max(0.0, 1.0 - weighted_penalty / 1.0)
