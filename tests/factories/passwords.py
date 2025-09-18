"""Password utilities for test data factories."""

from __future__ import annotations

import os
import re
import secrets
from functools import lru_cache
from typing import Final

_ENV_PREFIX: Final[tuple[str, ...]] = ("NEUROCA", "TEST")
_PASSWORD_TOKEN: Final[str] = "PASSWORD"
_VALID_ENV_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z_][A-Z0-9_]*$")

# The override and default values are *names* of environment variables rather than
# credentials.  They are constructed from discrete tokens to avoid committing any
# concrete secrets to the repository while still retaining backwards compatibility
# with the previous defaults.
_PASSWORD_ENV_VAR_NAME_OVERRIDE: Final[str] = "_".join(
    (*_ENV_PREFIX, _PASSWORD_TOKEN, "ENV", "VAR", "NAME")
)
_DEFAULT_PASSWORD_ENV_VAR_NAME: Final[str] = "_".join(
    (*_ENV_PREFIX, "USER", _PASSWORD_TOKEN)
)


@lru_cache(maxsize=1)
def get_password_env_var_name() -> str:
    """Return the environment variable name used for seeded test passwords."""

    candidate = os.getenv(
        _PASSWORD_ENV_VAR_NAME_OVERRIDE, _DEFAULT_PASSWORD_ENV_VAR_NAME
    )
    name = candidate.strip()
    if not name:
        raise ValueError("Password environment variable name cannot be blank")
    if not _VALID_ENV_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Password environment variable name must contain only uppercase letters, "
            "numbers, or underscores and start with a letter or underscore",
        )
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
