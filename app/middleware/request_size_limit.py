"""
Request Size Limit Middleware

Middleware for limiting the size of incoming requests.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.middleware.logging import StructuredLogger

logger = StructuredLogger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size to prevent DoS attacks.

    Rejects requests with body size exceeding configured limits.
    """

    def __init__(self, app: Any, max_size_mb: int = 10, enabled: bool = True) -> None:
        """
        Initialize request size limiting middleware.

        Args:
            app: FastAPI application
            max_size_mb: Maximum request body size in megabytes
            enabled: Whether size limiting is enabled
        """
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024  # Convert to bytes
        self.enabled = enabled
        self.max_size_mb = max_size_mb

        # Per-endpoint size limits in MB
        self.endpoint_limits = {
            "/v1/sessions/upload": 50,  # Example: allow larger uploads for sessions
            "/v1/admin/import": 100,  # Example: allow even larger for admin import
        }

    def _should_check_size(self, request: Request) -> bool:
        """
        Determine if request size should be checked.

        Args:
            request: HTTP request

        Returns:
            True if size should be checked
        """
        # Skip size check for methods that don't have bodies
        if request.method in ["GET", "HEAD", "OPTIONS", "DELETE"]:
            return False

        # Check content-length header if available
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    return True  # We can reject immediately
                elif size == 0:
                    return False  # No body to check
            except ValueError:
                pass  # Invalid content-length, proceed with stream check

        return True

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """
        Process request with size limiting.

        Args:
            request: HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response or 413 if request too large
        """
        # Skip if size limiting is disabled
        if not self.enabled:
            return await call_next(request)

        # Get applicable limit for this endpoint
        path = request.url.path
        limit_mb = self.max_size_mb
        for ep, ep_limit in self.endpoint_limits.items():
            if path.startswith(ep):
                limit_mb = ep_limit
                break

        limit_bytes = limit_mb * 1024 * 1024

        # Check if we should validate size for this request
        if not self._should_check_size(request):
            return await call_next(request)

        # Check content-length header first (most efficient)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > limit_bytes:
                    logger.warning(
                        "Request rejected due to content-length",
                        method=request.method,
                        path=request.url.path,
                        content_length=size,
                        max_size=limit_bytes,
                    )

                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "REQUEST_TOO_LARGE",
                                "message": f"Request body too large. Maximum size is {limit_mb}MB",
                                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                                "details": {
                                    "max_size_mb": limit_mb,
                                    "actual_size_bytes": size,
                                },
                            }
                        },
                    )
            except ValueError:
                pass  # Invalid content-length, proceed with stream check

        # For requests without content-length or with invalid header,
        # we need to check the actual stream
        try:
            # Get the request body stream
            body = await request.body()

            if len(body) > limit_bytes:
                logger.warning(
                    "Request rejected due to body size",
                    method=request.method,
                    path=request.url.path,
                    body_size=len(body),
                    max_size=limit_bytes,
                )

                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": f"Request body too large. Maximum size is {limit_mb}MB",
                            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                            "details": {
                                "max_size_mb": limit_mb,
                                "actual_size_bytes": len(body),
                            },
                        }
                    },
                )

        except Exception as e:
            logger.error(
                "Error checking request size",
                method=request.method,
                path=request.url.path,
                error=str(e),
            )

            # If we can't check the size, allow the request but log the error
            # (this prevents breaking the application due to middleware errors)
            pass

        # Process request
        return await call_next(request)
