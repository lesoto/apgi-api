"""
Unit tests for authentication middleware.

Tests JWT token and API key authentication, middleware dispatch, and helper functions.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from starlette.responses import JSONResponse

from app.middleware.authentication import (
    AuthenticationMiddleware,
    APIKeyInfo,
    get_current_user_from_request,
    is_authenticated,
)
from app.services.auth_manager import TokenPayload


@pytest.fixture
def auth_middleware():
    """Create authentication middleware instance."""
    app = MagicMock()
    return AuthenticationMiddleware(app)


@pytest.fixture
def mock_request():
    """Create a mock request."""

    class MockRequest:
        def __init__(self):
            self.url = type("URL", (), {"path": "/api/test"})()
            self.headers = {}
            self.state = type("State", (), {})()
            self.state.authenticated = False

    return MockRequest()


@pytest.fixture
def mock_user_payload():
    """Create a mock user payload."""
    return TokenPayload(
        user_id="user_123",
        username="testuser",
        roles=["user"],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def mock_api_key_info():
    """Create a mock API key info."""
    return APIKeyInfo(
        key_id="key_123",
        user_id="user_123",
        name="Test Key",
        permissions=["read", "write"],
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )


class TestAuthenticationMiddleware:
    """Test authentication middleware."""

    def test_is_public_path(self, auth_middleware):
        """Test public path detection."""
        assert auth_middleware._is_public_path("/health") is True
        assert auth_middleware._is_public_path("/api/users") is False
        assert auth_middleware._is_public_path("/v1/auth/login") is True

    @pytest.mark.asyncio
    async def test_dispatch_public_path(self, auth_middleware, mock_request):
        """Test dispatch for public paths skips authentication."""
        mock_request.url.path = "/health"
        call_next = AsyncMock(return_value=MagicMock())

        result = await auth_middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once_with(mock_request)
        # Should not set user state

    @pytest.mark.asyncio
    async def test_dispatch_no_auth_headers(self, auth_middleware, mock_request):
        """Test dispatch with no auth headers proceeds without authentication."""
        call_next = AsyncMock(return_value=MagicMock())

        with patch.object(auth_middleware, "_extract_and_verify_credentials", return_value=None):
            result = await auth_middleware.dispatch(mock_request, call_next)

            call_next.assert_called_once_with(mock_request)
            assert not hasattr(mock_request.state, "user")

    @pytest.mark.asyncio
    async def test_dispatch_invalid_auth_headers(self, auth_middleware, mock_request):
        """Test dispatch with invalid auth headers returns 401."""
        mock_request.headers = {"Authorization": "Bearer invalid"}
        call_next = AsyncMock()

        with patch.object(auth_middleware, "_extract_and_verify_credentials", return_value=None):
            result = await auth_middleware.dispatch(mock_request, call_next)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 401
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_valid_auth(self, auth_middleware, mock_request, mock_user_payload):
        """Test dispatch with valid authentication."""
        call_next = AsyncMock(return_value=MagicMock())

        with patch.object(
            auth_middleware,
            "_extract_and_verify_credentials",
            return_value=("jwt", mock_user_payload),
        ):
            result = await auth_middleware.dispatch(mock_request, call_next)

            assert mock_request.state.user == mock_user_payload
            assert mock_request.state.authenticated is True
            assert mock_request.state.auth_type == "jwt"
            call_next.assert_called_once_with(mock_request)

    def test_extract_token_valid(self, auth_middleware, mock_request):
        """Test token extraction from valid Authorization header."""
        mock_request.headers = {"Authorization": "Bearer test_token_123"}

        token = auth_middleware._extract_token(mock_request)

        assert token == "test_token_123"

    def test_extract_token_invalid_format(self, auth_middleware, mock_request):
        """Test token extraction from invalid Authorization header."""
        mock_request.headers = {"Authorization": "InvalidFormat"}

        token = auth_middleware._extract_token(mock_request)

        assert token is None

    def test_extract_token_no_header(self, auth_middleware, mock_request):
        """Test token extraction when no Authorization header."""
        token = auth_middleware._extract_token(mock_request)

        assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_valid(self, auth_middleware, mock_user_payload):
        """Test token verification."""
        with patch.object(
            auth_middleware, "_blocking_verify_token", return_value=mock_user_payload
        ):
            result = await auth_middleware._verify_token("test_token")

            assert result == mock_user_payload

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_middleware):
        """Test invalid token verification."""
        with patch.object(
            auth_middleware, "_blocking_verify_token", side_effect=Exception("Invalid token")
        ):
            with pytest.raises(Exception):
                await auth_middleware._verify_token("invalid_token")

    def test_blocking_verify_token(self, auth_middleware, mock_user_payload):
        """Test blocking token verification."""
        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.verify_token.return_value = mock_user_payload
            mock_auth_manager_class.return_value = mock_auth_manager

            result = auth_middleware._blocking_verify_token("test_token")

            assert result == mock_user_payload

    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self, auth_middleware, mock_api_key_info):
        """Test API key verification."""
        with patch.object(
            auth_middleware, "_blocking_verify_api_key", return_value=mock_api_key_info
        ):
            result = await auth_middleware._verify_api_key("test_key")

            assert result == mock_api_key_info

    def test_blocking_verify_api_key_valid(self, auth_middleware, mock_api_key_info):
        """Test blocking API key verification."""
        mock_api_key = MagicMock()
        mock_api_key.key_id = "key_123"
        mock_api_key.user_id = "user_123"
        mock_api_key.name = "Test Key"
        mock_api_key.permissions = ["read", "write"]
        mock_api_key.created_at = datetime.now(timezone.utc)
        mock_api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        mock_api_key.key_prefix = "prefix123"
        mock_api_key.key_hash = "hashed_key"

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.database.connection.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = (
                        "prefix123" + "0" * 32
                    )  # Make it long enough for [:32]
                    mock_hmac.return_value = mock_digest

                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session
                    mock_session.query.return_value.filter.return_value.all.return_value = [
                        mock_api_key
                    ]

                    mock_auth_manager = MagicMock()
                    mock_auth_manager.secret_key = "secret"
                    mock_auth_manager.verify_password.return_value = True
                    mock_auth_manager_class.return_value = mock_auth_manager

                    result = auth_middleware._blocking_verify_api_key("test_key")

                    assert result.key_id == "key_123"

    def test_blocking_verify_api_key_invalid(self, auth_middleware):
        """Test blocking API key verification with invalid key."""
        with patch("app.database.connection.SessionLocal") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.all.return_value = []

            with pytest.raises(ValueError, match="Invalid API key"):
                auth_middleware._blocking_verify_api_key("invalid_key")

    def test_blocking_verify_api_key_expired(self, auth_middleware):
        """Test blocking API key verification with expired key."""
        mock_api_key = MagicMock()
        mock_api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)  # Expired
        mock_api_key.key_prefix = "prefix123"
        mock_api_key.key_hash = "hashed_key"

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.database.connection.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "prefix123" + "0" * 32
                    mock_hmac.return_value = mock_digest

                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session
                    mock_session.query.return_value.filter.return_value.all.return_value = [
                        mock_api_key
                    ]

                    mock_auth_manager = MagicMock()
                    mock_auth_manager.secret_key = "secret"
                    mock_auth_manager.verify_password.return_value = True
                    mock_auth_manager_class.return_value = mock_auth_manager

                    with pytest.raises(ValueError, match="API key has expired"):
                        auth_middleware._blocking_verify_api_key("expired_key")

    @pytest.mark.asyncio
    async def test_extract_and_verify_credentials_jwt(
        self, auth_middleware, mock_request, mock_user_payload
    ):
        """Test credential extraction with JWT."""
        mock_request.headers = {"Authorization": "Bearer test_token"}

        with patch.object(auth_middleware, "_verify_token", return_value=mock_user_payload):
            result = await auth_middleware._extract_and_verify_credentials(mock_request)

            assert result == ("jwt", mock_user_payload)

    @pytest.mark.asyncio
    async def test_extract_and_verify_credentials_api_key(
        self, auth_middleware, mock_request, mock_api_key_info
    ):
        """Test credential extraction with API key."""
        mock_request.headers = {"X-API-Key": "test_key"}

        with patch.object(auth_middleware, "_verify_api_key", return_value=mock_api_key_info):
            result = await auth_middleware._extract_and_verify_credentials(mock_request)

            assert result[0] == "api_key"
            assert result[1].user_id == "user_123"

    @pytest.mark.asyncio
    async def test_extract_and_verify_credentials_none(self, auth_middleware, mock_request):
        """Test credential extraction with no valid credentials."""
        result = await auth_middleware._extract_and_verify_credentials(mock_request)

        assert result is None

    def test_create_error_response(self, auth_middleware):
        """Test error response creation."""
        response = auth_middleware._create_error_response(
            401, "invalid_credentials", "Invalid credentials"
        )

        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        content = response.body
        assert b"invalid_credentials" in content


def test_get_current_user_from_request_authenticated(mock_request, mock_user_payload):
    """Test getting current user from authenticated request."""
    mock_request.state.user = mock_user_payload

    user = get_current_user_from_request(mock_request)

    assert user == mock_user_payload


def test_get_current_user_from_request_unauthenticated(mock_request):
    """Test getting current user from unauthenticated request."""
    user = get_current_user_from_request(mock_request)

    assert user is None


def test_is_authenticated_true(mock_request):
    """Test checking if request is authenticated."""
    mock_request.state.authenticated = True

    assert is_authenticated(mock_request) is True


def test_is_authenticated_false(mock_request):
    """Test checking if request is not authenticated."""
    assert is_authenticated(mock_request) is False
