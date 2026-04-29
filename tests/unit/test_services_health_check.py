"""
Tests for health check service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health_check import HealthCheckService


class TestHealthCheckService:
    """Test health check service."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def health_service(self, mock_redis):
        """Health check service instance."""
        return HealthCheckService(mock_redis)

    @pytest.mark.asyncio
    async def test_perform_readiness_check_all_ready(self, health_service, mock_redis):
        """Test readiness check when all dependencies are ready."""
        mock_redis.ping.return_value = True

        with patch("app.services.health_check.settings") as mock_settings:
            mock_settings.health_connectivity_threshold = 1.0

            with patch("app.database.connection.engine") as mock_engine:
                mock_conn = MagicMock()
                mock_engine.connect.return_value.__enter__.return_value = mock_conn
                mock_conn.execute.return_value = None

                result = await health_service.perform_readiness_check()

                assert result["status"] == "ready"
                assert result["dependencies"]["redis"]["status"] == "ready"
                assert result["dependencies"]["database"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_perform_readiness_check_redis_slow(self, health_service, mock_redis):
        """Test readiness check when Redis is slow."""
        import time

        async def slow_ping():
            time.sleep(0.2)
            return True

        mock_redis.ping = slow_ping

        with patch("app.services.health_check.settings") as mock_settings:
            mock_settings.health_connectivity_threshold = 0.1

            with patch("app.database.connection.engine") as mock_engine:
                mock_conn = MagicMock()
                mock_engine.connect.return_value.__enter__.return_value = mock_conn
                mock_conn.execute.return_value = None

                result = await health_service.perform_readiness_check()

                assert result["status"] == "not_ready"
                assert result["dependencies"]["redis"]["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_perform_readiness_check_redis_error(self, health_service, mock_redis):
        """Test readiness check when Redis fails."""
        mock_redis.ping.side_effect = Exception("Redis connection failed")

        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.execute.return_value = None

            result = await health_service.perform_readiness_check()

            assert result["status"] == "not_ready"
            assert result["dependencies"]["redis"]["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_perform_readiness_check_database_error(self, health_service, mock_redis):
        """Test readiness check when database fails."""
        mock_redis.ping.return_value = True

        with patch("app.services.health_check.settings") as mock_settings:
            mock_settings.health_connectivity_threshold = 1.0

            with patch("app.database.connection.engine") as mock_engine:
                mock_engine.connect.side_effect = Exception("Database connection failed")

                result = await health_service.perform_readiness_check()

                assert result["status"] == "not_ready"
                assert result["dependencies"]["database"]["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_perform_health_check_includes_celery(self, health_service, mock_redis):
        """Test full health check includes Celery worker status."""
        mock_redis.ping.return_value = True

        with patch("app.services.health_check.settings") as mock_settings:
            mock_settings.health_connectivity_threshold = 1.0

            with patch("app.database.connection.engine") as mock_engine:
                mock_conn = MagicMock()
                mock_engine.connect.return_value.__enter__.return_value = mock_conn
                mock_conn.execute.return_value = None

                with patch("app.services.health_check.celery_app") as mock_celery:
                    mock_celery.control.inspect.return_value.stats.return_value = {
                        "worker1": {"status": "online"}
                    }

                    result = await health_service.perform_health_check()

                    assert "celery" in result["dependencies"]
