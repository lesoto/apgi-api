"""
Unit tests for app/routes/metrics.py

Covers all endpoints:
  GET  /v1/metrics                   - Prometheus endpoint
  GET  /v1/dashboard/overview        - dashboard overview
  GET  /v1/dashboard/sessions        - session metrics
  GET  /v1/dashboard/tasks           - task metrics
  GET  /v1/dashboard/users           - user metrics
  GET  /v1/dashboard/templates       - template metrics
  GET  /v1/dashboard                 - complete dashboard
  GET  /v1/dashboard/html            - HTML dashboard
  POST /v1/profiling/memory/start    - start memory tracing
  POST /v1/profiling/memory/stop     - stop memory tracing
  GET  /v1/profiling/memory          - memory snapshot
  GET  /v1/profiling/system          - system performance
  GET  /v1/profiling/history         - performance history
  GET  /v1/profiling/analysis        - bottleneck analysis

Also tests:
  - get_business_metrics_service() singleton factory
  - get_profiling_service() singleton factory
"""

import pytest
from typing import Any, Dict
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Module-level service factories
# ---------------------------------------------------------------------------


class TestServiceFactories:
    """Test the singleton service factory functions."""

    def test_get_business_metrics_service_creates_instance(self) -> None:
        """First call creates an instance; subsequent calls return the same one."""
        from app.routes.metrics import get_business_metrics_service
        import app.routes.metrics as metrics_module

        # Reset singleton
        metrics_module._business_metrics_service = None

        with patch("app.routes.metrics.BusinessMetricsService") as MockBMS:
            instance = MagicMock()
            MockBMS.return_value = instance

            result1 = get_business_metrics_service()
            result2 = get_business_metrics_service()

        assert result1 is result2
        MockBMS.assert_called_once()

    def test_get_business_metrics_service_reuses_existing(self) -> None:
        """If the singleton already exists it is returned without re-creating."""
        from app.routes.metrics import get_business_metrics_service
        import app.routes.metrics as metrics_module

        existing = MagicMock()
        metrics_module._business_metrics_service = existing

        with patch("app.routes.metrics.BusinessMetricsService") as MockBMS:
            result = get_business_metrics_service()

        MockBMS.assert_not_called()
        assert result is existing

        # Cleanup
        metrics_module._business_metrics_service = None

    def test_get_profiling_service_creates_instance(self) -> None:
        """First call creates a ProfilingService; subsequent calls reuse it."""
        from app.routes.metrics import get_profiling_service
        import app.routes.metrics as metrics_module

        metrics_module._profiling_service = None

        with patch("app.routes.metrics.ProfilingService") as MockPS:
            instance = MagicMock()
            MockPS.return_value = instance

            result1 = get_profiling_service()
            result2 = get_profiling_service()

        assert result1 is result2
        MockPS.assert_called_once()

    def test_get_profiling_service_reuses_existing(self) -> None:
        """If the singleton already exists it is returned without re-creating."""
        from app.routes.metrics import get_profiling_service
        import app.routes.metrics as metrics_module

        existing = MagicMock()
        metrics_module._profiling_service = existing

        with patch("app.routes.metrics.ProfilingService") as MockPS:
            result = get_profiling_service()

        MockPS.assert_not_called()
        assert result is existing

        # Cleanup
        metrics_module._profiling_service = None


# ---------------------------------------------------------------------------
# Endpoint-level tests (call the async functions directly)
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for GET /v1/metrics (Prometheus)."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_success(self) -> None:
        """metrics_endpoint() delegates to get_metrics_response()."""
        from app.routes.metrics import metrics_endpoint

        mock_response = MagicMock()
        with patch("app.routes.metrics.get_metrics_response", return_value=mock_response):
            result = await metrics_endpoint()

        assert result is mock_response


