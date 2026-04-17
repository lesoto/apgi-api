"""Test health check service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import redis.asyncio as redis

from app.services.health_check import HealthCheckService


class TestHealthCheckService:
    """Test health check service functionality."""

    @pytest.fixture
    def mock_redis_client(self) -> AsyncMock:
        """Create a mock Redis client."""
        client = AsyncMock(spec=redis.Redis)
        client.ping = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def health_service(self, mock_redis_client: AsyncMock) -> HealthCheckService:
        """Create health check service with mock dependencies."""
        return HealthCheckService(mock_redis_client)

    async def test_init(self, mock_redis_client: AsyncMock) -> None:
        """Test service initialization."""
        service = HealthCheckService(mock_redis_client)
        assert service.redis_client is mock_redis_client

    async def test_perform_readiness_check_success(
        self, health_service: HealthCheckService
    ) -> None:
        """Test successful readiness check."""
        # Mock Redis ping to return quickly
        health_service.redis_client.ping.return_value = True  # type: ignore[attr-defined]

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_conn.execute.return_value = None
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.return_value.__exit__.return_value = None

            result = await health_service.perform_readiness_check()

        assert "status" in result
        assert "dependencies" in result
        assert "timestamp" in result
        assert result["status"] == "ready"
        assert "redis" in result["dependencies"]
        assert "database" in result["dependencies"]
        assert result["dependencies"]["redis"]["status"] == "ready"
        assert result["dependencies"]["database"]["status"] == "ready"

    async def test_perform_readiness_check_redis_slow(
        self, health_service: HealthCheckService
    ) -> None:
        """Test readiness check with slow Redis response."""

        # Mock Redis ping to be slow
        async def slow_ping() -> bool:
            await asyncio.sleep(0.2)  # 200ms delay
            return True

        health_service.redis_client.ping = slow_ping  # type: ignore[assignment,method-assign]

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_conn.execute.return_value = None
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.return_value.__exit__.return_value = None

            with patch("app.services.health_check.settings.health_connectivity_threshold", 0.1):
                result = await health_service.perform_readiness_check()

        assert result["status"] == "not_ready"
        assert result["dependencies"]["redis"]["status"] == "degraded"

    async def test_perform_readiness_check_redis_error(
        self, health_service: HealthCheckService
    ) -> None:
        """Test readiness check with Redis error."""
        health_service.redis_client.ping.side_effect = Exception("Redis connection failed")  # type: ignore[attr-defined]

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_conn.execute.return_value = None
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.return_value.__exit__.return_value = None

            result = await health_service.perform_readiness_check()

        assert result["status"] == "not_ready"
        assert result["dependencies"]["redis"]["status"] == "not_ready"

    async def test_perform_health_check_success(self, health_service: HealthCheckService) -> None:
        """Test comprehensive health check with all dependencies healthy."""
        # Mock Redis
        health_service.redis_client.ping.return_value = True  # type: ignore[attr-defined]

        with patch("app.database.connection.engine") as mock_engine:
            # Mock both database connections
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]  # Return dummy count
            mock_conn.execute.return_value = mock_result

            # Mock the context manager properly
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.return_value.__exit__.return_value = None

            with patch("app.services.health_check.celery_app") as mock_celery:
                # Mock Celery inspection
                mock_inspect = MagicMock()
                mock_inspect.stats.return_value = {"worker1": {"status": "ready"}}
                mock_inspect.active.return_value = {}
                mock_celery.control.inspect.return_value = mock_inspect
                mock_celery.control.ping.return_value = {"worker1": "ok"}

                result = await health_service.perform_health_check()

        assert result["status"] == "healthy"
        assert "redis" in result["dependencies"]
        assert "database" in result["dependencies"]
        assert "celery" in result["dependencies"]
        assert result["dependencies"]["redis"]["status"] == "healthy"
        assert result["dependencies"]["database"]["status"] == "healthy"
        assert result["dependencies"]["celery"]["status"] == "healthy"

    async def test_perform_health_check_redis_error(
        self, health_service: HealthCheckService
    ) -> None:
        """Test comprehensive health check with Redis error."""
        health_service.redis_client.ping.side_effect = Exception("Redis connection failed")  # type: ignore[attr-defined]

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_conn.execute.return_value = None
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_engine.connect.return_value.__exit__.return_value = None

            result = await health_service.perform_health_check()

        assert result["status"] == "unhealthy"
        assert result["dependencies"]["redis"]["status"] == "unhealthy"

    async def test_perform_health_check_database_error(
        self, health_service: HealthCheckService
    ) -> None:
        """Test comprehensive health check with database error."""
        health_service.redis_client.ping.return_value = True  # type: ignore[attr-defined]

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()  # Use MagicMock for sync connections
            mock_engine.connect.side_effect = Exception("Database connection failed")

            result = await health_service.perform_health_check()

        assert result["status"] == "unhealthy"
