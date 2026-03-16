"""Comprehensive tests for SecurityValidationMiddleware."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException
from starlette.datastructures import Headers
from app.middleware.security_validation import SecurityValidationMiddleware


@pytest.fixture
def mock_app():
    """Mock ASGI application."""

    async def mock_call_next(request):
        from fastapi import Response

        return Response(content="OK")

    return mock_call_next


@pytest.fixture
def middleware(mock_app):
    """Create security validation middleware instance."""
    return SecurityValidationMiddleware(mock_app, enabled=True)


@pytest.fixture
def disabled_middleware(mock_app):
    """Create disabled security validation middleware."""
    return SecurityValidationMiddleware(mock_app, enabled=False)


class TestMiddlewareInitialization:
    """Tests for middleware initialization."""

    def test_enabled_middleware(self, mock_app):
        """Test middleware initialization when enabled."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True

    def test_disabled_middleware(self, mock_app):
        """Test middleware initialization when disabled."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False


class TestDispatch:
    """Tests for dispatch method."""

    @pytest.mark.asyncio
    async def test_disabled_middleware_passes_through(self, disabled_middleware):
        """Test that disabled middleware passes requests through."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        response = await disabled_middleware.dispatch(mock_request, disabled_middleware.app)
        assert response is not None

    @pytest.mark.asyncio
    async def test_valid_request_passes(self, middleware):
        """Test that valid requests pass through."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = {}

        response = await middleware.dispatch(mock_request, middleware.app)
        assert response is not None

    @pytest.mark.asyncio
    async def test_invalid_request_raises_exception(self, middleware):
        """Test that invalid requests raise HTTPException."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "test", "email": "invalid-email", "password": "short"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, middleware.app)
        assert exc_info.value.status_code == 422


class TestLoginValidation:
    """Tests for login endpoint validation."""

    @pytest.mark.asyncio
    async def test_valid_login_data(self, middleware):
        """Test valid login data."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "testuser", "password": "password123"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True
        assert result["error_message"] == ""

    @pytest.mark.asyncio
    async def test_missing_username_login(self, middleware):
        """Test login with missing username."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "password123"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_sql_injection_in_username_login(self, middleware):
        """Test SQL injection in username."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "admin'--", "password": "password123"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    @pytest.mark.asyncio
    async def test_union_select_injection_login(self, middleware):
        """Test UNION SELECT injection."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "admin UNION SELECT * FROM users--",
                "password": "password123",
            }
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_invalid_email_login(self, middleware):
        """Test invalid email format in login."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "testuser",
                "email": "invalid-email",
                "password": "password123",
            }
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Invalid email format" in result["error_message"]

    @pytest.mark.asyncio
    async def test_malicious_chars_in_username_login(self, middleware):
        """Test malicious control characters in username."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "test\x00user", "password": "password123"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_long_username_login(self, middleware):
        """Test username exceeding max length."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "a" * 101, "password": "password123"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]


class TestRegistrationValidation:
    """Tests for registration endpoint validation."""

    @pytest.mark.asyncio
    async def test_valid_registration_data(self, middleware):
        """Test valid registration data."""
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

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_missing_username_registration(self, middleware):
        """Test registration with missing username."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"email": "test@example.com", "password": "SecurePass123!"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_missing_email_registration(self, middleware):
        """Test registration with missing email."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "testuser", "password": "SecurePass123!"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Email is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_missing_password_registration(self, middleware):
        """Test registration with missing password."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "testuser", "email": "test@example.com"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Password is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_short_password_registration(self, middleware):
        """Test registration with short password."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "testuser", "email": "test@example.com", "password": "short"}
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    @pytest.mark.asyncio
    async def test_long_password_registration(self, middleware):
        """Test registration with long password."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "testuser",
                "email": "test@example.com",
                "password": "a" * 129,
            }
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    @pytest.mark.asyncio
    async def test_invalid_username_format_registration(self, middleware):
        """Test registration with invalid username format."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={
                "username": "test user!",
                "email": "test@example.com",
                "password": "SecurePass123!",
            }
        )

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False


class TestUserProfileValidation:
    """Tests for user profile validation."""

    @pytest.mark.asyncio
    async def test_valid_profile_update(self, middleware):
        """Test valid profile update."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"email": "newemail@example.com"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_xss_in_profile_field(self, middleware):
        """Test XSS in profile field."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"bio": "<script>alert('xss')</script>"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "potentially dangerous content" in result["error_message"]

    @pytest.mark.asyncio
    async def test_javascript_url_in_profile(self, middleware):
        """Test javascript: URL in profile."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"website": "javascript:alert('xss')"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_onload_in_profile(self, middleware):
        """Test onload attribute in profile."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"bio": "<img onload='alert(1)'>"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_invalid_email_in_profile(self, middleware):
        """Test invalid email in profile update."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "PATCH"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"email": "invalid-email"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Invalid email format" in result["error_message"]


