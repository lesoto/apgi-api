"""
Unit tests for health check service.

Tests health check functionality with mocked dependencies.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.health_check import HealthCheckService


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def health_check_service(mock_redis):
    """Create HealthCheckService instance."""
    return HealthCheckService(mock_redis)


class TestHealthCheckService:
    """Test HealthCheckService functionality."""

    @pytest.mark.asyncio
    async def test_perform_health_check_all_healthy(self, health_check_service, mock_redis):
        """Test health check when all dependencies are healthy."""
        # Mock database connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Mock Celery to return healthy status
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {}
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_control = MagicMock()
        mock_control.inspect.return_value = mock_inspect
        mock_control.ping.return_value = [{"worker1": "pong"}]

        with patch("app.database.connection.engine", mock_engine), patch(
            "app.services.health_check.celery_app.control", mock_control
        ):
            result = await health_check_service.perform_health_check()

        # Verify structure
        assert "status" in result
        assert "timestamp" in result
        assert "dependencies" in result

        # Verify status
        assert result["status"] == "healthy"

        # Verify dependencies
        deps = result["dependencies"]
        assert "redis" in deps
        assert "database" in deps
        assert "celery" in deps

        # Verify Redis
        assert deps["redis"]["status"] == "healthy"
        assert "Connected and responsive" in deps["redis"]["message"]

        # Verify Database
        assert deps["database"]["status"] == "healthy"
        assert deps["database"]["message"] == "Connected"

        # Verify Celery
        assert deps["celery"]["status"] == "healthy"
        assert "Workers responding" in deps["celery"]["message"]

        # Verify timestamp format
        datetime.fromisoformat(result["timestamp"].rstrip("Z"))

    @pytest.mark.asyncio
    async def test_perform_health_check_redis_unhealthy(self, health_check_service, mock_redis):
        """Test health check when Redis is unhealthy."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        # Mock database connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with patch("app.database.connection.engine", mock_engine):
            result = await health_check_service.perform_health_check()

        # Verify status
        assert result["status"] == "unhealthy"

        # Verify Redis
        deps = result["dependencies"]
        assert deps["redis"]["status"] == "unhealthy"
        assert deps["redis"]["message"] == "Connection failed"

        # Verify Database still healthy
        assert deps["database"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_perform_health_check_database_unhealthy(self, health_check_service, mock_redis):
        """Test health check when database is unhealthy."""
        # Mock database connection failure
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("DB connection failed")

        with patch("app.database.connection.engine", mock_engine):
            result = await health_check_service.perform_health_check()

        # Verify status
        assert result["status"] == "unhealthy"

        # Verify Database
        deps = result["dependencies"]
        assert deps["database"]["status"] == "unhealthy"
        assert deps["database"]["message"] == "DB connection failed"

        # Verify Redis still healthy
        assert deps["redis"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_perform_health_check_both_unhealthy(self, health_check_service, mock_redis):
        """Test health check when both Redis and database are unhealthy."""
        mock_redis.ping.side_effect = Exception("Redis failed")

        # Mock database connection failure
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("DB failed")

        with patch("app.database.connection.engine", mock_engine):
            result = await health_check_service.perform_health_check()

        # Verify status
        assert result["status"] == "unhealthy"

        # Verify both unhealthy
        deps = result["dependencies"]
        assert deps["redis"]["status"] == "unhealthy"
        assert deps["database"]["status"] == "unhealthy"
