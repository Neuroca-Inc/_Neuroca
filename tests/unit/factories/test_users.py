"""Tests for the user factory default password behaviour."""

from __future__ import annotations

import pytest

pytest.importorskip("factory")

from tests.factories import passwords as password_helpers
from tests.factories import users as user_factories


def test_user_factory_password_hash_matches_default_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Users produced by the factory should authenticate with the default password."""

    password_helpers.reset_default_user_password_cache()

    default_password = "FactorySecret!123"
    monkeypatch.setattr(user_factories, "get_default_user_password", lambda: default_password)

    hashed_inputs: list[str] = []

    def fake_hash(password: str) -> str:
        hashed_inputs.append(password)
        return f"hashed::{password}"

    monkeypatch.setattr(user_factories.User, "hash_password", staticmethod(fake_hash))

    password_hash = user_factories.UserFactory.password_hash.function()
    assert hashed_inputs == [default_password]

    user = user_factories.User(
        username="factory_user",
        email="factory@example.com",
        password_hash=password_hash,
    )

    assert user.check_password(default_password)
