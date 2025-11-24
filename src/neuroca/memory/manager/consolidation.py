"""
Memory Manager Consolidation

This module handles the consolidation of memories between tiers
(STM -> MTM -> LTM) based on importance, access patterns, and age.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata, MemoryStatus
# Define priority enum for MTM memories since no longer imported from mtm.storage
from enum import Enum
from neuroca.memory.manager.summarization import MemorySummarizer
from neuroca.memory.manager.consolidation_pipeline import (
    ConsolidationSkip,
    ConsolidationTransaction,
    TransactionalConsolidationPipeline,
)
from neuroca.memory.manager.consolidation_guard import ConsolidationInFlightGuard

class MemoryPriority(str, Enum):
    """Priority levels for MTM memories."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

# Use the same MemoryStatus for MTM
MTMStatus = MemoryStatus

# Configure logger
logger = logging.getLogger(__name__)


_GLOBAL_PIPELINE = TransactionalConsolidationPipeline(
    log=logger.getChild("pipeline")
)
_GLOBAL_GUARD = ConsolidationInFlightGuard()


async def _safe_delete(storage: Any, memory_id: Any, *, context: str) -> None:
    """Attempt to delete ``memory_id`` from ``storage`` while swallowing errors."""

    if not memory_id:
        return

    delete_handler = getattr(storage, "delete", None)
    if delete_handler is None:
        return

    try:
        await delete_handler(memory_id)
    except Exception:  # noqa: BLE001
        logger.exception("Rollback delete failed for %s on %s", memory_id, context)


