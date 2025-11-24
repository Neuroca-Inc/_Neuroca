"""Migration script wrapper utilities.

Purpose:
    Provide an object model that encapsulates individual migration scripts,
    handling dynamic loading, validation, and execution lifecycle concerns.
External Dependencies:
    Imports standard-library modules only. Migration scripts themselves may
    depend on database drivers available in the environment.
Fallback Semantics:
    No automated fallback is provided; caller code is expected to catch and
    process raised exceptions to determine remediation paths.
Timeout Strategy:
    Execution timeout handling is delegated to the underlying migration script
    and database connector. This module does not enforce additional timeouts.
"""

from __future__ import annotations

import importlib.util
import logging
import time
from pathlib import Path
from typing import Any

from .errors import MigrationError, MigrationExecutionError

logger = logging.getLogger(__name__)


class Migration:
    """Runtime representation of a migration script on disk.

    Summary:
        Encapsulates the metadata and scripted operations associated with a
        single migration, offering helper methods to load and invoke upgrade or
        downgrade routines safely.
    Parameters:
        version: Integer timestamp representing the migration version.
        name: Human-readable migration identifier derived from the filename.
        path: Filesystem path to the migration Python module.
    Attributes:
        version: Stored migration version identifier.
        name: Descriptive name of the migration.
        path: Path to the migration module file.
        module: Loaded Python module containing ``upgrade`` and ``downgrade``.
    Raises:
        MigrationError: Raised during loading when the underlying module is
            missing or lacks the required callables.
    Side Effects:
        Loading a migration imports Python code dynamically from disk.
    Timeout/Retries:
        No explicit timeout handling or retry logic is implemented here; any
        such behaviour must be handled by the caller or within the script.
    """

    def __init__(self, version: int, name: str, path: Path) -> None:
        self.version = version
        self.name = name
        self.path = path
        self.module = None

    def load(self) -> None:
        """Import the migration module, validating required callables.

        Summary:
            Dynamically imports the migration file and verifies that both
            ``upgrade`` and ``downgrade`` functions are exposed as callables.
        Parameters:
            None.
        Returns:
            None.
        Raises:
            MigrationError: Propagated when import fails or required functions
                are missing from the module.
        Side Effects:
            Caches the loaded module on ``self.module`` for later reuse.
        Timeout/Retries:
            No timeout or retry handling is provided; import latency depends on
            Python's import mechanism.
        """

        try:
            module_name = self.path.stem
            spec = importlib.util.spec_from_file_location(module_name, self.path)
            if spec is None or spec.loader is None:
                raise MigrationError(f"Failed to create module spec for {self.path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "upgrade") or not callable(module.upgrade):
                raise MigrationError(
                    f"Migration {self.name} is missing the 'upgrade' function"
                )

            if not hasattr(module, "downgrade") or not callable(module.downgrade):
                raise MigrationError(
                    f"Migration {self.name} is missing the 'downgrade' function"
                )

            self.module = module
        except ImportError as exc:  # pragma: no cover - defensive
            raise MigrationError(f"Failed to import migration {self.name}: {exc}") from exc

    def upgrade(self, connection: Any) -> None:
        """Execute the upgrade routine for this migration.

        Summary:
            Ensures the migration module is loaded and then invokes its
            ``upgrade`` callable, timing execution for telemetry purposes.
        Parameters:
            connection: Database connection object supplied to the migration.
        Returns:
            None.
        Raises:
            MigrationExecutionError: Raised when the underlying upgrade function
                fails.
        Side Effects:
            Executes arbitrary database changes as defined by the migration.
        Timeout/Retries:
            No retry is attempted; any timeout configuration must be implemented
            by the migration script or connection.
        """

        if not self.module:
            self.load()

        try:
            logger.info("Applying migration %s (%s)", self.version, self.name)
            start_time = time.time()
            self.module.upgrade(connection)
            duration = time.time() - start_time
            logger.info(
                "Migration %s applied successfully in %.2fs", self.version, duration
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Migration %s failed: %s", self.version, exc)
            raise MigrationExecutionError(
                f"Failed to apply migration {self.name}: {exc}"
            ) from exc

    def downgrade(self, connection: Any) -> None:
        """Execute the downgrade routine for this migration.

        Summary:
            Loads the migration module if necessary and invokes the ``downgrade``
            callable to roll back database changes.
        Parameters:
            connection: Database connection object supplied to the migration.
        Returns:
            None.
        Raises:
            MigrationExecutionError: Raised when the downgrade function fails.
        Side Effects:
            Executes database modifications intended to reverse the upgrade.
        Timeout/Retries:
            Timeout configuration is delegated to the migration implementation;
            this method performs no retries.
        """

        if not self.module:
            self.load()

        try:
            logger.info("Rolling back migration %s (%s)", self.version, self.name)
            start_time = time.time()
            self.module.downgrade(connection)
            duration = time.time() - start_time
            logger.info(
                "Migration %s rolled back successfully in %.2fs",
                self.version,
                duration,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Migration %s rollback failed: %s", self.version, exc)
            raise MigrationExecutionError(
                f"Failed to roll back migration {self.name}: {exc}"
            ) from exc


__all__ = ["Migration"]
