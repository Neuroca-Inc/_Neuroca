"""
Memory Service Layer

This module provides a service layer that acts as an intermediary between the
API routes and the core MemoryManager. It encapsulates business logic,
user-specific operations, and error handling.
"""

import logging
from uuid import UUID
from typing import Any

# Import the memory models from the memory system
try:
    from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata, MemoryContent
except ImportError:
    # Fallback if memory models don't exist yet
    MemoryItem = None
    MemoryMetadata = None
    MemoryContent = None

# Import core exceptions
from neuroca.core.enums import MemoryTier
from neuroca.core.exceptions import (
    MemoryNotFoundError,
    MemoryStorageError,
)

# Import MemoryManager
try:
    from neuroca.memory.manager.memory_manager import MemoryManager
except ImportError:
    # Fallback if MemoryManager doesn't exist yet - create an async-compatible mock
    class MemoryManager:  # pragma: no cover - used only when real manager is unavailable
        def __init__(self):
            self._memories: dict[str, dict[str, Any]] = {}
            self._id_counter = 0

        async def initialize(self) -> None:  # noqa: D401 - simple stub
            """Initialize the in-memory manager."""

        async def shutdown(self) -> None:  # noqa: D401 - simple stub
            """Shutdown stub."""

        async def add_memory(
            self,
            content: Any,
            summary: str | None = None,
            importance: float = 0.5,
            metadata: dict[str, Any] | None = None,
            tags: list[str] | None = None,
            embedding: list[float] | None = None,
            initial_tier: str | None = None,
        ) -> str:
            memory_id = f"mock-{self._id_counter}"
            self._id_counter += 1

            tags_dict = {tag: True for tag in tags or []}
            metadata_dict = dict(metadata or {})
            metadata_dict.setdefault("tier", initial_tier or MemoryTier.STM.storage_key)
            metadata_dict.setdefault("importance", importance)
            metadata_dict.setdefault("tags", tags_dict)

            stored = {
                "id": memory_id,
                "content": {"text": content} if isinstance(content, str) else content,
                "summary": summary,
                "metadata": metadata_dict,
            }

            self._memories[memory_id] = stored
            return memory_id

        async def retrieve_memory(self, memory_id: str, tier: str | None = None) -> dict[str, Any] | None:
            return self._memories.get(str(memory_id))

        async def search_memories(
            self,
            query: str | None = None,
            embedding: list[float] | None = None,
            tags: list[str] | None = None,
            metadata_filters: dict[str, Any] | None = None,
            limit: int = 10,
            min_relevance: float = 0.0,
            tiers: list[str] | None = None,
        ) -> list[dict[str, Any]]:
            if embedding:
                logging.getLogger(__name__).warning(
                    "Fallback MemoryManager.search_memories ignores embedding-based ranking."
                )
            results = list(self._memories.values())

            if tiers:
                tier_set = set(tiers)
                results = [m for m in results if m.get("metadata", {}).get("tier") in tier_set]

            if query:
                lowered = query.lower()
                results = [m for m in results if lowered in str(m.get("content", "")).lower()]

            if metadata_filters:
                for key, expected in metadata_filters.items():
                    if key.startswith("metadata."):
                        field = key.split(".", 1)[1]
                        results = [
                            m
                            for m in results
                            if m.get("metadata", {}).get(field) == expected
                        ]

            return results[:limit]

        async def update_memory(
            self,
            memory_id: str,
            content: Any | None = None,
            summary: str | None = None,
            importance: float | None = None,
            metadata: dict[str, Any] | None = None,
            tags: list[str] | None = None,
        ) -> bool:
            memory = self._memories.get(str(memory_id))
            if not memory:
                return False

            if content is not None:
                memory["content"] = {"text": content} if isinstance(content, str) else content
            if summary is not None:
                memory["summary"] = summary
            if importance is not None:
                memory.setdefault("metadata", {})["importance"] = importance
            if metadata:
                memory.setdefault("metadata", {}).update(metadata)
            if tags is not None:
                tag_dict = memory.setdefault("metadata", {}).setdefault("tags", {})
                for tag in tags:
                    tag_dict[tag] = True
            return True

        async def delete_memory(self, memory_id: str, tier: str | None = None) -> bool:
            return self._memories.pop(str(memory_id), None) is not None

        async def transfer_memory(
            self,
            memory_id: str,
            target_tier: str | MemoryTier,
        ) -> dict[str, Any]:
            memory = self._memories.get(str(memory_id))
            if not memory:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")

            resolved = (
                target_tier.storage_key
                if isinstance(target_tier, MemoryTier)
                else str(target_tier)
            )
            memory.setdefault("metadata", {})["tier"] = resolved
            return memory

        async def get_system_stats(self) -> dict[str, Any]:
            stats: dict[str, Any] = {"tiers": {}, "total_memories": len(self._memories)}
            for memory in self._memories.values():
                tier = memory.get("metadata", {}).get("tier", MemoryTier.STM.storage_key)
                tier_stats = stats["tiers"].setdefault(tier, {"total_memories": 0})
                tier_stats["total_memories"] += 1
            return stats

