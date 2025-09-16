"""
Base Model Implementation for NeuroCognitive Architecture (NCA).

This module provides the foundational model classes and mixins that serve as the
building blocks for all domain models in the NCA system. It implements common
functionality such as serialization, validation, persistence hooks, and lifecycle
management that all models inherit.

The BaseModel class follows a composition pattern with mixins to allow for flexible
extension of functionality while maintaining a clean inheritance hierarchy.

Usage:
    from neuroca.core.models.base import BaseModel, TimestampMixin

    class MyModel(TimestampMixin, BaseModel):
        def __init__(self, id, name, **kwargs):
            self.name = name
            super().__init__(id=id, **kwargs)

        def validate(self):
            super().validate()
            if not self.name:
                raise ValidationError("Name cannot be empty")
"""

import abc
import copy
import datetime
import inspect
import json
import logging
import uuid
from collections.abc import Iterable, Iterator
from threading import RLock
from typing import Any, Dict, List, Optional, Set, Type, TypeVar, Union, cast

# Setup module logger
logger = logging.getLogger(__name__)

# Type variables for self-referencing return types
T = TypeVar('T', bound='BaseModel')
S = TypeVar('S', bound='Serializable')


class ModelError(Exception):
    """Base exception class for all model-related errors."""
    pass


class ValidationError(ModelError):
    """Exception raised when model validation fails."""
    pass


class SerializationError(ModelError):
    """Exception raised when model serialization or deserialization fails."""
    pass


class PersistenceError(ModelError):
    """Exception raised when model persistence operations fail."""
    pass


class ModelNotFoundError(ModelError):
    """Exception raised when a model cannot be found by its identifier."""
    pass


class ModelID(str):
    """Strongly-typed identifier for registered domain models."""

    __slots__ = ()

    def __new__(cls, value: Union['ModelID', str]) -> 'ModelID':
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise TypeError(f"ModelID value must be a string, received {type(value).__name__}")
        normalized = value.strip()
        if not normalized:
            raise ValueError("ModelID value cannot be empty or whitespace")
        return super().__new__(cls, normalized)

    @property
    def canonical(self) -> str:
        """Return the canonical (case-insensitive) representation of the identifier."""

        return str(self).casefold()

    def __repr__(self) -> str:  # pragma: no cover - representational helper
        return f"ModelID({str(self)!r})"


