"""
Unit tests for ProfilingMiddleware covering dispatch with profiling enabled/disabled.
Requirements: 1.7, 4.7
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestProfilingMiddlewareDisabled:
    """Test ProfilingMiddleware when profiling is disabled."""

    def test_dispatch_disabled_passes_through(self) -> None:
        """When disabled, middleware passes request through without profiling."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        from app.middleware.profiling import ProfilingMiddleware

        app.add_middleware(ProfilingMiddleware, enabled=False)

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        # No profiling headers added when disabled
        assert "X-Request-Duration" not in response.headers

    def test_init_disabled_no_profiling_service(self) -> None:
        """When disabled, ProfilingService is not instantiated."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        middleware = ProfilingMiddleware(mock_app, enabled=False)

        assert middleware.enabled is False
        assert middleware.profiling_service is None


class TestProfilingMiddlewareEnabled:
    """Test ProfilingMiddleware when profiling is enabled."""

    def test_dispatch_enabled_adds_duration_header(self) -> None:
        """When enabled, dispatch adds X-Request-Duration header."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        from app.middleware.profiling import ProfilingMiddleware

        with patch("app.middleware.profiling.ProfilingService"):
            app.add_middleware(ProfilingMiddleware, enabled=True, profile_functions=False)
            client = TestClient(app)
            response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-Duration" in response.headers

    def test_dispatch_enabled_with_function_profiling(self) -> None:
        """When enabled with profile_functions=True, adds X-Profiled header."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        from app.middleware.profiling import ProfilingMiddleware

        with patch("app.middleware.profiling.ProfilingService"):
            app.add_middleware(ProfilingMiddleware, enabled=True, profile_functions=True)
            client = TestClient(app)
            response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-Duration" in response.headers
        assert response.headers.get("X-Profiled") == "true"

    def test_init_enabled_creates_profiling_service(self) -> None:
        """When enabled, ProfilingService is instantiated."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        with patch("app.middleware.profiling.ProfilingService") as mock_svc_cls:
            middleware = ProfilingMiddleware(mock_app, enabled=True)

        assert middleware.enabled is True
        assert middleware.profiling_service is not None
        mock_svc_cls.assert_called_once()

    def test_init_enabled_with_memory_tracing(self) -> None:
        """When enabled with memory_tracing=True, starts memory tracing."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        with patch("app.middleware.profiling.ProfilingService") as mock_svc_cls:
            mock_svc = mock_svc_cls.return_value
            middleware = ProfilingMiddleware(mock_app, enabled=True, memory_tracing=True)

        mock_svc.start_memory_tracing.assert_called_once()

    def test_dispatch_enabled_no_function_profiling(self) -> None:
        """When enabled without function profiling, no cProfile is used."""
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        from app.middleware.profiling import ProfilingMiddleware

        with patch("app.middleware.profiling.ProfilingService"):
            with patch("app.middleware.profiling.cProfile") as mock_cprofile:
                app.add_middleware(ProfilingMiddleware, enabled=True, profile_functions=False)
                client = TestClient(app)
                response = client.get("/test")

        assert response.status_code == 200
        # cProfile.Profile should not be called when profile_functions=False
        mock_cprofile.Profile.assert_not_called()


class TestProfilingMiddlewareDispatchDirect:
    """Test dispatch method directly using AsyncMock for call_next."""

    @pytest.mark.asyncio
    async def test_dispatch_disabled_calls_call_next(self) -> None:
        """Disabled middleware calls call_next and returns its response."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        middleware = ProfilingMiddleware(mock_app, enabled=False)

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        call_next.assert_awaited_once_with(mock_request)
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_dispatch_enabled_records_duration(self) -> None:
        """Enabled middleware records duration and adds header."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        with patch("app.middleware.profiling.ProfilingService"):
            middleware = ProfilingMiddleware(mock_app, enabled=True, profile_functions=False)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        call_next.assert_awaited_once_with(mock_request)
        assert "X-Request-Duration" in mock_response.headers

    @pytest.mark.asyncio
    async def test_dispatch_enabled_with_cprofile(self) -> None:
        """Enabled middleware with profile_functions uses cProfile."""
        from app.middleware.profiling import ProfilingMiddleware

        mock_app = MagicMock()
        with patch("app.middleware.profiling.ProfilingService"):
            middleware = ProfilingMiddleware(mock_app, enabled=True, profile_functions=True)

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/test"
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.middleware.profiling.cProfile") as mock_cprofile:
            mock_profiler = MagicMock()
            mock_cprofile.Profile.return_value = mock_profiler

            with patch("app.middleware.profiling.pstats") as mock_pstats:
                mock_stats = MagicMock()
                mock_pstats.Stats.return_value = mock_stats
                mock_stats.sort_stats.return_value = mock_stats
                mock_stats.print_stats.return_value = None

                with patch("app.middleware.profiling.io") as mock_io:
                    mock_stream = MagicMock()
                    mock_stream.getvalue.return_value = "profile output"
                    mock_io.StringIO.return_value = mock_stream

                    result = await middleware.dispatch(mock_request, call_next)

        assert "X-Request-Duration" in mock_response.headers
        assert mock_response.headers.get("X-Profiled") == "true"
        mock_profiler.enable.assert_called_once()
        mock_profiler.disable.assert_called_once()
