"""
Rate Limiting Middleware

Middleware for enforcing rate limits on API requests.
"""

from datetime import datetime

import redis.asyncio as redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.middleware.logging import StructuredLogger
from app.services.rate_limiter import RateLimiter

logger = StructuredLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API requests.

    Checks rate limits before processing requests and adds rate limit
    headers to all responses.
    """

    def __init__(self, app, redis_client=None, enabled: bool = True):
        """
        Initialize rate limiting middleware.

        Args:
            app: FastAPI application
            redis_client: Redis client for rate limiting (can be None initially)
            enabled: Whether rate limiting is enabled
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.enabled = enabled
        self.rate_limiter = None

        # Initialize rate limitter when Redis client is available
        if redis_client:
            self.rate_limiter = RateLimiter(redis_client)

    def set_redis_client(self, redis_client: redis.Redis):
        """
        Set Redis client and initialize rate limiter.

        Args:
            redis_client: Redis client for rate limiting
        """
        self.redis_client = redis_client
        self.rate_limiter = RateLimiter(redis_client)

    def _get_client_id(self, request: Request) -> str:
        """
        Extract client identifier from request.

        Uses authenticated user ID if available, otherwise falls back to IP address.

        Args:
            request: HTTP request

        Returns:
            Client identifier string
        """
        # Try to get user ID from request state (set by authentication middleware)
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.user_id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _get_endpoint_identifier(self, request: Request) -> str:
        """
        Get endpoint identifier for rate limiting.

        Maps request paths to endpoint identifiers for rate limit configuration.

        Args:
            request: HTTP request

        Returns:
            Endpoint identifier string
        """
        path = request.url.path
        method = request.method

        # Map paths to endpoint identifiers
        if path.startswith("/v1/sessions") and method == "POST":
            if path.endswith("/tasks"):
                return "task:execute"
            return "session:create"
        elif path.startswith("/v1/sessions") and method == "GET":
            return "session:read"
        elif path.startswith("/v1/sessions") and method == "DELETE":
            return "session:delete"
        elif path.startswith("/v1/sessions") and "export" in path:
            return "data:export"
        elif path.startswith("/v1/tasks"):
            return "task:execute"
        else:
            return "global"

    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """
        Determine if rate limiting should be skipped for this request.

        Args:
            request: HTTP request

        Returns:
            True if rate limiting should be skipped
        """
        path = request.url.path

        # Skip rate limiting for health checks and metrics
        if path in ["/health", "/health/ready", "/health/live", "/metrics"]:
            return True

        # Skip for docs
        if path in ["/docs", "/redoc", "/openapi.json"]:
            return True

        return False

    async def dispatch(self, request: Request, call_next):
        """
        Process request with rate limiting.

        Args:
            request: HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response with rate limit headers
        """
        # Skip if rate limiting is disabled or not yet initialized
        if not self.enabled or not self.rate_limiter:
            return await call_next(request)

        # Skip for certain endpoints
        if self._should_skip_rate_limiting(request):
            return await call_next(request)

        # Get client and endpoint identifiers
        client_id = self._get_client_id(request)
        endpoint = self._get_endpoint_identifier(request)

        try:
            # Check rate limit
            result = await self.rate_limiter.check_rate_limit(
                client_id=client_id, endpoint=endpoint
            )

            # Get rate limit headers
            rate_limit_headers = self.rate_limiter.get_rate_limit_headers(result)

            if not result.allowed:
                # Rate limit exceeded - return 429
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    endpoint=endpoint,
                    limit=result.limit,
                    retry_after=result.retry_after,
                )

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "details": {
                                "limit": result.limit,
                                "retry_after": result.retry_after,
                                "reset_at": result.reset_at.isoformat() + "Z",
                            },
                        }
                    },
                    headers=rate_limit_headers,
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            for header_name, header_value in rate_limit_headers.items():
                response.headers[header_name] = header_value

            return response

        except Exception as e:
            # Log error but don't block request if rate limiting fails
            logger.error(
                "Rate limiting error", error=str(e), client_id=client_id, endpoint=endpoint
            )

            # Continue without rate limiting
            return await call_next(request)
