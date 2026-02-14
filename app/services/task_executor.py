"""
Task Executor Service

Manages asynchronous task execution via Celery.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import get_db_context
from app.database.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Manages task submission, status checking, and result retrieval."""

    # Map of task types to Celery task names
    TASK_MAP = {
        "iowa_gambling": "app.tasks.experimental_tasks.execute_iowa_gambling_task",
        "masking_paradigm": "app.tasks.experimental_tasks.execute_masking_paradigm_task",
        "attentional_blink": "app.tasks.experimental_tasks.execute_attentional_blink_task",
        "change_blindness": "app.tasks.experimental_tasks.execute_change_blindness_task",
        "binocular_rivalry": "app.tasks.experimental_tasks.execute_binocular_rivalry_task",
    }

    # Task metadata for listing
    TASK_INFO = {
        "iowa_gambling": {
            "name": "Iowa Gambling Task",
            "description": "Decision-making task with four decks of cards",
            "parameters": {
                "num_trials": {
                    "type": "integer",
                    "default": 100,
                    "description": "Number of trials",
                },
                "initial_balance": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Starting balance",
                },
                "deck_stimulus_strength": {
                    "type": "float",
                    "default": 1.5,
                    "description": "Deck visual strength",
                },
                "outcome_stimulus_strength": {
                    "type": "float",
                    "default": 2.0,
                    "description": "Outcome strength",
                },
                "interoceptive_gain": {
                    "type": "float",
                    "default": 1.0,
                    "description": "Interoceptive signal multiplier",
                },
                "deck_selection_strategy": {
                    "type": "string",
                    "default": "balanced",
                    "description": "Selection strategy",
                },
            },
        },
        "masking_paradigm": {
            "name": "Masking Paradigm Task",
            "description": "Visual masking experiment with varying SOAs",
            "parameters": {
                "target_duration_ms": {
                    "type": "float",
                    "default": 50.0,
                    "description": "Target presentation duration",
                },
                "soas": {
                    "type": "array",
                    "default": [0, 17, 33, 50, 67, 83, 100, 150, 200, 300],
                    "description": "SOAs to test",
                },
                "mask_duration_ms": {
                    "type": "float",
                    "default": 100.0,
                    "description": "Mask presentation duration",
                },
                "num_trials_per_condition": {
                    "type": "integer",
                    "default": 20,
                    "description": "Trials per SOA",
                },
                "target_strength": {
                    "type": "float",
                    "default": 2.0,
                    "description": "Target stimulus strength",
                },
                "mask_strength": {
                    "type": "float",
                    "default": 3.0,
                    "description": "Mask stimulus strength",
                },
            },
        },
        "attentional_blink": {
            "name": "Attentional Blink Task",
            "description": "RSVP task measuring attentional blink effect",
            "parameters": {
                "stream_length": {
                    "type": "integer",
                    "default": 15,
                    "description": "Number of items in RSVP stream",
                },
                "item_duration_ms": {
                    "type": "float",
                    "default": 100.0,
                    "description": "Duration of each item",
                },
                "num_trials_per_lag": {
                    "type": "integer",
                    "default": 20,
                    "description": "Trials per lag condition",
                },
                "lags": {
                    "type": "array",
                    "default": [1, 2, 3, 4, 8],
                    "description": "Lags to test",
                },
                "target_salience": {
                    "type": "float",
                    "default": 2.0,
                    "description": "Target salience boost",
                },
            },
        },
        "change_blindness": {
            "name": "Change Blindness Task",
            "description": "Flicker paradigm for change detection",
            "parameters": {
                "image_size": {
                    "type": "array",
                    "default": [256, 256],
                    "description": "Image dimensions",
                },
                "change_magnitude": {
                    "type": "float",
                    "default": 0.3,
                    "description": "Magnitude of change",
                },
                "flicker_duration_ms": {
                    "type": "float",
                    "default": 100.0,
                    "description": "Flicker duration",
                },
                "num_trials": {"type": "integer", "default": 50, "description": "Number of trials"},
            },
        },
        "binocular_rivalry": {
            "name": "Binocular Rivalry Task",
            "description": "Binocular rivalry with competing patterns",
            "parameters": {
                "pattern_size": {
                    "type": "array",
                    "default": [256, 256],
                    "description": "Pattern dimensions",
                },
                "contrast_left": {
                    "type": "float",
                    "default": 1.0,
                    "description": "Left eye contrast",
                },
                "contrast_right": {
                    "type": "float",
                    "default": 1.0,
                    "description": "Right eye contrast",
                },
                "duration_seconds": {
                    "type": "float",
                    "default": 60.0,
                    "description": "Trial duration",
                },
                "sampling_rate_hz": {
                    "type": "float",
                    "default": 30.0,
                    "description": "Sampling rate",
                },
            },
        },
    }

    async def list_available_tasks(self) -> Dict[str, Any]:
        """
        List all available experimental tasks.

        Returns:
            Dict with list of available tasks and their metadata
        """
        tasks = []
        for task_type, info in self.TASK_INFO.items():
            tasks.append(
                {
                    "task_type": task_type,
                    "name": info["name"],
                    "description": info["description"],
                    "parameters": info["parameters"],
                }
            )

        return {"tasks": tasks}

    async def submit_task(
        self,
        session_id: str,
        task_type: str,
        parameters: Dict[str, Any],
        webhook_url: Optional[str] = None,
    ) -> str:
        """
        Submit a task for asynchronous execution.

        Args:
            session_id: Session identifier
            task_type: Type of experimental task
            parameters: Task parameters
            webhook_url: Optional webhook URL for completion notification

        Returns:
            Task ID

        Raises:
            ValueError: If task type is invalid
        """
        # Validate task type
        if task_type not in self.TASK_MAP:
            raise ValueError(
                f"Invalid task type: {task_type}. "
                f"Available types: {', '.join(self.TASK_MAP.keys())}"
            )

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create task record in database
        with get_db_context() as db:
            task_record = Task(
                task_id=task_id,
                session_id=session_id,
                task_type=task_type,
                parameters=parameters,
                status=TaskStatus.PENDING.value,
                webhook_url=webhook_url,
            )
            db.add(task_record)
            db.commit()

        # Submit task to Celery
        celery_task_name = self.TASK_MAP[task_type]
        celery_app.send_task(
            celery_task_name,
            args=[session_id, parameters],
            task_id=task_id,
        )

        logger.info(f"Task {task_id} submitted: {task_type} for session {session_id}")

        return task_id

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and results.

        Args:
            task_id: Task identifier

        Returns:
            Dict with task status, state, result, and error information

        Raises:
            ValueError: If task not found
        """
        # Get task from database
        with get_db_context() as db:
            task_record = db.query(Task).filter(Task.task_id == task_id).first()

            if not task_record:
                raise ValueError(f"Task {task_id} not found")

            # Get Celery task result
            async_result = AsyncResult(task_id, app=celery_app)

            # Build status response
            status_info = {
                "status": task_record.status,
                "state": async_result.state,
                "result": task_record.result_data,
                "error": task_record.error_message,
                "info": None,
            }

            # Add progress info if available
            if async_result.state == "STARTED" and async_result.info:
                status_info["info"] = async_result.info

            return status_info

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task.

        Args:
            task_id: Task identifier

        Returns:
            Dict with cancellation status

        Raises:
            ValueError: If task not found
        """
        # Get task from database
        with get_db_context() as db:
            task_record = db.query(Task).filter(Task.task_id == task_id).first()

            if not task_record:
                raise ValueError(f"Task {task_id} not found")

            # Revoke Celery task
            celery_app.control.revoke(task_id, terminate=True)

            # Update task status in database
            task_record.status = TaskStatus.FAILED.value
            task_record.error_message = "Task cancelled by user"
            task_record.completed_at = datetime.utcnow()
            db.commit()

            logger.info(f"Task {task_id} cancelled")

            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task cancellation requested",
            }
