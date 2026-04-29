"""
Tests for security headers middleware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.middleware.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock FastAPI app."""
        app = MagicMock()
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Middleware instance."""
        return SecurityHeadersMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_adds_security_headers(self, middleware):
        """Test middleware adds security headers to response."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert "X-Content-Type-Options" in result.headers
        assert "X-Frame-Options" in result.headers
        assert "X-XSS-Protection" in result.headers

    @pytest.mark.asyncio
    async def test_strict_transport_security(self, middleware):
        """Test HSTS header is added."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert "Strict-Transport-Security" in result.headers

    @pytest.mark.asyncio
    async def test_content_security_policy(self, middleware):
        """Test CSP header is added."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert "Content-Security-Policy" in result.headers

    @pytest.mark.asyncio
    async def test_referrer_policy(self, middleware):
        """Test Referrer-Policy header is added."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert "Referrer-Policy" in result.headers
