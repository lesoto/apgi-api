"""
Extended coverage tests for app/middleware/request_size_limit.py
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from starlette.responses import Response

from app.middleware.request_size_limit import RequestSizeLimitMiddleware


@pytest.mark.asyncio
async def test_endpoint_specific_limit():
    """Test that endpoint-specific limits are applied."""
    app = AsyncMock()
    middleware = RequestSizeLimitMiddleware(app, max_size_mb=10)

    # Path with larger limit
    mock_request = MagicMock(spec=Request)
    mock_request.method = "POST"
    mock_request.url.path = "/v1/sessions/upload"
    mock_request.headers = {"content-length": "20000000"}  # ~20MB, which is < 50MB but > 10MB

    call_next = AsyncMock(return_value=Response())

    response = await middleware.dispatch(mock_request, call_next)
    assert response.status_code != 413
    call_next.assert_called_once()


@pytest.mark.asyncio
async def test_request_too_large_content_length():
    """Test rejection based on content-length header."""
    app = AsyncMock()
    middleware = RequestSizeLimitMiddleware(app, max_size_mb=1)

    mock_request = MagicMock(spec=Request)
    mock_request.method = "POST"
    mock_request.url.path = "/any"
    mock_request.headers = {"content-length": "2000000"}  # ~2MB

    call_next = AsyncMock()

    response = await middleware.dispatch(mock_request, call_next)
    assert response.status_code == 413
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_request_too_large_body_stream():
    """Test rejection based on actual body stream size."""
    app = AsyncMock()
    middleware = RequestSizeLimitMiddleware(app, max_size_mb=1)

    mock_request = MagicMock(spec=Request)
    mock_request.method = "POST"
    mock_request.url.path = "/any"
    # No content-length, or invalid
    mock_request.headers = {"content-length": "invalid"}
    mock_request.body = AsyncMock(return_value=b"a" * 2000000)  # ~2MB

    call_next = AsyncMock()

    response = await middleware.dispatch(mock_request, call_next)
    assert response.status_code == 413
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_request_size_check_exception_fallback():
    """Test that it continues if body reading fails."""
    app = AsyncMock()
    middleware = RequestSizeLimitMiddleware(app, max_size_mb=1)

    mock_request = MagicMock(spec=Request)
    mock_request.method = "POST"
    mock_request.url.path = "/any"
    mock_request.headers = {}
    mock_request.body = AsyncMock(side_effect=Exception("Stream error"))

    call_next = AsyncMock(return_value=Response())

    response = await middleware.dispatch(mock_request, call_next)
    assert response.status_code != 413
    call_next.assert_called_once()
