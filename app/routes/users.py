"""
User Management Routes

API endpoints for user management including registration,
password reset, and user administration.
"""

from typing import List

import secrets
import logging

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import UserNotFoundError
from app.models.schemas import (
    ErrorResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    UserStatsResponse,
)
from app.services.authorization import (
    Permission,
    require_permission,
    get_current_user,
    TokenPayload,
    has_permission,
)
from app.services.user_management import get_user_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/users",
    tags=["User Management"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.post(
    "/register",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with auto-generated password if not provided",
)
async def register_user(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user.

    Args:
        request: User creation request
        db: Database session

    Returns:
        UserCreateResponse with user details and password

    Raises:
        HTTPException: If username already exists
    """
    user_service = get_user_management_service(db)

    try:
        user = user_service.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=["user"],
        )

        return UserCreateResponse(
            user_id=str(user.user_id),
            username=str(user.username),
            email=str(user.email),
            roles=list(user.roles) if user.roles else [],
            created_at=user.created_at,  # type: ignore[arg-type]
            message="User created successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.post(
    "/create-default",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create default system user",
    description="Create a default admin user for initial system setup",
    dependencies=[Depends(require_permission(Permission.USER_CREATE))],
)
async def create_default_user(
    db: Session = Depends(get_db),
):
    """
    Create a default system user.

    Args:
        db: Database session
        user_service: User management service

    Returns:
        UserCreateResponse with default user details
    """
    user_service = get_user_management_service(db)

    try:
        password = secrets.token_urlsafe(16)
        user = user_service.create_default_user(
            username="admin", email="admin@example.com", password=password
        )

        return UserCreateResponse(
            user_id=user.user_id,  # type: ignore[arg-type]
            username=user.username,  # type: ignore[arg-type]
            email=user.email,  # type: ignore[arg-type]
            roles=user.roles,  # type: ignore[arg-type]
            created_at=user.created_at,  # type: ignore[arg-type]
            message="Default user created successfully",
        )

    except Exception as e:
        logger.error(f"Failed to create default user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users",
    description="Retrieve list of all users (requires admin privileges)",
    dependencies=[Depends(require_permission(Permission.USER_READ))],
)
async def list_users(
    page: int = 1,
    per_page: int = 10,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    List all users.

    Args:
        page: Page number (1-based)
        per_page: Items per page (max 100)
        active_only: Only return active users
        db: Database session
        user_service: User management service

    Returns:
        List of UserResponse objects
    """
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Per page must be between 1 and 100",
        )

    user_service = get_user_management_service(db)
    users = user_service.list_users(
        skip=(page - 1) * per_page,
        limit=per_page,
        active_only=active_only,
    )

    return [
        UserResponse(  # type: ignore[arg-type]
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            roles=user.roles,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
        )
        for user in users
    ]


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Retrieve profile of currently authenticated user",
)
async def get_current_user_profile(
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user profile.

    Args:
        current_user: Authenticated user token payload
        db: Database session
        user_service: User management service

    Returns:
        UserResponse object
    """
    user_service = get_user_management_service(db)
    user = user_service.get_user(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(  # type: ignore[arg-type]
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        roles=user.roles,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


@router.get(
    "/stats",
    response_model=UserStatsResponse,
    summary="Get user statistics",
    description="Retrieve user statistics (requires admin privileges)",
    dependencies=[Depends(require_permission(Permission.USER_READ))],
)
async def get_user_stats(
    db: Session = Depends(get_db),
):
    """
    Get user statistics.

    Args:
        db: Database session
        user_service: User management service

    Returns:
        UserStatsResponse object
    """
    user_service = get_user_management_service(db)
    stats = user_service.get_user_stats()

    return UserStatsResponse(
        total_users=stats["total_users"],
        active_users=stats["active_users"],
        inactive_users=stats["inactive_users"],
        role_counts=stats["role_counts"],
        total_sessions=stats["total_sessions"],
        active_sessions=stats["active_sessions"],
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Retrieve specific user information (requires admin privileges)",
    dependencies=[Depends(require_permission(Permission.USER_READ))],
)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
):
    """
    Get user by ID.

    Args:
        user_id: User identifier
        db: Database session
        user_service: User management service

    Returns:
        UserResponse object

    Raises:
        HTTPException: If user not found
    """
    user_service = get_user_management_service(db)
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(  # type: ignore[arg-type]
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        roles=user.roles,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update user information (requires admin privileges or own user)",
)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    Update user information.

    Args:
        user_id: User identifier
        request: User update request
        db: Database session
        user_service: User management service
        current_user: Authenticated user

    Returns:
        Updated UserResponse object

    Raises:
        HTTPException: If user not found or unauthorized
    """
    user_service = get_user_management_service(db)
    # Check permissions (admin can update any user, users can only update themselves)
    is_admin = has_permission(current_user.roles, Permission.USER_ADMIN)
    is_own_user = current_user.user_id == user_id

    if not (is_admin or is_own_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this user"
        )

    try:
        user = user_service.update_user(
            user_id=user_id,
            email=request.email,
            roles=request.roles if is_admin else None,  # Only admins can change roles
            is_active=(
                request.is_active if is_admin else None
            ),  # Only admins can change active status
        )

        return UserResponse(  # type: ignore[arg-type]
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            roles=user.roles,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
        )

    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except Exception as e:
        logger.error(f"Failed to update user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    summary="Reset user password",
    description="Reset user password (requires admin privileges or own user)",
)
async def reset_user_password(
    user_id: str,
    request: PasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    Reset user password.

    Args:
        user_id: User identifier
        request: Password reset request
        db: Database session
        user_service: User management service
        current_user: Authenticated user

    Returns:
        PasswordResetResponse with new password

    Raises:
        HTTPException: If user not found or unauthorized
    """
    user_service = get_user_management_service(db)
    # Check permissions
    is_admin = has_permission(current_user.roles, Permission.USER_ADMIN)
    is_own_user = current_user.user_id == user_id

    if not (is_admin or is_own_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reset this user's password",
        )

    try:
        new_password = user_service.reset_password(
            user_id=user_id, new_password=request.new_password
        )

        return PasswordResetResponse(user_id=user_id, message="Password reset successfully")

    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except Exception as e:
        logger.error(f"Failed to reset password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete user account (requires admin privileges)",
    dependencies=[Depends(require_permission(Permission.USER_DELETE))],
)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete user.

    Args:
        user_id: User identifier
        db: Database session
        user_service: User management service

    Raises:
        HTTPException: If user not found
    """
    user_service = get_user_management_service(db)
    try:
        deleted = user_service.delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except Exception as e:
        logger.error(f"Failed to delete user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )
