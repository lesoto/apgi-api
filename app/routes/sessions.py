"""
Session Management Routes

API endpoints for creating, controlling, and managing APGI simulation sessions.
"""

import logging
from typing import Optional

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status

from app.database.connection import SessionLocal, get_db
from app.database.models import Session as SessionModel, Task
from app.exceptions import ServiceUnavailableError, SessionNotFoundError, SessionStateConflictError
from app.models.schemas import (
    ErrorResponse,
    SessionActionResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionMetricsResponse,
    SessionResponse,
    SessionTaskListResponse,
    TaskStatusResponse,
    PaginationInfo,
)
from app.services.authorization import (
    Permission,
    require_permission,
    get_current_user,
)
from app.services.session_manager import SessionLifecycleState, SessionManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/v1/sessions",
    tags=["Sessions"],
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# Redis client (will be initialized in main app)
_redis_client: Optional[redis.Redis] = None
_session_manager: Optional[SessionManager] = None


def get_redis_client() -> redis.Redis:
    """Get Redis client dependency."""
    if _redis_client is None:
        raise ServiceUnavailableError("Redis", "Redis client not initialized")
    return _redis_client


def get_session_manager() -> SessionManager:
    """Get SessionManager dependency."""
    if _session_manager is None:
        raise ServiceUnavailableError("SessionManager", "Session manager not initialized")
    return _session_manager


def init_session_routes(redis_client: redis.Redis):
    """
    Initialize session routes with Redis client.

    Args:
        redis_client: Async Redis client instance
    """
    global _redis_client, _session_manager
    _redis_client = redis_client
    _session_manager = SessionManager(redis_client, SessionLocal)
    logger.info("Session routes initialized")


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions",
    description="Retrieve list of user's sessions with pagination and optional state filtering",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def list_sessions(
    page: int = 1,
    per_page: int = 10,
    state: Optional[str] = None,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    List sessions with pagination.

    Args:
        page: Page number (1-based)
        per_page: Items per page (max 100)
        state: Optional state filter
        manager: Session manager dependency

    Returns:
        SessionListResponse with sessions and pagination info

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
        # Get sessions with filtering
        sessions_data = await manager.list_sessions(
            user_id=current_user.user_id,
            page=page,
            per_page=per_page,
            state=state,
        )

        # Convert to response format
        sessions = [
            SessionResponse(
                session_id=session.session_id,
                status=session.state,
                created_at=session.created_at,
                updated_at=session.updated_at,
                config=session.config,
                description=session.config.get("description"),
            )
            for session in sessions_data["sessions"]
        ]

        pagination = PaginationInfo(
            page=page,
            per_page=per_page,
            total=sessions_data["total"],
        )

        logger.info(f"Listed {len(sessions)} sessions for user {current_user.user_id}")

        return SessionListResponse(sessions=sessions, pagination=pagination)

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}",
        )


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new simulation session",
    description="Initialize a new APGI simulation session with provided configuration",
    dependencies=[Depends(require_permission(Permission.SESSION_CREATE))],
)
async def create_session(
    request: SessionCreateRequest,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Create new simulation session.

    Args:
        request: Session creation request with configuration
        manager: Session manager dependency

    Returns:
        SessionCreateResponse with session ID and details

    Raises:
        HTTPException: If session creation fails
    """
    # Create session
    session_id = await manager.create_session(request)

    # Get session details
    sim_session = await manager.get_session(session_id)

    logger.info(f"Session {session_id} created successfully")

    return SessionCreateResponse(
        session_id=session_id,
        status=sim_session.state.value,
        created_at=sim_session.created_at,
        config=sim_session.config,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session details",
    description="Retrieve detailed information about a specific simulation session",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Get session details.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionResponse with session details

    Raises:
        HTTPException: If session not found
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    return SessionResponse(
        session_id=session_id,
        status=sim_session.state.value,
        created_at=sim_session.created_at,
        updated_at=sim_session.updated_at,
        config=sim_session.config,
        description=sim_session.config.get("description"),
    )


@router.get(
    "/{session_id}/metrics",
    response_model=SessionMetricsResponse,
    summary="Get session metrics",
    description="Retrieve computed simulation metrics for a specific session",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_session_metrics(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Get session metrics.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionMetricsResponse with computed metrics

    Raises:
        HTTPException: If session not found
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    # Get current session state
    state = await sim_session.get_state()

    # Compute metrics from state
    # Assuming state contains allostatic, body, ignition, etc.
    allostatic = state.get("allostatic", {})
    body = state.get("body", {})
    ignition = state.get("ignition", {})

    metrics = {
        "session_id": session_id,
        "ignition_frequency": ignition.get("intensity", 0.0),  # Placeholder
        "free_energy": allostatic.get("load", 0.0),  # Placeholder
        "metabolic_load": body.get("energy", 0.0),  # Placeholder
        "additional_metrics": {
            "allostatic_threshold": allostatic.get("threshold", 0.0),
            "arousal": body.get("arousal", 0.0),
            "ignition_active": ignition.get("active", False),
        },
    }

    logger.info(f"Retrieved metrics for session {session_id}")

    return SessionMetricsResponse(**metrics)


@router.get(
    "/{session_id}/tasks",
    response_model=SessionTaskListResponse,
    summary="List tasks for session",
    description="Retrieve list of tasks associated with a specific session",
    dependencies=[Depends(require_permission(Permission.TASK_READ))],
)
async def get_session_tasks(
    session_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get tasks for a session.

    Args:
        session_id: Unique session identifier
        db: Database session

    Returns:
        SessionTaskListResponse with tasks for the session

    Raises:
        HTTPException: If session not found
    """
    try:
        # Verify session exists
        session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
            )

        # Get tasks for session
        tasks = db.query(Task).filter(Task.session_id == session_id).all()

        # Convert to response format
        task_responses = [
            TaskStatusResponse(
                task_id=task.task_id,
                status=task.status,
                state=None,  # Celery state not stored in DB
                result=task.result_data,
                error=task.error_message,
                info=None,
            )
            for task in tasks
        ]

        logger.info(f"Retrieved {len(task_responses)} tasks for session {session_id}")

        return SessionTaskListResponse(tasks=task_responses)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tasks for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks for session: {str(e)}",
        )


