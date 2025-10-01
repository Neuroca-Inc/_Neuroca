"""Shared constants used by the tracing middleware components."""

DEFAULT_EXCLUDE_PATHS: list[str] = [
    "/health",
    "/metrics",
    "/favicon.ico",
    "/docs",
    "/redoc",
    "/openapi.json",
]
"""Default set of HTTP paths that bypass tracing instrumentation."""
