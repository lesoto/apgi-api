"""
Additional tests for request_size_limit middleware to achieve 100% coverage.

Tests edge cases and uncovered lines:
- Lines 55->65, 59, 62-63: Content-length parsing edge cases
- Lines 80: Disabled middleware path
- Lines 88->119: Body reading path
- Lines 92-115: Body size check
- Lines 124-157: Exception handling in body check
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from starlette.responses import Response
from starlette.testclient import TestClient

from app.middleware.request_size_limit import RequestSizeLimitMiddleware


def _configure_fastapi_app(app: FastAPI) -> None:
    if not hasattr(app, "response_class"):
        app.response_class = Response

    if not hasattr(app, "test_request_context"):
        class _FastAPITestRequestContext:
            def push(self) -> None:
                return None

            def pop(self) -> None:
                return None

            def __enter__(self) -> "_FastAPITestRequestContext":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        app.test_request_context = lambda *args, **kwargs: _FastAPITestRequestContext()


class TestContentLengthEdgeCases:
    """Test content-length header parsing edge cases."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with middleware."""
        app = FastAPI()
        _configure_fastapi_app(app)
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=1)

        @app.post("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_zero_content_length(self, app: FastAPI) -> None:
        """Test request with zero content-length (should skip check)."""
        client = TestClient(app)

        response = client.post(
            "/test",
            headers={"Content-Length": "0"},
            content=b"",
        )
        # Should not be rejected for size
        assert response.status_code != 413

    def test_invalid_content_length_value(self, app: FastAPI) -> None:
        """Test request with invalid content-length value."""
        client = TestClient(app)

        # Send with invalid content-length that can't be parsed
        response = client.post(
            "/test",
            headers={"Content-Length": "invalid"},
            content=b"small body",
        )
        # Should proceed to check body
        assert response.status_code != 413

    def test_content_length_exactly_at_limit(self, app: FastAPI) -> None:
        """Test request with content-length exactly at limit."""
        client = TestClient(app)

        # 1MB = 1048576 bytes
        max_bytes = 1 * 1024 * 1024

        response = client.post(
            "/test",
            headers={"Content-Length": str(max_bytes)},
            content=b"x" * max_bytes,
        )
        # Should be allowed
        assert response.status_code != 413


class TestDisabledMiddleware:
    """Test middleware when disabled."""

    @pytest.fixture
    def disabled_app(self) -> FastAPI:
        """Create test app with disabled middleware."""
        app = FastAPI()
        _configure_fastapi_app(app)
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=1, enabled=False)

        @app.post("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_disabled_middleware_allows_large_request(self, disabled_app: FastAPI) -> None:
        """Test that disabled middleware allows large requests."""
        client = TestClient(disabled_app)

        # Send 2MB body
        large_body = b"x" * (2 * 1024 * 1024)

        response = client.post("/test", content=large_body)
        # Should be allowed because middleware is disabled
        assert response.status_code != 413


class TestBodySizeCheck:
    """Test body size checking paths."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with middleware."""
        app = FastAPI()
        _configure_fastapi_app(app)
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=1)

        @app.post("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_body_size_exceeds_limit(self, app: FastAPI) -> None:
        """Test request body exceeding limit."""
        client = TestClient(app)

        # Send 2MB body
        large_body = b"x" * (2 * 1024 * 1024 + 1)

        response = client.post("/test", content=large_body)
        assert response.status_code == 413
        assert "REQUEST_TOO_LARGE" in response.text

    def test_body_size_within_limit(self, app: FastAPI) -> None:
        """Test request body within limit."""
        client = TestClient(app)

        # Send small body
        small_body = b"small content"

        response = client.post("/test", content=small_body)
        # Should be allowed
        assert response.status_code != 413

    def test_body_size_exactly_at_limit(self, app: FastAPI) -> None:
        """Test request body exactly at limit."""
        client = TestClient(app)

        # Send exactly 1MB
        max_bytes = 1 * 1024 * 1024
        body = b"x" * max_bytes

        response = client.post("/test", content=body)
        # Should be allowed
        assert response.status_code != 413


class TestShouldCheckSizeMethod:
    """Test _should_check_size method directly."""

    @pytest.fixture
    def middleware(self) -> RequestSizeLimitMiddleware:
        """Create middleware instance."""
        app = MagicMock()
        return RequestSizeLimitMiddleware(app, max_size_mb=1)

    def test_should_check_size_get_request(self, middleware: RequestSizeLimitMiddleware) -> None:
        """Test GET requests are skipped."""
        request = MagicMock()
        request.method = "GET"

        result = middleware._should_check_size(request)
        assert result is False

    def test_should_check_size_head_request(self, middleware: RequestSizeLimitMiddleware) -> None:
        """Test HEAD requests are skipped."""
        request = MagicMock()
        request.method = "HEAD"

        result = middleware._should_check_size(request)
        assert result is False

    def test_should_check_size_options_request(
        self, middleware: RequestSizeLimitMiddleware
    ) -> None:
        """Test OPTIONS requests are skipped."""
        request = MagicMock()
        request.method = "OPTIONS"

        result = middleware._should_check_size(request)
        assert result is False

    def test_should_check_size_delete_request(self, middleware: RequestSizeLimitMiddleware) -> None:
        """Test DELETE requests are skipped."""
        request = MagicMock()
        request.method = "DELETE"

        result = middleware._should_check_size(request)
        assert result is False

    def test_should_check_size_post_request(self, middleware: RequestSizeLimitMiddleware) -> None:
        """Test POST requests are checked."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {}

        result = middleware._should_check_size(request)
        assert result is True

    def test_should_check_size_large_content_length(
        self, middleware: RequestSizeLimitMiddleware
    ) -> None:
        """Test large content-length causes immediate check/rejection."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {"content-length": str(2 * 1024 * 1024)}  # 2MB

        result = middleware._should_check_size(request)
        # Should return True to trigger rejection
        assert result is True

    def test_should_check_size_zero_content_length(
        self, middleware: RequestSizeLimitMiddleware
    ) -> None:
        """Test zero content-length skips check."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {"content-length": "0"}

        result = middleware._should_check_size(request)
        assert result is False

    def test_should_check_size_invalid_content_length(
        self, middleware: RequestSizeLimitMiddleware
    ) -> None:
        """Test invalid content-length proceeds to check."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {"content-length": "invalid"}

        result = middleware._should_check_size(request)
        # Should proceed to stream check
        assert result is True

    def test_should_check_size_no_content_length(
        self, middleware: RequestSizeLimitMiddleware
    ) -> None:
        """Test no content-length header proceeds to check."""
        request = MagicMock()
        request.method = "POST"
        request.headers = {}

        result = middleware._should_check_size(request)
        # Should proceed to stream check
        assert result is True


class TestResponseStructure:
    """Test error response structure."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with middleware."""
        app = FastAPI()
        _configure_fastapi_app(app)
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=1)

        @app.post("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_error_response_content_length(self, app: FastAPI) -> None:
        """Test error response for content-length rejection."""
        client = TestClient(app)

        response = client.post(
            "/test",
            headers={"Content-Length": str(10 * 1024 * 1024)},  # 10MB
        )

        assert response.status_code == 413
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "REQUEST_TOO_LARGE"
        assert "message" in data["error"]
        assert "timestamp" in data["error"]
        assert "details" in data["error"]
        assert "max_size_mb" in data["error"]["details"]
        assert "actual_size_bytes" in data["error"]["details"]

    def test_error_response_body_rejection(self, app: FastAPI) -> None:
        """Test error response for body size rejection."""
        client = TestClient(app)

        large_body = b"x" * (2 * 1024 * 1024)
        response = client.post("/test", content=large_body)

        assert response.status_code == 413
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "REQUEST_TOO_LARGE"
        assert "details" in data["error"]


class TestMiddlewareInitialization:
    """Test middleware initialization."""

    def test_default_max_size(self) -> None:
        """Test default max size is 10MB."""
        app = MagicMock()
        middleware = RequestSizeLimitMiddleware(app)

        assert middleware.max_size_mb == 10
        assert middleware.max_size_bytes == 10 * 1024 * 1024

    def test_custom_max_size(self) -> None:
        """Test custom max size configuration."""
        app = MagicMock()
        middleware = RequestSizeLimitMiddleware(app, max_size_mb=5)

        assert middleware.max_size_mb == 5
        assert middleware.max_size_bytes == 5 * 1024 * 1024

    def test_enabled_by_default(self) -> None:
        """Test middleware is enabled by default."""
        app = MagicMock()
        middleware = RequestSizeLimitMiddleware(app)

        assert middleware.enabled is True

    def test_explicit_disabled(self) -> None:
        """Test middleware can be explicitly disabled."""
        app = MagicMock()
        middleware = RequestSizeLimitMiddleware(app, enabled=False)

        assert middleware.enabled is False


class TestHttpMethodsSkipping:
    """Test that certain HTTP methods skip size checking."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with middleware."""
        app = FastAPI()
        _configure_fastapi_app(app)
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=1)

        @app.get("/test")
        async def get_endpoint() -> dict[str, str]:
            return {"method": "GET"}

        @app.head("/test")
        async def head_endpoint() -> dict[str, str]:
            return {"method": "HEAD"}

        @app.options("/test")
        async def options_endpoint() -> dict[str, str]:
            return {"method": "OPTIONS"}

        @app.delete("/test")
        async def delete_endpoint() -> dict[str, str]:
            return {"method": "DELETE"}

        @app.post("/test")
        async def post_endpoint() -> dict[str, str]:
            return {"method": "POST"}

        return app

    def test_get_skips_size_check(self, app: FastAPI) -> None:
        """Test GET requests skip size check."""
        client = TestClient(app)
        response = client.get("/test")
        # Should succeed
        assert response.status_code == 200

    def test_head_skips_size_check(self, app: FastAPI) -> None:
        """Test HEAD requests skip size check."""
        client = TestClient(app)
        response = client.head("/test")
        # Should succeed (HEAD returns no body)
        assert response.status_code == 200

    def test_options_skips_size_check(self, app: FastAPI) -> None:
        """Test OPTIONS requests skip size check."""
        client = TestClient(app)
        response = client.options("/test")
        # Should succeed
        assert response.status_code == 200

    def test_delete_skips_size_check(self, app: FastAPI) -> None:
        """Test DELETE requests skip size check."""
        client = TestClient(app)
        response = client.delete("/test")
        # Should succeed
        assert response.status_code == 200

    def test_post_checks_size(self, app: FastAPI) -> None:
        """Test POST requests check size."""
        client = TestClient(app)

        # Large body should be rejected
        large_body = b"x" * (2 * 1024 * 1024)
        response = client.post("/test", content=large_body)
        assert response.status_code == 413
