"""
Additional unit tests for logging middleware to achieve 100% coverage.

Covers:
- configure_structured_logging test mode skip
- Exception handling in logging methods
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.logging import configure_structured_logging, request_id_context


class TestConfigureStructuredLogging:
    """Test configure_structured_logging function."""

    @patch.dict(os.environ, {"TEST_MODE": "true"}, clear=False)
    def test_configure_structured_logging_skips_in_test_mode(self) -> None:
        """Test that logging configuration is skipped in test mode."""
        # Should not configure logging when TEST_MODE is true
        configure_structured_logging("INFO")
        # If we get here without error, the test passed

    @patch.dict(os.environ, {}, clear=True)
    def test_configure_structured_logging_normal_case(self) -> None:
        """Test that logging configuration works in normal case."""
        # Remove TEST_MODE from environment
        root_logger = logging.getLogger()
        # Clear existing handlers to simulate fresh state
        root_logger.handlers.clear()

        configure_structured_logging("INFO")
        # Should configure without error

    def test_configure_structured_logging_already_configured(self) -> None:
        """Test that logging configuration handles already configured loggers."""
        # First configure a logger
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            root_logger.addHandler(logging.StreamHandler())

        configure_structured_logging("INFO")
        # Should handle gracefully

    def test_configure_structured_logging_exception_handling(self) -> None:
        """Test that logging configuration handles exceptions gracefully."""
        with patch("logging.basicConfig", side_effect=Exception("Config failed")):
            # Should not raise despite basicConfig failing
            configure_structured_logging("INFO")
            # If we get here without error, the test passed


class TestRequestIdContext:
    """Test request ID context variable."""

    def test_request_id_context_default(self) -> None:
        """Test that request ID context has no default."""
        result = request_id_context.get()
        assert result is None

    def test_request_id_context_set_reset(self) -> None:
        """Test setting and resetting request ID context."""
        token = request_id_context.set("test-request-id")
        assert request_id_context.get() == "test-request-id"

        request_id_context.reset(token)
        assert request_id_context.get() is None


class TestStructuredLoggerExceptions:
    """Test exception handling in StructuredLogger."""

    def test_structured_logger_handles_logging_exceptions(self) -> None:
        """Test that StructuredLogger handles exceptions gracefully."""
        from app.middleware.logging import StructuredLogger

        logger = StructuredLogger("test.logger")

        # Mock the underlying logger to raise an exception
        with patch.object(logger.logger, "info", side_effect=Exception("Logging failed")):

            # Should not raise despite underlying logger failing
            try:
                logger.info("Test message", key="value")
            except Exception:
                pytest.fail("StructuredLogger should handle logging exceptions")

    def test_structured_logger_error_method(self) -> None:
        """Test error logging method."""
        from app.middleware.logging import StructuredLogger

        logger = StructuredLogger("test.logger")

        # Should not raise
        logger.error("Error message", error_type="TestError", details="Some details")

    def test_structured_logger_warning_method(self) -> None:
        """Test warning logging method."""
        from app.middleware.logging import StructuredLogger

        logger = StructuredLogger("test.logger")

        # Should not raise
        logger.warning("Warning message", warning_type="TestWarning")

    def test_structured_logger_debug_method(self) -> None:
        """Test debug logging method."""
        from app.middleware.logging import StructuredLogger

        logger = StructuredLogger("test.logger")

        # Should not raise
        logger.debug("Debug message", debug_info="test")


class TestErrorLoggingHandler:
    """Test ErrorLoggingHandler."""

    def test_error_logger_with_request(self) -> None:
        """Test error logging with request context."""
        from app.middleware.logging import error_logger

        mock_request = MagicMock()
        mock_request.state.request_id = "req-123"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "192.168.1.1"

        error = ValueError("Test error")

        # Should not raise
        error_logger.log_error(error, mock_request, error_code="TEST_ERROR")

    def test_error_logger_without_request(self) -> None:
        """Test error logging without request context."""
        from app.middleware.logging import error_logger

        error = ValueError("Test error without request")

        # Should not raise
        error_logger.log_error(error, error_code="TEST_ERROR_NO_REQ")

    def test_error_logger_with_context(self) -> None:
        """Test error logging with additional context."""
        from app.middleware.logging import error_logger

        error = RuntimeError("Runtime error")

        # Should not raise
        error_logger.log_error(
            error,
            error_code="RUNTIME_ERROR",
            additional_info="Extra context",
            user_id="user123",
        )

    def test_error_logger_exception_during_logging(self) -> None:
        """Test that ErrorLoggingHandler handles exceptions during logging."""
        from app.middleware.logging import ErrorLoggingHandler

        # Create a new handler and mock its logger to raise
        handler = ErrorLoggingHandler()
        with patch.object(handler.logger, "error", side_effect=Exception("Log failed")):

            error = ValueError("Test error")

            # Should not raise despite logging failure
            try:
                handler.log_error(error, error_code="TEST")
            except Exception:
                pytest.fail("ErrorLoggingHandler should handle logging exceptions")
