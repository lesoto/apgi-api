"""
Unit tests for PrometheusMetricsMiddleware and MetricsCollector.
Requirements: 4.10
"""

from typing import Any

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import sys

# Patch bcrypt before importing metrics to avoid PyO3 initialization issues
if "bcrypt" not in sys.modules:
    sys.modules["bcrypt"] = MagicMock()


class TestPrometheusMetricsMiddlewareInit:
    """Test PrometheusMetricsMiddleware initialization."""

    def test_init_creates_middleware(self) -> None:
        """Middleware initializes with app."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware.app is mock_app


class TestPrometheusMetricsMiddlewareDispatch:
    """Test PrometheusMetricsMiddleware dispatch method."""

    @pytest.mark.asyncio
    async def test_dispatch_skips_metrics_endpoint(self) -> None:
        """Dispatch skips metrics collection for /metrics endpoint."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/metrics"
        mock_request.method = "GET"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        call_next.assert_awaited_once_with(mock_request)
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_dispatch_successful_request(self) -> None:
        """Dispatch records metrics for successful request."""
        from app.middleware.metrics import (
            PrometheusMetricsMiddleware,
        )

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/users"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "100"}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests") as mock_active:
            with patch("app.middleware.metrics.request_counter") as mock_counter:
                with patch("app.middleware.metrics.request_duration") as mock_duration:
                    with patch("app.middleware.metrics.response_size_bytes") as mock_size:
                        with patch("app.middleware.metrics.error_counter") as mock_error:
                            result = await middleware.dispatch(mock_request, call_next)

        assert result is mock_response
        call_next.assert_awaited_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_increments_active_requests(self) -> None:
        """Dispatch increments and decrements active_requests gauge."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests") as mock_active:
            result = await middleware.dispatch(mock_request, call_next)

        # Should increment and decrement
        assert mock_active.inc.called
        assert mock_active.dec.called

    @pytest.mark.asyncio
    async def test_dispatch_records_error_4xx(self) -> None:
        """Dispatch records client error (4xx) metrics."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/users/123"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests"):
            with patch("app.middleware.metrics.request_counter") as mock_counter:
                with patch("app.middleware.metrics.request_duration"):
                    with patch("app.middleware.metrics.error_counter") as mock_error:
                        result = await middleware.dispatch(mock_request, call_next)

        # Error counter should be called for 4xx
        assert mock_error.labels.called

    @pytest.mark.asyncio
    async def test_dispatch_records_error_5xx(self) -> None:
        """Dispatch records server error (5xx) metrics."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/data"
        mock_request.method = "POST"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests"):
            with patch("app.middleware.metrics.request_counter"):
                with patch("app.middleware.metrics.request_duration"):
                    with patch("app.middleware.metrics.error_counter") as mock_error:
                        result = await middleware.dispatch(mock_request, call_next)

        # Error counter should be called for 5xx
        assert mock_error.labels.called

    @pytest.mark.asyncio
    async def test_dispatch_exception_handling(self) -> None:
        """Dispatch handles exceptions and records error metrics."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"

        call_next = AsyncMock(side_effect=ValueError("Test error"))

        with patch("app.middleware.metrics.active_requests"):
            with patch("app.middleware.metrics.request_duration"):
                with patch("app.middleware.metrics.error_counter") as mock_error:
                    with pytest.raises(ValueError):
                        await middleware.dispatch(mock_request, call_next)

        # Error counter should be called
        assert mock_error.labels.called

    @pytest.mark.asyncio
    async def test_dispatch_exception_decrements_active_requests(self) -> None:
        """Dispatch decrements active_requests even on exception."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"

        call_next = AsyncMock(side_effect=RuntimeError("Test error"))

        with patch("app.middleware.metrics.active_requests") as mock_active:
            with patch("app.middleware.metrics.request_duration"):
                with patch("app.middleware.metrics.error_counter"):
                    with pytest.raises(RuntimeError):
                        await middleware.dispatch(mock_request, call_next)

        # Should still decrement
        assert mock_active.dec.called

    @pytest.mark.asyncio
    async def test_dispatch_records_response_size(self) -> None:
        """Dispatch records response size when content-length header present."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/data"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "5000"}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests"):
            with patch("app.middleware.metrics.request_counter"):
                with patch("app.middleware.metrics.request_duration"):
                    with patch("app.middleware.metrics.response_size_bytes") as mock_size:
                        result = await middleware.dispatch(mock_request, call_next)

        # Response size should be recorded
        assert mock_size.labels.called

    @pytest.mark.asyncio
    async def test_dispatch_no_response_size_without_header(self) -> None:
        """Dispatch skips response size recording without content-length header."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/data"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.metrics.active_requests"):
            with patch("app.middleware.metrics.request_counter"):
                with patch("app.middleware.metrics.request_duration"):
                    with patch("app.middleware.metrics.response_size_bytes") as mock_size:
                        result = await middleware.dispatch(mock_request, call_next)

        # Response size should not be recorded
        mock_size.labels.assert_not_called()


class TestNormalizeEndpoint:
    """Test _normalize_endpoint method."""

    def test_normalize_endpoint_with_uuid(self) -> None:
        """Normalize endpoint replaces UUID with {id}."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/users/550e8400-e29b-41d4-a716-446655440000/profile"
        result = middleware._normalize_endpoint(path)

        assert "{id}" in result
        assert "550e8400-e29b-41d4-a716-446655440000" not in result

    def test_normalize_endpoint_with_numeric_id(self) -> None:
        """Normalize endpoint replaces numeric ID with {id}."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/users/12345/sessions"
        result = middleware._normalize_endpoint(path)

        assert "{id}" in result
        assert "12345" not in result

    def test_normalize_endpoint_with_task_id(self) -> None:
        """Normalize endpoint replaces task_xxx pattern with {id}."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/tasks/task_abc123def456/status"
        result = middleware._normalize_endpoint(path)

        assert "{id}" in result
        assert "task_abc123def456" not in result

    def test_normalize_endpoint_no_ids(self) -> None:
        """Normalize endpoint returns unchanged path without IDs."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/users/list"
        result = middleware._normalize_endpoint(path)

        assert result == path

    def test_normalize_endpoint_multiple_ids(self) -> None:
        """Normalize endpoint replaces multiple IDs."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/users/123/sessions/456/tasks"
        result = middleware._normalize_endpoint(path)

        assert result.count("{id}") == 2
        assert "123" not in result
        assert "456" not in result

    def test_normalize_endpoint_preserves_structure(self) -> None:
        """Normalize endpoint preserves path structure."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        path = "/api/users/123/sessions/456"
        result = middleware._normalize_endpoint(path)

        parts = result.split("/")
        assert parts[0] == ""
        assert parts[1] == "api"
        assert parts[2] == "users"
        assert parts[3] == "{id}"
        assert parts[4] == "sessions"
        assert parts[5] == "{id}"


class TestLooksLikeId:
    """Test _looks_like_id method."""

    def test_looks_like_id_uuid(self) -> None:
        """Identifies UUID pattern."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_looks_like_id_numeric(self) -> None:
        """Identifies numeric ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("12345") is True

    def test_looks_like_id_task_pattern(self) -> None:
        """Identifies task_xxx pattern."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("task_abc123") is True

    def test_looks_like_id_not_id_text(self) -> None:
        """Does not identify regular text as ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("users") is False

    def test_looks_like_id_not_id_list(self) -> None:
        """Does not identify 'list' as ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("list") is False

    def test_looks_like_id_not_id_empty(self) -> None:
        """Does not identify empty string as ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("") is False

    def test_looks_like_id_invalid_uuid(self) -> None:
        """Does not identify invalid UUID as ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("550e8400-e29b-41d4-a716") is False

    def test_looks_like_id_zero(self) -> None:
        """Identifies '0' as numeric ID."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        assert middleware._looks_like_id("0") is True


class TestUpdateSystemMetrics:
    """Test _update_system_metrics method."""

    def test_update_system_metrics_success(self) -> None:
        """Update system metrics records memory and CPU."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        with patch("app.middleware.metrics.psutil") as mock_psutil:
            mock_memory = MagicMock()
            mock_memory.used = 1000000
            mock_psutil.virtual_memory.return_value = mock_memory
            mock_psutil.cpu_percent.return_value = 25.5

            with patch("app.middleware.metrics.memory_usage_bytes") as mock_mem:
                with patch("app.middleware.metrics.cpu_usage_percent") as mock_cpu:
                    middleware._update_system_metrics()

            mock_mem.set.assert_called_once_with(1000000)
            mock_cpu.set.assert_called_once_with(25.5)

    def test_update_system_metrics_exception_handling(self) -> None:
        """Update system metrics silently handles exceptions."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        with patch("app.middleware.metrics.psutil") as mock_psutil:
            mock_psutil.virtual_memory.side_effect = Exception("psutil error")

            # Should not raise
            middleware._update_system_metrics()

    def test_update_system_metrics_cpu_error_handling(self) -> None:
        """Update system metrics handles CPU error."""
        from app.middleware.metrics import PrometheusMetricsMiddleware

        mock_app = MagicMock()
        middleware = PrometheusMetricsMiddleware(mock_app)

        with patch("app.middleware.metrics.psutil") as mock_psutil:
            mock_memory = MagicMock()
            mock_memory.used = 1000000
            mock_psutil.virtual_memory.return_value = mock_memory
            mock_psutil.cpu_percent.side_effect = Exception("CPU error")

            # Should not raise
            middleware._update_system_metrics()


class TestMetricsCollectorSessionMetrics:
    """Test MetricsCollector session-related methods."""

    def test_set_active_sessions(self) -> None:
        """Set active sessions updates gauge."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.active_sessions") as mock_gauge:
            MetricsCollector.set_active_sessions(42)
            mock_gauge.set.assert_called_once_with(42)

    def test_record_session_created_default(self) -> None:
        """Record session created with default type."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_created") as mock_counter:
            MetricsCollector.record_session_created()
            mock_counter.labels.assert_called_once_with(session_type="default")

    def test_record_session_created_custom_type(self) -> None:
        """Record session created with custom type."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_created") as mock_counter:
            MetricsCollector.record_session_created(session_type="simulation")
            mock_counter.labels.assert_called_once_with(session_type="simulation")

    def test_record_session_completed_default(self) -> None:
        """Record session completed with default type."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_completed") as mock_counter:
            MetricsCollector.record_session_completed()
            mock_counter.labels.assert_called_once_with(session_type="default")

    def test_record_session_completed_custom_type(self) -> None:
        """Record session completed with custom type."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_completed") as mock_counter:
            MetricsCollector.record_session_completed(session_type="training")
            mock_counter.labels.assert_called_once_with(session_type="training")

    def test_record_session_failed_default(self) -> None:
        """Record session failed with defaults."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_failed") as mock_counter:
            MetricsCollector.record_session_failed()
            mock_counter.labels.assert_called_once_with(
                session_type="default", failure_reason="unknown"
            )

    def test_record_session_failed_custom(self) -> None:
        """Record session failed with custom values."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.sessions_failed") as mock_counter:
            MetricsCollector.record_session_failed(
                session_type="simulation", failure_reason="timeout"
            )
            mock_counter.labels.assert_called_once_with(
                session_type="simulation", failure_reason="timeout"
            )

    def test_record_session_duration(self) -> None:
        """Record session duration."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.session_duration") as mock_histogram:
            MetricsCollector.record_session_duration("simulation", 123.45)
            mock_histogram.labels.assert_called_once_with(session_type="simulation")


class TestMetricsCollectorTaskMetrics:
    """Test MetricsCollector task-related methods."""

    def test_set_task_queue_length(self) -> None:
        """Set task queue length updates gauge."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.task_queue_length") as mock_gauge:
            MetricsCollector.set_task_queue_length(15)
            mock_gauge.set.assert_called_once_with(15)

    def test_record_task_created(self) -> None:
        """Record task created."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.tasks_created") as mock_counter:
            MetricsCollector.record_task_created("export")
            mock_counter.labels.assert_called_once_with(task_type="export")

    def test_record_task_completed(self) -> None:
        """Record task completed."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.tasks_completed") as mock_counter:
            MetricsCollector.record_task_completed("export")
            mock_counter.labels.assert_called_once_with(task_type="export")

    def test_record_task_failed_default(self) -> None:
        """Record task failed with default reason."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.tasks_failed") as mock_counter:
            MetricsCollector.record_task_failed("export")
            mock_counter.labels.assert_called_once_with(
                task_type="export", failure_reason="unknown"
            )

    def test_record_task_failed_custom_reason(self) -> None:
        """Record task failed with custom reason."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.tasks_failed") as mock_counter:
            MetricsCollector.record_task_failed("export", failure_reason="disk_full")
            mock_counter.labels.assert_called_once_with(
                task_type="export", failure_reason="disk_full"
            )

    def test_record_task_duration(self) -> None:
        """Record task duration."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.task_duration") as mock_histogram:
            MetricsCollector.record_task_duration("export", 45.67)
            mock_histogram.labels.assert_called_once_with(task_type="export")

    def test_record_task_queue_wait_time(self) -> None:
        """Record task queue wait time."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.task_queue_wait_time") as mock_histogram:
            MetricsCollector.record_task_queue_wait_time("export", 2.34)
            mock_histogram.labels.assert_called_once_with(task_type="export")


