"""Schema migrator adapter delegation unit tests.

Purpose:
    Validate that `SchemaMigrator` delegates lifecycle operations to its database
    adapters and that error conditions are translated into domain exceptions.
External Dependencies:
    None. The suite relies solely on in-process stubs and the standard library.
Fallback Semantics:
    No fallback paths are exercised; failures propagate directly to pytest.
Timeout Strategy:
    Utilises pytest defaults without custom timeout or retry handling.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pytest

from neuroca.tools.migration.schema_migrator import (
    DatabaseAdapter,
    MigrationDirection,
    MigrationError,
    MigrationExecutionError,
    SchemaMigrator,
)

LOGGER = logging.getLogger(__name__)


class StubAdapter(DatabaseAdapter):
    """Lightweight adapter stub capturing invocations for assertion purposes.

    Summary:
        Provides an in-memory implementation of `DatabaseAdapter` that records
        lifecycle interactions and can simulate failure scenarios to validate
        `SchemaMigrator` behaviour.
    Attributes:
        connected: Tracks whether the stub observed a connect invocation.
        disconnected: Indicates disconnect invocation handling.
        executed: Records executed queries and optional parameters.
        transaction_begun: Flags when a transaction begin request occurs.
        committed: Marks transaction commit attempts.
        rolled_back: Marks transaction rollback attempts.
        table_ensured: Tracks ensure-migration-table calls.
        recorded: Collects migration record payloads.
        current_version: Simulated version value returned to the migrator.
        failures: Mapping of method name to exception instances for fault injection.
    """

    def __init__(self) -> None:
        """Initialise the stub adapter state.

        Summary:
            Populates bookkeeping attributes used by the tests and aligns with the
            abstract base class constructor contract.
        Returns:
            None.
        Side Effects:
            Sets up mutable state used for later assertions.
        Timeout/Retries:
            Not applicable.
        """
        super().__init__({})
        self.connected = False
        self.disconnected = False
        self.executed: list[tuple[str, Optional[dict[str, Any]]]] = []
        self.transaction_begun = False
        self.committed = False
        self.rolled_back = False
        self.table_ensured = False
        self.recorded: list[tuple[str, MigrationDirection, str, float]] = []
        self.current_version: Optional[str] = "1.0.0"
        self.failures: dict[str, Exception] = {}

    def connect(self) -> None:
        """Simulate establishing a database connection.

        Summary:
            Either raises an injected failure or toggles the `connected` flag so
            tests can assert that connection delegation occurred.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failure for negative-path testing.
        Side Effects:
            Mutates `connected` when no failure is configured.
        Timeout/Retries:
            No timeout or retry handling is implemented.
        """
        if failure := self.failures.get("connect"):
            raise failure
        self.connected = True

    def disconnect(self) -> None:
        """Simulate closing the database connection.

        Summary:
            Records disconnect attempts or raises an injected failure for tests
            verifying error propagation.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failures for negative assertions.
        Side Effects:
            Sets the `disconnected` flag when successful.
        Timeout/Retries:
            No timeout or retry behaviour is present.
        """
        if failure := self.failures.get("disconnect"):
            raise failure
        self.disconnected = True

    def execute(self, query: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Record statement execution and return a deterministic payload.

        Summary:
            Logs the provided query and optional parameters for inspection unless
            a failure is injected, in which case the exception is propagated.
        Parameters:
            query: Statement string submitted by the migrator.
            params: Optional mapping of parameters accompanying the query.
        Returns:
            dict[str, Any]: Echo of the query and parameters for assertion.
        Raises:
            Exception: Propagates injected failures for error-handling tests.
        Side Effects:
            Appends invocation data to the `executed` list.
        Timeout/Retries:
            No explicit timeout or retry logic is applied.
        """
        if failure := self.failures.get("execute"):
            raise failure
        self.executed.append((query, params))
        return {"query": query, "params": params}

    def transaction_begin(self) -> None:
        """Record attempts to begin a transaction.

        Summary:
            Flags the begin-operation or raises a configured failure for tests
            validating transaction initialisation behaviour.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failures for negative coverage.
        Side Effects:
            Sets `transaction_begun` when successful.
        Timeout/Retries:
            No timeout or retry logic is implemented.
        """
        if failure := self.failures.get("transaction_begin"):
            raise failure
        self.transaction_begun = True

    def transaction_commit(self) -> None:
        """Record commit attempts or raise configured failures.

        Summary:
            Updates the `committed` flag or raises an injected exception so tests
            can exercise the migrator's commit error handling.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failure states.
        Side Effects:
            Marks the `committed` flag when commits succeed.
        Timeout/Retries:
            No timeout logic is required.
        """
        if failure := self.failures.get("transaction_commit"):
            raise failure
        self.committed = True

    def transaction_rollback(self) -> None:
        """Record rollback attempts or raise injected failures.

        Summary:
            Toggles the `rolled_back` flag or raises an injected exception so
            tests can assert rollback behaviour.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failures.
        Side Effects:
            Sets the `rolled_back` marker upon success.
        Timeout/Retries:
            No timeout policy is implemented.
        """
        if failure := self.failures.get("transaction_rollback"):
            raise failure
        self.rolled_back = True

    def ensure_migration_table(self) -> None:
        """Track ensure-table invocations for assertion purposes.

        Summary:
            Updates the `table_ensured` flag or raises an injected failure so
            tests can verify that the migrator requested bookkeeping setup.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failures where configured.
        Side Effects:
            Sets the `table_ensured` flag when successful.
        Timeout/Retries:
            No timeout or retry logic is implemented.
        """
        if failure := self.failures.get("ensure_migration_table"):
            raise failure
        self.table_ensured = True

    def get_current_version(self) -> Optional[str]:
        """Return the configured schema version or raise an injected failure.

        Summary:
            Exposes the stub's `current_version` for direct assertions unless a
            failure is configured, in which case the exception surfaces.
        Returns:
            Optional[str]: The simulated schema version for the migrator.
        Raises:
            Exception: Propagates injected failures for error-path testing.
        Side Effects:
            None beyond reading internal state.
        Timeout/Retries:
            Not applicable.
        """
        if failure := self.failures.get("get_current_version"):
            raise failure
        return self.current_version

    def record_migration(
        self,
        version: str,
        direction: MigrationDirection,
        script_hash: str,
        execution_time: float,
    ) -> None:
        """Capture migration record attempts for verification.

        Summary:
            Either propagates an injected failure or appends the supplied payload
            to `recorded` so tests can assert metadata handling.
        Parameters:
            version: Version identifier supplied by the migrator.
            direction: Migration direction (up/down) associated with the record.
            script_hash: Digest of the migration script under test.
            execution_time: Duration reported for migration execution.
        Returns:
            None.
        Raises:
            Exception: Propagates injected failure scenarios for negative tests.
        Side Effects:
            Extends the `recorded` list with the provided metadata tuple.
        Timeout/Retries:
            No timeout management is necessary.
        """
        if failure := self.failures.get("record_migration"):
            raise failure
        self.recorded.append((version, direction, script_hash, execution_time))


