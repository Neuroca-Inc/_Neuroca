"""Tests for the SQLite statistics component."""

from __future__ import annotations

from typing import Any, Iterable

from neuroca.memory.backends.sqlite.components.stats import SQLiteStats
from neuroca.memory.interfaces import StorageStats


class _DummyCursor:
    def __init__(self, value: int) -> None:
        self._value = value

    def fetchone(self) -> tuple[int]:
        return (self._value,)

    # The stats component does not call fetchall for the scenarios covered in
    # these tests, but sqlite3 cursors expose the method so we provide a noop to
    # avoid attribute errors if the implementation changes.
    def fetchall(self) -> list[Any]:  # pragma: no cover - defensive stub
        return []


class _DummyConnection:
    def __init__(self, values: Iterable[int]) -> None:
        self._values = list(values)
        self._index = 0

    def execute(self, *_: Any, **__: Any) -> _DummyCursor:
        value = self._values[self._index]
        self._index += 1
        return _DummyCursor(value)


class _DummyConnectionManager:
    def __init__(self, connection: _DummyConnection) -> None:
        self._connection = connection

    def get_connection(self) -> _DummyConnection:
        return self._connection


def test_sqlite_stats_produces_storage_stats_with_backend_metadata() -> None:
    connection = _DummyConnection([6, 4, 2])
    manager = _DummyConnectionManager(connection)
    stats_component = SQLiteStats(manager, db_path=":memory:")

    stats = stats_component.get_stats()

    assert isinstance(stats, StorageStats)
    assert stats.backend_type == "SQLiteBackend"
    assert stats.item_count == 6
    assert stats.additional_info["active_memories"] == 4
    assert stats.additional_info["archived_memories"] == 2
    assert "operation_counts" in stats.additional_info
    assert "last_access_time" in stats.additional_info


def test_sqlite_stats_formats_operation_counts() -> None:
    connection = _DummyConnection([1, 1, 0])
    manager = _DummyConnectionManager(connection)
    stats_component = SQLiteStats(manager, db_path=":memory:")

    stats_component.update_stat("create_count")
    stats_component.update_stat("read_count", 2)
    stats_component.update_stat("update_count", 3)
    stats_component.update_stat("delete_count")

    stats = stats_component.get_stats()

    counts = stats.additional_info["operation_counts"]

    assert counts == {"create": 1, "read": 2, "update": 3, "delete": 1}
