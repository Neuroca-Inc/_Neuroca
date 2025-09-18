"""Vector index integrity and maintenance helpers."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from pydantic import BaseModel, Field, ValidationError

from neuroca.memory.backends.vector.components.index import VectorIndex
from neuroca.memory.backends.vector.components.models import VectorEntry
from neuroca.memory.backends.vector.components.storage import VectorStorage
from neuroca.memory.models.memory_item import MemoryItem


class VectorIndexIntegrityIssue(BaseModel):
    """Represents a single integrity issue discovered for a memory entry."""

    memory_id: str
    issue_type: str
    details: Dict[str, Any] = Field(default_factory=dict)


class VectorIndexIntegrityReport(BaseModel):
    """Summary of integrity checks for the vector index and metadata store."""

    index_entry_count: int
    metadata_entry_count: int
    checked_entry_count: int
    index_only_ids: List[str] = Field(default_factory=list)
    metadata_only_ids: List[str] = Field(default_factory=list)
    missing_payload_ids: List[str] = Field(default_factory=list)
    missing_embedding_ids: List[str] = Field(default_factory=list)
    dimension_mismatch_ids: List[str] = Field(default_factory=list)
    drifted_ids: List[str] = Field(default_factory=list)
    drift_scores: Dict[str, float] = Field(default_factory=dict)
    max_drift: float = 0.0
    avg_drift: float = 0.0
    issues: List[VectorIndexIntegrityIssue] = Field(default_factory=list)
    reindexed: bool = False
    reindexed_entry_count: int = 0

    def extend(self, issues: Iterable[VectorIndexIntegrityIssue]) -> None:
        """Append additional issues to the report."""

        self.issues.extend(list(issues))


class VectorIndexMaintenance:
    """Provides integrity checks and reindex flows for the vector backend."""

    def __init__(self, index: VectorIndex, storage: VectorStorage, dimension: int) -> None:
        self._index = index
        self._storage = storage
        self._dimension = dimension

    def check_integrity(
        self,
        *,
        drift_threshold: float = 0.1,
        sample_size: Optional[int] = None,
    ) -> VectorIndexIntegrityReport:
        """Evaluate the index for drift, missing payloads, and mismatches."""

        metadata_map = self._storage.get_all_memory_metadata()
        index_ids: Set[str] = set(self._index.get_entry_ids())
        metadata_ids: Set[str] = set(metadata_map.keys())

        index_only_ids = sorted(index_ids - metadata_ids)
        metadata_only_ids = sorted(metadata_ids - index_ids)
        candidate_ids = sorted(index_ids & metadata_ids)

        if sample_size is not None and sample_size >= 0:
            candidate_ids = candidate_ids[:sample_size]

        drift_scores: Dict[str, float] = {}
        drifted_ids: List[str] = []
        missing_payload_ids: List[str] = []
        missing_embedding_ids: List[str] = []
        dimension_mismatch_ids: List[str] = []
        issues: List[VectorIndexIntegrityIssue] = []

        for memory_id in candidate_ids:
            entry = self._index.get(memory_id)
            metadata = metadata_map.get(memory_id, {})

            payload = metadata.get("memory")
            if not payload:
                missing_payload_ids.append(memory_id)
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="missing_payload",
                        details={"source": "metadata"},
                    )
                )
                continue

            try:
                memory_item = MemoryItem.model_validate(payload)
            except ValidationError as validation_error:
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="invalid_payload",
                        details={"error": str(validation_error)},
                    )
                )
                continue

            embedding = memory_item.embedding
            if not embedding:
                missing_embedding_ids.append(memory_id)
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="missing_embedding",
                        details={},
                    )
                )
                continue

            if len(embedding) != self._dimension:
                dimension_mismatch_ids.append(memory_id)
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="dimension_mismatch",
                        details={
                            "expected": self._dimension,
                            "observed": len(embedding),
                        },
                    )
                )
                continue

            if not entry:
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="missing_index_entry",
                        details={},
                    )
                )
                continue

            drift = self._cosine_distance(embedding, entry.vector)
            drift_scores[memory_id] = drift

            if drift > drift_threshold:
                drifted_ids.append(memory_id)
                issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="embedding_drift",
                        details={
                            "drift": drift,
                            "threshold": drift_threshold,
                        },
                    )
                )

        max_drift = max(drift_scores.values(), default=0.0)
        avg_drift = (
            sum(drift_scores.values()) / len(drift_scores)
            if drift_scores
            else 0.0
        )

        return VectorIndexIntegrityReport(
            index_entry_count=len(index_ids),
            metadata_entry_count=len(metadata_ids),
            checked_entry_count=len(candidate_ids),
            index_only_ids=index_only_ids,
            metadata_only_ids=metadata_only_ids,
            missing_payload_ids=missing_payload_ids,
            missing_embedding_ids=missing_embedding_ids,
            dimension_mismatch_ids=dimension_mismatch_ids,
            drifted_ids=drifted_ids,
            drift_scores=drift_scores,
            max_drift=max_drift,
            avg_drift=avg_drift,
            issues=issues,
        )

    async def rebuild_index(
        self,
        *,
        target_ids: Optional[Sequence[str]] = None,
        full_refresh: bool = False,
        drift_threshold: float = 0.1,
    ) -> VectorIndexIntegrityReport:
        """Rebuild index entries using stored metadata payloads."""

        metadata_map = self._storage.get_all_memory_metadata()
        available_ids = set(metadata_map.keys())

        if target_ids is None:
            selected_ids = sorted(available_ids)
        else:
            selected_ids = sorted(set(target_ids))

        rebuild_issues: List[VectorIndexIntegrityIssue] = []
        rebuilt_entries: List[VectorEntry] = []

        for memory_id in selected_ids:
            metadata = metadata_map.get(memory_id)
            if metadata is None:
                rebuild_issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="metadata_missing",
                        details={},
                    )
                )
                continue

            payload = metadata.get("memory")
            if not payload:
                rebuild_issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="missing_payload",
                        details={"source": "metadata"},
                    )
                )
                continue

            try:
                memory_item = MemoryItem.model_validate(payload)
            except ValidationError as validation_error:
                rebuild_issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="invalid_payload",
                        details={"error": str(validation_error)},
                    )
                )
                continue

            embedding = memory_item.embedding
            if not embedding:
                rebuild_issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="missing_embedding",
                        details={},
                    )
                )
                continue

            if len(embedding) != self._dimension:
                rebuild_issues.append(
                    VectorIndexIntegrityIssue(
                        memory_id=memory_id,
                        issue_type="dimension_mismatch",
                        details={
                            "expected": self._dimension,
                            "observed": len(embedding),
                        },
                    )
                )
                continue

            vector_metadata = dict(metadata)
            vector_metadata.setdefault("memory", memory_item.model_dump(mode="json"))

            rebuilt_entries.append(
                VectorEntry(
                    id=memory_item.id,
                    vector=embedding,
                    metadata=vector_metadata,
                )
            )

        if full_refresh:
            self._index.clear()

        if rebuilt_entries:
            self._index.batch_add(rebuilt_entries)

        await self._storage.save()

        report = self.check_integrity(
            drift_threshold=drift_threshold,
        )
        report.reindexed = True
        report.reindexed_entry_count = len(rebuilt_entries)
        report.extend(rebuild_issues)

        return report

    @staticmethod
    def _cosine_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        similarity = dot_product / (norm_a * norm_b)
        similarity = max(min(similarity, 1.0), -1.0)
        return 1.0 - similarity
