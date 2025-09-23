"""Metadata mixin complementing :class:`BaseObject`."""

from __future__ import annotations

from typing import Any, Optional

from .base_object import BaseObject


class WithMetadata(BaseObject):
    """Add arbitrary metadata storage to :class:`BaseObject` derivatives."""

    def __init__(self, metadata: Optional[dict[str, Any]] = None) -> None:
        """Initialise the mixin with optional metadata payload.

        Args:
            metadata: Mapping of metadata values supplied by the caller. When
                omitted an empty dictionary is created.
        """

        super().__init__()
        self.metadata = metadata or {}

    def add_metadata(self, key: str, value: Any) -> None:
        """Set or update a metadata field on the instance.

        Args:
            key: Metadata key that identifies the stored value.
            value: Payload associated with ``key``.
        """

        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieve a metadata value while preserving backward compatibility.

        Args:
            key: Metadata key to fetch.
            default: Value returned when ``key`` is not present.

        Returns:
            Any: Stored metadata entry or ``default`` when missing.
        """

        return self.metadata.get(key, default)
