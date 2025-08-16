"""
NeuroCognitive Architecture (NCA) API package.

Lightweight initializer (no framework imports at import time).
Use FastAPI app at neuroca.api.main:app to run the service.

Examples:
- uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000 --reload
- from neuroca.api.main import app  # FastAPI instance
"""

from __future__ import annotations

import logging

# Package metadata
__version__ = "0.1.0"
__all__ = ["__version__", "create_app"]

logger = logging.getLogger(__name__)


def create_app(*_args, **_kwargs):
    """
    Deprecated legacy shim for historical Flask entrypoints.

    Runtime behavior:
    - This function exists to avoid hard import failures in environments
      that still import neuroca.api:create_app.
    - It intentionally raises at call time (not at import time) to guide
      callers toward the FastAPI application.

    Preferred usage:
    - uvicorn neuroca.api.main:app
    - from neuroca.api.main import app
    """
    raise RuntimeError(
        "Legacy Flask API entrypoint is deprecated. "
        "Use FastAPI app at neuroca.api.main:app (e.g., "
        "'uvicorn neuroca.api.main:app --reload')."
    )
