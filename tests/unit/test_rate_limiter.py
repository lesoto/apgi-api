"""
Unit tests for rate limiter service.

Tests RateLimiter allow/deny logic using an AsyncMock redis client.
Validates Requirements 2.11.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock async Redis client.

    pipeline() is called synchronously in RateLimiter so it must be a plain MagicMock
    attribute (not AsyncMock). Individual pipeline methods are also synchronous; only
    pipeline.execute() is async.
    """
    client = MagicMock()
    return client


@pytest.fixture
def limiter(mock_redis: MagicMock) -> RateLimiter:
    """Create RateLimiter with default 60 req/min."""
    return RateLimiter(mock_redis, requests_per_minute=60)


def _make_pipeline_mock(zcard_result: int) -> MagicMock:
    """Return a pipeline mock whose execute() returns [None, zcard_result, None, None].

    pipeline() is called synchronously in RateLimiter, so the pipeline object itself
    must be a MagicMock (not AsyncMock), but its execute() must be an AsyncMock.
    """
    pipe = MagicMock()
    pipe.zremrangebyscore = MagicMock()
    pipe.zcard = MagicMock()
    pipe.zadd = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[None, zcard_result, None, None])
    return pipe


class TestRateLimiterInit:
    """Test RateLimiter initialisation."""

    def test_default_requests_per_minute(self, mock_redis: MagicMock) -> None:
        rl = RateLimiter(mock_redis)
        assert rl.requests_per_minute == 60

    def test_custom_requests_per_minute(self, mock_redis: MagicMock) -> None:
        rl = RateLimiter(mock_redis, requests_per_minute=100)
        assert rl.requests_per_minute == 100

    def test_redis_stored(self, mock_redis: MagicMock) -> None:
        rl = RateLimiter(mock_redis)
        assert rl.redis is mock_redis


