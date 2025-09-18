"""Embedding model swap planning utilities for the vector backend."""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from pydantic import ValidationError

from neuroca.memory.backends.vector.components.crud import VectorCRUD
from neuroca.memory.backends.vector.components.storage import VectorStorage
from neuroca.memory.models.memory_item import MemoryItem

EmbedderOutput = Sequence[Sequence[float]]
EmbedderCallable = Callable[[List[MemoryItem]], Union[EmbedderOutput, Awaitable[EmbedderOutput]]]


@dataclass
class EmbeddingModelSwapPlan:
    """Represents the staged output of an embedding model swap dry-run."""

    current_model: Optional[str]
    target_model: str
    current_dimension: int
    total_candidates: int
    sample_count: int
    target_dimension: Optional[int] = None
    staged_count: int = 0
    evaluated_count: int = 0
    drift_scores: Dict[str, float] = field(default_factory=dict)
    drift_over_threshold_ids: List[str] = field(default_factory=list)
    missing_payload_ids: List[str] = field(default_factory=list)
    validation_errors: Dict[str, str] = field(default_factory=dict)
    missing_embeddings: List[str] = field(default_factory=list)
    dimension_mismatch_ids: List[str] = field(default_factory=list)
    embedder_failures: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    ready: bool = False
    commit_allowed: bool = False
    committed: bool = False
    max_drift: float = 0.0
    avg_drift: float = 0.0
    full_coverage: bool = False
    _staged_memories: Dict[str, MemoryItem] = field(default_factory=dict, repr=False)

    def add_staged_memory(self, memory_item: MemoryItem) -> None:
        """Record a staged memory update."""

        self._staged_memories[memory_item.id] = memory_item
        self.staged_count = len(self._staged_memories)

    def iter_staged_memories(self) -> Iterable[MemoryItem]:
        """Yield the staged memory payloads in commit order."""

        return self._staged_memories.values()

    def staged_ids(self) -> List[str]:
        """Return the IDs covered by the staged swap."""

        return list(self._staged_memories.keys())


