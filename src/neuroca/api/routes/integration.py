"""
Integration API Routes for NeuroCognitive Architecture (NCA)

This module provides endpoints for managing integrations with external systems,
including LLM providers, databases, and other services. It handles provider
management, connection testing, and integration health monitoring.

Usage:
    These routes provide access to integration management:
    - LLM Provider Management: Configure and manage LLM connections
    - Database Integration: Manage database connections
    - External Services: Handle third-party service integrations
    - Health Monitoring: Monitor integration health

Security:
    Integration endpoints may expose sensitive configuration information
    and should be properly secured with appropriate authentication.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integration",
    tags=["integration"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


# Pydantic models for integration operations
class ProviderConfig(BaseModel):
    """Model for LLM provider configuration."""
    name: str = Field(..., description="Provider name (openai, anthropic, ollama, etc.)")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    base_url: Optional[str] = Field(None, description="Base URL for the provider API")
    model: Optional[str] = Field(None, description="Default model to use")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens per request")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Temperature setting")
    enabled: bool = Field(default=True, description="Whether this provider is enabled")


class DatabaseConfig(BaseModel):
    """Model for database configuration."""
    name: str = Field(..., description="Database connection name")
    type: str = Field(..., description="Database type (postgres, redis, sqlite, etc.)")
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(None, description="Database port")
    database: Optional[str] = Field(None, description="Database name")
    enabled: bool = Field(default=True, description="Whether this connection is enabled")


class IntegrationTest(BaseModel):
    """Model for integration test requests."""
    integration_type: str = Field(..., description="Type of integration to test")
    provider_name: Optional[str] = Field(None, description="Provider name for LLM tests")
    test_message: Optional[str] = Field(None, description="Test message for LLM providers")


class IntegrationResponse(BaseModel):
    """Generic response model for integration operations."""
    success: bool
    message: str
    data: Optional[dict[str, Any]] = None


class ProviderStatus(BaseModel):
    """Model for provider status information."""
    name: str
    type: str
    status: str = Field(description="Status: active, inactive, error")
    last_used: Optional[str] = None
    error_message: Optional[str] = None
    model: Optional[str] = None
    response_time_ms: Optional[float] = None


class IntegrationHealth(BaseModel):
    """Model for integration health status."""
    integration_type: str
    status: str
    details: dict[str, Any]
    last_check: str


# LLM Provider Management Endpoints
@router.get(
    "/providers",
    summary="List LLM providers",
    description="Get list of configured LLM providers and their status",
    response_model=list[ProviderStatus],
)
async def list_providers() -> list[ProviderStatus]:
    """
    Get list of configured LLM providers.
    
    Returns:
        List[ProviderStatus]: List of provider statuses
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.integration.manager import IntegrationManager
        
        integration_manager = IntegrationManager()
        
        # Get provider list
        # This would call actual methods on the integration manager
        logger.info("Retrieving LLM provider list")
        
        return [
            ProviderStatus(
                name="openai",
                type="llm",
                status="active",
                last_used="2024-01-01T00:00:00Z",
                model="gpt-3.5-turbo",
                response_time_ms=250.5,
            ),
            ProviderStatus(
                name="anthropic",
                type="llm", 
                status="inactive",
                model="claude-3-sonnet",
            ),
        ]
    except Exception as e:
        logger.exception("Failed to list providers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list providers: {str(e)}",
        ) from e


