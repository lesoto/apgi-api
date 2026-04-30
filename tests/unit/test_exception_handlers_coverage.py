"""
Coverage tests for app/exception_handlers.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.exceptions import HTTPException

from app.exception_handlers import (
    api_error_handler,
    generate_request_id,
    http_exception_handler,
    register_exception_handlers,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.exceptions import APIError


@pytest.fixture
def mock_request():
    from unittest.mock import MagicMock

    from fastapi import Request

    # Create a proper mock that mimics FastAPI Request structure
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.request_id = "req_123"
    request.url.path = "/test"
    request.method = "GET"
    request.headers = {}
    request.body = AsyncMock(return_value=b"")
    request.form = AsyncMock(return_value={})
    return request


@pytest.mark.asyncio
async def test_api_error_handler(mock_request):
    """Test api_error_handler."""
    exc = APIError(code="TEST_ERROR", message="msg", status_code=400)
    print(f"DEBUG: exc type: {type(exc)}")
    print(f"DEBUG: to_dict result: {exc.to_dict(request_id='test')}")
    with patch("app.exception_handlers.error_logger") as mock_logger:
        response = await api_error_handler(mock_request, exc)
        assert response.status_code == 400
        assert mock_logger.log_error.called


@pytest.mark.asyncio
async def test_validation_error_handler(mock_request):
    """Test validation_error_handler."""
    exc = MagicMock()
    exc.errors.return_value = [{"loc": ("body", "field"), "msg": "error", "type": "type"}]
    response = await validation_error_handler(mock_request, exc)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_http_exception_handler(mock_request):
    """Test http_exception_handler."""
    exc = HTTPException(status_code=404, detail="Not Found")
    response = await http_exception_handler(mock_request, exc)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unhandled_exception_handler(mock_request):
    """Test unhandled_exception_handler with body redaction."""
    mock_request.headers = {"content-type": "application/json", "content-length": "10"}
    mock_request.body = AsyncMock(return_value=b'{"password": "secret", "other": "data"}')

    exc = Exception("Unexpected")
    with patch("app.exception_handlers.error_logger"):
        with patch("app.exception_handlers.alert_manager") as mock_alert:
            mock_alert.channels = ["slack"]
            mock_alert.record_error = AsyncMock()
            response = await unhandled_exception_handler(mock_request, exc)
            assert response.status_code == 500
            assert mock_alert.record_error.called
            # Verify redaction
            args, kwargs = mock_alert.record_error.call_args
            assert kwargs["metadata"]["body"]["password"] == "[REDACTED]"


def test_register_exception_handlers():
    """Test register_exception_handlers."""
    app = MagicMock()
    register_exception_handlers(app)
    assert app.add_exception_handler.called


def test_generate_request_id():
    """Test generate_request_id."""
    rid = generate_request_id()
    assert rid.startswith("req_")
    assert len(rid) > 10
