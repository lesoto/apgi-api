"""
Tests for DeprecationMiddleware

Coverage: 18% -> 100% target
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.responses import Response

from app.middleware.deprecation import DeprecationMiddleware


class TestDeprecationMiddleware:
    """Test DeprecationMiddleware functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.deprecated_endpoints = {
            "/v1/deprecated": {"sunset": "2026-01-01", "replacement": "/v2/new"},
            "/v1/sessions/{session_id}": {"sunset": "2026-06-01"},
            "/v1/old": {"replacement": "/v2/modern"},
        }

    def test_init_default(self):
        """Test middleware initialization with defaults."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware.app == self.app
        assert middleware.deprecated_endpoints == {}

    def test_init_with_endpoints(self):
        """Test middleware initialization with deprecated endpoints."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        assert middleware.app == self.app
        assert middleware.deprecated_endpoints == self.deprecated_endpoints

    @pytest.mark.asyncio
    async def test_dispatch_non_deprecated_endpoint(self):
        """Test dispatch for non-deprecated endpoint."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        request = MagicMock()
        request.url.path = "/v1/active"
        response = Response("OK")

        call_next = AsyncMock(return_value=response)
        result = await middleware.dispatch(request, call_next)

        assert result == response
        # Should not add deprecation headers
        assert "Deprecation" not in result.headers
        assert "Sunset" not in result.headers
        assert "Link" not in result.headers
        assert "Warning" not in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_deprecated_endpoint_exact_match(self):
        """Test dispatch for deprecated endpoint with exact match."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        request = MagicMock()
        request.url.path = "/v1/deprecated"
        response = Response("OK")

        call_next = AsyncMock(return_value=response)
        result = await middleware.dispatch(request, call_next)

        assert result == response
        assert result.headers["Deprecation"] == "true"
        assert result.headers["Sunset"] == "2026-01-01"
        assert result.headers["Link"] == '</v2/new>; rel="successor-version"'
        assert "Warning" in result.headers
        assert "Deprecated API endpoint" in result.headers["Warning"]

    @pytest.mark.asyncio
    async def test_dispatch_deprecated_endpoint_pattern_match(self):
        """Test dispatch for deprecated endpoint with pattern match."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        request = MagicMock()
        request.url.path = "/v1/sessions/abc123"
        response = Response("OK")

        call_next = AsyncMock(return_value=response)
        result = await middleware.dispatch(request, call_next)

        assert result == response
        assert result.headers["Deprecation"] == "true"
        assert result.headers["Sunset"] == "2026-06-01"
        assert "Warning" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_deprecated_endpoint_minimal_info(self):
        """Test dispatch for deprecated endpoint with only replacement."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        request = MagicMock()
        request.url.path = "/v1/old"
        response = Response("OK")

        call_next = AsyncMock(return_value=response)
        result = await middleware.dispatch(request, call_next)

        assert result == response
        assert result.headers["Deprecation"] == "true"
        assert result.headers["Link"] == '</v2/modern>; rel="successor-version"'
        assert "Use /v2/modern instead" in result.headers["Warning"]
        # No sunset header since not specified
        assert "Sunset" not in result.headers

    def test_get_deprecation_info_exact_match(self):
        """Test getting deprecation info with exact match."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        info = middleware._get_deprecation_info("/v1/deprecated")
        assert info == {"sunset": "2026-01-01", "replacement": "/v2/new"}

    def test_get_deprecation_info_pattern_match(self):
        """Test getting deprecation info with pattern match."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        info = middleware._get_deprecation_info("/v1/sessions/abc123")
        assert info == {"sunset": "2026-06-01"}

    def test_get_deprecation_info_no_match(self):
        """Test getting deprecation info with no match."""
        middleware = DeprecationMiddleware(self.app, self.deprecated_endpoints)
        info = middleware._get_deprecation_info("/v1/active")
        assert info is None

    def test_get_deprecation_info_empty_endpoints(self):
        """Test getting deprecation info with empty endpoints."""
        middleware = DeprecationMiddleware(self.app, {})
        info = middleware._get_deprecation_info("/v1/any")
        assert info is None

    def test_path_matches_exact(self):
        """Test path matching with exact match."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware._path_matches("/api/test", "/api/test") is True

    def test_path_matches_with_parameters(self):
        """Test path matching with path parameters."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware._path_matches("/api/sessions/123", "/api/sessions/{session_id}") is True

    def test_path_matches_different_lengths(self):
        """Test path matching with different path lengths."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware._path_matches("/api/test", "/api/test/extra") is False

    def test_path_matches_no_match(self):
        """Test path matching with no match."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware._path_matches("/api/test", "/api/other") is False

    def test_path_matches_parameter_at_start(self):
        """Test path matching with parameter at path start."""
        middleware = DeprecationMiddleware(self.app)
        assert middleware._path_matches("/123/items", "/{id}/items") is True

    def test_build_warning_message_minimal(self):
        """Test building warning message with minimal info."""
        middleware = DeprecationMiddleware(self.app)
        message = middleware._build_warning_message("/api/test", {})
        assert message == '299 - "Deprecated API endpoint: /api/test"'

    def test_build_warning_message_with_sunset(self):
        """Test building warning message with sunset date."""
        middleware = DeprecationMiddleware(self.app)
        message = middleware._build_warning_message("/api/test", {"sunset": "2026-01-01"})
        expected = '299 - "Deprecated API endpoint: /api/test" "Sunset date: 2026-01-01"'
        assert message == expected

    def test_build_warning_message_with_replacement(self):
        """Test building warning message with replacement."""
        middleware = DeprecationMiddleware(self.app)
        message = middleware._build_warning_message("/api/test", {"replacement": "/v2/new"})
        expected = '299 - "Deprecated API endpoint: /api/test" "Use /v2/new instead"'
        assert message == expected

    def test_build_warning_message_full(self):
        """Test building warning message with all info."""
        middleware = DeprecationMiddleware(self.app)
        info = {"sunset": "2026-01-01", "replacement": "/v2/new"}
        message = middleware._build_warning_message("/api/test", info)
        expected = '299 - "Deprecated API endpoint: /api/test" "Sunset date: 2026-01-01" "Use /v2/new instead"'
        assert message == expected

    def test_build_warning_message_unicode_path(self):
        """Test building warning message with unicode path."""
        middleware = DeprecationMiddleware(self.app)
        # Test with non-ASCII characters
        message = middleware._build_warning_message("/api/tëst", {})
        assert "Deprecated API endpoint" in message

    def test_build_warning_message_unicode_replacement(self):
        """Test building warning message with unicode replacement."""
        middleware = DeprecationMiddleware(self.app)
        info = {"replacement": "/v2/nëw"}
        message = middleware._build_warning_message("/api/test", info)
        assert "Use" in message

    def test_update_deprecated_endpoints(self):
        """Test updating deprecated endpoints configuration."""
        middleware = DeprecationMiddleware(self.app)
        new_endpoints = {"/new": {"sunset": "2027-01-01"}}
        middleware.update_deprecated_endpoints(new_endpoints)
        assert middleware.deprecated_endpoints == new_endpoints
