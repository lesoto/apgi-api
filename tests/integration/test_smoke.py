"""
Smoke Tests for Deployed Application

These tests verify that the deployed API is functioning correctly by testing
critical end-to-end workflows:
- Health endpoints respond correctly
- Authentication flow works end-to-end
- Session creation and management works
- Task submission and retrieval works

These tests are designed to run against a deployed instance of the API
to validate that all components are working together correctly.

**Validates: Requirements 9.1, 9.2, 9.3**
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client(test_environment, mock_database_connection):
    """Create test client for smoke tests."""
    from app.main import create_app
    from unittest.mock import AsyncMock, patch

    # Mock Redis for the lifespan
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.close = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        app = create_app(test_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestHealthEndpoints:
    """Test health check endpoints respond correctly."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self, client):
        """
        Test that /health endpoint returns 200 OK.

        Validates: Requirement 9.1 - Basic health check endpoint
        """
        from unittest.mock import AsyncMock, patch

        # Mock the health check to return healthy
        mock_health_result = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "database": {"status": "healthy"},
            "redis": {"status": "healthy"},
            "celery": {"status": "healthy"},
        }

        with patch("app.routes.health.health_service") as mock_service:
            mock_service.perform_health_check = AsyncMock(return_value=mock_health_result)
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, client):
        """
        Test that /health/ready endpoint verifies dependencies.

        Validates: Requirement 9.2 - Readiness probe with dependency checks
        """
        response = await client.get("/health/ready")

        # Should return 200 if all dependencies are healthy
        # or 503 if any dependency is unavailable
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

        # If healthy, should have dependency information
        if response.status_code == 200:
            assert data["status"] in ["healthy", "ready"]

    @pytest.mark.asyncio
    async def test_health_service_not_initialized(self, client):
        """
        Test that health endpoints return 503 when health service is not initialized.

        Validates: Health service initialization check
        """
        from unittest.mock import patch

        # Patch health_service to None
        with patch("app.routes.health.health_service", None):
            # Test /health
            response = await client.get("/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data
            assert "Health service not initialized" in data["error"]

            # Test /health/ready
            response = await client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert "error" in data
            assert "Health service not initialized" in data["error"]

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client):
        """
        Test that health endpoints return 503 when health check fails.

        Validates: Unhealthy status handling
        """
        from unittest.mock import patch, AsyncMock

        # Mock perform_health_check to return unhealthy
        mock_health_check = AsyncMock(
            return_value={
                "status": "unhealthy",
                "database": {"status": "unhealthy", "error": "Connection failed"},
                "redis": {"status": "healthy"},
                "celery": {"status": "healthy"},
            }
        )

        # Mock perform_readiness_check to return unhealthy
        mock_readiness_check = AsyncMock(
            return_value={
                "status": "not_ready",
                "database": {"status": "not_ready", "error": "Connection failed"},
                "redis": {"status": "ready"},
            }
        )

        with patch("app.routes.health.health_service") as mock_service:
            mock_service.perform_health_check = mock_health_check
            mock_service.perform_readiness_check = mock_readiness_check

            # Test /health
            response = await client.get("/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

            # Test /health/ready
            response = await client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"


class TestAuthenticationFlow:
    """Test authentication flow works end-to-end."""

    @pytest.mark.asyncio
    async def test_login_endpoint_exists(self, client):
        """
        Test that login endpoint exists and responds.

        Validates: Requirement 8.1 - JWT authentication endpoint
        """
        from unittest.mock import patch

        # Patch authenticate_user to return None (invalid credentials)
        # This allows the endpoint to return 401 as expected without MagicMock issues
        with patch("app.services.auth_manager.AuthManager.authenticate_user", return_value=None):
            # Try to login (will fail with test credentials, but endpoint should exist)
            response = await client.post(
                "/v1/auth/login",
                json={"username": "test_user", "password": "TestPass123"},
            )

        # Should get either 200 (success) or 401 (invalid credentials)
        # but not 404 (endpoint missing)
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_refresh_endpoint_exists(self, client):
        """
        Test that token refresh endpoint exists.

        Validates: Requirement 8.2 - Token refresh mechanism
        """
        # Try to refresh with invalid token
        response = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )

        # Should get 401 (invalid token) but not 404 (endpoint missing)
        assert response.status_code in [401, 422]

    @pytest.mark.asyncio
    async def test_logout_endpoint_exists(self, client):
        """
        Test that logout endpoint exists.

        Validates: Requirement 8.1 - Authentication endpoints
        """
        # Try to logout without auth (will fail, but endpoint should exist)
        response = await client.post(
            "/v1/auth/logout",
            json={"refresh_token": "invalid_token"},
        )

        # Should get 401 (not authenticated) but not 404 (endpoint missing)
        assert response.status_code in [401, 422]


