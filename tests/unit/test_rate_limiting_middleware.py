"""
Unit tests for app/middleware/rate_limiting.py

Tests the actual RateLimitingMiddleware ASGI interface, not a fictional API.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from app.middleware.rate_limiting import RateLimitingMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_scope(path: str = "/v1/sessions", method: str = "GET") -> dict[str, object]:
    """Build a minimal ASGI HTTP scope dict."""
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 50000),
    }


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestRateLimitingMiddlewareInit:
    """Test middleware initialization."""

    def test_init_enabled_default(self) -> None:
        """Middleware can be created with enabled=True."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        mock_app = AsyncMock()
        mw = RateLimitingMiddleware(mock_app, enabled=True)

        assert mw.enabled is True
        assert mw.redis_client is None
        assert mw.rate_limiter is None

    def test_init_disabled(self) -> None:
        """Middleware can be created with enabled=False."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        mock_app = AsyncMock()
        mw = RateLimitingMiddleware(mock_app, enabled=False)

        assert mw.enabled is False

    def test_init_with_redis_client(self) -> None:
        """When a redis_client is provided, rate_limiter is initialised."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        mock_app = AsyncMock()
        mock_redis = MagicMock()

        with patch("app.middleware.rate_limiting.RateLimiter") as MockRL:
            mw = RateLimitingMiddleware(mock_app, redis_client=mock_redis, enabled=True)

        MockRL.assert_called_once_with(mock_redis)
        assert mw.redis_client is mock_redis

    def test_set_redis_client(self) -> None:
        """set_redis_client() updates the singleton instance."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        mock_app = AsyncMock()
        mw = RateLimitingMiddleware(mock_app, enabled=True)

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter") as MockRL:
            RateLimitingMiddleware.set_redis_client(mock_redis)

        MockRL.assert_called_once_with(mock_redis)

    def test_endpoint_rates_configured(self) -> None:
        """Default endpoint_rates dictionary is present."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        mock_app = AsyncMock()
        mw = RateLimitingMiddleware(mock_app)

        assert "auth:attempt" in mw.endpoint_rates
        assert "global" in mw.endpoint_rates


# ---------------------------------------------------------------------------
# _get_client_id() tests
# ---------------------------------------------------------------------------