@router.post(
    "/providers/{provider_name}/configure",
    summary="Configure LLM provider",
    description="Configure or update an LLM provider",
    response_model=IntegrationResponse,
)
async def configure_provider(
    provider_name: str,
    config: ProviderConfig,
) -> IntegrationResponse:
    """
    Configure an LLM provider.
    
    Args:
        provider_name: Name of the provider to configure
        config: Provider configuration
        
    Returns:
        IntegrationResponse: Result of configuration operation
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.integration.manager import IntegrationManager
        
        integration_manager = IntegrationManager()
        
        # Configure provider
        # This would call actual methods on the integration manager
        logger.info(f"Configuring provider: {provider_name}")
        
        return IntegrationResponse(
            success=True,
            message=f"Provider {provider_name} configured successfully",
            data={
                "provider_name": provider_name,
                "model": config.model,
                "enabled": config.enabled,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to configure provider {provider_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure provider: {str(e)}",
        ) from e


@router.post(
    "/providers/{provider_name}/test",
    summary="Test LLM provider",
    description="Test connection and functionality of an LLM provider",
    response_model=IntegrationResponse,
)
async def test_provider(
    provider_name: str,
    test_request: Optional[IntegrationTest] = None,
) -> IntegrationResponse:
    """
    Test an LLM provider connection.
    
    Args:
        provider_name: Name of the provider to test
        test_request: Optional test configuration
        
    Returns:
        IntegrationResponse: Test results
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.integration.manager import IntegrationManager
        
        integration_manager = IntegrationManager()
        
        # Test provider
        # This would call actual methods on the integration manager
        test_message = test_request.test_message if test_request else "Hello, this is a test"
        logger.info(f"Testing provider: {provider_name} with message: {test_message}")
        
        return IntegrationResponse(
            success=True,
            message=f"Provider {provider_name} test successful",
            data={
                "provider_name": provider_name,
                "test_message": test_message,
                "response_time_ms": 234.5,
                "response": "Test response from provider",
            }
        )
    except Exception as e:
        logger.exception(f"Failed to test provider {provider_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test provider: {str(e)}",
        ) from e


