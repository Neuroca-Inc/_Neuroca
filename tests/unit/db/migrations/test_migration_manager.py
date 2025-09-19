"""Migration manager integration tests with SQLite backing.

Purpose:
    Exercise `MigrationManager` against a lightweight SQLite database to ensure
    migrations are applied, recorded, and rolled back correctly.
External Dependencies:
    Relies on the standard library `sqlite3` module only; no CLI or HTTP calls
    are performed.
Fallback Semantics:
    Tests assert on raised exceptions; no fallback logic is applied here.
Timeout Strategy:
    Default pytest timeouts apply. The scenarios execute synchronously without
    additional timeout controls.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest

from neuroca.db.migrations.errors import MigrationVersionError
from neuroca.db.migrations.manager import MigrationManager


class SQLiteConnectionWrapper:
    """Summary: Minimal context manager delegating to sqlite3 connections.
    Parameters:
        db_path: Filesystem path to the SQLite database file.
    Attributes:
        db_path: Stored path used for subsequent connections.
    Side Effects:
        Opens and closes SQLite connections for each context usage.
    Timeout/Retries:
        Inherits default sqlite3 behaviour with no additional retries.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        """Summary: Open the SQLite database connection for a migration step.
        Returns:
            sqlite3.Connection: Active database connection.
        Raises:
            sqlite3.Error: Propagated if the connection cannot be opened.
        Side Effects:
            Establishes a new connection to the target database file.
        Timeout/Retries:
            Determined by sqlite3 defaults.
        """

        self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Summary: Commit or roll back and close the active connection.
        Parameters:
            exc_type: Raised exception type, if any.
            exc_val: Raised exception instance, if any.
            exc_tb: Traceback associated with the exception, if any.
        Returns:
            None.
        Side Effects:
            Commits on success, rolls back on failure, then closes the connection.
        Timeout/Retries:
            Uses sqlite3 defaults without extra retry logic.
        """

        if not self._conn:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None


def _write_migration(module_dir: Path) -> tuple[str, Path]:
    """Summary: Produce a migration file that creates and drops a sample table.
    Parameters:
        module_dir: Directory where the migration file should be written.
    Returns:
        tuple[str, Path]: Generated version string and the migration file path.
    Raises:
        OSError: Propagated if the file cannot be written.
    Side Effects:
        Writes a Python migration script to disk.
    Timeout/Retries:
        Inherits filesystem semantics without retries.
    """

    version = datetime.now().strftime("%Y%m%d%H%M%S")
    module_dir.mkdir(parents=True, exist_ok=True)
    migration_path = module_dir / f"V{version}__create_demo_table.py"
    migration_source = dedent(
        """
        from __future__ import annotations

        from typing import Any


        def upgrade(connection: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS demo (id INTEGER PRIMARY KEY)")


        def downgrade(connection: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE IF EXISTS demo")
        """
    ).strip()
    migration_path.write_text(migration_source + "\n")
    return version, migration_path


def _read_tracking_rows(db_path: Path) -> list[tuple[int, str]]:
    """Summary: Read version and name columns from the tracking table.
    Parameters:
        db_path: Path to the SQLite database file.
    Returns:
        list[tuple[int, str]]: Pairs of version and migration name.
    Raises:
        sqlite3.Error: Propagated if the query fails.
    Side Effects:
        Opens a read-only connection to the database file.
    Timeout/Retries:
        Utilises sqlite3 defaults without retries.
    """

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version, name FROM schema_migrations ORDER BY version")
        rows = cursor.fetchall()
    return [(int(row[0]), row[1]) for row in rows]


def test_migrate_records_version(tmp_path: Path) -> None:
    """Ensure migrations execute and tracking metadata is persisted."""

    migrations_dir = tmp_path / "migrations"
    version, _ = _write_migration(migrations_dir)
    db_path = tmp_path / "demo.sqlite"

    manager = MigrationManager(SQLiteConnectionWrapper(db_path), migrations_dir=migrations_dir)
    manager.migrate()

    rows = _read_tracking_rows(db_path)
    assert rows == [(int(version), "create_demo_table")]
    assert manager.get_current_version() == int(version)


def test_rollback_removes_migration_record(tmp_path: Path) -> None:
    """Verify rollback executes the downgrade and clears the tracking entry."""

    migrations_dir = tmp_path / "migrations"
    _write_migration(migrations_dir)
    db_path = tmp_path / "demo.sqlite"

    manager = MigrationManager(SQLiteConnectionWrapper(db_path), migrations_dir=migrations_dir)
    manager.migrate()
    manager.rollback(target_version=0)

    rows = _read_tracking_rows(db_path)
    assert rows == []

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demo'")
        assert cursor.fetchone() is None


def test_migrate_rejects_unknown_target_version(tmp_path: Path) -> None:
    """Ensure requesting a missing target version raises MigrationVersionError."""

    migrations_dir = tmp_path / "migrations"
    _write_migration(migrations_dir)
    db_path = tmp_path / "demo.sqlite"

    manager = MigrationManager(SQLiteConnectionWrapper(db_path), migrations_dir=migrations_dir)

    with pytest.raises(MigrationVersionError):
        manager.migrate(target_version=99999999999999)