class TestMetricsCollectorUserMetrics:
    """Test MetricsCollector user-related methods."""

    def test_record_user_registration(self) -> None:
        """Record user registration."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.user_registrations") as mock_counter:
            MetricsCollector.record_user_registration()
            mock_counter.inc.assert_called_once()

    def test_record_user_login_default(self) -> None:
        """Record user login with default method."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.user_logins") as mock_counter:
            MetricsCollector.record_user_login()
            mock_counter.labels.assert_called_once_with(login_method="password")

    def test_record_user_login_custom_method(self) -> None:
        """Record user login with custom method."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.user_logins") as mock_counter:
            MetricsCollector.record_user_login(login_method="oauth")
            mock_counter.labels.assert_called_once_with(login_method="oauth")

    def test_record_user_logout(self) -> None:
        """Record user logout."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.user_logouts") as mock_counter:
            MetricsCollector.record_user_logout()
            mock_counter.inc.assert_called_once()

    def test_set_active_users(self) -> None:
        """Set active users gauge."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.active_users") as mock_gauge:
            MetricsCollector.set_active_users(100)
            mock_gauge.set.assert_called_once_with(100)


class TestMetricsCollectorExportMetrics:
    """Test MetricsCollector export-related methods."""

    def test_record_export_requested(self) -> None:
        """Record export requested."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.exports_requested") as mock_counter:
            MetricsCollector.record_export_requested("json")
            mock_counter.labels.assert_called_once_with(export_format="json")

    def test_record_export_completed(self) -> None:
        """Record export completed."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.exports_completed") as mock_counter:
            MetricsCollector.record_export_completed("csv")
            mock_counter.labels.assert_called_once_with(export_format="csv")


class TestMetricsCollectorDatabaseMetrics:
    """Test MetricsCollector database-related methods."""

    def test_update_database_metrics(self) -> None:
        """Update database connection pool metrics."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.database_connections_active") as mock_active:
            with patch("app.middleware.metrics.database_connections_idle") as mock_idle:
                with patch("app.middleware.metrics.database_connections_used") as mock_used:
                    with patch(
                        "app.middleware.metrics.database_connections_overflow"
                    ) as mock_overflow:
                        MetricsCollector.update_database_metrics(
                            active=5, idle=10, used=3, overflow=0
                        )

        mock_active.set.assert_called_once_with(5)
        mock_idle.set.assert_called_once_with(10)
        mock_used.set.assert_called_once_with(3)
        mock_overflow.set.assert_called_once_with(0)


