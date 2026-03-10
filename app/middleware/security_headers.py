"""
Security Headers Middleware

Adds security-related HTTP headers to all responses for defense in depth.
"""

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.middleware.logging import StructuredLogger

logger = StructuredLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    Adds headers for:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - Cross-Origin-Embedder-Policy
    - Cross-Origin-Opener-Policy
    - Cross-Origin-Resource-Policy
    """

    def __init__(self, app):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)

        # Define security headers
        self.security_headers = {
            # HSTS - HTTP Strict Transport Security (conditionally added)
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            # Prevent XSS attacks
            "X-XSS-Protection": "1; mode=block",
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # Permissions policy (restrict features)
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "magnetometer=(), gyroscope=(), accelerometer=(), "
                "payment=(), usb=(), autoplay=(), encrypted-media=(), "
                "ambient-light-sensor=(), bluetooth=(), browsing-topics=()"
            ),
            # Cross-Origin policies
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            # DNS prefetch control
            "X-DNS-Prefetch-Control": "off",
        }

        # HSTS header - only added conditionally
        self.hsts_header = "max-age=31536000; includeSubDomains; preload"

        # Content Security Policy - more restrictive
        self.csp_header = (
            "default-src 'self'; "
            "script-src 'self'; "  # Removed unsafe-inline and unsafe-eval
            "style-src 'self'; "  # Removed unsafe-inline
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'none'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )

        logger.info("Security headers middleware initialized")

    async def dispatch(self, request, call_next):
        """
        Process request and add security headers to response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response with security headers
        """
        response = await call_next(request)

        # Add security headers to response
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value

        # Add CSP header
        response.headers["Content-Security-Policy"] = self.csp_header

        # Conditionally add HSTS header
        # Only add in production and when request is over HTTPS
        is_production = settings.environment.lower() in ["production", "prod"]
        is_https = request.url.scheme == "https"

        if is_production and is_https:
            response.headers["Strict-Transport-Security"] = self.hsts_header
        elif not is_production:
            # In non-production, explicitly disable HSTS to avoid browser caching issues
            response.headers["Strict-Transport-Security"] = "max-age=0"

        return response
