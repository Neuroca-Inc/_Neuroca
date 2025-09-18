"""Tests for PostgreSQL connection helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from psycopg2 import sql

from neuroca.db.connections import postgres
from neuroca.db.connections.postgres import PostgresConfig, PostgresConnection


@pytest.mark.parametrize(
    "schema,expected",
    [
        ("public", ["public"]),
        ("public,analytics", ["public", "analytics"]),
        ("$user,public", ["$user", "public"]),
        (" public , analytics ", ["public", "analytics"]),
    ],
)
def test_normalize_search_path_allows_expected_inputs(schema: str, expected: list[str]) -> None:
    assert postgres._normalize_search_path(schema) == expected


@pytest.mark.parametrize("schema", ["", "public;DROP", "public analytics", '"public"'])
def test_normalize_search_path_rejects_invalid_inputs(schema: str) -> None:
    with pytest.raises(ValueError):
        postgres._normalize_search_path(schema)


def test_build_connection_options_validates_inputs() -> None:
    options = postgres._build_connection_options("public,analytics", 5000)
    assert options == "-c search_path=public,analytics -c statement_timeout=5000"


def test_build_connection_options_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError):
        postgres._build_connection_options("public", -1)


def test_get_connection_uses_safe_session_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    config = PostgresConfig(
        host="localhost",
        user="postgres",
        password="",
        database="neuroca",
        schema="public",
        statement_timeout=1500,
        use_connection_pool=False,
    )

    conn_mock = MagicMock()
    cursor_mock = MagicMock()

    class _CursorManager:
        def __enter__(self) -> MagicMock:
            return cursor_mock

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    conn_mock.cursor.return_value = _CursorManager()

    def fake_connect(**kwargs: Any):
        assert kwargs["host"] == config.host
        assert kwargs["dbname"] == config.database
        assert kwargs["options"] == "-c search_path=public -c statement_timeout=1500"
        return conn_mock

    monkeypatch.setattr("neuroca.db.connections.postgres.psycopg2.connect", fake_connect)
    monkeypatch.setattr(
        "neuroca.db.connections.postgres.psycopg2.extras.register_json", lambda conn: None
    )

    connection = PostgresConnection(config=config)
    acquired = connection._get_connection()

    assert acquired is conn_mock
    assert cursor_mock.execute.call_count == 2

    first_call = cursor_mock.execute.call_args_list[0]
    assert isinstance(first_call.args[0], sql.Composable)
    assert len(first_call.args) == 1

    second_call = cursor_mock.execute.call_args_list[1]
    assert second_call.args[0] == "SET statement_timeout TO %s"
    assert second_call.args[1] == (1500,)


def test_get_connection_rejects_invalid_schema_before_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    config = PostgresConfig(
        host="localhost",
        user="postgres",
        password="",
        database="neuroca",
        schema="public;DROP",
        use_connection_pool=False,
    )

    def fail_connect(**_: Any) -> None:
        raise AssertionError("Database connection should not be attempted with invalid schema")

    monkeypatch.setattr("neuroca.db.connections.postgres.psycopg2.connect", fail_connect)

    connection = PostgresConnection(config=config)

    with pytest.raises(postgres.ConnectionError):
        connection._get_connection()
