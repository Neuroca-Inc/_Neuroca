"""
Monitoring API Routes for NeuroCognitive Architecture (NCA)

This module provides endpoints for monitoring system performance, metrics,
and operational status. It includes real-time metrics, historical data,
and alerting capabilities.

Usage:
    These routes provide monitoring services:
    - System Metrics: CPU, memory, disk usage
    - Application Metrics: Request rates, response times
    - Health Monitoring: Component health and status
    - Performance Analytics: Trend analysis and reporting

Security:
    Monitoring endpoints may expose sensitive system information
    and should be properly secured with appropriate authentication.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/monitoring",
    tags=["monitoring"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    },
)


# Pydantic models for monitoring
class SystemMetrics(BaseModel):
    """Model for system performance metrics."""
    cpu_percent: float = Field(ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(ge=0, le=100, description="Memory usage percentage")
    disk_percent: float = Field(ge=0, le=100, description="Disk usage percentage")
    network_bytes_sent: int = Field(ge=0, description="Network bytes sent")
    network_bytes_recv: int = Field(ge=0, description="Network bytes received")
    load_average: Optional[float] = Field(None, description="System load average")
    uptime_seconds: int = Field(ge=0, description="System uptime in seconds")


class ApplicationMetrics(BaseModel):
    """Model for application performance metrics."""
    requests_per_second: float = Field(ge=0, description="Requests per second")
    average_response_time_ms: float = Field(ge=0, description="Average response time in milliseconds")
    error_rate_percent: float = Field(ge=0, le=100, description="Error rate percentage")
    active_connections: int = Field(ge=0, description="Active connections count")
    memory_usage_mb: float = Field(ge=0, description="Application memory usage in MB")
    threads_count: int = Field(ge=0, description="Active threads count")


class MemoryTierMetrics(BaseModel):
    """Model for memory tier performance metrics."""
    tier_name: str = Field(description="Memory tier name (STM, MTM, LTM)")
    items_count: int = Field(ge=0, description="Number of items in tier")
    size_mb: float = Field(ge=0, description="Tier size in megabytes")
    hit_rate_percent: float = Field(ge=0, le=100, description="Cache hit rate percentage")
    operations_per_second: float = Field(ge=0, description="Operations per second")
    average_latency_ms: float = Field(ge=0, description="Average operation latency")


class MetricsSnapshot(BaseModel):
    """Model for a complete metrics snapshot."""
    timestamp: str
    system: SystemMetrics
    application: ApplicationMetrics
    memory_tiers: list[MemoryTierMetrics]


class AlertRule(BaseModel):
    """Model for monitoring alert rules."""
    rule_id: str
    name: str
    metric: str
    operator: str = Field(description="Comparison operator (>, <, >=, <=, ==)")
    threshold: float
    severity: str = Field(description="Alert severity (low, medium, high, critical)")
    enabled: bool = True


class Alert(BaseModel):
    """Model for monitoring alerts."""
    alert_id: str
    rule_id: str
    rule_name: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    message: str
    triggered_at: str
    resolved_at: Optional[str] = None
    status: str = Field(description="Alert status (active, resolved)")


@router.get(
    "/metrics/current",
    summary="Get current metrics",
    description="Get current system and application metrics snapshot",
    response_model=MetricsSnapshot,
)
async def get_current_metrics() -> MetricsSnapshot:
    """
    Get current metrics snapshot.
    
    Returns:
        MetricsSnapshot: Current system and application metrics
    """
    try:
        import psutil
        import time
        from datetime import datetime
        
        # Collect system metrics
        system_metrics = SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage('/').percent,
            network_bytes_sent=psutil.net_io_counters().bytes_sent,
            network_bytes_recv=psutil.net_io_counters().bytes_recv,
            load_average=psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None,
            uptime_seconds=int(time.time() - psutil.boot_time()),
        )
        
        # Collect application metrics
        process = psutil.Process()
        app_metrics = ApplicationMetrics(
            requests_per_second=10.5,  # Would be calculated from actual metrics
            average_response_time_ms=125.3,  # Would be calculated from actual metrics
            error_rate_percent=0.1,  # Would be calculated from actual metrics
            active_connections=5,  # Would be from connection pool metrics
            memory_usage_mb=process.memory_info().rss / 1024 / 1024,
            threads_count=process.num_threads(),
        )
        
        # Collect memory tier metrics
        memory_tier_metrics = [
            MemoryTierMetrics(
                tier_name="STM",
                items_count=150,
                size_mb=10.5,
                hit_rate_percent=95.2,
                operations_per_second=500.0,
                average_latency_ms=2.1,
            ),
            MemoryTierMetrics(
                tier_name="MTM",
                items_count=1250,
                size_mb=125.3,
                hit_rate_percent=88.7,
                operations_per_second=200.0,
                average_latency_ms=8.5,
            ),
            MemoryTierMetrics(
                tier_name="LTM",
                items_count=50000,
                size_mb=450.7,
                hit_rate_percent=75.1,
                operations_per_second=50.0,
                average_latency_ms=25.2,
            ),
        ]
        
        return MetricsSnapshot(
            timestamp=datetime.now().isoformat(),
            system=system_metrics,
            application=app_metrics,
            memory_tiers=memory_tier_metrics,
        )
        
    except Exception as e:
        logger.exception("Failed to collect current metrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect metrics: {str(e)}",
        ) from e


@router.get(
    "/metrics/history",
    summary="Get metrics history",
    description="Get historical metrics data for analysis",
)
async def get_metrics_history(
    hours: int = 24,
    metric: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Get historical metrics data.
    
    Args:
        hours: Number of hours of history to retrieve
        metric: Optional specific metric to retrieve
        
    Returns:
        List[Dict]: Historical metrics data
    """
    try:
        # In real implementation, this would query time-series database
        logger.info(f"Retrieving {hours} hours of metrics history")
        
        # Return mock historical data
        return [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "cpu_percent": 45.2,
                "memory_percent": 67.8,
                "requests_per_second": 12.3,
            },
            {
                "timestamp": "2024-01-01T01:00:00Z",
                "cpu_percent": 52.1,
                "memory_percent": 69.2,
                "requests_per_second": 15.7,
            },
        ]
        
    except Exception as e:
        logger.exception("Failed to retrieve metrics history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics history: {str(e)}",
        ) from e


