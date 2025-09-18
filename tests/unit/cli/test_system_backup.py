"""Tests for secure PostgreSQL backup and restore command construction."""

from types import SimpleNamespace

import pytest

pytest.importorskip("tabulate")

from neuroca.cli.commands import system
from neuroca.core.exceptions import BackupRestoreError


def _build_postgres_config(**overrides):
    base = {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "db.internal",
        "PORT": 5432,
        "USER": "neuro_admin",
        "NAME": "neuroca",
        "PASSWORD": "example",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_postgres_dump_command_uses_static_arguments(tmp_path):
    config = _build_postgres_config(PORT="5433")
    destination = tmp_path / "dump.sql"

    command = system._build_postgres_dump_command(config, destination)

    assert command == [
        "pg_dump",
        "--host",
        "db.internal",
        "--port",
        "5433",
        "--username",
        "neuro_admin",
        "--file",
        str(destination),
        "neuroca",
    ]


def test_build_postgres_restore_command_uses_static_arguments(tmp_path):
    config = _build_postgres_config(HOST="pg01.example.net")
    source = tmp_path / "dump.sql"

    command = system._build_postgres_restore_command(config, source)

    assert command == [
        "psql",
        "--host",
        "pg01.example.net",
        "--port",
        "5432",
        "--username",
        "neuro_admin",
        "--dbname",
        "neuroca",
        "--file",
        str(source),
    ]


@pytest.mark.parametrize(
    "field, value",
    [
        ("HOST", "db.internal && rm -rf"),
        ("USER", "admin; DROP"),
        ("NAME", "neuro ca"),
    ],
)
def test_build_postgres_dump_command_rejects_invalid_identifiers(field, value, tmp_path):
    config = _build_postgres_config(**{field: value})

    with pytest.raises(BackupRestoreError):
        system._build_postgres_dump_command(config, tmp_path / "dump.sql")


def test_build_postgres_dump_command_rejects_invalid_port(tmp_path):
    config = _build_postgres_config(PORT="not-a-port")

    with pytest.raises(BackupRestoreError):
        system._build_postgres_dump_command(config, tmp_path / "dump.sql")


def test_build_postgres_dump_command_rejects_null_path():
    config = _build_postgres_config()

    with pytest.raises(BackupRestoreError):
        system._build_postgres_dump_command(config, "")
