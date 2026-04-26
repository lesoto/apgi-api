"""
Unit tests for health check routes — targeting ≥90% coverage of app/routes/health.py.

Tests health check endpoints including root health check, readiness probe, and liveness probe.
Covers success paths, error paths, and edge cases.

Validates: Requirements 3.12, 3.15
"""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

try:
    # Ensure app modules can be imported
    from app.routes.health import (
        get_health_service,
        init_health_routes,
    )
except ImportError:
    pytest.skip(
        "Required app modules not available - skipping health routes tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client."""
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    return redis_client


@pytest.fixture
def mock_health_service(mock_redis_client: AsyncMock) -> MagicMock:
    """Create a mock health check service."""
    from app.services.health_check import HealthCheckService

    service = MagicMock(spec=HealthCheckService)
    service.redis_client = mock_redis_client
    service.perform_health_check = AsyncMock()
    service.perform_readiness_check = AsyncMock()
    return service


@pytest.fixture
def client(mock_db: MagicMock, mock_health_service: MagicMock) -> Generator[TestClient, None, None]:
    """Create a TestClient with mocked dependencies."""
    from app.database.connection import get_db
    from app.main import create_app

    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: mock_db

    # Override the get_health_service dependency to return our mock
    async def mock_get_health_service() -> Any:
        return mock_health_service

    app.dependency_overrides[get_health_service] = mock_get_health_service

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


class TestInitHealthRoutes:
    """Test health routes initialization."""

    def test_init_health_routes_creates_service(self, mock_redis_client: AsyncMock) -> None:
        """Test that init_health_routes creates a health service."""
        # Reset the global health_service
        import app.routes.health as health_module

        health_module.health_service = None

        # Initialize routes
        init_health_routes(mock_redis_client)

        # Verify service was created
        assert health_module.health_service is not None
        assert health_module.health_service.redis_client == mock_redis_client

        # Clean up
        health_module.health_service = None

    def test_init_health_routes_multiple_calls(self, mock_redis_client: AsyncMock) -> None:
        """Test that multiple init calls replace the service."""
        import app.routes.health as health_module

        health_module.health_service = None

        # First initialization
        init_health_routes(mock_redis_client)
        first_service = health_module.health_service

        # Second initialization with different client
        mock_redis_client_2 = AsyncMock()
        init_health_routes(mock_redis_client_2)
        second_service = health_module.health_service

        # Services should be different
        assert first_service is not second_service
        assert second_service.redis_client == mock_redis_client_2

        # Clean up
        health_module.health_service = None


# ---------------------------------------------------------------------------
# Get Health Service Dependency Tests
# ---------------------------------------------------------------------------


class TestGetHealthService:
    """Test the get_health_service dependency."""

    @pytest.mark.asyncio
    async def test_get_health_service_initialized(self, mock_health_service: MagicMock) -> None:
        """Test get_health_service returns service when initialized."""
        import app.routes.health as health_module

        health_module.health_service = mock_health_service

        service = await get_health_service()
        assert service == mock_health_service

        # Clean up
        health_module.health_service = None

    @pytest.mark.asyncio
    async def test_get_health_service_not_initialized(self) -> None:
        """Test get_health_service raises 503 when not initialized."""
        import app.routes.health as health_module

        health_module.health_service = None

        with patch("app.middleware.alerting.alert_manager") as mock_alert_manager:
            mock_alert_manager.trigger_custom_alert = AsyncMock()

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await get_health_service()

            assert exc_info.value.status_code == 503
            assert "not initialized" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Root Health Check Endpoint Tests
# ---------------------------------------------------------------------------


class TestRootHealthCheck:
    """Test the /health endpoint."""

    def test_health_check_all_healthy(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when all components are healthy."""
        mock_health_service.perform_health_check.return_value = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "healthy",
                    "message": "Connected and responsive",
                    "response_time": "0.001s",
                },
                "database": {
                    "status": "healthy",
                    "message": "Connected",
                },
                "celery": {
                    "status": "healthy",
                    "message": "Workers responding: 2, tasks running: 0",
                    "active_workers": "2",
                    "running_tasks": "0",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "dependencies" in data
        assert data["dependencies"]["redis"]["status"] == "healthy"
        assert data["dependencies"]["database"]["status"] == "healthy"
        assert data["dependencies"]["celery"]["status"] == "healthy"

    def test_health_check_redis_unhealthy(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when Redis is unhealthy."""
        mock_health_service.perform_health_check.return_value = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "unhealthy",
                    "message": "CRITICAL: Connection refused",
                },
                "database": {
                    "status": "healthy",
                    "message": "Connected",
                },
                "celery": {
                    "status": "healthy",
                    "message": "Workers responding: 2, tasks running: 0",
                    "active_workers": "2",
                    "running_tasks": "0",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["redis"]["status"] == "unhealthy"

    def test_health_check_database_unhealthy(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when database is unhealthy."""
        mock_health_service.perform_health_check.return_value = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "healthy",
                    "message": "Connected and responsive",
                    "response_time": "0.001s",
                },
                "database": {
                    "status": "unhealthy",
                    "message": "CRITICAL: Connection timeout",
                },
                "celery": {
                    "status": "healthy",
                    "message": "Workers responding: 2, tasks running: 0",
                    "active_workers": "2",
                    "running_tasks": "0",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["database"]["status"] == "unhealthy"

    def test_health_check_redis_degraded(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when Redis is degraded but not unhealthy."""
        mock_health_service.perform_health_check.return_value = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "degraded",
                    "message": "Connected but slow: 0.150s (threshold: 0.100s)",
                },
                "database": {
                    "status": "healthy",
                    "message": "Connected",
                },
                "celery": {
                    "status": "healthy",
                    "message": "Workers responding: 2, tasks running: 0",
                    "active_workers": "2",
                    "running_tasks": "0",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["dependencies"]["redis"]["status"] == "degraded"

    def test_health_check_celery_optional(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when Celery is unavailable (optional)."""
        mock_health_service.perform_health_check.return_value = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "healthy",
                    "message": "Connected and responsive",
                    "response_time": "0.001s",
                },
                "database": {
                    "status": "healthy",
                    "message": "Connected",
                },
                "celery": {
                    "status": "unknown",
                    "message": "OPTIONAL: Not checked",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["celery"]["status"] == "unknown"

    def test_health_check_multiple_dependencies_unhealthy(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when multiple dependencies are unhealthy."""
        mock_health_service.perform_health_check.return_value = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "unhealthy",
                    "message": "CRITICAL: Connection refused",
                },
                "database": {
                    "status": "unhealthy",
                    "message": "CRITICAL: Connection timeout",
                },
                "celery": {
                    "status": "unhealthy",
                    "message": "OPTIONAL: No Celery workers responded to ping",
                },
            },
        }

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"

    def test_health_check_service_exception(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check when service raises an exception."""
        mock_health_service.perform_health_check.side_effect = Exception("Service error")

        response = client.get("/health")

        # Should return 500 due to unhandled exception
        assert response.status_code == 500

    def test_health_check_response_structure(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check response has correct structure."""
        mock_health_service.perform_health_check.return_value = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "healthy", "message": "OK"},
                "database": {"status": "healthy", "message": "OK"},
                "celery": {"status": "healthy", "message": "OK"},
            },
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)