@pytest.fixture()
def migrator(tmp_path, monkeypatch):
    """Prepare a migrator and stub adapter pair for delegation scenarios.

    Summary:
        Instantiate a `SchemaMigrator` configured to return the `StubAdapter`,
        enabling downstream tests to observe adapter interactions deterministically.
    Parameters:
        tmp_path: Pytest-managed temporary directory used as the migration root.
        monkeypatch: Pytest fixture that replaces the adapter factory for the test.
    Returns:
        tuple[SchemaMigrator, StubAdapter]: Prepared migrator and backing adapter.
    Raises:
        MigrationError: Propagated if `SchemaMigrator` fails to initialise.
    Side Effects:
        Temporarily overrides `SchemaMigrator._create_adapter` via monkeypatch.
    Timeout/Retries:
        Inherits pytest defaults; no explicit timeout or retry strategy is applied.
    """

    adapter = StubAdapter()

    def _create_adapter_stub(self) -> StubAdapter:
        return adapter

    monkeypatch.setattr(SchemaMigrator, "_create_adapter", _create_adapter_stub)
    instance = SchemaMigrator({"type": "sqlite", "database": ":memory:"}, migration_dir=str(tmp_path))
    return instance, adapter


def test_connect_delegates_to_adapter(migrator) -> None:
    """Ensure `SchemaMigrator.connect` delegates to the adapter connection hook.

    Summary:
        Validates that invoking `SchemaMigrator.connect` triggers the adapter's
        `connect` method, signalling that connections are managed at the adapter
        layer.
    Parameters:
        migrator: Fixture providing the `(SchemaMigrator, StubAdapter)` pair under test.
    Returns:
        None: Success is asserted by verifying the adapter state mutation.
    Raises:
        AssertionError: Raised when the adapter does not observe a connection call.
    Side Effects:
        Mutates the stub adapter's `connected` flag to reflect delegation.
    Timeout/Retries:
        Relies on pytest defaults without additional timeout handling.
    """

    instance, adapter = migrator
    LOGGER.info("Verifying SchemaMigrator.connect delegates to the adapter's connect routine.")

    instance.connect()

    assert adapter.connected is True


