"""Password utilities for test data factories."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache

DEFAULT_PASSWORD_ENV_VAR = "NEUROCA_TEST_USER_PASSWORD"


@lru_cache(maxsize=1)
def get_default_user_password() -> str:
    """Return the default password for generated test users."""

    if (env_password := os.getenv(DEFAULT_PASSWORD_ENV_VAR)) and env_password.strip():
        return env_password
    return secrets.token_urlsafe(32)


def reset_default_user_password_cache() -> None:
    """Clear the cached default password value."""

    get_default_user_password.cache_clear()


__all__ = [
    "DEFAULT_PASSWORD_ENV_VAR",
    "get_default_user_password",
    "reset_default_user_password_cache",
]
