"""
API Routes package (lightweight).

This package intentionally avoids importing submodules at import time to
keep the dependency graph thin and prevent optional components from
breaking the API startup. Import routers explicitly from their modules
when needed, e.g.:

    from neuroca.api.routes.llm import router as llm_router

If you need to register the full route set, call register_routes(app).
This function performs lazy imports and skips unavailable modules.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

logger = logging.getLogger(__name__)

__all__ = ["register_routes"]


def register_routes(app: FastAPI) -> None:
    """
    Lazily register available routers on the provided FastAPI app.

    This function attempts to import known route modules and include them
    under the configured API prefix. Any missing modules are skipped so the
    core service can start with a reduced feature set.

    Note: For minimal deployments that only need the LLM endpoint, import the
    LLM router directly and include it in your app:

        from neuroca.api.routes.llm import router as llm_router
        app.include_router(llm_router, prefix="/api")

    """
    # Perform imports lazily and skip failures
    try:
        from neuroca.config import settings  # type: ignore
        api_prefix = getattr(settings, "API_PREFIX", "/api")
        auth_enabled = bool(getattr(settings, "AUTH_ENABLED", False))
    except Exception:
        api_prefix = "/api"
        auth_enabled = False

    def _include(name: str, mod: str, router_name: str = "router") -> None:
        try:
            module = __import__(mod, fromlist=[router_name])
            router = getattr(module, router_name)
            app.include_router(router, prefix=api_prefix)
            logger.debug("Included router %s from %s", name, mod)
        except Exception as e:
            logger.debug("Skipping router %s (%s): %s", name, mod, e)

    # Include commonly available routers if present
    _include("health", "neuroca.api.routes.health")
    _include("monitoring", "neuroca.api.routes.monitoring")
    _include("system", "neuroca.api.routes.system")
    _include("memory", "neuroca.api.routes.memory")
    _include("cognitive", "neuroca.api.routes.cognitive")
    _include("integration", "neuroca.api.routes.integration")
    _include("admin", "neuroca.api.routes.admin")
    _include("auth", "neuroca.api.routes.auth")

    # LLM router can also be included from here if desired
    _include("llm", "neuroca.api.routes.llm")

    logger.info("Route registration completed (lazy, best-effort).")