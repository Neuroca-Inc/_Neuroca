"""ASGI tracing middleware for frameworks that do not use Starlette wrappers."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .constants import DEFAULT_EXCLUDE_PATHS
from .context import current_request_id, current_trace_id

logger = logging.getLogger(__name__)

__all__ = ["ASGITracingMiddleware"]


class ASGITracingMiddleware:
    """Record OpenTelemetry spans for ASGI applications without Starlette."""

    def __init__(self, app: ASGIApp, exclude_paths: Optional[list[str]] = None) -> None:
        """Create the middleware wrapper with optional excluded paths.

        Args:
            app: ASGI application that should be wrapped with tracing support.
            exclude_paths: Optional list of path prefixes that bypass tracing.
        """

        self.app = app
        self.exclude_paths = exclude_paths or DEFAULT_EXCLUDE_PATHS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process an ASGI request while emitting tracing spans.

        Args:
            scope: ASGI connection scope for the request lifecycle.
            receive: Callable used to receive ASGI events from upstream.
            send: Callable that forwards events downstream.

        Returns:
            None: The wrapped application response is forwarded transparently.

        Raises:
            Exception: Propagates exceptions from the wrapped application after
                recording them on the active span.

        Side Effects:
            Writes request and trace identifiers to context variables and
            ensures response headers include ``X-Request-ID``/``X-Trace-ID`` when
            tracing data is available.
        """

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope) or str(uuid.uuid4())
        current_request_id.set(request_id)

        carrier = {
            name.decode("latin1").lower(): value.decode("latin1")
            for name, value in scope.get("headers", [])
        }
        context = TraceContextTextMapPropagator().extract(carrier=carrier)

        tracer = trace.get_tracer(__name__)
        method = scope.get("method", "UNKNOWN")
        span_name = f"{method} {path}"

        with tracer.start_as_current_span(
            span_name,
            context=context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span_context = span.get_span_context()
            if span_context.trace_id:
                current_trace_id.set(format(span_context.trace_id, "032x"))

            span.set_attribute("http.method", method)
            span.set_attribute(
                "http.url",
                f"{scope.get('scheme', 'http')}://{scope.get('server', ['localhost', 80])[0]}{path}",
            )
            span.set_attribute("http.request_id", request_id)
            span.set_attribute("http.route", path)

            client = scope.get("client")
            if client:
                span.set_attribute("http.client_ip", client[0])
                span.set_attribute("http.client_port", client[1])

            start_time = time.time()
            status_code = [200]

            async def send_with_tracing(message: Message) -> None:
                if message["type"] == "http.response.start":
                    status_code[0] = message["status"]
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode("latin1")))
                    if current_trace_id.get():
                        headers.append((b"x-trace-id", current_trace_id.get().encode("latin1")))
                    message["headers"] = headers
                await send(message)

            try:
                await self.app(scope, receive, send_with_tracing)
                span.set_attribute("http.status_code", status_code[0])
                span.set_attribute(
                    "http.response_time_ms", (time.time() - start_time) * 1000
                )
                if 400 <= status_code[0] < 600:
                    span.set_status(
                        trace.Status(
                            trace.StatusCode.ERROR,
                            f"HTTP {status_code[0]}",
                        )
                    )
            except Exception as exc:  # pragma: no cover - defensive path
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                logger.error(
                    "Request failed",
                    extra={
                        "request_id": request_id,
                        "trace_id": current_trace_id.get(),
                        "path": path,
                        "method": method,
                    },
                    exc_info=True,
                )
                raise


def _extract_request_id(scope: Scope) -> Optional[str]:
    """Return a request identifier from the ASGI headers if present.

    Args:
        scope: ASGI scope containing the incoming request metadata.

    Returns:
        Optional[str]: The provided request identifier or ``None`` when the
        header is absent.
    """

    for name, value in scope.get("headers", []):
        if name.decode("latin1").lower() == "x-request-id":
            return value.decode("latin1")
    return None
