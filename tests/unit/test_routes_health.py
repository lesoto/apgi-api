"""
Tests for health check routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routes.health import get_health_service, init_health_routes, router


class TestHealthRoutes:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_liveness_check(self):
        """Test liveness endpoint returns alive status."""
        from app.routes.health import liveness_check

        response = await liveness_check()
        assert response.status_code == 200
        assert response.body == b'{"status":"alive","message":"API is running"}'

    @pytest.mark.asyncio
    async def test_get_health_service_uninitialized(self):
        """Test get_health_service raises 503 when uninitialized."""
        # Reset global service
        import app.routes.health as health_module

        health_module.health_service = None

        with pytest.raises(HTTPException) as exc_info:
            await get_health_service()
        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.routes.health.asyncio.create_task")
    async def test_get_health_service_alerts_on_uninitialized(self, mock_create_task):
        """Test get health service triggers alert when uninitialized."""
        import app.routes.health as health_module

        health_module.health_service = None

        with pytest.raises(HTTPException) as exc_info:
            await get_health_service()
        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail

        # Verify alert task was created
        assert mock_create_task.called

    def test_init_health_routes(self):
        """Test init_health routes sets global service."""
        mock_redis = MagicMock()

        init_health_routes(mock_redis)

        # Import again to get the updated global
        from app.routes.health import health_service

        assert health_service is not None

    @pytest.mark.asyncio
    @patch("app.routes.health.get_health_service")
    async def test_root_health_check_healthy(self, mock_get_health):
        """Test root health check when all components healthy."""
        from app.routes.health import root_health_check

        mock_service = AsyncMock()
        mock_service.perform_health_check.return_value = {"status": "healthy"}
        mock_get_health.return_value = mock_service

        response = await root_health_check(mock_service)
        assert response.status_code == 200
        assert response.body == b'{"status":"healthy"}'

    @pytest.mark.asyncio
    @patch("app.routes.health.get_health_service")
    async def test_root_health_check_unhealthy(self, mock_get_health):
        """Test root health check when components unhealthy."""
        from app.routes.health import root_health_check

        mock_service = AsyncMock()
        mock_service.perform_health_check.return_value = {"status": "unhealthy"}
        mock_get_health.return_value = mock_service

        response = await root_health_check(mock_service)
        assert response.status_code == 503

    @pytest.mark.asyncio
    @patch("app.routes.health.get_health_service")
    async def test_readiness_check_ready(self, mock_get_health):
        """Test readiness check when ready."""
        from app.routes.health import readiness_check

        mock_service = AsyncMock()
        mock_service.perform_readiness_check.return_value = {"status": "ready"}
        mock_get_health.return_value = mock_service

        response = await readiness_check(mock_service)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.routes.health.get_health_service")
    async def test_readiness_check_not_ready(self, mock_get_health):
        """Test readiness check when not ready."""
        from app.routes.health import readiness_check

        mock_service = AsyncMock()
        mock_service.perform_readiness_check.return_value = {"status": "not_ready"}
        mock_get_health.return_value = mock_service

        response = await readiness_check(mock_service)
        assert response.status_code == 503

    def test_router_configuration(self):
        """Test router is properly configured."""
        assert router.tags == ["Health"]
        assert len(router.routes) == 3
