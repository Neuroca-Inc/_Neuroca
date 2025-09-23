"""Definition of supported schema source types."""

from enum import Enum


class SourceType(str, Enum):
    """Enumeration of supported schema generation source categories."""

    PYDANTIC = "pydantic"
    DATACLASS = "dataclass"
    SQLALCHEMY = "sqlalchemy"
    DICT = "dict"
    CLASS = "class"
    JSON = "json"


__all__ = ["SourceType"]
