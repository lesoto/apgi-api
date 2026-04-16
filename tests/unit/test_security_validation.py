"""
Unit tests for security validation middleware.
"""

import pytest
from unittest.mock import AsyncMock
from app.middleware.security_validation import SecurityValidationMiddleware


class TestSecurityValidationMiddleware:
    """Test security validation middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.fixture
    def disabled_middleware(self, mock_app):
        """Create disabled middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=False)

    @pytest.mark.asyncio
    async def test_dispatch_disabled(self, disabled_middleware):
        """Test dispatch when validation is disabled."""
        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        await disabled_middleware(scope, receive, send)
        # Should call mock_app and send response
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_get_request_valid(self, middleware):
        """Test dispatch with valid GET request."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/auth/login",
            "query_string": b"username=test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_post_request_valid(self, middleware):
        """Test dispatch with valid POST request."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/auth/login",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {
                "type": "http.request",
                "body": b'{"username": "testuser", "email": "test@example.com"}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    def test_validate_login_data_valid(self, middleware):
        """Test valid login data validation."""
        data = {"username": "testuser", "email": "test@example.com"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is True

    def test_validate_login_data_missing_username(self, middleware):
        """Test login validation with missing username."""
        data = {"email": "test@example.com"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    def test_validate_login_data_sql_injection(self, middleware):
        """Test login validation with SQL injection attempt."""
        # Using a pattern that is definitely in SQL_INJECTION_PATTERNS
        data = {"username": "admin; DROP TABLE users", "email": "test@example.com"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_login_data_malicious_chars(self, middleware):
        """Test login validation with malicious characters."""
        data = {"username": "test\x00user", "email": "test@example.com"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_login_data_too_long(self, middleware):
        """Test login validation with too long username."""
        data = {"username": "a" * 101, "email": "test@example.com"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    def test_validate_login_data_invalid_email(self, middleware):
        """Test login validation with invalid email."""
        data = {"username": "testuser", "email": "invalid-email"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "Invalid email format" in result["error_message"]

    def test_validate_registration_data_valid(self, middleware):
        """Test valid registration data validation."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePassword123!",
        }
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is True

    def test_validate_registration_data_missing_fields(self, middleware):
        """Test registration validation with missing fields."""
        data = {"username": "testuser"}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False

    def test_validate_registration_data_password_too_short(self, middleware):
        """Test registration validation with short password."""
        data = {"username": "testuser", "email": "test@example.com", "password": "short"}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    def test_validate_registration_data_password_too_long(self, middleware):
        """Test registration validation with long password."""
        data = {"username": "testuser", "email": "test@example.com", "password": "a" * 129}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    def test_validate_user_profile_data_valid(self, middleware):
        """Test valid user profile data validation."""
        data = {"email": "test@example.com", "name": "Test User"}
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is True

    def test_validate_user_profile_data_xss(self, middleware):
        """Test profile validation with XSS attempt."""
        data = {"name": "<script>alert('xss')</script>"}
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is False
        assert "dangerous content" in result["error_message"]

    def test_validate_search_data_valid(self, middleware):
        """Test valid search data validation."""
        data = {"search": "test query"}
        result = middleware._validate_search_data(data)
        assert result["is_valid"] is True

    def test_validate_search_data_sql_injection(self, middleware):
        """Test search validation with SQL injection."""
        data = {"search": "test; DROP TABLE users"}
        result = middleware._validate_search_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_password_data_valid(self, middleware):
        """Test valid password data validation."""
        data = {"password": "SecurePassword123"}
        result = middleware._validate_password_data(data)
        assert result["is_valid"] is True

    def test_validate_password_data_too_short(self, middleware):
        """Test password validation with short password."""
        data = {"password": "short"}
        result = middleware._validate_password_data(data)
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    def test_validate_generic_data_valid(self, middleware):
        """Test valid generic data validation."""
        data = {"field1": "value1", "field2": "value2"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is True

    def test_validate_generic_data_sql_injection(self, middleware):
        """Test generic validation with SQL injection."""
        data = {"field": "test; SELECT * FROM users"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False

    def test_validate_generic_data_xss(self, middleware):
        """Test generic validation with XSS."""
        data = {"field": "<script>alert('xss')</script>"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False

    def test_contains_sql_injection(self, middleware):
        """Test SQL injection detection."""
        assert middleware._contains_sql_injection("admin; SELECT * FROM users") is True
        assert middleware._contains_sql_injection("UNION SELECT") is True
        assert middleware._contains_sql_injection("normal text") is False

    def test_contains_xss(self, middleware):
        """Test XSS detection."""
        assert middleware._contains_xss("<script>alert('xss')</script>") is True
        assert middleware._contains_xss("javascript:alert('xss')") is True
        assert middleware._contains_xss("normal text") is False

    def test_contains_malicious_chars(self, middleware):
        """Test malicious character detection."""
        assert middleware._contains_malicious_chars("test\x00user") is True
        assert middleware._contains_malicious_chars("normal text") is False

    def test_is_valid_email_format(self, middleware):
        """Test email format validation."""
        assert middleware._is_valid_email_format("test@example.com") is True
        assert middleware._is_valid_email_format("invalid-email") is False
        assert middleware._is_valid_email_format("test@") is False

    @pytest.mark.asyncio
    async def test_validate_request_error_handling(self, middleware):
        """Test request validation error handling."""
        # Test with SQL injection in username
        # Mock a Request object with the malicious data
        from unittest.mock import MagicMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"username": "admin; DROP TABLE users"})

        # Call dispatch instead of _validate_request to test the full flow
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, None)

        assert exc_info.value.status_code == 422
        error_detail = str(exc_info.value.detail)
        assert "username contains invalid characters" in error_detail.lower()

    def test_middleware_initialization_enabled(self, mock_app):
        """Test middleware initialization with enabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True

    def test_middleware_initialization_disabled(self, mock_app):
        """Test middleware initialization with disabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False


# ---------------------------------------------------------------------------
# Tests merged from test_security_validation_real.py
# ---------------------------------------------------------------------------
class TestSecurityValidationMiddlewareASGI:
    """Test the security validation middleware at the ASGI level (scope/receive/send)."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create enabled middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.fixture
    def disabled_middleware(self, mock_app):
        """Create disabled middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=False)

    @pytest.mark.asyncio
    async def test_dispatch_disabled_passes_through(self, disabled_middleware):
        """Test that disabled middleware passes requests through."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"test": "data"}', "more_body": False}
        ]
        send = AsyncMock()

        await disabled_middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_head_request_skipped(self, middleware):
        """Test HEAD request is skipped from validation."""
        # Create a proper Request mock instead of ASGI scope
        from fastapi import Request

        # Mock request with HEAD method
        scope = {
            "type": "http",
            "method": "HEAD",
            "path": "/test",
            "headers": [],
        }

        async def mock_call_next(request):
            from fastapi import Response

            return Response(content="OK")

        # Convert ASGI scope to Request object for testing
        request = Request(scope)

        # HEAD and OPTIONS should be skipped
        response = await middleware.dispatch(request, mock_call_next)
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_dispatch_options_request_skipped(self, middleware):
        """Test OPTIONS request is skipped from validation."""
        # Create a proper Request mock instead of ASGI scope
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "OPTIONS",
            "path": "/test",
            "headers": [],
        }

        async def mock_call_next(request):
            from fastapi import Response

            return Response(content="OK")

        # Convert ASGI scope to Request object for testing
        request = Request(scope)

        # HEAD and OPTIONS should be skipped
        response = await middleware.dispatch(request, mock_call_next)
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_dispatch_post_valid_json(self, middleware):
        """Test POST request with valid JSON passes validation."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {
                "type": "http.request",
                "body": b'{"username": "test", "email": "test@example.com"}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_post_non_json_skipped(self, middleware):
        """Test POST request with non-JSON content type."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"text/plain")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b"some text data", "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_post_invalid_json_handled(self, middleware):
        """Test POST request with invalid JSON is handled gracefully."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"invalid": json}', "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_safe_query_params(self, middleware):
        """Test validation of safe query parameters."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/search",
            "query_string": b"q=test search",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_put_method(self, middleware):
        """Test PUT request validation."""
        scope = {
            "type": "http",
            "method": "PUT",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"data": "safe"}', "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_patch_method(self, middleware):
        """Test PATCH request validation."""
        scope = {
            "type": "http",
            "method": "PATCH",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"data": "safe"}', "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_multiple_chunks(self, middleware):
        """Test validation with chunked request body."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"partial":', "more_body": True},
            {"type": "http.request", "body": b' "data"}', "more_body": False},
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    def test_sql_injection_patterns_constants(self, middleware):
        """Test SQL injection pattern constants."""
        assert len(middleware.SQL_INJECTION_PATTERNS) > 0
        assert any("DROP" in pattern for pattern in middleware.SQL_INJECTION_PATTERNS)
        assert any("SELECT" in pattern for pattern in middleware.SQL_INJECTION_PATTERNS)

    def test_xss_patterns_constants(self, middleware):
        """Test XSS pattern constants."""
        assert len(middleware.XSS_PATTERNS) > 0
        assert any("script" in pattern for pattern in middleware.XSS_PATTERNS)
        assert any("javascript:" in pattern for pattern in middleware.XSS_PATTERNS)

    def test_malicious_chars_constants(self, middleware):
        """Test malicious character constants."""
        assert len(middleware.MALICIOUS_CHARS) > 0
        assert "\x00" in middleware.MALICIOUS_CHARS
        assert "\x01" in middleware.MALICIOUS_CHARS


# ---------------------------------------------------------------------------
# Tests merged from test_security_validation_comprehensive.py
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock
from fastapi import Request
from starlette.datastructures import Headers


@pytest.fixture
def _comp_mock_app():
    """Mock ASGI application for comprehensive tests."""

    async def mock_call_next(request):
        from fastapi import Response

        return Response(content="OK")

    return mock_call_next


@pytest.fixture
def _comp_middleware(_comp_mock_app):
    """Create security validation middleware instance for comprehensive tests."""
    return SecurityValidationMiddleware(_comp_mock_app, enabled=True)


@pytest.fixture
def _comp_disabled_middleware(_comp_mock_app):
    """Create disabled security validation middleware for comprehensive tests."""
    return SecurityValidationMiddleware(_comp_mock_app, enabled=False)


class TestValidateRequestAsync:
    """Tests for _validate_request async method (comprehensive)."""

    @pytest.mark.asyncio
    async def test_disabled_middleware_passes_through(self, _comp_disabled_middleware):
        """Test that disabled middleware passes requests through."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        response = await _comp_disabled_middleware.dispatch(
            mock_request, _comp_disabled_middleware.app
        )
        assert response is not None

    @pytest.mark.asyncio
    async def test_valid_login_data_via_validate_request(self, _comp_middleware):
        """Test valid login data via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "testuser", "password": "password123"}
        )

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True
        assert result["error_message"] == ""

    @pytest.mark.asyncio
    async def test_missing_username_login_via_validate_request(self, _comp_middleware):
        """Test login with missing username via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "password123"})

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_sql_injection_in_username_via_validate_request(self, _comp_middleware):
        """Test SQL injection in username via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "admin'--", "password": "password123"}
        )

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    @pytest.mark.asyncio
    async def test_valid_registration_via_validate_request(self, _comp_middleware):
        """Test valid registration data via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "testuser123",
                "email": "test@example.com",
                "password": "SecurePass123!",
            }
        )

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_xss_in_profile_via_validate_request(self, _comp_middleware):
        """Test XSS in profile field via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"bio": "<script>alert('xss')</script>"})

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "potentially dangerous content" in result["error_message"]

    @pytest.mark.asyncio
    async def test_sql_injection_in_search_via_validate_request(self, _comp_middleware):
        """Test SQL injection in search parameter via _validate_request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = {"search": "admin; DROP TABLE users"}

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_options_method_skipped(self, _comp_middleware):
        """Test OPTIONS method is skipped."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "OPTIONS"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        async def mock_call_next(request):
            from fastapi import Response

            return Response(content="OK")

        response = await _comp_middleware.dispatch(mock_request, mock_call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_head_method_skipped(self, _comp_middleware):
        """Test HEAD method is skipped."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "HEAD"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        async def mock_call_next(request):
            from fastapi import Response

            return Response(content="OK")

        response = await _comp_middleware.dispatch(mock_request, mock_call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_invalid_json_format_handled(self, _comp_middleware):
        """Test handling of invalid JSON."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        result = await _comp_middleware._validate_request(mock_request, "127.0.0.1")
        # Should return is_valid: False due to exception
        assert result["is_valid"] is False


class TestSQLInjectionPatternsDetailed:
    """Detailed tests for SQL injection pattern detection."""

    @pytest.fixture
    def middleware(self, _comp_mock_app):
        return SecurityValidationMiddleware(_comp_mock_app, enabled=True)

    def test_contains_sql_injection_comment(self, middleware):
        # Test with actual patterns that should match
        # The first pattern looks for: --\s or #\s
        assert middleware._contains_sql_injection("admin'-- ") is True
        assert middleware._contains_sql_injection("admin' # ") is True
        # Test semicolon patterns
        assert middleware._contains_sql_injection("admin'; DROP TABLE users") is True

    def test_contains_sql_injection_drop(self, middleware):
        assert middleware._contains_sql_injection("; DROP TABLE") is True

    def test_contains_sql_injection_union_all(self, middleware):
        assert middleware._contains_sql_injection("UNION ALL SELECT") is True

    def test_contains_sql_injection_time_based(self, middleware):
        # Test with actual patterns from the regex
        assert middleware._contains_sql_injection("WAITFOR DELAY '0:0:5'") is True
        assert middleware._contains_sql_injection("SELECT SLEEP(5)") is True
        assert middleware._contains_sql_injection("SELECT BENCHMARK(1000000, MD5(1))") is True

    def test_contains_sql_injection_boolean(self, middleware):
        # Test with actual patterns that should match
        # The pattern looks for: 1\s*=\s*1 or '1'\s*=\s*'1' or 1\s*OR\s*1
        assert middleware._contains_sql_injection("1 = 1") is True
        assert middleware._contains_sql_injection("'1' = '1'") is True
        assert middleware._contains_sql_injection("1 OR 1") is True

    def test_contains_sql_injection_negative_cases(self, middleware):
        assert middleware._contains_sql_injection("normalusername") is False
        assert middleware._contains_sql_injection("test@example.com") is False
        assert middleware._contains_sql_injection("Anderson") is False


class TestXSSPatternsDetailed:
    """Detailed tests for XSS pattern detection."""

    @pytest.fixture
    def middleware(self, _comp_mock_app):
        return SecurityValidationMiddleware(_comp_mock_app, enabled=True)

    def test_contains_xss_vbscript(self, middleware):
        assert middleware._contains_xss("vbscript:msgbox('xss')") is True

    def test_contains_xss_onload(self, middleware):
        assert middleware._contains_xss("<img onload='alert(1)'>") is True
        assert middleware._contains_xss("onload=") is True

    def test_contains_xss_onerror(self, middleware):
        assert middleware._contains_xss("<img src=x onerror='alert(1)'>") is True
        assert middleware._contains_xss("onerror=") is True

    def test_contains_xss_iframe(self, middleware):
        assert middleware._contains_xss("<iframe src='evil.html'></iframe>") is True

    def test_contains_xss_object(self, middleware):
        assert middleware._contains_xss("<object data='evil.swf'></object>") is True

    def test_contains_xss_expression(self, middleware):
        assert middleware._contains_xss("expression(alert('xss'))") is True

    def test_contains_xss_import(self, middleware):
        assert middleware._contains_xss("@import url('evil.css')") is True

    def test_contains_xss_negative_cases(self, middleware):
        assert middleware._contains_xss("normal text") is False
        assert middleware._contains_xss("javascript is a language") is False
        assert middleware._contains_xss("onload is an event") is False


class TestMaliciousCharactersDetailed:
    """Detailed tests for malicious character detection."""

    @pytest.fixture
    def middleware(self, _comp_mock_app):
        return SecurityValidationMiddleware(_comp_mock_app, enabled=True)

    def test_contains_control_chars(self, middleware):
        assert middleware._contains_malicious_chars("test\x01user") is True
        assert middleware._contains_malicious_chars("test\x1fuser") is True

    def test_contains_malicious_chars_negative(self, middleware):
        assert middleware._contains_malicious_chars("normal text") is False
        assert middleware._contains_malicious_chars("test\tuser") is False  # Tab is allowed
        assert middleware._contains_malicious_chars("test\nuser") is False  # Newline is allowed
        assert middleware._contains_malicious_chars("test\ruser") is False  # CR is allowed


class TestEmailValidationDetailed:
    """Detailed tests for email format validation."""

    @pytest.fixture
    def middleware(self, _comp_mock_app):
        return SecurityValidationMiddleware(_comp_mock_app, enabled=True)

    def test_valid_email_formats(self, middleware):
        assert middleware._is_valid_email_format("test@example.com") is True
        assert middleware._is_valid_email_format("user.name@example.com") is True
        assert middleware._is_valid_email_format("user+tag@example.co.uk") is True

    def test_invalid_email_formats(self, middleware):
        assert middleware._is_valid_email_format("invalid-email") is False
        assert middleware._is_valid_email_format("@example.com") is False
        assert middleware._is_valid_email_format("test@") is False
        assert middleware._is_valid_email_format("test@.com") is False

    def test_non_string_email(self, middleware):
        assert middleware._is_valid_email_format(123) is False
        assert middleware._is_valid_email_format(None) is False


# ---------------------------------------------------------------------------
# Additional tests for comprehensive coverage (reaching ≥90%)
# ---------------------------------------------------------------------------
class TestFormDataHandling:
    """Tests for form data handling in _validate_request."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_post_form_data_valid(self, middleware):
        """Test POST request with form data."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers, FormData

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        # Mock form data
        form_data = FormData()
        form_data._dict = {"username": "testuser", "password": "pass123"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock(side_effect=Exception("Not JSON"))

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_post_form_data_empty(self, middleware):
        """Test POST request with empty form data."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        mock_request.form = AsyncMock(return_value=None)
        mock_request.json = AsyncMock(side_effect=Exception("Not JSON"))

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        # Should fail because username is missing
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_post_form_data_exception(self, middleware):
        """Test POST request with form data exception."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        mock_request.form = AsyncMock(side_effect=Exception("Form parsing error"))
        mock_request.json = AsyncMock(side_effect=Exception("Not JSON"))

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        # Should handle exception gracefully
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_get_empty_query_params(self, middleware):
        """Test GET request with empty query parameters."""
        from unittest.mock import MagicMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = None

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        # Should pass with empty data
        assert result["is_valid"] is True


class TestNonDictDataHandling:
    """Tests for non-dict data handling in validation methods."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_login_data_non_dict(self, middleware):
        """Test login validation with non-dict data."""
        result = middleware._validate_login_data("not a dict")
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]

    def test_validate_login_data_non_string_username(self, middleware):
        """Test login validation with non-string username."""
        data = {"username": 123, "password": "pass"}
        result = middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    def test_validate_registration_data_non_dict(self, middleware):
        """Test registration validation with non-dict data."""
        result = middleware._validate_registration_data([])
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]

    def test_validate_registration_data_non_string_email(self, middleware):
        """Test registration validation with non-string email."""
        data = {"username": "test", "email": 123, "password": "SecurePass123"}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "email must be a string" in result["error_message"].lower()

    def test_validate_registration_data_non_string_password(self, middleware):
        """Test registration validation with non-string password."""
        data = {"username": "test", "email": "test@example.com", "password": 123}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "password must be a string" in result["error_message"].lower()

    def test_validate_user_profile_data_non_dict(self, middleware):
        """Test profile validation with non-dict data."""
        result = middleware._validate_user_profile_data(123)
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]

    def test_validate_search_data_non_dict(self, middleware):
        """Test search validation with non-dict data."""
        result = middleware._validate_search_data("not a dict")
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]

    def test_validate_password_data_non_dict(self, middleware):
        """Test password validation with non-dict data."""
        result = middleware._validate_password_data(None)
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]

    def test_validate_password_data_non_string_password(self, middleware):
        """Test password validation with non-string password."""
        data = {"password": 123}
        result = middleware._validate_password_data(data)
        assert result["is_valid"] is False
        assert "Password is required" in result["error_message"]

    def test_validate_generic_data_non_dict(self, middleware):
        """Test generic validation with non-dict data."""
        result = middleware._validate_generic_data([], "/test")
        assert result["is_valid"] is False
        assert "Invalid request format" in result["error_message"]


