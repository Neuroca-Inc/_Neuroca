"""
Memory Manager Implementation

This module provides the implementation of the Memory Manager, which serves as
the central orchestration layer for the entire memory system, coordinating
operations across all memory tiers (STM, MTM, LTM) and providing a unified API.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Union

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends import BackendType
from neuroca.memory.exceptions import (
    MemoryManagerInitializationError,
    MemoryManagerOperationError,
    MemoryNotFoundError,
    InvalidTierError,
)
from neuroca.memory.interfaces.memory_manager import MemoryManagerInterface
from neuroca.memory.models.memory_item import MemoryItem, MemoryContent, MemoryMetadata
from neuroca.memory.models.working_memory import WorkingMemoryBuffer, WorkingMemoryItem
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier


logger = logging.getLogger(__name__)


class MemoryManager(MemoryManagerInterface):
    """
    Memory Manager Implementation
    
    The Memory Manager serves as the central orchestration layer for the
    memory system, coordinating operations across memory tiers (STM, MTM, LTM)
    and providing a unified API for the entire system.
    
    This class implements the MemoryManagerInterface and provides all the
    functionality described in the interface.
    """
    
    # Tier names
    STM_TIER = "stm"
    MTM_TIER = "mtm"
    LTM_TIER = "ltm"
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        backend_type: Optional[BackendType] = None,
        backend_config: Optional[Dict[str, Any]] = None,
        # Support for tier-specific storage types (new API)
        stm_storage_type: Optional[BackendType] = None,
        mtm_storage_type: Optional[BackendType] = None, 
        ltm_storage_type: Optional[BackendType] = None,
        vector_storage_type: Optional[BackendType] = None,
        # Support for direct tier instances (test API)
        stm: Optional[Any] = None,
        mtm: Optional[Any] = None,
        ltm: Optional[Any] = None,
        # Additional config options
        working_buffer_size: int = 20,
        embedding_dimension: int = 768,
    ):
        """
        Initialize the Memory Manager.
        
        Args:
            config: Configuration dictionary
            backend_type: Type of backend to use for all tiers
            backend_config: Backend configuration
        """
        self._config = config or {}
        self._backend_config = backend_config or {}
        
        # Handle tier-specific storage types (NEW API)
        self._stm_storage_type = stm_storage_type or backend_type or BackendType.MEMORY
        self._mtm_storage_type = mtm_storage_type or backend_type or BackendType.MEMORY
        self._ltm_storage_type = ltm_storage_type or backend_type or BackendType.MEMORY
        self._vector_storage_type = vector_storage_type or backend_type or BackendType.MEMORY
        
        # Handle direct tier instances (TEST API)
        self._stm_instance = stm
        self._mtm_instance = mtm
        self._ltm_instance = ltm
        
        # Additional configuration
        self._working_buffer_size = working_buffer_size
        self._embedding_dimension = embedding_dimension
        
        # Set default tier configurations
        self._stm_config = self._config.get("stm", {})
        self._mtm_config = self._config.get("mtm", {})
        self._ltm_config = self._config.get("ltm", {})
        
        # Legacy support - store for backwards compatibility
        self._backend_type = backend_type
        
        # Initialize tiers to None
        self._stm = None
        self._mtm = None
        self._ltm = None
        
        # Initialize working memory buffer
        self._working_memory = WorkingMemoryBuffer()
        
        # Initialization flag
        self._initialized = False
        
        # Background tasks
        self._maintenance_task = None
        
        # Context related
        self._current_context = {}
        self._current_context_embedding = None
        
        # Maintenance interval
        self._maintenance_interval = self._config.get("maintenance_interval", 3600)  # Default: 1 hour

    # ------------------------------------------------------------------
    # Legacy compatibility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_tier_name(tier: Any | None) -> Optional[str]:
        """Normalize tier inputs originating from legacy call sites."""

        if tier is None:
            return None
        if isinstance(tier, MemoryTier):
            return tier.storage_key
        try:
            return MemoryTier.from_string(str(tier)).storage_key
        except ValueError:
            return str(tier).strip().lower()

    @staticmethod
    def _merge_metadata(
        metadata: Any | None,
        *,
        emotional_salience: float | None,
    ) -> dict[str, Any]:
        """Return a metadata dictionary honoring historical call patterns."""

        base: dict[str, Any] = {}
        if isinstance(metadata, dict):
            base.update(metadata)
        elif metadata is not None:
            base["legacy_metadata"] = metadata

        if emotional_salience is not None and "emotional_salience" not in base:
            base["emotional_salience"] = emotional_salience

        return base

    @staticmethod
    def _extract_content_payload(content: Any) -> Any:
        """Derive the legacy-facing content payload from tier search results."""

        if isinstance(content, dict):
            for key in ("data", "raw_content", "json_data"):
                if content.get(key) is not None:
                    return content[key]
            text = content.get("text")
            if text is not None:
                return text
            summary = content.get("summary")
            if summary is not None:
                return summary
        return content

    @classmethod
    def _wrap_search_results(cls, results: Iterable[Any] | None) -> list[Any]:
        """Coerce search results into legacy-compatible objects."""

        if not results:
            return []

        wrapped: list[Any] = []
        for item in results:
            if isinstance(item, MemoryItem):
                wrapped.append(
                    SimpleNamespace(
                        content=cls._extract_content_payload(item.content.model_dump()),
                        metadata=item.metadata.model_dump(),
                        tier=item.metadata.tier,
                        relevance=item.metadata.relevance,
                        raw=item,
                        id=getattr(item, "id", None),
                    )
                )
                continue

            if hasattr(item, "content") and hasattr(item, "metadata"):
                wrapped.append(item)
                continue

            if isinstance(item, dict):
                metadata = item.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {} if metadata is None else {"legacy_metadata": metadata}
                wrapped.append(
                    SimpleNamespace(
                        content=cls._extract_content_payload(item.get("content")),
                        metadata=metadata,
                        tier=item.get("tier") or metadata.get("tier"),
                        relevance=item.get("_relevance") or metadata.get("relevance"),
                        raw=item,
                        id=item.get("id") or metadata.get("id"),
                    )
                )
                continue

            wrapped.append(item)

        return wrapped

    def _legacy_call(
        self,
        coro: Awaitable[Any],
        *,
        transform: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Execute a coroutine while preserving historical synchronous semantics."""

        async def _runner() -> Any:
            result = await coro
            return transform(result) if transform is not None else result

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_runner())

        task = loop.create_task(_runner())

        def _log_failure(done: asyncio.Future[Any]) -> None:
            if done.cancelled():
                return
            try:
                done.result()
            except Exception:  # noqa: BLE001
                logger.exception("Legacy memory manager compatibility call failed")

        task.add_done_callback(_log_failure)
        return task

    # ------------------------------------------------------------------
    # Legacy public API compatibility
    # ------------------------------------------------------------------

    def store(
        self,
        content: Any,
        *,
        summary: str | None = None,
        importance: float = 0.5,
        metadata: Any | None = None,
        tags: Optional[List[str]] = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        emotional_salience: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Store a memory using the legacy synchronous signature."""

        initial_tier = self._normalize_tier_name(tier or memory_type)
        merged_metadata = self._merge_metadata(metadata, emotional_salience=emotional_salience)

        return self._legacy_call(
            self.add_memory(
                content=content,
                summary=summary,
                importance=importance,
                metadata=merged_metadata,
                tags=tags,
                initial_tier=initial_tier,
                **{k: v for k, v in kwargs.items() if k not in {"memory_type", "tier"}},
            )
        )

    def retrieve(
        self,
        *args: Any,
        query: str | None = None,
        memory_id: str | None = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        limit: int | None = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Retrieve memories using the historic flexible interface."""

        if args and not query and memory_id is None:
            # Support positional access via ID.
            memory_id = str(args[0])

        if memory_id is not None:
            normalized_tier = self._normalize_tier_name(tier)
            return self._legacy_call(
                self.retrieve_memory(memory_id, tier=normalized_tier),
                transform=lambda result: self._wrap_search_results([result])[0] if result else None,
            )

        normalized_tier = self._normalize_tier_name(tier or memory_type)
        search_kwargs: dict[str, Any] = {
            "query": query or (args[0] if args else None),
            "limit": kwargs.get("top_k", limit),
            "tiers": [normalized_tier] if normalized_tier else None,
        }

        if tags:
            search_kwargs["tags"] = tags
        if metadata_filters:
            search_kwargs["metadata_filters"] = metadata_filters

        return self._legacy_call(
            self.search_memories(**search_kwargs),
            transform=self._wrap_search_results,
        )

    def search(self, query: str | None = None, **kwargs: Any) -> Any:
        """Legacy alias that routed to search APIs."""

        return self.retrieve(query=query, **kwargs)

    def retrieve_relevant(self, query: str, *, tier: Any | None = None, limit: int | None = None, **kwargs: Any) -> Any:
        """Legacy helper used by integration utilities."""

        return self.retrieve(query=query, tier=tier, limit=limit, **kwargs)
    
    async def initialize(self) -> None:
        """
        Initialize the memory manager and all storage components.
        
        This method must be called before any other method.
        
        Raises:
            MemoryManagerInitializationError: If initialization fails
        """
        if self._initialized:
            logger.warning("Memory Manager already initialized")
            return
        
        try:
            logger.info("Initializing Memory Manager")
            
            # Initialize STM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing STM tier")
            if self._stm_instance:
                self._stm = self._stm_instance
                if hasattr(self._stm, 'initialize'):
                    await self._stm.initialize()
            else:
                self._stm = ShortTermMemoryTier(
                    backend_type=self._stm_storage_type,
                    backend_config=self._backend_config,
                    config=self._stm_config,
                )
                await self._stm.initialize()
            
            # Initialize MTM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing MTM tier")
            if self._mtm_instance:
                self._mtm = self._mtm_instance
                if hasattr(self._mtm, 'initialize'):
                    await self._mtm.initialize()
            else:
                self._mtm = MediumTermMemoryTier(
                    backend_type=self._mtm_storage_type,
                    backend_config=self._backend_config,
                    config=self._mtm_config,
                )
                await self._mtm.initialize()
            
            # Initialize LTM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing LTM tier")
            if self._ltm_instance:
                self._ltm = self._ltm_instance
                if hasattr(self._ltm, 'initialize'):
                    await self._ltm.initialize()
            else:
                self._ltm = LongTermMemoryTier(
                    backend_type=self._ltm_storage_type,
                    backend_config=self._backend_config,
                    config=self._ltm_config,
                )
                await self._ltm.initialize()
            
            # Start maintenance task if interval > 0
            if self._maintenance_interval > 0:
                self._start_maintenance_task()
            
            self._initialized = True
            logger.info("Memory Manager initialization complete")
        except Exception as e:
            logger.exception("Failed to initialize Memory Manager")
            raise MemoryManagerInitializationError(
                f"Failed to initialize Memory Manager: {str(e)}"
            ) from e
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the memory manager and all storage components.
        
        This method should be called when the memory system is no longer needed
        to ensure all resources are released and pending operations are completed.
        
        Raises:
            MemoryManagerOperationError: If shutdown fails
        """
        if not self._initialized:
            logger.warning("Memory Manager not initialized, nothing to shut down")
            return
        
        try:
            logger.info("Shutting down Memory Manager")
            
            # Stop maintenance task
            if self._maintenance_task:
                self._maintenance_task.cancel()
                try:
                    await self._maintenance_task
                except asyncio.CancelledError:
                    pass
                self._maintenance_task = None
            
            # Shutdown tiers
            if self._stm:
                await self._stm.shutdown()
            
            if self._mtm:
                await self._mtm.shutdown()
            
            if self._ltm:
                await self._ltm.shutdown()
            
            self._initialized = False
            logger.info("Memory Manager shutdown complete")
        except Exception as e:
            logger.exception("Failed to shut down Memory Manager")
            raise MemoryManagerOperationError(
                f"Failed to shut down Memory Manager: {str(e)}"
            ) from e
    
    def _ensure_initialized(self) -> None:
        """
        Ensure that the Memory Manager is initialized.

        Raises:
            MemoryManagerOperationError: If not initialized
        """
        if not self._initialized:
            raise MemoryManagerOperationError(
                "Memory Manager not initialized. Call initialize() first."
            )

    # ------------------------------------------------------------------
    # Tier accessors
    # ------------------------------------------------------------------

    @property
    def stm_storage(self) -> ShortTermMemoryTier:
        """Return the initialized STM tier instance."""

        self._ensure_initialized()
        if self._stm is None:
            raise MemoryManagerOperationError("STM storage tier not available")
        return self._stm

    @property
    def mtm_storage(self) -> MediumTermMemoryTier:
        """Return the initialized MTM tier instance."""

        self._ensure_initialized()
        if self._mtm is None:
            raise MemoryManagerOperationError("MTM storage tier not available")
        return self._mtm

    @property
    def ltm_storage(self) -> LongTermMemoryTier:
        """Return the initialized LTM tier instance."""

        self._ensure_initialized()
        if self._ltm is None:
            raise MemoryManagerOperationError("LTM storage tier not available")
        return self._ltm

    def get_tier(
        self, tier_name: str
    ) -> ShortTermMemoryTier | MediumTermMemoryTier | LongTermMemoryTier:
        """Public accessor for tier instances using canonical string names."""

        self._ensure_initialized()
        return self._get_tier_by_name(tier_name)
    
    def _start_maintenance_task(self) -> None:
        """
        Start the background maintenance task.
        """
        if self._maintenance_task is None or self._maintenance_task.done():
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
    
    async def _maintenance_loop(self) -> None:
        """
        Background task for periodically running maintenance on all tiers.
        """
        try:
            while True:
                # Wait for the next maintenance interval
                await asyncio.sleep(self._maintenance_interval)
                
                # Run maintenance
                try:
                    await self.run_maintenance()
                except Exception as e:
                    logger.error(f"Error in maintenance loop: {str(e)}")
        except asyncio.CancelledError:
            logger.info("Maintenance task cancelled")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in maintenance loop: {str(e)}")
    
    def _get_tier_by_name(self, tier_name: str):
        """
        Get a tier instance by name.
        
        Args:
            tier_name: Tier name ("stm", "mtm", "ltm")
            
        Returns:
            Tier instance
            
        Raises:
            InvalidTierError: If tier name is invalid
        """
        if tier_name == self.STM_TIER:
            return self._stm
        elif tier_name == self.MTM_TIER:
            return self._mtm
        elif tier_name == self.LTM_TIER:
            return self._ltm
        else:
            raise InvalidTierError(f"Invalid tier name: {tier_name}")
    
    #-----------------------------------------------------------------------
    # Core Memory Operations
    #-----------------------------------------------------------------------
    
    async def add_memory(
        self,
        content: Any,
        summary: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
        initial_tier: Optional[str] = None,
    ) -> str:
        """
        Add a new memory to the system.
        
        By default, memories start in STM and may be consolidated to MTM/LTM
        based on importance and access patterns.
        
        Args:
            content: Memory content (can be text, dict, or structured data)
            summary: Optional summary of the content
            importance: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            tags: Tags for categorization
            embedding: Optional pre-computed embedding vector
            initial_tier: Initial storage tier (default is STM)
            
        Returns:
            Memory ID
            
        Raises:
            MemoryManagerOperationError: If the add operation fails
        """
        self._ensure_initialized()
        
        # Determine initial tier
        initial_tier = initial_tier or self.STM_TIER
        
        # Get tier instance
        tier = self._get_tier_by_name(initial_tier)
        
        # Create memory item
        memory_content = MemoryContent(
            text=content if isinstance(content, str) else None,
            data=content if not isinstance(content, str) else None,
            summary=summary,
            embedding=embedding,
        )
        
        # Process metadata and tags
        tags = tags or []
        metadata_dict = metadata or {}
        if not isinstance(metadata_dict, dict):
            metadata_dict = {"data": metadata_dict}
        
        # Add tier-specific tags
        tags_dict = metadata_dict.get("tags", {})
        if not isinstance(tags_dict, dict):
            tags_dict = {}
            
        for tag in tags:
            tags_dict[tag] = True
            
        # Create memory metadata
        memory_metadata = MemoryMetadata(
            importance=importance,
            tags=tags_dict,
            **metadata_dict,
        )
        
        # Create memory item
        memory_item = MemoryItem(
            content=memory_content,
            metadata=memory_metadata,
        )
        
        try:
            # Store in tier
            memory_id = await tier.store(memory_item.model_dump())
            
            # Update working memory with new memory if it's relevant to current context
            # This would require calculating relevance, which we're keeping simple for now
            if self._current_context:
                # For demonstration, we'll add any memory with importance > 0.7 to working memory
                if importance > 0.7:
                    memory_data = await tier.retrieve(memory_id)
                    if memory_data:
                        # Convert to MemoryItem if needed
                        memory_item = memory_data if isinstance(memory_data, MemoryItem) else MemoryItem.model_validate(memory_data)
                        
                        self._working_memory.add_item(
                            WorkingMemoryItem(
                                memory=memory_item,
                                source_tier=initial_tier,
                                relevance=0.9,  # High relevance for highly important memories
                            )
                        )
            
            logger.debug(f"Added memory {memory_id} to {initial_tier} tier")
            return memory_id
        except Exception as e:
            logger.exception(f"Failed to add memory to {initial_tier} tier")
            raise MemoryManagerOperationError(
                f"Failed to add memory: {str(e)}"
            ) from e
    
    async def retrieve_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        Retrieve a specific memory by ID.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to search in (searches all tiers if not specified)
            
        Returns:
            MemoryItem if found, otherwise None
            
        Raises:
            MemoryManagerOperationError: If the retrieve operation fails
        """
        self._ensure_initialized()
        
        try:
            # If tier is specified, search only that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.retrieve(memory_id)
            
            # Otherwise, search all tiers starting from STM (most recent)
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                memory_data = await tier_instance.retrieve(memory_id)
                if memory_data:
                    # Access the memory to update its statistics
                    await tier_instance.access(memory_id)
                    return memory_data
            
            # Memory not found in any tier
            return None
        except InvalidTierError as e:
            # Re-raise with more specific error
            raise e
        except Exception as e:
            logger.exception(f"Failed to retrieve memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to retrieve memory: {str(e)}"
            ) from e
    
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[Any] = None,
        summary: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory ID
            content: New content (if None, keeps existing content)
            summary: New summary (if None, keeps existing summary)
            importance: New importance (if None, keeps existing importance)
            metadata: New metadata (if None, keeps existing metadata)
            tags: New tags (if None, keeps existing tags)
            
        Returns:
            bool: True if the update was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the update operation fails
        """
        self._ensure_initialized()
        
        # First, find the memory in all tiers
        memory_tier = None
        memory_data = None
        
        for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            tier_instance = self._get_tier_by_name(tier_name)
            data = await tier_instance.retrieve(memory_id)
            if data:
                memory_tier = tier_name
                memory_data = data
                break
        
        if not memory_data or not memory_tier:
            raise MemoryNotFoundError(f"Memory {memory_id} not found in any tier")
        
        try:
            # Prepare content updates
            content_updates = {}
            if content is not None:
                if isinstance(content, str):
                    content_updates["text"] = content
                    content_updates["data"] = None
                else:
                    content_updates["text"] = None
                    content_updates["data"] = content
            
            if summary is not None:
                content_updates["summary"] = summary
            
            # Prepare metadata updates
            metadata_updates = {}
            if importance is not None:
                metadata_updates["importance"] = importance
            
            # Process tags
            if tags is not None:
                metadata_source: dict[str, Any] = {}
                if isinstance(memory_data, dict):
                    raw_metadata = memory_data.get("metadata")
                    if isinstance(raw_metadata, dict):
                        metadata_source = dict(raw_metadata)
                else:
                    existing_metadata = getattr(memory_data, "metadata", None)
                    if existing_metadata is not None:
                        if hasattr(existing_metadata, "model_dump"):
                            try:
                                dumped = existing_metadata.model_dump()  # type: ignore[call-arg]
                            except Exception:  # noqa: BLE001
                                dumped = {}
                            metadata_source = dumped if isinstance(dumped, dict) else {}
                        elif hasattr(existing_metadata, "dict"):
                            try:
                                dumped = existing_metadata.dict()  # type: ignore[call-arg]
                            except Exception:  # noqa: BLE001
                                dumped = {}
                            metadata_source = dumped if isinstance(dumped, dict) else {}

                existing_tags = metadata_source.get("tags", {}) if metadata_source else {}
                if not isinstance(existing_tags, dict):
                    existing_tags = {}

                for tag in tags:
                    existing_tags[tag] = True

                metadata_updates["tags"] = existing_tags
            
            # Merge with additional metadata
            if metadata is not None:
                for key, value in metadata.items():
                    if key != "tags":  # Tags handled separately
                        metadata_updates[key] = value
            
            # Get the tier instance
            tier_instance = self._get_tier_by_name(memory_tier)
            
            # Update the memory
            success = await tier_instance.update(
                memory_id,
                content=content_updates if content_updates else None,
                metadata=metadata_updates if metadata_updates else None,
            )
            
            # Note: Working memory update would be handled here if needed
            # Currently WorkingMemoryBuffer doesn't have update_item method
            
            return success
        except Exception as e:
            logger.exception(f"Failed to update memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to update memory: {str(e)}"
            ) from e
    
    async def delete_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
    ) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to delete from (tries all tiers if not specified)
            
        Returns:
            bool: True if the deletion was successful
            
        Raises:
            MemoryManagerOperationError: If the delete operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, delete only from that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                success = await tier_instance.delete(memory_id)
            else:
                # Otherwise, try to delete from all tiers
                for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                    tier_instance = self._get_tier_by_name(tier_name)
                    if await tier_instance.delete(memory_id):
                        success = True
            
            # Remove from working memory if deleted
            if success:
                self._working_memory.remove_item(memory_id)
            
            return success
        except InvalidTierError as e:
            # Re-raise with more specific error
            raise e
        except Exception as e:
            logger.exception(f"Failed to delete memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to delete memory: {str(e)}"
            ) from e

    async def transfer_memory(
        self,
        memory_id: str,
        target_tier: Union[str, MemoryTier],
    ) -> MemoryItem:
        """Move a memory from its current tier into ``target_tier``."""

        self._ensure_initialized()

        try:
            resolved_target = (
                target_tier.storage_key
                if isinstance(target_tier, MemoryTier)
                else MemoryTier.from_string(str(target_tier)).storage_key
            )
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise InvalidTierError(f"Unknown target tier: {target_tier!r}") from exc

        source_tier_name: Optional[str] = None
        memory_item: Optional[MemoryItem] = None

        for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            tier_instance = self._get_tier_by_name(tier_name)
            fetched = await tier_instance.retrieve(memory_id)
            if fetched:
                source_tier_name = tier_name
                memory_item = (
                    fetched
                    if isinstance(fetched, MemoryItem)
                    else MemoryItem.model_validate(fetched)
                )
                break

        if memory_item is None or source_tier_name is None:
            raise MemoryNotFoundError(f"Memory {memory_id} not found in any tier")

        if source_tier_name == resolved_target:
            return memory_item

        source_tier = self._get_tier_by_name(source_tier_name)
        target_tier_instance = self._get_tier_by_name(resolved_target)

        if getattr(memory_item, "metadata", None):
            memory_item.metadata.tier = resolved_target
            if hasattr(memory_item.metadata, "updated_at"):
                memory_item.metadata.updated_at = datetime.now(timezone.utc)

        payload = memory_item.model_dump()

        try:
            await target_tier_instance.store(payload, memory_id=memory_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to transfer memory %s to %s", memory_id, resolved_target
            )
            raise MemoryManagerOperationError(
                f"Failed to move memory to {resolved_target}: {exc}"
            ) from exc

        try:
            await source_tier.delete(memory_id)
        except Exception:  # noqa: BLE001 - log and continue, target copy already exists
            logger.warning(
                "Failed to delete memory %s from %s after transfer",
                memory_id,
                source_tier_name,
                exc_info=True,
            )

        if self._working_memory and self._working_memory.contains(memory_id):
            self._working_memory.remove_item(memory_id)

        moved = await target_tier_instance.retrieve(memory_id)
        return (
            moved
            if isinstance(moved, MemoryItem)
            else MemoryItem.model_validate(moved)
        )

    #-----------------------------------------------------------------------
    # Search and Retrieval
    #-----------------------------------------------------------------------
    
    async def search_memories(
        self,
        query: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        min_relevance: float = 0.0,
        tiers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for memories across all tiers.
        
        Args:
            query: Text query
            embedding: Optional query embedding for vector search
            tags: Optional tags to filter by
            metadata_filters: Optional metadata field filters
            limit: Maximum number of results
            min_relevance: Minimum relevance score (0.0 to 1.0)
            tiers: Optional list of tiers to search in
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryManagerOperationError: If the search operation fails
        """
        self._ensure_initialized()
        
        try:
            # Determine which tiers to search
            search_tiers = tiers or [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]
            all_results = []
            
            # Build filter dictionary from tags
            if tags:
                if not metadata_filters:
                    metadata_filters = {}
                for tag in tags:
                    metadata_filters[f"metadata.tags.{tag}"] = True
            
            # Search each tier
            for tier_name in search_tiers:
                try:
                    tier_instance = self._get_tier_by_name(tier_name)
                    
                    # Create search options
                    tier_search_results = await tier_instance.search(
                        query=query,
                        embedding=embedding,
                        filters=metadata_filters,
                        limit=limit,
                    )
                    
                    # Extract results from MemorySearchResults and convert to dicts
                    for search_result in tier_search_results.results:
                        result_dict = search_result.memory.model_dump()
                        result_dict["tier"] = tier_name
                        # Add relevance score from search result
                        result_dict["_relevance"] = search_result.relevance
                        all_results.append(result_dict)
                    
                except Exception as e:
                    logger.error(f"Error searching tier {tier_name}: {str(e)}")
            
            # Sort results by relevance (if available) or importance
            def get_sort_key(item):
                relevance = item.get("_relevance", 0.0)
                importance = item.get("metadata", {}).get("importance", 0.0)
                # Weigh relevance higher than importance
                return (relevance * 0.7) + (importance * 0.3)
            
            sorted_results = sorted(
                all_results,
                key=get_sort_key,
                reverse=True,
            )
            
            # Limit final results
            return sorted_results[:limit]
        except Exception as e:
            logger.exception("Failed to search memories")
            raise MemoryManagerOperationError(
                f"Failed to search memories: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # Context Management
    #-----------------------------------------------------------------------
    
    async def update_context(
        self,
        context_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        Update the current context to trigger relevant memory retrieval.
        
        This method updates the system's understanding of the current context,
        such as the current conversation, user input, goals, etc. It triggers
        background retrieval of relevant memories for the working memory buffer.
        
        Args:
            context_data: Dictionary with current context information
            embedding: Optional pre-computed embedding of the context
            
        Raises:
            MemoryManagerOperationError: If the context update fails
        """
        self._ensure_initialized()
        
        try:
            # Update current context
            self._current_context = context_data
            self._current_context_embedding = embedding
            
            # Extract text for text search if no embedding provided
            query_text = None
            if not embedding:
                # Try to extract text from context_data
                if "text" in context_data:
                    query_text = context_data["text"]
                elif "query" in context_data:
                    query_text = context_data["query"]
                elif "input" in context_data:
                    query_text = context_data["input"]
                elif "message" in context_data:
                    query_text = context_data["message"]
            
            # Clear working memory
            self._working_memory.clear()
            
            # Search for relevant memories in all tiers
            relevant_memories = await self.search_memories(
                query=query_text,
                embedding=embedding,
                limit=20,  # Get more than needed for diversity
                min_relevance=0.3,  # Lower threshold to get more diverse results
            )
            
            # Add relevant memories to working memory
            for memory in relevant_memories:
                memory_id = memory.get("id")
                tier = memory.get("tier")
                relevance = memory.get("_relevance", 0.5)
                
                if memory_id and tier:
                    # Convert dict to MemoryItem if needed
                    memory_item = memory.get('memory') if isinstance(memory.get('memory'), MemoryItem) else MemoryItem.model_validate(memory)
                    
                    self._working_memory.add_item(
                        WorkingMemoryItem(
                            memory=memory_item,
                            source_tier=tier,
                            relevance=relevance,
                        )
                    )
            
            logger.debug(f"Updated context and working memory with {len(relevant_memories)} relevant memories")
        except Exception as e:
            logger.exception("Failed to update context")
            raise MemoryManagerOperationError(
                f"Failed to update context: {str(e)}"
            ) from e
    
    async def get_prompt_context_memories(
        self,
        max_memories: int = 5,
        max_tokens_per_memory: int = 150,
    ) -> List[Dict[str, Any]]:
        """
        Get the most relevant memories for injection into the agent's prompt.
        
        This method is used by the prompt builder to inject relevant context
        from the memory system into the agent's prompt.
        
        Args:
            max_memories: Maximum number of memories to include
            max_tokens_per_memory: Maximum tokens per memory
            
        Returns:
            List of formatted memory dictionaries
            
        Raises:
            MemoryManagerOperationError: If the prompt context retrieval fails
        """
        self._ensure_initialized()
        
        try:
            # Get the most relevant items from working memory
            working_memory_items = self._working_memory.get_most_relevant_items(max_memories)
            
            # Format memories for prompt inclusion
            formatted_memories = []
            
            for item in working_memory_items:
                memory_data = item.memory.model_dump()
                
                # Format the memory for prompt inclusion
                formatted_memory = {
                    "id": memory_data.get("id"),
                    "content": memory_data.get("content", {}).get("text") or "[Structured Data]",
                    "summary": memory_data.get("content", {}).get("summary") or None,
                    "importance": memory_data.get("metadata", {}).get("importance", 0.5),
                    "created_at": memory_data.get("metadata", {}).get("created_at"),
                    "relevance": item.relevance,
                    "tier": item.source_tier,
                }
                
                # Truncate content to max_tokens_per_memory
                # This is a simple approximation, a real implementation would use a proper tokenizer
                text = formatted_memory["content"]
                if text and isinstance(text, str):
                    words = text.split()
                    if len(words) > max_tokens_per_memory / 0.75:  # Approximate tokens by words
                        formatted_memory["content"] = " ".join(words[:int(max_tokens_per_memory / 0.75)]) + "..."
                
                formatted_memories.append(formatted_memory)
            
            return formatted_memories
        except Exception as e:
            logger.exception("Failed to get prompt context memories")
            raise MemoryManagerOperationError(
                f"Failed to get prompt context memories: {str(e)}"
            ) from e
    
    async def clear_context(self) -> None:
        """
        Clear the current context and working memory buffer.
        
        This method is typically called at the end of a conversation or
        when switching to a completely different task.
        
        Raises:
            MemoryManagerOperationError: If the clear context operation fails
        """
        self._ensure_initialized()
        
        try:
            # Clear current context
            self._current_context = {}
            self._current_context_embedding = None
            
            # Clear working memory
            self._working_memory.clear()
            
            logger.debug("Cleared context and working memory")
        except Exception as e:
            logger.exception("Failed to clear context")
            raise MemoryManagerOperationError(
                f"Failed to clear context: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # Memory Lifecycle Management
    #-----------------------------------------------------------------------
    
    async def consolidate_memory(
        self,
        memory_id: str,
        source_tier: str,
        target_tier: str,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Explicitly consolidate a memory from one tier to another.
        
        This method allows for manual consolidation of a memory, 
        in addition to the automatic consolidation done by the system.
        
        Args:
            memory_id: Memory ID
            source_tier: Source tier ("stm", "mtm", "ltm")
            target_tier: Target tier ("stm", "mtm", "ltm")
            additional_metadata: Optional additional metadata to add during consolidation
            
        Returns:
            The ID of the consolidated memory in the target tier (may be the same or different)
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            InvalidTierError: If source or target tier is invalid
            MemoryManagerOperationError: If the consolidation fails
        """
        self._ensure_initialized()
        
        # Validate tiers
        if source_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid source tier: {source_tier}")
        
        if target_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid target tier: {target_tier}")
        
        # Get source and target tier instances
        source_tier_instance = self._get_tier_by_name(source_tier)
        target_tier_instance = self._get_tier_by_name(target_tier)
        
        try:
            # Retrieve memory from source tier
            memory_data = await source_tier_instance.retrieve(memory_id)
            if not memory_data:
                raise MemoryNotFoundError(
                    f"Memory {memory_id} not found in {source_tier} tier"
                )
            
            # Apply additional metadata if provided
            if additional_metadata:
                # Update existing metadata
                if isinstance(memory_data, MemoryItem):
                    metadata = memory_data.metadata
                    # Store additional metadata in tags since MemoryMetadata has strict fields
                    tags = metadata.tags
                    for key, value in additional_metadata.items():
                        if key == "tags" and isinstance(value, dict):
                            # Merge with existing tags
                            tags.update(value)
                        else:
                            # Store other metadata as tags with a prefix
                            tags[f"_meta_{key}"] = value
                    metadata.tags = tags
                else:
                    # Legacy dict handling
                    metadata = memory_data.get("metadata", {})
                    for key, value in additional_metadata.items():
                        if key == "tags":
                            # Special handling for tags
                            tags = metadata.get("tags", {})
                            tags.update(value)
                            metadata["tags"] = tags
                        else:
                            metadata[key] = value
                    
                    memory_data["metadata"] = metadata
            
            # Add to target tier
            new_id = await target_tier_instance.store(memory_data)
            
            # If source and target tiers are different, delete from source tier
            if source_tier != target_tier:
                await source_tier_instance.delete(memory_id)
                
                # Note: Working memory tier update would be handled here if needed
                # Currently WorkingMemoryBuffer doesn't have update_item_tier method
            
            return new_id
        except Exception as e:
            if isinstance(e, (MemoryNotFoundError, InvalidTierError)):
                raise
            
            logger.exception(f"Failed to consolidate memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to consolidate memory: {str(e)}"
            ) from e
    
    async def strengthen_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        strengthen_amount: float = 0.1,
    ) -> bool:
        """
        Strengthen a memory to make it less likely to be forgotten.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to strengthen in (tries all tiers if not specified)
            strengthen_amount: Amount to strengthen by (0.0 to 1.0)
            
        Returns:
            bool: True if the strengthening was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the strengthen operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, strengthen only in that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.strengthen(memory_id, strengthen_amount)
            
            # Otherwise, try to strengthen in all tiers
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                if await tier_instance.exists(memory_id):
                    if await tier_instance.strengthen(memory_id, strengthen_amount):
                        success = True
                    break  # Stop after strengthening in first tier where memory exists
            
            return success
        except Exception as e:
            if isinstance(e, InvalidTierError):
                raise
            
            logger.exception(f"Failed to strengthen memory {memory_id}")
            if isinstance(e, MemoryNotFoundError):
                raise
            
            raise MemoryManagerOperationError(
                f"Failed to strengthen memory: {str(e)}"
            ) from e
    
    async def decay_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        decay_amount: float = 0.1,
    ) -> bool:
        """
        Explicitly decay a memory to make it more likely to be forgotten.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to decay in (tries all tiers if not specified)
            decay_amount: Amount to decay by (0.0 to 1.0)
            
        Returns:
            bool: True if the decay was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the decay operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, decay only in that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.decay(memory_id, decay_amount)
            
            # Otherwise, try to decay in all tiers
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                if await tier_instance.exists(memory_id):
                    if await tier_instance.decay(memory_id, decay_amount):
                        success = True
                    break  # Stop after decaying in first tier where memory exists
            
            return success
        except Exception as e:
            if isinstance(e, InvalidTierError):
                raise
            
            logger.exception(f"Failed to decay memory {memory_id}")
            if isinstance(e, MemoryNotFoundError):
                raise
            
            raise MemoryManagerOperationError(
                f"Failed to decay memory: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # System Management
    #-----------------------------------------------------------------------
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the memory system.
        
        Returns:
            Dictionary of statistics
            
        Raises:
            MemoryManagerOperationError: If the stats retrieval fails
        """
        self._ensure_initialized()
        
        try:
            stats = {
                "timestamp": time.time(),
                "tiers": {},
                "working_memory": {
                    "size": len(self._working_memory),
                    "capacity": self._working_memory.capacity,
                }
            }
            
            # Get stats for each tier
            for tier_name, tier_instance in [
                (self.STM_TIER, self._stm),
                (self.MTM_TIER, self._mtm),
                (self.LTM_TIER, self._ltm),
            ]:
                tier_stats = await tier_instance.get_stats()
                stats["tiers"][tier_name] = tier_stats
            
            # Calculate overall stats
            total_memories = sum(
                tier_stats.get("total_memories", 0)
                for tier_stats in stats["tiers"].values()
            )
            
            stats["total_memories"] = total_memories
            
            return stats
        except Exception as e:
            logger.exception("Failed to get system stats")
            raise MemoryManagerOperationError(
                f"Failed to get system stats: {str(e)}"
            ) from e
    
    async def run_maintenance(self) -> Dict[str, Any]:
        """
        Run maintenance tasks on the memory system.
        
        This includes tasks like:
        - Consolidating memories between tiers
        - Decaying memories
        - Cleaning up expired memories
        - Optimizing storage
        
        Returns:
            Dictionary of maintenance results
            
        Raises:
            MemoryManagerOperationError: If the maintenance fails
        """
        self._ensure_initialized()
        
        try:
            results = {
                "timestamp": time.time(),
                "tiers": {},
                "consolidated_memories": 0,
            }
            
            # Run maintenance on each tier
            for tier_name, tier_instance in [
                (self.STM_TIER, self._stm),
                (self.MTM_TIER, self._mtm),
                (self.LTM_TIER, self._ltm),
            ]:
                tier_results = await tier_instance.run_maintenance()
                results["tiers"][tier_name] = tier_results
            
            # Check for STM → MTM promotion candidates
            # For memories that have been accessed frequently or are important
            if self._stm and self._mtm:
                stm_memories = await self._stm.query(
                    filters={
                        "metadata.importance": {"$gt": 0.7},  # High importance memories
                        "metadata.access_count": {"$gt": 5},  # Frequently accessed memories
                    },
                    limit=10,
                )
                
                # Consolidate these memories to MTM
                for memory in stm_memories:
                    memory_id = memory.get("id")
                    if memory_id:
                        try:
                            new_id = await self.consolidate_memory(
                                memory_id=memory_id,
                                source_tier=self.STM_TIER,
                                target_tier=self.MTM_TIER,
                                additional_metadata={
                                    "consolidated": True,
                                    "consolidation_timestamp": time.time(),
                                }
                            )
                            if new_id:
                                results["consolidated_memories"] += 1
                        except Exception as e:
                            logger.error(f"Error consolidating memory {memory_id}: {str(e)}")
            
            # Check for MTM → LTM promotion candidates
            if self._mtm and self._ltm:
                # Get promotion candidates from MTM tier
                mtm_candidates = await self._mtm.get_promotion_candidates(limit=10)
                
                # Consolidate these memories to LTM
                for memory in mtm_candidates:
                    memory_id = memory.get("id")
                    if memory_id:
                        try:
                            new_id = await self.consolidate_memory(
                                memory_id=memory_id,
                                source_tier=self.MTM_TIER,
                                target_tier=self.LTM_TIER,
                                additional_metadata={
                                    "consolidated": True,
                                    "consolidation_timestamp": time.time(),
                                }
                            )
                            if new_id:
                                results["consolidated_memories"] += 1
                        except Exception as e:
                            logger.error(f"Error consolidating memory {memory_id}: {str(e)}")
            
            return results
        except Exception as e:
            logger.exception("Failed to run maintenance")
            raise MemoryManagerOperationError(
                f"Failed to run maintenance: {str(e)}"
            ) from e
