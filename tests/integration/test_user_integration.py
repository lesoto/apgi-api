"""
Integration Tests for User Routes

Tests user management endpoints through HTTP requests with authentication.
"""

import pytest
import uuid
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from typing import AsyncGenerator


@pytest.fixture
async def authenticated_client(
    test_environment: None, mock_database_connection: None, mock_user_management_service: MagicMock
) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated test client for user integration tests."""
    from app.main import create_app
    from app.services.auth_manager import AuthManager
    from unittest.mock import AsyncMock, patch

    # Mock Redis for the lifespan
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.aclose = AsyncMock()

    # Mock User for authentication
    mock_user = MagicMock()
    mock_user.user_id = str(uuid.uuid4())
    mock_user.username = "test_admin"
    mock_user.roles = ["admin"]

    # Create a real JWT token for the mock user
    auth_manager = AuthManager(db=None)  # type: ignore[arg-type]  # We don't need DB for token creation
    access_token = auth_manager.create_access_token(
        user_id=mock_user.user_id, username=mock_user.username, roles=mock_user.roles
    )

    with (
        patch("redis.asyncio.from_url", return_value=mock_redis_client),
        patch("app.services.auth_manager.AuthManager.authenticate_user", return_value=mock_user),
        patch("app.services.authorization.require_permission", return_value=None),
        patch("app.services.authorization.has_permission", return_value=True),
        patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ),
    ):
        app = create_app(test_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Add the JWT token to default headers
            ac.headers.update({"Authorization": f"Bearer {access_token}"})
            yield ac


# Mock functions
def create_user_mock(
    username: str, email: str, password: str, roles: list[str] | None = None
) -> "MockUser":
    return MockUser(
        username=username,
        email=email,
        roles=roles or ["user"],
        user_id=str(uuid.uuid4()),
        is_active=True,
        created_at=datetime(2023, 1, 1, 0, 0, 0),
        updated_at=datetime(2023, 1, 1, 0, 0, 0),
        last_login=None,
    )


def get_user_by_id_mock(user_id: str) -> MagicMock:
    user = MagicMock()
    user.user_id = user_id
    user.username = "test_user"
    user.email = "test@example.com"
    user.roles = ["user"]
    user.is_active = True
    user.created_at = datetime(2023, 1, 1, 0, 0, 0)
    user.updated_at = datetime(2023, 1, 1, 0, 0, 0)
    user.last_login = None
    return user


class MockUser:
    """Mock user object for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.user_id = kwargs.get("user_id", str(uuid.uuid4()))
        self.username = kwargs.get("username", "test_user")
        self.email = kwargs.get("email", "test@example.com")
        self.roles = kwargs.get("roles", ["user"])
        self.is_active = kwargs.get("is_active", True)
        self.last_login = kwargs.get("last_login", None)
        from datetime import datetime

        self.created_at = datetime(2023, 1, 1, 0, 0, 0)
        self.updated_at = datetime(2023, 1, 1, 0, 0, 0)


def update_user_mock(**kwargs: Any) -> MockUser:
    return MockUser(**kwargs)


@pytest.fixture
def mock_user_management_service() -> Generator[MagicMock, None, None]:
    """Create mock UserManagementService for integration tests."""
    service = MagicMock()
    service.create_user = MagicMock(side_effect=create_user_mock)
    service.get_user = MagicMock(side_effect=get_user_by_id_mock)
    service.update_user = MagicMock(
        return_value=MockUser(
            user_id="test_user_id",
            username="test_user",
            email="updated@example.com",
            roles=["user", "admin"],
            is_active=True,
            created_at=datetime(2023, 1, 1, 0, 0, 0),
            updated_at=datetime(2023, 1, 1, 0, 0, 0),
            last_login=None,
        )
    )
    service.delete_user = MagicMock(return_value=True)
    service.reset_user_password = MagicMock(return_value="new_password")
    service.get_user_stats = AsyncMock(return_value={"total_users": 10, "active_users": 8})
    return service


class TestUserRoutesIntegration:
    """Integration tests for user management endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, mock_user_management_service: MagicMock) -> None:
        """Test user registration."""
        from app.main import create_app
        from httpx import AsyncClient, ASGITransport
        from unittest.mock import patch

        request_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "Password!135",
        }

        with patch(
            "app.routes.users.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            app = create_app(test_mode=True)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/v1/users/register", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert "user_id" in data
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert (
            data["message"]
            == "User created successfully. Please check your email to verify your account."
        )

    @pytest.mark.asyncio
    async def test_get_user(
        self, authenticated_client: AsyncClient, mock_user_management_service: MagicMock
    ) -> None:
        """Test getting user by ID with authentication."""
        user_id = str(uuid.uuid4())

        with patch(
            "app.routes.users.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            response = await authenticated_client.get(f"/v1/users/{user_id}")

            print(f"DEBUG: status_code = {response.status_code}")
            print(f"DEBUG: response text = {response.text}")

            data = response.json()
            print(f"DEBUG: response data = {data}")

            assert response.status_code == 200
            assert data["user_id"] is not None
            assert data["username"] == "test_user"
            assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(
        self, authenticated_client: AsyncClient, mock_user_management_service: MagicMock
    ) -> None:
        """Test updating user with authentication."""
        from app.models.schemas import TokenPayload
        from datetime import timezone, timedelta

        mock_token_payload = TokenPayload(
            user_id=str(uuid.uuid4()),
            username="test_admin",
            roles=["admin"],
            token_type="access",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        with (
            patch("app.services.authorization.get_current_user", return_value=mock_token_payload),
            patch(
                "app.routes.users.get_user_management_service",
                return_value=mock_user_management_service,
            ),
        ):
            user_id = str(uuid.uuid4())
            update_data = {"email": "updated@example.com", "roles": ["user", "admin"]}

            response = await authenticated_client.put(f"/v1/users/{user_id}", json=update_data)

            print(f"DEBUG: status_code = {response.status_code}")
            print(f"DEBUG: response text = {response.text}")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] is not None
            assert data["email"] == "updated@example.com"
            assert "admin" in data["roles"]

    @pytest.mark.asyncio
    async def test_delete_user(
        self, authenticated_client: AsyncClient, mock_user_management_service: MagicMock
    ) -> None:
        """Test deleting user with authentication."""
        with patch(
            "app.services.user_management.get_user_management_service",
            return_value=mock_user_management_service,
        ):
            user_id = str(uuid.uuid4())

            response = await authenticated_client.delete(f"/v1/users/{user_id}")

            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_reset_password(
        self, authenticated_client: AsyncClient, mock_user_management_service: MagicMock
    ) -> None:
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
            assert data["user_id"] == user_id
            assert "message" in data

    @pytest.mark.asyncio
    async def test_get_user_stats(
        self, authenticated_client: AsyncClient, mock_user_management_service: MagicMock
    ) -> None:
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
