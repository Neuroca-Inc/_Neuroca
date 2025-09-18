"""Tests for embedding configuration utilities."""

import pytest

from neuroca.memory.config.embedding import (
    DEFAULT_EMBEDDING_DIMENSION,
    ensure_embedding_dimension_fields,
    resolve_embedding_dimension,
)
from neuroca.memory.exceptions import ConfigurationError


def test_resolve_embedding_dimension_uses_settings_default() -> None:
    """Without overrides the helper should fall back to settings defaults."""

    dimension = resolve_embedding_dimension(manager_config={})
    assert dimension == DEFAULT_EMBEDDING_DIMENSION


def test_resolve_embedding_dimension_detects_conflicts() -> None:
    """Conflicting dimension hints should raise a configuration error."""

    config = {"ltm": {"storage": {"dimension": 64}, "embedding_dimension": 32}}

    with pytest.raises(ConfigurationError):
        resolve_embedding_dimension(manager_config=config)


def test_ensure_embedding_dimension_fields_mutates_configuration() -> None:
    """ensure_embedding_dimension_fields should populate tier fields consistently."""

    config: dict[str, object] = {"ltm": {}}
    ensure_embedding_dimension_fields(config, dimension=256)

    assert config["ltm"] == {
        "embedding_dimension": 256,
        "storage": {"dimension": 256},
    }