class TestSearchValidation:
    """Tests for search endpoint validation."""

    @pytest.mark.asyncio
    async def test_valid_search_query(self, middleware):
        """Test valid search query."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = {"search": "testuser"}

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_sql_injection_in_search(self, middleware):
        """Test SQL injection in search parameter."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = {"search": "admin' OR '1'='1"}

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_union_in_search(self, middleware):
        """Test UNION in search parameter."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})
        mock_request.query_params = {"search": "test UNION SELECT * FROM users"}

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False


class TestPasswordChangeValidation:
    """Tests for password change validation."""

    @pytest.mark.asyncio
    async def test_valid_password_change(self, middleware):
        """Test valid password change."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me/password"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "NewSecurePass123!"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_missing_password_change(self, middleware):
        """Test password change with missing password."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me/password"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False
        assert "Password is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_short_password_change(self, middleware):
        """Test password change with short password."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me/password"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"password": "short"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False


class TestGenericValidation:
    """Tests for generic data validation."""

    @pytest.mark.asyncio
    async def test_generic_sql_injection(self, middleware):
        """Test SQL injection in generic endpoint."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/some/endpoint"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"field": "value' OR '1'='1"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_generic_xss(self, middleware):
        """Test XSS in generic endpoint."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/some/endpoint"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"field": "<script>alert('xss')</script>"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_generic_malicious_chars(self, middleware):
        """Test malicious characters in generic endpoint."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/some/endpoint"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(return_value={"field": "value\x00with\x01nulls"})

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False


class TestSQLInjectionPatterns:
    """Tests for SQL injection pattern detection."""

    def test_contains_sql_injection_comment(self, middleware):
        """Test SQL comment injection detection."""
        assert middleware._contains_sql_injection("admin'--") is True
        assert middleware._contains_sql_injection("admin' #") is True

    def test_contains_sql_injection_drop(self, middleware):
        """Test DROP statement injection detection."""
        assert middleware._contains_sql_injection("; DROP TABLE") is True
        assert middleware._contains_sql_injection("admin; DROP") is True

    def test_contains_sql_injection_select(self, middleware):
        """Test SELECT injection detection."""
        assert middleware._contains_sql_injection("; SELECT * FROM") is True
        assert middleware._contains_sql_injection("UNION SELECT") is True

    def test_contains_sql_injection_union_all(self, middleware):
        """Test UNION ALL SELECT injection detection."""
        assert middleware._contains_sql_injection("UNION ALL SELECT") is True

    def test_contains_sql_injection_time_based(self, middleware):
        """Test time-based injection detection."""
        assert middleware._contains_sql_injection("WAITFOR DELAY") is True
        assert middleware._contains_sql_injection("SLEEP(5)") is True
        assert middleware._contains_sql_injection("BENCHMARK(") is True

    def test_contains_sql_injection_boolean(self, middleware):
        """Test boolean-based injection detection."""
        assert middleware._contains_sql_injection("1=1") is True
        assert middleware._contains_sql_injection("'1'='1'") is True
        assert middleware._contains_sql_injection("1 OR 1") is True

    def test_contains_sql_injection_negative_cases(self, middleware):
        """Test negative cases for SQL injection."""
        assert middleware._contains_sql_injection("normalusername") is False
        assert middleware._contains_sql_injection("test@example.com") is False
        assert middleware._contains_sql_injection("Anderson") is False


class TestXSSPatterns:
    """Tests for XSS pattern detection."""

    def test_contains_xss_script(self, middleware):
        """Test script tag XSS detection."""
        assert middleware._contains_xss("<script>alert('xss')</script>") is True
        assert middleware._contains_xss("<script src='evil.js'></script>") is True

    def test_contains_xss_javascript(self, middleware):
        """Test javascript: URL detection."""
        assert middleware._contains_xss("javascript:alert('xss')") is True

    def test_contains_xss_vbscript(self, middleware):
        """Test vbscript: URL detection."""
        assert middleware._contains_xss("vbscript:msgbox('xss')") is True

    def test_contains_xss_onload(self, middleware):
        """Test onload event handler detection."""
        assert middleware._contains_xss("<img onload='alert(1)'>") is True
        assert middleware._contains_xss("onload=") is True

    def test_contains_xss_onerror(self, middleware):
        """Test onerror event handler detection."""
        assert middleware._contains_xss("<img src=x onerror='alert(1)'>") is True
        assert middleware._contains_xss("onerror=") is True

    def test_contains_xss_iframe(self, middleware):
        """Test iframe XSS detection."""
        assert middleware._contains_xss("<iframe src='evil.html'></iframe>") is True

    def test_contains_xss_object(self, middleware):
        """Test object XSS detection."""
        assert middleware._contains_xss("<object data='evil.swf'></object>") is True

    def test_contains_xss_expression(self, middleware):
        """Test CSS expression detection."""
        assert middleware._contains_xss("expression(alert('xss'))") is True

    def test_contains_xss_import(self, middleware):
        """Test @import CSS detection."""
        assert middleware._contains_xss("@import url('evil.css')") is True

    def test_contains_xss_negative_cases(self, middleware):
        """Test negative cases for XSS."""
        assert middleware._contains_xss("normal text") is False
        assert middleware._contains_xss("javascript is a language") is False
        assert middleware._contains_xss("onload is an event") is False


class TestMaliciousCharacters:
    """Tests for malicious character detection."""

    def test_contains_null_byte(self, middleware):
        """Test null byte detection."""
        assert middleware._contains_malicious_chars("test\x00user") is True

    def test_contains_control_chars(self, middleware):
        """Test control character detection."""
        assert middleware._contains_malicious_chars("test\x01user") is True
        assert middleware._contains_malicious_chars("test\x1fuser") is True

    def test_contains_malicious_chars_negative(self, middleware):
        """Test negative cases for malicious characters."""
        assert middleware._contains_malicious_chars("normal text") is False
        assert middleware._contains_malicious_chars("test\tuser") is False  # Tab is allowed
        assert middleware._contains_malicious_chars("test\nuser") is False  # Newline is allowed
        assert middleware._contains_malicious_chars("test\ruser") is False  # CR is allowed


class TestEmailValidation:
    """Tests for email format validation."""

    def test_valid_email_formats(self, middleware):
        """Test valid email formats."""
        assert middleware._is_valid_email_format("test@example.com") is True
        assert middleware._is_valid_email_format("user.name@example.com") is True
        assert middleware._is_valid_email_format("user+tag@example.co.uk") is True

    def test_invalid_email_formats(self, middleware):
        """Test invalid email formats."""
        assert middleware._is_valid_email_format("invalid-email") is False
        assert middleware._is_valid_email_format("@example.com") is False
        assert middleware._is_valid_email_format("test@") is False
        assert middleware._is_valid_email_format("test@.com") is False

    def test_non_string_email(self, middleware):
        """Test non-string email."""
        assert middleware._is_valid_email_format(123) is False
        assert middleware._is_valid_email_format(None) is False


class TestFormDataType:
    """Tests for form data handling."""

    @pytest.mark.asyncio
    async def test_form_data_validation(self, middleware):
        """Test form data validation."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/auth/login"
        mock_request.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        mock_form_data = MagicMock()
        mock_form_data.__iter__ = lambda self: iter(
            [("username", "testuser"), ("password", "pass123")]
        )
        mock_request.form = AsyncMock(return_value=mock_form_data)

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_form_data_with_xss(self, middleware):
        """Test form data with XSS."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/me"
        mock_request.headers = Headers({"content-type": "application/x-www-form-urlencoded"})

        mock_form_data = MagicMock()
        mock_form_data.__iter__ = lambda self: iter([("bio", "<script>alert('xss')</script>")])
        mock_request.form = AsyncMock(return_value=mock_form_data)

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is False


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_format(self, middleware):
        """Test handling of invalid JSON."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        result = await middleware._validate_request(mock_request)
        assert result["is_valid"] is True  # Should pass with empty data

    @pytest.mark.asyncio
    async def test_exception_in_validation(self, middleware):
        """Test handling of exceptions during validation."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/users/register"
        mock_request.headers = Headers({"content-type": "application/json"})
        mock_request.json = AsyncMock(
            return_value={"username": "test", "email": "test@example.com", "password": "pass"}
        )

        # Mock _validate_registration_data to raise exception
        with patch.object(
            middleware, "_validate_registration_data", side_effect=Exception("Unexpected error")
        ):
            result = await middleware._validate_request(mock_request)
            assert result["is_valid"] is False
            assert "Security validation failed" in result["error_message"]


class TestNonValidationMethods:
    """Tests for methods that don't require validation."""

    @pytest.mark.asyncio
    async def test_options_method_skipped(self, middleware):
        """Test OPTIONS method is skipped."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "OPTIONS"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, middleware.app)
        assert response is not None

    @pytest.mark.asyncio
    async def test_head_method_skipped(self, middleware):
        """Test HEAD method is skipped."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "HEAD"
        mock_request.url.path = "/v1/users"
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, middleware.app)
        assert response is not None
