"""
Task Execution Routes

API endpoints for executing and managing experimental tasks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    ErrorResponse,
    TaskListResponse,
    TaskStatusResponse,
    TaskSubmitRequest,
    TaskSubmitResponse,
)
from app.services.authorization import (
    Permission,
    require_permission,
    get_current_user,
)
from app.services.task_executor import TaskExecutor

logger = logging.getLogger(__name__)


# Create router
router = APIRouter(
    prefix="/v1",
    tags=["Tasks"],
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# Task executor instance
_task_executor: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """Get TaskExecutor dependency."""
    if _task_executor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Task executor not initialized"
        )
    return _task_executor


def init_task_routes():
    """Initialize task routes with TaskExecutor."""
    global _task_executor
    _task_executor = TaskExecutor()
    logger.info("Task routes initialized")


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List available tasks",
    description="Get a list of all available experimental tasks with their descriptions and parameters",
    dependencies=[Depends(require_permission(Permission.TASK_READ))],
)
async def list_tasks(
    executor: TaskExecutor = Depends(get_task_executor), current_user=Depends(get_current_user)
):
    """
    List all available experimental tasks.

    Args:
        executor: Task executor dependency

    Returns:
        TaskListResponse with available tasks and their parameters
    """
    try:
        tasks_info = await executor.list_available_tasks()

        return TaskListResponse(tasks=tasks_info["tasks"])
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/tasks",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute experimental task",
    description="Submit an experimental task for asynchronous execution on specified session",
    dependencies=[Depends(require_permission(Permission.TASK_CREATE))],
)
async def execute_task(
    session_id: str,
    request: TaskSubmitRequest,
    executor: TaskExecutor = Depends(get_task_executor),
    current_user=Depends(get_current_user),
):
    """
    Execute experimental task on a session.

    Args:
        session_id: Session identifier
        request: Task submission request with task type, parameters, and optional webhook URL
        executor: Task executor dependency

    Returns:
        TaskSubmitResponse with task ID and status URL

    Raises:
        HTTPException: If task submission fails
    """
    try:
        # Submit task for async execution
        task_id = await executor.submit_task(
            session_id=session_id,
            task_type=request.task_type,
            parameters=request.parameters,
            webhook_url=request.webhook_url,
        )

        logger.info(f"Task {task_id} submitted for session {session_id}")

        return TaskSubmitResponse(
            task_id=task_id,
            session_id=session_id,
            task_type=request.task_type,
            status="pending",
            status_url=f"/v1/tasks/{task_id}",
        )
    except ValueError as e:
        logger.warning(f"Invalid task submission: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}",
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Get current status and results of an experimental task",
    dependencies=[Depends(require_permission(Permission.TASK_READ))],
)
async def get_task_status(
    task_id: str,
    executor: TaskExecutor = Depends(get_task_executor),
    current_user=Depends(get_current_user),
):
    """
    Get task status and results.

    Args:
        task_id: Task identifier
        executor: Task executor dependency

    Returns:
        TaskStatusResponse with current status and results if completed

    Raises:
        HTTPException: If task not found
    """
    try:
        # Get task status
        status_info = await executor.get_task_status(task_id)

        # Build response
        response = TaskStatusResponse(
            task_id=task_id,
            status=status_info["status"],
            state=status_info.get("state"),
            result=status_info.get("result"),
            error=status_info.get("error"),
            info=status_info.get("info"),
        )

        return response
    except ValueError as e:
        # Task not found
        if "not found" in str(e).lower():
            logger.warning(f"Task {task_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
            )
        # Other value errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel task",
    description="Cancel a running experimental task",
    dependencies=[Depends(require_permission(Permission.TASK_DELETE))],
)
async def cancel_task(
    task_id: str,
    executor: TaskExecutor = Depends(get_task_executor),
    current_user=Depends(get_current_user),
):
    """
    Cancel a running task.

    Args:
        task_id: Task identifier
        executor: Task executor dependency

    Returns:
        Cancellation status

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        # Check if task exists before attempting cancellation
        task_status = await executor.get_task_status(task_id)
        if task_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        result = await executor.cancel_task(task_id)

        logger.info(f"Task {task_id} cancellation requested")

        return result
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) as-is
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )
