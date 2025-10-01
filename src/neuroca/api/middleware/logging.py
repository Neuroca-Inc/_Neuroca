"""Compatibility layer for API logging middleware components.

The original implementation co-located middleware, helper utilities, and
route instrumentation within a single module. To comply with the clean
architecture "one class per file" guidance, the implementation now lives in
specialised modules which are re-exported here for backwards compatibility.
"""

from __future__ import annotations

import sys
from importlib import import_module, util
from pathlib import Path
from types import ModuleType


def _ensure_package(name: str) -> None:
    """Ensure an importable namespace package exists in ``sys.modules``."""

    if name in sys.modules:
        return

    module = ModuleType(name)
    module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = module


for _package in ("neuroca", "neuroca.api", "neuroca.api.middleware"):
    _ensure_package(_package)


def _load_local_module(name: str) -> ModuleType:
    """Load a sibling module using the file system path.

    Args:
        name: Base filename (without extension) of the module to load.

    Returns:
        ModuleType: Dynamically loaded module reference.
    """

    base_dir = Path(__file__).resolve().parent
    module_path = base_dir / f"{name}.py"
    full_name = f"neuroca.api.middleware.{name}"
    spec = util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {name} from {module_path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[full_name] = module
    return module


def _import_module(name: str) -> ModuleType:
    """Import a module either relatively or via file-based fallback.

    Args:
        name: Module basename without the package prefix.

    Returns:
        ModuleType: Imported module reference ready for attribute access.
    """

    try:
        return import_module(f"{__package__}.{name}") if __package__ else import_module(name)
    except ImportError:
        return _load_local_module(name)


_helpers = _import_module("logging_helpers")
_route = _import_module("logging_route")
_middleware = _import_module("request_logging_middleware")

DEFAULT_EXCLUDE_PATHS = _helpers.DEFAULT_EXCLUDE_PATHS
SENSITIVE_FIELDS = _helpers.SENSITIVE_FIELDS
SENSITIVE_HEADERS = _helpers.SENSITIVE_HEADERS
correlation_id_context = _helpers.correlation_id_context
format_placeholder = _helpers.format_placeholder
get_correlation_id = _helpers.get_correlation_id
get_request_logger = _helpers.get_request_logger
sanitize_body = _helpers.sanitize_body
sanitize_headers = _helpers.sanitize_headers
set_correlation_id = _helpers.set_correlation_id

LoggingRoute = _route.LoggingRoute
RequestLoggingMiddleware = _middleware.RequestLoggingMiddleware
setup_request_logging = _middleware.setup_request_logging

# Historical name retained for backwards compatibility with tests importing the
# private helper directly from this module.
_format_placeholder = format_placeholder

# Backwards compatible alias expected by callers importing ``LoggingMiddleware``
# from this module.
LoggingMiddleware = RequestLoggingMiddleware

__all__ = [
    "DEFAULT_EXCLUDE_PATHS",
    "LoggingMiddleware",
    "LoggingRoute",
    "RequestLoggingMiddleware",
    "SENSITIVE_FIELDS",
    "SENSITIVE_HEADERS",
    "correlation_id_context",
    "format_placeholder",
    "_format_placeholder",
    "get_correlation_id",
    "get_request_logger",
    "sanitize_body",
    "sanitize_headers",
    "set_correlation_id",
    "setup_request_logging",
]
