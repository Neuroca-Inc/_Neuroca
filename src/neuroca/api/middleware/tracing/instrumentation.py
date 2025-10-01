"""Helpers to instrument FastAPI applications with tracing support."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .constants import DEFAULT_EXCLUDE_PATHS

logger = logging.getLogger(__name__)

__all__ = ["instrument_fastapi"]


def instrument_fastapi(app: FastAPI, excluded_urls: Optional[list[str]] = None) -> None:
    """Instrument a FastAPI application with the global tracer provider.

    Args:
        app: FastAPI application instance that should be instrumented.
        excluded_urls: Optional collection of URL patterns ignored by the
            tracer.

    Returns:
        None: The FastAPI application is instrumented in place.
    """

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=excluded_urls or DEFAULT_EXCLUDE_PATHS,
        tracer_provider=trace.get_tracer_provider(),
    )
    logger.info("FastAPI application instrumented with OpenTelemetry")
