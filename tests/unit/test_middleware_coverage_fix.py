"""
Coverage fix tests for middleware modules showing 0% coverage.

These tests import modules at the module level to ensure proper coverage tracking.
"""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _reload_module(module_name: str):
    """Reload a module to ensure coverage tracks it."""
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])


# Reload modules to ensure coverage tracking
_reload_module("app.middleware.api_versioning")
_reload_module("app.middleware.profiling")
_reload_module("app.middleware.slo")
_reload_module("app.middleware.db_profiling")

# Import modules at module level for coverage tracking
from app.middleware.api_versioning import API_VERSION, CURRENT_VERSION, APIVersioningMiddleware
from app.middleware.db_profiling import (
    CacheMetrics,
    DBProfilingMiddleware,
    PayloadMetrics,
    QueryMetrics,
    cache_stats_var,
    payload_sizes_var,
    query_timings_var,
)
from app.middleware.profiling import ProfilingMiddleware
from app.middleware.slo import API_SLOS, SLO, SLOMonitor, get_slo_for_request


class TestAPIVersioningMiddlewareCoverage:
    """Test APIVersioningMiddleware for coverage."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        return AsyncMock()

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return APIVersioningMiddleware(mock_app)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/v1/sessions"
        return request

    @pytest.mark.asyncio
    async def test_dispatch_adds_version_headers(self, middleware, mock_request):
        """Test dispatch adds version headers."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "API-Version" in result.headers
        assert "API-Version-Prefix" in result.headers
        assert result.headers["API-Version"] == CURRENT_VERSION
        assert result.headers["API-Version-Prefix"] == API_VERSION

    @pytest.mark.asyncio
    async def test_dispatch_adds_deprecation_headers(self, middleware, mock_request):
        """Test dispatch adds deprecation headers for deprecated endpoints."""
        mock_request.url.path = "/v1/auth/old-endpoint"

        with patch("app.middleware.api_versioning.is_endpoint_deprecated") as mock_deprecated:
            mock_deprecated.return_value = {
                "sunset": "2024-12-31",
                "replacement": "/v1/auth/new-endpoint",
            }
            response = JSONResponse({"status": "ok"})
            call_next = AsyncMock(return_value=response)

            result = await middleware.dispatch(mock_request, call_next)

            assert result.headers.get("Deprecation") == "true"
            assert "Sunset" in result.headers
            assert "Link" in result.headers
            assert "Warning" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_updates_content_type(self, middleware, mock_request):
        """Test dispatch updates content-type header for JSON responses."""
        response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        content_type = result.headers.get("Content-Type", "")
        assert "application/json" in content_type
        assert "version=" in content_type


