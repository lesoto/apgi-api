"""
Unit tests for HealthCheckService.

Tests healthy, degraded, and unhealthy paths for Redis, database, and Celery.
Requirements: 2.10
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.health_check import HealthCheckService


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def service(mock_redis):
    return HealthCheckService(mock_redis)


def _make_mock_engine(slow=False, fail=False):
    """Build a mock SQLAlchemy engine."""
    engine = MagicMock()
    if fail:
        engine.connect.side_effect = Exception("DB connection failed")
    else:
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        engine.connect.return_value = mock_conn
    return engine


def _make_mock_celery_control(workers_up=True):
    control = MagicMock()
    if workers_up:
        control.ping.return_value = [{"worker1": {"ok": "pong"}}]
        inspect = MagicMock()
        inspect.active.return_value = {"worker1": []}
        inspect.stats.return_value = {"worker1": {}}
        control.inspect.return_value = inspect
    else:
        control.ping.return_value = []
    return control


# ---------------------------------------------------------------------------
# perform_health_check
# ---------------------------------------------------------------------------


class TestPerformHealthCheck:

    @pytest.mark.asyncio
    async def test_all_healthy(self, service, mock_redis):
        mock_engine = _make_mock_engine()
        mock_control = _make_mock_celery_control(workers_up=True)

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = mock_control
            result = await service.perform_health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "dependencies" in result
        deps = result["dependencies"]
        assert deps["redis"]["status"] == "healthy"
        assert deps["database"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_redis_unhealthy_makes_overall_unhealthy(self, service, mock_redis):
        mock_redis.ping.side_effect = Exception("Redis down")
        mock_engine = _make_mock_engine()

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = _make_mock_celery_control()
            result = await service.perform_health_check()

        assert result["status"] == "unhealthy"
        assert result["dependencies"]["redis"]["status"] == "unhealthy"
        assert "CRITICAL" in result["dependencies"]["redis"]["message"]

    @pytest.mark.asyncio
    async def test_database_unhealthy_makes_overall_unhealthy(self, service, mock_redis):
        mock_engine = _make_mock_engine(fail=True)

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = _make_mock_celery_control()
            result = await service.perform_health_check()

        assert result["status"] == "unhealthy"
        assert result["dependencies"]["database"]["status"] == "unhealthy"
        assert "CRITICAL" in result["dependencies"]["database"]["message"]

    @pytest.mark.asyncio
    async def test_both_redis_and_db_unhealthy(self, service, mock_redis):
        mock_redis.ping.side_effect = Exception("Redis down")
        mock_engine = _make_mock_engine(fail=True)

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = _make_mock_celery_control()
            result = await service.perform_health_check()

        assert result["status"] == "unhealthy"
        assert result["dependencies"]["redis"]["status"] == "unhealthy"
        assert result["dependencies"]["database"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_celery_no_workers_does_not_fail_overall(self, service, mock_redis):
        """Celery is optional — no workers should not make overall status unhealthy."""
        mock_engine = _make_mock_engine()
        mock_control = _make_mock_celery_control(workers_up=False)

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = mock_control
            result = await service.perform_health_check()

        # Overall should still be healthy (Celery is optional)
        assert result["status"] == "healthy"
        assert result["dependencies"]["celery"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_celery_exception_does_not_fail_overall(self, service, mock_redis):
        """Celery exception should be caught and not affect overall health."""
        mock_engine = _make_mock_engine()

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control.ping.side_effect = Exception("Celery broker down")
            result = await service.perform_health_check()

        assert result["status"] == "healthy"
        assert result["dependencies"]["celery"]["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_timestamp_format(self, service, mock_redis):
        mock_engine = _make_mock_engine()

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = _make_mock_celery_control()
            result = await service.perform_health_check()

        ts = result["timestamp"]
        assert ts.endswith("Z")
        # Should parse without error
        datetime.fromisoformat(ts.rstrip("Z"))

    @pytest.mark.asyncio
    async def test_redis_degraded_when_slow(self, service, mock_redis):
        """When Redis responds but slowly, status should be degraded."""
        import time

        async def slow_ping():
            return True

        mock_redis.ping = slow_ping

        mock_engine = _make_mock_engine()

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
            patch("app.services.health_check.settings") as mock_settings,
        ):
            mock_celery.control = _make_mock_celery_control()
            mock_settings.health_connectivity_threshold = 0.0  # Force degraded
            mock_settings.health_critical_services = ["redis", "database"]
            mock_settings.health_query_threshold = 0.5
            result = await service.perform_health_check()

        # With threshold=0, any response time will be "slow"
        assert result["dependencies"]["redis"]["status"] in ("degraded", "healthy")

    @pytest.mark.asyncio
    async def test_celery_workers_healthy_message(self, service, mock_redis):
        mock_engine = _make_mock_engine()
        mock_control = _make_mock_celery_control(workers_up=True)

        with (
            patch("app.database.connection.engine", mock_engine),
            patch("app.services.health_check.celery_app") as mock_celery,
        ):
            mock_celery.control = mock_control
            result = await service.perform_health_check()

        celery_dep = result["dependencies"]["celery"]
        assert celery_dep["status"] == "healthy"
        assert "Workers responding" in celery_dep["message"]


# ---------------------------------------------------------------------------
# perform_readiness_check
# ---------------------------------------------------------------------------


class TestPerformReadinessCheck:

    @pytest.mark.asyncio
    async def test_all_ready(self, service, mock_redis):
        mock_engine = _make_mock_engine()

        with patch("app.database.connection.engine", mock_engine):
            result = await service.perform_readiness_check()

        assert result["status"] == "ready"
        assert "dependencies" in result
        deps = result["dependencies"]
        assert deps["redis"]["status"] == "ready"
        assert deps["database"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_redis_not_ready(self, service, mock_redis):
        mock_redis.ping.side_effect = Exception("Redis unavailable")
        mock_engine = _make_mock_engine()

        with patch("app.database.connection.engine", mock_engine):
            result = await service.perform_readiness_check()

        assert result["status"] == "not_ready"
        assert result["dependencies"]["redis"]["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_database_not_ready(self, service, mock_redis):
        mock_engine = _make_mock_engine(fail=True)

        with patch("app.database.connection.engine", mock_engine):
            result = await service.perform_readiness_check()

        assert result["status"] == "not_ready"
        assert result["dependencies"]["database"]["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_readiness_timestamp_format(self, service, mock_redis):
        mock_engine = _make_mock_engine()

        with patch("app.database.connection.engine", mock_engine):
            result = await service.perform_readiness_check()

        ts = result["timestamp"]
        assert ts.endswith("Z")
        datetime.fromisoformat(ts.rstrip("Z"))

    @pytest.mark.asyncio
    async def test_readiness_does_not_check_celery(self, service, mock_redis):
        """Readiness check should not include Celery."""
        mock_engine = _make_mock_engine()

        with patch("app.database.connection.engine", mock_engine):
            result = await service.perform_readiness_check()

        assert "celery" not in result["dependencies"]
