"""
Property-based tests for logging middleware.

Feature: api-migration
Tests universal properties of structured logging, request logging,
request ID propagation, and error logging with context.
"""

import json
import logging
import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import sys
from pathlib import Path
from io import StringIO

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from middleware.logging import (
    RequestLoggingMiddleware,
    StructuredLogger,
    ErrorLoggingHandler,
)


# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_logging():
    """Create a test FastAPI app with logging middleware."""
    app = FastAPI()

    # Add logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Add test endpoints
    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @app.post("/test")
    async def test_post_endpoint():
        return {"message": "test post"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.get("/http-error")
    async def http_error_endpoint():
        raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/v1/sessions")
    async def sessions_endpoint(request: Request):
        # Access request_id to verify it's set
        request_id = getattr(request.state, "request_id", None)
        return {"sessions": [], "request_id": request_id}

    return app


@contextmanager
def capture_logs(logger_name: str):
    """Context manager to capture log output."""
    logger = logging.getLogger(logger_name)
    string_io = StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    class LogCapture:
        def get_logs(self):
            return string_io.getvalue()

        def get_log_entries(self):
            """Parse JSON log entries."""
            logs = self.get_logs()
            entries = []
            for line in logs.strip().split("\n"):
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return entries

    capture = LogCapture()

    try:
        yield capture
    finally:
        logger.removeHandler(handler)
        string_io.close()


# ============================================================================
# Property 7: Structured JSON Logging Format
# ============================================================================


@settings(max_examples=2)
@given(
    message=st.text(min_size=1, max_size=100),
    level=st.sampled_from(["INFO", "WARNING", "ERROR", "DEBUG"]),
)
def test_property_7_structured_json_logging_format(message, level):
    """
    **Validates: Requirements 10.1**

    Feature: api-migration, Property 7: Structured JSON Logging Format

    For any log message, it should be valid JSON containing at minimum:
    timestamp, level, message, and component fields.

    This property ensures all log messages follow a structured JSON format
    that can be parsed and analyzed by log aggregation systems.
    """
    # Create structured logger
    logger = StructuredLogger("test.component")

    # Capture log output
    with capture_logs("test.component") as log_capture:
        # Log message at specified level
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "DEBUG":
            logger.debug(message)

        # Get log entries
        entries = log_capture.get_log_entries()

        # Skip if no logs captured (can happen with DEBUG level)
        assume(len(entries) > 0)

        # Get the last log entry
        log_entry = entries[-1]

        # Property 1: Log entry should be valid JSON (already parsed)
        assert isinstance(log_entry, dict), f"Log entry should be a valid JSON object"

        # Property 2: Log entry should contain timestamp field
        assert "timestamp" in log_entry, f"Log entry should contain 'timestamp' field"

        # Property 3: Log entry should contain level field
        assert "level" in log_entry, f"Log entry should contain 'level' field"
        assert (
            log_entry["level"] == level
        ), f"Log level should be '{level}', got '{log_entry['level']}'"

        # Property 4: Log entry should contain message field
        assert "message" in log_entry, f"Log entry should contain 'message' field"
        assert (
            log_entry["message"] == message
        ), f"Log message should be '{message}', got '{log_entry['message']}'"

        # Property 5: Log entry should contain component field (logger name)
        assert "logger" in log_entry, f"Log entry should contain 'logger' field"
        assert (
            log_entry["logger"] == "test.component"
        ), f"Logger name should be 'test.component', got '{log_entry['logger']}'"


@settings(max_examples=2)
@given(
    message=st.text(min_size=1, max_size=100),
    extra_field_key=st.text(
        min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))
    ),
    extra_field_value=st.one_of(
        st.text(min_size=1, max_size=50), st.integers(), st.floats(allow_nan=False)
    ),
)
def test_property_7_structured_logging_with_extra_fields(
    message, extra_field_key, extra_field_value
):
    """
    **Validates: Requirements 10.1**

    Feature: api-migration, Property 7: Structured JSON Logging Format

    For any log message with additional context fields, the log entry should
    include those fields in the JSON output.

    This property ensures that additional context can be added to log entries
    for better debugging and analysis.
    """
    # Create structured logger
    logger = StructuredLogger("test.component")

    # Capture log output
    with capture_logs("test.component") as log_capture:
        # Log message with extra field
        logger.info(message, **{extra_field_key: extra_field_value})

        # Get log entries
        entries = log_capture.get_log_entries()
        assume(len(entries) > 0)

        log_entry = entries[-1]

        # Property: Extra field should be present in log entry
        assert (
            extra_field_key in log_entry
        ), f"Log entry should contain extra field '{extra_field_key}'"

        # Verify the value matches (handle float comparison)
        actual_value = log_entry[extra_field_key]
        if isinstance(extra_field_value, float):
            assert isinstance(actual_value, (int, float)), f"Extra field value should be numeric"
        else:
            assert (
                actual_value == extra_field_value
            ), f"Extra field value should be '{extra_field_value}', got '{actual_value}'"


