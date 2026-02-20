"""
Rate Limiting Middleware

Middleware for enforcing rate limits on API requests.
"""

from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Optional

from app.middleware.logging import StructuredLogger
from app.services.rate_limiter import RateLimiter

logger = StructuredLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API requests.

    Checks rate limits before processing requests and adds rate limit
    headers to all responses.
    """

    _instance: Optional["RateLimitingMiddleware"] = None

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

        # Set global instance reference
        RateLimitingMiddleware._instance = self

    @classmethod
    def set_redis_client(cls, redis_client: redis.Redis):
        """
        Set Redis client on the global middleware instance.

        Args:
            redis_client: Redis client for rate limiting
        """
        if cls._instance:
            cls._instance.redis_client = redis_client
            cls._instance.rate_limiter = RateLimiter(redis_client)

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
        # Default rate limit headers (used when rate limiting is disabled or fails)
        rate_limit_headers = {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Reset": str(
                int((datetime.now(timezone.utc) + timedelta(seconds=60)).timestamp())
            ),
        }

        # Skip if rate limiting is disabled or not yet initialized
        if not self.enabled or not self.rate_limiter:
            response = await call_next(request)
            # Add default headers
            for header_name, header_value in rate_limit_headers.items():
                response.headers[header_name] = header_value
            return response

        # Skip for certain endpoints
        if self._should_skip_rate_limiting(request):
            response = await call_next(request)
            # Add default headers
            for header_name, header_value in rate_limit_headers.items():
                response.headers[header_name] = header_value
            return response

        # Get client and endpoint identifiers
        client_id = self._get_client_id(request)
        endpoint = self._get_endpoint_identifier(request)

        try:
            # Check rate limit - combine client and endpoint into key
            rate_limit_key = f"{client_id}:{endpoint}"
            allowed, remaining, reset_time = await self.rate_limiter.check_rate_limit(
                rate_limit_key
            )

            # Safely calculate reset timestamp
            try:
                reset_timestamp = int(datetime.now(timezone.utc).timestamp() + reset_time)
                if reset_timestamp < 0:
                    reset_timestamp = int(
                        (datetime.now(timezone.utc) + timedelta(seconds=60)).timestamp()
                    )
            except (TypeError, ValueError):
                reset_timestamp = int(
                    (datetime.now(timezone.utc) + timedelta(seconds=60)).timestamp()
                )

            # Update rate limit headers with actual values
            rate_limit_headers.update(
                {
                    "X-RateLimit-Limit": "60",  # Default limit
                    "X-RateLimit-Remaining": str(max(0, remaining)),
                    "X-RateLimit-Reset": str(reset_timestamp),
                }
            )

            if not allowed:
                # Rate limit exceeded - return 429
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    endpoint=endpoint,
                    limit=60,
                    retry_after=reset_time,
                )

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                            "details": {
                                "limit": 60,
                                "retry_after": reset_time,
                                "reset_at": (
                                    datetime.now(timezone.utc) + timedelta(seconds=reset_time)
                                ).isoformat()
                                + "Z",
                            },
                        }
                    },
                    headers=rate_limit_headers,
                )

        except Exception as e:
            # Log error but continue with default headers
            logger.error(
                "Rate limiting error", error=str(e), client_id=client_id, endpoint=endpoint
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in rate_limit_headers.items():
            response.headers[header_name] = header_value

        return response
