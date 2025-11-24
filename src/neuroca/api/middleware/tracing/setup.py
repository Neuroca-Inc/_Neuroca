"""Tracing configuration helpers for the NeuroCA API."""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio, TraceIdRatioBased

logger = logging.getLogger(__name__)

__all__ = ["setup_tracing"]


def setup_tracing(
    service_name: str,
    sample_rate: float = 0.1,
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
    exclude_paths: Optional[list[str]] = None,
) -> None:
    """Configure OpenTelemetry tracing for the API service.

    Args:
        service_name: Identifier applied to spans emitted by this service.
        sample_rate: Fraction of requests to sample between ``0.0`` and ``1.0``.
        otlp_endpoint: Optional OTLP collector endpoint used for exporting
            traces. When omitted the console exporter becomes the default.
        console_export: Flag controlling whether spans are echoed to stdout.
        exclude_paths: Optional list of URL paths excluded from tracing.

    Returns:
        None: The function mutates the global tracer provider configuration.

    Raises:
        ValueError: If ``sample_rate`` falls outside the inclusive ``[0, 1]``
            range.
    """

    if not 0.0 <= sample_rate <= 1.0:
        raise ValueError("Sample rate must be between 0.0 and 1.0")

    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=ParentBasedTraceIdRatio(TraceIdRatioBased(sample_rate)),
    )

    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("OTLP exporter configured", extra={"endpoint": otlp_endpoint})

    if console_export or not otlp_endpoint:
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console exporter enabled for tracing output")

    trace.set_tracer_provider(tracer_provider)

    if exclude_paths is not None:
        from .tracing_middleware import TracingMiddleware

        TracingMiddleware.exclude_paths = exclude_paths

    logger.info(
        "Tracing initialized", extra={"service": service_name, "sample_rate": sample_rate}
    )
