"""Consolidation workflows for manual tier promotion."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Optional

from neuroca.memory.exceptions import InvalidTierError, MemoryManagerOperationError, MemoryNotFoundError
from neuroca.memory.manager.consolidation_pipeline import ConsolidationSkip, ConsolidationTransaction
from neuroca.memory.models.memory_item import MemoryItem

from .base import LOGGER


class MemoryManagerConsolidationMixin:
    """Provide explicit consolidation control between memory tiers."""

    async def consolidate_memory(
        self,
        memory_id: str,
        source_tier: str,
        target_tier: str,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Explicitly consolidate a memory from one tier to another."""

        self._ensure_initialized()

        if source_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid source tier: {source_tier}")

        if target_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid target tier: {target_tier}")

        source_tier_instance = self._get_tier_by_name(source_tier)
        target_tier_instance = self._get_tier_by_name(target_tier)

        pipeline_key = f"{source_tier}:{memory_id}->{target_tier}"

        metrics = getattr(self, "_metrics", None)
        event_publisher = getattr(self, "_event_publisher", None)

        try:
            while True:
                decision = await self._consolidation_guard.reserve(pipeline_key)
                if not decision.proceed:
                    if decision.result is None:
                        continue
                    if event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="cached",
                            duration_seconds=None,
                            result_id=str(decision.result),
                        )
                    return decision.result

                reservation = decision.reservation
                if reservation is None:
                    if decision.result is not None and event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="cached",
                            duration_seconds=None,
                            result_id=str(decision.result),
                        )
                    return decision.result

                async with reservation:
                    started = perf_counter()
                    memory_data = await source_tier_instance.retrieve(memory_id)
                    if not memory_data:
                        raise MemoryNotFoundError(
                            f"Memory {memory_id} not found in {source_tier} tier"
                        )

                    if additional_metadata:
                        if isinstance(memory_data, MemoryItem):
                            metadata = memory_data.metadata
                            tags = metadata.tags
                            for key, value in additional_metadata.items():
                                if key == "tags" and isinstance(value, dict):
                                    tags.update(value)
                                else:
                                    tags[f"_meta_{key}"] = value
                            metadata.tags = tags
                        elif isinstance(memory_data, dict):
                            metadata = memory_data.get("metadata", {})
                            for key, value in additional_metadata.items():
                                if key == "tags":
                                    tags = metadata.get("tags", {})
                                    tags.update(value)
                                    metadata["tags"] = tags
                                else:
                                    metadata[key] = value
                            memory_data["metadata"] = metadata

                    async def runner(transaction: ConsolidationTransaction) -> Any:
                        stored_id = await transaction.stage(
                            lambda: target_tier_instance.store(memory_data),
                            rollback=lambda new_id: self._delete_if_supported(
                                target_tier_instance,
                                new_id,
                                context=f"consolidation {pipeline_key}",
                            ),
                            description="store_target",
                        )

                        if not stored_id:
                            raise ConsolidationSkip(
                                f"Target tier {target_tier} did not return an identifier"
                            )

                        if source_tier != target_tier:
                            await transaction.stage(
                                lambda: source_tier_instance.delete(memory_id),
                                description="delete_source",
                            )

                        return stored_id

                    try:
                        new_id = await self._consolidation_pipeline.run(
                            pipeline_key, runner
                        )
                        duration = perf_counter() - started
                    except ConsolidationSkip as exc:
                        duration = perf_counter() - started
                        if metrics is not None:
                            metrics.record_consolidation(
                                source=source_tier,
                                target=target_tier,
                                duration_seconds=duration,
                                succeeded=False,
                            )
                        if event_publisher is not None:
                            await event_publisher.consolidation_completed(
                                memory_id=memory_id,
                                source_tier=source_tier,
                                target_tier=target_tier,
                                status="skipped",
                                duration_seconds=duration,
                                result_id=None,
                                error=str(exc),
                            )
                        raise MemoryManagerOperationError(
                            f"Failed to consolidate memory {memory_id}: {exc}"
                        ) from exc
                    except Exception as exc:
                        duration = perf_counter() - started
                        if metrics is not None:
                            metrics.record_consolidation(
                                source=source_tier,
                                target=target_tier,
                                duration_seconds=duration,
                                succeeded=False,
                            )
                        if event_publisher is not None:
                            await event_publisher.consolidation_completed(
                                memory_id=memory_id,
                                source_tier=source_tier,
                                target_tier=target_tier,
                                status="error",
                                duration_seconds=duration,
                                result_id=None,
                                error=str(exc),
                            )
                        LOGGER.exception("Failed to consolidate memory %s", memory_id)
                        raise MemoryManagerOperationError(
                            f"Failed to consolidate memory: {exc}"
                        ) from exc

                    reservation.commit(new_id)
                    if metrics is not None:
                        metrics.record_consolidation(
                            source=source_tier,
                            target=target_tier,
                            duration_seconds=duration,
                            succeeded=True,
                        )
                    if event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="success",
                            duration_seconds=duration,
                            result_id=str(new_id) if new_id is not None else None,
                        )
                    await self._audit_trail.record_consolidation(
                        memory_data,
                        source_tier=source_tier,
                        target_tier=target_tier,
                        new_memory_id=str(new_id) if new_id is not None else None,
                    )
                    return new_id
        except Exception as exc:
            if isinstance(exc, (MemoryNotFoundError, InvalidTierError)):
                raise

            LOGGER.exception("Failed to consolidate memory %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to consolidate memory: {exc}"
            ) from exc


__all__ = ["MemoryManagerConsolidationMixin"]
