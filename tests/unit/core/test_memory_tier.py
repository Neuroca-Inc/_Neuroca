import pytest

from neuroca.core.enums import MemoryTier


@pytest.mark.parametrize(
    "alias, expected",
    [
        ("STM", MemoryTier.WORKING),
        ("working", MemoryTier.WORKING),
        ("short_term", MemoryTier.WORKING),
        ("mtm", MemoryTier.EPISODIC),
        ("medium-term", MemoryTier.EPISODIC),
        ("ltm", MemoryTier.SEMANTIC),
        ("long term", MemoryTier.SEMANTIC),
    ],
)
def test_memory_tier_from_string_accepts_aliases(alias, expected):
    assert MemoryTier.from_string(alias) is expected


def test_memory_tier_storage_keys_are_canonical():
    assert MemoryTier.WORKING.storage_key == "stm"
    assert MemoryTier.EPISODIC.storage_key == "mtm"
    assert MemoryTier.SEMANTIC.storage_key == "ltm"


@pytest.mark.parametrize("member", list(MemoryTier))
def test_memory_tier_canonical_labels(member):
    assert member.canonical_label in {"working", "episodic", "semantic"}


@pytest.mark.parametrize(
    "invalid",
    ["", "unknown", "primary"],
)
def test_memory_tier_from_string_rejects_invalid_inputs(invalid):
    with pytest.raises(ValueError):
        MemoryTier.from_string(invalid)
