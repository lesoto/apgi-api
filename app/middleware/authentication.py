"""
Authentication Middleware

Middleware to extract and verify JWT tokens from Authorization headers.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import asyncio

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.models import APIKey
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
        # Check exact matches only to prevent authentication bypass via path prefixes
        if path in self.PUBLIC_PATHS:
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
                user_payload = await self._verify_token(token)
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
                    roles=[],  # API keys have no roles, permissions are checked separately
                    exp=datetime.now(timezone.utc)
                    + timedelta(hours=1),  # API keys are session-based
                    token_type="api_key",
                    permissions=api_key_info.permissions,
                )
                return ("api_key", user_payload)
            except ValueError:
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

    async def _verify_token(self, token: str) -> TokenPayload:
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
        loop = asyncio.get_event_loop()
        payload = await loop.run_in_executor(None, self._blocking_verify_token, token)
        return payload

    def _blocking_verify_token(self, token: str) -> TokenPayload:
        """
        Blocking version of token verification for use in executor.
        """
        import asyncio

        # Create database session for token verification
        db = SessionLocal()
        try:
            auth_manager = AuthManager(db)
            payload = asyncio.run(auth_manager.verify_token(token, expected_type="access"))
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
        loop = asyncio.get_event_loop()
        api_key_info = await loop.run_in_executor(None, self._blocking_verify_api_key, api_key)
        return api_key_info

    def _blocking_verify_api_key(self, api_key: str) -> APIKeyInfo:
        """
        Blocking version of API key verification for use in executor.
        """
        # Create database session for API key verification
        db = SessionLocal()
        try:
            auth_manager = AuthManager(db)

            # Compute HMAC prefix for fast lookup
            import hmac
            import hashlib

            if auth_manager.secret_key is None:
                raise ValueError("Secret key not configured")
            prefix = hmac.new(
                auth_manager.secret_key.encode(), api_key.encode(), hashlib.sha256
            ).hexdigest()[:16]

            # Query API keys by prefix (should significantly reduce the number of candidates)
            active_keys = db.query(APIKey).filter(APIKey.is_active.is_(True)).all()

            # If no keys, the key is invalid
            if not active_keys:
                raise ValueError("Invalid API key")

            # Find the specific key by prefix and bcrypt check
            db_api_key = None
            print(f"DEBUG: prefix={prefix}")
            print(f"DEBUG: active_keys count={len(active_keys)}")
            for candidate_key in active_keys:
                print(f"DEBUG: candidate prefix={candidate_key.key_prefix}")
                if hmac.compare_digest(
                    str(candidate_key.key_prefix), prefix
                ) and auth_manager.verify_password(
                    api_key, candidate_key.key_hash
                ):  # type: ignore[arg-type]
                    db_api_key = candidate_key
                    print("DEBUG: found match!")
                    break

            if not db_api_key:
                print("DEBUG: no match found")
                raise ValueError("Invalid API key")

            # Check expiration
            if db_api_key.expires_at and db_api_key.expires_at < datetime.now(timezone.utc):
                raise ValueError("API key has expired")

            # Update last used timestamp
            try:
                db_api_key.last_used_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                db.commit()
            except Exception as e:
                # Log but don't fail authentication for this
                logger.warning(
                    f"Failed to update last_used_at for API key {db_api_key.key_id}: {e}"
                )
                db.rollback()

            return APIKeyInfo(
                key_id=db_api_key.key_id,  # type: ignore[arg-type]
                user_id=db_api_key.user_id,  # type: ignore[arg-type]
                name=db_api_key.name,  # type: ignore[arg-type]
                permissions=db_api_key.permissions,  # type: ignore[arg-type]
                created_at=db_api_key.created_at,  # type: ignore[arg-type]
                expires_at=db_api_key.expires_at,  # type: ignore[arg-type]
            )

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
