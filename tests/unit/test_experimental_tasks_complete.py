"""
Comprehensive Adversarial Test Suite for Experimental Tasks
Tests Celery bound tasks with proper mocking of self (task instance).
"""

import sys
from typing import Any, Callable, Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level helpers: ensure the Celery @task decorator returns raw functions
# ---------------------------------------------------------------------------

def _mock_celery_task_decorator(
    *args: Any, bind: bool = False, base: Any = None, name: str | None = None, **kwargs: Any
) -> Callable[..., Any]:
    """Return the decorated function unchanged."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "name", name or func.__name__)
        setattr(func, "bind", bind)
        setattr(func, "base", base)
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


@pytest.fixture(autouse=True)
def _fix_celery_mock_and_reload() -> Generator[None, None, None]:
    """
    Runs after conftest's mock_celery_app replaces sys.modules['app.celery_app'] with a
    bare MagicMock.  We patch that mock's .celery_app.task with our pass-through decorator,
    then force experimental_tasks to reimport so @celery_app.task returns raw functions.
    """
    celery_mod = sys.modules.get("app.celery_app")
    if celery_mod is not None:
        celery_mod.celery_app.task.side_effect = _mock_celery_task_decorator
    # Force fresh import of the task module so the decorator fires again
    sys.modules.pop("app.tasks.experimental_tasks", None)
    sys.modules.pop("app.tasks", None)
    yield
    sys.modules.pop("app.tasks.experimental_tasks", None)
    sys.modules.pop("app.tasks", None)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_celery_task() -> MagicMock:
    """Create a mock Celery task instance that mimics APGITask."""
    from app.tasks.experimental_tasks import APGITask  # fresh import after clear
    task = MagicMock(spec=APGITask)
    task.request = MagicMock()
    task.request.id = "celery-task-id-123"
    return task


@pytest.fixture
def mock_apgi_system() -> MagicMock:
    """Create a fully mocked APGI system."""
    system = MagicMock()
    system.run_all_trials = MagicMock(
        return_value={"trials": [{"result": "success"}], "summary": {"total": 100}}
    )
    return system


# ============================================================================
# Iowa Gambling Task Tests
# ============================================================================


class TestIowaGamblingTask:
    """Tests for execute_iowa_gambling_task Celery task."""

    def test_execute_iowa_gambling_task_apgi_unavailable(self, mock_celery_task: MagicMock) -> None:
        """Test when APGI system is not available (Lines 160-166)."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.IowaGamblingTask", None):
                from app.tasks.experimental_tasks import execute_iowa_gambling_task

                result = execute_iowa_gambling_task(
                    mock_celery_task, session_id="session-123", parameters={}
                )

                assert result["status"] == "failed"
                assert "not available" in result["error"].lower()

    def test_execute_iowa_gambling_task_success(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test successful Iowa Gambling task execution."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"trials": [{"deck": "A", "outcome": 100}], "final_balance": 2500}
                )
                mock_task_class.return_value = instance

                # Mock the apgi_system property on the task instance
                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_iowa_gambling_task

                result = execute_iowa_gambling_task(
                    mock_celery_task,
                    session_id="session-123",
                    parameters={
                        "num_trials": 100,
                        "initial_balance": 2000,
                        "deck_stimulus_strength": 1.5,
                        "outcome_stimulus_strength": 2.0,
                        "interoceptive_gain": 1.0,
                        "deck_selection_strategy": "balanced",
                    },
                )

                assert result["status"] == "completed"
                assert result["task_type"] == "iowa_gambling"
                assert result["session_id"] == "session-123"

    def test_execute_iowa_gambling_task_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test exception handling during task execution (Lines 200-207)."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(side_effect=Exception("Task failed"))
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_iowa_gambling_task

                result = execute_iowa_gambling_task(
                    mock_celery_task, session_id="session-123", parameters={}
                )

                assert result["status"] == "failed"
                assert "task failed" in result["error"].lower()

    def test_execute_iowa_gambling_task_webhook_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test webhook trigger exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"trials": [{"deck": "A", "outcome": 100}], "final_balance": 2500}
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                async def mock_run_with_exception(coro):
                    try:
                        await coro
                    except Exception:
                        pass
                    raise Exception("Webhook failed")

                with patch("asyncio.run", side_effect=mock_run_with_exception):
                    from app.tasks.experimental_tasks import execute_iowa_gambling_task

                    result = execute_iowa_gambling_task(
                        mock_celery_task, session_id="session-123", parameters={}
                    )

                    # Task should still complete successfully despite webhook failure
                    assert result["status"] == "completed"


# ============================================================================
# Masking Paradigm Task Tests
# ============================================================================


