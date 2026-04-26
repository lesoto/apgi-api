"""
Unit tests for app/middleware/api_versioning.py

Tests the APIVersioningMiddleware that adds semantic versioning headers to responses.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@pytest.fixture
def mock_app() -> AsyncMock:
    """Create a mock ASGI app."""
    return AsyncMock()


@pytest.fixture
def middleware(mock_app: AsyncMock) -> Any:
    """Create APIVersioningMiddleware instance."""
    from app.middleware.api_versioning import APIVersioningMiddleware

    return APIVersioningMiddleware(mock_app)


@pytest.fixture
def mock_request() -> MagicMock:
    """Create a mock request."""
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = "/v1/sessions"
    return request


class TestAPIVersioningMiddlewareInit:
    """Test middleware initialization."""

    def test_init_creates_middleware(self, mock_app: AsyncMock) -> None:
        """Middleware can be initialized with an app."""
        from app.middleware.api_versioning import APIVersioningMiddleware

        mw = APIVersioningMiddleware(mock_app)
        assert mw.app == mock_app


class TestAPIVersioningMiddlewareDispatch:
    """Test middleware dispatch and header injection."""

    @pytest.mark.asyncio
    async def test_dispatch_adds_version_headers(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch adds API-Version and API-Version-Prefix headers."""
        response = JSONResponse({"status": "ok"})
        middleware.app = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, middleware.app)

        assert "API-Version" in result.headers
        assert "API-Version-Prefix" in result.headers
        assert result.headers["API-Version-Prefix"] == "v1"

    @pytest.mark.asyncio
    async def test_dispatch_calls_next_middleware(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch calls the next middleware/handler."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_preserves_response_body(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch preserves the response body."""
        response_data = {"status": "ok", "data": [1, 2, 3]}
        response = JSONResponse(response_data)
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Response body should be preserved
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_preserves_status_code(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch preserves the response status code."""
        response = JSONResponse({"error": "not found"}, status_code=404)
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_dispatch_with_non_json_response(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch handles non-JSON responses."""
        response = Response(content="plain text", media_type="text/plain")
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "API-Version" in result.headers
        # Starlette automatically adds charset=utf-8 to text/plain
        assert "text/plain" in result.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_dispatch_with_json_response_updates_content_type(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch updates Content-Type header for JSON responses."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Content-Type should include version
        content_type = result.headers.get("content-type", "")
        assert "application/json" in content_type
        assert "version=" in content_type


class TestAPIVersioningMiddlewareDeprecation:
    """Test deprecation header injection."""

    @pytest.mark.asyncio
    async def test_dispatch_no_deprecation_for_active_endpoint(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch does not add deprecation headers for active endpoints."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.api_versioning.is_endpoint_deprecated", return_value=None):
            result = await middleware.dispatch(mock_request, call_next)

            assert "Deprecation" not in result.headers
            assert "Sunset" not in result.headers
            assert "Link" not in result.headers
            assert "Warning" not in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_adds_deprecation_headers_for_deprecated_endpoint(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch adds deprecation headers for deprecated endpoints."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        deprecation_info = {"sunset": "2026-01-01", "replacement": "/v2/sessions"}

        with patch(
            "app.middleware.api_versioning.is_endpoint_deprecated", return_value=deprecation_info
        ):
            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("Deprecation") == "true"
            assert result.headers.get("Sunset") == "2026-01-01"
            assert "successor-version" in result.headers.get("Link", "")
            assert "/v2/sessions" in result.headers.get("Link", "")
            assert "Warning" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_deprecation_without_sunset(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch handles deprecation info without sunset date."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        deprecation_info = {"replacement": "/v2/sessions"}

        with patch(
            "app.middleware.api_versioning.is_endpoint_deprecated", return_value=deprecation_info
        ):
            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("Deprecation") == "true"
            assert "Sunset" not in result.headers
            assert "successor-version" in result.headers.get("Link", "")

    @pytest.mark.asyncio
    async def test_dispatch_deprecation_without_replacement(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch handles deprecation info without replacement."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        deprecation_info = {"sunset": "2026-01-01"}

        with patch(
            "app.middleware.api_versioning.is_endpoint_deprecated", return_value=deprecation_info
        ):
            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("Deprecation") == "true"
            assert result.headers.get("Sunset") == "2026-01-01"
            assert "Link" not in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_deprecation_warning_includes_sunset(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch deprecation warning includes sunset date."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        deprecation_info = {"sunset": "2026-06-15"}

        with patch(
            "app.middleware.api_versioning.is_endpoint_deprecated", return_value=deprecation_info
        ):
            result = await middleware.dispatch(mock_request, call_next)

            warning = result.headers.get("Warning", "")
            assert "2026-06-15" in warning
            assert "deprecated" in warning.lower()


class TestAPIVersioningMiddlewareVersionHeaders:
    """Test version header values."""

    @pytest.mark.asyncio
    async def test_dispatch_version_header_from_env(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch uses CURRENT_VERSION from environment."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.api_versioning.CURRENT_VERSION", "2.5.3"):
            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("API-Version") == "2.5.3"

    @pytest.mark.asyncio
    async def test_dispatch_version_prefix_from_env(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch uses API_VERSION from environment."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.api_versioning.API_VERSION", "v2"):
            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("API-Version-Prefix") == "v2"

    @pytest.mark.asyncio
    async def test_dispatch_json_content_type_includes_version(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch JSON Content-Type header includes version."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.api_versioning.CURRENT_VERSION", "1.5.0"):
            result = await middleware.dispatch(mock_request, call_next)

            content_type = result.headers.get("content-type", "")
            assert "version=1.5.0" in content_type


class TestAPIVersioningMiddlewareEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_response(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch handles empty response."""
        response = Response(content="")
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "API-Version" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_with_different_paths(self, middleware: Any) -> None:
        """Dispatch works with different request paths."""
        paths = ["/v1/sessions", "/v1/tasks", "/health", "/v2/users"]

        for path in paths:
            request = MagicMock(spec=Request)
            request.url = MagicMock()
            request.url.path = path

            response = JSONResponse({"status": "ok"})
            call_next = AsyncMock(return_value=response)

            result = await middleware.dispatch(request, call_next)

            assert "API-Version" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_with_existing_headers(
        self, middleware: Any, mock_request: MagicMock
    ) -> None:
        """Dispatch preserves existing response headers."""
        response = JSONResponse({"status": "ok"})
        response.headers["X-Custom-Header"] = "custom-value"
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers.get("X-Custom-Header") == "custom-value"
        assert "API-Version" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_multiple_calls_independent(self, middleware: Any) -> None:
        """Multiple dispatch calls are independent."""
        request1 = MagicMock(spec=Request)
        request1.url = MagicMock()
        request1.url.path = "/v1/sessions"

        request2 = MagicMock(spec=Request)
        request2.url = MagicMock()
        request2.url.path = "/v1/tasks"

        response1 = JSONResponse({"status": "ok"})
        response2 = JSONResponse({"status": "ok"})

        call_next1 = AsyncMock(return_value=response1)
        call_next2 = AsyncMock(return_value=response2)

        result1 = await middleware.dispatch(request1, call_next1)
        result2 = await middleware.dispatch(request2, call_next2)

        assert "API-Version" in result1.headers
        assert "API-Version" in result2.headers
        call_next1.assert_called_once()
        call_next2.assert_called_once()
