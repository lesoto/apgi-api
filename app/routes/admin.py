"""
Admin Management Routes

API endpoints for administrative tasks, including audit log queries.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import BaseModel
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import AuditLog
from app.models.schemas import ErrorResponse, PaginationInfo
from app.services.authorization import (
    Permission,
    TokenPayload,
    get_current_user,
    require_permission,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/admin",
    tags=["Admin"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Resource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


class AuditLogResponse(BaseModel):
    """Response for a single audit log entry."""

    audit_id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str


class AuditLogListResponse(BaseModel):
    """Response for a list of audit logs."""

    logs: List[AuditLogResponse]
    pagination: PaginationInfo


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Query audit logs",
    description="Retrieve system audit logs with filtering and pagination.",
    dependencies=[Depends(require_permission(Permission.USER_ADMIN))],
)
async def query_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    status_filter: Optional[str] = Query(None, description="Filter by status (success/failure)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> AuditLogListResponse:
    """
    Query system audit logs.
    """
    try:
        # Build query
        query = db.query(AuditLog)

        # Apply filters
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if status_filter:
            filters.append(AuditLog.status == status_filter)

        if filters:
            query = query.filter(and_(*filters))

        # Get total count
        total = query.count()

        # Apply sorting and pagination
        logs = (
            query.order_by(desc(AuditLog.timestamp))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # Map to response models
        log_responses = [
            AuditLogResponse(
                audit_id=log.audit_id,  # type: ignore[arg-type]
                user_id=log.user_id,  # type: ignore[arg-type]
                action=log.action,  # type: ignore[arg-type]
                resource_type=log.resource_type,  # type: ignore[arg-type]
                resource_id=log.resource_id,  # type: ignore[arg-type]
                timestamp=log.timestamp,  # type: ignore[arg-type]
                details=log.details,  # type: ignore[arg-type]
                ip_address=log.ip_address,  # type: ignore[arg-type]
                user_agent=log.user_agent,  # type: ignore[arg-type]
                status=log.status,  # type: ignore[arg-type]
            )
            for log in logs
        ]

        return AuditLogListResponse(
            logs=log_responses, pagination=PaginationInfo(page=page, per_page=per_page, total=total)
        )

    except Exception as e:
        logger.exception("Failed to query audit logs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs",
        )
