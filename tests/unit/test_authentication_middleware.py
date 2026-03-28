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
            self.state = type("State", (), {"authenticated": False})()

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
        """Test dispatch with no auth headers returns 401 (deny-by-default)."""
        call_next = AsyncMock(return_value=MagicMock())

        with patch.object(auth_middleware, "_extract_and_verify_credentials", return_value=None):
            result = await auth_middleware.dispatch(mock_request, call_next)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 401
            call_next.assert_not_called()
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
            auth_middleware, "_decode_and_validate_token", return_value=mock_user_payload
        ):
            result = await auth_middleware._verify_token("test_token")

            assert result == mock_user_payload

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_middleware):
        """Test invalid token verification."""
        from app.exceptions import InvalidTokenError

        with patch.object(
            auth_middleware,
            "_decode_and_validate_token",
            side_effect=InvalidTokenError("Invalid token"),
        ):
            with pytest.raises(InvalidTokenError):
                await auth_middleware._verify_token("invalid_token")

    def test_decode_and_validate_token(self, auth_middleware, mock_user_payload):
        """Test blocking token verification."""
        from unittest.mock import patch

        # Mock jwt.decode to return a valid payload dict
        mock_payload = {
            "user_id": "test_user",
            "username": "testuser",
            "roles": ["user"],
            "exp": 2000000000,  # Future timestamp
            "token_type": "access",
        }

        with (
            patch("jwt.decode", return_value=mock_payload),
            patch(
                "app.services.auth_manager.TokenPayload.from_dict", return_value=mock_user_payload
            ),
        ):
            result = auth_middleware._decode_and_validate_token("valid.jwt.token")

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
        mock_api_key.key_prefix = "prefix1230000000"
        mock_api_key.key_hash = "hashed_key"
        mock_api_key.is_active = True

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "prefix1230000000"
                    mock_hmac.return_value = mock_digest

                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session
                    mock_session.query.return_value.filter.return_value.all.return_value = [
                        mock_api_key
                    ]
                    # Ensure prefix matches what was mocked in hexdigest above
                    mock_api_key.key_prefix = "prefix1230000000"

                    mock_auth_manager = MagicMock()
                    mock_auth_manager.secret_key = "secret"
                    mock_auth_manager.verify_password.return_value = True
                    mock_auth_manager_class.return_value = mock_auth_manager

                    result = auth_middleware._blocking_verify_api_key("test_key")

                    assert result.key_id == "key_123"

    def test_blocking_verify_api_key_invalid(self, auth_middleware):
        """Test blocking API key verification with invalid key."""
        with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.all.return_value = []

            with pytest.raises(ValueError, match="Invalid API key"):
                auth_middleware._blocking_verify_api_key("invalid_key")

    def test_blocking_verify_api_key_expired(self, auth_middleware):
        """Test blocking API key verification with expired key."""
        mock_api_key = MagicMock()
        mock_api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)  # Expired
        mock_api_key.key_prefix = "prefix1230000000"
        mock_api_key.key_hash = "hashed_key"
        mock_api_key.is_active = True

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "prefix1230000000"
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