class TestPathMatchingAndRouting:
    """Tests for path matching and routing logic."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_login_path_with_trailing_slash(self, middleware):
        """Test login path with trailing slash."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login/"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"username": "test", "password": "pass"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_registration_path_with_trailing_slash(self, middleware):
        """Test registration path with trailing slash."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register/"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "test",
                "email": "test@example.com",
                "password": "SecurePass123!",
            }
        )

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_user_profile_path_with_trailing_slash(self, middleware):
        """Test user profile path with trailing slash."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me/"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"name": "Test User"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_user_profile_get_request_not_validated(self, middleware):
        """Test user profile GET request is not validated as profile update."""
        from unittest.mock import MagicMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({})
        mock_request.query_params = {}

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        # Should use generic validation, not profile validation
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_password_change_endpoint(self, middleware):
        """Test password change endpoint validation."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me/password"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "NewSecurePass123"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_password_change_endpoint_too_short(self, middleware):
        """Test password change endpoint with short password."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me/password"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "short"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    @pytest.mark.asyncio
    async def test_unknown_endpoint_generic_validation(self, middleware):
        """Test unknown endpoint uses generic validation."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/unknown/endpoint"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"field": "safe value"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is True


class TestRegistrationDataValidation:
    """Additional tests for registration data validation edge cases."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_registration_data_invalid_username_format(self, middleware):
        """Test registration with invalid username format."""
        data = {
            "username": "test!!!user",  # Invalid characters
            "email": "test@example.com",
            "password": "SecurePass123",
        }
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_registration_data_username_too_long(self, middleware):
        """Test registration with username too long."""
        data = {"username": "a" * 101, "email": "test@example.com", "password": "SecurePass123"}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    def test_validate_registration_data_username_with_sql_injection(self, middleware):
        """Test registration with SQL injection in username."""
        data = {
            "username": "test'; DROP TABLE users; --",
            "email": "test@example.com",
            "password": "SecurePass123",
        }
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_registration_data_username_with_malicious_chars(self, middleware):
        """Test registration with malicious characters in username."""
        data = {
            "username": "test\x00user",
            "email": "test@example.com",
            "password": "SecurePass123",
        }
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    def test_validate_registration_data_valid_username_formats(self, middleware):
        """Test registration with various valid username formats."""
        valid_usernames = [
            "testuser",
            "test_user",
            "test.user",
            "test+user",
            "test-user",
            "test$user",
            "test@domain",
        ]
        for username in valid_usernames:
            data = {"username": username, "email": "test@example.com", "password": "SecurePass123!"}
            result = middleware._validate_registration_data(data)
            assert result["is_valid"] is True, f"Username '{username}' should be valid"