class EmbeddingModelSwapCoordinator:
    """Plans and executes safe embedding model swaps for the vector backend."""

    def __init__(self, crud: VectorCRUD, storage: VectorStorage, dimension: int) -> None:
        self._crud = crud
        self._storage = storage
        self._dimension = dimension

    async def plan_swap(
        self,
        target_model: str,
        embedder: EmbedderCallable,
        *,
        batch_size: int = 64,
        sample_size: Optional[int] = None,
        expected_dimension: Optional[int] = None,
        drift_threshold: float = 0.2,
    ) -> EmbeddingModelSwapPlan:
        """Stage a model swap by re-embedding stored payloads and validating compatibility."""

        metadata_map = self._storage.get_all_memory_metadata()
        total_candidates = len(metadata_map)
        sampled_ids = sorted(metadata_map.keys())

        if sample_size is not None and sample_size >= 0:
            sampled_ids = sampled_ids[:sample_size]

        plan = EmbeddingModelSwapPlan(
            current_model=None,
            target_model=target_model,
            current_dimension=self._dimension,
            total_candidates=total_candidates,
            sample_count=len(sampled_ids),
            full_coverage=len(sampled_ids) == total_candidates,
        )

        if total_candidates == 0:
            plan.ready = True
            plan.commit_allowed = True
            plan.full_coverage = True
            return plan

        staged_candidates: List[Tuple[str, MemoryItem]] = []
        detected_models: List[str] = []

        for memory_id in sampled_ids:
            metadata = metadata_map.get(memory_id, {})
            payload = metadata.get("memory")
            if not payload:
                plan.missing_payload_ids.append(memory_id)
                continue

            try:
                memory_item = MemoryItem.model_validate(payload)
            except ValidationError as validation_error:
                plan.validation_errors[memory_id] = str(validation_error)
                continue

            staged_candidates.append((memory_id, memory_item))
            if memory_item.metadata.embedding_model:
                detected_models.append(memory_item.metadata.embedding_model)

        plan.evaluated_count = len(staged_candidates)

        if detected_models:
            unique_models = sorted(set(detected_models))
            if len(unique_models) == 1:
                plan.current_model = unique_models[0]
            else:
                plan.warnings.append(
                    "Detected multiple existing embedding models: "
                    f"{', '.join(unique_models)}"
                )

        if not staged_candidates:
            plan.blocking_reasons.append(
                "No valid memory payloads available for re-embedding"
            )
            self._finalize_plan(plan, drift_threshold)
            return plan

        for batch in self._chunked(staged_candidates, batch_size):
            memory_items = [item for _, item in batch]
            try:
                embeddings = await self._call_embedder(embedder, memory_items)
            except Exception as error:  # pragma: no cover - defensive safeguard
                message = str(error)
                for memory_id, _ in batch:
                    plan.embedder_failures[memory_id] = message
                continue

            if len(embeddings) != len(batch):
                message = (
                    "Embedder returned "
                    f"{len(embeddings)} embeddings for {len(batch)} inputs"
                )
                for memory_id, _ in batch:
                    plan.embedder_failures[memory_id] = message
                continue

            for (memory_id, memory_item), embedding in zip(batch, embeddings):
                coerced = self._coerce_embedding(embedding)
                if coerced is None:
                    plan.embedder_failures[memory_id] = (
                        "Embedding output was not a sequence of numbers"
                    )
                    continue

                target_dimension = len(coerced)
                if plan.target_dimension is None:
                    plan.target_dimension = target_dimension
                elif target_dimension != plan.target_dimension:
                    plan.dimension_mismatch_ids.append(memory_id)
                    plan.embedder_failures[memory_id] = (
                        "Mismatched embedding dimension "
                        f"{target_dimension}; expected {plan.target_dimension}"
                    )
                    continue

                if (
                    expected_dimension is not None
                    and target_dimension != expected_dimension
                ):
                    plan.dimension_mismatch_ids.append(memory_id)
                    plan.embedder_failures[memory_id] = (
                        "Embedding dimension "
                        f"{target_dimension} did not match expected {expected_dimension}"
                    )
                    continue

                staged_memory = memory_item.model_copy(deep=True)
                staged_memory.embedding = list(coerced)
                staged_memory.metadata.embedding_model = target_model
                staged_memory.metadata.embedding_dimensions = target_dimension

                if memory_item.embedding:
                    drift = self._cosine_distance(memory_item.embedding, coerced)
                    plan.drift_scores[memory_id] = drift
                    if drift_threshold is not None and drift > drift_threshold:
                        plan.drift_over_threshold_ids.append(memory_id)
                else:
                    plan.missing_embeddings.append(memory_id)

                plan.add_staged_memory(staged_memory)

        if plan.drift_scores:
            plan.max_drift = max(plan.drift_scores.values())
            plan.avg_drift = sum(plan.drift_scores.values()) / len(plan.drift_scores)

        self._finalize_plan(plan, drift_threshold)
        return plan

    async def execute_swap(
        self,
        plan: EmbeddingModelSwapPlan,
        *,
        batch_size: int = 64,
        dry_run: bool = False,
    ) -> EmbeddingModelSwapPlan:
        """Apply a previously staged swap once compatibility checks pass."""

        if not plan.commit_allowed:
            raise ValueError(
                "Swap plan is not eligible for commit; resolve blocking issues first"
            )

        if dry_run or plan.committed:
            return plan

        staged_memories = list(plan.iter_staged_memories())
        for batch in self._chunked(staged_memories, batch_size):
            for memory_item in batch:
                await self._crud.update(memory_item)

        plan.committed = True
        return plan

    async def _call_embedder(
        self, embedder: EmbedderCallable, batch: List[MemoryItem]
    ) -> Sequence[Sequence[float]]:
        """Invoke the embedder, supporting both sync and async callables."""

        result = embedder(batch)
        if inspect.isawaitable(result):
            result = await result
        return result

    @staticmethod
    def _chunked(
        items: Sequence[Tuple[str, MemoryItem]], batch_size: int
    ) -> Iterable[Sequence[Tuple[str, MemoryItem]]]:
        for index in range(0, len(items), max(1, batch_size)):
            yield items[index : index + max(1, batch_size)]

    @staticmethod
    def _coerce_embedding(candidate: Sequence[float]) -> Optional[List[float]]:
        if not isinstance(candidate, Sequence):
            return None

        coerced: List[float] = []
        for value in candidate:
            if not isinstance(value, (int, float)):
                return None
            coerced.append(float(value))
        return coerced

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

    @staticmethod
    def _finalize_plan(
        plan: EmbeddingModelSwapPlan, drift_threshold: float
    ) -> None:
        if plan.target_dimension is None:
            plan.blocking_reasons.append(
                "Could not determine target embedding dimension"
            )

        if plan.dimension_mismatch_ids:
            plan.blocking_reasons.append(
                "Embedding dimension mismatch detected for staged memories"
            )

        if plan.validation_errors:
            plan.blocking_reasons.append(
                "Failed to validate stored payloads for some memories"
            )

        if plan.embedder_failures:
            plan.blocking_reasons.append(
                "Embedding generation failed for staged memories"
            )

        if plan.missing_payload_ids:
            plan.blocking_reasons.append(
                "Missing stored payloads prevented staging for some memories"
            )

        if plan.evaluated_count and plan.staged_count != plan.evaluated_count:
            plan.blocking_reasons.append(
                "One or more embeddings failed validation; inspect embedder failures"
            )

        if plan.drift_over_threshold_ids:
            plan.blocking_reasons.append(
                f"{len(plan.drift_over_threshold_ids)} embeddings exceeded drift threshold {drift_threshold:.3f}"
            )

        if plan.missing_embeddings:
            plan.warnings.append(
                f"{len(plan.missing_embeddings)} memories lacked prior embeddings; drift metrics are partial"
            )

        if not plan.full_coverage:
            plan.warnings.append(
                "Swap plan sampled a subset of memories; rerun without sample_size before committing"
            )

        plan.ready = not plan.blocking_reasons
        plan.commit_allowed = plan.ready and plan.full_coverage and plan.staged_count == plan.sample_count
