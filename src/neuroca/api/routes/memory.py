"""Aggregate memory API routers."""

from fastapi import APIRouter

from .memory_v1 import router as router_v1

router = APIRouter()
router.include_router(router_v1)

__all__ = ["router", "router_v1"]
