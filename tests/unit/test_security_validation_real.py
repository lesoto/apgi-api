"""
Comprehensive unit tests for security_validation.py middleware to achieve 100% coverage.
"""

import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException
from app.middleware.security_validation import SecurityValidationMiddleware


class TestSecurityValidationMiddlewareReal:
    """Test the actual security validation middleware implementation."""

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

    def test_initialization_enabled(self, mock_app):
        """Test middleware initialization with validation enabled."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True

    def test_initialization_disabled(self, mock_app):
        """Test middleware initialization with validation disabled."""
        middleware = SecurityValidationMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False

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
        # Should pass through to app
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_get_request_valid(self, middleware):
        """Test GET request passes through validation."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"search=test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_head_request_skipped(self, middleware):
        """Test HEAD request is skipped from validation."""
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
    async def test_dispatch_options_request_skipped(self, middleware):
        """Test OPTIONS request is skipped from validation."""
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
    async def test_dispatch_post_sql_injection_blocked(self, middleware):
        """Test POST request with SQL injection is blocked."""
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
                "body": b'{"username": "admin; DROP TABLE users"}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422
        assert "invalid characters" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dispatch_post_xss_blocked(self, middleware):
        """Test POST request with XSS is blocked."""
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
                "body": b'{"name": "<script>alert("xss")</script>"}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422
        assert "dangerous content" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dispatch_post_malicious_chars_blocked(self, middleware):
        """Test POST request with malicious characters is blocked."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"username": "test\x00user"}', "more_body": False}
        ]
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422
        assert "invalid characters" in str(exc_info.value.detail)

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
    async def test_validate_request_with_query_params(self, middleware):
        """Test validation of query parameters in GET request."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/search",
            "query_string": b"q=test; DROP TABLE users",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 422

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

    @pytest.mark.asyncio
    async def test_validate_request_various_paths(self, middleware):
        """Test validation works for different API paths."""
        paths = ["/api/v1/users", "/api/v1/auth/login", "/api/v1/data", "/health", "/docs"]

        for path in paths:
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
                "query_string": b"test=safe",
                "headers": [],
            }
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)
            send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_put_method(self, middleware):
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
    async def test_validate_request_patch_method(self, middleware):
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
    async def test_validate_request_delete_method(self, middleware):
        """Test DELETE request validation."""
        scope = {
            "type": "http",
            "method": "DELETE",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b'{"id": "123"}', "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_complex_json(self, middleware):
        """Test validation with complex nested JSON."""
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
                "body": b'{"user": {"name": "test", "email": "test@example.com"}, "items": [{"id": 1}]}',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_unicode_content(self, middleware):
        """Test validation with Unicode content."""
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
                "body": '{"name": "tést", "description": "测试"}'.encode("utf-8"),
                "more_body": False,
            }
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_empty_json(self, middleware):
        """Test validation with empty JSON."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [{"type": "http.request", "body": b"{}", "more_body": False}]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_large_payload(self, middleware):
        """Test validation with large payload."""
        large_data = {"data": "x" * 10000}  # Large but safe payload
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": str(large_data).encode(), "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_form_data(self, middleware):
        """Test validation with form data."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {"type": "http.request", "body": b"field1=value1&field2=value2", "more_body": False}
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_multipart_data(self, middleware):
        """Test validation with multipart data."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"multipart/form-data")],
        }
        receive = AsyncMock()
        receive.side_effect = [
            {
                "type": "http.request",
                "body": b'--boundary\r\nContent-Disposition: form-data; name="file"\r\n\r\nfile content',
                "more_body": False,
            }
        ]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_no_content_type(self, middleware):
        """Test validation with no content type header."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [],
        }
        receive = AsyncMock()
        receive.side_effect = [{"type": "http.request", "body": b"some data", "more_body": False}]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_empty_body(self, middleware):
        """Test validation with empty body."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-type", b"application/json")],
        }
        receive = AsyncMock()
        receive.side_effect = [{"type": "http.request", "body": b"", "more_body": False}]
        send = AsyncMock()

        await middleware(scope, receive, send)
        send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_request_multiple_chunks(self, middleware):
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
