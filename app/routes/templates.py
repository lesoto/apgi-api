"""
Template Management Routes

API endpoints for managing session templates.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from app.database.connection import get_async_db_context
from app.database.models import SessionTemplate
from app.models.schemas import (
    SessionTemplateCreateRequest,
    SessionTemplateUpdateRequest,
    SessionTemplateResponse,
    SessionTemplateListResponse,
    PaginationInfo,
)
from app.services.authorization import (
    get_current_user,
    require_permission,
    Permission,
    TokenPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/templates", tags=["Templates"])

# Global dependencies
_redis_client = None
_session_manager = None


def init_template_routes() -> None:
    """
    Initialize template routes.

    This function is called during application startup to initialize
    any global dependencies required by the template routes.
    """
    logger.info("Template routes initialized")


@router.get(
    "",
    response_model=SessionTemplateListResponse,
    summary="List templates",
    description="Retrieve list of user's templates with pagination and optional filtering",
    dependencies=[Depends(require_permission(Permission.TEMPLATE_READ))],
)
async def list_templates(
    page: int = 1,
    per_page: int = 10,
    public_only: bool = False,
    current_user: TokenPayload = Depends(get_current_user),
) -> SessionTemplateListResponse:
    """
    List templates with pagination.

    Args:
        page: Page number (1-based)
        per_page: Items per page (max 100)
        public_only: Whether to show only public templates
        current_user: Current authenticated user

    Returns:
        SessionTemplateListResponse with templates and pagination info

    Raises:
        HTTPException: If pagination parameters are invalid
    """
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Per page must be between 1 and 100"
        )

    try:
        result = None
        async with get_async_db_context() as db:
            # Build query
            query = select(SessionTemplate)

            if public_only:
                # Show only public templates
                query = query.where(SessionTemplate.is_public)
            else:
                # Show user's own templates and public templates
                query = query.where(
                    (SessionTemplate.user_id == current_user.user_id) | (SessionTemplate.is_public)
                )

            # Get total count
            # Use explicit None check to avoid SQLAlchemy boolean evaluation error
            where_clause = query.whereclause
            total = (
                db.query(SessionTemplate).filter(where_clause).count()
                if where_clause is not None
                else db.query(SessionTemplate).count()
            )

            # Apply pagination
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)

            # Execute query
            result = db.execute(query)
            templates_db = result.scalars().all()

        # Process results outside of context manager
        templates = [
            SessionTemplateResponse(
                template_id=str(template.template_id),
                user_id=str(template.user_id),
                name=str(template.name),
                description=template.description,  # type: ignore[arg-type]
                config_path=template.config_path,  # type: ignore[arg-type]
                custom_config=template.custom_config,  # type: ignore[arg-type]
                default_description=template.default_description,  # type: ignore[arg-type]
                tags=list(template.tags or []),
                is_public=bool(template.is_public),
                created_at=template.created_at,  # type: ignore[arg-type]
                updated_at=template.updated_at,  # type: ignore[arg-type]
            )
            for template in templates_db
        ]

        pagination = PaginationInfo(
            page=page,
            per_page=per_page,
            total=total,
        )

        logger.info(f"Listed {len(templates)} templates for user {current_user.user_id}")

        return SessionTemplateListResponse(templates=templates, pagination=pagination)

    except Exception as e:
        logger.error("Failed to list templates: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.post(
    "",
    response_model=SessionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new template",
    description="Create a new session template with provided configuration",
    dependencies=[Depends(require_permission(Permission.TEMPLATE_CREATE))],
)
async def create_template(
    request: SessionTemplateCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> SessionTemplateResponse:
    """
    Create new session template.

    Args:
        request: Template creation request with configuration
        current_user: Current authenticated user

    Returns:
        SessionTemplateResponse with template details

    Raises:
        HTTPException: If template creation fails
    """
    try:
        template = None
        async with get_async_db_context() as db:
            # Check for duplicate name for this user
            existing_stmt = select(SessionTemplate).where(
                SessionTemplate.user_id == current_user.user_id,
                SessionTemplate.name == request.name,
            )
            existing_result = db.execute(existing_stmt)
            existing_template = existing_result.scalar_one_or_none()

            if existing_template:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Template with name '{request.name}' already exists for this user",
                )

            # Create template
            template_id = str(uuid4())
            template = SessionTemplate(
                template_id=template_id,
                user_id=current_user.user_id,
                name=request.name,
                description=request.description,
                config_path=request.config_path,
                custom_config=request.custom_config,
                default_description=request.default_description,
                tags=request.tags,
                is_public=request.is_public,
            )

            db.add(template)

            try:
                db.commit()
                db.refresh(template)
            except Exception as e:
                db.rollback()

                # Handle specific database constraint errors
                error_msg = str(e).lower()
                if "unique" in error_msg and "name" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Template with name '{request.name}' already exists for this user",
                    )
                elif "foreign key" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid user reference",
                    )
                elif "check constraint" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid template data: " + str(e),
                    )
                else:
                    # Generic database error
                    logger.error(f"Database error creating template: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create template due to database error",
                    )

            logger.info(
                f"Template {template_id} created successfully by user {current_user.user_id}"
            )

        # Return response outside of context manager
        return SessionTemplateResponse(
            template_id=str(template.template_id),
            user_id=str(template.user_id),
            name=str(template.name),
            description=template.description,  # type: ignore[arg-type]
            config_path=template.config_path,  # type: ignore[arg-type]
            custom_config=template.custom_config,  # type: ignore[arg-type]
            default_description=template.default_description,  # type: ignore[arg-type]
            tags=list(template.tags or []),
            is_public=bool(template.is_public),
            created_at=template.created_at,  # type: ignore[arg-type]
            updated_at=template.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise


@router.get(
    "/{template_id}",
    response_model=SessionTemplateResponse,
    summary="Get template details",
    description="Retrieve detailed information about a specific template",
    dependencies=[Depends(require_permission(Permission.TEMPLATE_READ))],
)
async def get_template(
    template_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> SessionTemplateResponse:
    """
    Get template details.

    Args:
        template_id: Unique template identifier
        current_user: Current authenticated user

    Returns:
        SessionTemplateResponse with template details

    Raises:
        HTTPException: If template not found or access denied
    """
    try:
        template = None
        async with get_async_db_context() as db:
            stmt = select(SessionTemplate).where(SessionTemplate.template_id == template_id)
            result = db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found",
                )

            # Check access permissions
            if not template.is_public and template.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this template"
                )

        # Return response outside of context manager
        return SessionTemplateResponse(
            template_id=str(template.template_id),
            user_id=str(template.user_id),
            name=str(template.name),
            description=template.description,  # type: ignore[arg-type]
            config_path=template.config_path,  # type: ignore[arg-type]
            custom_config=template.custom_config,  # type: ignore[arg-type]
            default_description=template.default_description,  # type: ignore[arg-type]
            tags=list(template.tags or []),
            is_public=bool(template.is_public),
            created_at=template.created_at,  # type: ignore[arg-type]
            updated_at=template.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get template %s: %s", template_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.put(
    "/{template_id}",
    response_model=SessionTemplateResponse,
    summary="Update template",
    description="Update an existing session template",
    dependencies=[Depends(require_permission(Permission.TEMPLATE_UPDATE))],
)
async def update_template(
    template_id: str,
    request: SessionTemplateUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> SessionTemplateResponse:
    """
    Update template details.

    Args:
        template_id: Unique template identifier
        request: Template update request
        current_user: Current authenticated user

    Returns:
        SessionTemplateResponse with updated template details

    Raises:
        HTTPException: If template not found or access denied
    """
    try:
        template = None
        async with get_async_db_context() as db:
            stmt = select(SessionTemplate).where(SessionTemplate.template_id == template_id)
            result = db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found",
                )

            # Check ownership
            if template.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only template owner can update it",
                )

            # Check for name conflict if name is being updated
            if request.name and request.name != template.name:
                existing_stmt = select(SessionTemplate).where(
                    SessionTemplate.user_id == current_user.user_id,
                    SessionTemplate.name == request.name,
                    SessionTemplate.template_id != template_id,
                )
                existing_result = db.execute(existing_stmt)
                existing_template = existing_result.scalar_one_or_none()

                if existing_template:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Template with name '{request.name}' already exists for this user",
                    )

            # Update fields explicitly
            update_data = request.model_dump(exclude_unset=True)
            if "name" in update_data:
                template.name = update_data["name"]
            if "description" in update_data:
                template.description = update_data["description"]
            if "config_path" in update_data:
                template.config_path = update_data["config_path"]
            if "custom_config" in update_data:
                template.custom_config = update_data["custom_config"]
            if "default_description" in update_data:
                template.default_description = update_data["default_description"]
            if "tags" in update_data:
                template.tags = update_data["tags"]
            if "is_public" in update_data:
                template.is_public = update_data["is_public"]

            # Context manager will commit automatically

            logger.info(f"Template {template_id} updated by user {current_user.user_id}")

        # Return response outside of context manager
        return SessionTemplateResponse(
            template_id=str(template.template_id),
            user_id=str(template.user_id),
            name=str(template.name),
            description=template.description,  # type: ignore[arg-type]
            config_path=template.config_path,  # type: ignore[arg-type]
            custom_config=template.custom_config,  # type: ignore[arg-type]
            default_description=template.default_description,  # type: ignore[arg-type]
            tags=list(template.tags or []),
            is_public=bool(template.is_public),
            created_at=template.created_at,  # type: ignore[arg-type]
            updated_at=template.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete template",
    description="Delete an existing session template",
    dependencies=[Depends(require_permission(Permission.TEMPLATE_DELETE))],
)
async def delete_template(
    template_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    """
    Delete template.

    Args:
        template_id: Unique template identifier
        current_user: Current authenticated user

    Raises:
        HTTPException: If template not found or access denied
    """
    try:
        async with get_async_db_context() as db:
            stmt = select(SessionTemplate).where(SessionTemplate.template_id == template_id)
            result = db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found",
                )

            # Check ownership
            if template.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only template owner can delete it",
                )

            db.delete(template)
            # Context manager will commit automatically

            logger.info(f"Template {template_id} deleted by user {current_user.user_id}")

    except HTTPException:
        raise
