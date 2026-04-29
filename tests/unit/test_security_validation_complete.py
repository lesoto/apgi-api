"""
Additional unit tests for security validation middleware to achieve 100% coverage.

Covers:
- Blocked IP handling
- Rate limiting
- HEAD/OPTIONS request skipping
- Exception handling in dispatch and validation
- Client IP extraction edge cases
- Password complexity validation
- Field type validation edge cases
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.middleware.security_validation import SecurityValidationMiddleware


class TestSecurityValidationMiddlewareBlockedIP:
    """Test blocked IP handling."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_dispatch_blocked_ip(self, middleware: SecurityValidationMiddleware) -> None:
        """Test dispatch when client IP is blocked."""
        # Add IP to blocked list
        middleware.blocked_ips.add("192.168.1.100")

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"192.168.1.100")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 403
        assert "blocked" in str(exc_info.value.detail).lower()


class TestSecurityValidationMiddlewareRateLimit:
    """Test rate limiting functionality."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_exceeded(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test dispatch when rate limit is exceeded."""
        # Add many requests to exceed limit
        client_ip = "192.168.1.1"
        now = datetime.now(timezone.utc)
        # Add 101 timestamps to exceed the limit of 100, all within the last minute
        middleware.request_timestamps[client_ip] = [
            now - timedelta(seconds=i * 0.1) for i in range(101)
        ]

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"192.168.1.1")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 429

    def test_check_rate_limit_cleans_old_timestamps(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that old timestamps are cleaned when checking rate limit."""
        client_ip = "192.168.1.1"
        now = datetime.now(timezone.utc)

        # Add old and new timestamps
        middleware.request_timestamps[client_ip] = [
            now - timedelta(minutes=2),  # Old
            now - timedelta(seconds=30),  # Recent
        ]

        result = middleware._check_rate_limit(client_ip)

        assert result is True
        # Old timestamp should be cleaned
        assert len(middleware.request_timestamps[client_ip]) == 1


class TestSecurityValidationMiddlewareSkipMethods:
    """Test skipping validation for HEAD and OPTIONS methods."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_dispatch_head_request_skipped(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that HEAD requests skip validation."""
        scope = {
            "type": "http",
            "method": "HEAD",
            "path": "/test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_options_request_skipped(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that OPTIONS requests skip validation."""
        scope = {
            "type": "http",
            "method": "OPTIONS",
            "path": "/test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()


class TestSecurityValidationMiddlewareExceptionHandling:
    """Test exception handling in security validation."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_dispatch_exception_in_validation_returns_422(self, mock_app: Any) -> None:
        """Test that exceptions in validation return 422."""

        middleware = SecurityValidationMiddleware(mock_app, enabled=True)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/auth/login",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with patch.object(
            middleware,
            "_validate_request",
            return_value={"is_valid": False, "error_message": "Validation error", "score": 50},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422
        assert "Validation error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dispatch_high_risk_request_blocks_ip(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that high-risk requests block the IP."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        middleware = SecurityValidationMiddleware(app, enabled=True)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/auth/login",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with patch.object(
            middleware,
            "_validate_request",
            return_value={"is_valid": False, "error_message": "Dangerous content", "score": 90},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422
        # IP should be blocked
        assert len(middleware.blocked_ips) == 1


class TestClientIPExtraction:
    """Test client IP extraction."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_get_client_ip_x_forwarded_for(self, middleware: SecurityValidationMiddleware) -> None:
        """Test IP extraction from X-Forwarded-For header."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"x-forwarded-for", b"192.168.1.1, 10.0.0.1")],
        }
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}

        result = middleware._get_client_ip(request)
        assert result == "192.168.1.1"

    def test_get_client_ip_x_real_ip(self, middleware: SecurityValidationMiddleware) -> None:
        """Test IP extraction from X-Real-IP header."""
        request = MagicMock()
        request.headers = {"X-Real-IP": "192.168.1.2"}

        result = middleware._get_client_ip(request)
        assert result == "192.168.1.2"

    def test_get_client_ip_client_host(self, middleware: SecurityValidationMiddleware) -> None:
        """Test IP extraction from client host."""
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.3"

        result = middleware._get_client_ip(request)
        assert result == "192.168.1.3"

    def test_get_client_ip_unknown(self, middleware: SecurityValidationMiddleware) -> None:
        """Test IP extraction when no IP available."""
        request = MagicMock()
        request.headers = {}
        request.client = None

        result = middleware._get_client_ip(request)
        assert result == "unknown"


class TestPasswordComplexityValidation:
    """Test password complexity validation."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_password_missing_uppercase(self, middleware: SecurityValidationMiddleware) -> None:
        """Test password without uppercase letter."""
        result = middleware._validate_field_by_type("password", "lowercase123!")
        assert result["is_valid"] is False
        assert "uppercase" in result["error_message"]

    def test_password_missing_lowercase(self, middleware: SecurityValidationMiddleware) -> None:
        """Test password without lowercase letter."""
        result = middleware._validate_field_by_type("password", "UPPERCASE123!")
        assert result["is_valid"] is False
        assert "lowercase" in result["error_message"]

    def test_password_missing_digit(self, middleware: SecurityValidationMiddleware) -> None:
        """Test password without digit."""
        result = middleware._validate_field_by_type("password", "UpperCase!")
        assert result["is_valid"] is False
        assert "digit" in result["error_message"]

    def test_password_missing_special(self, middleware: SecurityValidationMiddleware) -> None:
        """Test password without special character."""
        result = middleware._validate_field_by_type("password", "UpperCase123")
        assert result["is_valid"] is False
        assert "special character" in result["error_message"]

    def test_password_valid_complex(self, middleware: SecurityValidationMiddleware) -> None:
        """Test valid complex password."""
        result = middleware._validate_field_by_type("password", "UpperCase123!")
        assert result["is_valid"] is True


class TestFieldTypeValidationEdgeCases:
    """Test field type validation edge cases."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_unknown_field_type_returns_valid(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that unknown field types return valid."""
        result = middleware._validate_field_by_type("unknown_type", "some_value")
        assert result["is_valid"] is True

    def test_string_not_string_type(self, middleware: SecurityValidationMiddleware) -> None:
        """Test string field with non-string value."""
        result = middleware._validate_field_by_type("username", 12345)
        assert result["is_valid"] is False
        assert "must be a string" in result["error_message"]

    def test_email_not_string(self, middleware: SecurityValidationMiddleware) -> None:
        """Test email field with non-string value."""
        result = middleware._validate_field_by_type("email", 12345)
        assert result["is_valid"] is False
        assert "must be a string" in result["error_message"]

    def test_uuid_not_string(self, middleware: SecurityValidationMiddleware) -> None:
        """Test UUID field with non-string value."""
        result = middleware._validate_field_by_type("id", 12345)
        assert result["is_valid"] is False
        assert "must be a string" in result["error_message"]

    def test_password_not_string(self, middleware: SecurityValidationMiddleware) -> None:
        """Test password field with non-string value."""
        result = middleware._validate_field_by_type("password", 12345)
        assert result["is_valid"] is False
        assert "must be a string" in result["error_message"]

    def test_uuid_invalid_format(self, middleware: SecurityValidationMiddleware) -> None:
        """Test UUID field with invalid format."""
        result = middleware._validate_field_by_type("id", "not-a-uuid")
        assert result["is_valid"] is False
        assert "Invalid" in result["error_message"]

    def test_uuid_valid_uppercase(self, middleware: SecurityValidationMiddleware) -> None:
        """Test UUID field with valid uppercase format."""
        result = middleware._validate_field_by_type("id", "550E8400-E29B-41D4-A716-446655440000")
        assert result["is_valid"] is True


class TestRequestValidationEdgeCases:
    """Test request validation edge cases."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_validate_request_large_payload(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test validation with large payload."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.json = AsyncMock(return_value={f"key{i}": f"value{i}" for i in range(60)})

        result = await middleware._validate_request(request, "192.168.1.1")

        # Large payload should increase score
        assert result["score"] >= 10

    @pytest.mark.asyncio
    async def test_validate_request_get_excessive_params(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test GET request with excessive query parameters."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/users"
        request.query_params = {f"param{i}": f"value{i}" for i in range(25)}
        request.headers = {}

        result = await middleware._validate_request(request, "192.168.1.1")

        # Excessive params should increase score
        assert result["score"] >= 5

    @pytest.mark.asyncio
    async def test_validate_request_json_parse_error(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test validation with JSON parse error."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/generic"
        request.headers = {"content-type": "application/json"}
        request.json = AsyncMock(side_effect=Exception("Parse error"))
        request.query_params = {}

        result = await middleware._validate_request(request, "192.168.1.1")

        # When parsing fails, validation returns invalid with error
        assert result["is_valid"] is False
        assert "Security validation failed" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_request_form_parse_error(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test validation with form parse error."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/generic"
        request.headers = {"content-type": "application/x-www-form-urlencoded"}
        request.form = AsyncMock(side_effect=Exception("Parse error"))
        request.query_params = {}

        result = await middleware._validate_request(request, "192.168.1.1")

        # When parsing fails, validation returns invalid with error
        assert result["is_valid"] is False
        assert "Security validation failed" in result["error_message"]


class TestUserProfileUpdatePath:
    """Test user profile update path validation."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_validate_user_profile_update_put(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test validation for PUT /v1/users/me."""
        request = MagicMock()
        request.method = "PUT"
        request.url.path = "/v1/users/me"
        request.headers = {"content-type": "application/json"}
        request.json = AsyncMock(return_value={"email": "test@example.com"})
        request.query_params = {}

        result = await middleware._validate_request(request, "192.168.1.1")

        assert "is_valid" in result
        assert "score" in result

    @pytest.mark.asyncio
    async def test_validate_user_profile_update_patch(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test validation for PATCH /v1/users/me."""
        request = MagicMock()
        request.method = "PATCH"
        request.url.path = "/v1/users/me"
        request.headers = {"content-type": "application/json"}
        request.json = AsyncMock(return_value={"name": "New Name"})
        request.query_params = {}

        result = await middleware._validate_request(request, "192.168.1.1")

        assert "is_valid" in result
        assert "score" in result


class TestRequestScoreTracking:
    """Test request score tracking."""

    @pytest.fixture
    def mock_app(self) -> Any:
        """Mock ASGI app."""

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app: Any) -> SecurityValidationMiddleware:
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_update_request_score_cleans_old_scores(
        self, middleware: SecurityValidationMiddleware
    ) -> None:
        """Test that old scores are cleaned when updating."""
        client_ip = "192.168.1.1"
        now = datetime.now(timezone.utc)

        # Add old scores
        middleware.request_scores[client_ip] = [50, 60, 70]
        middleware.request_timestamps[client_ip] = [
            now - timedelta(hours=2),  # Old
            now - timedelta(minutes=30),  # Recent
            now,  # Current
        ]

        middleware._update_request_score(client_ip, 40)

        # Old score should be cleaned
        assert len(middleware.request_scores[client_ip]) <= 3
