"""ID mixin built on top of :mod:`neuroca.utils.base.base_object`."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from .base_object import BaseObject


class WithID(BaseObject):
    """Augment :class:`BaseObject` derivatives with an immutable identifier."""

    def __init__(self, identifier: Optional[str] = None) -> None:
        """Initialise the mixin and allocate an identifier when required.

        Args:
            identifier: Pre-existing identifier supplied by the caller. When
                ``None`` a UUID4 string is generated.
        """

        super().__init__()
        self.id = identifier or str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        """Extend :meth:`BaseObject.to_dict` to include the identifier column.

        Returns:
            dict[str, Any]: Serialised representation containing the ``id``
                field and remaining public attributes.
        """

        return {**super().to_dict(), "id": self.id}
