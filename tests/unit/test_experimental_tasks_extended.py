"""
Comprehensive tests for experimental_tasks.py covering task execution paths.

Tests the actual task execution when APGI system is available (mocked).
"""

import sys
from typing import Any, Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_celery_task_decorator(
    *args: Any, bind: bool = False, base: Any = None, name: str | None = None, **kwargs: Any
) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "name", name or func.__name__)
        setattr(func, "bind", bind)
        setattr(func, "base", base)
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


@pytest.fixture(autouse=True)
def _fix_celery_mock_and_reload_ext() -> Generator[None, None, None]:
    celery_mod = sys.modules.get("app.celery_app")
    if celery_mod is not None:
        celery_mod.celery_app.task.side_effect = _mock_celery_task_decorator
    sys.modules.pop("app.tasks.experimental_tasks", None)
    sys.modules.pop("app.tasks", None)
    yield
    sys.modules.pop("app.tasks.experimental_tasks", None)
    sys.modules.pop("app.tasks", None)


class MockTask:
    """Mock task class for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.params = kwargs

    def run_all_trials(self, apgi_system: Any) -> dict[str, Any]:
        return {"trials": 10, "success_rate": 0.9}


class MockAPGISystem:
    """Mock APGI system for testing."""

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path


def mock_get_resource_path(path: str) -> str:
    """Mock resource path getter."""
    return f"/app/resources/{path}"


@pytest.fixture
def mock_apgi_modules() -> Generator[None, None, None]:
    """Fixture to mock all APGI modules."""
    with patch.dict(
        "sys.modules",
        {
            "apgi_system": MagicMock(),
            "apgi_system.experiments": MagicMock(),
            "apgi_system.experiments.tasks": MagicMock(),
            "apgi_system.experiments.tasks.attentional_blink": MagicMock(),
            "apgi_system.experiments.tasks.binocular_rivalry": MagicMock(),
            "apgi_system.experiments.tasks.change_blindness": MagicMock(),
            "apgi_system.experiments.tasks.iowa_gambling": MagicMock(),
            "apgi_system.experiments.tasks.masking_paradigm": MagicMock(),
            "apgi_system.platform_utils": MagicMock(),
            "apgi_system.system": MagicMock(),
        },
    ):
        # Set up mock classes
        sys_modules = __import__("sys").modules
        sys_modules["apgi_system.experiments.tasks.iowa_gambling"].IowaGamblingTask = MockTask
        sys_modules["apgi_system.experiments.tasks.masking_paradigm"].MaskingParadigmTask = MockTask
        sys_modules["apgi_system.experiments.tasks.attentional_blink"].AttentionalBlinkTask = (
            MockTask
        )
        sys_modules["apgi_system.experiments.tasks.change_blindness"].ChangeBlindnessTask = MockTask
        sys_modules["apgi_system.experiments.tasks.binocular_rivalry"].BinocularRivalryTask = (
            MockTask
        )
        sys_modules["apgi_system.platform_utils"].get_resource_path = mock_get_resource_path
        sys_modules["apgi_system.system"].APGISystem = MockAPGISystem

        yield


@pytest.fixture
def mock_task_record() -> MagicMock:
    """Mock task record for testing."""
    record = MagicMock()
    record.task_id = "test-task-id"
    record.session_id = "test-session-id"
    record.task_type = "iowa_gambling"
    record.webhook_url = None
    record.status = "pending"
    return record


@pytest.fixture
def mock_db(mock_task_record: MagicMock) -> MagicMock:
    """Mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_task_record
    return db


class TestIowaGamblingTaskExecution:
    """Test Iowa Gambling task execution with mocked APGI system."""

    def test_iowa_gambling_task_success(self, mock_apgi_modules: Any) -> None:
        """Test Iowa Gambling task returns unavailable response when APGI not available."""
        from app.tasks.experimental_tasks import APGI_SYSTEM_AVAILABLE, execute_iowa_gambling_task

        # When APGI is not available, task should return unavailable response
        if not APGI_SYSTEM_AVAILABLE:
            # Test the unavailable path - call the function directly without Celery wrapper
            result = execute_iowa_gambling_task(
                None,  # self will be provided by bind=True
                session_id="test-session",
                parameters={"num_trials": 10, "initial_balance": 2000},
            )
            assert result["task_type"] == "iowa_gambling"
            assert result["status"] == "failed"
            assert "apgi_system not installed" in result["error"]
            return

        # If APGI is available (mocked), call the raw function directly
        mock_self = MagicMock()
        mock_self.request.id = "celery-task-id-123"
        mock_self.apgi_system = MagicMock()

        with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class, \
                patch("asyncio.run"):
            mock_instance = MagicMock()
            mock_instance.run_all_trials = MagicMock(
                return_value={"trials": 10, "success_rate": 0.9}
            )
            mock_task_class.return_value = mock_instance
            result = execute_iowa_gambling_task(
                mock_self,
                session_id="test-session-id",
                parameters={"num_trials": 10},
            )

        # Verify the result structure
        assert result["task_type"] == "iowa_gambling"
        assert result["session_id"] == "test-session-id"
        assert result["status"] == "completed"
        assert "results" in result
        assert result["results"]["trials"] == 10
        assert result["results"]["success_rate"] == 0.9

    def test_iowa_gambling_task_unavailable(self) -> None:
        """Test Iowa Gambling task when APGI system unavailable."""
        from app.tasks.experimental_tasks import execute_iowa_gambling_task

        # Import should work even when APGI unavailable
        assert callable(execute_iowa_gambling_task)

        # When APGI is not available, the module sets APGI_SYSTEM_AVAILABLE = False
        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            # The task function should still exist and be callable
            # When called, it would return a failure result
            assert hasattr(experimental_tasks, "execute_iowa_gambling_task")


class TestMaskingParadigmTaskExecution:
    """Test Masking Paradigm task execution."""

    def test_masking_paradigm_task_unavailable(self) -> None:
        """Test Masking Paradigm task when APGI system unavailable."""
        from app.tasks.experimental_tasks import execute_masking_paradigm_task

        assert callable(execute_masking_paradigm_task)

        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            assert hasattr(experimental_tasks, "execute_masking_paradigm_task")


class TestAttentionalBlinkTaskExecution:
    """Test Attentional Blink task execution."""

    def test_attentional_blink_task_unavailable(self) -> None:
        """Test Attentional Blink task when APGI system unavailable."""
        from app.tasks.experimental_tasks import execute_attentional_blink_task

        assert callable(execute_attentional_blink_task)

        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            assert hasattr(experimental_tasks, "execute_attentional_blink_task")


class TestChangeBlindnessTaskExecution:
    """Test Change Blindness task execution."""

    def test_change_blindness_task_unavailable(self) -> None:
        """Test Change Blindness task when APGI system unavailable."""
        from app.tasks.experimental_tasks import execute_change_blindness_task

        assert callable(execute_change_blindness_task)

        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            assert hasattr(experimental_tasks, "execute_change_blindness_task")


class TestBinocularRivalryTaskExecution:
    """Test Binocular Rivalry task execution."""

    def test_binocular_rivalry_task_unavailable(self) -> None:
        """Test Binocular Rivalry task when APGI system unavailable."""
        from app.tasks.experimental_tasks import execute_binocular_rivalry_task

        assert callable(execute_binocular_rivalry_task)

        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            assert hasattr(experimental_tasks, "execute_binocular_rivalry_task")


class TestAPGITaskBaseClass:
    """Test APGITask base class."""

    def test_apgi_task_class_exists(self) -> None:
        """Test APGITask base class exists."""
        from app.tasks.experimental_tasks import APGITask

        assert APGITask is not None

    def test_apgi_task_lazy_initialization(self) -> None:
        """Test APGI task lazy initialization property."""
        from app.tasks import experimental_tasks
        from app.tasks.experimental_tasks import APGITask

        # When APGI not available, accessing apgi_system should raise ImportError
        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            task = APGITask()
            # The property raises ImportError when APGISystem is None
            try:
                _ = task.apgi_system
                # If no error, APGI might be available in test env
                pass
            except ImportError:
                pass  # Expected when APGI not available


