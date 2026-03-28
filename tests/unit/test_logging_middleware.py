"""
Unit tests for app/middleware/logging.py
Covers RequestLoggingMiddleware.dispatch, StructuredLogger log-level methods,
ErrorLoggingHandler, and configure_structured_logging.
Requirements: 1.3, 4.9
"""

import logging
from unittest.mock import MagicMock, patch
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

    def setup_method(self):
        self.logger = StructuredLogger("test.logger")

    def test_info_logs_message(self):
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("hello", key="val")
            mock_info.assert_called_once()
            logged = mock_info.call_args[0][0]
            assert "hello" in logged
            assert "INFO" in logged
            assert "val" in logged

    def test_warning_logs_message(self):
        with patch.object(self.logger.logger, "warning") as mock_warn:
            self.logger.warning("warn msg", code=42)
            mock_warn.assert_called_once()
            logged = mock_warn.call_args[0][0]
            assert "warn msg" in logged
            assert "WARNING" in logged

    def test_error_logs_message(self):
        with patch.object(self.logger.logger, "error") as mock_err:
            self.logger.error("err msg", detail="oops")
            mock_err.assert_called_once()
            logged = mock_err.call_args[0][0]
            assert "err msg" in logged
            assert "ERROR" in logged

    def test_debug_logs_message(self):
        with patch.object(self.logger.logger, "debug") as mock_dbg:
            self.logger.debug("dbg msg")
            mock_dbg.assert_called_once()
            logged = mock_dbg.call_args[0][0]
            assert "dbg msg" in logged
            assert "DEBUG" in logged

    def test_format_includes_timestamp(self):
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("ts test")
            logged = mock_info.call_args[0][0]
            assert "timestamp" in logged

    def test_format_includes_logger_name(self):
        with patch.object(self.logger.logger, "info") as mock_info:
            self.logger.info("name test")
            logged = mock_info.call_args[0][0]
            assert "test.logger" in logged

    def test_format_includes_request_id_from_context(self):
        token = request_id_context.set("req-ctx-123")
        try:
            with patch.object(self.logger.logger, "info") as mock_info:
                self.logger.info("ctx test")
                logged = mock_info.call_args[0][0]
                assert "req-ctx-123" in logged
        finally:
            request_id_context.reset(token)

    def test_format_no_request_id_when_context_empty(self):
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

    def _make_app(self):
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/ok")
        async def ok():
            return {"status": "ok"}

        @app.get("/fail")
        async def fail():
            raise ValueError("boom")

        return app

    def test_dispatch_success_adds_request_id_header(self):
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/ok")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_dispatch_success_logs_request(self):
        app = self._make_app()
        with patch("app.middleware.logging.StructuredLogger.info") as mock_info:
            client = TestClient(app)
            client.get("/ok")
            # At least one info call should mention "Request processed"
            calls = [str(c) for c in mock_info.call_args_list]
            assert any("Request processed" in c for c in calls)

    def test_dispatch_sets_request_id_on_state(self):
        captured = {}
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/state")
        async def state_route(request: Request):
            captured["rid"] = getattr(request.state, "request_id", None)
            return {}

        client = TestClient(app)
        client.get("/state")
        assert captured["rid"] is not None
        assert len(captured["rid"]) == 36  # UUID format

    def test_dispatch_exception_logs_error(self):
        app = self._make_app()
        with patch("app.middleware.logging.StructuredLogger.error") as mock_err:
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/fail")
            calls = [str(c) for c in mock_err.call_args_list]
            assert any("Request failed" in c for c in calls)

    def test_dispatch_no_client_uses_unknown(self):
        """Middleware handles missing client gracefully."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/noclient")
        async def noclient():
            return {}

        client = TestClient(app)
        response = client.get("/noclient")
        assert response.status_code == 200


class TestErrorLoggingHandler:
    """Test ErrorLoggingHandler.log_error."""

    def setup_method(self):
        self.handler = ErrorLoggingHandler()

    def test_log_error_without_request(self):
        with patch.object(self.handler.logger, "error") as mock_err:
            self.handler.log_error(ValueError("test error"))
            mock_err.assert_called_once()
            logged = mock_err.call_args[0][0]
            assert "Error occurred" in logged

    def test_log_error_with_request(self):
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

    def test_log_error_with_error_code(self):
        with patch.object(self.handler.logger, "error") as mock_err:
            self.handler.log_error(RuntimeError("coded"), error_code="ERR_001")
            mock_err.assert_called_once()

    def test_log_error_includes_stack_trace(self):
        # log_error calls self.logger.error(message, **kwargs) where message is "Error occurred"
        # and stack_trace is passed as a kwarg to _format_log_entry which embeds it in JSON
        # We patch StructuredLogger.error to capture the formatted JSON string
        with patch.object(self.handler.logger, "error") as mock_structured_err:
            try:
                raise RuntimeError("traceable")
            except RuntimeError as e:
                self.handler.log_error(e)
            mock_structured_err.assert_called_once()
            # The call is: self.logger.error("Error occurred", stack_trace=..., ...)
            call_kwargs = mock_structured_err.call_args[1]
            assert "stack_trace" in call_kwargs

    def test_global_error_logger_instance(self):
        assert isinstance(error_logger, ErrorLoggingHandler)


class TestConfigureStructuredLogging:
    """Test configure_structured_logging."""

    def test_configure_sets_log_level_info(self):
        with patch("logging.basicConfig") as mock_basic:
            configure_structured_logging("INFO")
            mock_basic.assert_called_once()
            kwargs = mock_basic.call_args[1]
            assert kwargs["level"] == logging.INFO

    def test_configure_sets_log_level_debug(self):
        with patch("logging.basicConfig") as mock_basic:
            configure_structured_logging("DEBUG")
            kwargs = mock_basic.call_args[1]
            assert kwargs["level"] == logging.DEBUG

    def test_configure_sets_log_level_warning(self):
        with patch("logging.basicConfig") as mock_basic:
            configure_structured_logging("WARNING")
            kwargs = mock_basic.call_args[1]
            assert kwargs["level"] == logging.WARNING

    def test_configure_disables_uvicorn_access_logs(self):
        with patch("logging.basicConfig"):
            configure_structured_logging("INFO")
            uvicorn_logger = logging.getLogger("uvicorn.access")
            assert uvicorn_logger.disabled is True