logger = logging.getLogger(__name__)

# Simple base class for models
class BaseModel:
    """Simple base model class."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# Simple User model for API compatibility
class User(BaseModel):
    """Simple User model for API compatibility."""
    
    def __init__(self, **kwargs):
        self.username = kwargs.get('username', '')
        self.email = kwargs.get('email', '')
        self.is_active = kwargs.get('is_active', True)
        self.is_admin = kwargs.get('is_admin', False)
        self.roles = kwargs.get('roles', [])
        super().__init__(**kwargs)

# Response models for API compatibility
class MemoryResponse(BaseModel):
    """Response model for memory operations."""
    
    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.tier = kwargs.get('tier')
        self.content = kwargs.get('content')
        self.metadata = kwargs.get('metadata', {})
        super().__init__(**kwargs)
    
    @classmethod
    def from_orm(cls, memory_item):
        """Create response from memory item."""
        # Handle both object and dictionary formats
        if isinstance(memory_item, dict):
            metadata = memory_item.get("metadata", {})
            tier = (
                memory_item.get("tier")
                or metadata.get("tier")
                or MemoryTier.STM.storage_key
            )
            return cls(
                id=memory_item.get("id", ""),
                user_id=metadata.get("user_id"),
                tier=tier,
                content=memory_item.get("content"),
                metadata=metadata,
            )

        metadata_obj = getattr(memory_item, "metadata", None)
        metadata_dict: dict[str, Any] = {}
        user_id = None
        tier_value = MemoryTier.STM.storage_key

        if metadata_obj is not None:
            if hasattr(metadata_obj, "model_dump"):
                metadata_dict = metadata_obj.model_dump()
            elif hasattr(metadata_obj, "dict"):
                metadata_dict = metadata_obj.dict()
            else:
                metadata_dict = {}

            user_id = metadata_dict.get("user_id")
            tier_value = metadata_dict.get("tier", tier_value)

        content_obj = getattr(memory_item, "content", None)
        if hasattr(content_obj, "model_dump"):
            content_payload = content_obj.model_dump()
        else:
            content_payload = content_obj

        return cls(
            id=getattr(memory_item, "id", ""),
            user_id=user_id,
            tier=tier_value,
            content=content_payload,
            metadata=metadata_dict,
        )

class MemorySearchParams(BaseModel):
    """Search parameters for memory queries."""
    
    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.query = kwargs.get('query', '')
        self.tier = kwargs.get('tier')
        self.tags = kwargs.get('tags', [])
        self.limit = kwargs.get('limit', 50)
        self.offset = kwargs.get('offset', 0)
        super().__init__(**kwargs)

# Memory tier enum-like class
class MemoryService:
    """
    Service class for memory operations, handling business logic and
    acting as a bridge between the API and the MemoryManager.
    """

    def __init__(self):
        """Initializes the MemoryService with a MemoryManager instance."""
        self.memory_manager = MemoryManager()
        self._initialized = False
        logger.info("MemoryService initialized.")
    
    async def _ensure_initialized(self):
        """Ensure the memory manager is initialized."""
        if not self._initialized:
            await self.memory_manager.initialize()
            self._initialized = True

    async def create_memory(self, memory_data: dict) -> MemoryResponse:
        """
        Creates a new memory for a user.
        
        Args:
            memory_data: Dictionary containing memory creation data.
            
        Returns:
            The created memory object.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Creating memory for user {memory_data.get('user_id')}")
        
        # Use the real MemoryManager interface
        memory_id = await self.memory_manager.add_memory(
            content=memory_data.get("content"),
            summary=memory_data.get("summary"),
            importance=memory_data.get("importance", 0.5),
            metadata={'user_id': memory_data.get('user_id')},
            tags=memory_data.get("tags", []),
            initial_tier=self._resolve_initial_tier(memory_data.get("tier")),
        )
        
        # Retrieve the stored memory to return it
        stored_item = await self.memory_manager.retrieve_memory(memory_id)
        return MemoryResponse.from_orm(stored_item)

    async def get_memory(self, memory_id: UUID) -> MemoryResponse:
        """
        Retrieves a specific memory by its ID.
        
        Args:
            memory_id: The ID of the memory to retrieve.
            
        Returns:
            The requested memory object.
            
        Raises:
            MemoryNotFoundError: If the memory is not found.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Retrieving memory {memory_id}")
        memory = await self.memory_manager.retrieve_memory(str(memory_id))
        if not memory:
            raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")
        return MemoryResponse.from_orm(memory)

    async def list_memories(self, search_params: MemorySearchParams) -> list[MemoryResponse]:
        """
        Lists memories based on search parameters.
        
        Args:
            search_params: The parameters to filter and paginate memories.
            
        Returns:
            A list of memories matching the criteria.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Listing memories for user {search_params.user_id}")

        metadata_filters: dict[str, Any] | None = None
        if search_params.user_id is not None:
            metadata_filters = {"metadata.user_id": search_params.user_id}

        tiers: list[str] | None = None
        if search_params.tier:
            try:
                tiers = [MemoryTier.from_string(search_params.tier).storage_key]
            except ValueError:
                tiers = [str(search_params.tier)]

        results = await self.memory_manager.search_memories(
            query=search_params.query,
            limit=search_params.limit,
            metadata_filters=metadata_filters,
            tiers=tiers,
        )
        return [MemoryResponse.from_orm(res) for res in results]

    @staticmethod
    def _resolve_initial_tier(tier: Any) -> str:
        if isinstance(tier, MemoryTier):
            return tier.storage_key
        if tier is None:
            return MemoryTier.STM.storage_key
        try:
            return MemoryTier.from_string(str(tier)).storage_key
        except ValueError:
            logging.getLogger(__name__).warning(
                "Unknown tier %r provided during memory creation. Defaulting to STM.",
                tier,
            )
            return MemoryTier.STM.storage_key

    async def update_memory(self, memory_id: UUID, update_data: dict) -> MemoryResponse:
        """
        Updates an existing memory.
        
        Args:
            memory_id: The ID of the memory to update.
            update_data: A dictionary with the fields to update.
            
        Returns:
            The updated memory object.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Updating memory {memory_id}")

        success = await self.memory_manager.update_memory(
            str(memory_id),
            content=update_data.get("content"),
            summary=update_data.get("summary"),
            importance=update_data.get("importance"),
            metadata=update_data.get("metadata"),
            tags=update_data.get("tags"),
        )
        if not success:
            raise MemoryNotFoundError(f"Memory with ID {memory_id} not found for update.")

        updated = await self.memory_manager.retrieve_memory(str(memory_id))
        if not updated:
            raise MemoryNotFoundError(f"Memory with ID {memory_id} not found after update.")

        return MemoryResponse.from_orm(updated)

    async def delete_memory(self, memory_id: UUID) -> None:
        """
        Deletes a memory by its ID.

        Args:
            memory_id: The ID of the memory to delete.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Deleting memory {memory_id}")
        deleted = await self.memory_manager.delete_memory(str(memory_id))
        if not deleted:
            raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")
        logger.info(f"Memory {memory_id} deleted from service.")

    async def transfer_memory(self, memory_id: UUID, target_tier: MemoryTier | str) -> MemoryResponse:
        """
        Transfers a memory to a different tier.
        
        Args:
            memory_id: The ID of the memory to transfer.
            target_tier: The destination tier.
            
        Returns:
            The transferred memory object with its updated tier.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Transferring memory {memory_id} to {target_tier}")

        try:
            resolved_tier = (
                target_tier
                if isinstance(target_tier, MemoryTier)
                else MemoryTier.from_string(str(target_tier))
            )
        except ValueError as exc:
            raise MemoryStorageError(f"Invalid target tier: {target_tier}") from exc

        transferred_memory = await self.memory_manager.transfer_memory(
            str(memory_id),
            resolved_tier,
        )
        return MemoryResponse.from_orm(transferred_memory)

    async def consolidate_memories(self, memory_ids: list[UUID], user_id: UUID, summary: str, tags: list[str]) -> list[MemoryResponse]:
        """
        Consolidates multiple memories into a new semantic memory.
        
        Args:
            memory_ids: A list of memory IDs to consolidate.
            user_id: The ID of the user performing the consolidation.
            summary: A summary for the new consolidated memory.
            tags: Tags for the new memory.
            
        Returns:
            A list containing the new consolidated memory and the original memories.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Consolidating memories for user {user_id}")

        metadata = {
            "user_id": str(user_id),
            "consolidated_from": [str(mid) for mid in memory_ids],
        }
        new_memory_content = f"Consolidated summary: {summary}"
        new_memory_id = await self.memory_manager.add_memory(
            content=new_memory_content,
            summary=summary,
            metadata=metadata,
            tags=tags,
            initial_tier=MemoryTier.SEMANTIC.storage_key,
        )

        consolidated = await self.memory_manager.retrieve_memory(new_memory_id)

        original_memories: list[Any] = []
        for mid in memory_ids:
            existing = await self.memory_manager.retrieve_memory(str(mid))
            if existing:
                original_memories.append(existing)

        responses: list[MemoryResponse] = []
        if consolidated:
            responses.append(MemoryResponse.from_orm(consolidated))
        responses.extend(MemoryResponse.from_orm(mem) for mem in original_memories)
        return responses

    async def get_memory_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Retrieves memory statistics for a specific user.
        
        Args:
            user_id: The ID of the user.
            
        Returns:
            A dictionary of memory statistics.
        """
        await self._ensure_initialized()
        logger.debug(f"Service: Getting memory stats for user {user_id}")
        return await self.memory_manager.get_system_stats()

    async def health_check(self) -> dict[str, Any]:
        """
        Performs a health check on the memory system.
        
        Returns:
            A dictionary with the health status of various components.
        """
        logger.debug("Service: Performing health check.")
        # This can be expanded to check database connections, etc.
        return {"status": "healthy", "memory_manager_status": "ok"}
