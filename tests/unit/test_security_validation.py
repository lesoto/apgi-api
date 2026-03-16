"""
Unit tests for security validation middleware.
"""

import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException
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
            "password": "SecurePassword123",
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
                "body": b'{"username": "admin; DROP TABLE users"}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        # BaseHTTPMiddleware handles HTTPException and converts it to a response
        await middleware(scope, receive, send)

        # Check if it sent a 422 response
        # In BaseHTTPMiddleware, exceptions might be caught and returned as 500 or just raised depending on setup.
        # But we want to see if our middleware logic is triggered.
        # If it raises HTTPException, BaseHTTPMiddleware might catch it.
        # Let's check if 'send' was called with 422
        calls = [
            call[0][0]
            for call in send.call_args_list
            if call[0][0]["type"] == "http.response.start"
        ]
        assert any(c["status"] == 422 for c in calls)

    def test_middleware_initialization_enabled(self, mock_app):
        """Test middleware initialization with enabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True

    def test_middleware_initialization_disabled(self, mock_app):
        """Test middleware initialization with disabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False
