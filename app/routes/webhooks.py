"""
Webhook Delivery Management Routes

API endpoints for managing webhook deliveries including listing, viewing, and retrying deliveries.
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

import logging

from app.database.connection import get_db
from app.database.models import WebhookDelivery
from app.models.schemas import (
    ErrorResponse,
    WebhookDeliveryResponse,
    WebhookDeliveryListResponse,
    WebhookRetryResponse,
    PaginationInfo,
)
from app.services.authorization import Permission, require_permission, TokenPayload
from app.services.webhook_manager import WebhookManager

router = APIRouter(
    prefix="/v1/webhooks",
    tags=["Webhook Delivery Management"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Webhook delivery not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

logger = logging.getLogger(__name__)


@router.get(
    "/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List webhook deliveries",
    description="List webhook deliveries with optional filtering by status.",
)
async def list_webhook_deliveries(
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """
    List webhook deliveries.

    Args:
        status_filter: Optional status filter (pending, delivered, failed, retry)
        page: Page number (1-based)
        per_page: Number of items per page
        db: Database session
        current_user: Current authenticated user (admin required)

    Returns:
        List of webhook deliveries with pagination info
    """
    try:
        # Calculate offset
        offset = (page - 1) * per_page

        # Build query
        query = db.query(WebhookDelivery)

        # Apply status filter if provided
        if status_filter:
            query = query.filter(WebhookDelivery.status == status_filter)

        # Get total count
        total = query.count()

        # Get paginated results
        deliveries = query.offset(offset).limit(per_page).all()

        # Convert to response models
        delivery_responses = []
        for delivery in deliveries:
            delivery_responses.append(
                WebhookDeliveryResponse(
                    delivery_id=delivery.delivery_id,  # type: ignore[arg-type]
                    task_id=delivery.task_id,  # type: ignore[arg-type]
                    webhook_url=delivery.webhook_url,  # type: ignore[arg-type]
                    status=delivery.status,  # type: ignore[arg-type]
                    attempts=delivery.attempts,  # type: ignore[arg-type]
                    last_attempt_at=delivery.last_attempt_at,  # type: ignore[arg-type]
                    next_retry_at=delivery.next_retry_at,  # type: ignore[arg-type]
                    response_status=delivery.response_status,  # type: ignore[arg-type]
                    response_body=delivery.response_body,  # type: ignore[arg-type]
                    error_message=delivery.error_message,  # type: ignore[arg-type]
                    created_at=delivery.created_at,  # type: ignore[arg-type]
                )
            )

        pagination = PaginationInfo(
            page=page,
            per_page=per_page,
            total=total,
        )

        return WebhookDeliveryListResponse(
            deliveries=delivery_responses,
            pagination=pagination,
        )
    except Exception as e:
        logger.exception("Failed to list webhook deliveries")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/deliveries/{delivery_id}",
    response_model=WebhookDeliveryResponse,
    summary="Get webhook delivery details",
    description="Get details of a specific webhook delivery.",
)
async def get_webhook_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """
    Get details of a specific webhook delivery.

    Args:
        delivery_id: Webhook delivery identifier
        db: Database session
        current_user: Current authenticated user (admin required)

    Returns:
        Webhook delivery details
    """
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.delivery_id == delivery_id).first()

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook delivery not found"
        )

    return WebhookDeliveryResponse(
        delivery_id=delivery.delivery_id,  # type: ignore[arg-type]
        task_id=delivery.task_id,  # type: ignore[arg-type]
        webhook_url=delivery.webhook_url,  # type: ignore[arg-type]
        status=delivery.status,  # type: ignore[arg-type]
        attempts=delivery.attempts,  # type: ignore[arg-type]
        last_attempt_at=delivery.last_attempt_at,  # type: ignore[arg-type]
        next_retry_at=delivery.next_retry_at,  # type: ignore[arg-type]
        response_status=delivery.response_status,  # type: ignore[arg-type]
        response_body=delivery.response_body,  # type: ignore[arg-type]
        error_message=delivery.error_message,  # type: ignore[arg-type]
        created_at=delivery.created_at,  # type: ignore[arg-type]
    )


@router.post(
    "/deliveries/{delivery_id}/retry",
    response_model=WebhookRetryResponse,
    summary="Retry webhook delivery",
    description="Manually retry a failed webhook delivery.",
)
async def retry_webhook_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """
    Retry a webhook delivery.

    Args:
        delivery_id: Webhook delivery identifier
        db: Database session
        current_user: Current authenticated user (admin required)

    Returns:
        Retry operation result
    """
    # Check if delivery exists
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.delivery_id == delivery_id).first()

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook delivery not found"
        )

    # Check if delivery can be retried
    if delivery.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot retry a successfully delivered webhook",
        )

    if delivery.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum retry attempts exceeded"
        )

    try:
        # Attempt delivery
        webhook_manager = WebhookManager()
        success = await webhook_manager.deliver_webhook(db, delivery_id)

        # Refresh delivery from database
        db.refresh(delivery)

        return WebhookRetryResponse(
            delivery_id=delivery_id,
            success=success,
            status=delivery.status,  # type: ignore[arg-type]
            attempts=delivery.attempts,  # type: ignore[arg-type]
            last_attempt_at=delivery.last_attempt_at,  # type: ignore[arg-type]
        )
    except Exception as e:
        logger.exception("Failed to retry webhook delivery")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.delete(
    "/deliveries/{delivery_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook delivery",
    description="Delete a webhook delivery record.",
)
async def delete_webhook_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """
    Delete a webhook delivery record.

    Args:
        delivery_id: Webhook delivery identifier
        db: Database session
        current_user: Current authenticated user (admin required)
    """
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.delivery_id == delivery_id).first()

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook delivery not found"
        )

    try:
        db.delete(delivery)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete webhook delivery")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )
