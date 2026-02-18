"""
API Versioning Middleware

Adds semantic versioning headers to all API responses.
"""

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.routes.version import CURRENT_VERSION, API_VERSION


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds API versioning headers to all responses.

    Requirements: 6.1, 6.4
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add API versioning headers to response.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response with versioning headers
        """
        # Get the response from the next middleware/handler
        response = await call_next(request)

        # Add semantic versioning headers
        response.headers["API-Version"] = CURRENT_VERSION
        response.headers["API-Version-Prefix"] = API_VERSION

        # Add content type version info for JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["Content-Type"] = f"application/json; version={CURRENT_VERSION}"

        return response
