"""Database migration orchestration package.

Purpose:
    Aggregate migration utilities including error types, migration wrappers, and
    the high-level manager responsible for applying or rolling back schema
    changes.
External Dependencies:
    Delegates to database connection objects supplied by callers; no direct CLI
    or HTTP interactions are initiated here.
Fallback Semantics:
    Exceptions raised within submodules propagate to callers so they can decide
    on remediation strategies.
Timeout Strategy:
    Timeout handling is delegated to the configured database connections. The
    package itself introduces no additional timeout logic.
"""

from __future__ import annotations

from .errors import (
    MigrationDependencyError,
    MigrationError,
    MigrationExecutionError,
    MigrationVersionError,
)
from pathlib import Path
from typing import Any, Optional

from .manager import MIGRATION_VERSION_PATTERN, MigrationManager, create_migration
from .migration import Migration

__all__ = [
    "Migration",
    "MigrationManager",
    "MigrationError",
    "MigrationVersionError",
    "MigrationExecutionError",
    "MigrationDependencyError",
    "create_migration",
    "MIGRATION_VERSION_PATTERN",
    "upgrade",
    "downgrade",
]


def upgrade(
    connection: Any,
    migrations_dir: Optional[Path | str] = None,
    target_version: Optional[int] = None,
) -> None:
    """Summary: Apply migrations up to ``target_version`` using the manager.
    Parameters:
        connection: Context-manageable database connection supplied by caller.
        migrations_dir: Optional directory housing migration scripts; defaults to
            the package directory.
        target_version: Optional highest version to apply; ``None`` applies all
            pending migrations.
    Returns:
        None.
    Raises:
        MigrationError: Propagated when migration execution or bookkeeping fails.
        MigrationVersionError: Raised when ``target_version`` is unknown.
    Side Effects:
        Executes migration ``upgrade`` routines and records metadata.
    Timeout/Retries:
        Delegated to the provided database connection implementation.
    """

    manager = MigrationManager(connection, migrations_dir=migrations_dir)
    manager.migrate(target_version=target_version)


def downgrade(
    connection: Any,
    migrations_dir: Optional[Path | str] = None,
    target_version: Optional[int] = None,
    steps: int = 1,
) -> None:
    """Summary: Roll back migrations to ``target_version`` or by ``steps``.
    Parameters:
        connection: Context-manageable database connection supplied by caller.
        migrations_dir: Optional directory containing migration scripts.
        target_version: Optional version to retain after rollback (defaults to
            removing ``steps`` migrations when ``None``).
        steps: Number of migrations to undo when ``target_version`` is absent.
    Returns:
        None.
    Raises:
        MigrationError: Propagated when downgrade execution or bookkeeping fails.
        MigrationVersionError: Raised for unknown ``target_version`` values.
    Side Effects:
        Executes migration ``downgrade`` routines and updates the tracking table.
    Timeout/Retries:
        Managed wholly by the supplied database connection.
    """

    manager = MigrationManager(connection, migrations_dir=migrations_dir)
    manager.rollback(target_version=target_version, steps=steps)
