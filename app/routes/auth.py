"""
Authentication Routes

Endpoints for user authentication, token management, and logout.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError
from app.models.schemas import LoginRequest, TokenRefreshRequest, TokenResponse
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
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    }
                }
            },
        },
        401: {"description": "Authentication failed - invalid credentials"},
    },
)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.

    Args:
        request: Login credentials (username and password)
        db: Database session

    Returns:
        TokenResponse with access_token, refresh_token, token_type, and expires_in

    Raises:
        AuthenticationError: If credentials are invalid
    """
    auth_manager = AuthManager(db)

    # Authenticate user
    user = auth_manager.authenticate_user(request.username, request.password)

    if not user:
        raise AuthenticationError("Invalid username or password")

    # Create tokens
    tokens = auth_manager.create_tokens_for_user(user)

    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
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
                        "token_type": "bearer",
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
) -> TokenResponse:
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
        tokens = auth_manager.refresh_access_token(request.refresh_token)
        return TokenResponse(**tokens)
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

    # Revoke the refresh token
    auth_manager.revoke_refresh_token(request.refresh_token)

    # Return 204 No Content (no response body)
    return None