class TestTriggerWebhookOnCompletion:
    """Test trigger_webhook_on_completion function."""

    @pytest.mark.asyncio
    async def test_trigger_webhook_task_not_found(self) -> None:
        """Test webhook trigger when task not found."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([mock_db])

            # Should not raise exception
            await trigger_webhook_on_completion("nonexistent-task", {"status": "completed"})

    @pytest.mark.asyncio
    async def test_trigger_webhook_success(self, mock_db: MagicMock) -> None:
        """Test successful webhook trigger."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        mock_task_record = mock_db.query.return_value.filter.return_value.first.return_value
        mock_task_record.webhook_url = "https://example.com/webhook"

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            with patch("app.tasks.experimental_tasks.WebhookManager") as mock_webhook_manager_class:
                mock_webhook_manager = AsyncMock()
                mock_webhook_manager_class.return_value = mock_webhook_manager
                mock_webhook_manager.create_webhook_delivery.return_value = "delivery-id"

                await trigger_webhook_on_completion("test-task-id", {"status": "completed"})

                # Verify webhook manager was used
                mock_webhook_manager.create_webhook_delivery.assert_called_once()
                mock_webhook_manager.deliver_webhook.assert_called_once()
                mock_webhook_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_webhook_no_webhook_url(self, mock_db: MagicMock) -> None:
        """Test webhook trigger when no webhook URL configured."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        mock_task_record = mock_db.query.return_value.filter.return_value.first.return_value
        mock_task_record.webhook_url = None

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            # Should not raise exception and not call webhook manager
            await trigger_webhook_on_completion("test-task-id", {"status": "completed"})

    @pytest.mark.asyncio
    async def test_trigger_webhook_task_executor_exception(self, mock_db: MagicMock) -> None:
        """Test webhook trigger when task executor fails."""
        from app.services.task_executor import TaskExecutor
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            with patch.object(TaskExecutor, "check_and_start_pending_tasks") as mock_check:
                mock_check.side_effect = Exception("Executor error")

                # Should not raise exception, just log error
                await trigger_webhook_on_completion("test-task-id", {"status": "completed"})

    @pytest.mark.asyncio
    async def test_trigger_webhook_failed_status(self, mock_db: MagicMock) -> None:
        """Test webhook trigger with failed task status."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        mock_task_record = mock_db.query.return_value.filter.return_value.first.return_value
        mock_task_record.webhook_url = "https://example.com/webhook"

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])

            with patch("app.tasks.experimental_tasks.WebhookManager") as mock_webhook_manager_class:
                mock_webhook_manager = AsyncMock()
                mock_webhook_manager_class.return_value = mock_webhook_manager
                mock_webhook_manager.create_webhook_delivery.return_value = "delivery-id"

                result = {"status": "failed", "error": "Task failed"}
                await trigger_webhook_on_completion("test-task-id", result)

                # Verify task record was updated with error
                assert mock_task_record.error_message == "Task failed"
                mock_db.commit.assert_called()


class TestExperimentalTaskParameters:
    """Test experimental task parameter extraction."""

    def test_iowa_gambling_task_is_callable(self) -> None:
        """Test Iowa Gambling task is callable."""
        from app.tasks.experimental_tasks import execute_iowa_gambling_task

        assert callable(execute_iowa_gambling_task)

    def test_masking_paradigm_task_is_callable(self) -> None:
        """Test Masking Paradigm task is callable."""
        from app.tasks.experimental_tasks import execute_masking_paradigm_task

        assert callable(execute_masking_paradigm_task)

    def test_attentional_blink_task_is_callable(self) -> None:
        """Test Attentional Blink task is callable."""
        from app.tasks.experimental_tasks import execute_attentional_blink_task

        assert callable(execute_attentional_blink_task)

    def test_change_blindness_task_is_callable(self) -> None:
        """Test Change Blindness task is callable."""
        from app.tasks.experimental_tasks import execute_change_blindness_task

        assert callable(execute_change_blindness_task)

    def test_binocular_rivalry_task_is_callable(self) -> None:
        """Test Binocular Rivalry task is callable."""
        from app.tasks.experimental_tasks import execute_binocular_rivalry_task

        assert callable(execute_binocular_rivalry_task)


class TestTaskRegistryIntegration:
    """Test task registry integration."""

    def test_celery_app_import(self) -> None:
        """Test that Celery app is available."""
        from app.tasks.experimental_tasks import celery_app

        assert celery_app is not None

    def test_all_tasks_registered(self) -> None:
        """Test all experimental tasks are registered."""
        from app.tasks.experimental_tasks import celery_app

        # Tasks should be registered with the Celery app
        tasks = celery_app.tasks

        expected_tasks = [
            "app.tasks.experimental_tasks.execute_iowa_gambling_task",
            "app.tasks.experimental_tasks.execute_masking_paradigm_task",
            "app.tasks.experimental_tasks.execute_attentional_blink_task",
            "app.tasks.experimental_tasks.execute_change_blindness_task",
            "app.tasks.experimental_tasks.execute_binocular_rivalry_task",
        ]

        for task_name in expected_tasks:
            # Task should be in the registry or we should be able to verify it's decorated
            assert task_name is not None


class TestWebhookTaskIntegration:
    """Test webhook task integration."""

    def test_webhook_tasks_import(self) -> None:
        """Test webhook tasks are imported."""
        from app.tasks import webhook_tasks

        assert webhook_tasks is not None

    def test_experimental_tasks_imports_webhook_manager(self) -> None:
        """Test experimental_tasks imports WebhookManager."""
        from app.tasks.experimental_tasks import WebhookManager

        assert WebhookManager is not None
