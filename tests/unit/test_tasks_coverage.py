"""
Comprehensive tests for tasks module to achieve 100% coverage.
Covers: experimental_tasks, webhook_tasks, task_registry, tasks.__init__
"""

from unittest.mock import MagicMock, patch

import pytest

from app.tasks import experimental_tasks, task_registry, webhook_tasks


class TestExperimentalTasks:
    """Test experimental tasks module."""

    @pytest.mark.asyncio
    @patch("app.tasks.experimental_tasks.get_db")
    @patch("app.tasks.experimental_tasks.WebhookManager")
    @patch("app.tasks.experimental_tasks.TaskExecutor", create=True)
    async def test_trigger_webhook_on_completion(
        self, mock_executor_class, mock_webhook_manager_class, mock_get_db
    ) -> None:
        """Test trigger webhook on completion."""
        from unittest.mock import AsyncMock

        # Setup mock db generator
        mock_db = MagicMock()
        mock_db_gen = MagicMock()
        mock_db_gen.__next__ = MagicMock(return_value=mock_db)
        mock_db_gen.__iter__ = MagicMock(return_value=iter([mock_db]))
        mock_get_db.return_value = mock_db_gen

        # Setup mock task with webhook URL
        mock_task = MagicMock()
        mock_task.session_id = "session-1"
        mock_task.task_type = "iowa_gambling"
        mock_task.webhook_url = "http://example.com"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        # Setup mock webhook manager with async methods
        mock_webhook_manager = mock_webhook_manager_class.return_value
        mock_webhook_manager.create_webhook_delivery = AsyncMock(return_value="delivery-1")
        mock_webhook_manager.deliver_webhook = AsyncMock()
        mock_webhook_manager.close = AsyncMock()

        # Setup mock executor
        mock_executor = mock_executor_class.return_value
        mock_executor.check_and_start_pending_tasks = AsyncMock()

        await experimental_tasks.trigger_webhook_on_completion("task-1", {"status": "completed"})

        # Verify the expected calls were made
        assert mock_db.commit.called, "db.commit() was not called"
        assert mock_webhook_manager.create_webhook_delivery.called, "create_webhook_delivery was not called"
        assert mock_webhook_manager.deliver_webhook.called, "deliver_webhook was not called"

    def test_experimental_tasks_availability(self):
        """Test that experimental_tasks module constants are available."""
        assert hasattr(experimental_tasks, "APGI_SYSTEM_AVAILABLE")
        assert hasattr(experimental_tasks, "APGITask")

    def test_execute_tasks_exist(self):
        """Test that all execute_*_task functions exist."""
        assert hasattr(experimental_tasks, "execute_iowa_gambling_task")
        assert hasattr(experimental_tasks, "execute_masking_paradigm_task")
        assert hasattr(experimental_tasks, "execute_attentional_blink_task")
        assert hasattr(experimental_tasks, "execute_change_blindness_task")
        assert hasattr(experimental_tasks, "execute_binocular_rivalry_task")


class TestWebhookTasks:
    """Test webhook tasks module."""

    @patch("app.tasks.webhook_tasks.asyncio.run")
    def test_process_pending_webhooks_task(self, mock_run):
        """Test process_pending_webhooks task."""
        webhook_tasks.process_pending_webhooks()
        assert mock_run.called


class TestTaskRegistry:
    """Test task registry module."""

    def test_task_registry_constants(self):
        """Test TaskRegistry constants."""
        assert "iowa_gambling" in task_registry.TASK_REGISTRY.keys()
        assert "iowa_gambling" in task_registry.TASK_FUNCTIONS.keys()

    def test_get_task_function(self):
        """Test get_task_function."""
        func = task_registry.get_task_function(task_registry.TaskType.IOWA_GAMBLING)
        assert func == experimental_tasks.execute_iowa_gambling_task

    def test_get_task_name(self):
        """Test get_task_name."""
        name = task_registry.get_task_name(task_registry.TaskType.IOWA_GAMBLING)
        assert name == "app.tasks.experimental_tasks.execute_iowa_gambling_task"

    def test_list_available_tasks(self):
        """Test list_available_tasks."""
        tasks = task_registry.list_available_tasks()
        assert task_registry.TaskType.IOWA_GAMBLING in tasks

    def test_validate_task_type(self):
        """Test validate_task_type."""
        tt = task_registry.validate_task_type("iowa_gambling")
        assert tt == task_registry.TaskType.IOWA_GAMBLING

        with pytest.raises(ValueError, match="Invalid task type"):
            task_registry.validate_task_type("invalid")


class TestTasksInit:
    """Test tasks package initialization."""

    def test_tasks_init_imports(self):
        """Test tasks __init__."""
        import app.tasks as tasks

        assert tasks is not None
