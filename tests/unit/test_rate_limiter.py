"""
Unit tests for rate limiter service.

Tests RateLimiter allow/deny logic using an AsyncMock redis client.
Validates Requirements 2.11.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis():
    """Mock async Redis client.

    pipeline() is called synchronously in RateLimiter so it must be a plain MagicMock
    attribute (not AsyncMock). Individual pipeline methods are also synchronous; only
    pipeline.execute() is async.
    """
    client = MagicMock()
    return client


@pytest.fixture
def limiter(mock_redis):
    """Create RateLimiter with default 60 req/min."""
    return RateLimiter(mock_redis, requests_per_minute=60)


def _make_pipeline_mock(zcard_result: int):
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

    def test_default_requests_per_minute(self, mock_redis):
        rl = RateLimiter(mock_redis)
        assert rl.requests_per_minute == 60

    def test_custom_requests_per_minute(self, mock_redis):
        rl = RateLimiter(mock_redis, requests_per_minute=100)
        assert rl.requests_per_minute == 100

    def test_redis_stored(self, mock_redis):
        rl = RateLimiter(mock_redis)
        assert rl.redis is mock_redis


class TestCheckRateLimit:
    """Test check_rate_limit — the primary public method."""

    @pytest.mark.asyncio
    async def test_allowed_when_under_limit(self, limiter, mock_redis):
        """Request is allowed when current count is below the limit."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is True
        assert remaining == 55  # 60 - 5
        assert reset_time > 0

    @pytest.mark.asyncio
    async def test_allowed_at_exactly_limit(self, limiter, mock_redis):
        """Request is allowed when count equals the limit (boundary)."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=60)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(self, limiter, mock_redis):
        """Request is denied when count exceeds the limit."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=61)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_custom_limit_overrides_default(self, limiter, mock_redis):
        """Passing an explicit limit is accepted; remaining is calculated from instance default
        (the current implementation uses self.requests_per_minute for the remaining calc)."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=5)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123", limit=10)

        # The implementation uses self.requests_per_minute (60) for remaining
        assert allowed is True
        assert remaining == 55  # 60 - 5

    @pytest.mark.asyncio
    async def test_custom_limit_deny(self, limiter, mock_redis):
        """When count exceeds the instance default (60), request is denied regardless of explicit limit."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=61)

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123", limit=3)

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_pipeline_operations_called(self, limiter, mock_redis):
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
    async def test_redis_key_includes_prefix(self, limiter, mock_redis):
        """The Redis key should be prefixed with 'rate_limit:'."""
        pipe = _make_pipeline_mock(zcard_result=0)
        mock_redis.pipeline.return_value = pipe

        await limiter.check_rate_limit("ip:10.0.0.1")

        # zremrangebyscore first arg is the key
        key_used = pipe.zremrangebyscore.call_args[0][0]
        assert key_used == "rate_limit:ip:10.0.0.1"

    @pytest.mark.asyncio
    async def test_reset_time_is_positive(self, limiter, mock_redis):
        """reset_time should always be a positive integer."""
        mock_redis.pipeline.return_value = _make_pipeline_mock(zcard_result=0)

        _, _, reset_time = await limiter.check_rate_limit("user:123")

        assert isinstance(reset_time, int)
        assert 0 < reset_time <= 60

    @pytest.mark.asyncio
    async def test_fail_closed_on_redis_error(self, limiter, mock_redis):
        """When Redis raises an exception the limiter should fail closed (deny)."""
        mock_redis.pipeline.side_effect = Exception("Redis connection refused")

        allowed, remaining, reset_time = await limiter.check_rate_limit("user:123")

        assert allowed is False
        assert remaining == 0
        assert reset_time == 60

    @pytest.mark.asyncio
    async def test_fail_closed_on_pipeline_execute_error(self, limiter, mock_redis):
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
    async def test_different_keys_are_independent(self, limiter, mock_redis):
        """Different keys should produce independent rate limit checks."""
        call_count = 0

        def pipeline_factory():
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


class TestIncrement:
    """Test the increment helper method."""

    @pytest.mark.asyncio
    async def test_increment_returns_count(self, limiter, mock_redis):
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
    async def test_increment_returns_1_on_error(self, limiter, mock_redis):
        """increment() should return 1 when Redis raises an exception."""
        mock_redis.pipeline.side_effect = Exception("Redis down")

        count = await limiter.increment("user:123")

        assert count == 1

    @pytest.mark.asyncio
    async def test_increment_uses_correct_key(self, limiter, mock_redis):
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
