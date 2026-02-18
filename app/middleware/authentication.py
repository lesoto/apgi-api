"""
Authentication Middleware

Middleware to extract and verify JWT tokens from Authorization headers.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.connection import SessionLocal
from app.exceptions import ExpiredTokenError, InvalidTokenError
from app.services.auth_manager import AuthManager, TokenPayload

logger = logging.getLogger(__name__)


@dataclass
class APIKeyInfo:
    """Information about an authenticated API key."""

    key_id: str
    user_id: str
    name: str
    permissions: list[str]
    created_at: datetime
    expires_at: Optional[datetime] = None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and verify JWT tokens and API keys from request headers.

    This middleware supports two authentication methods:
    1. JWT Bearer tokens (Authorization: Bearer <token>)
    2. API keys (X-API-Key: <key>)

    The middleware:
    1. Extracts credentials from request headers
    2. Verifies the credentials (JWT or API key)
    3. Attaches user identity to request state
    4. Handles token/key expiration and invalid credentials

    Public endpoints (those not requiring authentication) are excluded from verification.
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

        # Try to extract and verify credentials (JWT or API key)
        auth_result = await self._extract_and_verify_credentials(request)

        if auth_result is None:
            # Check if any authentication headers were provided
            has_auth_attempt = "Authorization" in request.headers or "X-API-Key" in request.headers
            if has_auth_attempt:
                # Invalid credentials provided - return 401
                return self._create_error_response(
                    401, "invalid_credentials", "Invalid authentication credentials"
                )
            else:
                # No authentication attempt - let the endpoint handle it
                # (some endpoints may be optional auth)
                return await call_next(request)

        # Attach authentication information to request state
        auth_type, user_payload = auth_result
        request.state.user = user_payload
        request.state.authenticated = True
        request.state.auth_type = auth_type

        # Continue to next handler
        response = await call_next(request)
        return response

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

    async def _extract_and_verify_credentials(
        self, request: Request
    ) -> Optional[tuple[str, TokenPayload]]:
        """
        Extract and verify authentication credentials from request.

        Tries JWT Bearer token first, then API key.

        Args:
            request: HTTP request

        Returns:
            Tuple of (auth_type, user_payload) if valid credentials found, None otherwise
        """
        # Try JWT Bearer token first
        token = self._extract_token(request)
        if token:
            try:
                user_payload = self._verify_token(token)
                return ("jwt", user_payload)
            except (ExpiredTokenError, InvalidTokenError):
                # Token invalid, continue to check API key
                pass

        # Try API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            try:
                api_key_info = await self._verify_api_key(api_key)
                # Convert API key info to TokenPayload format for compatibility
                user_payload = TokenPayload(
                    user_id=api_key_info.user_id,
                    username="",  # API keys don't have usernames
                    roles=api_key_info.permissions,
                    token_type="api_key",
                    exp=None,  # API keys may not expire
                )
                return ("api_key", user_payload)
            except Exception:
                # API key invalid, authentication failed
                pass

        return None

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

    async def _verify_api_key(self, api_key: str) -> APIKeyInfo:
        """
        Verify API key and return key information.

        Args:
            api_key: API key string

        Returns:
            APIKeyInfo with key details

        Raises:
            ValueError: If API key is invalid or expired
        """
        # For now, implement a simple API key verification
        # In a real implementation, this would check against a database table
        # For demonstration, we'll use a simple hash-based verification

        import hashlib
        from datetime import datetime, timezone

        # Simple verification - hash the key and check against known hashes
        # In production, this should be replaced with proper database lookup
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Mock API key database - replace with actual database query
        mock_api_keys = {
            "test_key_123": {
                "key_id": "key_123",
                "user_id": "user_test",
                "name": "Test API Key",
                "permissions": ["read", "write"],
                "created_at": datetime.now(timezone.utc),
                "expires_at": None,
            }
        }

        if key_hash not in mock_api_keys:
            raise ValueError("Invalid API key")

        key_info_dict = mock_api_keys[key_hash]

        # Check expiration
        if key_info_dict["expires_at"] and key_info_dict["expires_at"] < datetime.now(timezone.utc):
            raise ValueError("API key has expired")

        return APIKeyInfo(**key_info_dict)

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
