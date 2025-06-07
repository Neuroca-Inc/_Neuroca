"""
Episodic Memory Implementation (Stub)

This module provides a stub implementation of EpisodicMemory to satisfy imports
while the main memory system uses the tier-based architecture.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """
    Stub implementation of EpisodicMemory.
    
    This is a placeholder implementation to satisfy imports while the main
    memory system uses the more comprehensive tier-based architecture.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the episodic memory stub."""
        self.config = config or {}
        logger.debug("EpisodicMemory stub initialized")
    
    def store(self, content: Any, **kwargs) -> str:
        """Store content in episodic memory."""
        logger.warning("EpisodicMemory.store called on stub implementation")
        return "stub_episode_id"
    
    def retrieve(self, query: str, **kwargs) -> List[Any]:
        """Retrieve content from episodic memory."""
        logger.warning("EpisodicMemory.retrieve called on stub implementation")
        return []
    
    def clear(self, **kwargs) -> None:
        """Clear episodic memory."""
        logger.warning("EpisodicMemory.clear called on stub implementation")
        pass
    
    async def search_episodes(self, query: str, limit: int = 10, threshold: float = 0.0) -> List[Any]:
        """Search for episodes."""
        logger.warning("EpisodicMemory.search_episodes called on stub implementation")
        return []
    
    async def get_recent_episodes(self, limit: int = 10) -> List[Any]:
        """Get recent episodes."""
        logger.warning("EpisodicMemory.get_recent_episodes called on stub implementation")
        return []
    
    async def get_important_episodes(self, limit: int = 10) -> List[Any]:
        """Get important episodes."""
        logger.warning("EpisodicMemory.get_important_episodes called on stub implementation")
        return []
    
    async def get_episode(self, episode_id: str) -> Optional[Any]:
        """Get a specific episode."""
        logger.warning("EpisodicMemory.get_episode called on stub implementation")
        return None
    
    def add(self, episode: Any) -> str:
        """Add an episode."""
        logger.warning("EpisodicMemory.add called on stub implementation")
        return "stub_episode_id"
