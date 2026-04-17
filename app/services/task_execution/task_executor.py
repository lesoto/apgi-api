"""
Task Executor Service

Facade for task execution that orchestrates strategy-driven components
for task management, dependency handling, and Celery submission.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.task_execution.dependency_manager import DependencyManager

try:
    from celery.result import AsyncResult
except ImportError:  # pragma: no cover
    AsyncResult = None

from app.celery_app import celery_app
from app.database.connection import get_db_context
from app.database.models import Task, TaskStatus
from app.services.task_execution.dependency_manager import DependencyManager
from app.services.task_execution.task_submitter import TaskSubmitter, async_retry_with_backoff
from app.services.task_execution.task_strategies import get_task_strategy_registry

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    Facade for task execution management.

    Orchestrates:
    - TaskStrategyRegistry for parameter validation and task metadata
    - DependencyManager for cycle detection and prerequisite checking
    - TaskSubmitter for Celery submission with retry logic
    """

    def __init__(self) -> None:
        """Initialize the task executor with its component strategies."""
        self.strategy_registry = get_task_strategy_registry()
        self.dependency_manager: DependencyManager = DependencyManager()
        self.task_submitter = TaskSubmitter()

        # Map of task types to Celery task names (used by TaskSubmitter)
        self._task_map = {
            "iowa_gambling": "app.tasks.experimental_tasks.execute_iowa_gambling_task",
            "masking_paradigm": "app.tasks.experimental_tasks.execute_masking_paradigm_task",
            "attentional_blink": "app.tasks.experimental_tasks.execute_attentional_blink_task",
            "change_blindness": "app.tasks.experimental_tasks.execute_change_blindness_task",
            "binocular_rivalry": "app.tasks.experimental_tasks.execute_binocular_rivalry_task",
        }

    @property
    def ALLOWED_TASK_TYPES(self) -> List[str]:
        """List of allowed task types."""
        return self.strategy_registry.get_allowed_task_types()

    async def list_available_tasks(self) -> Dict[str, Any]:
        """
        List all available experimental tasks.

        Returns:
            Dict with list of available tasks and their metadata
        """
        strategies = self.strategy_registry.get_all()
        tasks = [strategy.get_task_info() for strategy in strategies]
        return {"tasks": tasks}

    async def submit_task(
        self,
        session_id: str,
        task_type: str,
        parameters: Dict[str, Any],
        user_id: str,
        webhook_url: Optional[str] = None,
        priority: int = 5,
    ) -> str:
        """
        Submit a task for asynchronous execution.

        Args:
            session_id: Session identifier
            task_type: Type of experimental task
            parameters: Task parameters
            user_id: User ID for ownership validation
            webhook_url: Optional webhook URL for completion notification
            priority: Task priority (1=highest, 10=lowest)

        Returns:
            Task ID

        Raises:
            ValueError: If task type is invalid or session not found/access denied
        """
        # Validate task type
        if not self.strategy_registry.is_valid_task_type(task_type):
            raise ValueError(
                f"Invalid task type: {task_type}. "
                f"Available types: {', '.join(self.ALLOWED_TASK_TYPES)}"
            )

        # Validate priority
        if not (1 <= priority <= 10):
            raise ValueError("Priority must be between 1 (highest) and 10 (lowest)")

        # Validate session ownership
        with get_db_context() as db:
            from app.database.models import Session as SessionModel

            session_record = (
                db.query(SessionModel)
                .filter(SessionModel.session_id == session_id)
                .filter(SessionModel.user_id == user_id)
                .first()
            )

            if not session_record:
                raise ValueError(f"Session {session_id} not found or access denied")

        # Create task via submitter (handles validation, DB record, etc.)
        task_id = await self.task_submitter.submit_task(
            session_id=session_id,
            task_type=task_type,
            parameters=parameters,
            user_id=user_id,
            webhook_url=webhook_url,
            priority=priority,
        )

        # Check for cycles in dependency graph
        if self.dependency_manager.has_cycle(task_id):
            # Clean up the created task
            with get_db_context() as db:
                task = db.query(Task).filter(Task.task_id == task_id).first()
                if task:
                    db.delete(task)
                    db.commit()
            raise ValueError("Task dependency cycle detected")

        # Check if task can be started immediately
        if self.dependency_manager.can_start_task(task_id):
            # Get validated parameters from strategy
            strategy = self.strategy_registry.get(task_type)
            if strategy:
                validated_params = strategy.validate_parameters(parameters)
            else:
                validated_params = parameters

            # Start task immediately
            await self.task_submitter.start_task_immediately(
                task_id=task_id,
                task_type=task_type,
                session_id=session_id,
                parameters=validated_params,
            )
        else:
            logger.info(
                f"Task {task_id} queued pending dependencies: {task_type} for session {session_id}"
            )

        return task_id

    async def check_and_start_pending_tasks(self, session_id: str) -> None:
        """
        Check for pending tasks in a session that can now be started.

        Args:
            session_id: Session identifier
        """
        ready_tasks = self.dependency_manager.get_ready_tasks(session_id)

        for task in ready_tasks:
            celery_task_name = self._task_map.get(str(task.task_type))
            if not celery_task_name:
                logger.error(f"No Celery task mapping for type: {task.task_type}")
                continue

            async def start_celery_task_async() -> Any:
                def start_celery_task() -> Any:
                    return celery_app.send_task(
                        celery_task_name,
                        args=[str(task.session_id), task.parameters],
                        task_id=str(task.task_id),
                    )

                return start_celery_task()

            try:
                await async_retry_with_backoff(
                    start_celery_task_async, max_retries=3, base_delay=0.5
                )

                # Update task status to running
                with get_db_context() as db:
                    task.status = TaskStatus.RUNNING.value  # type: ignore
                    task.started_at = datetime.now(timezone.utc)  # type: ignore
                    db.commit()

                logger.info(
                    f"Started previously blocked task {task.task_id} due to satisfied dependencies"
                )
            except Exception as e:
                logger.error(f"Failed to start task {task.task_id} after retries: {str(e)}")
                with get_db_context() as db:
                    task.status = TaskStatus.FAILED.value  # type: ignore
                    task.error_message = f"Task start failed: {str(e)}"  # type: ignore
                    task.completed_at = datetime.now(timezone.utc)  # type: ignore
                    db.commit()

    async def get_task_status(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get task status and results.

        Args:
            task_id: Task identifier
            user_id: User ID for ownership validation

        Returns:
            Dict with task status, state, result, and error information

        Raises:
            ValueError: If task not found or access denied
        """
        with get_db_context() as db:
            from app.database.models import Session as SessionModel

            task_record = (
                db.query(Task)
                .join(SessionModel, Task.session_id == SessionModel.session_id)
                .filter(Task.task_id == task_id)
                .filter(SessionModel.user_id == user_id)
                .first()
            )

            if not task_record:
                raise ValueError(f"Task {task_id} not found or access denied")

            async_result = AsyncResult(task_id, app=celery_app)

            status_info: Dict[str, Any] = {
                "status": task_record.status,
                "state": async_result.state,
                "result": task_record.result_data,
                "error": task_record.error_message,
                "info": None,
            }

            if async_result.state == "STARTED" and async_result.info:
                status_info["info"] = async_result.info

            if async_result.state == "FAILURE":
                if task_record.status != TaskStatus.FAILED.value:
                    task_record.status = TaskStatus.FAILED.value  # type: ignore
                    error_msg = (
                        str(async_result.result)
                        if async_result.result
                        else "Worker crashed or task failed unexpectedly"
                    )
                    task_record.error_message = str(error_msg)  # type: ignore
                    task_record.completed_at = datetime.now(timezone.utc)  # type: ignore
                    db.commit()
                if not status_info["error"]:
                    status_info["error"] = task_record.error_message

            # Check for stuck running tasks
            elif task_record.status == TaskStatus.RUNNING.value and task_record.started_at:
                time_running = (datetime.now(timezone.utc) - task_record.started_at).total_seconds()
                from app.config import settings

                max_runtime_seconds = settings.task_timeout_seconds
                if time_running > max_runtime_seconds:
                    task_record.status = TaskStatus.FAILED.value  # type: ignore
                    error_msg = f"Task timed out after {max_runtime_seconds} seconds"
                    task_record.error_message = error_msg  # type: ignore
                    task_record.completed_at = datetime.now(timezone.utc)  # type: ignore
                    db.commit()
                    status_info["status"] = TaskStatus.FAILED.value
                    status_info["error"] = task_record.error_message
                    logger.warning(f"Task {task_id} timed out and marked as failed")

            return status_info

    async def cancel_task(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """
        Cancel a running task.

        Args:
            task_id: Task identifier
            user_id: User ID for ownership validation

        Returns:
            Dict with cancellation status

        Raises:
            ValueError: If task not found or access denied
        """
        with get_db_context() as db:
            from app.database.models import Session as SessionModel

            task_record = (
                db.query(Task)
                .join(SessionModel, Task.session_id == SessionModel.session_id)
                .filter(Task.task_id == task_id)
                .filter(SessionModel.user_id == user_id)
                .first()
            )

            if not task_record:
                raise ValueError(f"Task {task_id} not found or access denied")

            celery_app.control.revoke(task_id, terminate=True)

            task_record.status = TaskStatus.CANCELLED.value  # type: ignore
            task_record.error_message = "Task cancelled by user"  # type: ignore
            task_record.completed_at = datetime.now(timezone.utc)  # type: ignore
            db.commit()

            logger.info(f"Task {task_id} cancelled")

            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task cancellation requested",
            }

    def get_dependency_chain(self, task_id: str) -> List[str]:
        """Get the dependency chain for a task."""
        return self.dependency_manager.get_dependency_chain(task_id)

    def get_dependent_tasks(self, task_id: str) -> List[str]:
        """Get tasks that depend on the given task."""
        return self.dependency_manager.get_dependent_tasks(task_id)

    async def retry_task(
        self, task_id: str, session_id: str, task_type: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retry a failed task.

        Args:
            task_id: Task ID to retry
            session_id: Session ID
            task_type: Task type
            parameters: Task parameters

        Returns:
            Dict with retry status
        """
        try:
            await self.task_submitter.retry_task(task_id, task_type, session_id, parameters)
            return {
                "task_id": task_id,
                "status": "retrying",
                "message": "Task resubmitted for execution",
            }
        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {str(e)}")
            raise
