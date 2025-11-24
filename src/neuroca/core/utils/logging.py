"""Logging helpers for NeuroCognitive Architecture components.

Purpose:
    Provide a centralised helper for configuring module-level loggers with a
    consistent formatter and level. Avoids duplicating logging boilerplate across
    packages.
External Dependencies:
    Uses only the Python standard library `logging` module. No CLI or HTTP calls
    are performed.
Fallback Semantics:
    If configuration fails the helper falls back to returning the default logger
    obtained via `logging.getLogger`.
Timeout Strategy:
    Not applicable; operations are in-process and non-blocking.
"""

from __future__ import annotations

import logging


def configure_logger(name: str, level: int | None = None) -> logging.Logger:
    """Summary: Return a logger configured with a standard formatter.
    Parameters:
        name: Name of the logger to retrieve.
        level: Optional logging level override. Defaults to ``logging.INFO`` when
            no handlers are configured on the logger.
    Returns:
        logging.Logger: Configured logger instance.
    Raises:
        None.
    Side Effects:
        Adds a ``StreamHandler`` with a standard formatter when the logger does
        not already have handlers attached.
    Timeout/Retries:
        Not applicable; logging configuration executes synchronously.
    """

    logger = logging.getLogger(name)
    effective_level = level if level is not None else logging.INFO

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(effective_level)

    return logger


__all__ = ["configure_logger"]
