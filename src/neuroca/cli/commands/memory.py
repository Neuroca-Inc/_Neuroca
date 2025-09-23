"""Operational CLI commands for inspecting and managing the memory system."""


from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from neuroca.cli.commands.memory_utils import (
    MemoryCLIContext,
    MemoryCLIError,
    build_integrity_table,
    coerce_seed_entry,
    format_tags,
    get_vector_backend,
    load_seed_entries,
    normalize_tier_name,
    parse_metadata_pairs,
    run_memory_operation,
    truncate,
)
from neuroca.cli.utils import setup_logging
from neuroca.memory.factory import create_memory_system
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.seeding import (
    get_sample_pack,
    list_sample_packs,
    write_sample_pack,
)

logger = setup_logging("memory")
console = Console()

memory_app = typer.Typer(name="memory", help="Inspect and operate on the memory tiers.")
sample_pack_app = typer.Typer(
    name="sample-packs",
    help="Discover and export bundled developer seeding scenarios.",
)
memory_app.add_typer(sample_pack_app, name="sample-packs")


@sample_pack_app.command("list")
def list_sample_packs_command() -> None:
    """Display bundled sample packs with recommended usage."""

    packs = list_sample_packs()
    if not packs:
        console.print("[yellow]No bundled sample packs available.[/]")
        return

    table = Table(title="Memory Sample Packs", show_lines=False)
    table.add_column("Slug", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Tags", style="magenta")
    table.add_column("Default CLI Args")
    table.add_column("Description")

    for pack in packs:
        tags = ", ".join(pack.tags) if pack.tags else "-"
        defaults = " ".join(pack.recommended_seed_args()) or "-"
        table.add_row(
            pack.slug,
            pack.title,
            tags,
            defaults,
            truncate(pack.description, width=80),
        )

    console.print(table)
    # Print a usage hint including default args so users see concrete flags
    with contextlib.suppress(Exception):
        first = packs[0]
        console.print(
            f"\n[blue]Hint:[/] Use default args when seeding, e.g.: --user {first.default_user}"
            + (f" --session {first.default_session}" if first.default_session else "")
        )


@sample_pack_app.command("export")
def export_sample_pack(
    slug: Annotated[str, typer.Argument(help="Slug of the sample pack to export.")],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Destination file or directory for the exported pack.",
        ),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite the destination file if it already exists.",
        ),
    ] = False,
) -> None:
    """Export a bundled sample pack to a local file."""

    try:
        pack = get_sample_pack(slug)
    except KeyError:
        console.print(
            f"[red]Unknown sample pack '{slug}'. Use 'memory sample-packs list' to view options.[/]"
        )
        raise typer.Exit(code=1) from None

    destination = output or Path.cwd() / pack.filename

    try:
        exported_path = write_sample_pack(pack.slug, destination, overwrite=overwrite)
    except FileExistsError:
        console.print(
            f"[red]Destination '{destination}' already exists. Use --overwrite to replace it.[/]"
        )
        raise typer.Exit(code=1) from None

    console.print(
        f"[green]Exported '{pack.title}' sample pack to {exported_path}.[/]"
    )
    seed_hint = " ".join(pack.recommended_seed_args())
    console.print(
        f"[blue]Hint:[/] nca memory seed {exported_path} {seed_hint}".rstrip()
    )


def _get_context(ctx: typer.Context) -> MemoryCLIContext:
    """Return the context object initialised by the callback."""

    obj = ctx.obj
    if isinstance(obj, MemoryCLIContext):
        return obj
    if isinstance(obj, dict):
        context = MemoryCLIContext(
            config_path=obj.get("config_path"),
            backend=obj.get("backend"),
            embedding_dimension=obj.get("embedding_dimension"),
        )
        ctx.obj = context
        return context
    context = MemoryCLIContext()
    ctx.obj = context
    return context


def _run_cli_coroutine(task: Awaitable[Any]) -> Any:
    """Execute an async operation within the CLI event loop."""

    try:
        return asyncio.run(task)
    except KeyboardInterrupt as exc:  # pragma: no cover - interactive safeguard
        console.print("[red]Operation cancelled by user.[/]")
        raise typer.Exit(code=130) from exc


def _execute_memory_command(
    ctx: typer.Context,
    operation: Callable[[MemoryManager], Awaitable[Any]],
) -> Any:
    """Helper that resolves context, runs the operation, and handles errors."""

    context = _get_context(ctx)
    try:
        return _run_cli_coroutine(
            run_memory_operation(
                context,
                operation,
                factory=create_memory_system,
            )
        )
    except MemoryCLIError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error
    except Exception as error:  # noqa: BLE001 - surface unexpected failures
        logger.exception("Memory command failed")
        console.print(f"[red]Memory command failed: {error}[/]")
        raise typer.Exit(code=1) from error


