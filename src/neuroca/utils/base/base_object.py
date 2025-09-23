"""Foundational serialisation helpers used across utility models."""

from __future__ import annotations

import json
from typing import Any


class BaseObject:
    """Provide consistent JSON and dictionary serialisation behaviour."""

    def to_dict(self) -> dict[str, Any]:
        """Return a mapping representation of the public attributes.

        Returns:
            dict[str, Any]: Dictionary containing attribute names and values
                excluding private members.
        """

        return {key: value for key, value in self.__dict__.items() if not key.startswith("_")}

    def to_json(self) -> str:
        """Serialise the object to JSON via :meth:`to_dict`.

        Returns:
            str: JSON encoded payload describing the object's public state.
        """

        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseObject":
        """Instantiate a subclass from dictionary data.

        Args:
            data: Mapping of attribute names to values that should be applied to
                the new instance.

        Returns:
            BaseObject: Newly created instance populated with ``data`` values
                where matching attributes exist.
        """

        obj = cls()
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        return obj

    @classmethod
    def from_json(cls, json_str: str) -> "BaseObject":
        """Instantiate a subclass from a JSON payload.

        Args:
            json_str: JSON string created by :meth:`to_json`.

        Returns:
            BaseObject: Instance of the subclass populated from ``json_str``.
        """

        return cls.from_dict(json.loads(json_str))
