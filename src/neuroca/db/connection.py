"""
Database Connection Module for NeuroCognitive Architecture.

This module provides a unified interface for database connections across
the NCA system. It serves as a facade over the specific connection implementations
in the connections package.

Usage:
    from neuroca.db.connection import get_connection, get_async_connection
    
    # Get a synchronous connection
    with get_connection() as conn:
        results = conn.execute_query("SELECT * FROM memory_items")
    
    # Get an asynchronous connection
    async with get_async_connection() as conn:
        results = await conn.execute_query("SELECT * FROM memory_items")
"""

import logging
from typing import Any, Dict, Optional, Union

from neuroca.db.connections.postgres import (
    PostgresConnection,
    AsyncPostgresConnection,
    PostgresConfig,
    get_postgres_connection
)
from neuroca.config.settings import get_settings

logger = logging.getLogger(__name__)


def get_connection(
    config: Optional[Dict[str, Any]] = None,
    connection_type: str = "postgres"
) -> Union[PostgresConnection]:
    """
    Get a database connection based on configuration.
    
    Args:
        config: Database configuration dictionary
        connection_type: Type of database connection (currently only 'postgres')
    
    Returns:
        Database connection instance
    
    Raises:
        ValueError: If unsupported connection type is specified
        RuntimeError: If connection creation fails
    """
    logger.debug("Creating %s database connection", connection_type)
    
    if connection_type.lower() == "postgres":
        if config:
            postgres_config = PostgresConfig(**config)
        else:
            postgres_config = PostgresConfig.from_env()
        
        return get_postgres_connection(postgres_config, async_mode=False)
    
    else:
        raise ValueError(f"Unsupported connection type: {connection_type}")


def get_async_connection(
    config: Optional[Dict[str, Any]] = None,
    connection_type: str = "postgres"
) -> Union[AsyncPostgresConnection]:
    """
    Get an asynchronous database connection based on configuration.
    
    Args:
        config: Database configuration dictionary
        connection_type: Type of database connection (currently only 'postgres')
    
    Returns:
        Async database connection instance
    
    Raises:
        ValueError: If unsupported connection type is specified
        RuntimeError: If connection creation fails
    """
    logger.debug("Creating async %s database connection", connection_type)
    
    if connection_type.lower() == "postgres":
        if config:
            postgres_config = PostgresConfig(**config)
        else:
            postgres_config = PostgresConfig.from_env()
        
        return get_postgres_connection(postgres_config, async_mode=True)
    
    else:
        raise ValueError(f"Unsupported connection type: {connection_type}")


def get_default_connection():
    """
    Get a default database connection using environment configuration.
    
    Returns:
        Default database connection instance
    """
    return get_connection()


def get_default_async_connection():
    """
    Get a default asynchronous database connection using environment configuration.
    
    Returns:
        Default async database connection instance
    """
    return get_async_connection()


def check_database_health(connection_type: str = "postgres") -> Dict[str, Any]:
    """
    Check the health of the database connection.
    
    Args:
        connection_type: Type of database to check
    
    Returns:
        Dictionary containing health status information
    """
    logger.debug("Checking database health for %s", connection_type)
    
    try:
        if connection_type.lower() == "postgres":
            with get_connection(connection_type=connection_type) as conn:
                return conn.check_connection_health()
        else:
            return {
                "status": "error",
                "message": f"Unsupported connection type: {connection_type}"
            }
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        return {
            "status": "unhealthy",
            "message": f"Database health check failed: {str(e)}",
            "error": str(e)
        }


# Export main functions
__all__ = [
    "get_connection",
    "get_async_connection", 
    "get_default_connection",
    "get_default_async_connection",
    "check_database_health",
    "PostgresConfig",
]
