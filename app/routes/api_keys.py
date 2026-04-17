"""
API Key Management Routes

API endpoints for managing API keys including creation, listing, updating, and deletion.
"""

import secrets
import logging
from typing import cast
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import APIKey
from app.config import settings
from app.models.schemas import (
    ErrorResponse,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    APIKeyListResponse,
    APIKeyUpdateRequest,
    PaginationInfo,
)
from app.services.authorization import get_current_user, TokenPayload
from app.services.auth_manager import AuthManager

router = APIRouter(
    prefix="/v1/api-keys",
    tags=["API Key Management"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key for the authenticated user.",
)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> APIKeyCreateResponse:
    """
    Create a new API key.

    Args:
        request: API key creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        API key creation response with the actual key
    """
    # Generate a secure API key
    api_key_plain = f"apgi_{secrets.token_urlsafe(32)}"

    # Enforce default expiry if not provided
    expires_at = request.expires_at or (datetime.now(timezone.utc) + timedelta(days=365))

    # Compute HMAC prefix for fast lookup
    import hmac
    import hashlib

    prefix = hmac.new(
        cast(str, settings.jwt_secret_key).encode(),
        api_key_plain.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]

    # Hash the API key for storage
    auth_manager = AuthManager(db)
    key_hash = auth_manager.hash_password(api_key_plain)

    # Create the API key record
    db_api_key = APIKey(
        user_id=current_user.user_id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=prefix,
        permissions=request.permissions,
        expires_at=expires_at,
        is_active=True,
    )

    try:
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)

        return APIKeyCreateResponse(
            key_id=db_api_key.key_id,  # type: ignore[arg-type]
            key=api_key_plain,
            name=db_api_key.name,  # type: ignore[arg-type]
            permissions=db_api_key.permissions,  # type: ignore[arg-type]
            expires_at=db_api_key.expires_at,  # type: ignore[arg-type]
            created_at=db_api_key.created_at,  # type: ignore[arg-type]
        )
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "",
    response_model=APIKeyListResponse,
    summary="List API keys",
    description="List API keys for the authenticated user.",
)
async def list_api_keys(
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> APIKeyListResponse:
    """
    List API keys for the current user.

    Args:
        page: Page number (1-based)
        per_page: Number of items per page
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of API keys with pagination info
    """
    try:
        if per_page < 1 or per_page > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Per page must be between 1 and 100"
            )

        # Calculate offset
        offset = (page - 1) * per_page

        # Query API keys for the user
        query = db.query(APIKey).filter(APIKey.user_id == current_user.user_id)
        total = query.count()
        api_keys = query.offset(offset).limit(per_page).all()

        # Convert to response models
        api_key_responses = []
        for api_key in api_keys:
            api_key_responses.append(
                APIKeyResponse(
                    key_id=api_key.key_id,  # type: ignore[arg-type]
                    name=api_key.name,  # type: ignore[arg-type]
                    permissions=api_key.permissions,  # type: ignore[arg-type]
                    expires_at=api_key.expires_at,  # type: ignore[arg-type]
                    is_active=api_key.is_active,  # type: ignore[arg-type]
                    created_at=api_key.created_at,  # type: ignore[arg-type]
                    last_used_at=api_key.last_used_at,  # type: ignore[arg-type]
                )
            )

        pagination = PaginationInfo(
            page=page,
            per_page=per_page,
            total=total,
        )

        return APIKeyListResponse(
            api_keys=api_key_responses,
            pagination=pagination,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list API keys")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get API key details",
    description="Get details of a specific API key.",
)
async def get_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> APIKeyResponse:
    """
    Get details of a specific API key.

    Args:
        key_id: API key identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        API key details
    """
    api_key = (
        db.query(APIKey)
        .filter(APIKey.key_id == key_id, APIKey.user_id == current_user.user_id)
        .first()
    )

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    return APIKeyResponse(
        key_id=api_key.key_id,  # type: ignore[arg-type]
        name=api_key.name,  # type: ignore[arg-type]
        permissions=api_key.permissions,  # type: ignore[arg-type]
        expires_at=api_key.expires_at,  # type: ignore[arg-type]
        is_active=api_key.is_active,  # type: ignore[arg-type]
        created_at=api_key.created_at,  # type: ignore[arg-type]
        last_used_at=api_key.last_used_at,  # type: ignore[arg-type]
    )


