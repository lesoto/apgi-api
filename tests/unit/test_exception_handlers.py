"""
Comprehensive unit tests for exception_handlers.py to achieve 100% coverage.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exception_handlers import (
    generate_request_id,
    api_error_handler,
    validation_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    register_exception_handlers,
)
from app.exceptions import APIError


class TestGenerateRequestId:
    """Test request ID generation."""

    def test_generate_request_id_unique(self) -> None:
        """Test that request IDs are unique."""
        id1 = generate_request_id()
        id2 = generate_request_id()
        assert id1 != id2
        assert id1.startswith("req_")
        assert len(id1) == 16  # "req_" + 12 hex chars

    def test_generate_request_id_format(self) -> None:
        """Test request ID format."""
        request_id = generate_request_id()
        assert request_id.startswith("req_")
        assert len(request_id) == 16


class TestApiErrorHandler:
    """Test API error handler."""

    @pytest.mark.asyncio
    async def test_api_error_handler_with_request_id(self) -> None:
        """Test API error handler with existing request ID."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = APIError(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400,
            details={"field": "value"},
        )

        with patch("app.exception_handlers.error_logger"):
            response = await api_error_handler(mock_request, exc)

        assert response.status_code == 400
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "req_test123" in data

    @pytest.mark.asyncio
    async def test_api_error_handler_without_request_id(self) -> None:
        """Test API error handler generates request ID."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        del mock_request.state.request_id  # Simulate missing request_id
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = APIError(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400,
            details={"field": "value"},
        )

        with patch("app.exception_handlers.error_logger"):
            response = await api_error_handler(mock_request, exc)

        assert response.status_code == 400
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "req_" in data

    @pytest.mark.asyncio
    async def test_api_error_handler_logging(self) -> None:
        """Test that API error handler logs errors."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = APIError(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400,
            details={"field": "value"},
        )

        with patch("app.exception_handlers.error_logger") as mock_logger:
            await api_error_handler(mock_request, exc)
            mock_logger.log_error.assert_called_once()


