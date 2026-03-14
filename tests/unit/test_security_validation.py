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
        scope = {"type": "http", "method": "GET", "path": "/test"}
        receive = AsyncMock()
        send = AsyncMock()

        await disabled_middleware(
            {"type": "lifespan", "asgi": {"sub_type": "startup"}}, receive, send
        )

    @pytest.mark.asyncio
    async def test_dispatch_get_request_valid(self, middleware):
        """Test dispatch with valid GET request."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/auth/login",
            "query_string": b"username=test",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_dispatch_post_request_valid(self, middleware):
        """Test dispatch with valid POST request."""
        scope = {"type": "http", "method": "POST", "path": "/v1/auth/login"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_validate_login_data_valid(self, middleware):
        """Test valid login data validation."""
        data = {"username": "testuser", "email": "test@example.com"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_login_data_missing_username(self, middleware):
        """Test login validation with missing username."""
        data = {"email": "test@example.com"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "Username is required" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_login_data_sql_injection(self, middleware):
        """Test login validation with SQL injection attempt."""
        data = {"username": "admin' OR '1'='1", "email": "test@example.com"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_login_data_malicious_chars(self, middleware):
        """Test login validation with malicious characters."""
        data = {"username": "test\x00user", "email": "test@example.com"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_login_data_too_long(self, middleware):
        """Test login validation with too long username."""
        data = {"username": "a" * 101, "email": "test@example.com"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_login_data_invalid_email(self, middleware):
        """Test login validation with invalid email."""
        data = {"username": "testuser", "email": "invalid-email"}
        result = await middleware._validate_login_data(data)
        assert result["is_valid"] is False
        assert "Invalid email format" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_registration_data_valid(self, middleware):
        """Test valid registration data validation."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePassword123",
        }
        result = await middleware._validate_registration_data(data)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_registration_data_missing_fields(self, middleware):
        """Test registration validation with missing fields."""
        data = {"username": "testuser"}
        result = await middleware._validate_registration_data(data)
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_validate_registration_data_password_too_short(self, middleware):
        """Test registration validation with short password."""
        data = {"username": "testuser", "email": "test@example.com", "password": "short"}
        result = await middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_registration_data_password_too_long(self, middleware):
        """Test registration validation with long password."""
        data = {"username": "testuser", "email": "test@example.com", "password": "a" * 129}
        result = await middleware._validate_registration_data(data)
        assert result["is_valid"] is False
        assert "too long" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_user_profile_data_valid(self, middleware):
        """Test valid user profile data validation."""
        data = {"email": "test@example.com", "name": "Test User"}
        result = await middleware._validate_user_profile_data(data)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_user_profile_data_xss(self, middleware):
        """Test profile validation with XSS attempt."""
        data = {"name": "<script>alert('xss')</script>"}
        result = await middleware._validate_user_profile_data(data)
        assert result["is_valid"] is False
        assert "dangerous content" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_search_data_valid(self, middleware):
        """Test valid search data validation."""
        data = {"search": "test query"}
        result = await middleware._validate_search_data(data)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_search_data_sql_injection(self, middleware):
        """Test search validation with SQL injection."""
        data = {"search": "test' OR '1'='1"}
        result = await middleware._validate_search_data(data)
        assert result["is_valid"] is False
        assert "invalid characters" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_password_data_valid(self, middleware):
        """Test valid password data validation."""
        data = {"password": "SecurePassword123"}
        result = await middleware._validate_password_data(data)
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_password_data_too_short(self, middleware):
        """Test password validation with short password."""
        data = {"password": "short"}
        result = await middleware._validate_password_data(data)
        assert result["is_valid"] is False
        assert "too short" in result["error_message"]

    @pytest.mark.asyncio
    async def test_validate_generic_data_valid(self, middleware):
        """Test valid generic data validation."""
        data = {"field1": "value1", "field2": "value2"}
        result = await middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is True

    @pytest.mark.asyncio
    async def test_validate_generic_data_sql_injection(self, middleware):
        """Test generic validation with SQL injection."""
        data = {"field": "test' OR '1'='1"}
        result = await middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_validate_generic_data_xss(self, middleware):
        """Test generic validation with XSS."""
        data = {"field": "<script>alert('xss')</script>"}
        result = await middleware._validate_generic_data(data, "/test")
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_contains_sql_injection(self, middleware):
        """Test SQL injection detection."""
        assert middleware._contains_sql_injection("admin' OR '1'='1") is True
        assert middleware._contains_sql_injection("UNION SELECT") is True
        assert middleware._contains_sql_injection("normal text") is False

    @pytest.mark.asyncio
    async def test_contains_xss(self, middleware):
        """Test XSS detection."""
        assert middleware._contains_xss("<script>alert('xss')</script>") is True
        assert middleware._contains_xss("javascript:alert('xss')") is True
        assert middleware._contains_xss("normal text") is False

    @pytest.mark.asyncio
    async def test_contains_malicious_chars(self, middleware):
        """Test malicious character detection."""
        assert middleware._contains_malicious_chars("test\x00user") is True
        assert middleware._contains_malicious_chars("normal text") is False

    @pytest.mark.asyncio
    async def test_is_valid_email_format(self, middleware):
        """Test email format validation."""
        assert middleware._is_valid_email_format("test@example.com") is True
        assert middleware._is_valid_email_format("invalid-email") is False
        assert middleware._is_valid_email_format("test@") is False

    @pytest.mark.asyncio
    async def test_validate_request_error_handling(self, middleware):
        """Test request validation error handling."""
        scope = {"type": "http", "method": "POST", "path": "/v1/auth/login"}
        receive = AsyncMock()
        receive.return_value = {"type": "http.request", "body": b"invalid"}
        send = AsyncMock()

        with pytest.raises(HTTPException):
            await middleware(scope, receive, send)

    def test_middleware_initialization_enabled(self, mock_app):
        """Test middleware initialization with enabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True

    def test_middleware_initialization_disabled(self, mock_app):
        """Test middleware initialization with disabled validation."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False
