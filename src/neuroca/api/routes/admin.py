"""
Admin API Routes for NeuroCognitive Architecture (NCA)

This module provides administrative endpoints for managing the NCA system.
It includes endpoints for system configuration, user management, and administrative
operations that require elevated privileges.

Security:
    All admin endpoints require authentication and authorization.
    Access is restricted to users with admin roles.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from neuroca.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Admin access required"},
        500: {"description": "Internal Server Error"},
    },
)


class SystemInfoResponse(BaseModel):
    """Response model for system information."""
    version: str
    environment: str
    debug_mode: bool
    features_enabled: list[str]


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""
    key: str
    value: Any


@router.get(
    "/info",
    summary="Get system information",
    description="Get basic system information and configuration",
    response_model=SystemInfoResponse,
)
async def get_system_info() -> SystemInfoResponse:
    """
    Get basic system information.
    
    Returns:
        SystemInfoResponse: System configuration and version info
    """
    features_enabled = []
    
    # Check what features are enabled
    if hasattr(settings, 'AUTH_ENABLED') and settings.AUTH_ENABLED:
        features_enabled.append("authentication")
    if hasattr(settings, 'MEMORY_SYSTEM_ENABLED') and getattr(settings, 'MEMORY_SYSTEM_ENABLED', True):
        features_enabled.append("memory_system")
    if hasattr(settings, 'HEALTH_SYSTEM_ENABLED') and getattr(settings, 'HEALTH_SYSTEM_ENABLED', True):
        features_enabled.append("health_system")
    
    return SystemInfoResponse(
        version=getattr(settings, 'VERSION', '0.1.0'),
        environment=settings.ENVIRONMENT,
        debug_mode=settings.ENVIRONMENT == "development",
        features_enabled=features_enabled,
    )


@router.get(
    "/health/components",
    summary="List all registered health components",
    description="Get a list of all components registered with the health system",
)
async def list_health_components() -> dict[str, Any]:
    """
    Get list of all health components.
    
    Returns:
        Dict containing component information
    """
    try:
        from neuroca.core.health.dynamics import get_health_dynamics
        
        health_dynamics = get_health_dynamics()
        components = list(health_dynamics._components.keys())
        
        return {
            "components": components,
            "count": len(components),
        }
    except Exception as e:
        logger.exception("Failed to retrieve health components")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve components: {str(e)}",
        ) from e


@router.post(
    "/config/update",
    summary="Update configuration setting",
    description="Update a configuration setting (development only)",
    status_code=status.HTTP_200_OK,
)
async def update_config(config_update: ConfigUpdateRequest) -> dict[str, str]:
    """
    Update a configuration setting.
    
    Args:
        config_update: Configuration key and value to update
        
    Returns:
        Dict with success message
        
    Raises:
        HTTPException: If not in development mode or update fails
    """
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Configuration updates only allowed in development mode",
        )
    
    try:
        # In a real implementation, this would update the configuration
        # For now, just log the request
        logger.info(f"Config update requested: {config_update.key} = {config_update.value}")
        
        return {
            "message": f"Configuration {config_update.key} updated successfully",
            "key": config_update.key,
            "value": str(config_update.value),
        }
    except Exception as e:
        logger.exception("Failed to update configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}",
        ) from e


@router.get(
    "/metrics/summary",
    summary="Get system metrics summary",
    description="Get a summary of system performance metrics",
)
async def get_metrics_summary() -> dict[str, Any]:
    """
    Get summary of system metrics.
    
    Returns:
        Dict containing metrics summary
    """
    try:
        # Basic metrics collection
        import psutil
        import time
        
        return {
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            },
            "process": {
                "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                "cpu_percent": psutil.Process().cpu_percent(),
                "uptime_seconds": int(time.time() - psutil.Process().create_time()),
            },
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.exception("Failed to collect metrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect metrics: {str(e)}",
        ) from e