class TestGetClientId:
    """Test the _get_client_id private method."""

    def _make_mw(self) -> "RateLimitingMiddleware":
        from app.middleware.rate_limiting import RateLimitingMiddleware

        return RateLimitingMiddleware(AsyncMock(), enabled=True)

    def test_returns_user_id_when_authenticated(self) -> None:
        """Returns 'user:<id>' when request.state.user is set."""
        mw = self._make_mw()

        class _User:
            user_id = "abc123"

        class _State:
            user = _User()

        class _Request(MagicMock):
            def __init__(self) -> None:
                super().__init__()
                self.state = _State()
                self.client = MagicMock()
                self.headers: dict[str, str] = {}

            def __call__(self) -> None:
                pass

        result = mw._get_client_id(_Request())
        assert result == "user:abc123"

    def test_returns_ip_when_no_user(self) -> None:
        """Falls back to 'ip:<addr>' when no state.user."""
        mw = self._make_mw()

        request = MagicMock()
        # Make hasattr return False for 'user'
        del request.state.user
        request.client.host = "10.0.0.1"
        request.headers = {}

        result = mw._get_client_id(request)
        assert result.startswith("ip:")

    def test_returns_ip_unknown_when_no_client(self) -> None:
        """Falls back to 'ip:unknown' when no client info."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client = None
        request.headers = {}

        result = mw._get_client_id(request)
        assert result == "ip:unknown"


# ---------------------------------------------------------------------------
# _get_endpoint_identifier() tests
# ---------------------------------------------------------------------------


class TestGetEndpointIdentifier:
    """Test endpoint identification for rate limit categories."""

    def _make_mw(self) -> "RateLimitingMiddleware":
        from app.middleware.rate_limiting import RateLimitingMiddleware

        return RateLimitingMiddleware(AsyncMock(), enabled=True)

    def _req(self, path: str, method: str = "GET") -> MagicMock:
        request = MagicMock()
        request.url.path = path
        request.method = method
        return request

    def test_auth_path(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/auth/login")) == "auth:attempt"

    def test_register_path(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/users/register")) == "auth:attempt"

    def test_reset_password_path(self) -> None:
        mw = self._make_mw()
        assert (
            mw._get_endpoint_identifier(self._req("/v1/users/reset-password"))
            == "users:reset-password"
        )

    def test_session_create_post(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/sessions", "POST")) == "session:create"

    def test_session_tasks_post(self) -> None:
        mw = self._make_mw()
        assert (
            mw._get_endpoint_identifier(self._req("/v1/sessions/123/tasks", "POST"))
            == "task:execute"
        )

    def test_session_read_get(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/sessions", "GET")) == "session:read"

    def test_session_delete(self) -> None:
        mw = self._make_mw()
        assert (
            mw._get_endpoint_identifier(self._req("/v1/sessions/123", "DELETE")) == "session:delete"
        )

    def test_session_export_other_method(self) -> None:
        """Non-GET/POST/DELETE to sessions path with 'export' returns 'data:export'."""
        mw = self._make_mw()
        # The export branch is only reachable after POST/GET/DELETE checks – use PUT
        assert (
            mw._get_endpoint_identifier(self._req("/v1/sessions/123/export", "PUT"))
            == "data:export"
        )

    def test_tasks_path(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/tasks")) == "task:execute"

    def test_unknown_path_returns_global(self) -> None:
        mw = self._make_mw()
        assert mw._get_endpoint_identifier(self._req("/v1/unknown/path")) == "global"


# ---------------------------------------------------------------------------
# _should_skip_rate_limiting() tests
# ---------------------------------------------------------------------------


class TestTrustedProxy:
    """Test trusted proxy detection for X-Forwarded-For headers (Lines 111-122)."""

    def _make_mw(self) -> "RateLimitingMiddleware":
        from app.middleware.rate_limiting import RateLimitingMiddleware

        return RateLimitingMiddleware(AsyncMock(), enabled=True)

    def test_x_forwarded_for_from_localhost(self) -> None:
        """X-Forwarded-For trusted when from localhost (127.0.0.1)."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_from_10_network(self) -> None:
        """X-Forwarded-For trusted when from 10.0.0.0/8 network."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "10.0.1.5"
        request.headers = {"X-Forwarded-For": "203.0.113.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_from_172_network(self) -> None:
        """X-Forwarded-For trusted when from 172.16.0.0/12 network."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "172.16.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_from_192_network(self) -> None:
        """X-Forwarded-For trusted when from 192.168.0.0/16 network."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "192.168.1.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_from_ipv6_localhost(self) -> None:
        """X-Forwarded-For trusted when from IPv6 localhost (::1)."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "::1"
        request.headers = {"X-Forwarded-For": "2001:db8::1"}

        result = mw._get_client_id(request)
        assert result == "ip:2001:db8::1"

    def test_x_forwarded_for_not_trusted_external_ip(self) -> None:
        """X-Forwarded-For NOT trusted when from external IP."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "203.0.113.1"
        request.headers = {"X-Forwarded-For": "198.51.100.1"}

        result = mw._get_client_id(request)
        # Should use direct IP, not forwarded
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_multiple_ips_takes_first(self) -> None:
        """X-Forwarded-For with multiple IPs takes the first one."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1, 192.0.2.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_real_ip_trusted_from_localhost(self) -> None:
        """X-Real-IP trusted when from localhost."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "127.0.0.1"
        request.headers = {"X-Real-IP": "203.0.113.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_real_ip_not_trusted_external(self) -> None:
        """X-Real-IP NOT trusted when from external IP."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "203.0.113.1"
        request.headers = {"X-Real-IP": "198.51.100.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_takes_priority_over_x_real_ip(self) -> None:
        """X-Forwarded-For takes priority over X-Real-IP when both present."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1", "X-Real-IP": "198.51.100.1"}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_x_forwarded_for_with_whitespace(self) -> None:
        """X-Forwarded-For handles whitespace correctly."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "  203.0.113.1  "}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_no_proxy_headers_uses_direct_ip(self) -> None:
        """No proxy headers, uses direct client IP."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "203.0.113.1"
        request.headers = {}

        result = mw._get_client_id(request)
        assert result == "ip:203.0.113.1"

    def test_is_trusted_proxy_with_invalid_direct_ip_format(self) -> None:
        """When direct_ip is invalid format, is_trusted_proxy returns False and uses direct IP."""
        mw = self._make_mw()

        request = MagicMock()
        del request.state.user
        request.client.host = "not-an-ip"
        request.headers = {"X-Forwarded-For": "203.0.113.1"}

        result = mw._get_client_id(request)
        # Should use direct IP since is_trusted_proxy fails on invalid direct_ip
        assert result == "ip:not-an-ip"


class TestShouldSkipRateLimiting:
    """Test skip-list logic."""

    def _make_mw(self) -> "RateLimitingMiddleware":
        from app.middleware.rate_limiting import RateLimitingMiddleware

        return RateLimitingMiddleware(AsyncMock(), enabled=True)

    def _req(self, path: str) -> MagicMock:
        request = MagicMock()
        request.url.path = path
        return request

    def test_health_path_skipped(self) -> None:
        mw = self._make_mw()
        assert mw._should_skip_rate_limiting(self._req("/health")) is True

    def test_health_ready_skipped(self) -> None:
        mw = self._make_mw()
        assert mw._should_skip_rate_limiting(self._req("/health/ready")) is True

    def test_metrics_path_skipped(self) -> None:
        mw = self._make_mw()
        assert mw._should_skip_rate_limiting(self._req("/metrics")) is True

    def test_docs_skipped(self) -> None:
        mw = self._make_mw()
        assert mw._should_skip_rate_limiting(self._req("/docs")) is True

    def test_api_path_not_skipped(self) -> None:
        mw = self._make_mw()
        assert mw._should_skip_rate_limiting(self._req("/v1/sessions")) is False


# ---------------------------------------------------------------------------
# dispatch() tests
# ---------------------------------------------------------------------------


class TestDispatch:
    """Test the middleware dispatch method."""

    @pytest.mark.asyncio
    async def test_disabled_middleware_passes_through(self) -> None:
        """When middleware is disabled, passes request to next handler."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"

        mw = RateLimitingMiddleware(AsyncMock(), enabled=False)
        result = await mw.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert result is response_mock

    @pytest.mark.asyncio
    async def test_no_rate_limiter_passes_through(self) -> None:
        """When rate_limiter is None, passes request through with default headers."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"

        mw = RateLimitingMiddleware(AsyncMock(), enabled=True)
        # rate_limiter is None by default (no redis_client provided)
        result = await mw.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        # Default rate limit headers added
        assert "X-RateLimit-Limit" in response_mock.headers

    @pytest.mark.asyncio
    async def test_skipped_path_passes_through(self) -> None:
        """Health-check paths bypass rate limiting."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/health"

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter"):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        result = await mw.dispatch(request, call_next)
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_allowed_request_passes_through(self) -> None:
        """An allowed request is forwarded and gets rate-limit headers."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"
        request.method = "GET"
        del request.state.user  # force IP-based fallback
        request.client.host = "127.0.0.1"
        request.headers = {}

        mock_rate_limiter = MagicMock()
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=(True, 59, 60))

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter", return_value=mock_rate_limiter):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        result = await mw.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert "X-RateLimit-Limit" in response_mock.headers
        assert "X-RateLimit-Remaining" in response_mock.headers

    @pytest.mark.asyncio
    async def test_rate_limited_request_returns_429(self) -> None:
        """A rate-limited request returns HTTP 429."""
        from starlette.responses import JSONResponse

        from app.middleware.rate_limiting import RateLimitingMiddleware

        call_next = AsyncMock()

        request = MagicMock()
        request.url.path = "/v1/sessions"
        request.method = "POST"
        del request.state.user
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.state.request_id = "req-123"

        mock_rate_limiter = MagicMock()
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=(False, 0, 60))

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter", return_value=mock_rate_limiter):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        result = await mw.dispatch(request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 429
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limiter_exception_continues(self) -> None:
        """If rate limiter raises, request still passes through."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"
        request.method = "GET"
        del request.state.user
        request.client.host = "10.0.0.1"
        request.headers = {}

        mock_rate_limiter = MagicMock()
        mock_rate_limiter.check_rate_limit = AsyncMock(side_effect=RuntimeError("redis down"))

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter", return_value=mock_rate_limiter):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        # Should not raise
        result = await mw.dispatch(request, call_next)
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_reset_time_negative_value_handled(self) -> None:
        """If reset_time is negative, uses default 60-second window."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"
        request.method = "GET"
        del request.state.user
        request.client.host = "10.0.0.1"
        request.headers = {}

        mock_rate_limiter = MagicMock()
        # Return a very large negative reset_time to trigger the negative timestamp check
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=(True, 59, -(10**15)))

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter", return_value=mock_rate_limiter):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        result = await mw.dispatch(request, call_next)
        call_next.assert_called_once_with(request)
        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response_mock.headers

    @pytest.mark.asyncio
    async def test_reset_time_invalid_type_handled(self) -> None:
        """If reset_time is invalid type, uses default 60-second window."""
        from app.middleware.rate_limiting import RateLimitingMiddleware

        response_mock = MagicMock()
        response_mock.headers = {}
        call_next = AsyncMock(return_value=response_mock)

        request = MagicMock()
        request.url.path = "/v1/sessions"
        request.method = "GET"
        del request.state.user
        request.client.host = "10.0.0.1"
        request.headers = {}

        mock_rate_limiter = MagicMock()
        # Return invalid reset_time type to trigger exception handling
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=(True, 59, "invalid"))

        mock_redis = MagicMock()
        with patch("app.middleware.rate_limiting.RateLimiter", return_value=mock_rate_limiter):
            mw = RateLimitingMiddleware(AsyncMock(), redis_client=mock_redis, enabled=True)

        result = await mw.dispatch(request, call_next)
        call_next.assert_called_once_with(request)
        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response_mock.headers
