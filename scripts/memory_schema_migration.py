#!/usr/bin/env python3
"""Command line helpers for migrating memory schema fields."""

from __future__ import annotations

# ruff: noqa: E402

import asyncio
import inspect
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import typer

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from neuroca.cli.commands.memory_utils import MemoryCLIError, load_memory_config
from neuroca.core.enums import MemoryTier
from neuroca.memory.factory import create_memory_system
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.migrations import adjust_embedding_dimension, ensure_summarization_package
from neuroca.memory.models.memory_item import MemoryItem

app = typer.Typer(help="Run schema migrations on persisted memory data.")


@dataclass
class TierMigrationStats:
    """Simple container for per-tier migration counts."""

    processed: int = 0
    summary_updates: int = 0
    embedding_updates: int = 0

    def register_summary(self) -> None:
        self.summary_updates += 1

    def register_embedding(self) -> None:
        self.embedding_updates += 1


async def _yield_memory_items(tier: Any, batch_size: int) -> Iterable[MemoryItem]:
    """Iterate over all memory items stored in a tier."""

    search = getattr(tier, "search", None)
    if callable(search):
        offset = 0
        while True:
            try:
                results = await search(query=None, limit=batch_size, offset=offset)
            except TypeError:
                results = await search(limit=batch_size, offset=offset)

            entries = getattr(results, "results", results)
            if not entries:
                break

            for entry in entries:
                candidate = getattr(entry, "memory", entry)
                if isinstance(candidate, MemoryItem):
                    yield MemoryItem.model_validate(candidate.model_dump())
                elif isinstance(candidate, Mapping):
                    yield MemoryItem.model_validate(dict(candidate))

            if len(entries) < batch_size:
                break
            offset += len(entries)
        return

    list_all = getattr(tier, "list_all", None)
    if callable(list_all):
        records = list_all()
        if inspect.isawaitable(records):
            records = await records
        for entry in records or []:
            if isinstance(entry, MemoryItem):
                yield MemoryItem.model_validate(entry.model_dump())
            elif isinstance(entry, Mapping):
                yield MemoryItem.model_validate(dict(entry))
        return

    raise RuntimeError("Tier does not expose a supported bulk retrieval method.")


async def _process_tier(
    manager: MemoryManager,
    tier_name: str,
    *,
    batch_size: int,
    migrate_summary: bool,
    migrate_embedding: bool,
    target_dimension: Optional[int],
    dry_run: bool,
    backups: List[Dict[str, Any]],
) -> TierMigrationStats:
    """Apply schema migrations to a single tier."""

    tier = manager._get_tier_by_name(tier_name)
    stats = TierMigrationStats()

    async for memory in _yield_memory_items(tier, batch_size):
        stats.processed += 1
        before = memory.model_dump(mode="json")

        summary_changed = False
        embedding_changed = False

        if migrate_summary:
            summary_changed = ensure_summarization_package(memory)
            if summary_changed:
                stats.register_summary()

        if migrate_embedding:
            embedding_changed = adjust_embedding_dimension(memory, target_dimension)
            if embedding_changed:
                stats.register_embedding()

        if summary_changed or embedding_changed:
            backups.append({
                "tier": tier_name,
                "id": memory.id,
                "data": before,
            })
            if not dry_run:
                await tier._backend.update(memory.id, memory.model_dump(mode="json"))

    return stats


def _normalise_tier_names(raw_tiers: Iterable[str]) -> List[str]:
    """Convert user supplied tier labels to canonical storage keys."""

    normalised: List[str] = []
    for tier in raw_tiers:
        resolved = MemoryTier.from_string(tier)
        if resolved.storage_key not in normalised:
            normalised.append(resolved.storage_key)
    return normalised


def _default_backup_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("backups") / f"memory_schema_backup_{timestamp}.json"