class TestMaskingParadigmTask:
    """Tests for execute_masking_paradigm_task Celery task."""

    def test_execute_masking_paradigm_task_apgi_unavailable(
        self, mock_celery_task: MagicMock
    ) -> None:
        """Test when APGI system is not available."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.MaskingParadigmTask", None):
                from app.tasks.experimental_tasks import execute_masking_paradigm_task

                result = execute_masking_paradigm_task(
                    mock_celery_task, session_id="session-456", parameters={}
                )

                assert result["status"] == "failed"
                assert "not available" in result["error"].lower()

    def test_execute_masking_paradigm_task_success(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test successful Masking Paradigm task execution."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.MaskingParadigmTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"soas": [50, 100, 150], "accuracy": [0.8, 0.9, 0.95]}
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_masking_paradigm_task

                result = execute_masking_paradigm_task(
                    mock_celery_task,
                    session_id="session-456",
                    parameters={
                        "target_duration_ms": 50.0,
                        "soas": [0, 17, 33, 50, 67, 83, 100, 150, 200, 300],
                        "mask_duration_ms": 100.0,
                        "num_trials_per_condition": 20,
                        "target_strength": 2.0,
                        "mask_strength": 3.0,
                    },
                )

                assert result["status"] == "completed"
                assert result["task_type"] == "masking_paradigm"

    def test_execute_masking_paradigm_task_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.MaskingParadigmTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(side_effect=Exception("Masking failed"))
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_masking_paradigm_task

                result = execute_masking_paradigm_task(
                    mock_celery_task, session_id="session-456", parameters={}
                )

                assert result["status"] == "failed"
                assert "masking failed" in result["error"].lower()

    def test_execute_masking_paradigm_task_webhook_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test webhook trigger exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.MaskingParadigmTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"trials": [{"mask": "forward", "response": "correct"}], "accuracy": 0.85}
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                async def mock_run_with_exception(coro):
                    # Await the coroutine to avoid warnings, then raise exception
                    try:
                        await coro
                    except Exception:
                        pass
                    raise Exception("Webhook failed")

                with patch("asyncio.run", side_effect=mock_run_with_exception):
                    from app.tasks.experimental_tasks import execute_masking_paradigm_task

                    result = execute_masking_paradigm_task(
                        mock_celery_task, session_id="session-xyz", parameters={}
                    )

                    assert result["status"] == "completed"


# ============================================================================
# Attentional Blink Task Tests
# ============================================================================


class TestAttentionalBlinkTask:
    """Tests for execute_attentional_blink_task Celery task."""

    def test_execute_attentional_blink_task_apgi_unavailable(
        self, mock_celery_task: MagicMock
    ) -> None:
        """Test when APGI system is not available."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.AttentionalBlinkTask", None):
                from app.tasks.experimental_tasks import execute_attentional_blink_task

                result = execute_attentional_blink_task(
                    mock_celery_task, session_id="session-789", parameters={}
                )

                assert result["status"] == "failed"
                assert "not available" in result["error"].lower()

    def test_execute_attentional_blink_task_success(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test successful Attentional Blink task execution."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.AttentionalBlinkTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={
                        "lags": [1, 2, 3, 4, 8],
                        "detection_rates": [0.9, 0.7, 0.5, 0.3, 0.2],
                    }
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_attentional_blink_task

                result = execute_attentional_blink_task(
                    mock_celery_task,
                    session_id="session-789",
                    parameters={
                        "stream_length": 15,
                        "item_duration_ms": 100.0,
                        "num_trials_per_lag": 10,
                        "lags": [1, 2, 3, 4, 8],
                        "target_salience": 2.0,
                    },
                )

                assert result["status"] == "completed"
                assert result["task_type"] == "attentional_blink"

    def test_execute_attentional_blink_task_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.AttentionalBlinkTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(side_effect=Exception("Blink task failed"))
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_attentional_blink_task

                result = execute_attentional_blink_task(
                    mock_celery_task, session_id="session-789", parameters={}
                )

                assert result["status"] == "failed"
                assert "blink task failed" in result["error"].lower()

    def test_execute_attentional_blink_task_webhook_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test webhook trigger exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.AttentionalBlinkTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={
                        "lags": [1, 2, 3, 4, 8],
                        "detection_rates": [0.9, 0.7, 0.5, 0.3, 0.2],
                    }
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                async def mock_run_with_exception(coro):
                    try:
                        await coro
                    except Exception:
                        pass
                    raise Exception("Webhook failed")

                with patch("asyncio.run", side_effect=mock_run_with_exception):
                    from app.tasks.experimental_tasks import execute_attentional_blink_task

                    result = execute_attentional_blink_task(
                        mock_celery_task, session_id="session-789", parameters={}
                    )

                    assert result["status"] == "completed"