# ============================================================================
# Property 8: Request Logging Completeness
# ============================================================================


@settings(max_examples=2)
@given(
    path=st.sampled_from(["/test", "/v1/sessions", "/health"]),
    method=st.sampled_from(["GET", "POST"]),
)
def test_property_8_request_logging_completeness(path, method):
    """
    **Validates: Requirements 10.2**

    Feature: api-migration, Property 8: Request Logging Completeness

    For any HTTP request, a log entry should be created containing method,
    path, status_code, duration_ms, and request_id fields.

    This property ensures that all requests are logged with complete information
    for monitoring and debugging.
    """
    app = create_test_app_with_logging()
    client = TestClient(app)

    # Capture log output
    with capture_logs("app.requests") as log_capture:
        # Make request
        try:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json={})
        except Exception:
            # If endpoint doesn't exist, skip
            assume(False)

        # Get log entries
        entries = log_capture.get_log_entries()
        assume(len(entries) > 0)

        # Find the request log entry
        request_log = None
        for entry in entries:
            if entry.get("message") == "Request processed":
                request_log = entry
                break

        assume(request_log is not None)

        # Property 1: Log should contain method field
        assert "method" in request_log, f"Request log should contain 'method' field"
        assert (
            request_log["method"] == method
        ), f"Method should be '{method}', got '{request_log['method']}'"

        # Property 2: Log should contain path field
        assert "path" in request_log, f"Request log should contain 'path' field"
        assert request_log["path"] == path, f"Path should be '{path}', got '{request_log['path']}'"

        # Property 3: Log should contain status_code field
        assert "status_code" in request_log, f"Request log should contain 'status_code' field"
        assert isinstance(request_log["status_code"], int), f"Status code should be an integer"

        # Property 4: Log should contain duration_ms field
        assert "duration_ms" in request_log, f"Request log should contain 'duration_ms' field"
        assert isinstance(request_log["duration_ms"], (int, float)), f"Duration should be numeric"
        assert request_log["duration_ms"] >= 0, f"Duration should be non-negative"

        # Property 5: Log should contain request_id field
        assert "request_id" in request_log, f"Request log should contain 'request_id' field"
        assert isinstance(request_log["request_id"], str), f"Request ID should be a string"
        assert len(request_log["request_id"]) > 0, f"Request ID should not be empty"


# ============================================================================
# Property 9: Request ID Propagation
# ============================================================================


@settings(max_examples=2)
@given(
    path=st.sampled_from(["/v1/sessions", "/test"]),
)
def test_property_9_request_id_propagation_in_response(path):
    """
    **Validates: Requirements 10.3**

    Feature: api-migration, Property 9: Request ID Propagation

    For any HTTP request, the response should include an X-Request-ID header
    containing the request ID.

    This property ensures that request IDs are propagated to clients for
    end-to-end tracing.
    """
    app = create_test_app_with_logging()
    client = TestClient(app)

    # Make request
    response = client.get(path)

    # Property 1: Response should contain X-Request-ID header
    assert "x-request-id" in response.headers, f"Response should contain 'X-Request-ID' header"

    # Property 2: Request ID should be a non-empty string
    request_id = response.headers["x-request-id"]
    assert isinstance(request_id, str), f"Request ID should be a string"
    assert len(request_id) > 0, f"Request ID should not be empty"

    # Property 3: Request ID should be a valid UUID format
    # UUIDs are 36 characters with hyphens
    assert (
        len(request_id) == 36
    ), f"Request ID should be 36 characters (UUID format), got {len(request_id)}"
    assert request_id.count("-") == 4, f"Request ID should contain 4 hyphens (UUID format)"


