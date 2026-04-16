"""
Experimental Task Celery Tasks

Celery tasks for executing experimental paradigms (Iowa Gambling, Masking, Attentional Blink).
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Add /app to Python path for proper imports
sys.path.insert(0, "/app")

from app.database.connection import get_db
from app.database.models import Task as TaskModel
from celery import Task

# apgi_system is an optional dependency for experimental paradigms
try:
    from apgi_system.experiments.tasks.attentional_blink import AttentionalBlinkTask  # type: ignore[import-untyped]
    from apgi_system.experiments.tasks.binocular_rivalry import BinocularRivalryTask  # type: ignore[import-untyped]
    from apgi_system.experiments.tasks.change_blindness import ChangeBlindnessTask  # type: ignore[import-untyped]
    from apgi_system.experiments.tasks.iowa_gambling import IowaGamblingTask  # type: ignore[import-untyped]
    from apgi_system.experiments.tasks.masking_paradigm import MaskingParadigmTask  # type: ignore[import-untyped]
    from apgi_system.platform_utils import get_resource_path  # type: ignore[import-untyped]
    from apgi_system.system import APGISystem  # type: ignore[import-untyped]

    APGI_SYSTEM_AVAILABLE = True
except ImportError:
    APGI_SYSTEM_AVAILABLE = False
    AttentionalBlinkTask = None
    BinocularRivalryTask = None
    ChangeBlindnessTask = None
    IowaGamblingTask = None
    MaskingParadigmTask = None
    get_resource_path = None
    APGISystem = None
    logging.getLogger(__name__).warning("apgi_system not available - experimental tasks disabled")

from app.celery_app import celery_app
from app.services.webhook_manager import WebhookManager

logger = logging.getLogger(__name__)

# Explicit exports for mypy
__all__ = [
    "APGITask",
    "execute_iowa_gambling_task",
    "execute_masking_paradigm_task",
    "execute_attentional_blink_task",
    "execute_change_blindness_task",
    "execute_binocular_rivalry_task",
    "trigger_webhook_on_completion",
    "APGI_SYSTEM_AVAILABLE",
    "AttentionalBlinkTask",
    "BinocularRivalryTask",
    "ChangeBlindnessTask",
    "IowaGamblingTask",
    "MaskingParadigmTask",
    "get_resource_path",
    "APGISystem",
    "celery_app",
    "WebhookManager",
]


async def trigger_webhook_on_completion(task_id: str, result: Dict[str, Any]) -> None:
    """
    Trigger webhook delivery when task completes and start dependent tasks.

    Args:
        task_id: Celery task ID
        result: Task result data
    """
    try:
        # Get database session
        db = next(get_db())

        # Find task record
        task_record = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()

        if not task_record:
            logger.warning(f"Task record not found for task {task_id}")
            return

        # Update task status in database
        task_record.status = result.get("status", "completed")
        task_record.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        task_record.result_data = result  # type: ignore[assignment]

        if result.get("status") == "failed":
            task_record.error_message = result.get("error")  # type: ignore[assignment]

        db.commit()

        # Start dependent tasks that were waiting for this task to complete
        try:
            from app.services.task_executor import TaskExecutor

            task_executor = TaskExecutor()
            await task_executor.check_and_start_pending_tasks(task_record.session_id)  # type: ignore[arg-type]
            logger.info(f"Checked for dependent tasks after completion of {task_id}")
        except Exception as e:
            logger.error(f"Failed to check dependent tasks for {task_id}: {e}")

        # Check if webhook URL is configured
        if task_record.webhook_url:
            logger.info(f"Triggering webhook for task {task_id} to {task_record.webhook_url}")

            # Create webhook payload
            payload = {
                "task_id": task_id,
                "session_id": task_record.session_id,
                "task_type": task_record.task_type,
                "status": result.get("status", "completed"),
                "completed_at": datetime.now(timezone.utc).isoformat() + "Z",
                "result": result,
            }

            # Create webhook delivery
            webhook_manager = WebhookManager()
            delivery_id = await webhook_manager.create_webhook_delivery(
                db=db, task_id=task_id, webhook_url=task_record.webhook_url, payload=payload  # type: ignore[arg-type]
            )

            # Attempt immediate delivery
            await webhook_manager.deliver_webhook(db, delivery_id)
            await webhook_manager.close()

            logger.info(f"Webhook delivery {delivery_id} created for task {task_id}")
        else:
            logger.debug(f"No webhook URL configured for task {task_id}")

        db.close()

    except Exception as e:
        logger.error(f"Failed to trigger webhook for task {task_id}: {e}", exc_info=True)


class APGITask(Task):  # type: ignore[misc]
    """Base task class with APGI system initialization."""

    _apgi_system: Any = None

    @property
    def apgi_system(self) -> Any:
        """Lazy initialization of APGI system."""
        if self._apgi_system is None:
            if not APGI_SYSTEM_AVAILABLE or APGISystem is None or get_resource_path is None:
                raise ImportError("APGI system not available - apgi_system not installed")
            # Use platform-aware resource path resolution
            self._apgi_system = APGISystem(
                config_path=str(get_resource_path("config/default.yaml"))
            )
        return self._apgi_system


@celery_app.task(
    bind=True, base=APGITask, name="app.tasks.experimental_tasks.execute_iowa_gambling_task"
)  # type: ignore[misc]
def execute_iowa_gambling_task(
    self: Any, session_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Iowa Gambling Task.

    Args:
        session_id: Session identifier
        parameters: Task parameters including:
            - num_trials: Number of trials (default: 100)
            - initial_balance: Starting balance (default: 2000)
            - deck_stimulus_strength: Deck visual strength (default: 1.5)
            - outcome_stimulus_strength: Outcome strength (default: 2.0)
            - interoceptive_gain: Interoceptive signal multiplier (default: 1.0)
            - deck_selection_strategy: 'balanced', 'random', or 'participant_choice' (default: 'balanced')

    Returns:
        Dict with task results and analysis
    """
    logger.info(f"Starting Iowa Gambling Task for session {session_id}")

    if not APGI_SYSTEM_AVAILABLE or IowaGamblingTask is None:
        return {
            "task_type": "iowa_gambling",
            "session_id": session_id,
            "status": "failed",
            "error": "IowaGamblingTask not available - apgi_system not installed",
        }

    result = None
    try:
        # Extract parameters with defaults
        num_trials = parameters.get("num_trials", 100)
        initial_balance = parameters.get("initial_balance", 2000)
        deck_stimulus_strength = parameters.get("deck_stimulus_strength", 1.5)
        outcome_stimulus_strength = parameters.get("outcome_stimulus_strength", 2.0)
        interoceptive_gain = parameters.get("interoceptive_gain", 1.0)
        deck_selection_strategy = parameters.get("deck_selection_strategy", "balanced")

        # Create task instance
        task = IowaGamblingTask(
            num_trials=num_trials,
            initial_balance=initial_balance,
            deck_stimulus_strength=deck_stimulus_strength,
            outcome_stimulus_strength=outcome_stimulus_strength,
            interoceptive_gain=interoceptive_gain,
            deck_selection_strategy=deck_selection_strategy,
        )

        # Run all trials
        results = task.run_all_trials(self.apgi_system)

        logger.info(f"Iowa Gambling Task completed for session {session_id}")

        result = {
            "task_type": "iowa_gambling",
            "session_id": session_id,
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Iowa Gambling Task failed for session {session_id}: {e}", exc_info=True)
        result = {
            "task_type": "iowa_gambling",
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
        }

    # Trigger webhook on completion (async)
    import asyncio

    try:
        asyncio.run(trigger_webhook_on_completion(self.request.id, result))
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}", exc_info=True)

    return result