# ============================================================================
# Change Blindness Task Tests
# ============================================================================


class TestChangeBlindnessTask:
    """Tests for execute_change_blindness_task Celery task."""

    def test_execute_change_blindness_task_apgi_unavailable(
        self, mock_celery_task: MagicMock
    ) -> None:
        """Test when APGI system is not available."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.ChangeBlindnessTask", None):
                from app.tasks.experimental_tasks import execute_change_blindness_task

                result = execute_change_blindness_task(
                    mock_celery_task, session_id="session-abc", parameters={}
                )

                assert result["status"] == "failed"
                assert "not available" in result["error"].lower()

    def test_execute_change_blindness_task_success(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test successful Change Blindness task execution."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.ChangeBlindnessTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"trials": [{"detected": True, "rt": 500}], "detection_rate": 0.75}
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_change_blindness_task

                result = execute_change_blindness_task(
                    mock_celery_task,
                    session_id="session-abc",
                    parameters={
                        "image_size": (128, 128),
                        "change_magnitude": 0.3,
                        "flicker_duration_ms": 100.0,
                        "num_trials": 50,
                    },
                )

                assert result["status"] == "completed"
                assert result["task_type"] == "change_blindness"

    def test_execute_change_blindness_task_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.ChangeBlindnessTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    side_effect=Exception("Change detection failed")
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_change_blindness_task

                result = execute_change_blindness_task(
                    mock_celery_task, session_id="session-abc", parameters={}
                )

                assert result["status"] == "failed"
                assert "change detection failed" in result["error"].lower()

    def test_execute_change_blindness_task_webhook_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test webhook trigger exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.ChangeBlindnessTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={"trials": [{"detected": True, "rt": 500}], "detection_rate": 0.75}
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                async def mock_run_with_exception(coro):
                    try:
                        await coro
                    except Exception:
                        pass
                    raise Exception("Webhook failed")

                with patch("asyncio.run", side_effect=mock_run_with_exception):
                    from app.tasks.experimental_tasks import execute_change_blindness_task

                    result = execute_change_blindness_task(
                        mock_celery_task, session_id="session-abc", parameters={}
                    )

                    assert result["status"] == "completed"


# ============================================================================
# Binocular Rivalry Task Tests
# ============================================================================


class TestBinocularRivalryTask:
    """Tests for execute_binocular_rivalry_task Celery task."""

    def test_execute_binocular_rivalry_task_apgi_unavailable(
        self, mock_celery_task: MagicMock
    ) -> None:
        """Test when APGI system is not available."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.BinocularRivalryTask", None):
                from app.tasks.experimental_tasks import execute_binocular_rivalry_task

                result = execute_binocular_rivalry_task(
                    mock_celery_task, session_id="session-def", parameters={}
                )

                assert result["status"] == "failed"
                assert "not available" in result["error"].lower()

    def test_execute_binocular_rivalry_task_success(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test successful Binocular Rivalry task execution."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.BinocularRivalryTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={
                        "percepts": [{"left": True, "duration": 1000}],
                        "alternation_rate": 0.5,
                    }
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_binocular_rivalry_task

                result = execute_binocular_rivalry_task(
                    mock_celery_task,
                    session_id="session-def",
                    parameters={
                        "pattern_size": (128, 128),
                        "contrast_left": 1.0,
                        "contrast_right": 1.0,
                        "duration_seconds": 60.0,
                        "sampling_rate_hz": 30.0,
                    },
                )

                assert result["status"] == "completed"
                assert result["task_type"] == "binocular_rivalry"

    def test_execute_binocular_rivalry_task_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.BinocularRivalryTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(side_effect=Exception("Rivalry task failed"))
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                from app.tasks.experimental_tasks import execute_binocular_rivalry_task

                result = execute_binocular_rivalry_task(
                    mock_celery_task, session_id="session-def", parameters={}
                )

                assert result["status"] == "failed"
                assert "rivalry task failed" in result["error"].lower()

    def test_execute_binocular_rivalry_task_webhook_exception(
        self, mock_celery_task: MagicMock, mock_apgi_system: MagicMock
    ) -> None:
        """Test webhook trigger exception handling."""
        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.BinocularRivalryTask") as mock_task_class:
                instance = MagicMock()
                instance.run_all_trials = MagicMock(
                    return_value={
                        "percepts": [{"left": True, "duration": 1000}],
                        "alternation_rate": 0.5,
                    }
                )
                mock_task_class.return_value = instance

                type(mock_celery_task).apgi_system = PropertyMock(return_value=mock_apgi_system)

                async def mock_run_with_exception(coro):
                    try:
                        await coro
                    except Exception:
                        pass
                    raise Exception("Webhook failed")

                with patch("asyncio.run", side_effect=mock_run_with_exception):
                    from app.tasks.experimental_tasks import execute_binocular_rivalry_task

                    result = execute_binocular_rivalry_task(
                        mock_celery_task, session_id="session-xyz", parameters={}
                    )

                    assert result["status"] == "completed"


# ============================================================================
# Webhook Integration Tests
# ============================================================================


class TestWebhookIntegration:
    """Tests for webhook triggering on task completion."""

    @pytest.mark.asyncio
    async def test_trigger_webhook_on_completion_success(self) -> None:
        """Test successful webhook triggering."""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_task.webhook_url = "https://example.com/webhook"
        mock_task.session_id = "session-123"
        mock_task.task_type = "iowa_gambling"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.tasks.experimental_tasks.get_db", return_value=iter([mock_db])):
            with patch("app.tasks.experimental_tasks.WebhookManager") as mock_webhook_class:
                mock_webhook = MagicMock()
                mock_webhook.create_webhook_delivery = AsyncMock(return_value="delivery-123")
                mock_webhook.deliver_webhook = AsyncMock()
                mock_webhook.close = AsyncMock()
                mock_webhook_class.return_value = mock_webhook

                # Patch TaskExecutor where it's imported inside the function
                with patch("app.services.task_executor.TaskExecutor") as mock_executor_class:
                    mock_executor = MagicMock()
                    mock_executor.check_and_start_pending_tasks = AsyncMock()
                    mock_executor_class.return_value = mock_executor

                    from app.tasks.experimental_tasks import trigger_webhook_on_completion
                    result = {"status": "completed", "data": "test"}
                    await trigger_webhook_on_completion("task-123", result)

                    assert mock_task.status == "completed"
                    mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_trigger_webhook_task_record_not_found(self) -> None:
        """Test when task record is not found."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.tasks.experimental_tasks.get_db", return_value=iter([mock_db])):
            result = {"status": "completed"}
            await trigger_webhook_on_completion("nonexistent-task", result)

            mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_webhook_exception(self) -> None:
        """Test exception handling in webhook trigger."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        with patch("app.tasks.experimental_tasks.get_db", side_effect=Exception("Database error")):
            result = {"status": "completed"}
            await trigger_webhook_on_completion("task-123", result)


# ============================================================================
# APGITask Base Class Tests
# ============================================================================


class TestAPGITaskBase:
    """Tests for APGITask base class."""

    def test_apgi_system_import_error(self) -> None:
        """Test import error handling when APGI not available."""
        from app.tasks.experimental_tasks import APGITask

        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", False):
            with patch("app.tasks.experimental_tasks.APGISystem", None):
                task = APGITask()

                with pytest.raises(ImportError) as exc_info:
                    _ = task.apgi_system

                assert "not available" in str(exc_info.value).lower()

    def test_apgi_system_lazy_initialization(self) -> None:
        """Test lazy initialization of apgi_system property."""
        from app.tasks.experimental_tasks import APGITask

        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.APGISystem") as mock_system_class:
                with patch("app.tasks.experimental_tasks.get_resource_path", return_value="/fake/path"):
                    mock_system = MagicMock()
                    mock_system_class.return_value = mock_system

                    task = APGITask()
                    # First access should initialize
                    result1 = task.apgi_system
                    # Second access should return cached instance
                    result2 = task.apgi_system

                    assert result1 is result2
                    mock_system_class.assert_called_once()

    def test_apgi_system_get_resource_path_none(self) -> None:
        """Test when get_resource_path is None."""
        from app.tasks.experimental_tasks import APGITask

        with patch("app.tasks.experimental_tasks.APGI_SYSTEM_AVAILABLE", True):
            with patch("app.tasks.experimental_tasks.APGISystem", MagicMock()):
                with patch("app.tasks.experimental_tasks.get_resource_path", None):
                    task = APGITask()

                    with pytest.raises(ImportError) as exc_info:
                        _ = task.apgi_system

                    assert "not available" in str(exc_info.value).lower()

    def test_module_import_failure_sets_none(self) -> None:
        """Test that module-level variables are set to None when import fails."""
        from app.tasks.experimental_tasks import (
            APGI_SYSTEM_AVAILABLE,
            AttentionalBlinkTask,
            BinocularRivalryTask,
            ChangeBlindnessTask,
            IowaGamblingTask,
            MaskingParadigmTask,
        )

        # When APGI_SYSTEM_AVAILABLE is False, task classes should be None
        if not APGI_SYSTEM_AVAILABLE:
            assert AttentionalBlinkTask is None
            assert BinocularRivalryTask is None
            assert ChangeBlindnessTask is None
            assert IowaGamblingTask is None
            assert MaskingParadigmTask is None