class TestUserProfileDataValidation:
    """Additional tests for user profile data validation."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_user_profile_data_multiple_fields_with_xss(self, middleware):
        """Test profile validation with XSS in multiple fields."""
        data = {
            "name": "Test User",
            "bio": "<script>alert('xss')</script>",
            "email": "test@example.com",
        }
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is False
        assert "bio" in result["error_message"]
        assert "dangerous content" in result["error_message"]

    def test_validate_user_profile_data_non_string_field(self, middleware):
        """Test profile validation with non-string field."""
        data = {
            "name": "Test User",
            "age": 25,  # Non-string field should be ignored
            "email": "test@example.com",
        }
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is True

    def test_validate_user_profile_data_empty_email(self, middleware):
        """Test profile validation with empty email."""
        data = {"name": "Test User", "email": ""}  # Empty email should be ignored
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is True

    def test_validate_user_profile_data_invalid_email(self, middleware):
        """Test profile validation with invalid email."""
        data = {"name": "Test User", "email": "invalid-email"}
        result = middleware._validate_user_profile_data(data)
        assert result["is_valid"] is False
        assert "Invalid email format" in result["error_message"]


class TestSearchDataValidation:
    """Additional tests for search data validation."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_search_data_non_string_search(self, middleware):
        """Test search validation with non-string search parameter."""
        data = {"search": 123}  # Non-string should be ignored
        result = middleware._validate_search_data(data)
        assert result["is_valid"] is True

    def test_validate_search_data_empty_search(self, middleware):
        """Test search validation with empty search parameter."""
        data = {"search": ""}
        result = middleware._validate_search_data(data)
        assert result["is_valid"] is True

    def test_validate_search_data_union_select(self, middleware):
        """Test search validation with UNION SELECT injection."""
        data = {"search": "test UNION SELECT * FROM users"}
        result = middleware._validate_search_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]


