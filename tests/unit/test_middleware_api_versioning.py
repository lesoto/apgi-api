"""
Tests for API versioning middleware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.middleware.api_versioning import APIVersioningMiddleware


class TestAPIVersioningMiddleware:
    """Test API versioning middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock FastAPI app."""
        app = MagicMock()
        app.routes = []
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Middleware instance."""
        return APIVersioningMiddleware(mock_app)

    def test_initialization(self, middleware):
        """Test middleware initialization."""
        assert middleware.app is not None

    @pytest.mark.asyncio
    async def test_adds_version_headers(self, middleware):
        """Test that middleware adds API version headers to response."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.url.path = "/v1/test"

        # Create a mock response with headers dict
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}

        call_next = AsyncMock(return_value=mock_response)

        response = await middleware.dispatch(request, call_next)

        assert response is not None
        assert "API-Version" in response.headers
        assert "API-Version-Prefix" in response.headers
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_adds_content_type_version_for_json(self, middleware):
        """Test that middleware adds version to Content-Type for JSON responses."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.url.path = "/v1/test"

        # Create a mock response with JSON content-type
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}

        call_next = AsyncMock(return_value=mock_response)

        response = await middleware.dispatch(request, call_next)

        # Content-Type should include version info
        assert "version=" in response.headers.get("Content-Type", "")