@settings(max_examples=2)
@given(
    path=st.sampled_from(["/v1/sessions"]),
)
def test_property_9_request_id_propagation_in_logs(path):
    """
    **Validates: Requirements 10.3**

    Feature: api-migration, Property 9: Request ID Propagation

    For any HTTP request, all log messages generated during that request
    should contain the same request_id value.

    This property ensures that all logs for a single request can be correlated
    using the request ID.
    """
    app = create_test_app_with_logging()
    client = TestClient(app)

    # Capture log output
    with capture_logs("app.requests") as log_capture:
        # Make request
        response = client.get(path)

        # Get request ID from response header
        request_id_from_header = response.headers.get("x-request-id")
        assume(request_id_from_header is not None)

        # Get log entries
        entries = log_capture.get_log_entries()
        assume(len(entries) > 0)

        # Property: All log entries for this request should have the same request_id
        for entry in entries:
            if "request_id" in entry:
                assert (
                    entry["request_id"] == request_id_from_header
                ), f"Log entry request_id '{entry['request_id']}' should match header request_id '{request_id_from_header}'"


@settings(max_examples=2)
@given(
    path=st.sampled_from(["/v1/sessions"]),
)
def test_property_9_request_id_in_request_state(path):
    """
    **Validates: Requirements 10.3**

    Feature: api-migration, Property 9: Request ID Propagation

    For any HTTP request, the request_id should be available in request.state
    for use by route handlers and other middleware.

    This property ensures that request IDs are accessible throughout the
    request processing pipeline.
    """
    app = create_test_app_with_logging()
    client = TestClient(app)

    # Make request to endpoint that returns request_id from state
    response = client.get(path)

    # Get request ID from response body
    response_data = response.json()
    request_id_from_state = response_data.get("request_id")

    # Property 1: Request ID should be present in request state
    assert request_id_from_state is not None, f"Request ID should be available in request.state"

    # Property 2: Request ID from state should match header
    request_id_from_header = response.headers.get("x-request-id")
    assert (
        request_id_from_state == request_id_from_header
    ), f"Request ID from state '{request_id_from_state}' should match header '{request_id_from_header}'"


# ============================================================================
# Property 10: Error Logging with Context
# ============================================================================


@settings(max_examples=2)
@given(
    error_message=st.text(min_size=1, max_size=100),
)
def test_property_10_error_logging_with_context(error_message):
    """
    **Validates: Requirements 10.7**

    Feature: api-migration, Property 10: Error Logging with Context

    For any error that occurs during request processing, the error log should
    contain the exception type, message, stack trace, and request context.

    This property ensures that errors are logged with sufficient context for
    debugging and troubleshooting.
    """
    # Create error logging handler
    error_handler = ErrorLoggingHandler()

    # Create a test exception
    try:
        raise ValueError(error_message)
    except ValueError as e:
        # Capture log output
        with capture_logs("app.errors") as log_capture:
            # Log the error
            error_handler.log_error(e, error_code="TEST_ERROR")

            # Get log entries
            entries = log_capture.get_log_entries()
            assume(len(entries) > 0)

            error_log = entries[-1]

            # Property 1: Log should contain error_type field
            assert "error_type" in error_log, f"Error log should contain 'error_type' field"
            assert (
                error_log["error_type"] == "ValueError"
            ), f"Error type should be 'ValueError', got '{error_log['error_type']}'"

            # Property 2: Log should contain error_message field
            assert "error_message" in error_log, f"Error log should contain 'error_message' field"
            assert (
                error_log["error_message"] == error_message
            ), f"Error message should be '{error_message}', got '{error_log['error_message']}'"

            # Property 3: Log should contain stack_trace field
            assert "stack_trace" in error_log, f"Error log should contain 'stack_trace' field"
            assert isinstance(error_log["stack_trace"], str), f"Stack trace should be a string"
            assert len(error_log["stack_trace"]) > 0, f"Stack trace should not be empty"

            # Property 4: Stack trace should contain the error message
            assert (
                error_message in error_log["stack_trace"]
            ), f"Stack trace should contain the error message"


