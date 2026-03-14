"""
Task Execution Routes

API endpoints for executing and managing experimental tasks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.database.connection import get_db
from app.database.models import Task as TaskModel, Session as SessionModel
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
        logger.exception("Failed to list tasks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tasks",
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
            user_id=current_user.user_id,
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
        logger.exception("Failed to submit task")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit task",
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
        # Get task status with ownership validation
        status_info = await executor.get_task_status(task_id, current_user.user_id)

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
        logger.exception("Failed to get task status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task status",
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
        # Get task from database with ownership validation
        task = (
            db.query(TaskModel)
            .join(SessionModel, TaskModel.session_id == SessionModel.session_id)
            .filter(TaskModel.task_id == task_id)
            .filter(SessionModel.user_id == current_user.user_id)
            .first()
        )

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
        logger.exception("Failed to get task result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.delete(
    "/sessions/{session_id}/tasks/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel task in session",
    description="Cancel a running experimental task in a specific session",
    dependencies=[Depends(require_permission(Permission.TASK_DELETE))],
)
async def cancel_task_in_session(
    session_id: str,
    task_id: str,
    db=Depends(get_db),
    executor: TaskExecutor = Depends(get_task_executor),
    current_user=Depends(get_current_user),
):
    """
    Cancel a running task in a specific session.

    Args:
        session_id: Session identifier
        task_id: Task identifier
        db: Database session
        executor: Task executor dependency

    Returns:
        Cancellation status

    Raises:
        HTTPException: If cancellation fails or access denied
    """
    try:
        # First validate session ownership
        from app.database.models import Session as SessionModel

        session = (
            db.query(SessionModel)
            .filter(
                SessionModel.session_id == session_id, SessionModel.user_id == current_user.user_id
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or access denied",
            )

        # Check if task exists and belongs to the session
        task = (
            db.query(TaskModel)
            .filter(TaskModel.task_id == task_id, TaskModel.session_id == session_id)
            .first()
        )

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found in session {session_id}",
            )

        # Cancel task with ownership validation
        result = await executor.cancel_task(task_id, current_user.user_id)

        logger.info(f"Task {task_id} in session {session_id} cancellation requested")

        return result
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) as-is
        raise
    except ValueError as e:
        # Handle ValueError from executor (access denied)
        if "access denied" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to cancel task in session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
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
        task_status = await executor.get_task_status(task_id, current_user.user_id)

        result = await executor.cancel_task(task_id, current_user.user_id)

        logger.info(f"Task {task_id} cancellation requested")

        return result
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) as-is
        raise
    except ValueError as e:
        # Handle ValueError from executor (access denied)
        if "access denied" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to cancel task")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
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
        # Check if dependent task exists and verify ownership
        dependent_task = (
            db.query(TaskModel)
            .join(SessionModel, TaskModel.session_id == SessionModel.session_id)
            .filter(TaskModel.task_id == task_id, SessionModel.user_id == current_user.user_id)
            .first()
        )
        if not dependent_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
            )

        # Check if prerequisite task exists and verify ownership
        prerequisite_task = (
            db.query(TaskModel)
            .join(SessionModel, TaskModel.session_id == SessionModel.session_id)
            .filter(
                TaskModel.task_id == request.prerequisite_task_id,
                SessionModel.user_id == current_user.user_id,
            )
            .first()
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

        # Check for cycles in dependency graph
        # Perform DFS from prerequisite_task_id to see if it can reach task_id
        def has_cycle(start_task_id: str, target_task_id: str, visited: set[str]) -> bool:
            """Check if there's a path from start_task_id to target_task_id (indicating a cycle)."""
            if start_task_id in visited:
                return False
            if start_task_id == target_task_id:
                return True

            visited.add(start_task_id)

            # Get all tasks that depend on start_task_id
            dependents = (
                db.query(TaskDependencyModel.dependent_task_id)
                .filter(TaskDependencyModel.prerequisite_task_id == start_task_id)
                .all()
            )

            for (dependent_id,) in dependents:
                if has_cycle(dependent_id, target_task_id, visited.copy()):
                    return True

            return False

        if has_cycle(request.prerequisite_task_id, task_id, set()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Creating this dependency would create a cycle in the task dependency graph",
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
        logger.exception("Failed to create task dependency")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
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
        # Check if task exists and verify ownership
        task = (
            db.query(TaskModel)
            .join(SessionModel, TaskModel.session_id == SessionModel.session_id)
            .filter(TaskModel.task_id == task_id, SessionModel.user_id == current_user.user_id)
            .first()
        )
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
        logger.exception("Failed to list task dependencies")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
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
        # First verify the dependent task exists and belongs to the user
        dependent_task = (
            db.query(TaskModel)
            .join(SessionModel, TaskModel.session_id == SessionModel.session_id)
            .filter(TaskModel.task_id == task_id, SessionModel.user_id == current_user.user_id)
            .first()
        )
        if not dependent_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
            )

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
        logger.exception("Failed to delete task dependency")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )
