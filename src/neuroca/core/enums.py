"""Enumerations for the NeuroCognitive Architecture (NCA) system."""

from __future__ import annotations

import logging
from enum import Enum, auto, unique

logger = logging.getLogger(__name__)

class MemoryTier(str, Enum):
    """
    Represents the three-tiered memory system in the NCA.
    
    Attributes:
        WORKING: Short-term, limited capacity, high-access speed memory
        EPISODIC: Medium-term memory for experiences and events
        SEMANTIC: Long-term memory for facts, concepts, and knowledge
    """
    WORKING = "stm"
    EPISODIC = "mtm"
    SEMANTIC = "ltm"

    # Backwards compatible aliases for storage terminology
    STM = WORKING
    MTM = EPISODIC
    LTM = SEMANTIC

    def __str__(self) -> str:
        return self.canonical_label

    @property
    def canonical_label(self) -> str:
        """Return the canonical cognitive label for the tier."""
        return _MEMORY_TIER_CANONICAL_LABELS[self]

    @property
    def storage_key(self) -> str:
        """Return the storage-layer key associated with this tier."""
        return self.value

    @classmethod
    def _normalize_key(cls, tier_name: str) -> str:
        return tier_name.strip().replace("-", "_").replace(" ", "_").lower()

    @classmethod
    def from_string(cls, tier_name: str) -> MemoryTier:
        """Convert a string (or alias) to a MemoryTier enum value."""
        if isinstance(tier_name, MemoryTier):
            return tier_name

        if not isinstance(tier_name, str):
            raise ValueError("Memory tier must be provided as a string")

        normalized_key = cls._normalize_key(tier_name)
        normalized_map = _MEMORY_TIER_NORMALIZED_MAP
        tier = normalized_map.get(normalized_key)
        if tier is not None:
            return tier

        try:
            return cls[tier_name.upper()]
        except KeyError:
            pass

        try:
            return cls(tier_name)
        except ValueError:
            valid_inputs = sorted(
                {
                    *_MEMORY_TIER_NORMALIZED_MAP.keys(),
                    *(member.storage_key for member in cls),
                    *(member.canonical_label for member in cls),
                }
            )
            logger.error(
                "Invalid memory tier: '%s'. Valid tiers are: %s",
                tier_name,
                ", ".join(valid_inputs),
            )
            raise ValueError(
                f"Invalid memory tier: '{tier_name}'. Valid tiers are: {', '.join(valid_inputs)}"
            ) from None


_MEMORY_TIER_CANONICAL_LABELS: dict[MemoryTier, str] = {
    MemoryTier.WORKING: "working",
    MemoryTier.EPISODIC: "episodic",
    MemoryTier.SEMANTIC: "semantic",
}

_MEMORY_TIER_ALIASES: dict[MemoryTier, tuple[str, ...]] = {
    MemoryTier.WORKING: (
        "working",
        "working_memory",
        "short_term",
        "short_term_memory",
        "shortterm",
        "shortterm_memory",
        "stm",
    ),
    MemoryTier.EPISODIC: (
        "episodic",
        "episodic_memory",
        "medium_term",
        "medium_term_memory",
        "mediumterm",
        "mediumterm_memory",
        "mtm",
    ),
    MemoryTier.SEMANTIC: (
        "semantic",
        "semantic_memory",
        "long_term",
        "long_term_memory",
        "longterm",
        "longterm_memory",
        "ltm",
    ),
}

def _build_memory_tier_normalized_map() -> dict[str, MemoryTier]:
    normalized_map: dict[str, MemoryTier] = {}
    for tier, aliases in _MEMORY_TIER_ALIASES.items():
        augmented_aliases = set(aliases) | {
            tier.storage_key,
            tier.canonical_label,
            tier.name,
            tier.name.lower(),
        }
        for alias in augmented_aliases:
            normalized_map[MemoryTier._normalize_key(str(alias))] = tier
    return normalized_map


_MEMORY_TIER_NORMALIZED_MAP: dict[str, MemoryTier] = _build_memory_tier_normalized_map()