class TestProfilingMiddlewareCoverage:
    """Test ProfilingMiddleware for coverage."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        return AsyncMock()

    @pytest.fixture
    def enabled_middleware(self, mock_app):
        """Create enabled middleware instance."""
        return ProfilingMiddleware(mock_app, enabled=True, profile_functions=True)

    @pytest.fixture
    def disabled_middleware(self, mock_app):
        """Create disabled middleware instance."""
        return ProfilingMiddleware(mock_app, enabled=False)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/v1/sessions"
        return request

    def test_init_disabled(self, mock_app):
        """Test middleware initialization when disabled."""
        middleware = ProfilingMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False
        assert middleware.profiling_service is None

    def test_init_enabled(self, mock_app):
        """Test middleware initialization when enabled."""
        middleware = ProfilingMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True
        assert middleware.profiling_service is not None

    def test_init_with_memory_tracing(self, mock_app):
        """Test middleware initialization with memory tracing."""
        middleware = ProfilingMiddleware(mock_app, enabled=True, memory_tracing=True)
        assert middleware.enabled is True
        assert middleware.memory_tracing is True

    @pytest.mark.asyncio
    async def test_dispatch_when_disabled(self, disabled_middleware, mock_request):
        """Test dispatch when middleware is disabled."""
        response = MagicMock(spec=Response)
        call_next = AsyncMock(return_value=response)

        result = await disabled_middleware.dispatch(mock_request, call_next)

        assert result == response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_when_enabled(self, enabled_middleware, mock_request):
        """Test dispatch when middleware is enabled."""
        response = MagicMock(spec=Response)
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await enabled_middleware.dispatch(mock_request, call_next)

        assert hasattr(result, "headers")
        assert "X-Request-Duration" in result.headers
        assert result.headers["X-Profiled"] == "true"


class TestSLOCoverage:
    """Test SLO module for coverage."""

    def test_slo_dataclass(self):
        """Test SLO dataclass creation."""
        slo = SLO(
            name="test_slo",
            target_p50=0.1,
            target_p95=0.25,
            target_p99=0.5,
            error_budget=0.999,
            description="Test SLO description",
        )
        assert slo.name == "test_slo"
        assert slo.target_p50 == 0.1
        assert slo.target_p95 == 0.25
        assert slo.target_p99 == 0.5
        assert slo.error_budget == 0.999
        assert slo.description == "Test SLO description"

    def test_get_slo_for_request_auth(self):
        """Test getting SLO for auth endpoints."""
        slo = get_slo_for_request("/v1/auth/login", "POST")
        assert slo.name == "Authentication"

    def test_get_slo_for_request_task_submission(self):
        """Test getting SLO for task submission."""
        slo = get_slo_for_request("/v1/tasks", "POST")
        assert slo.name == "Task Submission"

    def test_get_slo_for_request_data_read(self):
        """Test getting SLO for data read."""
        slo = get_slo_for_request("/v1/sessions/123", "GET")
        assert slo.name == "Data Retrieval"

    def test_get_slo_for_request_default(self):
        """Test getting default SLO."""
        slo = get_slo_for_request("/v1/unknown", "DELETE")
        assert slo.name == "Global API Latency"

    def test_slo_monitor_initialization(self):
        """Test SLOMonitor initialization."""
        monitor = SLOMonitor()
        assert monitor is not None
        assert len(monitor.slos) == 4

    def test_slo_monitor_check_compliance_p99_violation(self, caplog):
        """Test SLO monitor P99 violation detection."""
        import logging

        monitor = SLOMonitor()
        with caplog.at_level(logging.WARNING):
            monitor.check_compliance("auth", 1.0)  # 1 second > 0.5s target
        assert "P99 VIOLATION" in caplog.text

    def test_slo_monitor_check_compliance_p95_warning(self, caplog):
        """Test SLO monitor P95 warning."""
        import logging

        monitor = SLOMonitor()
        with caplog.at_level(logging.INFO):
            monitor.check_compliance("auth", 0.3)  # 0.3s > 0.25s target
        assert "P95 Warning" in caplog.text

    def test_api_slos_defined(self):
        """Test that API_SLOS dict is properly defined."""
        assert "auth" in API_SLOS
        assert "task_submission" in API_SLOS
        assert "data_read" in API_SLOS
        assert "global_default" in API_SLOS


class TestDBProfilingMiddlewareCoverage:
    """Test DBProfilingMiddleware for coverage."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        return AsyncMock()

    @pytest.fixture
    def enabled_middleware(self, mock_app):
        """Create enabled middleware instance."""
        return DBProfilingMiddleware(mock_app, enabled=True)

    @pytest.fixture
    def disabled_middleware(self, mock_app):
        """Create disabled middleware instance."""
        return DBProfilingMiddleware(mock_app, enabled=False)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/v1/sessions"
        request.headers = {}
        return request

    def test_init_disabled(self, mock_app):
        """Test middleware initialization when disabled."""
        middleware = DBProfilingMiddleware(mock_app, enabled=False)
        assert middleware.enabled is False

    def test_init_enabled(self, mock_app):
        """Test middleware initialization when enabled."""
        middleware = DBProfilingMiddleware(mock_app, enabled=True)
        assert middleware.enabled is True
        assert middleware.slow_query_threshold_ms == 100.0
        assert middleware.large_payload_threshold_bytes == 100_000

    def test_init_custom_thresholds(self, mock_app):
        """Test middleware initialization with custom thresholds."""
        middleware = DBProfilingMiddleware(
            mock_app,
            enabled=True,
            slow_query_threshold_ms=50.0,
            large_payload_threshold_bytes=50000,
        )
        assert middleware.slow_query_threshold_ms == 50.0
        assert middleware.large_payload_threshold_bytes == 50000

    @pytest.mark.asyncio
    async def test_dispatch_when_disabled(self, disabled_middleware, mock_request):
        """Test dispatch when middleware is disabled."""
        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        result = await disabled_middleware.dispatch(mock_request, call_next)

        assert result == response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_when_enabled(self, enabled_middleware, mock_request):
        """Test dispatch when middleware is enabled."""
        response = MagicMock()
        response.headers = {"content-length": "100"}
        call_next = AsyncMock(return_value=response)

        result = await enabled_middleware.dispatch(mock_request, call_next)

        assert result == response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_with_content_length(self, enabled_middleware, mock_request):
        """Test dispatch with content-length header."""
        mock_request.headers = {"content-length": "1024"}
        response = MagicMock()
        response.headers = {"content-length": "2048"}
        call_next = AsyncMock(return_value=response)

        result = await enabled_middleware.dispatch(mock_request, call_next)

        assert result == response


class TestDBProfilingDataclasses:
    """Test DB profiling dataclasses for coverage."""

    def test_query_metrics_creation(self):
        """Test QueryMetrics dataclass."""
        metrics = QueryMetrics(
            query_hash="abc123",
            query_text="SELECT * FROM users",
            duration_ms=50.0,
            rows_returned=10,
            endpoint="/v1/users",
        )
        assert metrics.query_hash == "abc123"
        assert metrics.query_text == "SELECT * FROM users"
        assert metrics.duration_ms == 50.0
        assert metrics.rows_returned == 10
        assert metrics.endpoint == "/v1/users"
        assert metrics.timestamp is not None

    def test_payload_metrics_creation(self):
        """Test PayloadMetrics dataclass."""
        metrics = PayloadMetrics(
            endpoint="/v1/sessions", request_size_bytes=1024, response_size_bytes=2048
        )
        assert metrics.endpoint == "/v1/sessions"
        assert metrics.request_size_bytes == 1024
        assert metrics.response_size_bytes == 2048
        assert metrics.timestamp is not None

    def test_cache_metrics_creation(self):
        """Test CacheMetrics dataclass."""
        metrics = CacheMetrics(endpoint="/v1/sessions", hits=10, misses=2, total_lookups=12)
        assert metrics.endpoint == "/v1/sessions"
        assert metrics.hits == 10
        assert metrics.misses == 2
        assert metrics.total_lookups == 12

    def test_cache_metrics_hit_ratio(self):
        """Test CacheMetrics hit ratio calculation."""
        metrics = CacheMetrics(endpoint="/v1/sessions", hits=8, misses=2, total_lookups=10)
        assert metrics.hit_ratio == 0.8

    def test_cache_metrics_hit_ratio_zero_lookups(self):
        """Test CacheMetrics hit ratio with zero lookups."""
        metrics = CacheMetrics(endpoint="/v1/sessions", hits=0, misses=0)
        assert metrics.hit_ratio == 0.0

    def test_context_variables_exist(self):
        """Test that context variables exist."""
        assert query_timings_var is not None
        assert payload_sizes_var is not None
        assert cache_stats_var is not None
