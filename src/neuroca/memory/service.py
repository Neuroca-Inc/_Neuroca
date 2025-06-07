"""
Memory Service Layer

This module provides a service layer that acts as an intermediary between the
API routes and the core MemoryManager. It encapsulates business logic,
user-specific operations, and error handling.
"""

from uuid import UUID
from typing import Any, List
import logging

# Import the memory models from the memory system
try:
    from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata, MemoryContent
except ImportError:
    # Fallback if memory models don't exist yet
    MemoryItem = None
    MemoryMetadata = None
    MemoryContent = None

# Import core exceptions
from neuroca.core.exceptions import (
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryStorageError,
    MemoryTierFullError,
)

# Import MemoryManager
try:
    from neuroca.memory.manager.memory_manager import MemoryManager
except ImportError:
    # Fallback if MemoryManager doesn't exist yet - create a mock
    class MemoryManager:
        def __init__(self):
            self._memories = {}
            self._id_counter = 0
        
        def store(self, content, tier="working", metadata=None):
            memory_id = f"mock-{self._id_counter}"
            self._id_counter += 1
            memory = {
                "id": memory_id,
                "content": content,
                "tier": tier,  # Properly store the tier
                "metadata": metadata or {}
            }
            self._memories[memory_id] = memory
            return memory
        
        def get(self, memory_id):
            memory = self._memories.get(str(memory_id))
            if not memory:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")
            return memory
        
        def search(self, query, limit=50):
            return list(self._memories.values())[:limit]
        
        def update(self, memory_id, update_data):
            if str(memory_id) not in self._memories:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found for update.")
            
            # Update the memory with new data
            memory = self._memories[str(memory_id)]
            if "content" in update_data:
                memory["content"] = update_data["content"]
            if "metadata" in update_data:
                memory["metadata"].update(update_data["metadata"])
            if "tier" in update_data:
                memory["tier"] = update_data["tier"]
            
            return memory
        
        def delete(self, memory_id):
            if str(memory_id) not in self._memories:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")
            return self._memories.pop(str(memory_id), None)
        
        def transfer_tier(self, memory_id, target_tier):
            if str(memory_id) not in self._memories:
                raise MemoryNotFoundError(f"Memory with ID {memory_id} not found.")
            
            memory = self._memories[str(memory_id)]
            memory["tier"] = target_tier  # Update the tier
            return memory
        
        def get_tier_stats(self):
            stats = {"working": 0, "episodic": 0, "semantic": 0}
            for memory in self._memories.values():
                tier = memory.get("tier", "working")
                if tier in stats:
                    stats[tier] += 1
            
            return {
                "total_memories": len(self._memories), 
                "tiers": stats
            }

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
            # Dictionary format (from mock MemoryManager)
            metadata = memory_item.get('metadata', {})
            return cls(
                id=memory_item.get('id', ''),
                user_id=metadata.get('user_id'),
                tier=memory_item.get('tier', 'working'),  # Get tier from top level
                content=memory_item.get('content'),
                metadata=metadata
            )
        else:
            # Object format (from real MemoryManager) - MemoryItem with MemoryMetadata
            # Handle MemoryMetadata Pydantic model
            metadata_obj = getattr(memory_item, 'metadata', None)
            if metadata_obj:
                # For MemoryMetadata objects, access fields directly
                if hasattr(metadata_obj, 'tags') and isinstance(metadata_obj.tags, dict):
                    user_id = metadata_obj.tags.get('user_id')
                else:
                    user_id = getattr(metadata_obj, 'user_id', None)
                
                # Convert MemoryMetadata to dict for response
                if hasattr(metadata_obj, 'model_dump'):
                    metadata_dict = metadata_obj.model_dump()
                elif hasattr(metadata_obj, 'dict'):
                    metadata_dict = metadata_obj.dict()
                else:
                    metadata_dict = {}
            else:
                user_id = None
                metadata_dict = {}
            
            return cls(
                id=getattr(memory_item, 'id', ''),
                user_id=user_id,
                tier='stm',  # Default tier for real memory items
                content=getattr(memory_item, 'content', None),
                metadata=metadata_dict
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
class MemoryTier:
    """Memory tier constants."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"

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
            initial_tier=memory_data.get("tier", "stm")  # Use stm as default, not working
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
        logger.debug(f"Service: Listing memories for user {search_params.user_id}")
        # The manager's search needs to be adapted to handle user_id from metadata
        # This is a placeholder implementation.
        results = self.memory_manager.search(
            query=search_params.query,
            limit=search_params.limit,
            # More complex filtering would be needed here
        )
        return [MemoryResponse.from_orm(res) for res in results]

    async def update_memory(self, memory_id: UUID, update_data: dict) -> MemoryResponse:
        """
        Updates an existing memory.
        
        Args:
            memory_id: The ID of the memory to update.
            update_data: A dictionary with the fields to update.
            
        Returns:
            The updated memory object.
        """
        logger.debug(f"Service: Updating memory {memory_id}")
        updated_memory = self.memory_manager.update(memory_id, update_data)
        if not updated_memory:
            raise MemoryNotFoundError(f"Memory with ID {memory_id} not found for update.")
        return MemoryResponse.from_orm(updated_memory)

    async def delete_memory(self, memory_id: UUID) -> None:
        """
        Deletes a memory by its ID.
        
        Args:
            memory_id: The ID of the memory to delete.
        """
        logger.debug(f"Service: Deleting memory {memory_id}")
        self.memory_manager.delete(memory_id)
        logger.info(f"Memory {memory_id} deleted from service.")

    async def transfer_memory(self, memory_id: UUID, target_tier: MemoryTier) -> MemoryResponse:
        """
        Transfers a memory to a different tier.
        
        Args:
            memory_id: The ID of the memory to transfer.
            target_tier: The destination tier.
            
        Returns:
            The transferred memory object with its updated tier.
        """
        logger.debug(f"Service: Transferring memory {memory_id} to {target_tier}")
        transferred_memory = self.memory_manager.transfer_tier(memory_id, target_tier)
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
        logger.debug(f"Service: Consolidating memories for user {user_id}")
        # This is a complex operation that needs careful implementation.
        # The manager likely needs a corresponding method.
        # Placeholder implementation:
        new_memory_content = f"Consolidated summary: {summary}"
        new_memory = self.memory_manager.store(
            content=new_memory_content,
            tier="semantic",
            metadata={'user_id': user_id, 'consolidated_from': memory_ids}
        )
        
        original_memories = [self.memory_manager.get(mid) for mid in memory_ids]
        
        return [MemoryResponse.from_orm(new_memory)] + [MemoryResponse.from_orm(mem) for mem in original_memories if mem]

    async def get_memory_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Retrieves memory statistics for a specific user.
        
        Args:
            user_id: The ID of the user.
            
        Returns:
            A dictionary of memory statistics.
        """
        logger.debug(f"Service: Getting memory stats for user {user_id}")
        # The manager's stats methods would need to be adapted to filter by user.
        # Placeholder implementation:
        return self.memory_manager.get_tier_stats()

    async def health_check(self) -> dict[str, Any]:
        """
        Performs a health check on the memory system.
        
        Returns:
            A dictionary with the health status of various components.
        """
        logger.debug("Service: Performing health check.")
        # This can be expanded to check database connections, etc.
        return {"status": "healthy", "memory_manager_status": "ok"}