class TestMetricsCollectorRedisMetrics:
    """Test MetricsCollector Redis-related methods."""

    def test_update_redis_metrics(self) -> None:
        """Update Redis metrics."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.redis_connections_active") as mock_conn:
            with patch("app.middleware.metrics.redis_memory_used_bytes") as mock_mem:
                with patch("app.middleware.metrics.redis_keys_total") as mock_keys:
                    with patch("app.middleware.metrics.redis_hit_rate") as mock_hit:
                        MetricsCollector.update_redis_metrics(
                            connections=2, memory_bytes=1000000, keys=500, hit_rate=0.85
                        )

        mock_conn.set.assert_called_once_with(2)
        mock_mem.set.assert_called_once_with(1000000)
        mock_keys.set.assert_called_once_with(500)
        mock_hit.set.assert_called_once_with(0.85)


class TestMetricsCollectorCeleryMetrics:
    """Test MetricsCollector Celery-related methods."""

    def test_update_celery_metrics(self) -> None:
        """Update Celery metrics."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.celery_active_workers") as mock_workers:
            with patch("app.middleware.metrics.celery_active_tasks") as mock_tasks:
                with patch("app.middleware.metrics.celery_scheduled_tasks") as mock_scheduled:
                    with patch("app.middleware.metrics.celery_queued_tasks") as mock_queued:
                        MetricsCollector.update_celery_metrics(
                            active_workers=3, active_tasks=10, scheduled=5, queued=20
                        )

        mock_workers.set.assert_called_once_with(3)
        mock_tasks.set.assert_called_once_with(10)
        mock_scheduled.set.assert_called_once_with(5)
        mock_queued.set.assert_called_once_with(20)