class TestGenericDataValidation:
    """Additional tests for generic data validation."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_generic_data_multiple_fields_with_threats(self, middleware):
        """Test generic validation with multiple fields containing threats."""
        data = {"field1": "safe", "field2": "test; DROP TABLE", "field3": "safe"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False
        assert "field2" in result["error_message"]

    def test_validate_generic_data_xss_in_field(self, middleware):
        """Test generic validation with XSS in field."""
        data = {"field1": "safe", "field2": "<script>alert('xss')</script>"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False
        assert "field2" in result["error_message"]

    def test_validate_generic_data_malicious_chars_in_field(self, middleware):
        """Test generic validation with malicious characters."""
        data = {"field1": "safe", "field2": "test\x00user"}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False
        assert "field2" in result["error_message"]

    def test_validate_generic_data_non_string_fields(self, middleware):
        """Test generic validation with non-string fields."""
        data = {"field1": "safe", "field2": 123, "field3": True, "field4": None}
        result = middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is True


class TestContainsMethodsWithNonStringInput:
    """Tests for contains methods with non-string input."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_contains_sql_injection_non_string(self, middleware):
        """Test SQL injection detection with non-string input."""
        assert middleware._contains_sql_injection(123) is False
        assert middleware._contains_sql_injection(None) is False
        assert middleware._contains_sql_injection([]) is False

    def test_contains_xss_non_string(self, middleware):
        """Test XSS detection with non-string input."""
        assert middleware._contains_xss(123) is False
        assert middleware._contains_xss(None) is False
        assert middleware._contains_xss({}) is False

    def test_contains_malicious_chars_non_string(self, middleware):
        """Test malicious character detection with non-string input."""
        assert middleware._contains_malicious_chars(123) is False
        assert middleware._contains_malicious_chars(None) is False
        assert middleware._contains_malicious_chars(True) is False


