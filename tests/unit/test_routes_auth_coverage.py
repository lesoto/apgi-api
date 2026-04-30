"""
Coverage tests for app/routes/auth.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.exceptions import AuthenticationError, InvalidTokenError
from app.routes.auth import login, logout, logout_access, refresh_token
from app.services.authorization import TokenPayload


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "test-agent"}
    return request


@pytest.fixture
def mock_current_user():
    return TokenPayload(
        user_id="user-1", username="testuser", roles=["user"], permissions=[], exp=1234567890
    )


@pytest.mark.asyncio
async def test_login_success(mock_db, mock_request):
    """Test successful login."""
    with patch("app.routes.auth.AuthManager") as mock_auth_mgr_cls:
        mock_auth_mgr = mock_auth_mgr_cls.return_value
        mock_user = MagicMock()
        mock_user.user_id = "user-1"
        mock_auth_mgr.authenticate_user.return_value = mock_user
        mock_auth_mgr.create_tokens_for_user.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "token_type": "bearer",
            "expires_in": 1800,
        }

        from app.models.schemas import LoginRequest

        body = LoginRequest(username="test_user", password="Password123")

        response = await login(mock_request, body, mock_db)
        assert response.access_token == "at"
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_login_failure(mock_db, mock_request):
    """Test failed login."""
    with patch("app.routes.auth.AuthManager") as mock_auth_mgr_cls:
        mock_auth_mgr = mock_auth_mgr_cls.return_value
        mock_auth_mgr.authenticate_user.return_value = None

        from app.models.schemas import LoginRequest

        body = LoginRequest(username="test_user", password="Password123")

        with pytest.raises(AuthenticationError):
            await login(mock_request, body, mock_db)


@pytest.mark.asyncio
async def test_refresh_token_success(mock_db):
    """Test successful token refresh."""
    with patch("app.routes.auth.AuthManager") as mock_auth_mgr_cls:
        mock_auth_mgr = mock_auth_mgr_cls.return_value
        mock_auth_mgr.refresh_access_token = AsyncMock(
            return_value={
                "access_token": "new-at",
                "refresh_token": "new-rt",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        )

        from app.models.schemas import TokenRefreshRequest

        req = TokenRefreshRequest(refresh_token="rt")

        response = await refresh_token(req, mock_db)
        assert response.access_token == "new-at"


@pytest.mark.asyncio
async def test_logout_success(mock_db, mock_current_user):
    """Test successful logout."""
    with patch("app.routes.auth.AuthManager") as mock_auth_mgr_cls:
        mock_auth_mgr = mock_auth_mgr_cls.return_value
        mock_payload = MagicMock()
        mock_payload.user_id = mock_current_user.user_id
        mock_auth_mgr.verify_token = AsyncMock(return_value=mock_payload)
        mock_auth_mgr.revoke_refresh_token = AsyncMock()

        from app.models.schemas import TokenRefreshRequest

        req = TokenRefreshRequest(refresh_token="rt")

        await logout(req, mock_current_user, mock_db)
        assert mock_auth_mgr.revoke_refresh_token.called


@pytest.mark.asyncio
async def test_logout_access_success(mock_db, mock_current_user):
    """Test successful access token logout."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"authorization": "Bearer token123"}

    with patch("app.routes.auth.AuthManager") as mock_auth_mgr_cls:
        mock_auth_mgr = mock_auth_mgr_cls.return_value
        mock_auth_mgr.revoke_access_token = AsyncMock(return_value=True)

        await logout_access(mock_request, mock_current_user, mock_db)
        mock_auth_mgr.revoke_access_token.assert_called_with("token123")


@pytest.mark.asyncio
async def test_logout_access_no_header(mock_db, mock_current_user):
    """Test access token logout without header."""
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}

    with pytest.raises(InvalidTokenError):
        await logout_access(mock_request, mock_current_user, mock_db)