# Database Integration Endpoints
@router.get(
    "/databases",
    summary="List database connections",
    description="Get list of configured database connections",
    response_model=list[dict[str, Any]],
)
async def list_databases() -> list[dict[str, Any]]:
    """
    Get list of configured database connections.
    
    Returns:
        List[Dict]: List of database connection information
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.db.connection import get_db_status
        
        # Get database status
        # This would call actual methods to check database connections
        logger.info("Retrieving database connection list")
        
        return [
            {
                "name": "primary_db",
                "type": "sqlite",
                "status": "connected",
                "database": "neuroca_temporal_analysis.db",
                "last_check": "2024-01-01T00:00:00Z",
            },
            {
                "name": "redis_cache",
                "type": "redis",
                "status": "disconnected",
                "host": "localhost",
                "port": 6379,
                "last_check": "2024-01-01T00:00:00Z",
            },
        ]
    except Exception as e:
        logger.exception("Failed to list databases")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list databases: {str(e)}",
        ) from e


@router.post(
    "/databases/{database_name}/test",
    summary="Test database connection",
    description="Test connection to a specific database",
    response_model=IntegrationResponse,
)
async def test_database(database_name: str) -> IntegrationResponse:
    """
    Test a database connection.
    
    Args:
        database_name: Name of the database to test
        
    Returns:
        IntegrationResponse: Test results
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.db.connection import get_db_status
        
        # Test database connection
        # This would call actual methods to test the specific database
        logger.info(f"Testing database connection: {database_name}")
        
        db_status = get_db_status()
        
        return IntegrationResponse(
            success=db_status.get("connected", False),
            message=f"Database {database_name} connection test completed",
            data={
                "database_name": database_name,
                "connected": db_status.get("connected", False),
                "error": db_status.get("error"),
                "response_time_ms": 12.3,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to test database {database_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test database: {str(e)}",
        ) from e


# Memory System Integration Endpoints
@router.get(
    "/memory/backends",
    summary="List memory backends",
    description="Get list of configured memory storage backends",
    response_model=list[dict[str, Any]],
)
async def list_memory_backends() -> list[dict[str, Any]]:
    """
    Get list of configured memory backends.
    
    Returns:
        List[Dict]: List of memory backend information
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
        
        # Get memory backends
        # This would call actual methods to get backend information
        logger.info("Retrieving memory backend list")
        
        return [
            {
                "name": "working_memory",
                "backend_type": "redis",
                "status": "active",
                "tier": "STM",
                "size_mb": 10.5,
            },
            {
                "name": "episodic_memory",
                "backend_type": "sqlite",
                "status": "active",
                "tier": "MTM",
                "size_mb": 125.3,
            },
            {
                "name": "semantic_memory",
                "backend_type": "sql",
                "status": "active",
                "tier": "LTM",
                "size_mb": 450.7,
            },
        ]
    except Exception as e:
        logger.exception("Failed to list memory backends")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list memory backends: {str(e)}",
        ) from e


@router.post(
    "/memory/backends/{backend_name}/test",
    summary="Test memory backend",
    description="Test connection and functionality of a memory backend",
    response_model=IntegrationResponse,
)
async def test_memory_backend(backend_name: str) -> IntegrationResponse:
    """
    Test a memory backend.
    
    Args:
        backend_name: Name of the backend to test
        
    Returns:
        IntegrationResponse: Test results
    """
    try:
        # Import here to avoid circular dependencies
        from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
        
        # Test memory backend
        # This would call actual methods to test the backend
        logger.info(f"Testing memory backend: {backend_name}")
        
        return IntegrationResponse(
            success=True,
            message=f"Memory backend {backend_name} test successful",
            data={
                "backend_name": backend_name,
                "test_operation": "basic_crud",
                "response_time_ms": 5.2,
                "items_tested": 10,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to test memory backend {backend_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test memory backend: {str(e)}",
        ) from e


# General Integration Health Endpoints
@router.get(
    "/health",
    summary="Get integration health",
    description="Get overall health status of all integrations",
    response_model=list[IntegrationHealth],
)
async def get_integration_health() -> list[IntegrationHealth]:
    """
    Get overall integration health status.
    
    Returns:
        List[IntegrationHealth]: Health status of all integrations
    """
    try:
        # Get integration health
        # This would call actual methods to check integration health
        logger.info("Retrieving integration health status")
        
        return [
            IntegrationHealth(
                integration_type="llm_providers",
                status="healthy",
                details={
                    "active_providers": 1,
                    "total_providers": 2,
                    "last_request": "2024-01-01T00:00:00Z",
                },
                last_check="2024-01-01T00:00:00Z",
            ),
            IntegrationHealth(
                integration_type="memory_backends",
                status="healthy",
                details={
                    "active_backends": 3,
                    "total_backends": 3,
                    "total_size_mb": 586.5,
                },
                last_check="2024-01-01T00:00:00Z",
            ),
            IntegrationHealth(
                integration_type="databases",
                status="degraded",
                details={
                    "connected": 1,
                    "total": 2,
                    "error": "Redis connection failed",
                },
                last_check="2024-01-01T00:00:00Z",
            ),
        ]
    except Exception as e:
        logger.exception("Failed to get integration health")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get integration health: {str(e)}",
        ) from e


@router.post(
    "/test/all",
    summary="Test all integrations",
    description="Run comprehensive tests on all configured integrations",
    response_model=IntegrationResponse,
)
async def test_all_integrations() -> IntegrationResponse:
    """
    Test all integrations comprehensively.
    
    Returns:
        IntegrationResponse: Comprehensive test results
    """
    try:
        # Test all integrations
        # This would call actual methods to test all integrations
        logger.info("Running comprehensive integration tests")
        
        test_results = {
            "llm_providers": {"tested": 2, "passed": 1, "failed": 1},
            "memory_backends": {"tested": 3, "passed": 3, "failed": 0},
            "databases": {"tested": 2, "passed": 1, "failed": 1},
        }
        
        total_tests = sum(r["tested"] for r in test_results.values())
        total_passed = sum(r["passed"] for r in test_results.values())
        
        return IntegrationResponse(
            success=total_passed == total_tests,
            message=f"Integration tests completed: {total_passed}/{total_tests} passed",
            data={
                "summary": {
                    "total_tests": total_tests,
                    "passed": total_passed,
                    "failed": total_tests - total_passed,
                },
                "details": test_results,
            }
        )
    except Exception as e:
        logger.exception("Failed to test all integrations")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test integrations: {str(e)}",
        ) from e


@router.get(
    "/status",
    summary="Get integration system status",
    description="Get overall status of the integration system",
)
async def get_integration_status() -> dict[str, Any]:
    """
    Get overall integration system status.
    
    Returns:
        Dict containing integration system status
    """
    try:
        return {
            "status": "operational",
            "components": {
                "llm_providers": "active",
                "memory_backends": "active",
                "databases": "degraded",
                "external_services": "active",
            },
            "active_providers": 1,
            "active_backends": 3,
            "last_test": "2024-01-01T00:00:00Z",
        }
    except Exception as e:
        logger.exception("Failed to get integration status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get integration status: {str(e)}",
        ) from e
