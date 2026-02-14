"""
Integration Tests for User Routes

Tests user management endpoints through HTTP requests with authentication.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def authenticated_client(test_environment, mock_database_connection):
    """Create authenticated test client for user integration tests."""
    from app.main import create_app
    from app.services.auth_manager import AuthManager
    from unittest.mock import AsyncMock, patch

    # Mock Redis for the lifespan
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.close = AsyncMock()

    # Mock User for authentication
    mock_user = MagicMock()
    mock_user.user_id = str(uuid.uuid4())
    mock_user.username = "test_admin"
    mock_user.roles = ["admin"]

    # Create a real JWT token for the mock user
    auth_manager = AuthManager(db=None)  # We don't need DB for token creation
    access_token = auth_manager.create_access_token(
        user_id=mock_user.user_id, username=mock_user.username, roles=mock_user.roles
    )

    with (
        patch("redis.asyncio.from_url", return_value=mock_redis_client),
        patch("app.services.auth_manager.AuthManager.authenticate_user", return_value=mock_user),
        patch("app.services.authorization.require_permission"),
    ):
        app = create_app(test_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Add the JWT token to default headers
            ac.headers.update({"Authorization": f"Bearer {access_token}"})
            yield ac


@pytest.fixture
def mock_user_management_service():
    """Create mock UserManagementService for integration tests."""
    service = MagicMock()
    mock_user = MagicMock()
    mock_user.user_id = str(uuid.uuid4())
    mock_user.username = "test_user"
    mock_user.email = "test@example.com"
    mock_user.roles = ["user"]
    mock_user.created_at = "2023-01-01T00:00:00Z"

    service.create_user = MagicMock(return_value=(mock_user, "generated_password"))
    service.get_user_by_id = AsyncMock(return_value=mock_user)
    service.update_user = AsyncMock(return_value=mock_user)
    service.delete_user = AsyncMock(return_value=True)
    service.reset_user_password = AsyncMock(return_value="new_password")
    service.get_user_stats = AsyncMock(return_value={"total_users": 10, "active_users": 8})
    return service


class TestUserRoutesIntegration:
    """Integration tests for user management endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, authenticated_client, mock_user_management_service):
        """Test user registration."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            request_data = {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "password123",
                "roles": ["user"],
            }

            response = await authenticated_client.post("/v1/users/register", json=request_data)

            assert response.status_code == 201
            data = response.json()
            assert "user_id" in data
            assert data["username"] == "newuser"
            assert data["email"] == "newuser@example.com"
            assert "password" in data
            assert data["message"] == "User created successfully"

    @pytest.mark.asyncio
    async def test_get_user(self, authenticated_client, mock_user_management_service):
        """Test getting user by ID with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            user_id = str(uuid.uuid4())

            response = await authenticated_client.get(f"/v1/users/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert (
                data["user_id"] == mock_user_management_service.get_user_by_id.return_value.user_id
            )
            assert data["username"] == "test_user"
            assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self, authenticated_client, mock_user_management_service):
        """Test updating user with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            user_id = str(uuid.uuid4())
            update_data = {"email": "updated@example.com", "roles": ["user", "admin"]}

            response = await authenticated_client.put(f"/v1/users/{user_id}", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == mock_user_management_service.update_user.return_value.user_id

    @pytest.mark.asyncio
    async def test_delete_user(self, authenticated_client, mock_user_management_service):
        """Test deleting user with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            user_id = str(uuid.uuid4())

            response = await authenticated_client.delete(f"/v1/users/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "User deleted successfully"

    @pytest.mark.asyncio
    async def test_reset_password(self, authenticated_client, mock_user_management_service):
        """Test password reset with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            user_id = str(uuid.uuid4())
            reset_data = {"new_password": "newpassword123"}

            response = await authenticated_client.post(
                f"/v1/users/{user_id}/reset-password", json=reset_data
            )

            assert response.status_code == 200
            data = response.json()
            assert "new_password" in data

    @pytest.mark.asyncio
    async def test_get_user_stats(self, authenticated_client, mock_user_management_service):
        """Test getting user statistics with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            response = await authenticated_client.get("/v1/users/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_users" in data
            assert "active_users" in data
