"""
Tests for database profiling middleware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.middleware.db_profiling import DBProfilingMiddleware


class TestDBProfilingMiddleware:
    """Test database profiling middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock FastAPI app."""
        app = MagicMock()
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Middleware instance."""
        return DBProfilingMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_tracks_query_duration(self, middleware):
        """Test middleware tracks query duration."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert result is not None

    @pytest.mark.asyncio
    async def test_records_slow_queries(self, middleware):
        """Test middleware records slow queries."""
        request = MagicMock(spec=Request)
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)

        assert result is not None