@celery_app.task(
    bind=True, base=APGITask, name="app.tasks.experimental_tasks.execute_masking_paradigm_task"
)  # type: ignore[misc]
def execute_masking_paradigm_task(
    self: Any, session_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Masking Paradigm Task.

    Args:
        session_id: Session identifier
        parameters: Task parameters including:
            - target_duration_ms: Target presentation duration (default: 50.0)
            - soas: List of SOAs to test in ms (default: [0, 17, 33, 50, 67, 83, 100, 150, 200, 300])
            - mask_duration_ms: Mask presentation duration (default: 100.0)
            - num_trials_per_condition: Trials per SOA (default: 20)
            - target_strength: Target stimulus strength (default: 2.0)
            - mask_strength: Mask stimulus strength (default: 3.0)

    Returns:
        Dict with task results and analysis
    """
    logger.info(f"Starting Masking Paradigm Task for session {session_id}")

    if not APGI_SYSTEM_AVAILABLE or MaskingParadigmTask is None:
        return {
            "task_type": "masking_paradigm",
            "session_id": session_id,
            "status": "failed",
            "error": "MaskingParadigmTask not available - apgi_system not installed",
        }

    result = None
    try:
        # Extract parameters with defaults
        target_duration_ms = parameters.get("target_duration_ms", 50.0)
        soas = parameters.get("soas", [50.0, 100.0, 150.0])
        mask_duration_ms = parameters.get("mask_duration_ms", 100.0)
        num_trials_per_condition = parameters.get("num_trials_per_condition", 20)
        target_strength = parameters.get("target_strength", 2.0)
        mask_strength = parameters.get("mask_strength", 3.0)

        # Create task instance
        # noqa: E501 - Parameters are from external apgi_system classes
        task = MaskingParadigmTask(
            target_duration_ms=target_duration_ms,
            soas=soas,
            mask_duration_ms=mask_duration_ms,
            num_trials_per_condition=num_trials_per_condition,
            target_strength=target_strength,
            mask_strength=mask_strength,
        )

        # Run all trials
        results = task.run_all_trials(self.apgi_system)

        logger.info(f"Masking Paradigm Task completed for session {session_id}")

        result = {
            "task_type": "masking_paradigm",
            "session_id": session_id,
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Masking Paradigm Task failed for session {session_id}: {e}", exc_info=True)
        result = {
            "task_type": "masking_paradigm",
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
        }

    # Trigger webhook on completion (async)
    import asyncio

    try:
        asyncio.run(trigger_webhook_on_completion(self.request.id, result))
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}", exc_info=True)

    return result


@celery_app.task(
    bind=True, base=APGITask, name="app.tasks.experimental_tasks.execute_attentional_blink_task"
)  # type: ignore[misc]
def execute_attentional_blink_task(
    self: Any, session_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Attentional Blink Task.

    Args:
        session_id: Session identifier
        parameters: Task parameters including:
            - stream_length: Number of items in RSVP stream (default: 15)
            - item_duration_ms: Duration of each item (default: 100.0)
            - num_trials_per_lag: Trials per lag condition (default: 10)
            - lags: List of lags to test (default: [1, 2, 3, 4, 8])
            - target_salience: Target salience boost (default: 2.0)

    Returns:
        Dict with task results and analysis
    """
    logger.info(f"Starting Attentional Blink Task for session {session_id}")

    if not APGI_SYSTEM_AVAILABLE or AttentionalBlinkTask is None:
        return {
            "task_type": "attentional_blink",
            "session_id": session_id,
            "status": "failed",
            "error": "AttentionalBlinkTask not available - apgi_system not installed",
        }

    result = None
    try:
        # Extract parameters with defaults
        stream_length = parameters.get("stream_length", 15)
        item_duration_ms = parameters.get("item_duration_ms", 100.0)
        num_trials_per_lag = parameters.get("num_trials_per_lag", 10)
        lags = parameters.get("lags", [1, 2, 3, 4, 8])
        target_salience = parameters.get("target_salience", 2.0)

        # Create task instance
        # noqa: E501 - Parameters are from external apgi_system classes
        task = AttentionalBlinkTask(
            stream_length=stream_length,
            item_duration_ms=item_duration_ms,
            num_trials_per_lag=num_trials_per_lag,
            lags=lags,
            target_salience=target_salience,
        )

        # Run all trials
        results = task.run_all_trials(self.apgi_system)

        logger.info(f"Attentional Blink Task completed for session {session_id}")

        result = {
            "task_type": "attentional_blink",
            "session_id": session_id,
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Attentional Blink Task failed for session {session_id}: {e}", exc_info=True)
        result = {
            "task_type": "attentional_blink",
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
        }

    # Trigger webhook on completion (async)
    import asyncio

    try:
        asyncio.run(trigger_webhook_on_completion(self.request.id, result))
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}", exc_info=True)

    return result


@celery_app.task(
    bind=True, base=APGITask, name="app.tasks.experimental_tasks.execute_change_blindness_task"
)  # type: ignore[misc]
def execute_change_blindness_task(
    self: Any, session_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Change Blindness Task.

    Args:
        session_id: Session identifier
        parameters: Task parameters

    Returns:
        Dict with task results and analysis
    """
    logger.info(f"Starting Change Blindness Task for session {session_id}")

    if not APGI_SYSTEM_AVAILABLE or ChangeBlindnessTask is None:
        return {
            "task_type": "change_blindness",
            "session_id": session_id,
            "status": "failed",
            "error": "ChangeBlindnessTask not available - apgi_system not installed",
        }

    result = None
    try:
        # Extract parameters with defaults
        image_size = parameters.get("image_size", (128, 128))
        change_magnitude = parameters.get("change_magnitude", 0.3)
        flicker_duration_ms = parameters.get("flicker_duration_ms", 100.0)
        num_trials = parameters.get("num_trials", 50)

        # Create task instance
        # noqa: E501 - Parameters are from external apgi_system classes
        # type: ignore[arg-type] - External library parameters
        task = ChangeBlindnessTask(
            image_size=image_size,  # type: ignore[arg-type]
            change_magnitude=change_magnitude,  # type: ignore[arg-type]
            flicker_duration_ms=flicker_duration_ms,  # type: ignore[arg-type]
            num_trials=num_trials,  # type: ignore[arg-type]
        )

        # Run all trials
        results = task.run_all_trials(self.apgi_system)

        logger.info(f"Change Blindness Task completed for session {session_id}")

        result = {
            "task_type": "change_blindness",
            "session_id": session_id,
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Change Blindness Task failed for session {session_id}: {e}", exc_info=True)
        result = {
            "task_type": "change_blindness",
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
        }

    # Trigger webhook on completion (async)
    import asyncio

    try:
        asyncio.run(trigger_webhook_on_completion(self.request.id, result))
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}", exc_info=True)

    return result


@celery_app.task(
    bind=True, base=APGITask, name="app.tasks.experimental_tasks.execute_binocular_rivalry_task"
)  # type: ignore[misc]
def execute_binocular_rivalry_task(
    self: Any, session_id: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Binocular Rivalry Task.

    Args:
        session_id: Session identifier
        parameters: Task parameters

    Returns:
        Dict with task results and analysis
    """
    logger.info(f"Starting Binocular Rivalry Task for session {session_id}")

    if not APGI_SYSTEM_AVAILABLE or BinocularRivalryTask is None:
        return {
            "task_type": "binocular_rivalry",
            "session_id": session_id,
            "status": "failed",
            "error": "BinocularRivalryTask not available - apgi_system not installed",
        }

    result = None
    try:
        # Extract parameters with defaults
        pattern_size = parameters.get("pattern_size", (128, 128))
        contrast_left = parameters.get("contrast_left", 1.0)
        contrast_right = parameters.get("contrast_right", 1.0)
        duration_seconds = parameters.get("duration_seconds", 60.0)
        sampling_rate_hz = parameters.get("sampling_rate_hz", 30.0)

        # Create task instance
        # noqa: E501 - Parameters are from external apgi_system classes
        # type: ignore[arg-type] - External library parameters
        task = BinocularRivalryTask(
            pattern_size=pattern_size,  # type: ignore[arg-type]
            contrast_left=contrast_left,  # type: ignore[arg-type]
            contrast_right=contrast_right,  # type: ignore[arg-type]
            duration_seconds=duration_seconds,  # type: ignore[arg-type]
            sampling_rate_hz=sampling_rate_hz,  # type: ignore[arg-type]
        )

        # Run all trials
        results = task.run_all_trials(self.apgi_system)

        logger.info(f"Binocular Rivalry Task completed for session {session_id}")

        result = {
            "task_type": "binocular_rivalry",
            "session_id": session_id,
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Binocular Rivalry Task failed for session {session_id}: {e}", exc_info=True)
        result = {
            "task_type": "binocular_rivalry",
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
        }

    # Trigger webhook on completion (async)
    import asyncio

    try:
        asyncio.run(trigger_webhook_on_completion(self.request.id, result))
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}", exc_info=True)

    return result