class TestExceptionHandling:
    """Tests for exception handling in _validate_request."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    @pytest.mark.asyncio
    async def test_validate_request_exception_in_url_path_access(self, middleware):
        """Test exception handling when accessing request properties fails."""
        from unittest.mock import MagicMock, AsyncMock
        from starlette.datastructures import Headers

        mock_request = MagicMock()
        mock_request.method = "POST"
        # Simulate exception when accessing url.path
        mock_request.url = MagicMock()
        mock_request.url.path = MagicMock(side_effect=RuntimeError("URL access error"))
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"username": "test"})

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "Security validation failed" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_request_exception_in_headers_access(self, middleware):
        """Test exception handling when accessing headers fails."""
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        # Simulate exception when accessing headers
        mock_request.headers = MagicMock(side_effect=RuntimeError("Headers access error"))
        mock_request.headers.get = MagicMock(side_effect=RuntimeError("Headers access error"))

        result = await middleware._validate_request(mock_request, "127.0.0.1")
        assert result["is_valid"] is False
        assert "Security validation failed" in result["error_message"]


class TestRegistrationPasswordValidation:
    """Tests for password validation in registration."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return SecurityValidationMiddleware(mock_app, enabled=True)

    def test_validate_registration_data_missing_password(self, middleware):
        """Test registration validation with missing password."""
        data = {"username": "testuser", "email": "test@example.com"}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "Password is required" in result["error_message"]

    def test_validate_registration_data_empty_password(self, middleware):
        """Test registration validation with empty password."""
        data = {"username": "testuser", "email": "test@example.com", "password": ""}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "Password is required" in result["error_message"]

    def test_validate_registration_data_non_string_password(self, middleware):
        """Test registration validation with non-string password."""
        data = {"username": "testuser", "email": "test@example.com", "password": 12345}
        result = middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "password must be a string" in result["error_message"].lower()