@memory_app.callback()
def memory_callback(
    ctx: typer.Context,
    config: Annotated[Optional[Path], typer.Option(
        "--config",
        "-c",
        help="Path to a memory manager configuration file (YAML or JSON).",
    )] = None,
    backend: Annotated[Optional[str], typer.Option(
        "--backend",
        help="Override the storage backend for all tiers during the session.",
    )] = None,
    embedding_dimension: Annotated[Optional[int], typer.Option(
        "--embedding-dimension",
        help="Override the embedding dimension used when constructing the manager.",
    )] = None,
) -> None:
    """Initialise shared options for subsequent memory commands."""

    ctx.obj = MemoryCLIContext(
        config_path=str(config) if config else None,
        backend=backend,
        embedding_dimension=embedding_dimension,
    )


@memory_app.command("seed")
def seed_memories(
    ctx: typer.Context,
    source: Annotated[Path, typer.Argument(help="Seed file containing JSON or JSONL memories.")],
    tier: Annotated[Optional[str], typer.Option(
        "--tier",
        "-t",
        help="Initial tier for seeded memories (defaults to manager configuration).",
    )] = None,
    user_id: Annotated[Optional[str], typer.Option(
        "--user",
        "-u",
        help="Default user identifier applied to seeded memories.",
    )] = None,
    session_id: Annotated[Optional[str], typer.Option(
        "--session",
        help="Default session identifier applied to seeded memories.",
    )] = None,
) -> None:
    """Seed one or more memories from a JSON payload."""

    try:
        entries = load_seed_entries(source)
        default_tier = normalize_tier_name(tier)
    except MemoryCLIError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    if not entries:
        console.print("[yellow]Seed file contained no entries.[/]")
        return

    async def _seed(manager: MemoryManager) -> tuple[List[str], List[tuple[int, str]]]:
        successes: List[str] = []
        failures: List[tuple[int, str]] = []
        for index, entry in enumerate(entries, start=1):
            try:
                payload = coerce_seed_entry(
                    entry,
                    default_tier=default_tier,
                    default_user=user_id,
                    default_session=session_id,
                )
            except MemoryCLIError as error:
                failures.append((index, str(error)))
                continue

            try:
                stored_id = await manager.add_memory(**payload)
            except Exception as error:  # noqa: BLE001 - surface to user
                logger.exception("Failed to seed memory entry %s", index)
                failures.append((index, str(error)))
                continue

            successes.append(stored_id)

        return successes, failures

    stored_ids, failures = _execute_memory_command(ctx, _seed)

    console.print(f"[green]Seeded {len(stored_ids)} memories successfully.[/]")

    if failures:
        console.print(f"[yellow]{len(failures)} entries failed to seed. Details:[/]")
        for index, message in failures:
            console.print(f"  • Entry {index}: {message}")
        raise typer.Exit(code=1)