@router.get(
    "/alerts",
    summary="Get active alerts",
    description="Get list of active monitoring alerts",
    response_model=list[Alert],
)
async def get_active_alerts() -> list[Alert]:
    """
    Get list of active alerts.
    
    Returns:
        List[Alert]: Active monitoring alerts
    """
    try:
        # In real implementation, this would query alerts database
        logger.info("Retrieving active alerts")
        
        return [
            Alert(
                alert_id="alert_1",
                rule_id="rule_cpu_high",
                rule_name="High CPU Usage",
                metric="cpu_percent",
                current_value=85.2,
                threshold=80.0,
                severity="high",
                message="CPU usage is above 80%",
                triggered_at="2024-01-01T12:00:00Z",
                status="active",
            ),
        ]
        
    except Exception as e:
        logger.exception("Failed to retrieve active alerts")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve alerts: {str(e)}",
        ) from e


@router.get(
    "/alerts/rules",
    summary="Get alert rules",
    description="Get list of monitoring alert rules",
    response_model=list[AlertRule],
)
async def get_alert_rules() -> list[AlertRule]:
    """
    Get list of alert rules.
    
    Returns:
        List[AlertRule]: Monitoring alert rules
    """
    try:
        # In real implementation, this would query rules database
        logger.info("Retrieving alert rules")
        
        return [
            AlertRule(
                rule_id="rule_cpu_high",
                name="High CPU Usage",
                metric="cpu_percent",
                operator=">",
                threshold=80.0,
                severity="high",
                enabled=True,
            ),
            AlertRule(
                rule_id="rule_memory_high",
                name="High Memory Usage",
                metric="memory_percent",
                operator=">",
                threshold=85.0,
                severity="high",
                enabled=True,
            ),
            AlertRule(
                rule_id="rule_error_rate",
                name="High Error Rate",
                metric="error_rate_percent",
                operator=">",
                threshold=5.0,
                severity="critical",
                enabled=True,
            ),
        ]
        
    except Exception as e:
        logger.exception("Failed to retrieve alert rules")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve alert rules: {str(e)}",
        ) from e


@router.post(
    "/alerts/rules",
    summary="Create alert rule",
    description="Create a new monitoring alert rule",
    response_model=dict[str, str],
)
async def create_alert_rule(rule: AlertRule) -> dict[str, str]:
    """
    Create a new alert rule.
    
    Args:
        rule: Alert rule configuration
        
    Returns:
        Dict: Created rule information
    """
    try:
        # In real implementation, this would save to database
        logger.info(f"Creating alert rule: {rule.name}")
        
        return {
            "rule_id": rule.rule_id,
            "message": f"Alert rule '{rule.name}' created successfully",
        }
        
    except Exception as e:
        logger.exception("Failed to create alert rule")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert rule: {str(e)}",
        ) from e


