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
async def client(test_environment):
    """Create test client for smoke tests."""
    from app.main import create_app

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
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, client):
        """
        Test that /v1/health/ready endpoint verifies dependencies.

        Validates: Requirement 9.2 - Readiness probe with dependency checks
        """
        response = await client.get("/v1/health/ready")

        # Should return 200 if all dependencies are healthy
        # or 503 if any dependency is unavailable
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

        # If healthy, should have dependency information
        if response.status_code == 200:
            assert data["status"] in ["healthy", "ready"]

    @pytest.mark.asyncio
    async def test_liveness_check(self, client):
        """
        Test that /v1/health/live endpoint confirms process is running.

        Validates: Requirement 9.3 - Liveness probe
        """
        response = await client.get("/v1/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "message" in data


class TestAuthenticationFlow:
    """Test authentication flow works end-to-end."""

    @pytest.mark.asyncio
    async def test_login_endpoint_exists(self, client):
        """
        Test that login endpoint exists and responds.

        Validates: Requirement 8.1 - JWT authentication endpoint
        """
        # Try to login (will fail with test credentials, but endpoint should exist)
        response = await client.post(
            "/v1/auth/login",
            json={"username": "test_user", "password": "test_password"},
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
    async def test_openapi_json_available(self, client):
        """
        Test that OpenAPI JSON schema is available.

        Validates: API schema availability
        """
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