@memory_app.command("inspect")
def inspect_memories(
    ctx: typer.Context,
    tier: Annotated[str, typer.Option(
        "--tier",
        "-t",
        help="Tier to inspect (working/stm, episodic/mtm, semantic/ltm, or all).",
        show_default=True,
    )] = "all",
    limit: Annotated[int, typer.Option(
        "--limit",
        "-l",
        help="Maximum number of memories to display.",
        min=1,
        show_default=True,
    )] = 20,
    query: Annotated[Optional[str], typer.Option(
        "--query",
        "-q",
        help="Optional text query to filter memories.",
    )] = None,
    tags: Annotated[List[str], typer.Option(
        "--tag",
        "-T",
        help="Filter results by tag (repeat for multiple tags).",
    )] = [],
    metadata: Annotated[List[str], typer.Option(
        "--metadata",
        "-m",
        help="Filter results using metadata key=value pairs.",
    )] = [],
) -> None:
    """Inspect memories from one or all tiers with optional filters."""

    try:
        tiers = None if tier == "all" else [normalize_tier_name(tier)]
        metadata_filters = parse_metadata_pairs(metadata) if metadata else None
    except MemoryCLIError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    async def _inspect(manager: MemoryManager) -> List[Dict[str, Any]]:
        return await manager.search_memories(
            query=query,
            tags=tags or None,
            metadata_filters=metadata_filters,
            limit=limit,
            tiers=tiers,
            scope=MemoryRetrievalScope.system(),
        )

    results: List[Dict[str, Any]] = _execute_memory_command(ctx, _inspect)

    if not results:
        console.print("[yellow]No memories matched the provided criteria.[/]")
        return

    table = Table(title="Memory Inspection Results")
    table.add_column("ID", style="cyan", overflow="fold")
    table.add_column("Tier", style="magenta")
    table.add_column("Content", style="green", overflow="fold")
    table.add_column("Importance", style="yellow")
    table.add_column("Tags", style="blue", overflow="fold")

    for item in results:
        content = item.get("content", {})
        metadata_obj = item.get("metadata", {})

        text_candidate = None
        if isinstance(content, dict):
            for key in ("summary", "text"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    text_candidate = value.strip()
                    break
            if text_candidate is None:
                json_blob = content.get("json_data")
                if json_blob:
                    text_candidate = json.dumps(json_blob, ensure_ascii=False)
            if text_candidate is None and content.get("raw_content") is not None:
                text_candidate = str(content["raw_content"])

        rendered_content = truncate(text_candidate or "[no content]")
        rendered_tags = format_tags(metadata_obj)
        importance = metadata_obj.get("importance")
        importance_str = f"{importance:.2f}" if isinstance(importance, (int, float)) else ""
        tier_label = item.get("tier") or (tiers[0] if tiers else "")

        table.add_row(
            str(item.get("id", "")),
            tier_label,
            rendered_content,
            importance_str,
            rendered_tags,
        )

    console.print(table)


@memory_app.command("consolidate")
def consolidate_memory(
    ctx: typer.Context,
    memory_id: Annotated[str, typer.Argument(help="Identifier of the memory to consolidate.")],
    source: Annotated[str, typer.Option(
        "--source",
        "-s",
        help="Source tier of the memory (working/stm or episodic/mtm).",
    )],
    target: Annotated[str, typer.Option(
        "--target",
        "-t",
        help="Target tier for consolidation (episodic/mtm or semantic/ltm).",
    )],
    metadata: Annotated[List[str], typer.Option(
        "--metadata",
        "-m",
        help="Additional metadata to apply during consolidation (key=value).",
    )] = [],
    tags: Annotated[List[str], typer.Option(
        "--tag",
        "-T",
        help="Tags to add during consolidation (repeat for multiple).",
    )] = [],
) -> None:
    """Force a consolidation between tiers using the transactional pipeline."""

    try:
        additional_metadata = parse_metadata_pairs(metadata) if metadata else {}
        if tags:
            tag_map = additional_metadata.setdefault("tags", {})
            if not isinstance(tag_map, dict):
                raise MemoryCLIError("'tags' metadata must not conflict with other fields.")
            for tag in tags:
                tag_map[str(tag)] = True
        source_tier = normalize_tier_name(source) or "stm"
        target_tier = normalize_tier_name(target) or "mtm"
    except MemoryCLIError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    async def _consolidate(manager: MemoryManager) -> str | None:
        return await manager.consolidate_memory(
            memory_id,
            source_tier=source_tier,
            target_tier=target_tier,
            additional_metadata=additional_metadata or None,
        )

    new_id = _execute_memory_command(ctx, _consolidate)

    final_id = new_id or memory_id
    console.print(
        f"[green]Consolidation succeeded. Memory now stored as '{final_id}'.[/]"
    )


@memory_app.command("reindex")
def reindex_vector_store(
    ctx: typer.Context,
    ids: Annotated[List[str], typer.Option(
        "--id",
        help="Specific memory IDs to rebuild (repeat for multiple).",
    )] = [],
    full_refresh: Annotated[bool, typer.Option(
        "--full-refresh",
        help="Rebuild every vector entry from metadata regardless of drift.",
    )] = False,
    drift_threshold: Annotated[float, typer.Option(
        "--drift-threshold",
        help="Drift threshold used when evaluating embeddings.",
        show_default=True,
    )] = 0.1,
    check_only: Annotated[bool, typer.Option(
        "--check-only",
        help="Only run integrity checks without rebuilding the index.",
    )] = False,
    sample_size: Annotated[Optional[int], typer.Option(
        "--sample-size",
        help="Optional sample size when evaluating drift.",
    )] = None,
) -> None:
    """Rebuild or inspect the vector index backing the LTM tier."""

    target_ids = ids or None

    async def _reindex(manager: MemoryManager) -> Any:
        backend = get_vector_backend(manager)
        if check_only:
            return await backend.check_index_integrity(
                drift_threshold=drift_threshold,
                sample_size=sample_size,
            )
        return await backend.reindex(
            target_ids=target_ids,
            full_refresh=full_refresh,
            drift_threshold=drift_threshold,
        )

    report = _execute_memory_command(ctx, _reindex)
    console.print(build_integrity_table(report))
