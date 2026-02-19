"""
Health Check Routes

Endpoints for API health monitoring.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Optional

from app.services.health_check import HealthCheckService

router = APIRouter(tags=["Health"])

# Global health check service instance
health_service: Optional[HealthCheckService] = None


def init_health_routes(redis_client):
    """
    Initialize health routes with Redis client.

    Args:
        redis_client: Redis client instance
    """
    global health_service
    health_service = HealthCheckService(redis_client=redis_client)


@router.get("/health")
async def root_health_check():
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
    if not health_service:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": "Health service not initialized"},
        )

    # Perform health check
    health_status = await health_service.perform_health_check()

    # Return 503 if any component is unhealthy
    status_code = 200 if health_status["status"] == "healthy" else 503

    return JSONResponse(status_code=status_code, content=health_status)


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness probe endpoint.

    Verifies that all dependencies (database, Redis, Celery) are available
    and the API is ready to serve requests.

    Returns:
        JSON response with readiness status

    Response Codes:
        200: API is ready
        503: API is not ready (dependencies unavailable)
    """
    if not health_service:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": "Health service not initialized"},
        )

    # Perform readiness check (same as health check)
    health_status = await health_service.perform_health_check()

    # Return 503 if any component is unhealthy
    status_code = 200 if health_status["status"] == "healthy" else 503

    return JSONResponse(status_code=status_code, content=health_status)


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
