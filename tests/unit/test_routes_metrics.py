"""
Tests for metrics routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.routes.metrics import (
    get_bottleneck_analysis,
    get_business_metrics_service,
    get_complete_dashboard,
    get_dashboard_html,
    get_dashboard_overview,
    get_dashboard_sessions,
    get_dashboard_tasks,
    get_dashboard_templates,
    get_dashboard_users,
    get_memory_snapshot,
    get_performance_history,
    get_system_performance,
    metrics_endpoint,
    start_memory_tracing,
    stop_memory_tracing,
)


class TestMetricsRoutes:
    """Test metrics endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        with patch("app.routes.metrics.get_metrics_response") as mock_get_metrics:
            mock_response = MagicMock()
            mock_get_metrics.return_value = mock_response

            response = await metrics_endpoint()
            assert response == mock_response

    def test_get_business_metrics_service_singleton(self):
        """Test BusinessMetricsService singleton."""
        service1 = get_business_metrics_service()
        service2 = get_business_metrics_service()
        assert service1 is service2

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_overview_success(self, mock_require_perm):
        """Test getting dashboard overview metrics."""
        mock_require_perm.return_value = None
        mock_service = AsyncMock()
        mock_service.get_overview_metrics.return_value = {"total_requests": 100}

        response = await get_dashboard_overview(mock_service)
        assert response == {"total_requests": 100}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_overview_exception(self, mock_require_perm):
        """Test dashboard overview handles exceptions."""
        mock_require_perm.return_value = None
        mock_service = AsyncMock()
        mock_service.get_overview_metrics.side_effect = Exception("Service error")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_overview(mock_service)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_sessions_valid_days(self, mock_require_perm):
        """Test getting session metrics with valid days parameter."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_session_metrics.return_value = {"sessions": 10}

        response = await get_dashboard_sessions(days=30, service=mock_service)
        assert response == {"sessions": 10}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_sessions_invalid_days_low(self, mock_require_perm):
        """Test session metrics rejects days < 1."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=0, service=mock_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_sessions_invalid_days_high(self, mock_require_perm):
        """Test session metrics rejects days > 365."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_sessions(days=400, service=mock_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_tasks(self, mock_require_perm):
        """Test getting task metrics."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_task_metrics.return_value = {"tasks": 5}

        response = await get_dashboard_tasks(days=30, service=mock_service)
        assert response == {"tasks": 5}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_users(self, mock_require_perm):
        """Test getting user metrics."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_user_metrics.return_value = {"users": 20}

        response = await get_dashboard_users(days=30, service=mock_service)
        assert response == {"users": 20}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_dashboard_templates(self, mock_require_perm):
        """Test getting template metrics."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_template_metrics.return_value = {"templates": 3}

        response = await get_dashboard_templates(days=30, service=mock_service)
        assert response == {"templates": 3}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    @patch("app.routes.metrics.get_cache_service")
    async def test_get_complete_dashboard_with_cache_hit(self, mock_get_cache, mock_require_perm):
        """Test complete dashboard with cache hit."""
        mock_require_perm.return_value = None
        mock_service = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.get_api_response.return_value = {"cached": True}
        mock_get_cache.return_value = mock_cache

        response = await get_complete_dashboard(days=30, service=mock_service)
        assert response == {"cached": True}
        assert not mock_service.get_dashboard_data.called

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    @patch("app.routes.metrics.get_cache_service")
    async def test_get_complete_dashboard_cache_miss(self, mock_get_cache, mock_require_perm):
        """Test complete dashboard with cache miss."""
        mock_require_perm.return_value = None
        mock_service = AsyncMock()
        mock_service.get_dashboard_data.return_value = {"overview": {}}
        mock_cache = AsyncMock()
        mock_cache.get_api_response.return_value = None
        mock_get_cache.return_value = mock_cache

        response = await get_complete_dashboard(days=30, service=mock_service)
        assert response == {"overview": {}}
        assert mock_service.get_dashboard_data.called
        assert mock_cache.set_api_response.called

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    @patch("app.routes.metrics._load_dashboard_template")
    @patch("app.routes.metrics._render_dashboard_template")
    async def test_get_dashboard_html(self, mock_render, mock_load, mock_require_perm):
        """Test getting dashboard HTML."""
        mock_require_perm.return_value = None
        mock_service = AsyncMock()
        mock_service.get_dashboard_data.return_value = {"overview": {}}
        mock_load.return_value = "<html>{{days}}</html>"
        mock_render.return_value = "<html>30</html>"

        response = await get_dashboard_html(days=30, service=mock_service)
        assert response.body == b"<html>30</html>"

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_start_memory_tracing(self, mock_require_perm):
        """Test starting memory tracing."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()

        response = await start_memory_tracing(mock_service)
        assert response == {"message": "Memory tracing started successfully"}
        assert mock_service.start_memory_tracing.called

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_stop_memory_tracing(self, mock_require_perm):
        """Test stopping memory tracing."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()

        response = await stop_memory_tracing(mock_service)
        assert response == {"message": "Memory tracing stopped successfully"}
        assert mock_service.stop_memory_tracing.called

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_memory_snapshot(self, mock_require_perm):
        """Test getting memory snapshot."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_memory_snapshot.return_value = {"memory": "1GB"}

        response = await get_memory_snapshot(mock_service)
        assert response == {"memory": "1GB"}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_system_performance(self, mock_require_perm):
        """Test getting system performance metrics."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_system_performance.return_value = {"cpu": 50}

        response = await get_system_performance(mock_service)
        assert response == {"cpu": 50}

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_performance_history_valid_hours(self, mock_require_perm):
        """Test getting performance history with valid hours."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_performance_history.return_value = []

        response = await get_performance_history(hours=12, service=mock_service)
        assert response == []

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_performance_history_invalid_hours(self, mock_require_perm):
        """Test performance history rejects invalid hours."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_performance_history(hours=25, service=mock_service)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch("app.routes.metrics.require_permission")
    async def test_get_bottleneck_analysis(self, mock_require_perm):
        """Test getting bottleneck analysis."""
        mock_require_perm.return_value = None
        mock_service = MagicMock()
        mock_service.get_bottleneck_analysis.return_value = {"bottlenecks": []}

        response = await get_bottleneck_analysis(mock_service)
        assert response == {"bottlenecks": []}
