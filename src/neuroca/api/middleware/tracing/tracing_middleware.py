"""ASGI middleware that enriches requests with tracing metadata."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .constants import DEFAULT_EXCLUDE_PATHS
from .context import current_request_id, current_trace_id

logger = logging.getLogger(__name__)

__all__ = ["TracingMiddleware"]


class TracingMiddleware(BaseHTTPMiddleware):
    """Record OpenTelemetry spans for incoming FastAPI/Starlette requests."""

    exclude_paths: list[str] = DEFAULT_EXCLUDE_PATHS

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process an incoming request while recording tracing information.

        Args:
            request: Incoming HTTP request handled by FastAPI/Starlette.
            call_next: Next middleware or endpoint handler in the ASGI chain.

        Returns:
            Response: The HTTP response returned by downstream handlers.

        Raises:
            Exception: Propagates any exception raised by ``call_next`` after
                recording the error on the span.

        Side Effects:
            Updates request/trace context variables and injects ``X-Request-ID``
            plus ``X-Trace-ID`` headers into the outgoing response when tracing
            is active.
        """

        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        current_request_id.set(request_id)

        carrier = dict(request.headers.items())
        context = TraceContextTextMapPropagator().extract(carrier=carrier)

        tracer = trace.get_tracer(__name__)
        span_name = f"{request.method} {request.url.path}"

        with tracer.start_as_current_span(
            span_name,
            context=context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span_context = span.get_span_context()
            if span_context.trace_id:
                current_trace_id.set(format(span_context.trace_id, "032x"))

            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.host", request.headers.get("host", ""))
            span.set_attribute("http.user_agent", request.headers.get("user-agent", ""))
            span.set_attribute("http.request_id", request_id)
            span.set_attribute("http.route", request.url.path)

            client = request.client
            if client:
                span.set_attribute("http.client_ip", client.host)
                if client.port:
                    span.set_attribute("http.client_port", client.port)

            start_time = time.time()

            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute(
                    "http.response_time_ms", (time.time() - start_time) * 1000
                )

                response.headers["X-Request-ID"] = request_id
                if current_trace_id.get():
                    response.headers["X-Trace-ID"] = current_trace_id.get()

                if 400 <= response.status_code < 600:
                    span.set_status(
                        trace.Status(
                            trace.StatusCode.ERROR,
                            f"HTTP {response.status_code}",
                        )
                    )

                return response
            except Exception as exc:  # pragma: no cover - defensive path
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                logger.error(
                    "Request failed",
                    extra={
                        "request_id": request_id,
                        "trace_id": current_trace_id.get(),
                        "path": request.url.path,
                        "method": request.method,
                    },
                    exc_info=True,
                )
                raise
