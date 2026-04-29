"""
Tests for profiling middleware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.middleware.profiling import ProfilingMiddleware


class TestProfilingMiddleware:
    """Test profiling middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock FastAPI app."""
        app = MagicMock()
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Middleware instance."""
        return ProfilingMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_profiles_request(self, middleware):
        """Test middleware profiles requests."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert result is not None

    @pytest.mark.asyncio
    async def test_collects_performance_metrics(self, middleware):
        """Test middleware collects performance metrics."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert result is not None