class Serializable(abc.ABC):
    """Interface describing serialization behaviour for domain models."""

    __slots__ = ()

    @abc.abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert the object into a JSON-serialisable dictionary."""

    @classmethod
    @abc.abstractmethod
    def from_dict(cls: Type[S], data: Dict[str, Any]) -> S:
        """Create an object instance from a dictionary payload."""

    def to_json(self, **kwargs: Any) -> str:
        """Serialise the object into a JSON string."""

        try:
            return json.dumps(self.to_dict(), **kwargs)
        except (TypeError, ValueError, OverflowError) as error:
            logger.error(
                "JSON serialization error for %s: %s",
                self.__class__.__name__,
                error,
            )
            raise SerializationError(
                f"Failed to serialize {self.__class__.__name__} to JSON"
            ) from error

    @classmethod
    def from_json(cls: Type[S], json_str: str) -> S:
        """Deserialise an object instance from a JSON payload."""

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as error:
            logger.error("JSON parsing error for %s: %s", cls.__name__, error)
            raise SerializationError(
                f"Invalid JSON format for {cls.__name__}"
            ) from error

        if not isinstance(data, dict):
            raise SerializationError(
                f"Expected JSON object when decoding {cls.__name__}, received {type(data).__name__}"
            )

        return cls.from_dict(data)


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp fields to models.
    
    Automatically manages timestamps during model lifecycle events.
    """
    
    def __init__(self, **kwargs):
        """Initialize timestamp fields with current time or provided values."""
        self.created_at = kwargs.get('created_at', datetime.datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', self.created_at)
        super().__init__(**kwargs)
    
    def pre_save(self) -> None:
        """Update the updated_at timestamp before saving."""
        self.updated_at = datetime.datetime.utcnow()
        super().pre_save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert timestamps to ISO format strings in dictionary representation."""
        data = super().to_dict()
        # Convert datetime objects to ISO format strings
        if hasattr(self, 'created_at') and self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if hasattr(self, 'updated_at') and self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parse ISO format timestamp strings from dictionary."""
        data_copy = copy.deepcopy(data)
        
        # Convert ISO format strings to datetime objects
        for field in ['created_at', 'updated_at']:
            if field in data_copy and isinstance(data_copy[field], str):
                try:
                    data_copy[field] = datetime.datetime.fromisoformat(data_copy[field])
                except ValueError as e:
                    logger.error(f"Failed to parse {field} timestamp: {e}")
                    raise SerializationError(f"Invalid timestamp format for {field}") from e
        
        return super(TimestampMixin, cls).from_dict(data_copy)


class VersionedMixin:
    """
    Mixin that adds versioning capability to models.
    
    Tracks version numbers and provides methods to handle version conflicts.
    """
    
    def __init__(self, **kwargs):
        """Initialize version field with default or provided value."""
        self.version = kwargs.get('version', 1)
        super().__init__(**kwargs)
    
    def pre_save(self) -> None:
        """Increment version number before saving."""
        self.version += 1
        super().pre_save()
    
    def check_version(self, expected_version: int) -> bool:
        """
        Check if the current version matches the expected version.
        
        Args:
            expected_version: The version number to check against
            
        Returns:
            bool: True if versions match, False otherwise
        """
        return self.version == expected_version


class BaseModel(Serializable, abc.ABC):
    """
    Abstract base class for all domain models in the NCA system.
    
    Provides core functionality for model lifecycle, serialization,
    validation, and persistence operations.
    """
    
    # Class-level registry of field names to exclude from serialization
    _private_fields: Set[str] = {'_private_fields', '_id_field'}
    
    # Name of the field that serves as the primary identifier
    _id_field: str = 'id'
    
    def __init__(self, **kwargs):
        """
        Initialize a new model instance.
        
        Args:
            **kwargs: Keyword arguments corresponding to model fields
        """
        # Set ID field if provided, otherwise generate a new UUID
        id_value = kwargs.get(self._id_field)
        if id_value is None:
            id_value = str(uuid.uuid4())
        
        self.__dict__[self._id_field] = id_value
        
        # Initialize any additional fields from kwargs
        for key, value in kwargs.items():
            if key != self._id_field and not key.startswith('_'):
                setattr(self, key, value)
        
        logger.debug(
            "Initialized %s with ID: %s",
            self.__class__.__name__,
            self.__dict__.get(self._id_field),
        )
    
    @property
    def id(self) -> str:
        """
        Get the model's unique identifier.

        Returns:
            str: The model's ID
        """
        return cast(str, self.__dict__.get(self._id_field))

    @id.setter
    def id(self, value: str) -> None:
        """Update the model's identifier."""

        if not isinstance(value, str) or not value:
            raise ValidationError("Model identifier must be a non-empty string")
        self.__dict__[self._id_field] = value
    
    def validate(self) -> None:
        """
        Validate the model state.
        
        Raises:
            ValidationError: If validation fails
        """
        # Base validation ensures ID is present
        if not self.__dict__.get(self._id_field):
            raise ValidationError(f"Model {self.__class__.__name__} must have a valid {self._id_field}")
    
    def pre_save(self) -> None:
        """
        Hook called before the model is saved.
        
        Override in subclasses to implement custom pre-save logic.
        """
        pass
    
    def post_save(self) -> None:
        """
        Hook called after the model is saved.
        
        Override in subclasses to implement custom post-save logic.
        """
        pass
    
    def pre_delete(self) -> None:
        """
        Hook called before the model is deleted.
        
        Override in subclasses to implement custom pre-delete logic.
        """
        pass
    
    def post_delete(self) -> None:
        """
        Hook called after the model is deleted.
        
        Override in subclasses to implement custom post-delete logic.
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        result = {}
        
        for key, value in self.__dict__.items():
            # Skip private fields
            if key in self._private_fields or key.startswith('_'):
                continue
            
            # Handle nested models
            if isinstance(value, BaseModel):
                result[key] = value.to_dict()
            # Handle lists of models
            elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
                result[key] = [item.to_dict() if isinstance(item, BaseModel) else item for item in value]
            # Handle all other types
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        Create a model instance from a dictionary.
        
        Args:
            data: Dictionary containing model data
            
        Returns:
            T: New model instance
            
        Raises:
            SerializationError: If deserialization fails
        """
        if not isinstance(data, dict):
            raise SerializationError(f"Expected dict, got {type(data).__name__}")
        
        try:
            # Create a copy to avoid modifying the input
            data_copy = copy.deepcopy(data)
            
            # Create a new instance with the data
            instance = cls(**data_copy)
            
            # Validate the new instance
            instance.validate()
            
            return instance
        except Exception as e:
            logger.error(f"Error deserializing {cls.__name__} from dict: {e}")
            raise SerializationError(f"Failed to deserialize {cls.__name__} from dictionary") from e
    
    def __eq__(self, other: Any) -> bool:
        """
        Compare two model instances for equality.
        
        Models are considered equal if they have the same class and ID.
        
        Args:
            other: Object to compare with
            
        Returns:
            bool: True if equal, False otherwise
        """
        if not isinstance(other, self.__class__):
            return False
        
        return getattr(self, self._id_field) == getattr(other, self._id_field)
    
    def __hash__(self) -> int:
        """
        Generate a hash value for the model.
        
        Returns:
            int: Hash value based on the model's ID
        """
        return hash((self.__class__, getattr(self, self._id_field)))
    
    def __str__(self) -> str:
        """
        Get a string representation of the model.
        
        Returns:
            str: String representation including class name and ID
        """
        return f"{self.__class__.__name__}(id={getattr(self, self._id_field)})"
    
    def __repr__(self) -> str:
        """
        Get a detailed string representation of the model.
        
        Returns:
            str: Detailed string representation including all fields
        """
        fields = ', '.join(f"{k}={repr(v)}" for k, v in self.to_dict().items())
        return f"{self.__class__.__name__}({fields})"
    
    def clone(self: T, **kwargs) -> T:
        """
        Create a deep copy of the model with optional field overrides.
        
        Args:
            **kwargs: Fields to override in the cloned instance
            
        Returns:
            T: New model instance with the same data
        """
        # Create a dictionary representation
        data = self.to_dict()
        
        # Apply overrides
        data.update(kwargs)
        
        # Create a new instance
        return self.__class__.from_dict(data)


class AggregateRoot(BaseModel):
    """
    Base class for aggregate roots in the domain model.
    
    Aggregate roots are the entry point to an aggregate of domain objects and
    enforce consistency rules for the entire aggregate.
    """
    
    def __init__(self, **kwargs):
        """Initialize a new aggregate root instance."""
        self._events: List[Dict[str, Any]] = []
        super().__init__(**kwargs)
    
    def add_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a domain event that occurred within this aggregate.
        
        Args:
            event_type: Type of the event
            data: Additional event data
        """
        if data is None:
            data = {}
            
        event = {
            'type': event_type,
            'aggregate_id': self.id,
            'aggregate_type': self.__class__.__name__,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'data': data
        }
        
        self._events.append(event)
        logger.debug(f"Added event {event_type} to {self.__class__.__name__} {self.id}")
    
    def clear_events(self) -> List[Dict[str, Any]]:
        """
        Clear and return all recorded events.
        
        Returns:
            List[Dict[str, Any]]: List of recorded events
        """
        events = self._events.copy()
        self._events = []
        return events
    
    def get_events(self) -> List[Dict[str, Any]]:
        """
        Get all recorded events without clearing them.
        
        Returns:
            List[Dict[str, Any]]: List of recorded events
        """
        return self._events.copy()


class ReadOnlyModelError(ModelError):
    """Exception raised when attempting to modify a read-only model."""
    pass


class ReadOnlyModel(BaseModel):
    """
    Base class for read-only models.
    
    These models cannot be modified after creation and are typically used
    for query results or views.
    """
    
    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent modification of attributes after initialization.
        
        Args:
            name: Attribute name
            value: Attribute value
            
        Raises:
            ReadOnlyModelError: If attempting to modify an existing attribute
        """
        if hasattr(self, name):
            raise ReadOnlyModelError(f"Cannot modify {name} on read-only model {self.__class__.__name__}")
        super().__setattr__(name, value)
    
    def pre_save(self) -> None:
        """
        Prevent saving of read-only models.
        
        Raises:
            ReadOnlyModelError: Always raised when called
        """
        raise ReadOnlyModelError(f"Cannot save read-only model {self.__class__.__name__}")
    
    def pre_delete(self) -> None:
        """
        Prevent deletion of read-only models.
        
        Raises:
            ReadOnlyModelError: Always raised when called
        """
        raise ReadOnlyModelError(f"Cannot delete read-only model {self.__class__.__name__}")


class ModelRegistry:
    """Thread-safe registry tracking concrete ``BaseModel`` implementations."""

    def __init__(self) -> None:
        self._models: Dict[str, Type[BaseModel]] = {}
        self._aliases: Dict[str, Set[ModelID]] = {}
        self._alias_to_canonical: Dict[str, str] = {}
        self._lock = RLock()

    def register(
        self,
        model: Type[T],
        *,
        name: Optional[Union[str, ModelID]] = None,
        aliases: Optional[Iterable[Union[str, ModelID]]] = None,
        overwrite: bool = False,
    ) -> Type[T]:
        """Register a model type with optional aliases."""

        if not inspect.isclass(model) or not issubclass(model, BaseModel):
            raise TypeError("Only BaseModel subclasses can be registered")

        canonical_id = ModelID(name or model.__name__)
        alias_ids: Set[ModelID] = set()
        if aliases:
            for alias in aliases:
                alias_ids.add(ModelID(alias))

        with self._lock:
            existing = self._models.get(canonical_id.canonical)
            if existing is not None and existing is not model and not overwrite:
                raise ValueError(
                    f"Model '{canonical_id}' is already registered to {existing.__name__}"
                )

            if existing is not None and existing is not model:
                self._remove_alias_mappings_locked(canonical_id.canonical)

            self._models[canonical_id.canonical] = model
            alias_bucket = self._aliases.setdefault(canonical_id.canonical, set())
            if overwrite and existing is not model:
                alias_bucket.clear()

            self._alias_to_canonical[canonical_id.canonical] = canonical_id.canonical
            alias_bucket.add(canonical_id)

            for alias_id in alias_ids:
                alias_key = alias_id.canonical
                mapped = self._alias_to_canonical.get(alias_key)
                if mapped and mapped != canonical_id.canonical:
                    if not overwrite:
                        raise ValueError(
                            f"Alias '{alias_id}' is already registered to {self._models[mapped].__name__}"
                        )
                    self._remove_alias_reference_locked(alias_key, mapped)

                alias_bucket.add(alias_id)
                self._alias_to_canonical[alias_key] = canonical_id.canonical

            return model

    def unregister(self, identifier: Union[str, ModelID, Type[BaseModel]]) -> Optional[Type[BaseModel]]:
        """Remove a registered model and associated aliases."""

        with self._lock:
            canonical_key = self._resolve_locked(identifier, allow_missing=True)
            if canonical_key is None:
                return None

            model = self._models.pop(canonical_key, None)
            self._remove_alias_mappings_locked(canonical_key)
            self._aliases.pop(canonical_key, None)
            return model

    def get(
        self,
        identifier: Union[str, ModelID, Type[BaseModel]],
        default: Optional[Type[BaseModel]] = None,
    ) -> Optional[Type[BaseModel]]:
        """Retrieve a registered model by name, alias, or type."""

        with self._lock:
            canonical_key = self._resolve_locked(identifier, allow_missing=True)
            if canonical_key is None:
                return default
            return self._models.get(canonical_key, default)

    def require(self, identifier: Union[str, ModelID, Type[BaseModel]]) -> Type[BaseModel]:
        """Retrieve a registered model, raising if it is absent."""

        with self._lock:
            canonical_key = self._resolve_locked(identifier, allow_missing=False)
            return self._models[canonical_key]

    def aliases_for(self, identifier: Union[str, ModelID, Type[BaseModel]]) -> Set[str]:
        """Return the set of aliases registered for the given model."""

        with self._lock:
            canonical_key = self._resolve_locked(identifier, allow_missing=False)
            return {str(alias) for alias in self._aliases.get(canonical_key, set())}

    def canonical_name(self, identifier: Union[str, ModelID, Type[BaseModel]]) -> str:
        """Resolve and return the canonical registry key for the identifier."""

        with self._lock:
            return self._resolve_locked(identifier, allow_missing=False)

    def __contains__(self, identifier: Union[str, ModelID, Type[BaseModel]]) -> bool:
        with self._lock:
            canonical_key = self._resolve_locked(identifier, allow_missing=True)
            return canonical_key in self._models if canonical_key is not None else False

    def __len__(self) -> int:
        with self._lock:
            return len(self._models)

    def __iter__(self) -> Iterator[Type[BaseModel]]:
        with self._lock:
            models = list(self._models.values())
        return iter(models)

    def items(self) -> Iterator[tuple[str, Type[BaseModel]]]:
        with self._lock:
            snapshot = list(self._models.items())
        return iter(snapshot)

    def keys(self) -> Iterator[str]:
        with self._lock:
            snapshot = list(self._models.keys())
        return iter(snapshot)

    def values(self) -> Iterator[Type[BaseModel]]:
        with self._lock:
            snapshot = list(self._models.values())
        return iter(snapshot)

    def clear(self) -> None:
        with self._lock:
            self._models.clear()
            self._alias_to_canonical.clear()
            self._aliases.clear()

    def _resolve_locked(
        self,
        identifier: Union[str, ModelID, Type[BaseModel]],
        *,
        allow_missing: bool,
    ) -> Optional[str]:
        if inspect.isclass(identifier) and issubclass(identifier, BaseModel):
            for canonical_key, model in self._models.items():
                if model is identifier:
                    return canonical_key
            if allow_missing:
                return None
            raise ModelNotFoundError(
                f"Model {identifier.__name__} is not registered"
            )

        model_id = identifier if isinstance(identifier, ModelID) else ModelID(identifier)
        canonical_key = self._alias_to_canonical.get(model_id.canonical)
        if canonical_key is not None:
            return canonical_key

        if model_id.canonical in self._models:
            return model_id.canonical

        if allow_missing:
            return None
        raise ModelNotFoundError(f"Model '{identifier}' is not registered")

    def _remove_alias_mappings_locked(self, canonical_key: str) -> None:
        alias_bucket = self._aliases.get(canonical_key, set())
        for alias_id in list(alias_bucket):
            self._alias_to_canonical.pop(alias_id.canonical, None)
        alias_bucket.clear()

    def _remove_alias_reference_locked(self, alias_key: str, canonical_key: str) -> None:
        alias_bucket = self._aliases.get(canonical_key)
        if alias_bucket:
            for alias_id in list(alias_bucket):
                if alias_id.canonical == alias_key:
                    alias_bucket.discard(alias_id)
        self._alias_to_canonical.pop(alias_key, None)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        with self._lock:
            entries = ', '.join(f"{key}: {model.__name__}" for key, model in self._models.items())
        return f"ModelRegistry({{{entries}}})"