@unique
class CognitiveState(Enum):
    """
    Represents the possible cognitive states of the NCA.
    
    These states influence processing priorities, attention mechanisms,
    and resource allocation within the architecture.
    """
    IDLE = auto()        # Default state, minimal processing
    FOCUSED = auto()     # Concentrated on specific task
    LEARNING = auto()    # Prioritizing knowledge acquisition
    CREATIVE = auto()    # Emphasizing novel connections
    ANALYTICAL = auto()  # Detailed logical processing
    REFLECTIVE = auto()  # Internal state assessment
    EXPLORATORY = auto() # Seeking new information
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, state_name: str) -> CognitiveState:
        """
        Convert a string to a CognitiveState enum value.
        
        Args:
            state_name: String representation of the cognitive state
            
        Returns:
            Corresponding CognitiveState enum value
            
        Raises:
            ValueError: If the string doesn't match any cognitive state
        """
        try:
            return cls[state_name.upper()]
        except KeyError as err:
            valid_states = [s.name.lower() for s in cls]
            logger.error(
                "Invalid cognitive state: '%s'. Valid states are: %s",
                state_name,
                ", ".join(valid_states),
            )
            raise ValueError(
                f"Invalid cognitive state: '{state_name}'. Valid states are: {', '.join(valid_states)}"
            ) from err


@unique
class HealthIndicator(Enum):
    """
    Health indicators for the NCA system's biological-inspired dynamics.
    
    These indicators represent various aspects of the system's operational health,
    which can influence performance, decision-making, and resource allocation.
    """
    ENERGY = auto()       # Available computational resources
    COHERENCE = auto()    # Internal consistency of knowledge
    STABILITY = auto()    # Resistance to rapid state changes
    ADAPTABILITY = auto() # Ability to adjust to new information
    EFFICIENCY = auto()   # Resource utilization optimization
    RESILIENCE = auto()   # Recovery from errors or contradictions
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, indicator_name: str) -> HealthIndicator:
        """
        Convert a string to a HealthIndicator enum value.
        
        Args:
            indicator_name: String representation of the health indicator
            
        Returns:
            Corresponding HealthIndicator enum value
            
        Raises:
            ValueError: If the string doesn't match any health indicator
        """
        try:
            return cls[indicator_name.upper()]
        except KeyError as err:
            valid_indicators = [i.name.lower() for i in cls]
            logger.error(
                "Invalid health indicator: '%s'. Valid indicators are: %s",
                indicator_name,
                ", ".join(valid_indicators),
            )
            raise ValueError(
                f"Invalid health indicator: '{indicator_name}'. Valid indicators are: {', '.join(valid_indicators)}"
            ) from err


@unique
class ProcessingMode(Enum):
    """
    Processing modes for the NCA system.
    
    These modes determine how information is processed, affecting
    the balance between speed, depth, and resource utilization.
    """
    FAST = auto()      # Quick, heuristic-based processing
    DEEP = auto()      # Thorough, resource-intensive processing
    BALANCED = auto()  # Moderate balance of speed and depth
    ADAPTIVE = auto()  # Dynamically adjusts based on context
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, mode_name: str) -> ProcessingMode:
        """
        Convert a string to a ProcessingMode enum value.
        
        Args:
            mode_name: String representation of the processing mode
            
        Returns:
            Corresponding ProcessingMode enum value
            
        Raises:
            ValueError: If the string doesn't match any processing mode
        """
        try:
            return cls[mode_name.upper()]
        except KeyError as err:
            valid_modes = [m.name.lower() for m in cls]
            logger.error(
                "Invalid processing mode: '%s'. Valid modes are: %s",
                mode_name,
                ", ".join(valid_modes),
            )
            raise ValueError(
                f"Invalid processing mode: '{mode_name}'. Valid modes are: {', '.join(valid_modes)}"
            ) from err


@unique
class MemoryOperation(Enum):
    """
    Operations that can be performed on memory.
    
    These operations represent the fundamental actions that can be
    taken with memory items across the different memory tiers.
    """
    STORE = auto()    # Add new information to memory
    RETRIEVE = auto() # Access existing information
    UPDATE = auto()   # Modify existing information
    FORGET = auto()   # Remove or decay information
    CONSOLIDATE = auto() # Move between memory tiers
    ASSOCIATE = auto()   # Create links between memory items
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, operation_name: str) -> MemoryOperation:
        """
        Convert a string to a MemoryOperation enum value.
        
        Args:
            operation_name: String representation of the memory operation
            
        Returns:
            Corresponding MemoryOperation enum value
            
        Raises:
            ValueError: If the string doesn't match any memory operation
        """
        try:
            return cls[operation_name.upper()]
        except KeyError as err:
            valid_operations = [o.name.lower() for o in cls]
            logger.error(
                "Invalid memory operation: '%s'. Valid operations are: %s",
                operation_name,
                ", ".join(valid_operations),
            )
            raise ValueError(
                f"Invalid memory operation: '{operation_name}'. Valid operations are: {', '.join(valid_operations)}"
            ) from err