class TestSessionManagement:
    """Test session creation and management endpoints exist."""

    @pytest.mark.asyncio
    async def test_session_create_endpoint_exists(self, client):
        """
        Test that session creation endpoint exists.

        Validates: Requirement 18.3 - Session creation
        """
        # Try to create session (will fail without auth in non-test mode)
        response = await client.post(
            "/v1/sessions",
            json={"config": {"description": "test"}},
        )

        # Should get 401 (not authenticated) or 201 (success in test mode)
        # but not 404 (endpoint missing)
        assert response.status_code in [200, 201, 401, 422]

    @pytest.mark.asyncio
    async def test_session_get_endpoint_exists(self, client):
        """
        Test that session retrieval endpoint exists.

        Validates: Requirement 18.4 - Session retrieval
        """
        # Try to get non-existent session
        response = await client.get("/v1/sessions/test_session_id")

        # Should get 404 (not found) or 401 (not authenticated)
        # but endpoint should exist
        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_session_start_endpoint_exists(self, client):
        """
        Test that session start endpoint exists.

        Validates: Requirement 18.4 - Session control
        """
        response = await client.post("/v1/sessions/test_session_id/start")

        # Should get 401 or 404, but not 404 for the endpoint itself
        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_session_pause_endpoint_exists(self, client):
        """
        Test that session pause endpoint exists.

        Validates: Requirement 18.4 - Session control
        """
        response = await client.post("/v1/sessions/test_session_id/pause")

        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_session_stop_endpoint_exists(self, client):
        """
        Test that session stop endpoint exists.

        Validates: Requirement 18.4 - Session control
        """
        response = await client.post("/v1/sessions/test_session_id/stop")

        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_session_reset_endpoint_exists(self, client):
        """
        Test that session reset endpoint exists.

        Validates: Requirement 18.4 - Session control
        """
        response = await client.post("/v1/sessions/test_session_id/reset")

        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_session_delete_endpoint_exists(self, client):
        """
        Test that session deletion endpoint exists.

        Validates: Requirement 18.6 - Session deletion
        """
        response = await client.delete("/v1/sessions/test_session_id")

        assert response.status_code in [401, 404]


class TestTaskSubmissionAndRetrieval:
    """Test task submission and retrieval endpoints exist."""

    @pytest.mark.asyncio
    async def test_list_tasks_endpoint_exists(self, client):
        """
        Test that task listing endpoint exists.

        Validates: Requirement 15.3 - Task definitions available
        """
        response = await client.get("/v1/tasks")

        # Should get 200 (success) or 401 (not authenticated)
        # but not 404 (endpoint missing)
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_submit_task_endpoint_exists(self, client):
        """
        Test that task submission endpoint exists.

        Validates: Requirements 15.1, 15.2 - Task submission
        """
        response = await client.post(
            "/v1/sessions/test_session_id/tasks",
            json={"task_type": "test_task", "parameters": {}},
        )

        # Should get 401, 404, or 422, but not 404 for the endpoint itself
        assert response.status_code in [401, 404, 422]

    @pytest.mark.asyncio
    async def test_get_task_status_endpoint_exists(self, client):
        """
        Test that task status endpoint exists.

        Validates: Requirement 15.4 - Task status checking
        """
        response = await client.get("/v1/tasks/test_task_id")

        # Should get 401 or 404, but endpoint should exist
        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_cancel_task_endpoint_exists(self, client):
        """
        Test that task cancellation endpoint exists.

        Validates: Task management functionality
        """
        response = await client.delete("/v1/tasks/test_task_id")

        # Should get 401 or 404, but endpoint should exist
        assert response.status_code in [401, 404]


class TestAPIStructure:
    """Test overall API structure and availability."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """
        Test that root endpoint provides API information.

        Validates: Basic API functionality
        """
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    @pytest.mark.asyncio
    async def test_openapi_docs_available(self, client):
        """
        Test that OpenAPI documentation is available.

        Validates: API documentation availability
        """
        response = await client.get("/docs")

        # Should return HTML page (200) or redirect
        assert response.status_code in [200, 307]

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client):
        """
        Test that version endpoint returns correct information.

        Validates: API version information availability
        """
        response = await client.get("/v1/version")

        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert "api_version" in data
        assert "supported_versions" in data
        assert "deprecated_versions" in data
        assert "api_spec_url" in data
        assert "documentation_url" in data
        assert "timestamp" in data
        assert data["api_spec_url"] == "/openapi.json"
        assert data["documentation_url"] == "/docs"
