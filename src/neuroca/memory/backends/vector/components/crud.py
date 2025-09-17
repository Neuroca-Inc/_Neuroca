"""
Vector CRUD Operations Component

This module provides the VectorCRUD class for performing CRUD operations on memory items
in the vector database, handling conversion between MemoryItem and VectorEntry objects.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends.vector.components.index import VectorIndex
from neuroca.memory.backends.vector.components.models import VectorEntry
from neuroca.memory.backends.vector.components.storage import VectorStorage
from neuroca.memory.exceptions import StorageOperationError
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata, MemoryStatus

logger = logging.getLogger(__name__)


class VectorCRUD:
    """
    Handles CRUD operations for memory items in the vector database.
    
    This class provides methods for creating, reading, updating, and
    deleting memory items in a vector database, handling the conversion
    between MemoryItem objects and VectorEntry objects.
    """
    
    def __init__(
        self,
        index: VectorIndex,
        storage: VectorStorage,
    ):
        """
        Initialize the vector CRUD operations component.
        
        Args:
            index: Vector index component
            storage: Vector storage component
        """
        self.index = index
        self.storage = storage
        self.include_full_payload_and_tier_in_metadata = True
    
    async def create(self, memory_item: MemoryItem) -> str:
        """
        Store a memory item with its embedding in the vector database.
        
        Args:
            memory_item: The memory item to store
            
        Returns:
            str: The ID of the stored memory
            
        Raises:
            StorageOperationError: If the memory cannot be stored
        """
        try:
            memory_id = memory_item.id
            
            # Check if memory has embedding
            if not memory_item.embedding:
                raise StorageOperationError(f"Memory item {memory_id} does not have an embedding")
            
            # Convert MemoryItem to VectorEntry
            vector_entry = self._memory_to_vector_entry(memory_item)
            
            # Store in index
            if memory_id in self.index.entries:
                self.index.update(vector_entry)
            else:
                self.index.add(vector_entry)
            
            # Store additional metadata
            metadata = memory_item.metadata or None
            now_iso = datetime.now().isoformat()
            metadata_dict: Dict[str, Any] = {
                "summary": memory_item.summary or "No summary available",
                "status": metadata.status.value if metadata and metadata.status else "active",
                "created_at": metadata.created_at.isoformat() if metadata and metadata.created_at else now_iso,
                "last_accessed": now_iso,
                "access_count": 0,
                "tags": metadata.tags if metadata else {},
                "importance": metadata.importance if metadata else 0.5,
            }
            if self.include_full_payload_and_tier_in_metadata:
                metadata_dict["memory"] = memory_item.model_dump(mode="json")
                if metadata and metadata.tier:
                    metadata_dict["tier"] = metadata.tier
            elif metadata and metadata.tier:
                metadata_dict["tier"] = metadata.tier

            self.storage.set_memory_metadata(memory_id, metadata_dict)
            
            # Save index to disk if path is provided
            await self.storage.save()
            
            logger.debug(f"Stored memory with ID {memory_id} in vector database")
            return memory_id
            
        except Exception as e:
            error_msg = f"Failed to store memory in vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def read(self, memory_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item by ID from the vector database.
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            Optional[MemoryItem]: The memory item if found, None otherwise
            
        Raises:
            StorageOperationError: If there's an error retrieving the memory
        """
        try:
            # Check if memory exists in index
            vector_entry = self.index.get(memory_id)
            if not vector_entry:
                logger.debug(f"Memory with ID {memory_id} not found in vector database")
                return None
            
            # Get metadata
            metadata_dict = self.storage.get_memory_metadata(memory_id)
            
            # Convert VectorEntry to MemoryItem
            memory_item = self._vector_entry_to_memory(vector_entry, metadata_dict)

            # Update access stats and persist full memory payload
            now_iso = datetime.now().isoformat()
            metadata_dict["last_accessed"] = now_iso
            metadata_dict["access_count"] = metadata_dict.get("access_count", 0) + 1
            if self.include_full_payload_and_tier_in_metadata:
                metadata_dict["memory"] = memory_item.model_dump(mode="json")
            metadata_dict["importance"] = memory_item.metadata.importance
            if memory_item.metadata.tier:
                metadata_dict["tier"] = memory_item.metadata.tier
            self.storage.set_memory_metadata(memory_id, metadata_dict)

            # Save updated metadata
            await self.storage.save()
            
            logger.debug(f"Retrieved memory with ID {memory_id} from vector database")
            return memory_item
            
        except Exception as e:
            error_msg = f"Failed to retrieve memory with ID {memory_id} from vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def update(self, memory_item: MemoryItem) -> bool:
        """
        Update an existing memory item in the vector database.
        
        Args:
            memory_item: The memory item to update
            
        Returns:
            bool: True if the update was successful, False otherwise
            
        Raises:
            StorageOperationError: If there's an error updating the memory
        """
        try:
            memory_id = memory_item.id
            
            # Check if memory exists
            if memory_id not in self.index.entries:
                logger.warning(f"Memory with ID {memory_id} not found for update in vector database")
                return False
            
            # Just use create for simplicity (it handles updates)
            await self.create(memory_item)
            logger.debug(f"Updated memory with ID {memory_id} in vector database")
            return True
            
        except Exception as e:
            error_msg = f"Failed to update memory with ID {memory_item.id} in vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory item from the vector database.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            bool: True if the deletion was successful, False otherwise
            
        Raises:
            StorageOperationError: If there's an error deleting the memory
        """
        try:
            # Check if memory exists
            if memory_id not in self.index.entries:
                logger.warning(f"Memory with ID {memory_id} not found for deletion in vector database")
                return False
            
            # Delete from index
            self.index.delete(memory_id)
            
            # Delete metadata
            self.storage.delete_memory_metadata(memory_id)
            
            # Save changes
            await self.storage.save()
            
            logger.debug(f"Deleted memory with ID {memory_id} from vector database")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete memory with ID {memory_id} from vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def exists(self, memory_id: str) -> bool:
        """
        Check if a memory item exists in the vector database.
        
        Args:
            memory_id: The ID of the memory to check
            
        Returns:
            bool: True if the memory exists, False otherwise
            
        Raises:
            StorageOperationError: If there's an error checking the memory
        """
        try:
            return memory_id in self.index.entries
            
        except Exception as e:
            error_msg = f"Failed to check if memory with ID {memory_id} exists in vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def batch_create(self, memory_items: List[MemoryItem]) -> List[str]:
        """
        Store multiple memory items in the vector database in a batch.
        
        Args:
            memory_items: List of memory items to store
            
        Returns:
            List[str]: List of stored memory IDs
            
        Raises:
            StorageOperationError: If there's an error storing the memories
        """
        try:
            if not memory_items:
                return []
            
            memory_ids = []
            vector_entries = []
            
            for memory_item in memory_items:
                memory_id = memory_item.id
                memory_ids.append(memory_id)
                
                # Check if memory has embedding
                if not memory_item.embedding:
                    raise StorageOperationError(f"Memory item {memory_id} does not have an embedding")
                
                # Convert MemoryItem to VectorEntry
                vector_entry = self._memory_to_vector_entry(memory_item)
                vector_entries.append(vector_entry)
                
                # Store additional metadata
                metadata = memory_item.metadata or None
                now_iso = datetime.now().isoformat()
                metadata_dict: Dict[str, Any] = {
                    "summary": memory_item.summary or "No summary available",
                    "status": metadata.status.value if metadata and metadata.status else "active",
                    "created_at": metadata.created_at.isoformat() if metadata and metadata.created_at else now_iso,
                    "last_accessed": now_iso,
                    "access_count": 0,
                    "tags": metadata.tags if metadata else {},
                    "importance": metadata.importance if metadata else 0.5,
                }
                if self.include_full_payload_and_tier_in_metadata:
                    metadata_dict["memory"] = memory_item.model_dump(mode="json")
                    if metadata and metadata.tier:
                        metadata_dict["tier"] = metadata.tier
                elif metadata and metadata.tier:
                    metadata_dict["tier"] = metadata.tier

                self.storage.set_memory_metadata(memory_id, metadata_dict)
            
            # Store in index
            self.index.batch_add(vector_entries)
            
            # Save index to disk if path is provided
            await self.storage.save()
            
            logger.debug(f"Batch stored {len(memory_ids)} memories in vector database")
            return memory_ids
            
        except Exception as e:
            error_msg = f"Failed to batch store memories in vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def batch_read(self, memory_ids: List[str]) -> Dict[str, Optional[MemoryItem]]:
        """
        Retrieve multiple memory items from the vector database in a batch.
        
        Args:
            memory_ids: List of memory IDs to retrieve
            
        Returns:
            Dict[str, Optional[MemoryItem]]: Dictionary mapping memory IDs to their items
            
        Raises:
            StorageOperationError: If there's an error retrieving the memories
        """
        try:
            if not memory_ids:
                return {}
            
            result = {}
            
            # Get vector entries
            entries = self.index.get_entries_by_ids(memory_ids)
            
            # Get metadata
            metadata_by_id = {}
            need_save = False
            
            for memory_id in memory_ids:
                if memory_id in entries and entries[memory_id]:
                    # Get metadata
                    metadata_dict = self.storage.get_memory_metadata(memory_id)

                    # Update access stats
                    now_iso = datetime.now().isoformat()
                    metadata_dict["last_accessed"] = now_iso
                    metadata_dict["access_count"] = metadata_dict.get("access_count", 0) + 1
                    metadata_by_id[memory_id] = metadata_dict
            
            # Convert entries to memory items
            for memory_id in memory_ids:
                entry = entries.get(memory_id)
                if entry:
                    metadata_dict = metadata_by_id.get(memory_id, {})
                    memory_item = self._vector_entry_to_memory(entry, metadata_dict)
                    if self.include_full_payload_and_tier_in_metadata:
                        metadata_dict["memory"] = memory_item.model_dump(mode="json")
                    metadata_dict["importance"] = memory_item.metadata.importance
                    if memory_item.metadata.tier:
                        metadata_dict["tier"] = memory_item.metadata.tier
                    self.storage.set_memory_metadata(memory_id, metadata_dict)
                    need_save = True
                    result[memory_id] = memory_item
                else:
                    result[memory_id] = None
            
            # Save updated metadata
            if need_save:
                await self.storage.save()
            
            logger.debug(
                f"Batch retrieved {sum(bool(item) for item in result.values())} out of {len(memory_ids)} memories from vector database"
            )
            return result
            
        except Exception as e:
            error_msg = f"Failed to batch retrieve memories from vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e
    
    async def batch_delete(self, memory_ids: List[str]) -> Dict[str, bool]:
        """
        Delete multiple memory items from the vector database in a batch.
        
        Args:
            memory_ids: List of memory IDs to delete
            
        Returns:
            Dict[str, bool]: Dictionary mapping memory IDs to deletion success
            
        Raises:
            StorageOperationError: If there's an error deleting the memories
        """
        try:
            if not memory_ids:
                return {}
            
            # Delete from index
            results = self.index.batch_delete(memory_ids)
            
            # Delete metadata
            for memory_id in memory_ids:
                if results.get(memory_id, False):
                    self.storage.delete_memory_metadata(memory_id)
            
            # Save changes
            await self.storage.save()
            
            logger.debug(f"Batch deleted {sum(1 for success in results.values() if success)} out of {len(memory_ids)} memories from vector database")
            return results
            
        except Exception as e:
            error_msg = f"Failed to batch delete memories from vector database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageOperationError(error_msg) from e

    def vector_entry_to_memory(
        self,
        vector_entry: VectorEntry,
        metadata_dict: Dict[str, Any],
    ) -> MemoryItem:
        """Public wrapper for converting a stored vector entry to a memory item."""
        return self._vector_entry_to_memory(vector_entry, metadata_dict)

    def _memory_to_vector_entry(self, memory_item: MemoryItem) -> VectorEntry:
        """
        Convert a MemoryItem to a VectorEntry.
        
        Args:
            memory_item: The memory item to convert
            
        Returns:
            VectorEntry: The converted vector entry
        """
        metadata = memory_item.metadata or None
        tag_map = metadata.tags if metadata and isinstance(metadata.tags, dict) else {}
        serialized_memory = memory_item.model_dump(mode="json")

        return VectorEntry(
            id=memory_item.id,
            vector=memory_item.embedding,
            metadata={
                "summary": memory_item.summary or serialized_memory.get("summary") or "",
                "status": metadata.status.value if metadata and metadata.status else "active",
                "created_at": metadata.created_at.isoformat() if metadata and metadata.created_at else datetime.now().isoformat(),
                "tags": list(tag_map.keys()) if tag_map else metadata.tags if metadata else [],
                "importance": metadata.importance if metadata else 0.5,
                "tier": metadata.tier if metadata and metadata.tier else None,
                "memory": serialized_memory,
            },
        )
    
    def _vector_entry_to_memory(
        self, 
        vector_entry: VectorEntry, 
        metadata_dict: Dict[str, Any]
    ) -> MemoryItem:
        """
        Convert a VectorEntry to a MemoryItem.
        
        Args:
            vector_entry: The vector entry to convert
            metadata_dict: Additional metadata from storage
            
        Returns:
            MemoryItem: The converted memory item
        """
        memory_payload = metadata_dict.get("memory") or vector_entry.metadata.get("memory")

        if memory_payload:
            memory_item = MemoryItem.model_validate(memory_payload)
        else:
            metadata = MemoryMetadata(
                status=MemoryStatus(vector_entry.metadata.get("status", "active")),
                created_at=datetime.fromisoformat(
                    vector_entry.metadata.get("created_at", datetime.now().isoformat())
                ),
                tags=vector_entry.metadata.get("tags", {}),
                importance=vector_entry.metadata.get("importance", 0.5),
            )

            memory_item = MemoryItem(
                id=vector_entry.id,
                content={},
                summary=vector_entry.metadata.get("summary", ""),
                embedding=vector_entry.vector,
                metadata=metadata,
            )

        memory_item.metadata.last_accessed = datetime.fromisoformat(
            metadata_dict.get("last_accessed", datetime.now().isoformat())
        )
        memory_item.metadata.access_count = metadata_dict.get("access_count", 0)

        tier_value = metadata_dict.get("tier") or vector_entry.metadata.get("tier")
        if tier_value is not None:
            if isinstance(tier_value, MemoryTier):
                resolved_tier = tier_value.storage_key
            else:
                try:
                    resolved_tier = MemoryTier.from_string(str(tier_value)).storage_key
                except ValueError:
                    resolved_tier = str(tier_value)
            memory_item.metadata.tier = resolved_tier

        return memory_item