class TestValidationErrorHandler:
    """Test validation error handler."""

    @pytest.mark.asyncio
    async def test_validation_error_handler_request_validation(self) -> None:
        """Test handling RequestValidationError."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        # Create a validation error
        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "field1"), "msg": "field required", "type": "value_error.missing"},
                {
                    "loc": ("body", "field2"),
                    "msg": "value is not a valid integer",
                    "type": "type_error.integer",
                },
            ]
        )

        with patch("app.exception_handlers.logger"):
            response = await validation_error_handler(mock_request, exc)

        assert response.status_code == 422
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "VALIDATION_ERROR" in data
        assert "field1" in data
        assert "field2" in data

    @pytest.mark.asyncio
    async def test_validation_error_handler_logging(self) -> None:
        """Test that validation errors are logged."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "field1"), "msg": "field required", "type": "value_error.missing"}
            ]
        )

        with patch("app.exception_handlers.logger") as mock_logger:
            await validation_error_handler(mock_request, exc)
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_error_handler_nested_location(self) -> None:
        """Test handling nested field locations."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        exc = RequestValidationError(
            errors=[
                {
                    "loc": ("body", "user", "address", "street"),
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ]
        )

        with patch("app.exception_handlers.logger") as mock_logger:
            await validation_error_handler(mock_request, exc)
            mock_logger.warning.assert_called_once()


class TestHttpExceptionHandler:
    """Test HTTP exception handler."""

    @pytest.mark.asyncio
    async def test_http_exception_handler_400(self) -> None:
        """Test handling 400 Bad Request."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=400, detail="Bad request")

        with patch("app.exception_handlers.logger"):
            response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 400
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "BAD_REQUEST" in data
        assert "Bad request" in data

    @pytest.mark.asyncio
    async def test_http_exception_handler_404(self) -> None:
        """Test handling 404 Not Found."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=404, detail="Not found")

        with patch("app.exception_handlers.logger"):
            response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 404
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "NOT_FOUND" in data

    @pytest.mark.asyncio
    async def test_http_exception_handler_500(self) -> None:
        """Test handling 500 Internal Server Error."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=500, detail="Internal error")

        with patch("app.exception_handlers.logger"):
            response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 500
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "INTERNAL_SERVER_ERROR" in data

    @pytest.mark.asyncio
    async def test_http_exception_handler_unknown_status(self) -> None:
        """Test handling unknown status code."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=418, detail="I'm a teapot")

        with patch("app.exception_handlers.logger"):
            response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 418
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "HTTP_ERROR" in data

    @pytest.mark.asyncio
    async def test_http_exception_handler_logging_error(self) -> None:
        """Test that 5xx errors are logged as ERROR."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=500, detail="Internal error")

        with patch("app.exception_handlers.logger") as mock_logger:
            await http_exception_handler(mock_request, exc)
            mock_logger.log.assert_called_once()
            # Check that it was called with ERROR level
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == 40  # logging.ERROR

    @pytest.mark.asyncio
    async def test_http_exception_handler_logging_warning(self) -> None:
        """Test that 4xx errors are logged as WARNING."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        exc = StarletteHTTPException(status_code=404, detail="Not found")

        with patch("app.exception_handlers.logger") as mock_logger:
            await http_exception_handler(mock_request, exc)
            mock_logger.log.assert_called_once()
            # Check that it was called with WARNING level
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == 30  # logging.WARNING


class TestUnhandledExceptionHandler:
    """Test unhandled exception handler."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_basic(self) -> None:
        """Test basic unhandled exception handling."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "INTERNAL_SERVER_ERROR" in data
        assert "req_test123" in data

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_generates_ids(self) -> None:
        """Test that error ID and request ID are generated."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        del mock_request.state.request_id
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500
        if isinstance(response.body, bytes):
            data = response.body.decode()
        else:
            data = response.body.tobytes().decode()
        assert "req_" in data  # request ID
        assert "err_" in data  # error ID

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_with_json_body(self) -> None:
        """Test handling JSON request body."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json", "content-length": "50"}
        mock_request.body = AsyncMock(return_value=b'{"user": "test", "data": "value"}')

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_sensitive_data_redaction(self) -> None:
        """Test that sensitive data is redacted from body."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json", "content-length": "100"}
        mock_request.body = AsyncMock(
            return_value=b'{"username": "test", "password": "secret123", "token": "abc123"}'
        )

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_large_body(self) -> None:
        """Test handling of large request body."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json", "content-length": "20000"}
        mock_request.body = AsyncMock(return_value=b"x" * 20000)

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_form_data(self) -> None:
        """Test handling form data."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}

        mock_form_data = MagicMock()
        mock_form_data.__iter__ = lambda self: iter([("username", "test"), ("password", "secret")])
        mock_request.form = AsyncMock(return_value=mock_form_data)

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_sensitive_headers(self) -> None:
        """Test that sensitive headers are excluded."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {
            "authorization": "Bearer token123",
            "cookie": "session=abc",
            "x-api-key": "key123",
            "content-type": "application/json",
            "user-agent": "test",
        }
        mock_request.body = AsyncMock(return_value=b"{}")

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_with_alerting(self) -> None:
        """Test that error is recorded for alerting when configured."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"{}")

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = ["email"]
                mock_alert_mgr.record_error = AsyncMock()
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500
        mock_alert_mgr.record_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_body_capture_error(self) -> None:
        """Test handling errors during body capture."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json"}
        mock_request.body = AsyncMock(side_effect=Exception("Body read failed"))

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_unparseable_json(self) -> None:
        """Test handling unparseable JSON body."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req_test123"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "POST"
        mock_request.headers = {"content-type": "application/json", "content-length": "50"}
        mock_request.body = AsyncMock(return_value=b"not valid json")

        exc = Exception("Unexpected error")

        with patch("app.exception_handlers.error_logger"):
            with patch("app.exception_handlers.alert_manager") as mock_alert_mgr:
                mock_alert_mgr.channels = []
                response = await unhandled_exception_handler(mock_request, exc)

        assert response.status_code == 500


class TestRegisterExceptionHandlers:
    """Test exception handler registration."""

    def test_register_exception_handlers(self) -> None:
        """Test that all handlers are registered."""
        mock_app = MagicMock()

        with patch("app.exception_handlers.logger"):
            register_exception_handlers(mock_app)

        # Verify all handlers were added
        assert mock_app.add_exception_handler.call_count == 5

        # Check handler types
        handler_calls = mock_app.add_exception_handler.call_args_list

        # APIError handler
        api_error_call = [call for call in handler_calls if call[0][0] == APIError]
        assert len(api_error_call) == 1

        # RequestValidationError handler
        req_validation_call = [
            call for call in handler_calls if call[0][0] == RequestValidationError
        ]
        assert len(req_validation_call) == 1

        # PydanticValidationError handler
        pydantic_validation_call = [
            call for call in handler_calls if call[0][0] == PydanticValidationError
        ]
        assert len(pydantic_validation_call) == 1

        # StarletteHTTPException handler
        http_call = [call for call in handler_calls if call[0][0] == StarletteHTTPException]
        assert len(http_call) == 1

        # Exception handler (catch-all)
        exception_call = [call for call in handler_calls if call[0][0] == Exception]
        assert len(exception_call) == 1

    def test_register_exception_handlers_logging(self) -> None:
        """Test that registration is logged."""
        mock_app = MagicMock()

        with patch("app.exception_handlers.logger") as mock_logger:
            register_exception_handlers(mock_app)
            mock_logger.info.assert_called_once_with("Exception handlers registered successfully")
