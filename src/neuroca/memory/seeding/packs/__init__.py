"""Sample memory seed packs for developer scenarios."""

from pathlib import Path
from typing import Iterable

__all__ = ["iter_pack_files", "get_pack_path"]

_PACKS_DIR = Path(__file__).resolve().parent


def iter_pack_files() -> Iterable[Path]:
    """Yield the available pack files for discovery tools."""

    for resource in _PACKS_DIR.iterdir():
        if resource.is_file() and resource.name.endswith((".json", ".jsonl")):
            yield resource


def get_pack_path(filename: str) -> Path:
    """Return the absolute path to a pack file bundled in the package."""

    resource = _PACKS_DIR / filename
    if not resource.is_file():  # pragma: no cover - validated by callers
        raise FileNotFoundError(filename)
    return resource
