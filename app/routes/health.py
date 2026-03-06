"""
Health Check Routes

Endpoints for API health monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio

from app.services.health_check import HealthCheckService

router = APIRouter(tags=["Health"])

# Global health check service instance
health_service: Optional[HealthCheckService] = None


async def get_health_service() -> HealthCheckService:
    """Get health service dependency."""
    if health_service is None:
        # Trigger alert for uninitialized service
        from app.middleware.alerting import alert_manager, AlertSeverity

        # Create alert for uninitialized health service (fire and forget)
        asyncio.create_task(
            alert_manager.trigger_custom_alert(
                title="Health Service Uninitialized",
                message="Health check endpoint accessed but health service is not initialized",
                severity=AlertSeverity.CRITICAL,
                metadata={
                    "endpoint": "/health",
                    "error": "Health service not initialized",
                    "timestamp": "immediate",
                },
            )
        )

        raise HTTPException(
            status_code=503,
            detail="Health service not initialized",
        )
    return health_service


def init_health_routes(redis_client):
    """
    Initialize health routes with Redis client.

    Args:
        redis_client: Redis client instance
    """
    global health_service
    health_service = HealthCheckService(redis_client=redis_client)


@router.get("/health")
async def root_health_check(health_service: HealthCheckService = Depends(get_health_service)):
    """
    Comprehensive health check endpoint at root path.

    Checks the health of all API dependencies:
    - Database connectivity
    - Redis connectivity
    - Celery worker status

    Returns:
        JSON response with overall status and individual component checks

    Response Codes:
        200: All components healthy
        503: One or more components unhealthy
    """
    # Perform health check
    health_status = await health_service.perform_health_check()

    # Return 503 if any component is unhealthy
    status_code = 200 if health_status["status"] == "healthy" else 503

    return JSONResponse(status_code=status_code, content=health_status)


@router.get("/health/ready")
async def readiness_check(health_service: HealthCheckService = Depends(get_health_service)):
    """
    Readiness probe endpoint.

    Verifies that critical dependencies (database, Redis) are available
    and API is ready to serve requests.

    Returns:
        JSON response with readiness status

    Response Codes:
        200: API is ready
        503: API is not ready (dependencies unavailable)
    """
    # Perform readiness check (critical dependencies only)
    readiness_status = await health_service.perform_readiness_check()

    # Return 503 if any critical component is not ready
    status_code = 200 if readiness_status["status"] == "ready" else 503

    return JSONResponse(status_code=status_code, content=readiness_status)


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe endpoint.

    Simple check to verify the API process is running and responsive.
    Does not check dependencies.

    Returns:
        JSON response indicating the API is alive

    Response Codes:
        200: API process is alive
    """
    return JSONResponse(
        status_code=200,
        content={"status": "alive", "message": "API is running"},
    )
