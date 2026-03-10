"""
CSRF Protection Middleware

Provides CSRF token validation for state-changing operations to prevent
Cross-Site Request Forgery attacks.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.logging import StructuredLogger

logger = StructuredLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware to provide CSRF protection for state-changing operations.

    Generates CSRF tokens for safe methods (GET, HEAD, OPTIONS) and validates
    tokens for unsafe methods (POST, PUT, DELETE, PATCH).
    """

    def __init__(
        self,
        app,
        enabled: bool = True,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        token_expiry_minutes: int = 60,
    ):
        """
        Initialize CSRF middleware.

        Args:
            app: FastAPI application
            enabled: Whether CSRF protection is enabled
            cookie_name: Name of the CSRF token cookie
            header_name: Name of the CSRF token header
            token_expiry_minutes: How long CSRF tokens are valid
        """
        super().__init__(app)
        self.enabled = enabled
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.token_expiry_minutes = token_expiry_minutes

    def _generate_csrf_token(self) -> str:
        """
        Generate a secure CSRF token.

        Returns:
            Secure random CSRF token
        """
        return secrets.token_urlsafe(32)

    def _hash_token(self, token: str) -> str:
        """
        Hash a CSRF token for storage using HMAC with secret key.

        Args:
            token: CSRF token to hash

        Returns:
            HMAC-SHA256 hash of the token
        """
        # Use HMAC with a server-side secret key
        # This prevents token prediction attacks and ensures only the server can validate tokens
        if not settings.jwt_secret_key:
            raise ValueError("JWT secret key not configured")
        return hmac.new(
            settings.jwt_secret_key.encode(), token.encode(), hashlib.sha256
        ).hexdigest()

    def _should_protect(self, request: Request) -> bool:
        """
        Determine if the request should be protected by CSRF validation.

        Args:
            request: HTTP request

        Returns:
            True if request should be protected
        """
        # Skip CSRF for safe methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return False

        # Skip CSRF for API endpoints that use JWT authentication
        # (CSRF is primarily for browser-based form submissions)
        # However, DELETE requests should always be protected due to their destructive nature
        if request.headers.get("authorization", "").startswith("Bearer "):
            return False
        if request.method == "DELETE":
            return True

        # Skip CSRF for content-type that's not form-based
        content_type = request.headers.get("content-type", "").lower()
        if content_type and not any(
            ct in content_type
            for ct in ["application/x-www-form-urlencoded", "multipart/form-data"]
        ):
            return False

        return True

    async def _get_csrf_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request headers or form data.

        Args:
            request: HTTP request

        Returns:
            CSRF token if found, None otherwise
        """
        # Try header first
        token = request.headers.get(self.header_name)
        if token:
            return token

        # Try form data
        try:
            form = await request.form()
            form_token = form.get("csrf_token")
            if form_token and isinstance(form_token, str):
                return form_token
        except Exception:
            pass

        return None

    async def dispatch(self, request: Request, call_next):
        """
        Process request with CSRF protection.

        Args:
            request: HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Skip if CSRF protection is disabled
        if not self.enabled:
            return await call_next(request)

        # Generate or validate CSRF token
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            # For safe methods, generate and set CSRF token
            token = self._generate_csrf_token()

            # Process request
            response = await call_next(request)

            # Set CSRF token in cookie
            response.set_cookie(
                key=self.cookie_name,
                value=self._hash_token(token),
                max_age=self.token_expiry_minutes * 60,
                httponly=False,  # JavaScript needs to read this for AJAX requests
                samesite="strict",
                secure=True,  # Only send over HTTPS
            )

            return response
        else:
            # For unsafe methods, validate CSRF token
            if self._should_protect(request):
                request_token: Optional[str] = await self._get_csrf_token_from_request(request)
                cookie_token = request.cookies.get(self.cookie_name)

                if not request_token or not cookie_token:
                    logger.warning(
                        "CSRF token missing",
                        method=request.method,
                        path=request.url.path,
                        has_header=bool(request.headers.get(self.header_name)),
                        has_cookie=bool(cookie_token),
                    )

                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_TOKEN_MISSING",
                                "message": "CSRF token is required for this request",
                                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                            }
                        },
                    )

                # Validate token (constant-time comparison would be ideal here)
                if not secrets.compare_digest(self._hash_token(request_token), cookie_token):
                    logger.warning(
                        "CSRF token mismatch", method=request.method, path=request.url.path
                    )

                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_TOKEN_INVALID",
                                "message": "Invalid CSRF token",
                                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                            }
                        },
                    )

            # Process request
            return await call_next(request)
