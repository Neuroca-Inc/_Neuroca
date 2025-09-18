import pytest

from benchmarks.memory_systems_comparison.base import MemoryEntry
from benchmarks.memory_systems_comparison.competitors.sqlite_memory import SQLiteMemory


@pytest.fixture
def memory_system():
    system = SQLiteMemory()
    yield system
    system.clear()


def _make_entry(idx: int) -> MemoryEntry:
    return MemoryEntry(
        id=f"entry-{idx}",
        content=f"content-{idx}",
        metadata={"idx": idx},
        timestamp=float(idx + 1),
    )


def test_list_all_applies_limit(memory_system):
    for i in range(5):
        memory_system.store(_make_entry(i))

    results = memory_system.list_all(limit=2)

    assert len(results) == 2
    assert [entry.id for entry in results] == ["entry-4", "entry-3"]


def test_list_all_rejects_non_integer_limits(memory_system):
    memory_system.store(_make_entry(0))

    with pytest.raises(ValueError):
        memory_system.list_all(limit="1; DROP TABLE memories")


def test_list_all_rejects_non_positive_limits(memory_system):
    memory_system.store(_make_entry(0))

    with pytest.raises(ValueError):
        memory_system.list_all(limit=0)

    with pytest.raises(ValueError):
        memory_system.list_all(limit=-1)


def test_list_all_rejects_boolean_limits(memory_system):
    memory_system.store(_make_entry(0))

    with pytest.raises(ValueError):
        memory_system.list_all(limit=True)