def _write_backup(path: Path, metadata: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    payload = {
        "metadata": metadata,
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


async def _run_with_manager(
    config_path: Optional[Path],
    backend_override: Optional[str],
    operation,
):
    try:
        config = load_memory_config(str(config_path) if config_path else None)
    except MemoryCLIError as error:  # pragma: no cover - configuration validated in tests
        raise typer.BadParameter(str(error)) from error

    manager = create_memory_system(
        backend_type=backend_override,
        config=config or None,
    )

    await manager.initialize()
    try:
        return await operation(manager)
    finally:
        await manager.shutdown()


@app.command()
def upgrade(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a memory configuration file used to instantiate the manager.",
    ),
    backend: Optional[str] = typer.Option(
        None,
        "--backend",
        help="Override the storage backend for all tiers during migration.",
    ),
    tier: List[str] = typer.Option(
        ["mtm", "ltm"],
        "--tier",
        "-t",
        help="Memory tier to migrate (repeat for multiple).",
    ),
    target_dimension: Optional[int] = typer.Option(
        None,
        "--target-dimension",
        help="Adjust embeddings to the provided dimension (omit to skip embedding migration).",
    ),
    batch_size: int = typer.Option(
        200,
        "--batch-size",
        help="Number of records to inspect per batch when scanning a tier.",
        min=1,
    ),
    backup: Optional[Path] = typer.Option(
        None,
        "--backup",
        help="Optional path for the backup JSON file (auto-generated when omitted).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the planned changes without writing them to the storage backends.",
    ),
    skip_summary: bool = typer.Option(
        False,
        "--skip-summary",
        help="Do not migrate legacy summarisation metadata.",
    ),
    skip_embedding: bool = typer.Option(
        False,
        "--skip-embedding",
        help="Do not adjust stored embedding vectors.",
    ),
) -> None:
    """Upgrade persisted memories to the latest summarisation and embedding schema."""

    migrate_summary = not skip_summary
    migrate_embedding = not skip_embedding and target_dimension is not None

    if not migrate_summary and not migrate_embedding:
        typer.echo("Nothing to do: both summary and embedding migrations are disabled.")
        raise typer.Exit(code=0)

    tiers = _normalise_tier_names(tier or ["mtm", "ltm"])
    backup_path = backup or _default_backup_path()
    backup_records: List[Dict[str, Any]] = []
    tier_reports: Dict[str, TierMigrationStats] = {}

    async def _run(manager: MemoryManager) -> None:
        for tier_name in tiers:
            stats = await _process_tier(
                manager,
                tier_name,
                batch_size=batch_size,
                migrate_summary=migrate_summary,
                migrate_embedding=migrate_embedding,
                target_dimension=target_dimension,
                dry_run=dry_run,
                backups=backup_records,
            )
            tier_reports[tier_name] = stats

    asyncio.run(_run_with_manager(config, backend, _run))

    total_processed = sum(report.processed for report in tier_reports.values())
    total_summary = sum(report.summary_updates for report in tier_reports.values())
    total_embedding = sum(report.embedding_updates for report in tier_reports.values())

    typer.echo("Migration summary:")
    for tier_name, report in tier_reports.items():
        typer.echo(
            f"  - {tier_name}: processed={report.processed}, "
            f"summary_updates={report.summary_updates}, embedding_updates={report.embedding_updates}"
        )

    typer.echo(
        f"Totals: processed={total_processed}, "
        f"summary_updates={total_summary}, embedding_updates={total_embedding}"
    )

    if dry_run:
        typer.echo("Dry-run mode enabled; no changes were written and no backup was created.")
        raise typer.Exit(code=0)

    if not backup_records:
        typer.echo("No changes detected; skipping backup creation.")
        raise typer.Exit(code=0)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tiers": tiers,
        "target_dimension": target_dimension,
    }
    _write_backup(backup_path, metadata, backup_records)
    typer.echo(f"Backup written to {backup_path}")


@app.command()
def rollback(
    backup: Path = typer.Argument(..., help="Path to the backup file generated by the upgrade command."),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file used to instantiate the memory manager.",
    ),
    backend: Optional[str] = typer.Option(
        None,
        "--backend",
        help="Override the storage backend while restoring the backup.",
    ),
) -> None:
    """Restore memories from a migration backup."""

    if not backup.exists():
        raise typer.BadParameter(f"Backup file '{backup}' does not exist.")

    try:
        payload = json.loads(backup.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise typer.BadParameter(f"Backup file is not valid JSON: {error}") from error

    records = payload.get("records", [])
    if not isinstance(records, list):
        raise typer.BadParameter("Backup payload is missing the 'records' array.")

    restored: List[str] = []

    async def _run(manager: MemoryManager) -> None:
        for entry in records:
            if not isinstance(entry, Mapping):
                continue
            tier_name = MemoryTier.from_string(str(entry.get("tier", "ltm"))).storage_key
            memory_id = entry.get("id")
            data = entry.get("data")
            if not memory_id or not isinstance(data, Mapping):
                continue
            tier = manager._get_tier_by_name(tier_name)
            await tier._backend.update(str(memory_id), dict(data))
            restored.append(str(memory_id))

    asyncio.run(_run_with_manager(config, backend, _run))

    typer.echo(f"Restored {len(restored)} memories from {backup}.")


if __name__ == "__main__":
    app()
