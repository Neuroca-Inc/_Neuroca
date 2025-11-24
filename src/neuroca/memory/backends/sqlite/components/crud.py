"""
SQLite CRUD Operations Component

This module provides a class for handling CRUD (Create, Read, Update, Delete)
operations on memory items in the SQLite database.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata

logger = logging.getLogger(__name__)


class SQLiteCRUD:
    """
    Handles CRUD operations for memory items in SQLite database.
    
    This class provides methods for storing, retrieving, updating, and
    deleting memory items in the SQLite database.
    """
    
    def __init__(self, connection_manager):
        """
        Initialize the CRUD operations handler.
        
        Args:
            connection_manager: SQLiteConnection instance to manage database connections
        """
        self.connection_manager = connection_manager

    def _serialise_content(self, content: Any) -> str:
        """Return a database-friendly representation of ``content``."""

        if isinstance(content, MemoryContent):
            return json.dumps(content.model_dump(exclude_none=True))
        if isinstance(content, dict):
            return json.dumps(content)
        if isinstance(content, str):
            return content
        if content is None:
            return ""
        try:
            return json.dumps(content)
        except TypeError:
            return str(content)

    def _serialise_metadata(self, metadata: Any) -> Tuple[Dict[str, Any], List[str]]:
        """Normalise ``metadata`` into a JSON payload and flattened tag list."""

        if metadata is None:
            return {}, []

        if isinstance(metadata, MemoryMetadata):
            metadata_dict: Dict[str, Any] = metadata.model_dump(exclude_none=True)
        elif isinstance(metadata, dict):
            metadata_dict = dict(metadata)
        else:
            return {}, []

        tags_field = metadata_dict.get("tags")
        if isinstance(tags_field, dict):
            tag_list = [str(tag) for tag, enabled in tags_field.items() if enabled]
        elif isinstance(tags_field, list):
            tag_list = [str(tag) for tag in tags_field]
        elif tags_field is None:
            tag_list = []
        else:
            tag_list = [str(tags_field)]

        metadata_dict["tags"] = tag_list
        metadata_dict = self._make_json_safe(metadata_dict)
        return metadata_dict, tag_list

    def _deserialise_content(self, stored_value: Any) -> Any:
        """Convert stored SQLite content back into the MemoryContent payload."""

        if stored_value is None:
            return {}
        if isinstance(stored_value, (dict, list)):
            return stored_value
        if isinstance(stored_value, str):
            try:
                return json.loads(stored_value)
            except json.JSONDecodeError:
                return stored_value
        return stored_value

    def _make_json_safe(self, value: Any) -> Any:
        """Recursively convert metadata payloads into JSON-serialisable structures."""

        if isinstance(value, dict):
            return {key: self._make_json_safe(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._make_json_safe(item) for item in value]
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return value

    def _now_iso(self) -> str:
        """Return the current UTC timestamp in ISO 8601 format."""

        return datetime.now(timezone.utc).isoformat()
    
    def store(self, memory_item: MemoryItem) -> str:
        """
        Store a memory item in the database.
        
        Args:
            memory_item: The memory item to store
            
        Returns:
            str: The ID of the stored memory
        """
        memory_id = memory_item.id or self._generate_id()
        
        # Ensure the memory item has an ID
        if not memory_item.id:
            memory_item.id = memory_id
        
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        with conn:
            # Begin transaction
            conn.execute("BEGIN")
            
            try:
                # Store the memory item using the helper method
                self._store_memory_without_transaction(memory_item)
                
                # Commit the transaction
                conn.execute("COMMIT")
                
                logger.debug(f"Stored memory with ID: {memory_id}")
                return memory_id
            except Exception as e:
                # Rollback the transaction on error
                conn.execute("ROLLBACK")
                logger.error(f"Failed to store memory: {str(e)}")
                raise
    
    def _store_memory_without_transaction(self, memory_item: MemoryItem) -> str:
        """
        Store a memory item without transaction handling.
        
        This method is used by both store() and batch_store() to avoid
        duplicating the core storage logic.
        
        Args:
            memory_item: The memory item to store
            
        Returns:
            str: The ID of the stored memory
        """
        memory_id = memory_item.id
        
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        # Store the memory item
        serialised_content = self._serialise_content(memory_item.content)

        conn.execute(
            """
            INSERT INTO memory_items (id, content, summary, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                memory_id,
                serialised_content,
                memory_item.summary,
                self._now_iso()
            )
        )

        # Store metadata if it exists
        if memory_item.metadata:
            self._store_metadata(memory_id, memory_item.metadata)
        
        return memory_id
    
    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item from the database by ID.
        
        Args:
            memory_id: ID of the memory to retrieve
            
        Returns:
            Optional[MemoryItem]: The memory item if found, None otherwise
        """
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        # Get the memory item
        memory_row = conn.execute(
            """
            SELECT id, content, summary, created_at, last_accessed, last_modified
            FROM memory_items
            WHERE id = ?
            """,
            (memory_id,)
        ).fetchone()
        
        if not memory_row:
            logger.debug(f"Memory with ID {memory_id} not found")
            return None
        
        # Update access time
        conn.execute(
            """
            UPDATE memory_items
            SET last_accessed = ?
            WHERE id = ?
            """,
            (self._now_iso(), memory_id)
        )
        
        # Get metadata
        metadata = self._retrieve_metadata(memory_id)
        
        # Create the memory item
        content_payload = self._deserialise_content(memory_row[1])

        memory_item = MemoryItem(
            id=memory_row[0],
            content=content_payload,
            summary=memory_row[2],
            metadata=metadata
        )
        
        logger.debug(f"Retrieved memory with ID: {memory_id}")
        return memory_item
    
    def update(self, memory_item: MemoryItem) -> bool:
        """
        Update an existing memory item in the database.
        
        Args:
            memory_item: Memory item to update
            
        Returns:
            bool: True if update was successful, False if memory not found
        """
        memory_id = memory_item.id
        
        if not memory_id:
            logger.error("Cannot update memory without ID")
            return False
        
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        with conn:
            # Begin transaction
            conn.execute("BEGIN")
            
            try:
                # Check if memory exists
                exists = conn.execute(
                    "SELECT 1 FROM memory_items WHERE id = ?",
                    (memory_id,)
                ).fetchone()
                
                if not exists:
                    conn.execute("ROLLBACK")
                    logger.warning(f"Memory with ID {memory_id} not found for update")
                    return False
                
                # Update the memory item using the helper method
                success = self._update_memory_without_transaction(memory_item)
                
                # Commit the transaction
                conn.execute("COMMIT")
                
                logger.debug(f"Updated memory with ID: {memory_id}")
                return success
            except Exception as e:
                # Rollback the transaction on error
                conn.execute("ROLLBACK")
                logger.error(f"Failed to update memory {memory_id}: {str(e)}")
                raise
    
    def _update_memory_without_transaction(self, memory_item: MemoryItem) -> bool:
        """
        Update a memory item without transaction handling.
        
        This method is used by both update() and batch_update() to avoid
        duplicating the core update logic.
        
        Args:
            memory_item: Memory item to update
            
        Returns:
            bool: True if update was successful
        """
        memory_id = memory_item.id
        
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        # Update the memory item
        serialised_content = self._serialise_content(memory_item.content)

        conn.execute(
            """
            UPDATE memory_items
            SET content = ?, summary = ?, last_modified = ?
            WHERE id = ?
            """,
            (
                serialised_content,
                memory_item.summary,
                self._now_iso(),
                memory_id
            )
        )

        # Update metadata if it exists
        if memory_item.metadata:
            self._update_metadata(memory_id, memory_item.metadata)
        
        return True
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory item from the database.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            bool: True if deletion was successful, False if memory not found
        """
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        with conn:
            # Check if memory exists
            exists = conn.execute(
                "SELECT 1 FROM memory_items WHERE id = ?",
                (memory_id,)
            ).fetchone()
            
            if not exists:
                logger.warning(f"Memory with ID {memory_id} not found for deletion")
                return False
            
            # Delete the memory item
            # Foreign key constraints will handle related deletions
            conn.execute(
                "DELETE FROM memory_items WHERE id = ?",
                (memory_id,)
            )
            
            logger.debug(f"Deleted memory with ID: {memory_id}")
            return True
    
    def _store_metadata(self, memory_id: str, metadata: Any) -> None:
        """
        Store metadata for a memory item.

        Args:
            memory_id: ID of the memory item
            metadata: Metadata to store
        """
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()

        metadata_dict, tag_list = self._serialise_metadata(metadata)
        if not metadata_dict:
            return

        metadata_json = json.dumps(metadata_dict)

        conn.execute(
            """
            INSERT INTO memory_metadata (memory_id, metadata_json)
            VALUES (?, ?)
            """,
            (memory_id, metadata_json)
        )

        # Store tags if they exist
        if tag_list:
            for tag in tag_list:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO memory_tags (memory_id, tag)
                    VALUES (?, ?)
                    """,
                    (memory_id, tag)
                )
    
    def _update_metadata(self, memory_id: str, metadata: Any) -> None:
        """
        Update metadata for a memory item.

        Args:
            memory_id: ID of the memory item
            metadata: Updated metadata
        """
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()

        metadata_dict, tag_list = self._serialise_metadata(metadata)
        if not metadata_dict:
            conn.execute(
                "DELETE FROM memory_metadata WHERE memory_id = ?",
                (memory_id,),
            )
            conn.execute(
                "DELETE FROM memory_tags WHERE memory_id = ?",
                (memory_id,),
            )
            return

        metadata_json = json.dumps(metadata_dict)

        # Check if metadata exists
        metadata_exists = conn.execute(
            "SELECT 1 FROM memory_metadata WHERE memory_id = ?",
            (memory_id,)
        ).fetchone()
        
        if metadata_exists:
            conn.execute(
                """
                UPDATE memory_metadata
                SET metadata_json = ?
                WHERE memory_id = ?
                """,
                (metadata_json, memory_id)
            )
        else:
            conn.execute(
                """
                INSERT INTO memory_metadata (memory_id, metadata_json)
                VALUES (?, ?)
                """,
                (memory_id, metadata_json)
            )
        
        # Update tags
        if tag_list:
            # Delete existing tags
            conn.execute(
                "DELETE FROM memory_tags WHERE memory_id = ?",
                (memory_id,)
            )

            # Add new tags
            for tag in tag_list:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO memory_tags (memory_id, tag)
                    VALUES (?, ?)
                    """,
                    (memory_id, tag)
                )

    def _retrieve_metadata(self, memory_id: str) -> Dict:
        """
        Retrieve metadata for a memory item.
        
        Args:
            memory_id: ID of the memory item
            
        Returns:
            Dict: Memory metadata or empty dict if not found
        """
        # Get a connection for the current thread
        conn = self.connection_manager.get_connection()
        
        metadata_row = conn.execute(
            """
            SELECT metadata_json
            FROM memory_metadata
            WHERE memory_id = ?
            """,
            (memory_id,)
        ).fetchone()
        
        if metadata_row:
            metadata_dict = json.loads(metadata_row[0])
            tags_field = metadata_dict.get("tags")
            if isinstance(tags_field, list):
                metadata_dict["tags"] = {str(tag): True for tag in tags_field}
            return metadata_dict

        return {}
    
    def _generate_id(self) -> str:
        """
        Generate a unique ID for a memory item.
        
        Returns:
            str: A unique UUID
        """
        return str(uuid.uuid4())
