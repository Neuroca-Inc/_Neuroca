"""Sample memory seed packs for developer scenarios."""

from importlib import resources
from pathlib import Path
from typing import Iterable

__all__ = ["iter_pack_files", "get_pack_path"]


def iter_pack_files() -> Iterable[Path]:
    """Yield the available pack files for discovery tools."""

    package = resources.files(__name__)
    for resource in package.iterdir():
        if resource.is_file() and resource.name.endswith((".json", ".jsonl")):
            yield Path(resource)


def get_pack_path(filename: str) -> Path:
    """Return the absolute path to a pack file bundled in the package."""

    package = resources.files(__name__)
    resource = package.joinpath(filename)
    if not resource.is_file():  # pragma: no cover - validated by callers
        raise FileNotFoundError(filename)
    return Path(resource)
