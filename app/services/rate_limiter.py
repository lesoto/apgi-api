"""
Rate Limiter Service

Service for tracking and enforcing rate limits using Redis.
"""

import logging
import time
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter using Redis for distributed rate limiting.

    Tracks request counts per user/IP in sliding windows.
    """

    def __init__(self, redis_client: redis.Redis, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            redis_client: Async Redis client
            requests_per_minute: Maximum requests allowed per minute
        """
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute

    async def check_rate_limit(
        self, key: str, limit: Optional[int] = None
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit using sliding window.

        Args:
            key: Rate limit key (e.g., "user:123" or "ip:192.168.1.1")
            limit: Maximum requests allowed per minute (optional, uses instance default if not provided)

        Returns:
            Tuple of (allowed, remaining, reset_time)
            - allowed: True if request is allowed
            - remaining: Number of requests remaining in window
            - reset_time: Seconds until rate limit resets
        """
        limit = limit or self.requests_per_minute
        current_time = int(time.time())
        window_start = current_time - 60  # 1-minute sliding window
        redis_key = f"rate_limit:{key}"

        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Count current requests in window (before adding current)
            pipe.zcard(redis_key)

            # Add current request
            pipe.zadd(redis_key, {str(current_time): current_time})

            # Set expiration to clean up old keys
            pipe.expire(redis_key, 60)

            results = await pipe.execute()
            current_count = results[1]

            # Check if over limit (current_count includes the request we just added)
            allowed = current_count <= self.requests_per_minute
            remaining = max(0, self.requests_per_minute - current_count)
            reset_time = 60 - (current_time % 60)

            return allowed, remaining, reset_time

        except Exception as e:
            logger.error(f"Rate limit check failed for key {key}: {e}")
            # Fail closed - deny request if Redis is down for security
            return False, 0, 60

    async def increment(self, key: str) -> int:
        """
        Increment request count for key.

        Args:
            key: Rate limit key

        Returns:
            Current request count
        """
        current_time = int(time.time())
        window_start = current_time - 60
        redis_key = f"rate_limit:{key}"

        try:
            pipe = self.redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Add current request
            pipe.zadd(redis_key, {str(current_time): current_time})

            # Get current count
            pipe.zcard(redis_key)

            # Set expiration
            pipe.expire(redis_key, 60)

            results = await pipe.execute()
            return int(results[2])  # Current count after adding

        except Exception as e:
            logger.error(f"Rate limit increment failed for key {key}: {e}")
            return 1
