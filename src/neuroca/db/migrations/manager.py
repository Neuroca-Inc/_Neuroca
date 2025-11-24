"""Migration discovery and execution utilities.

Purpose:
    Coordinate discovery of migration scripts, execute them in order, and keep
    an auditable record of applied versions inside the target database.
External Dependencies:
    Relies on the calling code to provide an active database connection object.
    No CLI or HTTP services are invoked from this module directly.
Fallback Semantics:
    Exceptions raised during discovery or execution are propagated to callers;
    the module does not attempt automatic retries or fallbacks.
Timeout Strategy:
    Delegates timeout configuration to the supplied database connection. The
    manager itself does not enforce additional timing constraints.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .errors import (
    MigrationError,
    MigrationVersionError,
)
from .migration import Migration

logger = logging.getLogger(__name__)

MIGRATION_VERSION_PATTERN = r"^V(\d{14})__.*\.py$"
_SCHEMA_TABLE_NAME = "schema_migrations"

TransactionStatement = Tuple[str, Optional[Sequence[Any]]]


class MigrationManager:
    """Summary: Coordinate migration discovery, execution, and bookkeeping.
    Parameters:
        connection: Context-manageable database connection exposing query helpers
            or DB-API semantics.
        migrations_dir: Optional directory containing migration scripts.
    Attributes:
        connection: Stored connection provider used for all operations.
        migrations_dir: Path object resolved from the provided directory.
        migrations: Mapping of version numbers to ``Migration`` objects.
        _param_token: Parameter placeholder token derived from the connection.
    Raises:
        MigrationError: Emitted when discovery or bookkeeping preparation fails.
    Side Effects:
        May create the ``schema_migrations`` tracking table and import scripts.
    Timeout/Retries:
        Fully delegated to the supplied database connection implementation.
    """

    def __init__(self, connection: Any, migrations_dir: Optional[Path | str] = None) -> None:
        self.connection = connection
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).parent
        self.migrations: Dict[int, Migration] = {}
        self._param_token = "%s" if hasattr(connection, "execute_transaction") else "?"

        self._ensure_migration_table()
        self._discover_migrations()

    @contextmanager
    def _connection_scope(self) -> Iterator[Any]:
        """Summary: Yield a managed database connection for migration work.
        Parameters:
            None.
        Returns:
            Iterator[Any]: Managed connection object.
        Raises:
            MigrationError: If the connection lacks context manager support.
        Side Effects:
            Delegates lifecycle control to the wrapped connection.
        Timeout/Retries:
            Left to the underlying connection implementation.
        """

        conn = self.connection
        if hasattr(conn, "__enter__") and hasattr(conn, "__exit__"):
            with conn as managed:
                yield managed
        else:
            raise MigrationError(
                "Connection object must support context manager semantics for migrations."
            )

    def _ensure_migration_table(self) -> None:
        """Summary: Create the tracking table when absent.
        Parameters:
            None.
        Returns:
            None.
        Raises:
            MigrationError: If the DDL statement cannot be executed.
        Side Effects:
            Issues ``CREATE TABLE`` against the target database.
        Timeout/Retries:
            Delegated to the database connection implementation.
        """

        ddl_statements = [
            (
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    execution_time REAL NOT NULL,
                    checksum TEXT
                )
                """,
                None,
            ),
        ]

        with self._connection_scope() as conn:
            self._execute_transaction(conn, ddl_statements)

    def _discover_migrations(self) -> None:
        """Summary: Scan the migration directory and register scripts.
        Parameters:
            None.
        Returns:
            None.
        Raises:
            MigrationError: When filesystem access or parsing fails.
        Side Effects:
            Populates ``self.migrations`` and may import migration modules.
        Timeout/Retries:
            Uses default filesystem behaviour with no extra timeouts.
        """

        self.migrations.clear()
        try:
            pattern = re.compile(MIGRATION_VERSION_PATTERN)
            if not self.migrations_dir.exists():
                logger.warning("Migrations directory %s does not exist", self.migrations_dir)
                return

            for file_path in self.migrations_dir.glob("V*__*.py"):
                match = pattern.match(file_path.name)
                if not match:
                    continue
                version = int(match[1])
                name = file_path.stem.split("__", 1)[1]

                if version in self.migrations:
                    logger.warning("Duplicate migration version %s found at %s", version, file_path)
                    continue

                self.migrations[version] = Migration(version, name, file_path)
                logger.debug("Discovered migration V%s__%s", version, name)

            logger.info("Discovered %d migration(s)", len(self.migrations))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to discover migrations: %s", exc)
            raise MigrationError(f"Failed to discover migrations: {exc}") from exc

    def get_current_version(self) -> int:
        """Summary: Fetch the highest recorded migration version.
        Parameters:
            None.
        Returns:
            int: Latest applied version or ``0`` if none exist.
        Raises:
            MigrationError: If the tracking query cannot be executed.
        Side Effects:
            Issues a ``SELECT`` against ``schema_migrations``.
        Timeout/Retries:
            Determined by the connection layer.
        """

        query = "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        with self._connection_scope() as conn:
            rows = self._fetch(conn, query)
        return int(rows[0]["version"]) if rows else 0

    def get_pending_migrations(self) -> List[Migration]:
        """Summary: List migrations with versions greater than the current one.
        Parameters:
            None.
        Returns:
            list[Migration]: Pending migrations ordered by version.
        Raises:
            MigrationError: When determining the current version fails.
        Side Effects:
            None.
        Timeout/Retries:
            Deferred to the connection implementation.
        """

        current_version = self.get_current_version()
        pending = [migration for v, migration in self.migrations.items() if v > current_version]
        return sorted(pending, key=lambda migration: migration.version)

    def migrate(self, target_version: Optional[int] = None) -> None:
        """Summary: Apply pending migrations up to ``target_version``.
        Parameters:
            target_version: Optional highest version to apply; ``None`` applies all.
        Returns:
            None.
        Raises:
            MigrationError: When upgrade execution or bookkeeping fails.
            MigrationVersionError: If ``target_version`` does not exist.
        Side Effects:
            Executes migration ``upgrade`` routines and records metadata.
        Timeout/Retries:
            Controlled by the underlying connection; no internal retries occur.
        """

        pending = self.get_pending_migrations()
        if target_version is not None:
            if target_version not in self.migrations:
                raise MigrationVersionError(f"Target version {target_version} not found")
            pending = [migration for migration in pending if migration.version <= target_version]

        if not pending:
            logger.info("No pending migrations to apply")
            return

        for migration in pending:
            with self._connection_scope() as conn:
                start = time.time()
                migration.upgrade(conn)
                execution_time = time.time() - start
                checksum = self._calculate_checksum(migration)
                self._record_migration(conn, migration, execution_time, checksum)

        logger.info("Migration complete. Current version: %s", self.get_current_version())

    def rollback(self, target_version: Optional[int] = None, steps: int = 1) -> None:
        """Summary: Roll back migrations to ``target_version`` or by ``steps``.
        Parameters:
            target_version: Optional version to retain after rollback.
            steps: Number of migrations to undo when ``target_version`` is absent.
        Returns:
            None.
        Raises:
            MigrationError: When downgrade execution or bookkeeping fails.
            MigrationVersionError: If ``target_version`` is unknown.
        Side Effects:
            Executes migration ``downgrade`` routines and deletes tracking rows.
        Timeout/Retries:
            Managed by the database connection; no internal retries are executed.
        """

        applied_versions = self._get_applied_versions()
        if not applied_versions:
            logger.info("No migrations to roll back")
            return

        applied_versions.sort(reverse=True)
        if target_version is None:
            to_rollback = applied_versions[:steps]

        elif target_version not in self.migrations and target_version != 0:
            raise MigrationVersionError(f"Target version {target_version} not found")
        else:
            to_rollback = [version for version in applied_versions if version > target_version]
        if not to_rollback:
            logger.info("No migrations to roll back")
            return

        for version in to_rollback:
            migration = self.migrations.get(version)
            if not migration:
                logger.warning("Migration %s not found among discovered migrations", version)
                continue

            with self._connection_scope() as conn:
                migration.downgrade(conn)
                self._remove_migration_record(conn, version)

        logger.info("Rollback complete. Current version: %s", self.get_current_version())

    def _get_applied_versions(self) -> List[int]:
        """Summary: Retrieve ordered migration versions from the database.
        Parameters:
            None.
        Returns:
            list[int]: Applied migration versions in ascending order.
        Raises:
            MigrationError: If the select query fails.
        Side Effects:
            None.
        Timeout/Retries:
            Delegated to the database connection.
        """

        query = "SELECT version FROM schema_migrations ORDER BY version ASC"
        with self._connection_scope() as conn:
            rows = self._fetch(conn, query)
        return [int(row["version"]) for row in rows]

    def _record_migration(
        self,
        conn: Any,
        migration: Migration,
        execution_time: float,
        checksum: str,
    ) -> None:
        """Summary: Persist metadata for a successfully applied migration.
        Parameters:
            conn: Managed database connection.
            migration: Migration that completed successfully.
            execution_time: Duration in seconds for the migration run.
            checksum: SHA-256 digest of the migration file contents.
        Returns:
            None.
        Raises:
            MigrationError: When the delete/insert statements fail.
        Side Effects:
            Updates ``schema_migrations`` with the new version record.
        Timeout/Retries:
            Determined by the connection; no internal retries occur.
        """

        delete_sql = f"DELETE FROM { _SCHEMA_TABLE_NAME } WHERE version = {self._param_token}"
        insert_sql = (
            f"INSERT INTO { _SCHEMA_TABLE_NAME } (version, name, execution_time, checksum) "
            f"VALUES ({self._param_token}, {self._param_token}, {self._param_token}, {self._param_token})"
        )
        statements: List[TransactionStatement] = [
            (delete_sql, (migration.version,)),
            (insert_sql, (migration.version, migration.name, execution_time, checksum)),
        ]
        self._execute_transaction(conn, statements)

    def _remove_migration_record(self, conn: Any, version: int) -> None:
        """Summary: Remove a migration record after a downgrade.
        Parameters:
            conn: Managed database connection.
            version: Migration version to delete from tracking.
        Returns:
            None.
        Raises:
            MigrationError: If the delete statement fails.
        Side Effects:
            Modifies the ``schema_migrations`` tracking table.
        Timeout/Retries:
            Controlled by the database driver.
        """

        delete_sql = f"DELETE FROM { _SCHEMA_TABLE_NAME } WHERE version = {self._param_token}"
        self._execute_transaction(conn, [(delete_sql, (version,))])

    def _fetch(self, conn: Any, query: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        """Summary: Execute ``SELECT`` statements and return dictionary rows.
        Parameters:
            conn: Managed database connection.
            query: SQL text to execute.
            params: Optional positional parameters.
        Returns:
            list[dict[str, Any]]: Rows expressed as dictionaries.
        Raises:
            MigrationError: When the query fails on the underlying driver.
        Side Effects:
            Issues ``SELECT`` statements on the database.
        Timeout/Retries:
            Governed entirely by the connection implementation.
        """

        try:
            if hasattr(conn, "execute_query"):
                return conn.execute_query(query, params, fetch_all=True)

            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                columns = [column[0] for column in cursor.description or []]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            finally:
                cursor.close()
        except Exception as exc:  # noqa: BLE001
            raise MigrationError(f"Failed to execute query '{query}': {exc}") from exc

    def _execute_transaction(self, conn: Any, statements: Sequence[TransactionStatement]) -> None:
        """Summary: Run statements atomically using the available transaction API.
        Parameters:
            conn: Managed database connection.
            statements: Sequence of SQL statements with optional parameters.
        Returns:
            None.
        Raises:
            MigrationError: When execution or commit fails.
        Side Effects:
            Applies the supplied mutations to the database.
        Timeout/Retries:
            Controlled by the underlying connection implementation.
        """

        try:
            if hasattr(conn, "execute_transaction"):
                conn.execute_transaction(list(statements))
                return

            cursor = conn.cursor()
            try:
                for query, params in statements:
                    cursor.execute(query, params or ())
                if hasattr(conn, "commit"):
                    conn.commit()
            except Exception:  # noqa: BLE001
                if hasattr(conn, "rollback"):
                    conn.rollback()
                raise
            finally:
                cursor.close()
        except Exception as exc:  # noqa: BLE001
            raise MigrationError(f"Failed to execute migration transaction: {exc}") from exc

    @staticmethod
    def _calculate_checksum(migration: Migration) -> str:
        """Summary: Generate a SHA-256 digest for the migration source file.
        Parameters:
            migration: Migration whose file contents should be hashed.
        Returns:
            str: Hexadecimal digest or an empty string when hashing fails.
        Raises:
            None explicitly; failures are logged and return an empty string.
        Side Effects:
            Reads bytes from the migration file on disk.
        Timeout/Retries:
            Governed by the operating system's file IO behaviour.
        """

        try:
            return hashlib.sha256(migration.path.read_bytes()).hexdigest()
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("Failed to hash migration %s: %s", migration.path, exc)
            return ""


def create_migration(name: str, migrations_dir: Optional[Path | str] = None) -> Path:
    """Summary: Create a timestamped migration template on disk.
    Parameters:
        name: Descriptive migration name (CamelCase or spaced words).
        migrations_dir: Optional target directory for the new file.
    Returns:
        Path: Absolute path to the generated migration module.
    Raises:
        MigrationError: If directory creation or file write fails.
    Side Effects:
        Writes a Python source file containing upgrade/downgrade stubs.
    Timeout/Retries:
        Subject to filesystem behaviour; no explicit retries.
    """

    try:
        snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        snake_name = re.sub(r"[^a-z0-9_]", "_", snake_name)
        version = datetime.now().strftime("%Y%m%d%H%M%S")

        directory = Path(migrations_dir) if migrations_dir else Path(__file__).parent
        directory.mkdir(parents=True, exist_ok=True)

        file_path = directory / f"V{version}__{snake_name}.py"
        template = f"""\"\"\"Migration script: {name}.\"\"\"

from __future__ import annotations

from typing import Any


def upgrade(connection: Any) -> None:
    \"\"\"Apply the migration changes.\"\"\"
    raise NotImplementedError("Implement migration upgrade logic.")


def downgrade(connection: Any) -> None:
    \"\"\"Revert the migration changes.\"\"\"
    raise NotImplementedError("Implement migration downgrade logic.")
"""
        file_path.write_text(template.strip() + "\n")
        logger.info("Created migration file: %s", file_path)
        return file_path
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to create migration file: %s", exc)
        raise MigrationError(f"Failed to create migration file: {exc}") from exc


__all__ = [
    "MigrationManager",
    "create_migration",
    "MIGRATION_VERSION_PATTERN",
]
