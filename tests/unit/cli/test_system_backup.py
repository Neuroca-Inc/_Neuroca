"""Tests for secure PostgreSQL backup and restore command construction."""
# ruff: noqa: E402  # test module adjusts sys.modules before importing production code
import copy
import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import importlib
import pytest

if "tabulate" not in sys.modules:
    _tabulate_stub = ModuleType("tabulate")
    _tabulate_stub.tabulate = lambda *args, **kwargs: ""
    sys.modules["tabulate"] = _tabulate_stub
pytest.importorskip("tabulate")

memory_module = importlib.import_module("neuroca.memory")
if not hasattr(memory_module, "memory_manager"):
    memory_module.memory_manager = object()

import neuroca.cli.commands.system as system
from neuroca.config.settings import EnvironmentType
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


def test_build_postgres_dump_command_uses_static_arguments(monkeypatch, tmp_path):
    config = _build_postgres_config(PORT="5433")
    destination = tmp_path / "dump.sql"

    fake_executable = tmp_path / "pg_dump"
    fake_executable.touch()
    monkeypatch.setattr(system, "_resolve_database_executable", lambda *_, **__: fake_executable.as_posix())

    command = system._build_postgres_dump_command(config, destination)

    assert command == [
        fake_executable.as_posix(),
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


def test_build_postgres_restore_command_uses_static_arguments(monkeypatch, tmp_path):
    config = _build_postgres_config(HOST="pg01.example.net")
    source = tmp_path / "dump.sql"

    fake_executable = tmp_path / "psql"
    fake_executable.touch()
    monkeypatch.setattr(system, "_resolve_database_executable", lambda *_, **__: fake_executable.as_posix())

    command = system._build_postgres_restore_command(config, source)

    assert command == [
        fake_executable.as_posix(),
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


def test_backup_database_invokes_postgres_dump(monkeypatch, tmp_path):
    """Ensure `_backup_database` composes pg_dump command with credentials."""

    pg_dump_path = tmp_path / "pg_dump"
    pg_dump_path.touch()
    destination = tmp_path / "dump.sql"

    captured: dict[str, object] = {}

    monkeypatch.setattr(system, "_resolve_database_executable", lambda name, _: pg_dump_path.as_posix())
    monkeypatch.setattr(
        system,
        "_execute_database_command",
        lambda command, *, env=None: captured.update({"command": command, "env": env}),
    )

    db_config = _build_postgres_config(PASSWORD="s3cret")
    monkeypatch.setattr(system.settings, "DATABASE", db_config, raising=False)

    system._backup_database(destination.as_posix())

    assert captured["command"] == [
        pg_dump_path.as_posix(),
        "--host",
        "db.internal",
        "--port",
        "5432",
        "--username",
        "neuro_admin",
        "--file",
        destination.as_posix(),
        "neuroca",
    ]
    assert captured["env"]["PGPASSWORD"] == "s3cret"


def test_backup_database_copies_sqlite_source(monkeypatch, tmp_path):
    """Verify SQLite backups are created via filesystem copy."""

    source_db = tmp_path / "source.sqlite"
    source_db.write_text("data")
    destination = tmp_path / "backup.sqlite"

    db_config = SimpleNamespace(
        ENGINE="django.db.backends.sqlite3",
        NAME=source_db.as_posix(),
    )
    monkeypatch.setattr(system.settings, "DATABASE", db_config, raising=False)

    system._backup_database(destination.as_posix())

    assert destination.read_text() == "data"


def test_validate_database_command_allows_pg_dump(tmp_path):
    executable = tmp_path / "pg_dump"
    executable.touch()
    dump_file = tmp_path / "dump.sql"

    sanitized = system._validate_database_command(
        [
            executable.as_posix(),
            "--host",
            "db.internal",
            "--port",
            "5432",
            "--username",
            "neuro_admin",
            "--file",
            dump_file.as_posix(),
            "neuroca",
        ]
    )

    assert sanitized == [
        executable.as_posix(),
        "--host",
        "db.internal",
        "--port",
        "5432",
        "--username",
        "neuro_admin",
        "--file",
        dump_file.as_posix(),
        "neuroca",
    ]


class _StubSettings:
    """Lightweight settings stub for exercising backup and restore flows."""

    def __init__(self, base_dir: Path):
        temp_root = base_dir / "tmp"
        backup_root = base_dir / "backups"
        log_root = base_dir / "logs"
        for directory in (temp_root, backup_root, log_root):
            directory.mkdir(parents=True, exist_ok=True)

        self.SYSTEM = SimpleNamespace(TEMP_DIR=temp_root.as_posix(), BACKUP_DIR=backup_root.as_posix())
        self.LOGGING = SimpleNamespace(LOG_FILE=(log_root / "app.log").as_posix())
        self._snapshot = {
            "ENV": EnvironmentType.DEVELOPMENT,
            "paths": {"data_dir": base_dir / "data"},
        }
        self.updated_payload: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a deep copy of the captured configuration snapshot."""

        return copy.deepcopy(self._snapshot)

    def update_from_dict(self, payload: dict[str, object]) -> None:
        """Persist updates and keep a copy for assertions."""

        self.updated_payload = copy.deepcopy(payload)
        self._snapshot.update(payload)


def test_backup_and_restore_round_trip_normalizes_yaml(monkeypatch, tmp_path):
    """Ensure backups serialize enums safely and restores load them without errors."""

    stub_settings = _StubSettings(tmp_path)
    monkeypatch.setattr(system, "settings", stub_settings, raising=False)

    backup_path = tmp_path / "neuroca_backup_test.zip"

    created = system._create_system_backup(backup_path.as_posix(), include_logs=False, include_data=False)
    assert created is True

    with zipfile.ZipFile(backup_path) as archive:
        with archive.open("config/settings.yaml") as config_stream:
            yaml_text = config_stream.read().decode("utf-8")

    assert "!!python" not in yaml_text

    restored = system._restore_system_from_backup(backup_path.as_posix())
    assert restored is True
    assert stub_settings.updated_payload is not None
    assert stub_settings.updated_payload["ENV"] == "development"
    assert isinstance(stub_settings.updated_payload["paths"], dict)
    assert isinstance(stub_settings.updated_payload["paths"]["data_dir"], str)


def test_validate_database_command_rejects_unexpected_executable(tmp_path):
    executable = tmp_path / "mysql"
    executable.touch()
    dump_file = tmp_path / "dump.sql"

    with pytest.raises(BackupRestoreError):
        system._validate_database_command(
            [
                executable.as_posix(),
                "--host",
                "db.internal",
                "--port",
                "5432",
                "--username",
                "neuro_admin",
                "--file",
                dump_file.as_posix(),
                "neuroca",
            ]
        )


def test_validate_database_command_allows_psql(tmp_path):
    executable = tmp_path / "psql"
    executable.touch()
    dump_file = tmp_path / "dump.sql"

    sanitized = system._validate_database_command(
        [
            executable.as_posix(),
            "--host",
            "db.internal",
            "--port",
            "5432",
            "--username",
            "neuro_admin",
            "--dbname",
            "neuroca",
            "--file",
            dump_file.as_posix(),
        ]
    )

    assert sanitized == [
        executable.as_posix(),
        "--host",
        "db.internal",
        "--port",
        "5432",
        "--username",
        "neuro_admin",
        "--dbname",
        "neuroca",
        "--file",
        dump_file.as_posix(),
    ]


def test_validate_database_command_rejects_malformed_arguments(tmp_path):
    executable = tmp_path / "psql"
    executable.touch()

    with pytest.raises(BackupRestoreError):
        system._validate_database_command(
            [
                executable.as_posix(),
                "--host",
                "db.internal",
                "--port",
                "5432",
                "--username",
                "neuro_admin",
                "--file",
                "dump.sql",
            ]
        )


def test_restore_database_invokes_postgres_psql(monkeypatch, tmp_path):
    """Ensure `_restore_database` issues psql command with password."""

    psql_path = tmp_path / "psql"
    psql_path.touch()
    source = tmp_path / "dump.sql"
    source.write_text("payload")

    captured: dict[str, object] = {}

    monkeypatch.setattr(system, "_resolve_database_executable", lambda name, _: psql_path.as_posix())
    monkeypatch.setattr(
        system,
        "_execute_database_command",
        lambda command, *, env=None: captured.update({"command": command, "env": env}),
    )

    db_config = _build_postgres_config(PASSWORD="restore")
    monkeypatch.setattr(system.settings, "DATABASE", db_config, raising=False)

    system._restore_database(source.as_posix())

    assert captured["command"] == [
        psql_path.as_posix(),
        "--host",
        "db.internal",
        "--port",
        "5432",
        "--username",
        "neuro_admin",
        "--dbname",
        "neuroca",
        "--file",
        source.as_posix(),
    ]
    assert captured["env"]["PGPASSWORD"] == "restore"


def test_restore_database_copies_sqlite_destination(monkeypatch, tmp_path):
    """Verify SQLite restore replaces the database file with the backup contents."""

    backup_file = tmp_path / "backup.sqlite"
    backup_file.write_text("restored")
    target_dir = tmp_path / "db"
    target_path = target_dir / "database.sqlite"

    db_config = SimpleNamespace(
        ENGINE="django.db.backends.sqlite3",
        NAME=target_path.as_posix(),
    )
    monkeypatch.setattr(system.settings, "DATABASE", db_config, raising=False)

    system._restore_database(backup_file.as_posix())

    assert target_path.read_text() == "restored"
