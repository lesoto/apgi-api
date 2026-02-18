"""
Health Check Service

Provides health check functionality for monitoring API dependencies.
"""

from datetime import datetime
from typing import Dict, Any
import time
import redis.asyncio as redis
from sqlalchemy import text


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

        # Check Redis connectivity and performance
        try:
            start_time = time.time()
            await self.redis_client.ping()
            redis_time = time.time() - start_time

            # Performance threshold (in seconds)
            redis_threshold = 0.05  # 50ms

            if redis_time > redis_threshold:
                dependencies["redis"] = {
                    "status": "degraded",
                    "message": f"Connected but slow: {redis_time:.3f}s (threshold: {redis_threshold}s)",
                }
                all_healthy = False
            else:
                dependencies["redis"] = {
                    "status": "healthy",
                    "message": "Connected and responsive",
                    "response_time": f"{redis_time:.3f}s",
                }
        except Exception as e:
            dependencies["redis"] = {"status": "unhealthy", "message": str(e)}
            all_healthy = False

        # Check database connectivity and performance
        try:
            from app.database.connection import engine

            # Test basic connectivity
            start_time = time.time()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            connectivity_time = time.time() - start_time

            # Test query performance with a more complex query
            start_time = time.time()
            with engine.connect() as conn:
                # Test a query that exercises indexes and joins
                result = conn.execute(
                    text(
                        """
                    SELECT COUNT(*) as user_count
                    FROM users u
                    LEFT JOIN sessions s ON u.user_id = s.user_id
                    WHERE u.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
                """
                    )
                )
                user_count = result.fetchone()[0]
            query_time = time.time() - start_time

            # Performance thresholds (in seconds)
            connectivity_threshold = 0.1  # 100ms
            query_threshold = 0.5  # 500ms

            # Check performance
            performance_issues = []
            if connectivity_time > connectivity_threshold:
                performance_issues.append(
                    f"Connectivity slow: {connectivity_time:.3f}s (threshold: {connectivity_threshold}s)"
                )
            if query_time > query_threshold:
                performance_issues.append(
                    f"Query slow: {query_time:.3f}s (threshold: {query_threshold}s)"
                )

            if performance_issues:
                dependencies["database"] = {
                    "status": "degraded",
                    "message": f"Connected but performance issues: {'; '.join(performance_issues)}",
                    "connectivity_time": f"{connectivity_time:.3f}s",
                    "query_time": f"{query_time:.3f}s",
                    "active_users_30d": user_count,
                }
                all_healthy = False
            else:
                dependencies["database"] = {
                    "status": "healthy",
                    "message": "Connected and performant",
                    "connectivity_time": f"{connectivity_time:.3f}s",
                    "query_time": f"{query_time:.3f}s",
                    "active_users_30d": user_count,
                }
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