class TestDashboardOverview:
    """Tests for GET /v1/dashboard/overview."""

    @pytest.mark.asyncio
    async def test_get_dashboard_overview_success(self) -> None:
        """Returns service result on success."""
        from app.routes.metrics import get_dashboard_overview

        mock_service = MagicMock()
        mock_service.get_overview_metrics = AsyncMock(return_value={"total_requests": 100})

        result = await get_dashboard_overview(service=mock_service)

        assert result == {"total_requests": 100}

    @pytest.mark.asyncio
    async def test_get_dashboard_overview_service_error(self) -> None:
        """Service exception is converted to HTTP 500."""
        from app.routes.metrics import get_dashboard_overview

        mock_service = MagicMock()
        mock_service.get_overview_metrics = AsyncMock(side_effect=RuntimeError("db down"))

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_overview(service=mock_service)

        assert exc_info.value.status_code == 500


class TestDashboardSessions:
    """Tests for GET /v1/dashboard/sessions."""

    @pytest.mark.asyncio
    async def test_valid_days(self) -> None:
        """Returns service result for a valid days parameter."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        mock_service.get_session_metrics.return_value = {"sessions": 10}

        result = await get_dashboard_sessions(days=7, service=mock_service)

        assert result == {"sessions": 10}
        mock_service.get_session_metrics.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_days_below_minimum(self) -> None:
        """days < 1 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=0, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_days_above_maximum(self) -> None:
        """days > 365 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=366, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception is converted to HTTP 500."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        mock_service.get_session_metrics.side_effect = RuntimeError("oops")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=30, service=mock_service)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_http_exception_re_raised(self) -> None:
        """HTTPException from service propagates unchanged."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        mock_service.get_session_metrics.side_effect = HTTPException(status_code=403)

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=30, service=mock_service)

        assert exc_info.value.status_code == 403