@router.patch(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Update API key",
    description="Update an existing API key.",
)
async def update_api_key(
    key_id: str,
    request: APIKeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> APIKeyResponse:
    """
    Update an existing API key.

    Args:
        key_id: API key identifier
        request: API key update request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated API key details
    """
    api_key = (
        db.query(APIKey)
        .filter(APIKey.key_id == key_id, APIKey.user_id == current_user.user_id)
        .first()
    )

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # Update fields if provided
    if request.name is not None:
        api_key.name = request.name  # type: ignore[assignment]
    if request.permissions is not None:
        api_key.permissions = request.permissions  # type: ignore[assignment]
    if request.is_active is not None:
        api_key.is_active = request.is_active  # type: ignore[assignment]

    try:
        db.commit()
        db.refresh(api_key)

        return APIKeyResponse(
            key_id=api_key.key_id,  # type: ignore[arg-type]
            name=api_key.name,  # type: ignore[arg-type]
            permissions=api_key.permissions,  # type: ignore[arg-type]
            expires_at=api_key.expires_at,  # type: ignore[arg-type]
            is_active=api_key.is_active,  # type: ignore[arg-type]
            created_at=api_key.created_at,  # type: ignore[arg-type]
            last_used_at=api_key.last_used_at,  # type: ignore[arg-type]
        )
    except Exception as e:
        db.rollback()
        logger.exception("Failed to update API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.post(
    "/{key_id}/rotate",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rotate API key",
    description="Rotate an existing API key by creating a new one and optionally deactivating the old one.",
)
async def rotate_api_key(
    key_id: str,
    deactivate_old: bool = True,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> APIKeyCreateResponse:
    """
    Rotate an existing API key.

    Creates a new API key with the same properties as the existing one,
    and optionally deactivates the old key.

    Args:
        key_id: API key identifier to rotate
        deactivate_old: Whether to deactivate the old key (default: True)
        db: Database session
        current_user: Current authenticated user

    Returns:
        New API key creation response with the actual key
    """
    # Find the existing API key
    existing_key = (
        db.query(APIKey)
        .filter(APIKey.key_id == key_id, APIKey.user_id == current_user.user_id)
        .first()
    )

    if not existing_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # Generate a new secure API key
    api_key_plain = f"apgi_{secrets.token_urlsafe(32)}"

    # Compute HMAC prefix for fast lookup
    import hmac
    import hashlib

    prefix = hmac.new(
        cast(str, settings.jwt_secret_key).encode(),
        api_key_plain.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]

    # Hash the API key for storage
    auth_manager = AuthManager(db)
    key_hash = auth_manager.hash_password(api_key_plain)

    # Create the new API key record with same properties
    db_new_api_key = APIKey(
        user_id=current_user.user_id,
        name=existing_key.name,
        key_hash=key_hash,
        key_prefix=prefix,
        permissions=existing_key.permissions,
        # BUG-020 fix: always use a fresh expiry, not the inherited one which may be expired.
        # Default to 1 year from now; callers can adjust by updating afterward.
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        is_active=True,
    )

    try:
        # Add the new key
        db.add(db_new_api_key)

        # Optionally deactivate the old key
        if deactivate_old:
            existing_key.is_active = False  # type: ignore[assignment]

        db.commit()
        db.refresh(db_new_api_key)

        return APIKeyCreateResponse(
            key_id=db_new_api_key.key_id,  # type: ignore[arg-type]
            key=api_key_plain,
            name=db_new_api_key.name,  # type: ignore[arg-type]
            permissions=db_new_api_key.permissions,  # type: ignore[arg-type]
            expires_at=db_new_api_key.expires_at,  # type: ignore[arg-type]
            created_at=db_new_api_key.created_at,  # type: ignore[arg-type]
        )
    except Exception as e:
        db.rollback()
        logger.exception("Failed to rotate API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API key",
    description="Delete an existing API key.",
)
async def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    """
    Delete an existing API key.

    Args:
        key_id: API key identifier
        db: Database session
        current_user: Current authenticated user
    """
    api_key = (
        db.query(APIKey)
        .filter(APIKey.key_id == key_id, APIKey.user_id == current_user.user_id)
        .first()
    )

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    try:
        db.delete(api_key)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )
