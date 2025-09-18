"""Developer-facing memory seeding helpers and bundled sample packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from . import packs as _packs

__all__ = [
    "SamplePack",
    "list_sample_packs",
    "get_sample_pack",
    "load_sample_pack",
    "write_sample_pack",
]


@dataclass(frozen=True)
class SamplePack:
    """Metadata describing a bundled developer seeding scenario."""

    slug: str
    title: str
    description: str
    filename: str
    default_user: str
    default_session: str
    tags: Tuple[str, ...] = ()

    @property
    def resource_path(self) -> Path:
        """Return the absolute resource path for the pack file."""

        return _packs.get_pack_path(self.filename)

    def recommended_seed_args(self) -> Tuple[str, ...]:
        """Return default CLI arguments to seed the pack quickly."""

        args = ["--user", self.default_user]
        if self.default_session:
            args.extend(["--session", self.default_session])
        return tuple(args)


_SAMPLE_PACKS: Tuple[SamplePack, ...] = (
    SamplePack(
        slug="collaborative-brainstorm",
        title="Collaborative Brainstorm",
        description=(
            "Captures a multi-stage product ideation workshop including benchmarks, "
            "assigned spikes, and retrospective actions to exercise tier transitions."
        ),
        filename="collaborative_brainstorm.jsonl",
        default_user="team-alpha",
        default_session="brainstorm-2024q4",
        tags=("collaboration", "planning", "retro"),
    ),
    SamplePack(
        slug="customer-support-playbook",
        title="Customer Support Playbook",
        description=(
            "Follows an enterprise support incident from intake through remediation, "
            "documentation, and post-mortem to validate lifecycle retention."
        ),
        filename="customer_support_playbook.jsonl",
        default_user="support-pod-a",
        default_session="ticket-58271",
        tags=("support", "incident-response", "runbook"),
    ),
)


def list_sample_packs() -> Tuple[SamplePack, ...]:
    """Return all available sample packs in a deterministic order."""

    return _SAMPLE_PACKS


def get_sample_pack(slug: str) -> SamplePack:
    """Return the sample pack matching ``slug`` or raise ``KeyError``."""

    for pack in _SAMPLE_PACKS:
        if pack.slug == slug:
            return pack
    raise KeyError(slug)


def load_sample_pack(slug: str) -> str:
    """Load the raw text contents for the specified sample pack."""

    pack = get_sample_pack(slug)
    return pack.resource_path.read_text(encoding="utf-8")


def write_sample_pack(slug: str, destination: Path, *, overwrite: bool = False) -> Path:
    """Write the sample pack to ``destination`` and return the resulting path."""

    pack = get_sample_pack(slug)
    destination = destination.expanduser()
    if destination.is_dir():
        destination = destination / pack.filename

    if destination.exists() and not overwrite:
        raise FileExistsError(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    # ``pack.resource_path`` already resolves through importlib resources; use a
    # simple read/write so paths behave consistently in tests.
    destination.write_text(pack.resource_path.read_text(encoding="utf-8"), encoding="utf-8")
    return destination
