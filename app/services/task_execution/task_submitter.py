"""
Task Submitter Module

Handles task submission to Celery with retry logic and error handling.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

try:
    from celery.result import AsyncResult
except ImportError:  # pragma: no cover
    import celery

    AsyncResult = celery.result.AsyncResult

from app.celery_app import celery_app
from app.database.connection import get_db_context
from app.database.models import Task, TaskStatus
from app.services.task_execution.task_strategies import get_task_strategy_registry

logger = logging.getLogger(__name__)


async def async_retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
) -> Any:
    """
    Async retry a function with exponential backoff for transient failures.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Factor to multiply delay by each retry

    Returns:
        Result of the function call

    Raises:
        Last exception if all retries fail
    """
    last_exception: Optional[Exception] = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.1f}s: {str(e)}")
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {str(e)}")

    if last_exception is not None:
        raise last_exception

    raise RuntimeError("All retries failed but no exception was captured")  # pragma: no cover


class TaskSubmitter:
    """
    Handles task submission to Celery with retry logic.

    Responsible for:
    - Validating task parameters using strategies
    - Creating database records
    - Submitting to Celery with retries
    - Handling submission failures
    """

    def __init__(self) -> None:
        """Initialize the task submitter."""
        self.strategy_registry = get_task_strategy_registry()
        self._task_map = {
            "iowa_gambling": "app.tasks.experimental_tasks.execute_iowa_gambling_task",
            "masking_paradigm": "app.tasks.experimental_tasks.execute_masking_paradigm_task",
            "attentional_blink": "app.tasks.experimental_tasks.execute_attentional_blink_task",
            "change_blindness": "app.tasks.experimental_tasks.execute_change_blindness_task",
            "binocular_rivalry": "app.tasks.experimental_tasks.execute_binocular_rivalry_task",
        }

    def validate_task_type(self, task_type: str) -> bool:
        """
        Validate that a task type is allowed.

        Args:
            task_type: The task type to validate

        Returns:
            True if task type is valid

        Raises:
            ValueError: If task type is invalid
        """
        if not self.strategy_registry.is_valid_task_type(task_type):
            allowed = self.strategy_registry.get_allowed_task_types()
            raise ValueError(
                f"Invalid task type: {task_type}. Available types: {', '.join(allowed)}"
            )
        return True

    def validate_priority(self, priority: int) -> bool:
        """
        Validate task priority.

        Args:
            priority: Priority value (1-10)

        Returns:
            True if valid

        Raises:
            ValueError: If priority is out of range
        """
        if not (1 <= priority <= 10):
            raise ValueError("Priority must be between 1 (highest) and 10 (lowest)")
        return True

    def validate_parameters(self, task_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize task parameters using strategy.

        Args:
            task_type: The task type
            parameters: Raw parameters

        Returns:
            Validated and normalized parameters
        """
        strategy = self.strategy_registry.get(task_type)
        if not strategy:
            raise ValueError(f"No strategy found for task type: {task_type}")
        return strategy.validate_parameters(parameters)

    def create_task_record(
        self,
        task_id: str,
        session_id: str,
        task_type: str,
        parameters: Dict[str, Any],
        priority: int,
        webhook_url: Optional[str],
    ) -> Task:
        """
        Create a task record in the database.

        Args:
            task_id: Unique task identifier
            session_id: Session ID
            task_type: Task type
            parameters: Task parameters
            priority: Task priority
            webhook_url: Optional webhook URL

        Returns:
            The created Task record
        """
        with get_db_context() as db:
            task_record = Task(
                task_id=task_id,
                session_id=session_id,
                task_type=task_type,
                parameters=parameters,
                status=TaskStatus.PENDING.value,
                priority=priority,
                webhook_url=webhook_url,
            )
            db.add(task_record)
            db.commit()
            return task_record

    async def submit_to_celery(
        self, task_id: str, task_type: str, session_id: str, parameters: Dict[str, Any]
    ) -> AsyncResult:
        """
        Submit task to Celery with retry logic.

        Args:
            task_id: Task ID
            task_type: Task type
            session_id: Session ID
            parameters: Task parameters

        Returns:
            Celery AsyncResult

        Raises:
            Exception: If submission fails after retries
        """
        celery_task_name = self._task_map.get(task_type)
        if not celery_task_name:
            raise ValueError(f"No Celery task mapping for type: {task_type}")

        async def submit() -> AsyncResult:
            return await asyncio.to_thread(
                celery_app.send_task,
                celery_task_name,
                args=[session_id, parameters],
                task_id=task_id,
            )

        return await async_retry_with_backoff(submit, max_retries=3, base_delay=0.5)

    def mark_task_failed(self, task_id: str, error_message: str) -> None:
        """
        Mark a task as failed in the database.

        Args:
            task_id: Task ID
            error_message: Error message
        """
        with get_db_context() as db:
            task_record = db.query(Task).filter(Task.task_id == task_id).first()
            if task_record:
                task_record.status = TaskStatus.FAILED.value  # type: ignore[assignment]
                task_record.error_message = error_message  # type: ignore[assignment]
                task_record.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                db.commit()

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
            ValueError: If task type is invalid or parameters are invalid
        """
        # Validate task type
        self.validate_task_type(task_type)

        # Validate priority
        self.validate_priority(priority)

        # Validate and normalize parameters
        validated_params = self.validate_parameters(task_type, parameters)

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create task record
        self.create_task_record(
            task_id=task_id,
            session_id=session_id,
            task_type=task_type,
            parameters=validated_params,
            priority=priority,
            webhook_url=webhook_url,
        )

        logger.info(f"Task {task_id} created: {task_type} for session {session_id}")

        return task_id

    async def start_task_immediately(
        self, task_id: str, task_type: str, session_id: str, parameters: Dict[str, Any]
    ) -> None:
        """
        Start a task immediately by submitting to Celery.

        Args:
            task_id: Task ID
            task_type: Task type
            session_id: Session ID
            parameters: Task parameters

        Raises:
            Exception: If submission fails
        """
        try:
            await self.submit_to_celery(task_id, task_type, session_id, parameters)
            logger.info(f"Task {task_id} submitted immediately to Celery")
        except Exception as e:
            error_msg = f"Celery submission failed: {str(e)}"
            logger.error(f"Failed to submit task {task_id} to Celery: {error_msg}")
            self.mark_task_failed(task_id, error_msg)
            raise

    async def retry_task(
        self, task_id: str, task_type: str, session_id: str, parameters: Dict[str, Any]
    ) -> AsyncResult:
        """
        Retry a failed task.

        Args:
            task_id: Task ID
            task_type: Task type
            session_id: Session ID
            parameters: Task parameters

        Returns:
            Celery AsyncResult
        """
        # Reset task status to pending
        with get_db_context() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if task:
                task.status = TaskStatus.PENDING.value  # type: ignore[assignment]
                task.error_message = None  # type: ignore[assignment]
                task.completed_at = None  # type: ignore[assignment]
                db.commit()

        # Re-submit to Celery
        return await self.submit_to_celery(task_id, task_type, session_id, parameters)