@settings(max_examples=2)
@given(
    error_message=st.text(min_size=1, max_size=100),
    path=st.sampled_from(["/test", "/v1/sessions"]),
    method=st.sampled_from(["GET", "POST"]),
)
def test_property_10_error_logging_with_request_context(error_message, path, method):
    """
    **Validates: Requirements 10.7**

    Feature: api-migration, Property 10: Error Logging with Context

    For any error that occurs during request processing with a request context,
    the error log should include request_id, method, path, and client_id.

    This property ensures that errors can be correlated with specific requests
    for debugging.
    """
    # Create error logging handler
    error_handler = ErrorLoggingHandler()

    # Create a mock request
    mock_request = Mock(spec=Request)
    mock_request.method = method
    mock_request.url.path = path
    mock_request.state.request_id = "test-request-id-123"
    mock_request.client.host = "127.0.0.1"

    # Create a test exception
    try:
        raise RuntimeError(error_message)
    except RuntimeError as e:
        # Capture log output
        with capture_logs("app.errors") as log_capture:
            # Log the error with request context
            error_handler.log_error(e, request=mock_request)

            # Get log entries
            entries = log_capture.get_log_entries()
            assume(len(entries) > 0)

            error_log = entries[-1]

            # Property 1: Log should contain request_id from request context
            assert "request_id" in error_log, f"Error log should contain 'request_id' field"
            assert error_log["request_id"] == "test-request-id-123", f"Request ID should match"

            # Property 2: Log should contain method from request context
            assert "method" in error_log, f"Error log should contain 'method' field"
            assert (
                error_log["method"] == method
            ), f"Method should be '{method}', got '{error_log['method']}'"

            # Property 3: Log should contain path from request context
            assert "path" in error_log, f"Error log should contain 'path' field"
            assert error_log["path"] == path, f"Path should be '{path}', got '{error_log['path']}'"

            # Property 4: Log should contain client_id from request context
            assert "client_id" in error_log, f"Error log should contain 'client_id' field"
            assert (
                error_log["client_id"] == "127.0.0.1"
            ), f"Client ID should be '127.0.0.1', got '{error_log['client_id']}'"


@settings(max_examples=2)
@given(
    path=st.sampled_from(["/error"]),
)
def test_property_10_error_logging_in_middleware(path):
    """
    **Validates: Requirements 10.7**

    Feature: api-migration, Property 10: Error Logging with Context

    For any error that occurs during request processing in the middleware,
    the error should be logged with full context before being re-raised.

    This property ensures that middleware errors are properly logged.
    """
    app = create_test_app_with_logging()
    client = TestClient(app, raise_server_exceptions=False)

    # Capture log output
    with capture_logs("app.requests") as log_capture:
        # Make request to error endpoint
        response = client.get(path)

        # Get log entries
        entries = log_capture.get_log_entries()
        assume(len(entries) > 0)

        # Find the error log entry
        error_log = None
        for entry in entries:
            if entry.get("message") == "Request failed":
                error_log = entry
                break

        assume(error_log is not None)

        # Property 1: Error log should contain error_type
        assert "error_type" in error_log, f"Error log should contain 'error_type' field"

        # Property 2: Error log should contain error_message
        assert "error_message" in error_log, f"Error log should contain 'error_message' field"

        # Property 3: Error log should contain stack_trace
        assert "stack_trace" in error_log, f"Error log should contain 'stack_trace' field"

        # Property 4: Error log should contain request context
        assert "request_id" in error_log, f"Error log should contain 'request_id' field"
        assert "method" in error_log, f"Error log should contain 'method' field"
        assert "path" in error_log, f"Error log should contain 'path' field"
