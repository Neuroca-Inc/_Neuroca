"""Composable CRUD and search mixins for the memory manager."""

from __future__ import annotations

from .add import MemoryManagerAddMixin
from .delete import MemoryManagerDeleteMixin
from .retrieve import MemoryManagerRetrieveMixin
from .search import MemoryManagerSearchMixin
from .support import MemoryManagerOperationSupportMixin
from .transfer import MemoryManagerTransferMixin
from .update import MemoryManagerUpdateMixin


class MemoryManagerOperationsMixin(
    MemoryManagerAddMixin,
    MemoryManagerRetrieveMixin,
    MemoryManagerUpdateMixin,
    MemoryManagerDeleteMixin,
    MemoryManagerTransferMixin,
    MemoryManagerSearchMixin,
    MemoryManagerOperationSupportMixin,
):
    """Aggregate CRUD and search behaviours for the memory manager."""

    pass


__all__ = ["MemoryManagerOperationsMixin"]