@unique
class Priority(Enum):
    """
    Priority levels for tasks, memories, and processes.
    
    These priorities help the system allocate resources and
    determine processing order for competing demands.
    """
    CRITICAL = 5   # Highest priority, immediate attention required
    HIGH = 4       # Important, should be processed soon
    MEDIUM = 3     # Standard priority
    LOW = 2        # Process when resources available
    BACKGROUND = 1 # Lowest priority, process during idle time
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, priority_name: str) -> Priority:
        """
        Convert a string to a Priority enum value.
        
        Args:
            priority_name: String representation of the priority
            
        Returns:
            Corresponding Priority enum value
            
        Raises:
            ValueError: If the string doesn't match any priority
        """
        try:
            return cls[priority_name.upper()]
        except KeyError as err:
            valid_priorities = [p.name.lower() for p in cls]
            logger.error(
                "Invalid priority: '%s'. Valid priorities are: %s",
                priority_name,
                ", ".join(valid_priorities),
            )
            raise ValueError(
                f"Invalid priority: '{priority_name}'. Valid priorities are: {', '.join(valid_priorities)}"
            ) from err
    
    @classmethod
    def from_int(cls, value: int) -> Priority:
        """
        Convert an integer to a Priority enum value.
        
        Args:
            value: Integer value of the priority (1-5)
            
        Returns:
            Corresponding Priority enum value
            
        Raises:
            ValueError: If the integer doesn't match any priority
        """
        for priority in cls:
            if priority.value == value:
                return priority
        
        valid_values = [str(p.value) for p in cls]
        logger.error(f"Invalid priority value: {value}. Valid values are: {', '.join(valid_values)}")
        raise ValueError(f"Invalid priority value: {value}. Valid values are: {', '.join(valid_values)}")


@unique
class IntegrationMode(Enum):
    """
    Modes for integrating with external LLM systems.
    
    These modes determine how the NCA system interacts with
    and utilizes external language models.
    """
    STANDALONE = auto()  # NCA operates independently
    AUGMENTED = auto()   # NCA enhances LLM capabilities
    EMBEDDED = auto()    # NCA runs within LLM context
    COLLABORATIVE = auto() # NCA and LLM work as peers
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, mode_name: str) -> IntegrationMode:
        """
        Convert a string to an IntegrationMode enum value.
        
        Args:
            mode_name: String representation of the integration mode
            
        Returns:
            Corresponding IntegrationMode enum value
            
        Raises:
            ValueError: If the string doesn't match any integration mode
        """
        try:
            return cls[mode_name.upper()]
        except KeyError as err:
            valid_modes = [m.name.lower() for m in cls]
            logger.error(
                "Invalid integration mode: '%s'. Valid modes are: %s",
                mode_name,
                ", ".join(valid_modes),
            )
            raise ValueError(
                f"Invalid integration mode: '{mode_name}'. Valid modes are: {', '.join(valid_modes)}"
            ) from err


@unique
class LogLevel(Enum):
    """
    Log levels for the NCA system.
    
    These levels correspond to standard logging levels but are
    exposed as an enum for type safety and consistency.
    """
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    def __str__(self) -> str:
        return self.name.lower()
    
    @classmethod
    def from_string(cls, level_name: str) -> LogLevel:
        """
        Convert a string to a LogLevel enum value.
        
        Args:
            level_name: String representation of the log level
            
        Returns:
            Corresponding LogLevel enum value
            
        Raises:
            ValueError: If the string doesn't match any log level
        """
        try:
            return cls[level_name.upper()]
        except KeyError as err:
            valid_levels = [level.name.lower() for level in cls]
            logger.error(
                "Invalid log level: '%s'. Valid levels are: %s",
                level_name,
                ", ".join(valid_levels),
            )
            raise ValueError(
                f"Invalid log level: '{level_name}'. Valid levels are: {', '.join(valid_levels)}"
            ) from err
    
    def to_logging_level(self) -> int:
        """
        Convert the enum value to a standard logging module level.
        
        Returns:
            Integer value corresponding to logging module levels
        """
        return self.value