@router.get(
    "/performance/summary",
    summary="Get performance summary",
    description="Get summary of system performance over time",
)
async def get_performance_summary(hours: int = 24) -> dict[str, Any]:
    """
    Get performance summary.
    
    Args:
        hours: Number of hours to summarize
        
    Returns:
        Dict: Performance summary data
    """
    try:
        # In real implementation, this would analyze historical data
        logger.info(f"Generating performance summary for {hours} hours")
        
        return {
            "period_hours": hours,
            "average_cpu_percent": 45.2,
            "average_memory_percent": 67.8,
            "average_response_time_ms": 125.3,
            "total_requests": 12500,
            "total_errors": 15,
            "error_rate_percent": 0.12,
            "peak_cpu_percent": 85.2,
            "peak_memory_percent": 78.9,
            "slowest_response_ms": 2500.0,
            "fastest_response_ms": 12.5,
        }
        
    except Exception as e:
        logger.exception("Failed to generate performance summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate performance summary: {str(e)}",
        ) from e


@router.get(
    "/health/components",
    summary="Get component health status",
    description="Get health status of all monitored components",
)
async def get_component_health() -> dict[str, Any]:
    """
    Get health status of monitored components.
    
    Returns:
        Dict: Component health status
    """
    try:
        # In real implementation, this would check actual component health
        logger.info("Retrieving component health status")
        
        return {
            "overall_status": "healthy",
            "components": {
                "api_server": {
                    "status": "healthy",
                    "response_time_ms": 15.2,
                    "uptime_hours": 168.5,
                },
                "memory_system": {
                    "status": "healthy",
                    "active_tiers": 3,
                    "total_items": 51400,
                },
                "database": {
                    "status": "healthy",
                    "connection_pool_active": 5,
                    "connection_pool_max": 20,
                },
                "llm_integration": {
                    "status": "degraded",
                    "active_providers": 1,
                    "total_providers": 2,
                    "last_error": "Provider timeout",
                },
            },
            "last_check": "2024-01-01T12:00:00Z",
        }
        
    except Exception as e:
        logger.exception("Failed to retrieve component health")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve component health: {str(e)}",
        ) from e


@router.get(
    "/logs/recent",
    summary="Get recent logs",
    description="Get recent system logs for monitoring",
)
async def get_recent_logs(
    level: str = "info",
    lines: int = 100,
) -> dict[str, Any]:
    """
    Get recent system logs.
    
    Args:
        level: Log level filter (debug, info, warning, error)
        lines: Number of log lines to retrieve
        
    Returns:
        Dict: Recent log entries
    """
    try:
        # In real implementation, this would read from log files
        logger.info(f"Retrieving {lines} recent log lines at {level} level")
        
        return {
            "level": level,
            "lines_requested": lines,
            "lines_returned": 3,
            "logs": [
                {
                    "timestamp": "2024-01-01T12:00:00Z",
                    "level": "info",
                    "logger": "neuroca.api.routes.memory",
                    "message": "Memory operation completed successfully",
                },
                {
                    "timestamp": "2024-01-01T12:01:00Z",
                    "level": "warning",
                    "logger": "neuroca.integration.manager",
                    "message": "Provider response time exceeded threshold",
                },
                {
                    "timestamp": "2024-01-01T12:02:00Z",
                    "level": "error",
                    "logger": "neuroca.core.health.monitor",
                    "message": "Health check failed for component: llm_provider_2",
                },
            ],
        }
        
    except Exception as e:
        logger.exception("Failed to retrieve recent logs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve logs: {str(e)}",
        ) from e


@router.get(
    "/status",
    summary="Get monitoring system status",
    description="Get overall status of the monitoring system",
)
async def get_monitoring_status() -> dict[str, Any]:
    """
    Get monitoring system status.
    
    Returns:
        Dict: Monitoring system status
    """
    try:
        return {
            "status": "operational",
            "metrics_collection": "active",
            "alerting": "active",
            "log_aggregation": "active",
            "data_retention_days": 30,
            "active_alerts": 1,
            "total_rules": 15,
            "last_metrics_update": "2024-01-01T12:00:00Z",
        }
        
    except Exception as e:
        logger.exception("Failed to get monitoring status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitoring status: {str(e)}",
        ) from e
