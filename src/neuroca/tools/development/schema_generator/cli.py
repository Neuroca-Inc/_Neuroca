"""Command line support for the schema generator tooling."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from . import SchemaFormat, SchemaGenerator, SourceType
from .exceptions.schema_generation_error import SchemaGenerationError

LOGGER = logging.getLogger(__name__)


def build_argument_parser(generator: SchemaGenerator) -> argparse.ArgumentParser:
    """Create and configure the argument parser for the CLI."""
    source_choices = [choice.value for choice in generator.available_source_types()]
    format_choices = [choice.value for choice in generator.available_formats()]
    parser = argparse.ArgumentParser(
        description="Generate schemas from supported Neuroca models",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        choices=source_choices,
        required=True,
        help="Type of the source to generate schema from.",
    )
    parser.add_argument(
        "--source-path",
        type=str,
        required=True,
        help="Module path, file path, or identifier for the source object.",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=format_choices,
        required=True,
        help="Output format for the generated schema.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./schemas",
        help="Directory to write generated schemas into.",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        help="Optional namespace for the generated schema.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    return parser


def configure_logging(verbose: bool) -> None:
    """Configure logging for the CLI run."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def build_output_path(output_dir: str, source_path: str) -> Path:
    """Compute the output path for the generated schema file."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    source_name = source_path.split(".")[-1]
    return target_dir / f"{source_name}_schema"


def main(argv: Optional[list[str]] = None) -> int:
    """Execute the schema generator CLI."""
    try:
        generator = SchemaGenerator()
        parser = build_argument_parser(generator)
        args = parser.parse_args(argv)

        configure_logging(args.verbose)
        schema_source_type = SourceType(args.source_type)
        schema_format = SchemaFormat(args.output_format)
        output_path = build_output_path(args.output_dir, args.source_path)
        generator.generate(
            source=args.source_path,
            source_type=schema_source_type,
            output_format=schema_format,
            output_path=str(output_path),
            namespace=args.namespace,
        )
        LOGGER.info("Schema generation completed successfully. Output: %s", output_path)
        return 0
    except SchemaGenerationError as error:
        LOGGER.error("Schema generation failed: %s", error, exc_info=True)
        return 1


__all__ = ["main"]
