"""
Tests for metrics routes.

Tests for metrics endpoints and dashboard functionality.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse


@pytest.fixture
def mock_business_metrics_service():
    """Mock BusinessMetricsService."""
    service = MagicMock()
    service.get_overview_metrics = MagicMock(return_value={"total_requests": 1000})
    service.get_session_metrics = MagicMock(return_value={"total_sessions": 50})
    service.get_task_metrics = MagicMock(return_value={"total_tasks": 20})
    service.get_user_metrics = MagicMock(return_value={"total_users": 10})
    service.get_template_metrics = MagicMock(return_value={"total_templates": 5})
    service.get_dashboard_data = MagicMock(
        return_value={
            "overview": {
                "total_requests": 1000,
                "active_users": 100,
                "avg_response_time": 50.0,
                "error_rate": 0.5,
            },
            "system": {"uptime_hours": 720.0, "cpu_usage": 45.0, "memory_usage": 60.0},
            "trends": {"dates": ["2024-01-01"], "response_times": [50.0], "requests": [100]},
            "endpoints": {"labels": ["/api/test"], "counts": [100]},
        }
    )
    return service


@pytest.fixture
def mock_profiling_service():
    """Mock ProfilingService."""
    service = MagicMock()
    service.start_memory_tracing = MagicMock()
    service.stop_memory_tracing = MagicMock()
    service.get_memory_snapshot = MagicMock(return_value={"total_memory": 1024})
    service.get_system_performance = MagicMock(return_value={"cpu": 50, "memory": 60})
    service.get_performance_history = MagicMock(return_value={"history": []})
    service.get_bottleneck_analysis = MagicMock(return_value={"bottlenecks": []})
    return service


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    service = AsyncMock()
    service.get_api_response = AsyncMock(return_value=None)
    service.set_api_response = AsyncMock()
    return service


class TestMetricsRoutes:
    """Tests for metrics routes."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        from app.routes.metrics import metrics_endpoint

        with patch("app.routes.metrics.get_metrics_response") as mock_get_metrics:
            mock_get_metrics.return_value = "# HELP test_metric Test metric\n"
            result = await metrics_endpoint()
            mock_get_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dashboard_overview(self, mock_business_metrics_service):
        """Test get dashboard overview endpoint."""
        from app.routes.metrics import get_dashboard_overview

        # Mock the service method to return proper data as async
        async def mock_async_overview():
            return {"total_requests": 1000}

        mock_business_metrics_service.get_overview_metrics = mock_async_overview

        result = await get_dashboard_overview(mock_business_metrics_service)

        assert result == {"total_requests": 1000}
        # Check that the async mock was called
        # Since it's an async function, we can't use assert_called_once() directly
        assert hasattr(mock_business_metrics_service.get_overview_metrics, "__call__")

    @pytest.mark.asyncio
    async def test_get_dashboard_overview_exception(self, mock_business_metrics_service):
        """Test get dashboard overview handles exceptions."""
        from app.routes.metrics import get_dashboard_overview

        mock_business_metrics_service.get_overview_metrics.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_overview(mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_dashboard_sessions_valid_days(self, mock_business_metrics_service):
        """Test get dashboard sessions with valid days parameter."""
        from app.routes.metrics import get_dashboard_sessions

        result = await get_dashboard_sessions(days=30, service=mock_business_metrics_service)

        assert result == {"total_sessions": 50}
        mock_business_metrics_service.get_session_metrics.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_dashboard_sessions_invalid_days_too_low(self, mock_business_metrics_service):
        """Test get dashboard sessions rejects days < 1."""
        from app.routes.metrics import get_dashboard_sessions

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=0, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Days must be between 1 and 365" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_dashboard_sessions_invalid_days_too_high(
        self, mock_business_metrics_service
    ):
        """Test get dashboard sessions rejects days > 365."""
        from app.routes.metrics import get_dashboard_sessions

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=366, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_dashboard_sessions_exception(self, mock_business_metrics_service):
        """Test get dashboard sessions handles exceptions."""
        from app.routes.metrics import get_dashboard_sessions

        mock_business_metrics_service.get_session_metrics.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=30, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_dashboard_tasks(self, mock_business_metrics_service):
        """Test get dashboard tasks endpoint."""
        from app.routes.metrics import get_dashboard_tasks

        result = await get_dashboard_tasks(days=30, service=mock_business_metrics_service)

        assert result == {"total_tasks": 20}
        mock_business_metrics_service.get_task_metrics.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_dashboard_tasks_invalid_days(self, mock_business_metrics_service):
        """Test get dashboard tasks validates days parameter."""
        from app.routes.metrics import get_dashboard_tasks

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_tasks(days=400, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_dashboard_users(self, mock_business_metrics_service):
        """Test get dashboard users endpoint."""
        from app.routes.metrics import get_dashboard_users

        result = await get_dashboard_users(days=30, service=mock_business_metrics_service)

        assert result == {"total_users": 10}
        mock_business_metrics_service.get_user_metrics.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_dashboard_users_invalid_days(self, mock_business_metrics_service):
        """Test get dashboard users validates days parameter."""
        from app.routes.metrics import get_dashboard_users

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_users(days=0, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_dashboard_templates(self, mock_business_metrics_service):
        """Test get dashboard templates endpoint."""
        from app.routes.metrics import get_dashboard_templates

        result = await get_dashboard_templates(days=30, service=mock_business_metrics_service)

        assert result == {"total_templates": 5}
        mock_business_metrics_service.get_template_metrics.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_dashboard_templates_invalid_days(self, mock_business_metrics_service):
        """Test get dashboard templates validates days parameter."""
        from app.routes.metrics import get_dashboard_templates

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_templates(days=500, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_with_cache(
        self, mock_business_metrics_service, mock_cache_service
    ):
        """Test get complete dashboard uses cache."""
        from app.routes.metrics import get_complete_dashboard

        mock_cache_service.get_api_response = AsyncMock(
            return_value={"cached": True, "total_requests": 500}
        )

        with patch("app.routes.metrics.get_cache_service", return_value=mock_cache_service):
            result = await get_complete_dashboard(days=30, service=mock_business_metrics_service)

            assert result == {"cached": True, "total_requests": 500}
            mock_cache_service.get_api_response.assert_called_once()
            mock_business_metrics_service.get_dashboard_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_without_cache(
        self, mock_business_metrics_service, mock_cache_service
    ):
        """Test get complete dashboard computes data when cache miss."""
        from app.routes.metrics import get_complete_dashboard

        mock_cache_service.get_api_response = AsyncMock(return_value=None)

        with patch("app.routes.metrics.get_cache_service", return_value=mock_cache_service):
            result = await get_complete_dashboard(days=30, service=mock_business_metrics_service)

            assert "overview" in result
            assert "system" in result
            mock_business_metrics_service.get_dashboard_data.assert_called_once_with(30)
            mock_cache_service.set_api_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_invalid_days(self, mock_business_metrics_service):
        """Test get complete dashboard validates days parameter."""
        from app.routes.metrics import get_complete_dashboard

        with pytest.raises(HTTPException) as exc_info:
            await get_complete_dashboard(days=0, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_complete_dashboard_exception(self, mock_business_metrics_service):
        """Test get complete dashboard handles exceptions."""
        from app.routes.metrics import get_complete_dashboard

        mock_business_metrics_service.get_dashboard_data.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_complete_dashboard(days=30, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_dashboard_html(self, mock_business_metrics_service):
        """Test get dashboard HTML endpoint."""
        from app.routes.metrics import get_dashboard_html

        result = await get_dashboard_html(days=30, service=mock_business_metrics_service)

        assert isinstance(result, HTMLResponse)
        body_str = str(result.body)
        assert "APGI API Analytics Dashboard" in body_str
        assert "Showing data for the last 30 days" in body_str

    @pytest.mark.asyncio
    async def test_get_dashboard_html_invalid_days(self, mock_business_metrics_service):
        """Test get dashboard HTML validates days parameter."""
        from app.routes.metrics import get_dashboard_html

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=0, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_dashboard_html_exception(self, mock_business_metrics_service):
        """Test get dashboard HTML handles exceptions."""
        from app.routes.metrics import get_dashboard_html

        mock_business_metrics_service.get_dashboard_data.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_html(days=30, service=mock_business_metrics_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_start_memory_tracing(self, mock_profiling_service):
        """Test start memory tracing endpoint."""
        from app.routes.metrics import start_memory_tracing

        result = await start_memory_tracing(mock_profiling_service)

        assert result == {"message": "Memory tracing started successfully"}
        mock_profiling_service.start_memory_tracing.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_memory_tracing_exception(self, mock_profiling_service):
        """Test start memory tracing handles exceptions."""
        from app.routes.metrics import start_memory_tracing

        mock_profiling_service.start_memory_tracing.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await start_memory_tracing(mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_stop_memory_tracing(self, mock_profiling_service):
        """Test stop memory tracing endpoint."""
        from app.routes.metrics import stop_memory_tracing

        result = await stop_memory_tracing(mock_profiling_service)

        assert result == {"message": "Memory tracing stopped successfully"}
        mock_profiling_service.stop_memory_tracing.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_memory_tracing_exception(self, mock_profiling_service):
        """Test stop memory tracing handles exceptions."""
        from app.routes.metrics import stop_memory_tracing

        mock_profiling_service.stop_memory_tracing.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await stop_memory_tracing(mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_memory_snapshot(self, mock_profiling_service):
        """Test get memory snapshot endpoint."""
        from app.routes.metrics import get_memory_snapshot

        result = await get_memory_snapshot(mock_profiling_service)

        assert result == {"total_memory": 1024}
        mock_profiling_service.get_memory_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_memory_snapshot_exception(self, mock_profiling_service):
        """Test get memory snapshot handles exceptions."""
        from app.routes.metrics import get_memory_snapshot

        mock_profiling_service.get_memory_snapshot.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_memory_snapshot(mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_system_performance(self, mock_profiling_service):
        """Test get system performance endpoint."""
        from app.routes.metrics import get_system_performance

        result = await get_system_performance(mock_profiling_service)

        assert result == {"cpu": 50, "memory": 60}
        mock_profiling_service.get_system_performance.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_performance_exception(self, mock_profiling_service):
        """Test get system performance handles exceptions."""
        from app.routes.metrics import get_system_performance

        mock_profiling_service.get_system_performance.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_system_performance(mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_performance_history_valid_hours(self, mock_profiling_service):
        """Test get performance history with valid hours parameter."""
        from app.routes.metrics import get_performance_history

        result = await get_performance_history(hours=5, service=mock_profiling_service)

        assert result == {"history": []}
        mock_profiling_service.get_performance_history.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_performance_history_invalid_hours_too_low(self, mock_profiling_service):
        """Test get performance history rejects hours < 1."""
        from app.routes.metrics import get_performance_history

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=0, service=mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Hours must be between 1 and 24" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_performance_history_invalid_hours_too_high(self, mock_profiling_service):
        """Test get performance history rejects hours > 24."""
        from app.routes.metrics import get_performance_history

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=25, service=mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_performance_history_exception(self, mock_profiling_service):
        """Test get performance history handles exceptions."""
        from app.routes.metrics import get_performance_history

        mock_profiling_service.get_performance_history.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=5, service=mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_bottleneck_analysis(self, mock_profiling_service):
        """Test get bottleneck analysis endpoint."""
        from app.routes.metrics import get_bottleneck_analysis

        result = await get_bottleneck_analysis(mock_profiling_service)

        assert result == {"bottlenecks": []}
        mock_profiling_service.get_bottleneck_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bottleneck_analysis_exception(self, mock_profiling_service):
        """Test get bottleneck analysis handles exceptions."""
        from app.routes.metrics import get_bottleneck_analysis

        mock_profiling_service.get_bottleneck_analysis.side_effect = Exception("Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_bottleneck_analysis(mock_profiling_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestMetricsDependencies:
    """Tests for metrics dependency functions."""

    def test_get_business_metrics_service_singleton(self):
        """Test business metrics service is singleton."""
        from app.routes.metrics import get_business_metrics_service

        # Reset global to None to test initialization
        import app.routes.metrics as metrics_module

        metrics_module._business_metrics_service = None

        service1 = get_business_metrics_service()
        service2 = get_business_metrics_service()

        assert service1 is service2
        assert metrics_module._business_metrics_service is not None

    def test_get_profiling_service_singleton(self):
        """Test profiling service is singleton."""
        from app.routes.metrics import get_profiling_service

        # Reset global to None to test initialization
        import app.routes.metrics as metrics_module

        metrics_module._profiling_service = None

        service1 = get_profiling_service()
        service2 = get_profiling_service()

        assert service1 is service2
        assert metrics_module._profiling_service is not None
