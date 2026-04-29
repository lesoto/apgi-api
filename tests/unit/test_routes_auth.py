"""
Tests for authentication routes.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from app.exceptions import AuthenticationError
from app.models.schemas import LoginRequest
from app.routes.auth import login, router


class TestAuthRoutes:
    """Test authentication endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        from sqlalchemy.orm import Session

        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_request(self):
        """Mock HTTP request."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        return request

    @pytest.mark.asyncio
    @patch("app.routes.auth.AuthManager")
    async def test_login_success(self, mock_auth_manager_class, mock_db, mock_request):
        """Test successful login."""
        mock_auth_manager = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = "user-1"
        mock_auth_manager.authenticate_user.return_value = mock_user
        mock_auth_manager.create_tokens_for_user.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "token_type": "bearer",
            "expires_in": 1800,
        }
        mock_auth_manager_class.return_value = mock_auth_manager

        body = LoginRequest(username="testuser", password="Password123")

        response = await login(mock_request, body, mock_db)

        assert response.access_token == "access123"
        assert response.refresh_token == "refresh123"
        assert response.token_type == "bearer"
        assert response.expires_in == 1800

    @pytest.mark.asyncio
    @patch("app.routes.auth.AuthManager")
    async def test_login_invalid_credentials(self, mock_auth_manager_class, mock_db, mock_request):
        """Test login with invalid credentials."""
        mock_auth_manager = MagicMock()
        mock_auth_manager.authenticate_user.return_value = None
        mock_auth_manager_class.return_value = mock_auth_manager

        body = LoginRequest(username="testuser", password="Wrongpassword1")

        with pytest.raises(AuthenticationError) as exc_info:
            await login(mock_request, body, mock_db)

        assert "Invalid username or password" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.routes.auth.AuthManager")
    async def test_login_with_mfa(self, mock_auth_manager_class, mock_db, mock_request):
        """Test login with MFA code."""
        mock_auth_manager = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = "user-1"
        mock_auth_manager.authenticate_user.return_value = mock_user
        mock_auth_manager.create_tokens_for_user.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "token_type": "bearer",
            "expires_in": 1800,
        }
        mock_auth_manager_class.return_value = mock_auth_manager

        body = LoginRequest(username="testuser", password="Password123", mfa_code="123456")

        response = await login(mock_request, body, mock_db)

        mock_auth_manager.authenticate_user.assert_called_with("testuser", "Password123", "123456")
        assert response.access_token == "access123"

    @pytest.mark.asyncio
    @patch("app.routes.auth.AuthManager")
    async def test_login_remember_me(self, mock_auth_manager_class, mock_db, mock_request):
        """Test login with remember_me flag."""
        mock_auth_manager = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = "user-1"
        mock_auth_manager.authenticate_user.return_value = mock_user
        mock_auth_manager.create_tokens_for_user.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "token_type": "bearer",
            "expires_in": 1800,
        }
        mock_auth_manager_class.return_value = mock_auth_manager

        body = LoginRequest(username="testuser", password="Password123", remember_me=True)

        response = await login(mock_request, body, mock_db)

        mock_auth_manager.create_tokens_for_user.assert_called_with(mock_user, True)

    def test_router_configuration(self):
        """Test router is properly configured."""
        assert router.prefix == "/v1/auth"
        assert router.tags == ["Authentication"]
        assert 401 in router.routes[0].responses
