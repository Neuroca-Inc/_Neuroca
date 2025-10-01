"""Timestamp mixin providing creation and update bookkeeping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base_object import BaseObject


class WithTimestamp(BaseObject):
    """Track creation and update timestamps for mutable models."""

    def __init__(self) -> None:
        """Stamp the instance with the current creation and update times."""

        super().__init__()
        self.created_at = datetime.now()
        self.updated_at = self.created_at

    def update_timestamp(self) -> None:
        """Refresh the ``updated_at`` field to the current time."""

        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Serialise timestamps to ISO 8601 strings in the output mapping.

        Returns:
            dict[str, Any]: Mapping containing the timestamp fields with ISO 8601
                formatting alongside remaining public attributes.
        """

        result = super().to_dict()
        if hasattr(self, "created_at"):
            result["created_at"] = self.created_at.isoformat()
        if hasattr(self, "updated_at"):
            result["updated_at"] = self.updated_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WithTimestamp":
        """Rebuild the mixin from serialized dictionary data.

        Args:
            data: Dictionary produced via :meth:`to_dict`.

        Returns:
            WithTimestamp: Instance with timestamp attributes populated from
                ``data`` when available.
        """

        obj = super().from_dict(data)
        if isinstance(obj.created_at, str):
            obj.created_at = datetime.fromisoformat(obj.created_at)
        else:
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                obj.created_at = datetime.fromisoformat(created_at)
        if isinstance(obj.updated_at, str):
            obj.updated_at = datetime.fromisoformat(obj.updated_at)
        else:
            updated_at = data.get("updated_at")
            if isinstance(updated_at, str):
                obj.updated_at = datetime.fromisoformat(updated_at)
        return obj
