"""
Health Check Service

Provides health check functionality for monitoring API dependencies.
"""

from datetime import datetime
from typing import Dict, Any
import redis.asyncio as redis


class HealthCheckService:
    """Service for performing health checks on API dependencies."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize health check service.

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on all dependencies.

        Returns:
            Dict containing health status and dependency information
        """
        dependencies = {}
        all_healthy = True

        # Check Redis
        try:
            await self.redis_client.ping()
            dependencies["redis"] = {"status": "healthy", "message": "Connected"}
        except Exception as e:
            dependencies["redis"] = {"status": "unhealthy", "message": str(e)}
            all_healthy = False

        # Check database (simplified - would need actual DB connection)
        try:
            from app.database.connection import engine

            with engine.connect() as conn:
                conn.execute("SELECT 1")
            dependencies["database"] = {"status": "healthy", "message": "Connected"}
        except Exception as e:
            dependencies["database"] = {"status": "unhealthy", "message": str(e)}
            all_healthy = False

        # Check Celery (simplified - would need actual Celery inspection)
        dependencies["celery"] = {"status": "unknown", "message": "Not checked"}

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "dependencies": dependencies,
        }
