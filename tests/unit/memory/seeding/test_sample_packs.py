from __future__ import annotations

from pathlib import Path

import pytest

from neuroca.memory.seeding import (
    get_sample_pack,
    list_sample_packs,
    load_sample_pack,
    write_sample_pack,
)


def test_list_sample_packs_exposes_known_scenarios() -> None:
    packs = list_sample_packs()

    assert len(packs) >= 2
    slugs = [pack.slug for pack in packs]
    assert "collaborative-brainstorm" in slugs
    assert "customer-support-playbook" in slugs

    first = get_sample_pack("collaborative-brainstorm")
    assert first.default_user == "team-alpha"
    assert "collaboration" in first.tags


def test_load_sample_pack_returns_text() -> None:
    contents = load_sample_pack("customer-support-playbook")

    assert "Inbound ticket from ACME Corp" in contents
    assert contents.count("\n") >= 4


def test_write_sample_pack_creates_expected_file(tmp_path: Path) -> None:
    destination = tmp_path / "seedpacks"
    exported_path = write_sample_pack("collaborative-brainstorm", destination)

    assert exported_path.exists()
    assert exported_path.read_text(encoding="utf-8").startswith("{\"content\": \"Kickoff workshop")

    with pytest.raises(FileExistsError):
        write_sample_pack("collaborative-brainstorm", exported_path)

    overwritten = write_sample_pack(
        "collaborative-brainstorm",
        exported_path,
        overwrite=True,
    )
    assert overwritten == exported_path