def test_execute_returns_adapter_payload(migrator) -> None:
    """Confirm `SchemaMigrator.execute` proxies queries and returns adapter data.

    Summary:
        Executes a representative query through `SchemaMigrator` and ensures the
        adapter receives identical arguments while its response is surfaced
        unchanged.
    Parameters:
        migrator: Fixture supplying the prepared migrator and stub adapter.
    Returns:
        None: Assertions validate adapter interaction and payload propagation.
    Raises:
        AssertionError: Raised if delegation arguments or returned payload differ.
    Side Effects:
        Appends the executed query metadata to the stub adapter's history.
    Timeout/Retries:
        Uses pytest defaults; no bespoke timeout behaviour is implemented.
    """

    instance, adapter = migrator
    LOGGER.info("Ensuring SchemaMigrator.execute proxies the query to the adapter and relays its result.")

    payload = instance.execute("SELECT 1", {"id": 1})

    assert adapter.executed == [("SELECT 1", {"id": 1})]
    assert payload == {"query": "SELECT 1", "params": {"id": 1}}


def test_transaction_commit_wraps_unexpected_errors(migrator) -> None:
    """Verify commit failures translate into `MigrationExecutionError` instances.

    Summary:
        Forces the stub adapter to raise a runtime error during commit and asserts
        that `SchemaMigrator.transaction_commit` rewraps the issue using the
        canonical migration execution exception type.
    Parameters:
        migrator: Fixture exposing the migrator and stub adapter under test.
    Returns:
        None: Behaviour is validated through pytest context managers.
    Raises:
        AssertionError: Raised if the expected `MigrationExecutionError` is not emitted.
    Side Effects:
        Injects a temporary failure into the stub adapter's commit path.
    Timeout/Retries:
        Depends on pytest's native timeout handling; no custom logic is present.
    """

    instance, adapter = migrator
    adapter.failures["transaction_commit"] = RuntimeError("commit failed")
    LOGGER.info("Confirming SchemaMigrator.transaction_commit converts unexpected adapter errors.")

    with pytest.raises(MigrationExecutionError):
        instance.transaction_commit()


def test_get_current_version_proxies_adapter(migrator) -> None:
    """Ensure adapter-reported schema versions flow through `get_current_version`.

    Summary:
        Sets a deterministic version on the stub adapter and checks that
        `SchemaMigrator.get_current_version` returns the same value without
        additional processing.
    Parameters:
        migrator: Fixture yielding the `(SchemaMigrator, StubAdapter)` tuple.
    Returns:
        None: Assertions confirm the returned version matches the stub value.
    Raises:
        AssertionError: Raised when the migrator does not relay the adapter version.
    Side Effects:
        Mutates the stub adapter's `current_version` attribute for the test case.
    Timeout/Retries:
        Uses pytest defaults; no retry or timeout customisation is necessary.
    """

    instance, adapter = migrator
    adapter.current_version = "2.0.0"
    LOGGER.info("Checking SchemaMigrator.get_current_version defers to the adapter for version retrieval.")

    assert instance.get_current_version() == "2.0.0"


def test_record_migration_rewraps_failures(migrator) -> None:
    """Confirm record failures are surfaced as `MigrationError` instances.

    Summary:
        Configures the stub adapter to fail during `record_migration` and asserts
        that `SchemaMigrator.record_migration` raises the expected domain-level
        `MigrationError` to signal persistence issues.
    Parameters:
        migrator: Fixture returning the configured migrator and stub adapter pair.
    Returns:
        None: Pytest assertion contexts validate the raised exception type.
    Raises:
        AssertionError: Elevated when the expected `MigrationError` is not observed.
    Side Effects:
        Temporarily injects a failure into the stub adapter's recording path.
    Timeout/Retries:
        Relies on pytest defaults without customised timeout handling.
    """

    instance, adapter = migrator
    adapter.failures["record_migration"] = RuntimeError("write failed")
    LOGGER.info(
        "Validating SchemaMigrator.record_migration re-raises adapter persistence failures as MigrationError."
    )

    with pytest.raises(MigrationError):
        instance.record_migration("1.0.0", MigrationDirection.UP, "deadbeef", 0.5)
