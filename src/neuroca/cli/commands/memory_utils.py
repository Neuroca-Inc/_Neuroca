"""Shared helpers for the memory CLI commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rich.table import Table

from neuroca.cli.utils import ConfigError, load_config
from neuroca.core.enums import MemoryTier
from neuroca.memory.manager.memory_manager import MemoryManager


@dataclass
class MemoryCLIContext:
    """Shared CLI options resolved from the sub-command callback."""

    config_path: str | None = None
    backend: str | None = None
    embedding_dimension: int | None = None


class MemoryCLIError(RuntimeError):
    """Raised when a CLI operation encounters a user-facing error."""


def load_memory_config(config_path: str | None) -> Dict[str, Any]:
    """Load the memory manager configuration from disk when provided."""

    if not config_path:
        return {}

    try:
        loaded = load_config(config_path=config_path, required=True)
    except ConfigError as error:  # pragma: no cover - validated in integration
        raise MemoryCLIError(f"Failed to load configuration: {error}") from error

    if not isinstance(loaded, dict):
        raise MemoryCLIError("Configuration file must contain a JSON/YAML object.")

    for key in ("memory", "memory_system", "memory_manager"):
        nested = loaded.get(key)
        if isinstance(nested, dict):
            return dict(nested)

    return dict(loaded)


def merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge dictionaries for configuration overrides."""

    merged = dict(base)
    for key, value in updates.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_tier_name(tier: str | None) -> str | None:
    """Normalise tier aliases to storage keys."""

    if tier is None:
        return None
    try:
        return MemoryTier.from_string(tier).storage_key
    except ValueError as error:
        raise MemoryCLIError(str(error)) from error


def parse_metadata_pairs(pairs: Sequence[str]) -> Dict[str, Any]:
    """Parse CLI ``key=value`` pairs into a metadata filter dictionary."""

    metadata: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise MemoryCLIError(
                f"Metadata value '{pair}' must be in key=value format."
            )
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise MemoryCLIError("Metadata keys cannot be empty.")
        value = raw_value.strip()
        if not key.startswith("metadata."):
            key = f"metadata.{key}"
        metadata[key] = value
    return metadata


def load_seed_entries(path: Path) -> List[Dict[str, Any]]:
    """Load seed entries from a JSON or JSONL file."""

    if not path.exists():
        raise MemoryCLIError(f"Seed file '{path}' does not exist.")

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        entries: List[Dict[str, Any]] = []
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise MemoryCLIError(
                    f"Invalid JSON on line {line_number}: {error.msg}"
                ) from error
            entries.append(value)
    else:
        entries = parsed if isinstance(parsed, list) else [parsed]

    normalised: List[Dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict):
            normalised.append(entry)
        elif isinstance(entry, str):
            normalised.append({"content": entry})
        else:
            raise MemoryCLIError(
                "Seed entries must be JSON objects or plain strings."
            )
    return normalised


def coerce_seed_entry(
    entry: Dict[str, Any],
    *,
    default_tier: str | None,
    default_user: str | None,
    default_session: str | None,
) -> Dict[str, Any]:
    """Normalise a seed entry into ``MemoryManager.add_memory`` kwargs."""

    content = entry.get("content")
    if content is None:
        content = entry.get("text") or entry.get("memory")
    if content is None:
        raise MemoryCLIError("Seed entry missing 'content'.")

    summary = entry.get("summary")

    importance = entry.get("importance", 0.5)
    try:
        importance_value = float(importance)
    except (TypeError, ValueError) as error:
        raise MemoryCLIError(
            f"Importance must be numeric, received {importance!r}."
        ) from error
    importance_value = max(0.0, min(1.0, importance_value))

    metadata = entry.get("metadata")
    metadata_dict: Dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}
    if default_user and "user_id" not in metadata_dict:
        metadata_dict["user_id"] = default_user
    if default_session and "session_id" not in metadata_dict:
        metadata_dict["session_id"] = default_session

    tags_option = entry.get("tags")
    tags: List[str] | None
    if tags_option is None:
        tags = None
    elif isinstance(tags_option, (list, tuple, set)):
        tags = [str(tag).strip() for tag in tags_option if str(tag).strip()]
    else:
        tags = [str(tags_option).strip()]

    embedding = entry.get("embedding")
    if embedding is not None and not isinstance(embedding, (list, tuple)):
        raise MemoryCLIError("Embeddings must be provided as an array of numbers.")

    tier_override = entry.get("tier")
    initial_tier = normalize_tier_name(tier_override or default_tier)

    return {
        "content": content,
        "summary": summary,
        "importance": importance_value,
        "metadata": metadata_dict,
        "tags": tags,
        "embedding": list(embedding) if isinstance(embedding, (list, tuple)) else None,
        "initial_tier": initial_tier,
    }


def truncate(text: str, width: int = 80) -> str:
    """Utility to truncate long strings for table display."""

    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def format_tags(metadata: Dict[str, Any]) -> str:
    """Render the tag map from metadata into a comma-separated list."""

    tags_field = metadata.get("tags")
    if not isinstance(tags_field, dict):
        return ""
    enabled = [tag for tag, flag in tags_field.items() if flag]
    return ", ".join(sorted(enabled))


def get_vector_backend(manager: MemoryManager) -> Any:
    """Resolve the vector backend from the LTM tier."""

    ltm_tier = manager.ltm_storage
    backend = getattr(ltm_tier, "_backend", None)
    if backend is None:
        raise MemoryCLIError("LTM tier is not configured with a storage backend.")
    if not hasattr(backend, "reindex"):
        raise MemoryCLIError("Configured LTM backend does not support reindex operations.")
    return backend


def build_integrity_table(report: Any) -> Table:
    """Render an integrity or reindex report to a rich table."""

    table = Table(title="Vector Index Integrity", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", overflow="fold")

    table.add_row("Index entries", str(report.index_entry_count))
    table.add_row("Metadata entries", str(report.metadata_entry_count))
    table.add_row("Checked entries", str(report.checked_entry_count))
    table.add_row("Reindexed", "yes" if getattr(report, "reindexed", False) else "no")
    table.add_row("Reindexed count", str(getattr(report, "reindexed_entry_count", 0)))
    table.add_row("Missing payload", str(len(getattr(report, "missing_payload_ids", []))))
    table.add_row("Missing embedding", str(len(getattr(report, "missing_embedding_ids", []))))
    table.add_row("Dimension mismatch", str(len(getattr(report, "dimension_mismatch_ids", []))))
    table.add_row("Drifted ids", str(len(getattr(report, "drifted_ids", []))))
    table.add_row("Max drift", f"{getattr(report, 'max_drift', 0.0):.4f}")
    table.add_row("Avg drift", f"{getattr(report, 'avg_drift', 0.0):.4f}")

    issues = getattr(report, "issues", [])
    if issues:
        first_issues = ", ".join(str(issue.memory_id) for issue in issues[:5])
        table.add_row("Issue sample", first_issues)

    return table


__all__ = [
    "MemoryCLIContext",
    "MemoryCLIError",
    "load_memory_config",
    "merge_dicts",
    "normalize_tier_name",
    "parse_metadata_pairs",
    "load_seed_entries",
    "coerce_seed_entry",
    "truncate",
    "format_tags",
    "get_vector_backend",
    "build_integrity_table",
]
