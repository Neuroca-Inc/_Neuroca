"""Snapshot helpers for the memory soak-test harness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.manager.memory_manager import MemoryManager

from .manager import _default_manager_config


async def _export_memories(
    manager: MemoryManager,
    identifiers: Iterable[str],
    destination: Path,
) -> None:
    """Persist the selected memories to ``destination`` as JSON.

    Args:
        manager: Memory manager providing retrieval operations.
        identifiers: Iterable of memory identifiers to capture.
        destination: Path where the JSON snapshot will be written.

    Side Effects:
        Writes the serialised snapshot to disk.
    """

    records: List[Mapping[str, Any]] = []
    for memory_id in identifiers:
        try:
            memory = await manager.retrieve_memory(memory_id)
        except Exception:  # noqa: BLE001
            continue

        if memory is None:
            continue

        if hasattr(memory, "model_dump"):
            payload = memory.model_dump(mode="json")  # type: ignore[assignment]
        elif hasattr(memory, "dict"):
            payload = memory.dict()  # type: ignore[assignment]
        elif isinstance(memory, Mapping):
            payload = dict(memory)
        else:
            payload = {"content": str(memory)}

        payload["id"] = str(memory_id)
        records.append(payload)

    destination.write_text(json.dumps(records, indent=2), encoding="utf-8")


async def _restore_snapshot(snapshot: Path) -> int:
    """Restore memories from ``snapshot`` into a fresh manager instance.

    Args:
        snapshot: Path to a JSON snapshot created by :func:`_export_memories`.

    Returns:
        Number of memories reconstructed in the new manager instance.
    """

    data = json.loads(snapshot.read_text(encoding="utf-8"))
    manager = MemoryManager(
        backend_type=BackendType.MEMORY,
        config=_default_manager_config(0.0),
    )
    await manager.initialize()
    restored = 0
    try:
        for record in data:
            content = record.get("content") or {}
            text = ""
            if isinstance(content, Mapping):
                text = str(content.get("text") or content.get("summary") or "")
            elif isinstance(content, str):
                text = content
            metadata = record.get("metadata")
            tags: Sequence[str] = []
            if isinstance(metadata, Mapping):
                candidate_tags = metadata.get("tags")
                if isinstance(candidate_tags, Mapping):
                    tags = [str(key) for key in candidate_tags.keys()]
                elif isinstance(candidate_tags, Sequence):
                    tags = [str(tag) for tag in candidate_tags]
            try:
                await manager.add_memory(
                    content=text or f"restored-memory-{restored}",
                    summary=record.get("summary") or f"restored-{restored}",
                    metadata={"source": "snapshot"},
                    tags=list(tags),
                )
            except Exception:  # noqa: BLE001
                continue
            restored += 1
    finally:
        await manager.shutdown()

    return restored


async def _snapshot_and_restore(
    manager: MemoryManager,
    identifiers: Iterable[str],
    backup_dir: Path | None,
) -> Tuple[Optional[Path], bool]:
    """Create a snapshot of ``identifiers`` and verify the restore workflow.

    Args:
        manager: Memory manager providing retrieval operations.
        identifiers: Iterable of memory identifiers to capture.
        backup_dir: Optional directory where the snapshot will be preserved.

    Returns:
        Tuple containing the snapshot path (when persisted) and a boolean flag
        indicating whether the restore reconstructed all memories.
    """

    identifiers = list(identifiers)
    if not identifiers:
        return None, True

    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = backup_dir / "memory_snapshot.json"
        await _export_memories(manager, identifiers, snapshot_path)
        restored = await _restore_snapshot(snapshot_path)
        return snapshot_path, restored == len(identifiers)

    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot_path = Path(temp_dir) / "memory_snapshot.json"
        await _export_memories(manager, identifiers, snapshot_path)
        restored = await _restore_snapshot(snapshot_path)
        return None, restored == len(identifiers)


__all__ = [
    "_export_memories",
    "_restore_snapshot",
    "_snapshot_and_restore",
]