class TestAuthenticationMiddlewareCoverage:
    """Additional tests to reach ≥90% coverage for authentication.py."""

    # ── set_redis_client (line 93) ──────────────────────────────────────────

    def test_set_redis_client(self, auth_middleware):
        """Test set_redis_client classmethod sets the class-level attribute."""
        mock_redis = MagicMock()
        AuthenticationMiddleware.set_redis_client(mock_redis)
        assert AuthenticationMiddleware._redis_client is mock_redis
        # Clean up
        AuthenticationMiddleware._redis_client = None

    # ── _verify_token: Redis revocation check (lines 178-180) ──────────────

    @pytest.mark.asyncio
    async def test_verify_token_revoked_in_redis(self, auth_middleware, mock_user_payload):
        """Token with jti that is revoked in Redis raises InvalidTokenError."""
        from app.exceptions import InvalidTokenError

        mock_user_payload.jti = "some-jti-value"
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=True)
        AuthenticationMiddleware._redis_client = mock_redis

        try:
            with patch.object(
                auth_middleware, "_decode_and_validate_token", return_value=mock_user_payload
            ):
                with pytest.raises(InvalidTokenError, match="revoked"):
                    await auth_middleware._verify_token("some.jwt.token")
        finally:
            AuthenticationMiddleware._redis_client = None

    @pytest.mark.asyncio
    async def test_verify_token_not_revoked_in_redis(self, auth_middleware, mock_user_payload):
        """Token with jti that is NOT revoked in Redis passes through."""
        mock_user_payload.jti = "some-jti-value"
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)
        AuthenticationMiddleware._redis_client = mock_redis

        try:
            with patch.object(
                auth_middleware, "_decode_and_validate_token", return_value=mock_user_payload
            ):
                result = await auth_middleware._verify_token("some.jwt.token")
                assert result == mock_user_payload
        finally:
            AuthenticationMiddleware._redis_client = None

    # ── _decode_and_validate_token: missing secret key (lines 198-200) ─────

    def test_decode_and_validate_token_no_secret_key(self, auth_middleware):
        """Raises InvalidTokenError when JWT secret key is not configured."""
        from app.exceptions import InvalidTokenError

        with patch("app.middleware.authentication._decode_and_validate_token", create=True):
            with patch("app.config.settings") as mock_settings:
                mock_settings.jwt_secret_key = None
                with pytest.raises(InvalidTokenError, match="not configured"):
                    auth_middleware._decode_and_validate_token("some.token")

    # ── _decode_and_validate_token: wrong token_type (lines 247-251) ───────

    def test_decode_and_validate_token_wrong_type(self, auth_middleware, mock_user_payload):
        """Raises InvalidTokenError when token_type is not 'access'."""
        from app.exceptions import InvalidTokenError

        mock_user_payload.token_type = "refresh"
        mock_payload_dict = {
            "user_id": "u1",
            "username": "u",
            "roles": [],
            "exp": 9999999999,
            "token_type": "refresh",
        }

        with (
            patch("jwt.decode", return_value=mock_payload_dict),
            patch(
                "app.services.auth_manager.TokenPayload.from_dict",
                return_value=mock_user_payload,
            ),
        ):
            with pytest.raises(InvalidTokenError, match="Invalid token type"):
                auth_middleware._decode_and_validate_token("some.token")

    # ── _decode_and_validate_token: manual expiry check (line 267) ──────────

    def test_decode_and_validate_token_expired_manually(self, auth_middleware):
        """Raises ExpiredTokenError when exp is in the past (manual check)."""
        from app.exceptions import ExpiredTokenError

        expired_payload = TokenPayload(
            user_id="u1",
            username="u",
            roles=[],
            exp=datetime(2000, 1, 1, tzinfo=timezone.utc),  # past
            token_type="access",
        )
        mock_payload_dict = {
            "user_id": "u1",
            "username": "u",
            "roles": [],
            "exp": 946684800,  # 2000-01-01 in the past
            "token_type": "access",
        }

        with (
            patch("jwt.decode", return_value=mock_payload_dict),
            patch(
                "app.services.auth_manager.TokenPayload.from_dict",
                return_value=expired_payload,
            ),
        ):
            with pytest.raises(ExpiredTokenError):
                auth_middleware._decode_and_validate_token("some.token")

    # ── _decode_and_validate_token: jwt.ExpiredSignatureError (line 281) ────

    def test_decode_and_validate_token_jwt_expired_signature(self, auth_middleware):
        """Raises ExpiredTokenError when jwt raises ExpiredSignatureError."""
        import jwt as pyjwt
        from app.exceptions import ExpiredTokenError

        with patch("jwt.decode", side_effect=pyjwt.ExpiredSignatureError("expired")):
            with pytest.raises(ExpiredTokenError):
                auth_middleware._decode_and_validate_token("some.token")

    # ── _decode_and_validate_token: jwt.InvalidTokenError (line 287) ────────

    def test_decode_and_validate_token_jwt_invalid_token_error(self, auth_middleware):
        """Raises InvalidTokenError when jwt raises InvalidTokenError."""
        import jwt as pyjwt
        from app.exceptions import InvalidTokenError

        with patch("jwt.decode", side_effect=pyjwt.InvalidTokenError("bad token")):
            with pytest.raises(InvalidTokenError, match="Invalid token"):
                auth_middleware._decode_and_validate_token("some.token")

    # ── _decode_and_validate_token: generic Exception (lines 291-298) ───────

    def test_decode_and_validate_token_generic_exception(self, auth_middleware):
        """Raises InvalidTokenError when an unexpected exception occurs."""
        from app.exceptions import InvalidTokenError

        with patch("jwt.decode", side_effect=RuntimeError("unexpected")):
            with pytest.raises(InvalidTokenError, match="Token verification failed"):
                auth_middleware._decode_and_validate_token("some.token")

    # ── _blocking_verify_api_key: no secret key (line 331) ──────────────────

    def test_blocking_verify_api_key_no_secret_key(self, auth_middleware):
        """Raises ValueError when AuthManager has no secret key."""
        with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
            with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                mock_auth_manager = MagicMock()
                mock_auth_manager.secret_key = None
                mock_auth_manager_class.return_value = mock_auth_manager

                with pytest.raises(ValueError, match="Secret key not configured"):
                    auth_middleware._blocking_verify_api_key("some_key")

    # ── _blocking_verify_api_key: no matching key after loop (line 367) ─────

    def test_blocking_verify_api_key_no_match_after_loop(self, auth_middleware):
        """Raises ValueError when prefix matches but password check fails for all candidates."""
        mock_api_key = MagicMock()
        mock_api_key.key_prefix = "prefix1230000000"
        mock_api_key.key_hash = "hashed_key"
        mock_api_key.is_active = True

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "prefix1230000000"
                    mock_hmac.return_value = mock_digest

                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session
                    mock_session.query.return_value.filter.return_value.all.return_value = [
                        mock_api_key
                    ]

                    mock_auth_manager = MagicMock()
                    mock_auth_manager.secret_key = "secret"
                    # Password check always fails → no match found
                    mock_auth_manager.verify_password.return_value = False
                    mock_auth_manager_class.return_value = mock_auth_manager

                    with pytest.raises(ValueError, match="Invalid API key"):
                        auth_middleware._blocking_verify_api_key("test_key")

    # ── _blocking_verify_api_key: commit failure → warning + rollback (lines 377-382) ──

    def test_blocking_verify_api_key_commit_failure_logs_warning(self, auth_middleware):
        """When db.commit() raises, logs a warning and rolls back without failing auth."""
        mock_api_key = MagicMock()
        mock_api_key.key_id = "key_123"
        mock_api_key.user_id = "user_123"
        mock_api_key.name = "Test Key"
        mock_api_key.permissions = ["read"]
        mock_api_key.created_at = datetime.now(timezone.utc)
        mock_api_key.expires_at = None  # no expiry
        mock_api_key.key_prefix = "prefix1230000000"
        mock_api_key.key_hash = "hashed_key"
        mock_api_key.is_active = True

        with patch("app.middleware.authentication.AuthManager") as mock_auth_manager_class:
            with patch("app.middleware.authentication.SessionLocal") as mock_session_class:
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "prefix1230000000"
                    mock_hmac.return_value = mock_digest

                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session
                    mock_session.query.return_value.filter.return_value.all.return_value = [
                        mock_api_key
                    ]
                    # Simulate commit failure
                    mock_session.commit.side_effect = Exception("DB error")

                    mock_auth_manager = MagicMock()
                    mock_auth_manager.secret_key = "secret"
                    mock_auth_manager.verify_password.return_value = True
                    mock_auth_manager_class.return_value = mock_auth_manager

                    # Should still return APIKeyInfo despite commit failure
                    result = auth_middleware._blocking_verify_api_key("test_key")
                    assert result.key_id == "key_123"
                    mock_session.rollback.assert_called_once()

    # ── _extract_and_verify_credentials: JWT fails, API key also fails ──────

    @pytest.mark.asyncio
    async def test_extract_and_verify_credentials_jwt_fails_api_key_fails(
        self, auth_middleware, mock_request
    ):
        """Returns None when JWT is invalid and API key is also invalid."""
        from app.exceptions import InvalidTokenError

        mock_request.headers = {
            "Authorization": "Bearer bad_token",
            "X-API-Key": "bad_key",
        }

        with patch.object(auth_middleware, "_verify_token", side_effect=InvalidTokenError("bad")):
            with patch.object(
                auth_middleware, "_verify_api_key", side_effect=ValueError("bad key")
            ):
                result = await auth_middleware._extract_and_verify_credentials(mock_request)
                assert result is None

    # ── dispatch: valid JWT token on protected path → 200 ───────────────────

    @pytest.mark.asyncio
    async def test_dispatch_valid_jwt_protected_path(
        self, auth_middleware, mock_request, mock_user_payload
    ):
        """Valid JWT on a protected path passes through and returns the downstream response."""
        mock_request.url.path = "/api/protected"
        mock_request.headers = {"Authorization": "Bearer valid.jwt.token"}
        downstream_response = MagicMock(status_code=200)
        call_next = AsyncMock(return_value=downstream_response)

        with patch.object(
            auth_middleware,
            "_extract_and_verify_credentials",
            return_value=("jwt", mock_user_payload),
        ):
            result = await auth_middleware.dispatch(mock_request, call_next)

        assert result is downstream_response
        assert mock_request.state.authenticated is True
        assert mock_request.state.user == mock_user_payload
        call_next.assert_called_once_with(mock_request)

    # ── dispatch: missing token on protected path → 401 ─────────────────────

    @pytest.mark.asyncio
    async def test_dispatch_missing_token_protected_path(self, auth_middleware, mock_request):
        """No auth headers on a protected path returns 401 authentication_required."""
        import json

        mock_request.url.path = "/api/protected"
        mock_request.headers = {}
        call_next = AsyncMock()

        result = await auth_middleware.dispatch(mock_request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        body = json.loads(result.body)
        assert body["error"]["code"] == "authentication_required"
        call_next.assert_not_called()

    # ── dispatch: expired JWT token → 401 ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_dispatch_expired_jwt_protected_path(self, auth_middleware, mock_request):
        """Expired JWT on a protected path returns 401 invalid_credentials."""
        import json

        mock_request.url.path = "/api/protected"
        mock_request.headers = {"Authorization": "Bearer expired.jwt.token"}
        call_next = AsyncMock()

        # _extract_and_verify_credentials returns None (expired token → no valid creds)
        with patch.object(auth_middleware, "_extract_and_verify_credentials", return_value=None):
            result = await auth_middleware.dispatch(mock_request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        body = json.loads(result.body)
        assert body["error"]["code"] == "invalid_credentials"
        call_next.assert_not_called()

    # ── _create_error_response: non-401 status code (no WWW-Authenticate) ───

    def test_create_error_response_non_401(self, auth_middleware):
        """Non-401 error response does not include WWW-Authenticate header."""
        response = auth_middleware._create_error_response(403, "forbidden", "Access denied")
        assert response.status_code == 403
        assert "WWW-Authenticate" not in response.headers
