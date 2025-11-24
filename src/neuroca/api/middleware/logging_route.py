"""Logging-enabled API route implementation.

The route wrapper mirrors the middleware behaviour but can be applied on a
per-endpoint basis, giving fine-grained control over which handlers receive
structured logging without installing global middleware.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute

from .logging_helpers import get_request_logger, sanitize_headers, set_correlation_id


class LoggingRoute(APIRoute):
    """API route that injects structured logging around request handling."""

    def get_route_handler(self) -> Callable[[Request], Response]:
        """Return a wrapped route handler that emits structured logs.

        Returns:
            Callable[[Request], Response]: Route handler decorated with logging
            instrumentation.
        """

        original_route_handler = super().get_route_handler()

        async def logging_route_handler(request: Request) -> Response:
            """Execute the wrapped handler while emitting request lifecycle logs.

            Args:
                request: Incoming HTTP request routed to the handler.

            Returns:
                Response: Response produced by the original route handler.
            """

            correlation_id = self._resolve_correlation_id(request.headers.get("X-Correlation-ID"))
            request_logger = get_request_logger()
            start_time = time.time()

            self._log_request(request_logger, request)

            try:
                response = await original_route_handler(request)
            except Exception as exc:  # pragma: no cover - defensive path
                self._log_failure(request_logger, exc, start_time)
                raise

            self._log_response(request_logger, response, start_time)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        return logging_route_handler

    def _resolve_correlation_id(self, provided_id: str | None) -> str:
        """Derive the correlation identifier used for the current request.

        Args:
            provided_id: Optional identifier supplied by the client.

        Returns:
            str: Identifier persisted for subsequent log statements.
        """

        return set_correlation_id(provided_id or str(uuid.uuid4()))

    def _log_request(self, request_logger: logging.LoggerAdapter, request: Request) -> None:
        """Emit a structured log entry for the incoming request.

        Args:
            request_logger: Logger adapter enriched with correlation metadata.
            request: The request currently being processed.
        """

        request_logger.info(
            "Request: %s %s",
            request.method,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": sanitize_headers(dict(request.headers)),
            },
        )

    def _log_response(
        self,
        request_logger: logging.LoggerAdapter,
        response: Response,
        start_time: float,
    ) -> None:
        """Emit a structured log entry for the outgoing response.

        Args:
            request_logger: Logger adapter enriched with correlation metadata.
            response: Response returned by the wrapped handler.
            start_time: Timestamp captured before invoking the handler.
        """

        process_time = time.time() - start_time
        request_logger.info(
            "Response: %s (took %.4fs)",
            response.status_code,
            process_time,
            extra={
                "status_code": response.status_code,
                "process_time": f"{process_time:.4f}s",
                "headers": sanitize_headers(dict(response.headers)),
            },
        )

    def _log_failure(
        self, request_logger: logging.LoggerAdapter, exc: Exception, start_time: float
    ) -> None:
        """Emit a structured log entry when the wrapped handler raises.

        Args:
            request_logger: Logger adapter enriched with correlation metadata.
            exc: Exception raised by the wrapped handler.
            start_time: Timestamp captured before invoking the handler.
        """

        process_time = time.time() - start_time
        request_logger.exception(
            "Error processing request: %s (after %.4fs)",
            exc,
            process_time,
            extra={"exception": str(exc), "process_time": process_time},
        )


__all__ = ["LoggingRoute"]
