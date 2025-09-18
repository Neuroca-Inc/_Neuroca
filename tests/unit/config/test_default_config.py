"""Tests for the default configuration module."""

import contextlib
import importlib
import sys
import warnings

MODULE_PATH = "neuroca.config.default"


@contextlib.contextmanager
def load_default_config(monkeypatch, env=None, token=None):
    env = env or {}

    for var in ("NEUROCA_SECRET_KEY", "SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    if token is not None:
        monkeypatch.setattr("secrets.token_urlsafe", lambda _: token)

    sys.modules.pop(MODULE_PATH, None)
    module = importlib.import_module(MODULE_PATH)
    try:
        yield module
    finally:
        sys.modules.pop(MODULE_PATH, None)


def test_secret_key_prefers_neuroca_env(monkeypatch):
    env = {"NEUROCA_SECRET_KEY": "primary", "SECRET_KEY": "legacy"}
    with load_default_config(monkeypatch, env=env) as module:
        assert module.SECRET_KEY == "primary"


def test_secret_key_falls_back_to_legacy_env(monkeypatch):
    env = {"SECRET_KEY": "legacy"}
    with load_default_config(monkeypatch, env=env) as module:
        assert module.SECRET_KEY == "legacy"


def test_secret_key_generates_when_missing(monkeypatch):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with load_default_config(monkeypatch, token="generated") as module:
            assert module.SECRET_KEY == "generated"

    assert any("SECRET_KEY environment variable not set" in str(item.message) for item in caught)
