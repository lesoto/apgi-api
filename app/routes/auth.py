"""
Authentication Routes

Endpoints for user authentication, token management, and logout.
"""

import logging

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database.connection import get_db
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError
from app.models.schemas import (
    LoginRequest,
    TokenRefreshRequest,
    TokenRefreshResponse,
    TokenResponse,
)
from app.services.auth_manager import AuthManager
from app.services.authorization import TokenPayload, get_current_user

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT tokens",
    description="""
    Authenticate with username and password to receive access and refresh tokens.

    The access token should be included in the Authorization header for subsequent requests:
    `Authorization: Bearer <access_token>`

    The refresh token can be used to obtain a new access token when it expires.
    """,
    responses={
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # nosec: B105 - example JWT token, not password
                        "token_type": "bearer",  # nosec: B105 - token type, not password
                        "expires_in": 1800,
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # nosec: B105 - example JWT token, not password
                    }
                }
            },
        },
        401: {"description": "Authentication failed - invalid credentials"},
    },
)
async def login(
    request: Request, body: LoginRequest = Body(...), db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.

    Args:
        request: HTTP request for logging IP
        body: Login credentials (username and password)
        db: Database session

    Returns:
        TokenResponse with access_token, refresh_token, token_type, and expires_in

    Raises:
        AuthenticationError: If credentials are invalid
    """
    auth_manager = AuthManager(db)

    # Authenticate user
    user = auth_manager.authenticate_user(body.username, body.password, body.mfa_code)

    if not user:
        # Log security event for failed authentication
        logger.warning(
            "Authentication failed",
            extra={
                "username": body.username,
                "ip": request.client.host if request.client else None,
                "event_type": "authentication_failure",
            },
        )
        raise AuthenticationError("Invalid username or password")

    # Create tokens first
    tokens = auth_manager.create_tokens_for_user(user, body.remember_me or False)

    # Log successful authentication to AuditLog (best-effort, doesn't block token issuance)
    try:
        from datetime import datetime, timezone

        from app.database.models import AuditLog

        audit_entry = AuditLog(
            user_id=user.user_id,
            action="login",
            resource_type="user",
            resource_id=user.user_id,
            timestamp=datetime.now(timezone.utc),
            details={"username": body.username, "method": "password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="success",
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Audit log commit failed: {e}")
        db.rollback()
        # Don't raise - tokens have already been generated

    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="""
    Use a refresh token to obtain a new access token.

    This endpoint should be called when the access token expires to get a new one
    without requiring the user to log in again.
    """,
    responses={
        200: {
            "description": "Token refreshed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",  # nosec: B105 - token type, not password
                        "expires_in": 1800,
                    }
                }
            },
        },
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    request: TokenRefreshRequest, db: Session = Depends(get_db)
) -> TokenRefreshResponse:
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        TokenResponse with new access_token, token_type, and expires_in

    Raises:
        InvalidTokenError: If refresh token is invalid
        ExpiredTokenError: If refresh token has expired
        AuthenticationError: If refresh token has been revoked
    """
    auth_manager = AuthManager(db)

    try:
        # Get new access token
        tokens = await auth_manager.refresh_access_token(request.refresh_token)
        return TokenRefreshResponse(**tokens)
    except (InvalidTokenError, ExpiredTokenError, AuthenticationError) as e:
        raise e
    except Exception as e:
        raise InvalidTokenError(f"Token refresh failed: {str(e)}")


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and invalidate refresh token",
    description="""
    Logout by revoking the refresh token.

    After logout, the refresh token can no longer be used to obtain new access tokens.
    The current access token will remain valid until it expires.

    Requires authentication with a valid access token.
    """,
    responses={
        204: {"description": "Logout successful"},
        401: {"description": "Invalid or missing authentication token"},
    },
)
async def logout(
    request: TokenRefreshRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Logout user by revoking refresh token.

    Args:
        request: Refresh token to revoke
        current_user: Current authenticated user (from access token)
        db: Database session

    Returns:
        None (204 No Content)
    """
    auth_manager = AuthManager(db)

    # Verify token belongs to user before revoking
    try:
        payload = await auth_manager.verify_token(request.refresh_token, expected_type="refresh")
        if payload.user_id != current_user.user_id:
            raise InvalidTokenError("Token does not belong to current user")
    except Exception:
        # Ignore verification errors on logout, just don't revoke
        return None

    # Revoke the refresh token
    await auth_manager.revoke_refresh_token(request.refresh_token)

    # Return 204 No Content (no response body)
    return None


@router.post(
    "/logout-access",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke current access token",
    description="""
    Revoke the current access token by adding it to the blocklist.

    After revocation, the current access token can no longer be used for authentication.
    This provides immediate logout functionality.

    Requires authentication with a valid access token (which will be revoked).
    """,
    responses={
        204: {"description": "Access token revoked successfully"},
        401: {"description": "Invalid or missing authentication token"},
        400: {"description": "Access token does not support revocation (missing JTI)"},
    },
)
async def logout_access(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Revoke the current access token by adding its JTI to the blocklist.

    Args:
        request: HTTP request containing the Authorization header
        current_user: Current authenticated user (from access token)
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        InvalidTokenError: If token cannot be revoked
    """
    # Extract access token from Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise InvalidTokenError("Missing or invalid authorization header")

    access_token = auth_header[len("Bearer ") :]

    auth_manager = AuthManager(db)

    # Revoke the access token (graceful degradation if Redis unavailable)
    revoked = await auth_manager.revoke_access_token(access_token)

    if not revoked:
        logger.warning("Access token could not be revoked (Redis unavailable or invalid token)")
        # Don't raise error - logout should always succeed

    # Return 204 No Content (no response body)
    return None