class TestCheckRateLimit:
    """Test check_rate_limit — the primary public method."""

    @pytest.mark.asyncio
    async def test_allowed_when_under_limit(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Request is allowed when current count is below the limit."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is True
        assert remaining == 55  # 60 - 5
        assert reset_time > 0

    @pytest.mark.asyncio
    async def test_allowed_at_exactly_limit(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Request is allowed when count equals the limit (boundary)."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=60)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Request is denied when count exceeds the limit."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=61)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_custom_limit_overrides_default(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Passing an explicit limit correctly enforces endpoint-specific limits.
        Remaining is calculated from the provided limit parameter, not instance default."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123", limit=10)

        # With the fix: uses provided limit (10), not self.requests_per_minute (60)
        assert allowed is True
        assert remaining == 5  # 10 - 5

    @pytest.mark.asyncio
    async def test_custom_limit_deny(self, limiter: RateLimiter, mock_redis: MagicMock) -> None:
        """When count exceeds the custom limit, request is denied based on the custom limit, not instance default."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123", limit=3)

        # With the fix: correctly denies when count (5) exceeds custom limit (3)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_pipeline_operations_called(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Verify the pipeline executes the expected Redis operations."""
        pipe = _make_pipeline_mock(zcard_result=0)
        mock_redis.pipeline.return_value = pipe

        await limiter.check_rate_limit("user:abc")

        pipe.zremrangebyscore.assert_called_once()
        pipe.zcard.assert_called_once()
        pipe.zadd.assert_called_once()
        pipe.expire.assert_called_once()
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_key_includes_prefix(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """The Redis key should be prefixed with 'rate_limit:'."""
        pipe = _make_pipeline_mock(zcard_result=0)
        mock_redis.pipeline.return_value = pipe

        await limiter.check_rate_limit("ip:10.0.0.1")

        # zremrangebyscore first arg is the key
        key_used = pipe.zremrangebyscore.call_args[0][0]
        assert key_used == "rate_limit:ip:10.0.0.1"

    @pytest.mark.asyncio
    async def test_reset_time_is_positive(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """reset_time should always be a positive integer."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=0)

        _, _, reset_time = await limiter.check_rate_limit("user:123")

        assert isinstance(reset_time, int)
        assert 0 < reset_time <= 60

    @pytest.mark.asyncio
    async def test_fail_closed_on_redis_error(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """When Redis raises an exception the limiter should fail closed (deny)."""
        mock_redis.pipeline.side_effect = Exception("Redis connection refused")

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is False
        assert remaining == 0
        assert reset_time == 60

    @pytest.mark.asyncio
    async def test_fail_closed_on_pipeline_execute_error(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """When pipeline.execute() raises, the limiter should fail closed."""
        pipe = MagicMock()
        pipe.zremrangebyscore = MagicMock()
        pipe.zcard = MagicMock()
        pipe.zadd = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock(side_effect=Exception("timeout"))
        mock_redis.pipeline.return_value = pipe

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is False

    @pytest.mark.asyncio
    async def test_different_keys_are_independent(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """Different keys should produce independent rate limit checks."""
        call_count = 0

        def pipeline_factory() -> MagicMock:
            nonlocal call_count
            call_count += 1
            # First key: under limit; second key: over limit
            count = 5 if call_count == 1 else 100
            return _make_pipeline_mock(zcard_result=count)

        mock_redis.pipeline.side_effect = pipeline_factory

        allowed1, _, _ = await limiter.check_rate_limit("user:A")
        allowed2, _, _ = await limiter.check_rate_limit("user:B")

        assert allowed1 is True
        assert allowed2 is False


class TestEndpointSpecificRateLimits:
    """Regression tests for endpoint-specific rate limit enforcement.

    These tests verify that the rate limiter correctly enforces per-endpoint
    limits (e.g., auth:attempt=10, task:execute=5) rather than always using
    the global default (60).
    """

    @pytest.mark.asyncio
    async def test_auth_endpoint_strict_limit_enforced(self, mock_redis: MagicMock) -> None:
        """Auth attempts endpoint should enforce limit=10, not default=60."""
        limiter = RateLimiter(mock_redis, requests_per_minute=60)
        # 8 requests made, limit=10 -> should allow (was buggy: used 60)
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=8)

        allowed, remaining, _ = await limiter.check_rate_limit("user:123:auth:attempt", limit=10)

        assert allowed is True
        assert remaining == 2  # 10 - 8

    @pytest.mark.asyncio
    async def test_auth_endpoint_deny_when_over_strict_limit(self, mock_redis: MagicMock) -> None:
        """Auth attempts should be denied when count exceeds strict limit=10."""
        limiter = RateLimiter(mock_redis, requests_per_minute=60)
        # 12 requests made, limit=10 -> should deny (was buggy: allowed up to 60)
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=12)

        allowed, remaining, _ = await limiter.check_rate_limit("user:123:auth:attempt", limit=10)

        assert allowed is False  # BUG FIX: now correctly denies
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_task_execute_very_strict_limit(self, mock_redis: MagicMock) -> None:
        """Task execution endpoint should enforce limit=5."""
        limiter = RateLimiter(mock_redis, requests_per_minute=60)
        # 6 requests made, limit=5 -> should deny
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=6)

        allowed, remaining, _ = await limiter.check_rate_limit("user:123:task:execute", limit=5)

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_password_reset_strictest_limit(self, mock_redis: MagicMock) -> None:
        """Password reset endpoint should enforce limit=5."""
        limiter = RateLimiter(mock_redis, requests_per_minute=60)
        # 5 requests made, limit=5 -> should allow (boundary)
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, _ = await limiter.check_rate_limit(
            "user:123:users:reset-password", limit=5
        )

        assert allowed is True
        assert remaining == 0  # exactly at limit

    @pytest.mark.asyncio
    async def test_global_endpoint_uses_default_limit(self, mock_redis: MagicMock) -> None:
        """Global/default endpoints should still use the instance default (60)."""
        limiter = RateLimiter(mock_redis, requests_per_minute=60)
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=45)

        # No limit parameter passed - should use default
        allowed, remaining, _ = await limiter.check_rate_limit("user:123:global")

        assert allowed is True
        assert remaining == 15  # 60 - 45


class TestIncrement:
    """Test the increment helper method."""

    @pytest.mark.asyncio
    async def test_increment_returns_count(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """increment() should return the current request count."""
        pipe = MagicMock()
        pipe.zremrangebyscore = MagicMock()
        pipe.zadd = MagicMock()
        pipe.zcard = MagicMock()
        pipe.expire = MagicMock()
        # Results: [zremrangebyscore, zadd, zcard, expire]
        pipe.execute = AsyncMock(return_value=[None, None, 7, None])
        mock_redis.pipeline.return_value = pipe

        count = await limiter.increment("user:123")

        assert count == 7

    @pytest.mark.asyncio
    async def test_increment_returns_1_on_error(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """increment() should return 1 when Redis raises an exception."""
        mock_redis.pipeline.side_effect = Exception("Redis down")

        count = await limiter.increment("user:123")

        assert count == 1

    @pytest.mark.asyncio
    async def test_increment_uses_correct_key(
        self, limiter: RateLimiter, mock_redis: MagicMock
    ) -> None:
        """increment() should use the 'rate_limit:' prefixed key."""
        pipe = MagicMock()
        pipe.zremrangebyscore = MagicMock()
        pipe.zadd = MagicMock()
        pipe.zcard = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock(return_value=[None, None, 1, None])
        mock_redis.pipeline.return_value = pipe

        await limiter.increment("mykey")

        key_used = pipe.zremrangebyscore.call_args[0][0]
        assert key_used == "rate_limit:mykey"
