"""
Authentication Middleware

Middleware to extract and verify JWT tokens from Authorization headers.
"""

import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.connection import SessionLocal
from app.exceptions import ExpiredTokenError, InvalidTokenError
from app.services.auth_manager import AuthManager, TokenPayload

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and verify JWT tokens from Authorization headers.

    This middleware:
    1. Extracts JWT token from Authorization header
    2. Verifies the token
    3. Attaches user identity to request state
    4. Handles token expiration and invalid tokens

    Public endpoints (those not requiring authentication) are excluded from token verification.
    """

    # Endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/health/ready",
        "/health/live",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/version",
        "/v1/auth/login",
        "/v1/auth/refresh",
    }

    def __init__(self, app):
        """
        Initialize authentication middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """
        Process request and verify authentication.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler or error response
        """
        # Skip authentication for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract token from Authorization header
        token = self._extract_token(request)

        if not token:
            # No token provided - let the endpoint handle it
            # (some endpoints may be optional auth)
            return await call_next(request)

        # Verify token and attach user to request state
        try:
            user_payload = self._verify_token(token)

            # Attach user information to request state
            request.state.user = user_payload
            request.state.authenticated = True

            # Continue to next handler
            response = await call_next(request)
            return response

        except ExpiredTokenError as e:
            # Token has expired
            return self._create_error_response(
                status_code=401, code="TOKEN_EXPIRED", message=str(e)
            )
        except InvalidTokenError as e:
            # Token is invalid
            return self._create_error_response(
                status_code=401, code="INVALID_TOKEN", message=str(e)
            )
        except Exception as e:
            # Unexpected error during token verification
            logger.error(f"Unexpected error during token verification: {str(e)}")
            return self._create_error_response(
                status_code=401, code="AUTHENTICATION_ERROR", message="Authentication failed"
            )

    def _is_public_path(self, path: str) -> bool:
        """
        Check if path is public (doesn't require authentication).

        Args:
            path: Request path

        Returns:
            True if path is public, False otherwise
        """
        # Check exact matches first
        if path in self.PUBLIC_PATHS:
            return True

        # Check for path patterns that should be public (e.g., static files)
        # Only use prefix matching for specific safe patterns
        path_prefixes = [
            "/static/",
            "/docs/",
            "/redoc/",
        ]

        for prefix in path_prefixes:
            if path.startswith(prefix):
                return True

        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from Authorization header.

        Args:
            request: HTTP request

        Returns:
            Token string if present, None otherwise
        """
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        # Expected format: "Bearer <token>"
        parts = auth_header.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def _verify_token(self, token: str) -> TokenPayload:
        """
        Verify JWT token and extract payload.

        Args:
            token: JWT token string

        Returns:
            TokenPayload with user information

        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        # Create database session for token verification
        db = SessionLocal()
        try:
            auth_manager = AuthManager(db)
            payload = auth_manager.verify_token(token, expected_type="access")
            return payload
        finally:
            db.close()

    def _create_error_response(self, status_code: int, code: str, message: str) -> JSONResponse:
        """
        Create standardized error response.

        Args:
            status_code: HTTP status code
            code: Error code
            message: Error message

        Returns:
            JSONResponse with error details
        """
        from datetime import datetime, timezone

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            },
            headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else {},
        )


def get_current_user_from_request(request: Request) -> Optional[TokenPayload]:
    """
    Get current authenticated user from request state.

    This is a helper function to access the user attached by the middleware.

    Args:
        request: HTTP request

    Returns:
        TokenPayload if user is authenticated, None otherwise
    """
    return getattr(request.state, "user", None)


def is_authenticated(request: Request) -> bool:
    """
    Check if request is authenticated.

    Args:
        request: HTTP request

    Returns:
        True if authenticated, False otherwise
    """
    return getattr(request.state, "authenticated", False)
