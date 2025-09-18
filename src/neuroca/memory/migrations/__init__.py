"""Memory schema migration helpers."""

from .schema import adjust_embedding_dimension, ensure_summarization_package

__all__ = [
    "adjust_embedding_dimension",
    "ensure_summarization_package",
]
