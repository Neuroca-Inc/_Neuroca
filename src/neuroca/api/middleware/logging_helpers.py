"""Utility helpers for API logging components.

This module centralizes the shared helpers used by the logging middleware and
route instrumentation so they can be reused without duplicating logic. The
helpers provide correlation ID management, logging adapters, and sanitization
utilities that protect sensitive information from being written to logs.
"""

from __future__ import annotations

import html
import json
import logging
import uuid
from contextvars import ContextVar
from typing import Any, Optional, Union

correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")
"""Context variable that stores the correlation identifier for the request."""

# Default paths that will be excluded from request logging output.
DEFAULT_EXCLUDE_PATHS: set[str] = {
    "/health",
    "/metrics",
    "/ping",
    "/favicon.ico",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Default HTTP headers that should be redacted in log output.
SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "password",
    "token",
    "secret",
}

# Default JSON fields that should be redacted in request and response bodies.
SENSITIVE_FIELDS: set[str] = {
    "password",
    "token",
    "secret",
    "api_key",
    "apiKey",
    "access_token",
    "refresh_token",
    "credit_card",
    "creditCard",
    "ssn",
    "social_security",
}


def get_correlation_id() -> str:
    """Return the correlation identifier for the active request context.

    Returns:
        str: The correlation identifier associated with the current task
        context. A new UUID is generated and stored when none exists so the
        caller always receives a valid identifier.
    """

    try:
        return correlation_id_context.get()
    except LookupError:
        new_id = str(uuid.uuid4())
        correlation_id_context.set(new_id)
        return new_id


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Persist a correlation identifier in the active request context.

    Args:
        correlation_id: Pre-generated identifier to store. When omitted a new
            UUID is created and used automatically.

    Returns:
        str: The identifier that is now stored in the context.
    """

    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_context.set(correlation_id)
    return correlation_id


def get_request_logger() -> logging.LoggerAdapter:
    """Create a logger adapter enriched with the correlation identifier.

    Returns:
        logging.LoggerAdapter: Logger adapter scoped to the correlation ID so
        downstream log statements automatically include request context.
    """

    correlation_id = get_correlation_id()
    return logging.LoggerAdapter(logging.getLogger("neuroca.api.middleware.logging"), {"correlation_id": correlation_id})


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive HTTP headers before logging them.

    Args:
        headers: Raw HTTP headers collected from a request or response.

    Returns:
        dict[str, str]: Sanitized headers where sensitive values are replaced
        with placeholder text.
    """

    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        sanitized[key] = "[REDACTED]" if key_lower in SENSITIVE_HEADERS else value
    return sanitized


def format_placeholder(label: str, value: Optional[str]) -> str:
    """Return an HTML safe placeholder for non-logged payloads.

    Args:
        label: Human readable descriptor for the placeholder, such as
            ``"binary data"``.
        value: Optional hint about the underlying content (for example the
            ``Content-Type`` header value).

    Returns:
        str: Sanitized placeholder string safe for log emission.
    """

    safe_value = html.escape(value or "unknown", quote=True)
    return f"<{label}: {safe_value}>"


def sanitize_body(body: Union[dict[str, Any], list[Any], str, None]) -> Union[dict[str, Any], list[Any], str, None]:
    """Redact sensitive fields in request or response bodies.

    Args:
        body: The decoded request or response payload.

    Returns:
        Union[dict[str, Any], list[Any], str, None]: Sanitized structure with
        sensitive fields replaced by placeholder text.
    """

    if body is None:
        return None

    if isinstance(body, str):
        try:
            parsed_body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return body
        sanitized = sanitize_body(parsed_body)
        return json.dumps(sanitized)

    if isinstance(body, dict):
        sanitized_dict: dict[str, Any] = {}
        for key, value in body.items():
            key_lower = key.lower() if isinstance(key, str) else key
            if isinstance(key_lower, str) and key_lower in SENSITIVE_FIELDS:
                sanitized_dict[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized_dict[key] = sanitize_body(value)
            else:
                sanitized_dict[key] = value
        return sanitized_dict

    if isinstance(body, list):
        return [sanitize_body(item) if isinstance(item, (dict, list)) else item for item in body]

    return body


__all__ = [
    "DEFAULT_EXCLUDE_PATHS",
    "SENSITIVE_HEADERS",
    "SENSITIVE_FIELDS",
    "correlation_id_context",
    "format_placeholder",
    "get_correlation_id",
    "get_request_logger",
    "sanitize_body",
    "sanitize_headers",
    "set_correlation_id",
]
