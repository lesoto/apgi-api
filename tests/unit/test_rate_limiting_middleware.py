"""
Unit tests for rate limiting middleware.
"""

import pytest
from unittest.mock import AsyncMock
from app.middleware.rate_limiting import RateLimitingMiddleware


class TestRateLimitingMiddleware:
    """Test rate limiting middleware."""

    @pytest.fixture
    def mock_app(self):
        """Mock ASGI app."""

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance."""
        return RateLimitingMiddleware(mock_app, enabled=True)

    @pytest.fixture
    def disabled_middleware(self, mock_app):
        """Create disabled middleware instance."""
        return RateLimitingMiddleware(mock_app, enabled=False)

    @pytest.mark.asyncio
    async def test_dispatch_enabled(self, middleware):
        """Test dispatch when rate limiting is enabled."""
        scope = {"type": "http", "method": "GET", "path": "/test"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_dispatch_disabled(self, disabled_middleware):
        """Test dispatch when rate limiting is disabled."""
        scope = {"type": "http", "method": "GET", "path": "/test"}
        receive = AsyncMock()
        send = AsyncMock()

        await disabled_middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_token_bucket_algorithm(self, middleware):
        """Test token bucket rate limiting algorithm."""
        user_id = "user123"
        limit = 100
        window = 60

        for i in range(100):
            is_allowed = middleware.check_rate_limit(user_id, limit, window)
            assert is_allowed is True

        is_allowed = middleware.check_rate_limit(user_id, limit, window)
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_sliding_window_rate_limiting(self, middleware):
        """Test sliding window rate limiting."""
        user_id = "user123"
        limit = 10
        window = 10

        for i in range(10):
            is_allowed = middleware.check_rate_limit(user_id, limit, window)
            assert is_allowed is True

        is_allowed = middleware.check_rate_limit(user_id, limit, window)
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_distributed_rate_limiting(self, middleware):
        """Test distributed rate limit coordination."""
        user_id = "user123"
        limit = 50
        window = 60

        is_allowed = middleware.check_distributed_rate_limit(user_id, limit, window)
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_admin_bypass(self, middleware):
        """Test admin bypass for rate limiting."""
        user_id = "admin123"
        limit = 10
        window = 60

        is_admin = True
        is_allowed = middleware.check_rate_limit(user_id, limit, window, is_admin=is_admin)
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_exemption_rules(self, middleware):
        """Test rate limit exemption rules."""
        user_id = "user123"
        limit = 10
        window = 60

        exemption_rules = {"user123": True}
        is_allowed = middleware.check_rate_limit(
            user_id, limit, window, exemption_rules=exemption_rules
        )
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_ip_based_rate_limiting(self, middleware):
        """Test IP-based rate limiting."""
        ip_address = "192.168.1.1"
        limit = 100
        window = 60

        for i in range(100):
            is_allowed = middleware.check_ip_rate_limit(ip_address, limit, window)
            assert is_allowed is True

        is_allowed = middleware.check_ip_rate_limit(ip_address, limit, window)
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_user_based_rate_limiting(self, middleware):
        """Test user-based rate limiting."""
        user_id = "user123"
        limit = 50
        window = 60

        for i in range(50):
            is_allowed = middleware.check_user_rate_limit(user_id, limit, window)
            assert is_allowed is True

        is_allowed = middleware.check_user_rate_limit(user_id, limit, window)
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self, middleware):
        """Test rate limit reset after window expires."""
        user_id = "user123"
        limit = 10
        window = 1

        for i in range(10):
            is_allowed = middleware.check_rate_limit(user_id, limit, window)
            assert is_allowed is True

        is_allowed = middleware.check_rate_limit(user_id, limit, window)
        assert is_allowed is False

        # Wait for window to expire (simulated)
        import asyncio

        await asyncio.sleep(1.1)

        is_allowed = middleware.check_rate_limit(user_id, limit, window)
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, middleware):
        """Test rate limit headers in response."""
        user_id = "user123"
        limit = 100
        window = 60

        headers = middleware.get_rate_limit_headers(user_id, limit, window)

        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    @pytest.mark.asyncio
    async def test_rate_limit_with_burst(self, middleware):
        """Test rate limit with burst allowance."""
        user_id = "user123"
        limit = 10
        window = 60
        burst = 5

        for i in range(15):
            is_allowed = middleware.check_rate_limit_with_burst(user_id, limit, window, burst)
            if i < 15:
                assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_priority_queue(self, middleware):
        """Test rate limit with priority queue."""
        user_id = "user123"
        limit = 10
        window = 60
        priority = "high"

        for i in range(15):
            is_allowed = middleware.check_rate_limit_with_priority(user_id, limit, window, priority)
            if i < 15:
                assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_multiple_endpoints(self, middleware):
        """Test rate limiting for multiple endpoints."""
        user_id = "user123"
        endpoint1_limit = 100
        endpoint2_limit = 50

        for i in range(100):
            is_allowed1 = middleware.check_endpoint_rate_limit(
                user_id, "/api/endpoint1", endpoint1_limit, 60
            )
            assert is_allowed1 is True

        is_allowed2 = middleware.check_endpoint_rate_limit(
            user_id, "/api/endpoint2", endpoint2_limit, 60
        )
        assert is_allowed2 is True

    @pytest.mark.asyncio
    async def test_rate_limit_block_duration(self, middleware):
        """Test rate limit block duration."""
        user_id = "user123"
        limit = 10
        window = 60
        block_duration = 300

        for i in range(11):
            middleware.check_rate_limit(user_id, limit, window)

        is_blocked = middleware.is_user_blocked(user_id)
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_rate_limit_whitelist(self, middleware):
        """Test rate limit whitelist."""
        user_id = "user123"
        limit = 10
        window = 60
        whitelist = {"user123"}

        for i in range(20):
            is_allowed = middleware.check_rate_limit(user_id, limit, window, whitelist=whitelist)
            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_blacklist(self, middleware):
        """Test rate limit blacklist."""
        user_id = "user123"
        limit = 10
        window = 60
        blacklist = {"user123"}

        is_allowed = middleware.check_rate_limit(user_id, limit, window, blacklist=blacklist)
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_tiered_limits(self, middleware):
        """Test tiered rate limits based on user tier."""
        user_id = "user123"
        user_tier = "premium"
        tier_limits = {"free": 100, "premium": 1000, "enterprise": 10000}

        limit = tier_limits[user_tier]
        for i in range(limit):
            is_allowed = middleware.check_tiered_rate_limit(user_id, user_tier, tier_limits, 60)
            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_geographic(self, middleware):
        """Test geographic rate limiting."""
        ip_address = "192.168.1.1"
        country = "US"
        limit = 100
        window = 60

        is_allowed = middleware.check_geographic_rate_limit(ip_address, country, limit, window)
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_anomaly_detection(self, middleware):
        """Test rate limit anomaly detection."""
        user_id = "user123"
        limit = 10
        window = 60

        # Normal usage pattern
        for i in range(10):
            middleware.check_rate_limit(user_id, limit, window)

        # Anomalous burst
        has_anomaly = middleware.detect_anomaly(user_id)
        assert has_anomaly is False

    @pytest.mark.asyncio
    async def test_rate_limit_adaptive(self, middleware):
        """Test adaptive rate limiting."""
        user_id = "user123"
        base_limit = 100
        window = 60

        # Adaptive limit increases for trusted users
        adaptive_limit = middleware.get_adaptive_limit(user_id, base_limit)
        assert adaptive_limit >= base_limit

    @pytest.mark.asyncio
    async def test_rate_limit_cleanup(self, middleware):
        """Test rate limit data cleanup."""
        user_id = "user123"

        middleware.cleanup_user_data(user_id)

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_rate_limit_stats(self, middleware):
        """Test rate limit statistics."""
        user_id = "user123"

        stats = middleware.get_user_stats(user_id)

        assert "requests" in stats
        assert "blocked" in stats
        assert "limit" in stats

    @pytest.mark.asyncio
    async def test_rate_limit_global_stats(self, middleware):
        """Test global rate limit statistics."""
        stats = middleware.get_global_stats()

        assert "total_requests" in stats
        assert "total_blocked" in stats
        assert "active_users" in stats

    @pytest.mark.asyncio
    async def test_rate_limit_config_update(self, middleware):
        """Test dynamic rate limit config update."""
        new_config = {"default_limit": 200, "default_window": 120}

        middleware.update_config(new_config)

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_rate_limit_health_check(self, middleware):
        """Test rate limiter health check."""
        is_healthy = middleware.health_check()

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_rate_limit_with_backpressure(self, middleware):
        """Test rate limiting with backpressure signaling."""
        user_id = "user123"
        limit = 10
        window = 60

        backpressure = middleware.check_backpressure(user_id, limit, window)
        assert backpressure["pressure"] >= 0

    @pytest.mark.asyncio
    async def test_rate_limit_circuit_breaker(self, middleware):
        """Test circuit breaker for rate limiting."""
        endpoint = "/api/test"
        failure_threshold = 5

        for i in range(failure_threshold):
            middleware.record_failure(endpoint)

        is_open = middleware.is_circuit_breaker_open(endpoint)
        assert is_open is True

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after(self, middleware):
        """Test retry-after header calculation."""
        user_id = "user123"
        limit = 10
        window = 60

        for i in range(11):
            middleware.check_rate_limit(user_id, limit, window)

        retry_after = middleware.get_retry_after(user_id)
        assert retry_after > 0

    def test_middleware_initialization(self, mock_app):
        """Test middleware initialization."""
        middleware = RateLimitingMiddleware(mock_app, enabled=True)

        assert middleware.enabled is True

    def test_middleware_initialization_disabled(self, mock_app):
        """Test middleware initialization with disabled rate limiting."""
        middleware = RateLimitingMiddleware(mock_app, enabled=False)

        assert middleware.enabled is False