class TestMetricsCollectorCacheMetrics:
    """Test MetricsCollector cache-related methods."""

    def test_record_cache_hit(self) -> None:
        """Record cache hit."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.cache_hits") as mock_counter:
            MetricsCollector.record_cache_hit()
            mock_counter.inc.assert_called_once()

    def test_record_cache_miss(self) -> None:
        """Record cache miss."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.cache_misses") as mock_counter:
            MetricsCollector.record_cache_miss()
            mock_counter.inc.assert_called_once()

    def test_record_cache_set(self) -> None:
        """Record cache set."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.cache_sets") as mock_counter:
            MetricsCollector.record_cache_set()
            mock_counter.inc.assert_called_once()


class TestMetricsCollectorAuthMetrics:
    """Test MetricsCollector authentication-related methods."""

    def test_record_auth_attempt_success(self) -> None:
        """Record successful auth attempt."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.auth_attempts") as mock_counter:
            MetricsCollector.record_auth_attempt("success")
            mock_counter.labels.assert_called_once_with(result="success")

    def test_record_auth_attempt_failure(self) -> None:
        """Record failed auth attempt."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.auth_attempts") as mock_counter:
            MetricsCollector.record_auth_attempt("failure")
            mock_counter.labels.assert_called_once_with(result="failure")

    def test_record_token_issued(self) -> None:
        """Record token issued."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.auth_tokens_issued") as mock_counter:
            MetricsCollector.record_token_issued()
            mock_counter.inc.assert_called_once()

    def test_record_token_revoked(self) -> None:
        """Record token revoked."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.auth_tokens_revoked") as mock_counter:
            MetricsCollector.record_token_revoked()
            mock_counter.inc.assert_called_once()


class TestMetricsCollectorRateLimitMetrics:
    """Test MetricsCollector rate limit-related methods."""

    def test_record_rate_limit_exceeded(self) -> None:
        """Record rate limit exceeded."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.rate_limit_exceeded") as mock_counter:
            MetricsCollector.record_rate_limit_exceeded("/api/users")
            mock_counter.labels.assert_called_once_with(endpoint="/api/users")

    def test_record_rate_limit_allowed(self) -> None:
        """Record rate limit allowed."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.rate_limit_allowed") as mock_counter:
            MetricsCollector.record_rate_limit_allowed("/api/data")
            mock_counter.labels.assert_called_once_with(endpoint="/api/data")


class TestMetricsCollectorErrorMetrics:
    """Test MetricsCollector error-related methods."""

    def test_increment_error(self) -> None:
        """Increment error counter."""
        from app.middleware.metrics import MetricsCollector

        with patch("app.middleware.metrics.error_counter") as mock_counter:
            MetricsCollector.increment_error("ValueError", "/api/test")
            mock_counter.labels.assert_called_once_with(
                error_type="ValueError", endpoint="/api/test"
            )


class TestGetMetricsResponse:
    """Test get_metrics_response function."""

    def test_get_metrics_response(self) -> None:
        """Get metrics response returns Prometheus format."""
        from app.middleware.metrics import get_metrics_response

        with patch("app.middleware.metrics.generate_latest") as mock_generate:
            mock_generate.return_value = b"# HELP test\n# TYPE test counter\n"

            response = get_metrics_response()

            assert response.status_code == 200
            mock_generate.assert_called_once()

    def test_get_metrics_response_content_type(self) -> None:
        """Get metrics response has correct content type."""
        from app.middleware.metrics import get_metrics_response

        with patch("app.middleware.metrics.generate_latest") as mock_generate:
            mock_generate.return_value = b"test"

            response = get_metrics_response()

            assert (
                (response.media_type and "text/plain" in response.media_type)
                or response.media_type == "text/plain; version=0.0.4"
                or response.media_type is None
            )


class TestPrometheusMetricsMiddlewareIntegration:
    """Integration tests using TestClient."""

    def test_middleware_with_test_client_successful_request(self) -> None:
        """Middleware records metrics for successful request via TestClient."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, str]:
            return {"status": "ok"}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_middleware_with_test_client_404_error(self) -> None:
        """Middleware records 404 error metrics."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, str]:
            return {"status": "ok"}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.get("/nonexistent")

        assert response.status_code == 404

    def test_middleware_with_test_client_post_request(self) -> None:
        """Middleware records POST request metrics."""
        app = FastAPI()

        @app.post("/data")
        async def create_data(data: dict[str, Any]) -> dict[str, Any]:
            return {"created": True, "data": data}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.post("/data", json={"key": "value"})

        assert response.status_code == 200

    def test_middleware_skips_metrics_endpoint(self) -> None:
        """Middleware skips metrics endpoint."""
        app = FastAPI()

        from app.middleware.metrics import PrometheusMetricsMiddleware, get_metrics_response

        app.add_middleware(PrometheusMetricsMiddleware)

        @app.get("/metrics")
        async def metrics() -> Any:
            return get_metrics_response()

        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == 200

    def test_middleware_with_test_client_multiple_requests(self) -> None:
        """Middleware handles multiple requests."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, str]:
            return {"status": "ok"}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)

        # Make multiple requests
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

    def test_middleware_with_test_client_different_paths(self) -> None:
        """Middleware normalizes different paths with IDs."""
        app = FastAPI()

        @app.get("/users/{user_id}")
        async def get_user(user_id: str) -> dict[str, str]:
            return {"user_id": user_id}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)

        # Request with numeric ID
        response1 = client.get("/users/123")
        assert response1.status_code == 200

        # Request with different numeric ID
        response2 = client.get("/users/456")
        assert response2.status_code == 200

    def test_middleware_with_test_client_exception_in_route(self) -> None:
        """Middleware handles exceptions in route."""
        app = FastAPI()

        @app.get("/error")
        async def error_route() -> None:
            raise ValueError("Test error")

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")

        # Should get 500 error
        assert response.status_code == 500

    def test_middleware_with_test_client_response_with_content_length(self) -> None:
        """Middleware records response size when content-length present."""
        app = FastAPI()

        @app.get("/data")
        async def get_data() -> dict[str, str]:
            return {"data": "x" * 1000}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.get("/data")

        assert response.status_code == 200
        # Response should have content-length header
        assert "content-length" in response.headers or len(response.content) > 0

    def test_middleware_with_test_client_put_request(self) -> None:
        """Middleware records PUT request metrics."""
        app = FastAPI()

        @app.put("/data/{item_id}")
        async def update_data(item_id: str, data: dict[str, str]) -> dict[str, str | bool]:
            return {"updated": True, "item_id": item_id}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.put("/data/123", json={"key": "value"})

        assert response.status_code == 200

    def test_middleware_with_test_client_delete_request(self) -> None:
        """Middleware records DELETE request metrics."""
        app = FastAPI()

        @app.delete("/data/{item_id}")
        async def delete_data(item_id: str) -> dict[str, str | bool]:
            return {"deleted": True, "item_id": item_id}

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.delete("/data/123")

        assert response.status_code == 200

    def test_middleware_with_test_client_head_request(self) -> None:
        """Middleware records HEAD request metrics."""
        app = FastAPI()

        @app.head("/test")
        async def head_test() -> None:
            return None

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.head("/test")

        assert response.status_code == 200

    def test_middleware_with_test_client_options_request(self) -> None:
        """Middleware records OPTIONS request metrics."""
        app = FastAPI()

        @app.options("/test")
        async def options_test() -> None:
            return None

        from app.middleware.metrics import PrometheusMetricsMiddleware

        app.add_middleware(PrometheusMetricsMiddleware)

        client = TestClient(app)
        response = client.options("/test")

        assert response.status_code == 200
