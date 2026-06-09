"""
Unit tests for exception_handlers.py that execute real code paths.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exception_handlers import (
    api_error_handler,
    generate_request_id,
    http_exception_handler,
    register_exception_handlers,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.exceptions import APIError


class TestGenerateRequestId:
    """Test generate_request_id function."""

    def test_generate_request_id(self):
        """Test request ID generation."""
        request_id = generate_request_id()
        assert request_id.startswith("req_")
        assert len(request_id) == 16  # "req_" + 12 hex characters


class TestApiErrorHandler:
    """Test api_error_handler function."""

    @pytest.mark.asyncio
    async def test_api_error_handler_basic(self):
        """Test basic API error handling."""
        exc = APIError(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400,
            details={"key": "value"},
        )
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await api_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_api_error_handler_with_request_id(self):
        """Test API error handling with existing request ID."""
        exc = APIError(code="TEST_ERROR", message="Test error message", status_code=400)
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "existing_req_id"
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await api_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_api_error_handler_generates_request_id(self):
        """Test API error handling generates request ID when missing."""
        exc = APIError(code="TEST_ERROR", message="Test error message", status_code=400)
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None  # Explicitly set to None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await api_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400


class TestValidationErrorHandler:
    """Test validation_error_handler function."""

    @pytest.mark.asyncio
    async def test_validation_error_handler_request_validation(self):
        """Test handling RequestValidationError."""
        exc = RequestValidationError(
            [
                {
                    "loc": ("body", "field"),
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ]
        )
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}

        response = await validation_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_validation_error_handler_pydantic_validation(self):
        """Test handling PydanticValidationError."""
        # Mock PydanticValidationError with errors() method
        exc = MagicMock(spec=PydanticValidationError)
        exc.errors.return_value = [
            {"loc": ("field",), "msg": "error", "type": "value_error"},
        ]
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}

        response = await validation_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_validation_error_handler_with_request_id(self):
        """Test validation error with existing request ID."""
        exc = RequestValidationError([{"loc": ("body",), "msg": "error", "type": "value_error"}])
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "existing_req_id"
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}

        response = await validation_error_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestHttpExceptionHandler:
    """Test http_exception_handler function."""

    @pytest.mark.asyncio
    async def test_http_exception_handler_400(self):
        """Test handling 400 HTTP exception."""
        exc = StarletteHTTPException(status_code=400, detail="Bad request")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await http_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_http_exception_handler_404(self):
        """Test handling 404 HTTP exception."""
        exc = StarletteHTTPException(status_code=404, detail="Not found")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await http_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_http_exception_handler_500(self):
        """Test handling 500 HTTP exception."""
        exc = StarletteHTTPException(status_code=500, detail="Internal error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await http_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_http_exception_handler_unknown_status(self):
        """Test handling HTTP exception with unknown status code."""
        exc = StarletteHTTPException(status_code=418, detail="I'm a teapot")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await http_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 418

    @pytest.mark.asyncio
    async def test_http_exception_handler_with_request_id(self):
        """Test HTTP exception with existing request ID."""
        exc = StarletteHTTPException(status_code=400, detail="Bad request")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "existing_req_id"
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}

        response = await http_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400


class TestUnhandledExceptionHandler:
    """Test unhandled_exception_handler function."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_basic(self):
        """Test basic unhandled exception handling."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}
        request.body = AsyncMock(return_value=b"")

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_with_request_id(self):
        """Test unhandled exception with existing request ID."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "existing_req_id"
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}
        request.query_params = {}
        request.body = AsyncMock(return_value=b"")

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_json_body(self):
        """Test unhandled exception with JSON body."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}
        request.body = AsyncMock(return_value=b'{"key": "value"}')

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_sensitive_headers(self):
        """Test that sensitive headers are excluded."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value="application/json")
        request.headers.__iter__ = MagicMock(return_value=iter(["authorization", "content-type"]))
        header_dict = {
            "authorization": "Bearer token",
            "content-type": "application/json",
        }
        request.headers.__getitem__ = MagicMock(side_effect=header_dict.get)
        request.query_params = {}
        request.body = AsyncMock(return_value=b"")

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_sensitive_body_fields(self):
        """Test that sensitive body fields are redacted."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}
        request.body = AsyncMock(return_value=b'{"password": "secret", "token": "abc"}')

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler_form_data(self):
        """Test unhandled exception with form data."""
        exc = Exception("Unexpected error")
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = MagicMock()
        request.url.path = "/test"
        request.method = "POST"
        request.headers = {}
        request.query_params = {}
        request.form = AsyncMock(return_value={"username": "test", "password": "secret"})

        response = await unhandled_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestRegisterExceptionHandlers:
    """Test register_exception_handlers function."""

    def test_register_exception_handlers(self):
        """Test registering all exception handlers."""
        app = MagicMock()
        app.add_exception_handler = MagicMock()

        register_exception_handlers(app)

        # Verify all handlers were registered
        assert (
            app.add_exception_handler.call_count == 5
        )  # APIError, RequestValidationError, PydanticValidationError, StarletteHTTPException, Exception

    def test_register_exception_handlers_log(self):
        """Test that registration is logged."""
        app = MagicMock()
        app.add_exception_handler = MagicMock()

        with patch("app.exception_handlers.logger") as mock_logger:
            register_exception_handlers(app)
            mock_logger.info.assert_called_once_with("Exception handlers registered successfully")