@router.post(
    "/{session_id}/start",
    response_model=SessionActionResponse,
    summary="Start simulation",
    description="Start or resume simulation for specified session",
    dependencies=[Depends(require_permission(Permission.SESSION_CONTROL))],
)
async def start_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Start simulation.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionActionResponse with updated status

    Raises:
        HTTPException: If session not found or cannot be started
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    try:
        result = await sim_session.start()
    except ValueError:
        # State conflict - trying to start session in invalid state
        raise SessionStateConflictError(session_id, sim_session.state.value, "start")

    # Update state in database
    await manager.update_session_state(session_id, SessionLifecycleState.RUNNING)

    logger.info(f"Session {session_id} started")

    return SessionActionResponse(
        session_id=session_id, status=result["status"], timestamp=sim_session.updated_at
    )


@router.post(
    "/{session_id}/pause",
    response_model=SessionActionResponse,
    summary="Pause simulation",
    description="Pause simulation while preserving current state",
    dependencies=[Depends(require_permission(Permission.SESSION_CONTROL))],
)
async def pause_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Pause simulation.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionActionResponse with updated status

    Raises:
        HTTPException: If session not found or cannot be paused
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    try:
        result = await sim_session.pause()
    except ValueError:
        # State conflict - trying to pause session in invalid state
        raise SessionStateConflictError(session_id, sim_session.state.value, "pause")

    # Update state in database
    await manager.update_session_state(session_id, SessionLifecycleState.PAUSED)

    logger.info(f"Session {session_id} paused")

    return SessionActionResponse(
        session_id=session_id, status=result["status"], timestamp=sim_session.updated_at
    )


@router.post(
    "/{session_id}/stop",
    response_model=SessionActionResponse,
    summary="Stop simulation",
    description="Stop simulation for specified session",
    dependencies=[Depends(require_permission(Permission.SESSION_CONTROL))],
)
async def stop_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Stop simulation.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionActionResponse with updated status

    Raises:
        HTTPException: If session not found
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    result = await sim_session.stop()

    # Update state in database
    await manager.update_session_state(session_id, SessionLifecycleState.STOPPED)

    logger.info(f"Session {session_id} stopped")

    return SessionActionResponse(
        session_id=session_id, status=result["status"], timestamp=sim_session.updated_at
    )


@router.post(
    "/{session_id}/reset",
    response_model=SessionActionResponse,
    summary="Reset simulation",
    description="Reset simulation to initial conditions",
    dependencies=[Depends(require_permission(Permission.SESSION_CONTROL))],
)
async def reset_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Reset simulation to initial state.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SessionActionResponse with updated status

    Raises:
        HTTPException: If session not found
    """
    try:
        sim_session = await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    result = await sim_session.reset()

    # Update state in database
    await manager.update_session_state(session_id, SessionLifecycleState.CREATED)

    logger.info(f"Session {session_id} reset")

    return SessionActionResponse(
        session_id=session_id, status=result["status"], timestamp=sim_session.updated_at
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete session",
    description="Delete session and clean up all associated resources",
    dependencies=[Depends(require_permission(Permission.SESSION_DELETE))],
)
async def delete_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user=Depends(get_current_user),
):
    """
    Delete session and clean up resources.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        No content (204)

    Raises:
        HTTPException: If session not found or deletion fails
    """
    try:
        # Verify session exists before deletion
        await manager.get_session(session_id)
    except ValueError:
        raise SessionNotFoundError(session_id)

    # Delete session
    await manager.delete_session(session_id)

    logger.info(f"Session {session_id} deleted")

    return None
