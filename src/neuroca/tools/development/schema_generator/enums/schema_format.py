"""Definition of supported schema output formats."""

from enum import Enum


class SchemaFormat(str, Enum):
    """Enumeration of available schema serialization formats."""

    JSON = "json"
    YAML = "yaml"
    PROTOBUF = "protobuf"
    AVRO = "avro"
    GRAPHQL = "graphql"
    PYDANTIC = "pydantic"
    TYPESCRIPT = "typescript"


__all__ = ["SchemaFormat"]
