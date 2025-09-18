"""
Memory Item Models

This module defines the core data models for memory items in the Neuroca memory system.
These models represent the structure of memory items across all tiers and are used
for data validation, serialization, and documentation.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class MemoryStatus(str, Enum):
    """Status of a memory item."""
    
    ACTIVE = "active"  # Normal status, actively used
    ARCHIVED = "archived"  # No longer active but preserved
    CONSOLIDATED = "consolidated"  # Moved to a higher tier
    FORGOTTEN = "forgotten"  # Marked for deletion but not yet removed
    DECAYING = "decaying"  # In the process of natural decay


class MemoryContent(BaseModel):
    """
    Content of a memory item.
    
    This can be structured (with separate text, json_data, etc. fields)
    or unstructured (using the raw_content field).
    """
    
    # Structured content fields
    text: Optional[str] = None
    summary: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    
    # Unstructured content (used when content doesn't fit structured fields)
    raw_content: Optional[Any] = None
    
    # Content properties
    content_type: Optional[str] = None
    language: Optional[str] = "en"
    
    @field_validator("raw_content", mode="before")
    def validate_raw_content(cls, v):
        """Ensure raw_content is JSON serializable."""
        if v is None:
            return v
        
        # Check if raw_content is a primitive type or dict/list
        if isinstance(v, (str, int, float, bool, dict, list)):
            return v
        
        # Otherwise convert to string
        return str(v)
    
    @property
    def primary_text(self) -> str:
        """Get the primary text representation of this content."""
        if self.text:
            return self.text
        elif self.summary:
            return self.summary
        elif self.json_data:
            return str(self.json_data)
        elif self.raw_content:
            return str(self.raw_content)
        else:
            return ""
    
    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Override dict() to handle empty fields."""
        result = super().dict(*args, **kwargs)
        
        # Remove None values to save space
        return {k: v for k, v in result.items() if v is not None}


class MemoryMetadata(BaseModel):
    """
    Metadata associated with a memory item.
    
    This includes information about the memory's creation, status,
    importance, and other properties that are not part of the content itself.
    """
    
    # Basic metadata
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    
    # Importance and usage metrics
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    access_count: int = Field(default=0, ge=0)
    
    # Ownership and scoping
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)

    # Categorization
    tags: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    
    # Tier-specific metadata
    tier: Optional[str] = None  # "stm", "mtm", "ltm"
    expires_at: Optional[datetime] = None  # For STM
    priority: Optional[Union[int, str]] = None  # For MTM
    
    # Consolidation metadata
    consolidated_from: Optional[str] = None  # ID of the source memory
    consolidated_at: Optional[datetime] = None
    
    # Vector representation
    embedding_model: Optional[str] = None  # Name of the model used to generate embedding
    embedding_dimensions: Optional[int] = None  # Dimensionality of the embedding
    # Relevance score (often added during search)
    relevance: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Extensible metadata
    additional_metadata: Dict[str, Any] = Field(default_factory=dict)

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Override dict() to handle empty fields and enum serialization."""
        result = super().dict(*args, **kwargs)

        # Convert enum to string
        if "status" in result and isinstance(result["status"], MemoryStatus):
            result["status"] = result["status"].value
        
        # Remove None values to save space
        return {k: v for k, v in result.items() if v is not None}
    
    def mark_accessed(self) -> None:
        """Mark the memory as accessed, updating access metrics."""
        self.last_accessed = datetime.now()
        self.access_count += 1
        
        # Strengthen memory slightly on access
        self.strength = min(1.0, self.strength + 0.05)
    
    def add_tag(self, tag: str, value: Any = True) -> None:
        """Add a tag to the memory with an optional value."""
        self.tags[tag] = value
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the memory if it exists."""
        if tag in self.tags:
            del self.tags[tag]
            return True
        return False


class MemoryItem(BaseModel):
    """
    A memory item in the Neuroca memory system.
    
    This is the main data model for memory items, representing a unit of
    information stored in the memory system. It includes both content
    (what is remembered) and metadata (information about the memory itself).
    """
    
    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Core memory data
    content: Union[MemoryContent, Dict[str, Any]]
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    
    # Optional summary for quick retrieval
    summary: Optional[str] = None
    
    # Vector embedding for similarity search
    embedding: Optional[List[float]] = None
    
    @field_validator("content", mode="before")
    def validate_content(cls, v):
        """Ensure content is a MemoryContent object."""
        if isinstance(v, dict):
            return MemoryContent(**v)
        return v
    
    @field_validator("metadata", mode="before")
    def validate_metadata(cls, v):
        """Ensure metadata is a MemoryMetadata object."""
        if isinstance(v, dict):
            return MemoryMetadata(**v)
        return v
    
    def mark_accessed(self) -> None:
        """Mark the memory as accessed, updating access metrics."""
        self.metadata.mark_accessed()
    
    def get_text(self) -> str:
        """Get the main text representation of this memory."""
        if isinstance(self.content, MemoryContent):
            return self.content.primary_text
        elif self.summary:
            return self.summary
        elif isinstance(self.content, dict) and "text" in self.content:
            return self.content["text"]
        else:
            return str(self.content)
    
    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Override dict() to handle custom fields."""
        result = super().dict(*args, **kwargs)

        # Convert MemoryContent to dict
        if "content" in result and isinstance(result["content"], MemoryContent):
            result["content"] = result["content"].dict()

        # Convert MemoryMetadata to dict
        if "metadata" in result and isinstance(result["metadata"], MemoryMetadata):
            result["metadata"] = result["metadata"].dict()

        # Remove None values to save space
        return {k: v for k, v in result.items() if v is not None}

    def calculate_activation(self, *, now: Optional[datetime] = None) -> float:
        """Estimate activation strength based on metadata heuristics."""

        meta = self.metadata
        reference_time = now or datetime.now()

        # Recency factor: 1.0 when accessed within the last hour, decays over a day.
        time_since_access = reference_time - meta.last_accessed
        recency_window = timedelta(hours=1)
        decay_window = timedelta(hours=24)
        if time_since_access <= recency_window:
            recency_factor = 1.0
        elif time_since_access >= decay_window:
            recency_factor = 0.0
        else:
            span = (decay_window - recency_window).total_seconds()
            recency_factor = 1.0 - ((time_since_access - recency_window).total_seconds() / span)

        # Access frequency provides a small boost but caps quickly.
        access_boost = min(1.0, meta.access_count * 0.05)

        # Combine intrinsic strength and importance with recency/frequency factors.
        intrinsic = 0.6 * meta.strength + 0.4 * meta.importance
        activation = 0.7 * intrinsic + 0.2 * recency_factor + 0.1 * access_boost

        return max(0.0, min(1.0, round(activation, 3)))
    
    @staticmethod
    def from_text(
        text: str,
        importance: float = 0.5,
        tags: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "MemoryItem":
        """
        Create a MemoryItem from a simple text string.
        
        Args:
            text: The text content
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags dictionary
            metadata: Optional additional metadata
            
        Returns:
            A MemoryItem instance
        """
        content = MemoryContent(text=text)
        
        meta = MemoryMetadata(
            importance=importance,
            tags=tags or {},
            additional_metadata=metadata or {},
        )
        
        return MemoryItem(content=content, metadata=meta)
