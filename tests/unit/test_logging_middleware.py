"""
Unit tests for app/middleware/logging.py
Covers RequestLoggingMiddleware.dispatch, StructuredLogger log-level methods,
ErrorLoggingHandler, and configure_structured_logging.
Requirements: 1.3, 4.9
"""

from typing import Any

from unittest.mock import MagicMock, patch

import pytest  # noqa: F401
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.logging import (
    StructuredLogger,
    RequestLoggingMiddleware,
    ErrorLoggingHandler,
    configure_structured_logging,
    request_id_context,
    error_logger,
)


class TestStructuredLogger:
    """Test StructuredLogger log-level methods."""

    def setup_method(self) -> None:
        self.logger = StructuredLogger("test.logger")

    def test_info_logs_message(self) -> None:
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("hello", key="val")
            mock_info.assert_called_once()
            logged = mock_info.call_args[0][0]
            assert "hello" in logged
            assert "INFO" in logged
            assert "val" in logged

    def test_warning_logs_message(self) -> None:
        with patch.object(self.logger.logger, "warning") as mock_warn:
            self.logger.warning("warn msg", code=42)
            mock_warn.assert_called_once()
            logged = mock_warn.call_args[0][0]
            assert "warn msg" in logged
            assert "WARNING" in logged

    def test_error_logs_message(self) -> None:
        with patch.object(self.logger.logger, "error") as mock_err:
            self.logger.error("err msg", detail="oops")
            mock_err.assert_called_once()
            logged = mock_err.call_args[0][0]
            assert "err msg" in logged
            assert "ERROR" in logged

    def test_debug_logs_message(self) -> None:
        with patch.object(self.logger.logger, "debug") as mock_dbg:
            self.logger.debug("dbg msg")
            mock_dbg.assert_called_once()
            logged = mock_dbg.call_args[0][0]
            assert "dbg msg" in logged
            assert "DEBUG" in logged

    def test_format_includes_timestamp(self) -> None:
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("ts test")
            logged = mock_info.call_args[0][0]
            assert "timestamp" in logged

    def test_format_includes_logger_name(self) -> None:
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("name test")
            logged = mock_info.call_args[0][0]
            assert "test.logger" in logged

    def test_format_includes_request_id_from_context(self) -> None:
        token = request_id_context.set("req-ctx-123")
        try:
            with patch.object(self.logger.logger, "info") as mock_info:
                self.logger.info("ctx test")
                logged = mock_info.call_args[0][0]
                assert "req-ctx-123" in logged
        finally:
            request_id_context.reset(token)

    def test_format_no_request_id_when_context_empty(self) -> None:
        # Ensure context is cleared
        token = request_id_context.set(None)
        try:
            with patch.object(self.logger.logger, "info") as mock_info:
                self.logger.info("no ctx")
                logged = mock_info.call_args[0][0]
                assert "request_id" not in logged
        finally:
            request_id_context.reset(token)


class TestRequestLoggingMiddleware:
    """Test RequestLoggingMiddleware.dispatch via TestClient."""

    def _make_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/fail")
        async def fail() -> None:
            raise ValueError("boom")

        return app

    def test_dispatch_success_adds_request_id_header(self) -> None:
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/ok")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_dispatch_success_logs_request(self) -> None:
        app = self._make_app()
        with patch("app.middleware.logging.StructuredLogger.info") as mock_info:
            client = TestClient(app)
            client.get("/ok")
            # At least one info call should mention "Request processed"
            calls = [str(c) for c in mock_info.call_args_list]
            assert any("Request processed" in c for c in calls)

    def test_dispatch_sets_request_id_on_state(self) -> None:
        captured = {}
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/state")
        async def state_route(request: Request) -> dict[str, Any]:
            captured["rid"] = getattr(request.state, "request_id", None)
            return {}

        client = TestClient(app)
        client.get("/state")
        assert captured["rid"] is not None
        assert len(captured["rid"]) == 36  # UUID format

    def test_dispatch_exception_logs_error(self) -> None:
        app = self._make_app()
        with patch("app.middleware.logging.StructuredLogger.error") as mock_err:
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/fail")
            calls = [str(c) for c in mock_err.call_args_list]
            assert any("Request failed" in c for c in calls)

    def test_dispatch_no_client_uses_unknown(self) -> None:
        """Middleware handles missing client gracefully."""
        from unittest.mock import PropertyMock

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/noclient")
        async def noclient() -> dict[str, Any]:
            return {}

        # Patch Request.client property to return None
        with patch("fastapi.Request.client", new_callable=PropertyMock, return_value=None):
            with patch("app.middleware.logging.StructuredLogger.info") as mock_info:
                client = TestClient(app)
                response = client.get("/noclient")
                assert response.status_code == 200
                calls = [str(c) for c in mock_info.call_args_list]
                assert any("unknown" in c for c in calls)


class TestErrorLoggingHandler:
    """Test ErrorLoggingHandler.log_error."""

    def setup_method(self) -> None:
        self.handler = ErrorLoggingHandler()

    def test_log_error_without_request(self) -> None:
        with patch.object(self.handler.logger, "error") as mock_err:
            self.handler.log_error(ValueError("test error"))
            mock_err.assert_called_once()
            logged = mock_err.call_args[0][0]
            assert "Error occurred" in logged

    def test_log_error_with_request(self) -> None:
        mock_request = MagicMock()
        mock_request.state.request_id = "req-abc"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"

        with patch.object(self.handler.logger, "error") as mock_err:
            self.handler.log_error(ValueError("with request"), request=mock_request)
            mock_err.assert_called_once()
            logged = mock_err.call_args[0][0]
            assert "Error occurred" in logged

    def test_log_error_with_error_code(self) -> None:
        with patch.object(self.handler.logger, "error") as mock_err:
            self.handler.log_error(RuntimeError("coded"), error_code="ERR_001")
            mock_err.assert_called_once()

    def test_log_error_calls_logger_error(self) -> None:
        """Test that log_error calls the logger's error method with context data."""
        with patch.object(self.handler.logger, "error") as mock_structured_err:
            try:
                raise RuntimeError("traceable")
            except RuntimeError as e:
                self.handler.log_error(e)
            # Verify error was called with message and context data
            mock_structured_err.assert_called_once()
            call_args = mock_structured_err.call_args
            assert call_args[0][0] == "Error occurred"
            assert call_args[1] is not None  # kwargs should be present

    def test_global_error_logger_instance(self) -> None:
        assert isinstance(error_logger, ErrorLoggingHandler)


class TestConfigureStructuredLogging:
    """Test configure_structured_logging."""

    def test_skips_configuration_in_test_mode(self) -> None:
        """Test that function returns early when TEST_MODE is true."""
        with patch("logging.basicConfig") as mock_basic:
            with patch.dict("os.environ", {"TEST_MODE": "true"}):
                configure_structured_logging("INFO")
                mock_basic.assert_not_called()

    def test_function_is_callable_with_various_log_levels(self) -> None:
        """Test that function can be called without error in test mode."""
        # In test mode, the function should simply return without error
        with patch.dict("os.environ", {"TEST_MODE": "true"}):
            configure_structured_logging("DEBUG")
            configure_structured_logging("INFO")
            configure_structured_logging("WARNING")
            configure_structured_logging("ERROR")
            # If we get here without exception, the test passes
            assert True