class StandardMemoryConsolidator:
    """
    Standard implementation of memory consolidation.
    
    This class handles the consolidation of memories between different tiers
    (STM -> MTM -> LTM) based on importance, access patterns, and age.
    """
    
    def __init__(
        self,
        pipeline: TransactionalConsolidationPipeline | None = None,
        guard: ConsolidationInFlightGuard | None = None,
    ):
        """Initialize the memory consolidator."""

        self.config = {}
        self._pipeline = pipeline or TransactionalConsolidationPipeline(
            log=logger.getChild("transactional")
        )
        self._guard = guard or _GLOBAL_GUARD
    
    async def consolidate_stm_to_mtm(self, stm_storage, mtm_storage):
        """
        Consolidate important memories from STM to MTM.
        
        Args:
            stm_storage: STM storage backend
            mtm_storage: MTM storage backend
        """
        await consolidate_stm_to_mtm(
            stm_storage,
            mtm_storage,
            self.config,
            pipeline=self._pipeline,
            guard=self._guard,
        )
    
    async def consolidate_mtm_to_ltm(self, mtm_storage, ltm_storage):
        """
        Consolidate important memories from MTM to LTM.
        
        Args:
            mtm_storage: MTM storage backend
            ltm_storage: LTM storage backend
        """
        await consolidate_mtm_to_ltm(
            mtm_storage,
            ltm_storage,
            self.config,
            pipeline=self._pipeline,
            guard=self._guard,
        )
    
    def configure(self, config):
        """
        Configure the consolidator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
    
    async def consolidate(self, stm_storage, mtm_storage, ltm_storage):
        """
        Perform full consolidation across all tiers.
        
        Args:
            stm_storage: STM storage backend
            mtm_storage: MTM storage backend
            ltm_storage: LTM storage backend
        """
        await self.consolidate_stm_to_mtm(stm_storage, mtm_storage)
        await self.consolidate_mtm_to_ltm(mtm_storage, ltm_storage)


async def consolidate_stm_to_mtm(
    stm_storage,
    mtm_storage,
    config: Dict[str, Any],
    *,
    pipeline: TransactionalConsolidationPipeline | None = None,
    guard: ConsolidationInFlightGuard | None = None,
) -> None:
    """Consolidate important memories from STM to MTM."""
    pipeline = pipeline or _GLOBAL_PIPELINE
    guard = guard or _GLOBAL_GUARD
    logger.debug("Starting STM to MTM consolidation")
    
    # Get items from STM
    try:
        # Get all STM items
        stm_items = await stm_storage.retrieve_all()
        
        # Skip if no items
        if not stm_items:
            return
        
        # Prioritize items for consolidation
        # (This is a simplified approach - a more sophisticated prioritization could be implemented)
        candidates = []
        for item in stm_items:
            if not item:
                continue
                
            # Get importance
            importance = 0.5
            if isinstance(item, dict) and "metadata" in item and isinstance(item["metadata"], dict):
                importance = item["metadata"].get("importance", 0.5)
            
            # Get access count
            access_count = 0
            if isinstance(item, dict) and "access_count" in item:
                access_count = item.get("access_count", 0)
            
            # Calculate priority score
            priority_score = importance * (0.5 + (0.5 * min(access_count, 10) / 10))
            
            # Add to candidates if priority is high enough
            if priority_score >= 0.6:  # Threshold for STM->MTM consolidation
                candidates.append((item, priority_score))
        
        # Sort by priority score (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Take top N candidates (limit batch size)
        batch_size = min(len(candidates), config.get("consolidation_batch_size", 5))
        top_candidates = candidates[:batch_size]
        
        # Consolidate top candidates
        for item, _ in top_candidates:
            item_id = item.get("id") if isinstance(item, dict) else None
            if not item_id:
                continue

            content = dict(item.get("content", {})) if isinstance(item, dict) else {}
            metadata = dict(item.get("metadata", {})) if isinstance(item, dict) else {}
            tags = metadata.get("tags", [])
            importance = metadata.get("importance", 0.5)

            priority = MemoryPriority.MEDIUM
            if importance >= 0.8:
                priority = MemoryPriority.HIGH
            elif importance < 0.5:
                priority = MemoryPriority.LOW

            async def runner(transaction: ConsolidationTransaction) -> Any:
                mtm_id = await transaction.stage(
                    lambda: mtm_storage.store(
                        content=content,
                        tags=tags,
                        priority=priority,
                        metadata=metadata,
                    ),
                    rollback=lambda new_id: _safe_delete(
                        mtm_storage,
                        new_id,
                        context=f"mtm rollback for {item_id}",
                    ),
                    description="store_mtm",
                )

                if not mtm_id:
                    raise ConsolidationSkip("MTM storage returned no identifier")

                await transaction.stage(
                    lambda: stm_storage.delete(item_id),
                    description="delete_stm",
                )

                logger.info(
                    "Consolidated memory %s from STM to MTM (new ID: %s)",
                    item_id,
                    mtm_id,
                )

                return mtm_id

            key = f"stm:{item_id}->mtm"

            while True:
                decision = await guard.reserve(key)
                if not decision.proceed:
                    if decision.result is None:
                        continue
                    break

                reservation = decision.reservation
                if reservation is None:
                    break

                async with reservation:
                    try:
                        mtm_id = await pipeline.run(key, runner)
                    except ConsolidationSkip:
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "Error consolidating STM memory %s: %s",
                            item_id,
                            exc,
                        )
                        break

                    reservation.commit(mtm_id)
                    break

    except Exception as e:
        logger.error(f"Error in STM to MTM consolidation: {str(e)}")


async def consolidate_mtm_to_ltm(
    mtm_storage,
    ltm_storage,
    config: Dict[str, Any],
    *,
    pipeline: TransactionalConsolidationPipeline | None = None,
    guard: ConsolidationInFlightGuard | None = None,
) -> None:
    """Consolidate important memories from MTM to LTM."""
    pipeline = pipeline or _GLOBAL_PIPELINE
    guard = guard or _GLOBAL_GUARD
    logger.debug("Starting MTM to LTM consolidation")
    
    try:
        # Get candidates from MTM
        # Focus on high priority, frequently accessed, and older memories
        mtm_memories = await mtm_storage.search(
            min_priority=MemoryPriority.HIGH
        )
        
        # Skip if no candidates
        if not mtm_memories:
            return
        
        # Prioritize candidates
        candidates = []
        for memory in mtm_memories:
            if not memory:
                continue
            
            # Get age in days
            age_days = 0
            if hasattr(memory, "created_at") and memory.created_at:
                age_days = (datetime.now() - memory.created_at).days
            
            # Get access count
            access_count = getattr(memory, "access_count", 0)
            
            # Get importance
            importance = 0.5
            if hasattr(memory, "metadata") and memory.metadata:
                if isinstance(memory.metadata, dict) and "importance" in memory.metadata:
                    importance = memory.metadata.get("importance", 0.5)
            
            # Calculate priority score for MTM->LTM consolidation
            # Favor: high importance, high access count, older memories
            priority_score = (
                importance * 0.5 +
                min(access_count, 20) / 20 * 0.3 +
                min(age_days, 30) / 30 * 0.2
            )
            
            # Add to candidates if score is high enough
            if priority_score >= 0.7:  # Threshold for MTM->LTM
                candidates.append((memory, priority_score))
        
        # Sort and limit
        candidates.sort(key=lambda x: x[1], reverse=True)
        batch_size = min(len(candidates), config.get("consolidation_batch_size", 3))
        top_candidates = candidates[:batch_size]
        
        summarizer = MemorySummarizer.from_config(config.get("summarization"))
        batch_summary = summarizer.summarize_memories([memory for memory, _ in top_candidates])
        per_item_summary = batch_summary.per_item
        batch_keywords = batch_summary.keywords
        batch_highlights = batch_summary.highlights
        batch_aggregate = batch_summary.aggregated_summary

        # Consolidate top candidates
        for memory, _ in top_candidates:
            memory_id = getattr(memory, "id", None)
            if not memory_id:
                continue

            content = getattr(memory, "content", {})
            summary = per_item_summary.get(str(memory_id)) or batch_aggregate
            if not summary:
                if isinstance(content, dict) and "text" in content:
                    summary = str(content.get("text", ""))[:200]
                else:
                    summary = str(content)[:200]

            tags = getattr(memory, "tags", [])

            importance = 0.5
            metadata_obj = getattr(memory, "metadata", None)
            if metadata_obj:
                if isinstance(metadata_obj, dict):
                    importance = metadata_obj.get("importance", importance)
                elif hasattr(metadata_obj, "importance"):
                    importance = getattr(metadata_obj, "importance")

            additional_metadata: Dict[str, Any] = {}
            if metadata_obj:
                if isinstance(metadata_obj, dict):
                    additional_metadata = dict(metadata_obj.get("additional_metadata", {}))
                elif hasattr(metadata_obj, "additional_metadata"):
                    additional_metadata = dict(getattr(metadata_obj, "additional_metadata"))

            summarization_package = {
                "aggregated": batch_aggregate,
                "keywords": batch_keywords,
                "highlights": batch_highlights.get(str(memory_id), []),
                "batch": batch_summary.batch_metadata,
            }
            additional_metadata["summarization"] = summarization_package

            if isinstance(tags, dict):
                tag_map: Dict[str, Any] = {str(k): v for k, v in tags.items()}
            elif isinstance(tags, (list, tuple, set)):
                tag_map = {str(tag): True for tag in tags}
            elif tags:
                tag_map = {str(tags): True}
            else:
                tag_map = {}

            memory_item = MemoryItem(
                content=content,
                summary=summary,
                metadata=MemoryMetadata(
                    status=MemoryStatus.ACTIVE,
                    tags=tag_map,
                    importance=importance,
                    created_at=datetime.now(),
                    source="mtm_consolidation",
                    consolidated_from=str(memory_id),
                    consolidated_at=datetime.now(),
                    additional_metadata=additional_metadata,
                )
            )

            async def runner(transaction: ConsolidationTransaction) -> Any:
                ltm_id = await transaction.stage(
                    lambda: ltm_storage.store(memory_item),
                    rollback=lambda inserted_id: _safe_delete(
                        ltm_storage,
                        inserted_id,
                        context=f"ltm rollback for {memory_id}",
                    ),
                    description="store_ltm",
                )

                if not ltm_id:
                    raise ConsolidationSkip("LTM storage returned no identifier")

                if hasattr(mtm_storage, "consolidate_memory"):
                    await transaction.stage(
                        lambda: mtm_storage.consolidate_memory(memory_id),
                        description="finalize_mtm",
                    )
                elif hasattr(mtm_storage, "delete"):
                    await transaction.stage(
                        lambda: mtm_storage.delete(memory_id),
                        description="delete_mtm",
                    )
                else:
                    raise RuntimeError("MTM storage lacks consolidation finalizer")

                logger.info(
                    "Consolidated memory %s from MTM to LTM (new ID: %s)",
                    memory_id,
                    ltm_id,
                )

                return ltm_id

            key = f"mtm:{memory_id}->ltm"

            while True:
                decision = await guard.reserve(key)
                if not decision.proceed:
                    if decision.result is None:
                        continue
                    break

                reservation = decision.reservation
                if reservation is None:
                    break

                async with reservation:
                    try:
                        ltm_id = await pipeline.run(key, runner)
                    except ConsolidationSkip:
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "Error consolidating MTM memory %s: %s",
                            memory_id,
                            exc,
                        )
                        break

                    reservation.commit(ltm_id)
                    break

    except Exception as e:
        logger.error(f"Error in MTM to LTM consolidation: {str(e)}")
