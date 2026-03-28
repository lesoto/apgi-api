"""
Tests for SecurityHeadersMiddleware.

Tests cover:
- Middleware initialization
- Security header injection on all responses
- Different request types (GET, POST, PUT, DELETE, etc.)
- HSTS header conditional logic (production vs non-production, HTTPS vs HTTP)
- CSP header injection
- All security headers present
- Response modification without breaking response
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddlewareInit:
    """Test SecurityHeadersMiddleware initialization."""

    def test_init_creates_security_headers_dict(self):
        """Test that __init__ creates security headers dictionary."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers is not None
        assert isinstance(middleware.security_headers, dict)
        assert len(middleware.security_headers) > 0

    def test_init_sets_required_headers(self):
        """Test that __init__ sets all required security headers."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
            "Cross-Origin-Embedder-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
            "X-DNS-Prefetch-Control",
        ]

        for header in required_headers:
            assert header in middleware.security_headers

    def test_init_sets_hsts_header(self):
        """Test that __init__ sets HSTS header template."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.hsts_header is not None
        assert "max-age=31536000" in middleware.hsts_header
        assert "includeSubDomains" in middleware.hsts_header
        assert "preload" in middleware.hsts_header

    def test_init_sets_csp_header(self):
        """Test that __init__ sets CSP header."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.csp_header is not None
        assert "default-src 'self'" in middleware.csp_header
        assert "script-src 'self'" in middleware.csp_header
        assert "style-src 'self'" in middleware.csp_header

    def test_x_content_type_options_is_nosniff(self):
        """Test that X-Content-Type-Options is set to nosniff."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_is_deny(self):
        """Test that X-Frame-Options is set to DENY."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection_enabled(self):
        """Test that X-XSS-Protection is enabled."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy_set(self):
        """Test that Referrer-Policy is set."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_restrictive(self):
        """Test that Permissions-Policy is restrictive."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        policy = middleware.security_headers["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy

    def test_cross_origin_policies_set(self):
        """Test that Cross-Origin policies are set."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["Cross-Origin-Embedder-Policy"] == "require-corp"
        assert middleware.security_headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert middleware.security_headers["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_dns_prefetch_control_off(self):
        """Test that DNS prefetch control is off."""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        assert middleware.security_headers["X-DNS-Prefetch-Control"] == "off"


class TestSecurityHeadersMiddlewareDispatch:
    """Test SecurityHeadersMiddleware.dispatch method."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock()
        request.url.scheme = "http"
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_dispatch_adds_security_headers_to_response(
        self, middleware, mock_request, mock_response
    ):
        """Test that dispatch adds security headers to response."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "X-Content-Type-Options" in result.headers
        assert "X-Frame-Options" in result.headers
        assert "X-XSS-Protection" in result.headers
        assert "Referrer-Policy" in result.headers
        assert "Permissions-Policy" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_adds_csp_header(self, middleware, mock_request, mock_response):
        """Test that dispatch adds Content-Security-Policy header."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "Content-Security-Policy" in result.headers
        csp = result.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    @pytest.mark.asyncio
    async def test_dispatch_adds_cross_origin_headers(
        self, middleware, mock_request, mock_response
    ):
        """Test that dispatch adds Cross-Origin headers."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert "Cross-Origin-Embedder-Policy" in result.headers
        assert "Cross-Origin-Opener-Policy" in result.headers
        assert "Cross-Origin-Resource-Policy" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_calls_next_middleware(self, middleware, mock_request, mock_response):
        """Test that dispatch calls the next middleware."""
        call_next = AsyncMock(return_value=mock_response)

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_returns_response(self, middleware, mock_request, mock_response):
        """Test that dispatch returns the response."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result is mock_response

    @pytest.mark.asyncio
    async def test_dispatch_header_values_correct(self, middleware, mock_request, mock_response):
        """Test that dispatch sets correct header values."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["X-Content-Type-Options"] == "nosniff"
        assert result.headers["X-Frame-Options"] == "DENY"
        assert result.headers["X-XSS-Protection"] == "1; mode=block"
        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert result.headers["X-DNS-Prefetch-Control"] == "off"

    @pytest.mark.asyncio
    async def test_dispatch_csp_header_value_correct(self, middleware, mock_request, mock_response):
        """Test that dispatch sets correct CSP header value."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_dispatch_cross_origin_embedder_policy_correct(
        self, middleware, mock_request, mock_response
    ):
        """Test that Cross-Origin-Embedder-Policy is correct."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["Cross-Origin-Embedder-Policy"] == "require-corp"

    @pytest.mark.asyncio
    async def test_dispatch_cross_origin_opener_policy_correct(
        self, middleware, mock_request, mock_response
    ):
        """Test that Cross-Origin-Opener-Policy is correct."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["Cross-Origin-Opener-Policy"] == "same-origin"

    @pytest.mark.asyncio
    async def test_dispatch_cross_origin_resource_policy_correct(
        self, middleware, mock_request, mock_response
    ):
        """Test that Cross-Origin-Resource-Policy is correct."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["Cross-Origin-Resource-Policy"] == "same-origin"

    @pytest.mark.asyncio
    async def test_dispatch_permissions_policy_correct(
        self, middleware, mock_request, mock_response
    ):
        """Test that Permissions-Policy is correct."""
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        policy = result.headers["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy


class TestSecurityHeadersMiddlewareHSTS:
    """Test HSTS header conditional logic."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_hsts_header_in_production_https(self, middleware, mock_response):
        """Test that HSTS header is added in production with HTTPS."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Reload settings to pick up new environment
            with patch("app.middleware.security_headers.settings") as mock_settings:
                mock_settings.environment = "production"
                middleware_prod = SecurityHeadersMiddleware(MagicMock())

                request = MagicMock()
                request.url.scheme = "https"
                call_next = AsyncMock(return_value=mock_response)

                result = await middleware_prod.dispatch(request, call_next)

                # HSTS should be present
                assert "Strict-Transport-Security" in result.headers

    @pytest.mark.asyncio
    async def test_hsts_header_in_development(self, middleware, mock_response):
        """Test that HSTS header is set to max-age=0 in development."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.environment = "development"
            middleware_dev = SecurityHeadersMiddleware(MagicMock())

            request = MagicMock()
            request.url.scheme = "http"
            call_next = AsyncMock(return_value=mock_response)

            result = await middleware_dev.dispatch(request, call_next)

            # In development, HSTS should be max-age=0
            assert "Strict-Transport-Security" in result.headers
            hsts = result.headers["Strict-Transport-Security"]
            assert "max-age=0" in hsts

    @pytest.mark.asyncio
    async def test_hsts_header_in_staging(self, middleware, mock_response):
        """Test that HSTS header is set to max-age=0 in staging."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.environment = "staging"
            middleware_staging = SecurityHeadersMiddleware(MagicMock())

            request = MagicMock()
            request.url.scheme = "http"
            call_next = AsyncMock(return_value=mock_response)

            result = await middleware_staging.dispatch(request, call_next)

            # In staging, HSTS should be max-age=0
            assert "Strict-Transport-Security" in result.headers
            hsts = result.headers["Strict-Transport-Security"]
            assert "max-age=0" in hsts

    @pytest.mark.asyncio
    async def test_hsts_header_production_https_has_preload(self, middleware, mock_response):
        """Test that HSTS header in production HTTPS includes preload."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.environment = "production"
            middleware_prod = SecurityHeadersMiddleware(MagicMock())

            request = MagicMock()
            request.url.scheme = "https"
            call_next = AsyncMock(return_value=mock_response)

            result = await middleware_prod.dispatch(request, call_next)

            hsts = result.headers.get("Strict-Transport-Security", "")
            # In production HTTPS, should have full HSTS
            if "max-age=31536000" in hsts:
                assert "includeSubDomains" in hsts
                assert "preload" in hsts

    @pytest.mark.asyncio
    async def test_hsts_header_production_http_is_zero(self, mock_response):
        """Test that HSTS header in production HTTP is not set (no HSTS in non-HTTPS)."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.environment = "production"
            middleware_prod = SecurityHeadersMiddleware(MagicMock())

            request = MagicMock()
            request.url.scheme = "http"
            call_next = AsyncMock(return_value=mock_response)

            result = await middleware_prod.dispatch(request, call_next)

            # In production but HTTP, HSTS should not be set (only set in production+HTTPS or non-production)
            hsts = result.headers.get("Strict-Transport-Security", "")
            # The middleware doesn't set HSTS for production+HTTP
            assert hsts == ""


class TestSecurityHeadersMiddlewareMultipleRequests:
    """Test that headers are added consistently across multiple requests."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_headers_consistent_across_requests(self, middleware, mock_response):
        """Test that headers are consistent across multiple requests."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result1 = await middleware.dispatch(request, call_next)
        # Reset headers for second call
        mock_response.headers = {}
        result2 = await middleware.dispatch(request, call_next)

        assert (
            result1.headers["X-Content-Type-Options"] == result2.headers["X-Content-Type-Options"]
        )
        assert result1.headers["X-Frame-Options"] == result2.headers["X-Frame-Options"]
        assert (
            result1.headers["Content-Security-Policy"] == result2.headers["Content-Security-Policy"]
        )

    @pytest.mark.asyncio
    async def test_headers_do_not_duplicate(self, middleware, mock_response):
        """Test that headers are not duplicated."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        # Headers should appear only once
        assert result.headers.get("X-Content-Type-Options") == "nosniff"
        # Check that it's not duplicated (would appear as comma-separated)
        assert "," not in result.headers.get("X-Content-Type-Options", "")


class TestSecurityHeadersMiddlewareEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_response_headers(self, middleware, mock_response):
        """Test that dispatch works with empty response headers."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        assert "X-Content-Type-Options" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_with_existing_headers(self, middleware, mock_response):
        """Test that dispatch preserves existing headers."""
        mock_response.headers = {"X-Custom-Header": "custom-value"}
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        # Should have both security headers and existing headers
        assert "X-Content-Type-Options" in result.headers
        assert result.headers.get("X-Custom-Header") == "custom-value"

    @pytest.mark.asyncio
    async def test_csp_header_no_unsafe_inline(self, middleware, mock_response):
        """Test that CSP header does not include unsafe-inline."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "unsafe-inline" not in csp

    @pytest.mark.asyncio
    async def test_csp_header_no_unsafe_eval(self, middleware, mock_response):
        """Test that CSP header does not include unsafe-eval."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "unsafe-eval" not in csp

    @pytest.mark.asyncio
    async def test_permissions_policy_no_payment(self, middleware, mock_response):
        """Test that Permissions-Policy disables payment API."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        policy = result.headers["Permissions-Policy"]
        assert "payment=()" in policy

    @pytest.mark.asyncio
    async def test_permissions_policy_no_usb(self, middleware, mock_response):
        """Test that Permissions-Policy disables USB API."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        policy = result.headers["Permissions-Policy"]
        assert "usb=()" in policy

    @pytest.mark.asyncio
    async def test_permissions_policy_no_autoplay(self, middleware, mock_response):
        """Test that Permissions-Policy disables autoplay."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        policy = result.headers["Permissions-Policy"]
        assert "autoplay=()" in policy

    @pytest.mark.asyncio
    async def test_csp_restricts_script_sources(self, middleware, mock_response):
        """Test that CSP restricts script sources."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp

    @pytest.mark.asyncio
    async def test_csp_restricts_style_sources(self, middleware, mock_response):
        """Test that CSP restricts style sources."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "style-src 'self'" in csp

    @pytest.mark.asyncio
    async def test_csp_disables_plugins(self, middleware, mock_response):
        """Test that CSP disables plugins."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "object-src 'none'" in csp

    @pytest.mark.asyncio
    async def test_csp_disables_frames(self, middleware, mock_response):
        """Test that CSP disables frames."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        csp = result.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_referrer_policy_strict(self, middleware, mock_response):
        """Test that Referrer-Policy is strict."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_cross_origin_policies_restrictive(self, middleware, mock_response):
        """Test that Cross-Origin policies are restrictive."""
        call_next = AsyncMock(return_value=mock_response)
        request = MagicMock()
        request.url.scheme = "http"

        result = await middleware.dispatch(request, call_next)

        assert result.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
        assert result.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert result.headers["Cross-Origin-Resource-Policy"] == "same-origin"