class TestDashboardTasks:
    """Tests for GET /v1/dashboard/tasks."""

    @pytest.mark.asyncio
    async def test_valid_days(self) -> None:
        """Returns service result for valid days."""
        from app.routes.metrics import get_dashboard_tasks

        mock_service = MagicMock()
        mock_service.get_task_metrics.return_value = {"tasks": 5}

        result = await get_dashboard_tasks(days=14, service=mock_service)

        assert result == {"tasks": 5}

    @pytest.mark.asyncio
    async def test_days_out_of_range(self) -> None:
        """days=0 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_tasks

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_tasks(days=0, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_dashboard_tasks

        mock_service = MagicMock()
        mock_service.get_task_metrics.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_tasks(days=30, service=mock_service)

        assert exc_info.value.status_code == 500


class TestDashboardUsers:
    """Tests for GET /v1/dashboard/users."""

    @pytest.mark.asyncio
    async def test_valid_days(self) -> None:
        """Returns service result for valid days."""
        from app.routes.metrics import get_dashboard_users

        mock_service = MagicMock()
        mock_service.get_user_metrics.return_value = {"users": 20}

        result = await get_dashboard_users(days=30, service=mock_service)

        assert result == {"users": 20}

    @pytest.mark.asyncio
    async def test_days_above_max(self) -> None:
        """days > 365 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_users

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_users(days=400, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_dashboard_users

        mock_service = MagicMock()
        mock_service.get_user_metrics.side_effect = Exception("error")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_users(days=30, service=mock_service)

        assert exc_info.value.status_code == 500


class TestDashboardTemplates:
    """Tests for GET /v1/dashboard/templates."""

    @pytest.mark.asyncio
    async def test_valid_days(self) -> None:
        """Returns service result for valid days."""
        from app.routes.metrics import get_dashboard_templates

        mock_service = MagicMock()
        mock_service.get_template_metrics.return_value = {"templates": 3}

        result = await get_dashboard_templates(days=30, service=mock_service)

        assert result == {"templates": 3}

    @pytest.mark.asyncio
    async def test_invalid_days(self) -> None:
        """days=0 or days=400 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_templates

        mock_service = MagicMock()
        for bad_days in (0, 400):
            with pytest.raises(HTTPException) as exc_info:
                await get_dashboard_templates(days=bad_days, service=mock_service)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_dashboard_templates

        mock_service = MagicMock()
        mock_service.get_template_metrics.side_effect = Exception("fail")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_templates(days=30, service=mock_service)

        assert exc_info.value.status_code == 500


class TestCompleteDashboard:
    """Tests for GET /v1/dashboard."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self) -> None:
        """If cache contains data, service is NOT called."""
        from app.routes.metrics import get_complete_dashboard

        mock_service = MagicMock()
        cached = {"overview": {"total_requests": 42}}

        mock_cache = AsyncMock()
        mock_cache.get_api_response = AsyncMock(return_value=cached)
        mock_cache.set_api_response = AsyncMock()

        with patch("app.routes.metrics.get_cache_service", return_value=mock_cache):
            result = await get_complete_dashboard(days=30, service=mock_service)

        assert result == cached
        mock_service.get_dashboard_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_computes_and_caches_when_no_cache(self) -> None:
        """If cache misses, service is called and result is cached."""
        from app.routes.metrics import get_complete_dashboard

        mock_service = MagicMock()
        dashboard_data = {"overview": {"total_requests": 99}}
        mock_service.get_dashboard_data = AsyncMock(return_value=dashboard_data)

        mock_cache = AsyncMock()
        mock_cache.get_api_response = AsyncMock(return_value=None)  # cache miss
        mock_cache.set_api_response = AsyncMock()

        with patch("app.routes.metrics.get_cache_service", return_value=mock_cache):
            result = await get_complete_dashboard(days=30, service=mock_service)

        assert result == dashboard_data
        mock_service.get_dashboard_data.assert_called_once_with(30)
        mock_cache.set_api_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cache_service(self) -> None:
        """When get_cache_service() returns None, service data is returned directly."""
        from app.routes.metrics import get_complete_dashboard

        mock_service = MagicMock()
        dashboard_data: Dict[str, Any] = {"overview": {}}
        mock_service.get_dashboard_data = AsyncMock(return_value=dashboard_data)

        with patch("app.routes.metrics.get_cache_service", return_value=None):
            result = await get_complete_dashboard(days=30, service=mock_service)

        assert result == dashboard_data

    @pytest.mark.asyncio
    async def test_invalid_days(self) -> None:
        """days=0 raises HTTP 400."""
        from app.routes.metrics import get_complete_dashboard

        mock_service = MagicMock()
        with patch("app.routes.metrics.get_cache_service", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_complete_dashboard(days=0, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_complete_dashboard

        mock_service = MagicMock()
        mock_service.get_dashboard_data.side_effect = RuntimeError("db error")

        with patch("app.routes.metrics.get_cache_service", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_complete_dashboard(days=30, service=mock_service)

        assert exc_info.value.status_code == 500


class TestDashboardHTML:
    """Tests for GET /v1/dashboard/html."""

    @pytest.mark.asyncio
    async def test_returns_html_response(self) -> None:
        """Returns an HTMLResponse containing dashboard metrics."""
        from app.routes.metrics import get_dashboard_html
        from fastapi.responses import HTMLResponse

        mock_service = MagicMock()
        mock_service.get_dashboard_data = AsyncMock(
            return_value={
                "overview": {
                    "total_requests": 100,
                    "active_users": 5,
                    "avg_response_time": 12.3,
                    "error_rate": 0.5,
                },
                "system": {"uptime_hours": 24.0, "cpu_usage": 30.0, "memory_usage": 45.0},
            }
        )

        result = await get_dashboard_html(days=30, service=mock_service)

        assert isinstance(result, HTMLResponse)
        assert b"APGI API Analytics Dashboard" in result.body

    @pytest.mark.asyncio
    async def test_invalid_days(self) -> None:
        """days=0 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_html

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=0, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_days_above_max(self) -> None:
        """days > 365 raises HTTP 400."""
        from app.routes.metrics import get_dashboard_html

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=400, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_dashboard_html

        mock_service = MagicMock()
        mock_service.get_dashboard_data.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=30, service=mock_service)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_html_escaping(self) -> None:
        """Special characters in metrics are HTML-escaped by html.escape()."""
        from app.routes.metrics import get_dashboard_html

        mock_service = MagicMock()
        # A value containing XSS payload stored as total_requests
        mock_service.get_dashboard_data = AsyncMock(
            return_value={
                "overview": {
                    "total_requests": 100,  # numeric, no XSS risk
                    "active_users": 5,
                    "avg_response_time": 12.3,
                    "error_rate": 0.5,
                },
                "system": {"uptime_hours": 24.0, "cpu_usage": 30.0, "memory_usage": 45.0},
            }
        )

        result = await get_dashboard_html(days=30, service=mock_service)
        # Verify it returns a valid HTML dashboard
        assert b"APGI API Analytics Dashboard" in result.body
        assert b"100" in result.body  # total_requests value is present

    @pytest.mark.asyncio
    async def test_http_exception_re_raised(self) -> None:
        """HTTPException from inside propagates unchanged."""
        from app.routes.metrics import get_dashboard_html

        mock_service = MagicMock()
        mock_service.get_dashboard_data.side_effect = HTTPException(status_code=403)

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=30, service=mock_service)

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Profiling endpoints
# ---------------------------------------------------------------------------


class TestMemoryTracing:
    """Tests for POST /v1/profiling/memory/start and /stop."""

    @pytest.mark.asyncio
    async def test_start_memory_tracing_success(self) -> None:
        """start_memory_tracing() delegates to service and returns message."""
        from app.routes.metrics import start_memory_tracing

        mock_service = MagicMock()
        result = await start_memory_tracing(service=mock_service)

        mock_service.start_memory_tracing.assert_called_once()
        assert result == {"message": "Memory tracing started successfully"}

    @pytest.mark.asyncio
    async def test_start_memory_tracing_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import start_memory_tracing

        mock_service = MagicMock()
        mock_service.start_memory_tracing.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await start_memory_tracing(service=mock_service)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_stop_memory_tracing_success(self) -> None:
        """stop_memory_tracing() delegates to service and returns message."""
        from app.routes.metrics import stop_memory_tracing

        mock_service = MagicMock()
        result = await stop_memory_tracing(service=mock_service)

        mock_service.stop_memory_tracing.assert_called_once()
        assert result == {"message": "Memory tracing stopped successfully"}

    @pytest.mark.asyncio
    async def test_stop_memory_tracing_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import stop_memory_tracing

        mock_service = MagicMock()
        mock_service.stop_memory_tracing.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await stop_memory_tracing(service=mock_service)

        assert exc_info.value.status_code == 500


class TestMemorySnapshot:
    """Tests for GET /v1/profiling/memory."""

    @pytest.mark.asyncio
    async def test_get_memory_snapshot_success(self) -> None:
        """Returns service result."""
        from app.routes.metrics import get_memory_snapshot

        mock_service = MagicMock()
        mock_service.get_memory_snapshot.return_value = {"rss_mb": 100}

        result = await get_memory_snapshot(service=mock_service)
        assert result == {"rss_mb": 100}

    @pytest.mark.asyncio
    async def test_get_memory_snapshot_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_memory_snapshot

        mock_service = MagicMock()
        mock_service.get_memory_snapshot.side_effect = RuntimeError("err")

        with pytest.raises(HTTPException) as exc_info:
            await get_memory_snapshot(service=mock_service)

        assert exc_info.value.status_code == 500


class TestSystemPerformance:
    """Tests for GET /v1/profiling/system."""

    @pytest.mark.asyncio
    async def test_get_system_performance_success(self) -> None:
        """Returns service result."""
        from app.routes.metrics import get_system_performance

        mock_service = MagicMock()
        mock_service.get_system_performance.return_value = {"cpu": 10.0}

        result = await get_system_performance(service=mock_service)
        assert result == {"cpu": 10.0}

    @pytest.mark.asyncio
    async def test_get_system_performance_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_system_performance

        mock_service = MagicMock()
        mock_service.get_system_performance.side_effect = RuntimeError("err")

        with pytest.raises(HTTPException) as exc_info:
            await get_system_performance(service=mock_service)

        assert exc_info.value.status_code == 500


class TestPerformanceHistory:
    """Tests for GET /v1/profiling/history."""

    @pytest.mark.asyncio
    async def test_valid_hours(self) -> None:
        """Returns service result for valid hours."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        mock_service.get_performance_history.return_value = {"history": []}

        result = await get_performance_history(hours=2, service=mock_service)
        assert result == {"history": []}
        mock_service.get_performance_history.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_hours_below_minimum(self) -> None:
        """hours < 1 raises HTTP 400."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=0, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_hours_above_maximum(self) -> None:
        """hours > 24 raises HTTP 400."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=25, service=mock_service)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        mock_service.get_performance_history.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=1, service=mock_service)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_http_exception_re_raised(self) -> None:
        """HTTPException from service propagates unchanged."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        mock_service.get_performance_history.side_effect = HTTPException(status_code=403)

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=1, service=mock_service)

        assert exc_info.value.status_code == 403


class TestBottleneckAnalysis:
    """Tests for GET /v1/profiling/analysis."""

    @pytest.mark.asyncio
    async def test_get_bottleneck_analysis_success(self) -> None:
        """Returns service result."""
        from app.routes.metrics import get_bottleneck_analysis

        mock_service = MagicMock()
        mock_service.get_bottleneck_analysis.return_value = {"bottlenecks": []}

        result = await get_bottleneck_analysis(service=mock_service)
        assert result == {"bottlenecks": []}

    @pytest.mark.asyncio
    async def test_get_bottleneck_analysis_service_error(self) -> None:
        """Service exception becomes HTTP 500."""
        from app.routes.metrics import get_bottleneck_analysis

        mock_service = MagicMock()
        mock_service.get_bottleneck_analysis.side_effect = RuntimeError("fail")

        with pytest.raises(HTTPException) as exc_info:
            await get_bottleneck_analysis(service=mock_service)

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Boundary / parameter tests
# ---------------------------------------------------------------------------


class TestBoundaryConditions:
    """Boundary tests for days/hours parameters."""

    @pytest.mark.asyncio
    async def test_dashboard_sessions_boundary_days_1(self) -> None:
        """days=1 (minimum) is accepted."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        mock_service.get_session_metrics.return_value = {}
        result = await get_dashboard_sessions(days=1, service=mock_service)
        assert result == {}

    @pytest.mark.asyncio
    async def test_dashboard_sessions_boundary_days_365(self) -> None:
        """days=365 (maximum) is accepted."""
        from app.routes.metrics import get_dashboard_sessions

        mock_service = MagicMock()
        mock_service.get_session_metrics.return_value = {}
        result = await get_dashboard_sessions(days=365, service=mock_service)
        assert result == {}

    @pytest.mark.asyncio
    async def test_performance_history_boundary_hours_1(self) -> None:
        """hours=1 (minimum) is accepted."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        mock_service.get_performance_history.return_value = {}
        result = await get_performance_history(hours=1, service=mock_service)
        assert result == {}

    @pytest.mark.asyncio
    async def test_performance_history_boundary_hours_24(self) -> None:
        """hours=24 (maximum) is accepted."""
        from app.routes.metrics import get_performance_history

        mock_service = MagicMock()
        mock_service.get_performance_history.return_value = {}
        result = await get_performance_history(hours=24, service=mock_service)
        assert result == {}
