"""Password utilities for test data factories."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache

_PASSWORD_ENV_VAR_NAME_OVERRIDE = "NEUROCA_TEST_PASSWORD_ENV_VAR_NAME"
_DEFAULT_PASSWORD_ENV_VAR_NAME = "NEUROCA_TEST_USER_PASSWORD"


@lru_cache(maxsize=1)
def get_password_env_var_name() -> str:
    """Return the environment variable name used for seeded test passwords."""

    candidate = os.getenv(_PASSWORD_ENV_VAR_NAME_OVERRIDE, _DEFAULT_PASSWORD_ENV_VAR_NAME)
    name = candidate.strip()
    if not name:
        raise ValueError("Password environment variable name cannot be blank")
    if any(char.isspace() for char in name):
        raise ValueError("Password environment variable name must not contain whitespace")
    return name


@lru_cache(maxsize=1)
def get_default_user_password() -> str:
    """Return the default password for generated test users."""

    env_var_name = get_password_env_var_name()
    env_password = os.getenv(env_var_name)
    if env_password and env_password.strip():
        return env_password.strip()
    return secrets.token_urlsafe(32)


def reset_default_user_password_cache() -> None:
    """Clear the cached default password value."""

    get_password_env_var_name.cache_clear()
    get_default_user_password.cache_clear()


__all__ = [
    "get_password_env_var_name",
    "get_default_user_password",
    "reset_default_user_password_cache",
]
