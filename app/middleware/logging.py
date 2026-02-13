"""
Structured Logging Middleware

Provides structured JSON logging for all API requests and errors.
"""

import json
import logging
import time
import traceback
import uuid
from datetime import datetime
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted log entries.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _format_log_entry(self, level: str, message: str, **kwargs) -> str:
        """
        Format log entry as JSON.

        Args:
            level: Log level (INFO, ERROR, etc.)
            message: Log message
            **kwargs: Additional fields to include in log entry

        Returns:
            JSON-formatted log string
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.logger.name,
            "message": message,
            **kwargs,
        }
        return json.dumps(log_entry)

    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(self._format_log_entry("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self.logger.warning(self._format_log_entry("WARNING", message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self.logger.error(self._format_log_entry("ERROR", message, **kwargs))

    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self.logger.debug(self._format_log_entry("DEBUG", message, **kwargs))


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests with structured data.

    Logs include:
    - Request method, path, status code
    - Request duration
    - Client identifier
    - Request ID for tracing
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = StructuredLogger("app.requests")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract client identifier (IP or user ID if authenticated)
        client_id = request.client.host if request.client else "unknown"

        # Record start time
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful request
            self.logger.info(
                "Request processed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                client_id=client_id,
                user_agent=request.headers.get("user-agent", "unknown"),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            self.logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                client_id=client_id,
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )

            # Re-raise exception to be handled by exception handlers
            raise


class ErrorLoggingHandler:
    """
    Handler for logging errors with full context and stack traces.
    """

    def __init__(self):
        self.logger = StructuredLogger("app.errors")

    def log_error(
        self,
        error: Exception,
        request: Optional[Request] = None,
        error_code: Optional[str] = None,
        **context,
    ):
        """
        Log error with full context.

        Args:
            error: Exception that occurred
            request: HTTP request (if available)
            error_code: Application error code
            **context: Additional context fields
        """
        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
            **context,
        }

        # Add request context if available
        if request:
            log_data.update(
                {
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "method": request.method,
                    "path": request.url.path,
                    "client_id": request.client.host if request.client else "unknown",
                }
            )

        # Add error code if provided
        if error_code:
            log_data["error_code"] = error_code

        self.logger.error("Error occurred", **log_data)


# Global error logging handler instance
error_logger = ErrorLoggingHandler()


def configure_structured_logging(log_level: str = "INFO"):
    """
    Configure Python logging to use structured format.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Set root logger level
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",  # Just output the message (already JSON formatted)
        handlers=[logging.StreamHandler()],
    )

    # Disable uvicorn access logs (we handle them in middleware)
    logging.getLogger("uvicorn.access").disabled = True
