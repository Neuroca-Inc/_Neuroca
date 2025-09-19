"""Migration error hierarchy for database schema changes.

Purpose:
    Provide strongly typed exceptions that describe migration-related failure
    modes so callers can respond with precise remediation or logging.
External Dependencies:
    None; relies exclusively on the Python standard library.
Fallback Semantics:
    No automatic fallback handling is implemented. Raised exceptions propagate
    to the caller where recovery strategies should be applied.
Timeout Strategy:
    Not applicable. Errors represent logical or operational faults rather than
    timeout conditions. Timeout behaviour is delegated to the underlying
    database connection layer.
"""

from __future__ import annotations


class MigrationError(Exception):
    """Base exception for migration processing.

    Summary:
        Acts as the shared parent for all migration-specific exceptions so that
        calling code can catch a single error type when detailed discrimination
        is unnecessary.
    Parameters:
        *args: Positional arguments forwarded to ``Exception``.
        **kwargs: Keyword arguments forwarded to ``Exception``.
    Returns:
        None.
    Raises:
        MigrationError: When instantiated to signal a migration failure.
    Side Effects:
        None.
    Timeout/Retries:
        Timeout logic is governed by upstream database connectors; this class
        introduces no retry handling.
    """


class MigrationVersionError(MigrationError):
    """Exception describing migration version conflicts.

    Summary:
        Raised when version discovery, sorting, or validation fails (for
        example, when a requested target version does not exist).
    Parameters:
        *args: Positional details of the failure.
        **kwargs: Keyword details used to enrich the exception message.
    Returns:
        None.
    Raises:
        MigrationVersionError: Emitted to indicate an invalid migration version
            was encountered.
    Side Effects:
        None.
    Timeout/Retries:
        No timeout behaviour is added beyond upstream connectors.
    """


class MigrationExecutionError(MigrationError):
    """Exception raised when executing a migration step fails.

    Summary:
        Wraps lower-level database or script exceptions that occur while running
        ``upgrade`` or ``downgrade`` routines, ensuring the migration engine can
        differentiate execution faults from discovery issues.
    Parameters:
        *args: Positional execution failure details.
        **kwargs: Keyword details for additional context.
    Returns:
        None.
    Raises:
        MigrationExecutionError: Signals a migration script execution failure.
    Side Effects:
        None.
    Timeout/Retries:
        Retries are handled at the connection layer; this class does not modify
        timeout behaviour.
    """


class MigrationDependencyError(MigrationError):
    """Exception describing unsatisfied migration dependencies.

    Summary:
        Used when dependency analysis finds missing prerequisite migrations or
        cyclic dependencies that prevent a migration from running safely.
    Parameters:
        *args: Positional dependency details.
        **kwargs: Keyword arguments providing additional context.
    Returns:
        None.
    Raises:
        MigrationDependencyError: Raised when migration dependency checks fail.
    Side Effects:
        None.
    Timeout/Retries:
        Timeout logic is determined by the caller; the exception does not
        introduce retry semantics.
    """


__all__ = [
    "MigrationError",
    "MigrationVersionError",
    "MigrationExecutionError",
    "MigrationDependencyError",
]
