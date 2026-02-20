"""
Task Execution Routes

API endpoints for executing and managing experimental tasks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.database.connection import get_db
from app.database.models import Task as TaskModel
from app.database.models import TaskDependency as TaskDependencyModel
from app.models.schemas import (
    ErrorResponse,
    TaskDependencyCreateRequest,
    TaskDependencyResponse,
    TaskListResponse,
    TaskResultResponse,
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
            priority=request.priority or 0,
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


@router.get(
    "/tasks/{task_id}/result",
    response_model=TaskResultResponse,
    summary="Get task result",
    description="Get the complete result payload for a completed task",
    dependencies=[Depends(require_permission(Permission.TASK_READ))],
)
async def get_task_result(
    task_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get task result.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        TaskResultResponse with complete result data

    Raises:
        HTTPException: If task not found or not completed
    """
    try:
        # Get task from database
        task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
            )

        # Check if task is completed
        if task.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task {task_id} is not completed (status: {task.status})",
            )

        # Check if result_data exists
        if not task.result_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Result data not found for task {task_id}",
            )

        logger.info(f"Retrieved result for task {task_id}")

        return TaskResultResponse(
            task_id=task_id,
            result=task.result_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result for {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task result: {str(e)}",
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


@router.post(
    "/tasks/{task_id}/dependencies",
    response_model=TaskDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task dependency",
    description="Create a dependency between tasks for execution ordering",
    dependencies=[Depends(require_permission(Permission.TASK_CREATE))],
)
async def create_task_dependency(
    task_id: str,
    request: TaskDependencyCreateRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a task dependency.

    Args:
        task_id: Dependent task identifier
        request: Dependency creation request
        db: Database session

    Returns:
        TaskDependencyResponse with dependency details

    Raises:
        HTTPException: If dependency creation fails
    """
    try:
        # Check if dependent task exists
        dependent_task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
        if not dependent_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Dependent task {task_id} not found"
            )

        # Check if prerequisite task exists
        prerequisite_task = (
            db.query(TaskModel).filter(TaskModel.task_id == request.prerequisite_task_id).first()
        )
        if not prerequisite_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prerequisite task {request.prerequisite_task_id} not found",
            )

        # Check if tasks are in the same session
        if dependent_task.session_id != prerequisite_task.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tasks must be in the same session to create dependencies",
            )

        # Check for self-dependency
        if task_id == request.prerequisite_task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Task cannot depend on itself"
            )

        # Check for existing dependency
        existing = (
            db.query(TaskDependencyModel)
            .filter(
                TaskDependencyModel.dependent_task_id == task_id,
                TaskDependencyModel.prerequisite_task_id == request.prerequisite_task_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dependency already exists between these tasks",
            )

        # Create dependency
        dependency = TaskDependencyModel(
            dependent_task_id=task_id,
            prerequisite_task_id=request.prerequisite_task_id,
            dependency_type=request.dependency_type,
        )

        db.add(dependency)
        db.commit()
        db.refresh(dependency)

        logger.info(f"Created dependency: {request.prerequisite_task_id} -> {task_id}")

        return TaskDependencyResponse(
            id=dependency.id,  # type: ignore[arg-type]
            dependent_task_id=dependency.dependent_task_id,  # type: ignore[arg-type]
            prerequisite_task_id=dependency.prerequisite_task_id,  # type: ignore[arg-type]
            dependency_type=dependency.dependency_type,  # type: ignore[arg-type]
            created_at=dependency.created_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create task dependency: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task dependency: {str(e)}",
        )


@router.get(
    "/tasks/{task_id}/dependencies",
    response_model=list[TaskDependencyResponse],
    summary="List task dependencies",
    description="Get all dependencies for a task",
    dependencies=[Depends(require_permission(Permission.TASK_READ))],
)
async def list_task_dependencies(
    task_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List task dependencies.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        List of TaskDependencyResponse objects

    Raises:
        HTTPException: If task not found
    """
    try:
        # Check if task exists
        task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
            )

        # Get dependencies
        dependencies = (
            db.query(TaskDependencyModel)
            .filter(TaskDependencyModel.dependent_task_id == task_id)
            .all()
        )

        return [
            TaskDependencyResponse(
                id=dep.id,
                dependent_task_id=dep.dependent_task_id,
                prerequisite_task_id=dep.prerequisite_task_id,
                dependency_type=dep.dependency_type,
                created_at=dep.created_at,
            )
            for dep in dependencies
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list task dependencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list task dependencies: {str(e)}",
        )


@router.delete(
    "/tasks/{task_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete task dependency",
    description="Remove a dependency between tasks",
    dependencies=[Depends(require_permission(Permission.TASK_DELETE))],
)
async def delete_task_dependency(
    task_id: str,
    dependency_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Delete a task dependency.

    Args:
        task_id: Task identifier
        dependency_id: Dependency identifier
        db: Database session

    Raises:
        HTTPException: If dependency not found or task doesn't match
    """
    try:
        # Find dependency
        dependency = (
            db.query(TaskDependencyModel)
            .filter(
                TaskDependencyModel.id == dependency_id,
                TaskDependencyModel.dependent_task_id == task_id,
            )
            .first()
        )

        if not dependency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dependency {dependency_id} not found for task {task_id}",
            )

        db.delete(dependency)
        db.commit()

        logger.info(f"Deleted dependency {dependency_id} for task {task_id}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete task dependency: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task dependency: {str(e)}",
        )
