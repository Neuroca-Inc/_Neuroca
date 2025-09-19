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
]
