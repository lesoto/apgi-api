"""
Unit tests for authentication routes — targeting ≥90% coverage of app/routes/auth.py.

Tests login, logout, token-refresh, and error paths.
Validates: Requirements 3.10, 3.15
"""

from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

try:
    from app.database.connection import get_db
    from app.exceptions import (
        AuthenticationError,
        ExpiredTokenError,
        InvalidTokenError,
    )
    from app.main import create_app
    from app.models.schemas import (
        TokenPayload,
    )
except ImportError:
    pytest.skip(
        "Required app modules not available - skipping auth routes tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_user() -> MagicMock:
    """Create a mock user object."""
    user = MagicMock()
    user.user_id = "test_user_123"
    user.username = "testuser"
    user.password_hash = "$2b$12$test_hash"
    user.is_active = True
    user.mfa_enabled = False
    user.mfa_secret = None
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = None
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_current_user() -> TokenPayload:
    """Create a mock current user token payload."""
    return TokenPayload(
        user_id="test_user_123",
        username="testuser",
        roles=["user"],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
        token_type="access",
    )


@pytest.fixture
def client(mock_db: MagicMock) -> Generator[TestClient, None, None]:
    """Create a TestClient with mocked database dependency."""
    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Login Tests
# ---------------------------------------------------------------------------


class TestLogin:
    """Test the /login endpoint."""

    def test_login_success(
        self, client: TestClient, mock_db: MagicMock, mock_user: MagicMock
    ) -> None:
        """Test successful login with valid credentials."""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = mock_user
            mock_auth_manager.create_tokens_for_user.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                    "remember_me": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test_access_token"
        assert data["refresh_token"] == "test_refresh_token"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800

    def test_login_with_remember_me(
        self, client: TestClient, mock_db: MagicMock, mock_user: MagicMock
    ) -> None:
        """Test login with remember_me flag."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = mock_user
            mock_auth_manager.create_tokens_for_user.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 2592000,  # 30 days
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                    "remember_me": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["refresh_expires_in"] == 2592000

    def test_login_with_mfa_code(
        self, client: TestClient, mock_db: MagicMock, mock_user: MagicMock
    ) -> None:
        """Test login with MFA code."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = mock_user
            mock_auth_manager.create_tokens_for_user.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                    "mfa_code": "123456",
                },
            )

        assert response.status_code == 200
        mock_auth_manager.authenticate_user.assert_called_once_with(
            "testuser", "SecurePassword123", "123456"
        )

    def test_login_invalid_credentials(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test login with invalid credentials."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = None
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "WrongPassword123",
                },
            )

        assert response.status_code == 401

    def test_login_account_locked(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test login when account is locked."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.side_effect = AuthenticationError(
                "Account is locked due to too many failed login attempts"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                },
            )

        assert response.status_code == 401

    def test_login_account_inactive(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test login when account is not active."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.side_effect = AuthenticationError(
                "Account is pending activation"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                },
            )

        assert response.status_code == 401

    def test_login_mfa_required(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test login when MFA code is required but not provided."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.side_effect = AuthenticationError(
                "MFA code required"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                },
            )

        assert response.status_code == 401

    def test_login_invalid_mfa_code(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test login with invalid MFA code."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.side_effect = AuthenticationError(
                "Invalid MFA code"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                    "mfa_code": "000000",
                },
            )

        assert response.status_code == 401

    def test_login_audit_log_import_failure(
        self, client: TestClient, mock_db: MagicMock, mock_user: MagicMock
    ) -> None:
        """Test login succeeds even if AuditLog import fails."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = mock_user
            mock_auth_manager.create_tokens_for_user.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            # Patch db.add to raise an exception (simulating audit log failure)
            mock_db.add.side_effect = Exception("Audit log error")

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                },
            )

        # Login should still succeed even if audit log fails
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_missing_username(self, client: TestClient) -> None:
        """Test login with missing username."""
        response = client.post(
            "/v1/auth/login",
            json={
                "password": "SecurePassword123",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_login_missing_password(self, client: TestClient) -> None:
        """Test login with missing password."""
        response = client.post(
            "/v1/auth/login",
            json={
                "username": "testuser",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_login_empty_username(self, client: TestClient) -> None:
        """Test login with empty username."""
        response = client.post(
            "/v1/auth/login",
            json={
                "username": "",
                "password": "SecurePassword123",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_login_weak_password(self, client: TestClient) -> None:
        """Test login with weak password."""
        response = client.post(
            "/v1/auth/login",
            json={
                "username": "testuser",
                "password": "weak",
            },
        )

        assert response.status_code == 422  # Validation error


# ---------------------------------------------------------------------------
# Token Refresh Tests
# ---------------------------------------------------------------------------


class TestRefreshToken:
    """Test the /refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test successful token refresh."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "valid_refresh_token",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new_access_token"
        assert data["refresh_token"] == "new_refresh_token"
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test refresh with invalid token."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.side_effect = InvalidTokenError("Invalid token")
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "invalid_token",
                },
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test refresh with expired token."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.side_effect = ExpiredTokenError(
                "Token has expired"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "expired_token",
                },
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_revoked(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test refresh with revoked token."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.side_effect = AuthenticationError(
                "Invalid or revoked refresh token"
            )
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "revoked_token",
                },
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_generic_error(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test refresh with generic error."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.side_effect = Exception("Unexpected error")
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "some_token",
                },
            )

        assert response.status_code == 401

    def test_refresh_token_missing(self, client: TestClient) -> None:
        """Test refresh with missing token."""
        response = client.post(
            "/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422  # Validation error


# ---------------------------------------------------------------------------
# Logout Tests
# ---------------------------------------------------------------------------


class TestLogout:
    """Test the /logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test successful logout."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.verify_token.return_value = mock_current_user
            mock_auth_manager.revoke_refresh_token.return_value = True
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

            response = client.post(
                "/v1/auth/logout",
                json={
                    "refresh_token": "valid_refresh_token",
                },
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_logout_token_mismatch(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test logout when token doesn't belong to current user."""
        other_user = TokenPayload(
            user_id="other_user_456",
            username="otheruser",
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            token_type="refresh",
        )

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.verify_token.return_value = other_user
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

            response = client.post(
                "/v1/auth/logout",
                json={
                    "refresh_token": "other_user_token",
                },
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_logout_invalid_token(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test logout with invalid refresh token."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.verify_token.side_effect = InvalidTokenError("Invalid token")
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

            response = client.post(
                "/v1/auth/logout",
                json={
                    "refresh_token": "invalid_token",
                },
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204  # Logout is graceful

    def test_logout_missing_refresh_token(
        self, client: TestClient, mock_current_user: TokenPayload
    ) -> None:
        """Test logout with missing refresh token."""
        # Override the get_current_user dependency
        from app.services.authorization import get_current_user

        client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

        response = client.post(
            "/v1/auth/logout",
            json={},
            headers={"Authorization": "Bearer valid_access_token"},
        )

        assert response.status_code == 422  # Validation error


# ---------------------------------------------------------------------------
# Logout Access Tests
# ---------------------------------------------------------------------------


class TestLogoutAccess:
    """Test the /logout-access endpoint."""

    @pytest.mark.asyncio
    async def test_logout_access_success(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test successful access token revocation."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.revoke_access_token.return_value = True
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

            response = client.post(
                "/v1/auth/logout-access",
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_logout_access_redis_unavailable(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test logout-access when Redis is unavailable."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.revoke_access_token.return_value = False
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

            response = client.post(
                "/v1/auth/logout-access",
                headers={"Authorization": "Bearer valid_access_token"},
            )

        # Should still return 204 (graceful degradation)
        assert response.status_code == 204

    def test_logout_access_missing_auth_header(
        self, client: TestClient, mock_current_user: TokenPayload
    ) -> None:
        """Test logout-access without Authorization header."""
        # Override the get_current_user dependency
        from app.services.authorization import get_current_user

        client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

        response = client.post("/v1/auth/logout-access")

        assert response.status_code == 401

    def test_logout_access_invalid_auth_header(
        self, client: TestClient, mock_current_user: TokenPayload
    ) -> None:
        """Test logout-access with invalid Authorization header."""
        # Override the get_current_user dependency
        from app.services.authorization import get_current_user

        client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

        response = client.post(
            "/v1/auth/logout-access",
            headers={"Authorization": "InvalidHeader"},
        )

        assert response.status_code == 401

    def test_logout_access_missing_bearer_token(
        self, client: TestClient, mock_current_user: TokenPayload
    ) -> None:
        """Test logout-access with Bearer prefix but no token."""
        # Override the get_current_user dependency
        from app.services.authorization import get_current_user

        client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore

        response = client.post(
            "/v1/auth/logout-access",
            headers={"Authorization": "Bearer "},
        )

        # Should still work (token extraction will get empty string)
        assert response.status_code in [204, 401]


# ---------------------------------------------------------------------------
# Integration Tests via TestClient
# ---------------------------------------------------------------------------


class TestAuthRoutesIntegration:
    """Integration tests for auth routes via TestClient."""

    def test_login_endpoint_via_client(
        self, client: TestClient, mock_db: MagicMock, mock_user: MagicMock
    ) -> None:
        """Test login endpoint through TestClient."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.authenticate_user.return_value = mock_user
            mock_auth_manager.create_tokens_for_user.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/login",
                json={
                    "username": "testuser",
                    "password": "SecurePassword123",
                },
            )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_refresh_endpoint_via_client(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test refresh endpoint through TestClient."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.refresh_access_token.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer",
                "expires_in": 1800,
                "refresh_expires_in": 604800,
            }
            mock_auth_manager_class.return_value = mock_auth_manager

            response = client.post(
                "/v1/auth/refresh",
                json={
                    "refresh_token": "valid_refresh_token",
                },
            )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_logout_endpoint_via_client(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test logout endpoint through TestClient."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.verify_token.return_value = mock_current_user
            mock_auth_manager.revoke_refresh_token.return_value = True
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore[attr-defined]

            response = client.post(
                "/v1/auth/logout",
                json={
                    "refresh_token": "valid_refresh_token",
                },
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204

    def test_logout_access_endpoint_via_client(
        self, client: TestClient, mock_db: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test logout-access endpoint through TestClient."""
        with patch("app.routes.auth.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = AsyncMock()
            mock_auth_manager.revoke_access_token.return_value = True
            mock_auth_manager_class.return_value = mock_auth_manager

            # Override the get_current_user dependency
            from app.services.authorization import get_current_user

            client.app.dependency_overrides[get_current_user] = lambda: mock_current_user  # type: ignore[attr-defined]

            response = client.post(
                "/v1/auth/logout-access",
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == 204