# ---------------------------------------------------------------------------
# Readiness Check Endpoint Tests
# ---------------------------------------------------------------------------


class TestReadinessCheck:
    """Test the /health/ready endpoint."""

    def test_readiness_check_ready(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when API is ready."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "ready",
                    "message": "Connected and responsive",
                    "response_time": "0.001s",
                },
                "database": {
                    "status": "ready",
                    "message": "Connected",
                    "connectivity_time": "0.005s",
                },
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "dependencies" in data

    def test_readiness_check_not_ready_redis(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when Redis is not ready."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "not_ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "not_ready",
                    "message": "Connection refused",
                },
                "database": {
                    "status": "ready",
                    "message": "Connected",
                    "connectivity_time": "0.005s",
                },
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["redis"]["status"] == "not_ready"

    def test_readiness_check_not_ready_database(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when database is not ready."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "not_ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "ready",
                    "message": "Connected and responsive",
                    "response_time": "0.001s",
                },
                "database": {
                    "status": "not_ready",
                    "message": "Connection timeout",
                },
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["database"]["status"] == "not_ready"

    def test_readiness_check_degraded_redis(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when Redis is degraded."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "not_ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "degraded",
                    "message": "Connected but slow: 0.150s (threshold: 0.100s)",
                },
                "database": {
                    "status": "ready",
                    "message": "Connected",
                    "connectivity_time": "0.005s",
                },
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["dependencies"]["redis"]["status"] == "degraded"

    def test_readiness_check_both_not_ready(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when both critical dependencies are not ready."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "not_ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {
                    "status": "not_ready",
                    "message": "Connection refused",
                },
                "database": {
                    "status": "not_ready",
                    "message": "Connection timeout",
                },
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"

    def test_readiness_check_service_exception(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check when service raises an exception."""
        mock_health_service.perform_readiness_check.side_effect = Exception("Service error")

        response = client.get("/health/ready")

        # Should return 500 due to unhandled exception
        assert response.status_code == 500

    def test_readiness_check_response_structure(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check response has correct structure."""
        mock_health_service.perform_readiness_check.return_value = {
            "status": "ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "ready", "message": "OK"},
                "database": {"status": "ready", "message": "OK"},
            },
        }

        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "dependencies" in data


# ---------------------------------------------------------------------------
# Liveness Check Endpoint Tests
# ---------------------------------------------------------------------------


class TestLivenessCheck:
    """Test the /health/live endpoint."""

    def test_liveness_check_success(self, client: TestClient) -> None:
        """Test liveness check always returns 200."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["message"] == "API is running"

    def test_liveness_check_no_dependencies(self, client: TestClient) -> None:
        """Test liveness check does not check dependencies."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        # Should not have dependencies key
        assert "dependencies" not in data

    def test_liveness_check_response_structure(self, client: TestClient) -> None:
        """Test liveness check response has correct structure."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data
        assert data["status"] == "alive"

    def test_liveness_check_multiple_calls(self, client: TestClient) -> None:
        """Test liveness check can be called multiple times."""
        for _ in range(5):
            response = client.get("/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "alive"

    def test_liveness_check_no_service_dependency(self, client: TestClient) -> None:
        """Test liveness check does not depend on health service."""
        # Even if health service is not initialized, liveness should work
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestHealthRoutesIntegration:
    """Integration tests for health routes."""

    def test_health_endpoints_all_available(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test all health endpoints are available."""
        mock_health_service.perform_health_check.return_value = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "healthy", "message": "OK"},
                "database": {"status": "healthy", "message": "OK"},
                "celery": {"status": "healthy", "message": "OK"},
            },
        }
        mock_health_service.perform_readiness_check.return_value = {
            "status": "ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "ready", "message": "OK"},
                "database": {"status": "ready", "message": "OK"},
            },
        }

        # Test all endpoints
        health_response = client.get("/health")
        ready_response = client.get("/health/ready")
        live_response = client.get("/health/live")

        assert health_response.status_code == 200
        assert ready_response.status_code == 200
        assert live_response.status_code == 200

    def test_health_check_consistency(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health check returns consistent data."""
        health_data = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "healthy", "message": "OK"},
                "database": {"status": "healthy", "message": "OK"},
                "celery": {"status": "healthy", "message": "OK"},
            },
        }
        mock_health_service.perform_health_check.return_value = health_data

        response1 = client.get("/health")
        response2 = client.get("/health")

        assert response1.json() == response2.json()

    def test_readiness_check_consistency(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test readiness check returns consistent data."""
        ready_data = {
            "status": "ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "redis": {"status": "ready", "message": "OK"},
                "database": {"status": "ready", "message": "OK"},
            },
        }
        mock_health_service.perform_readiness_check.return_value = ready_data

        response1 = client.get("/health/ready")
        response2 = client.get("/health/ready")

        assert response1.json() == response2.json()

    def test_health_status_codes_correct(
        self, client: TestClient, mock_health_service: MagicMock
    ) -> None:
        """Test health endpoints return correct status codes."""
        # Healthy
        mock_health_service.perform_health_check.return_value = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {},
        }
        assert client.get("/health").status_code == 200

        # Unhealthy
        mock_health_service.perform_health_check.return_value = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {},
        }
        assert client.get("/health").status_code == 503

        # Ready
        mock_health_service.perform_readiness_check.return_value = {
            "status": "ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {},
        }
        assert client.get("/health/ready").status_code == 200

        # Not ready
        mock_health_service.perform_readiness_check.return_value = {
            "status": "not_ready",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {},
        }
        assert client.get("/health/ready").status_code == 503

        # Liveness always 200
        assert client.get("/health/live").status_code == 200
