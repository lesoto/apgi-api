"""
Unit tests for experimental tasks.

Tests Celery tasks for Iowa Gambling, Masking Paradigm, Attentional Blink, etc.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.tasks.experimental_tasks import (
    trigger_webhook_on_completion,
    APGITask,
    execute_iowa_gambling_task,
    execute_masking_paradigm_task,
    execute_attentional_blink_task,
    execute_change_blindness_task,
    execute_binocular_rivalry_task,
)


@pytest.fixture
def mock_task_record():
    """Create a mock task record."""
    record = MagicMock()
    record.task_id = "task_123"
    record.session_id = "session_456"
    record.task_type = "iowa_gambling"
    record.webhook_url = "https://example.com/webhook"
    return record


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


class TestTriggerWebhookOnCompletion:
    """Test webhook triggering on task completion."""

    @pytest.mark.asyncio
    async def test_trigger_webhook_success(self, mock_db_session, mock_task_record):
        """Test successful webhook triggering."""
        result = {"status": "completed", "results": {"score": 100}}

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            with patch("app.tasks.experimental_tasks.TaskModel") as mock_task_model:
                with patch(
                    "app.tasks.experimental_tasks.WebhookManager"
                ) as mock_webhook_manager_class:
                    mock_get_db.return_value = iter([mock_db_session])
                    mock_task_model.query.filter.return_value.first.return_value = mock_task_record
                    mock_webhook_manager = MagicMock()
                    mock_webhook_manager.create_webhook_delivery = AsyncMock(
                        return_value="delivery_123"
                    )
                    mock_webhook_manager.deliver_webhook = AsyncMock(return_value=True)
                    mock_webhook_manager.close = AsyncMock()
                    mock_webhook_manager_class.return_value = mock_webhook_manager

                    await trigger_webhook_on_completion("task_123", result)

                    mock_db_session.commit.assert_called()
                    mock_webhook_manager.create_webhook_delivery.assert_called_once()
                    mock_webhook_manager.deliver_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_webhook_no_record(self, mock_db_session):
        """Test webhook triggering when task record not found."""
        result = {"status": "completed"}

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            with patch("app.tasks.experimental_tasks.TaskModel") as mock_task_model:
                mock_get_db.return_value = iter([mock_db_session])
                mock_task_model.query.filter.return_value.first.return_value = None

                await trigger_webhook_on_completion("task_123", result)

                # Should not crash, just log warning

    @pytest.mark.asyncio
    async def test_trigger_webhook_no_webhook_url(self, mock_db_session, mock_task_record):
        """Test webhook triggering when no webhook URL configured."""
        result = {"status": "completed"}
        mock_task_record.webhook_url = None

        with patch("app.tasks.experimental_tasks.get_db") as mock_get_db:
            with patch("app.tasks.experimental_tasks.TaskModel") as mock_task_model:
                mock_get_db.return_value = iter([mock_db_session])
                mock_task_model.query.filter.return_value.first.return_value = mock_task_record

                await trigger_webhook_on_completion("task_123", result)

                # Should not create webhook delivery


class TestAPGITask:
    """Test APGITask base class."""

    def test_apgi_system_initialization(self):
        """Test lazy initialization of APGI system."""
        task = APGITask()

        with patch("app.tasks.experimental_tasks.APGISystem") as mock_apgi_system:
            with patch("app.tasks.experimental_tasks.get_resource_path") as mock_get_resource_path:
                mock_get_resource_path.return_value = "path/to/config"
                mock_apgi_system.return_value = MagicMock()

                system = task.apgi_system

                mock_apgi_system.assert_called_once_with(config_path="path/to/config")
                assert task._apgi_system is not None


class TestExecuteIowaGamblingTask:
    """Test Iowa Gambling Task execution."""

    def test_execute_iowa_gambling_task_success(self):
        """Test successful Iowa Gambling task execution."""
        session_id = "session_123"
        parameters = {
            "num_trials": 50,
            "initial_balance": 1000,
        }

        mock_result = {
            "task_type": "iowa_gambling",
            "session_id": session_id,
            "status": "completed",
            "results": {"score": 100},
        }

        with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class:
            with patch(
                "app.tasks.experimental_tasks.trigger_webhook_on_completion"
            ) as mock_webhook:
                mock_task_instance = MagicMock()
                mock_task_instance.run_all_trials.return_value = {"score": 100}
                mock_task_class.return_value = mock_task_instance
                mock_webhook.return_value = AsyncMock()

                mock_celery_task = MagicMock()
                mock_celery_task.request.id = "task_123"
                mock_celery_task.apgi_system = MagicMock()

                result = execute_iowa_gambling_task(session_id, parameters)

                assert result["status"] == "completed"
                assert result["task_type"] == "iowa_gambling"
                mock_task_class.assert_called_once()

    def test_execute_iowa_gambling_task_failure(self):
        """Test Iowa Gambling task execution failure."""
        session_id = "session_123"
        parameters: dict = {}

        with patch("app.tasks.experimental_tasks.IowaGamblingTask") as mock_task_class:
            mock_task_instance = MagicMock()
            mock_task_instance.run_all_trials.side_effect = Exception("Task failed")
            mock_task_class.return_value = mock_task_instance

            mock_celery_task = MagicMock()
            mock_celery_task.request.id = "task_123"
            mock_celery_task.apgi_system = MagicMock()

            result = execute_iowa_gambling_task(session_id, parameters)

            assert result["status"] == "failed"
            assert "Task failed" in result["error"]


class TestExecuteMaskingParadigmTask:
    """Test Masking Paradigm Task execution."""

    def test_execute_masking_paradigm_task_success(self):
        """Test successful Masking Paradigm task execution."""
        session_id = "session_123"
        parameters = {
            "target_duration_ms": 25.0,
            "soas": [0, 50, 100],
        }

        mock_result = {
            "task_type": "masking_paradigm",
            "session_id": session_id,
            "status": "completed",
            "results": {"accuracy": 0.8},
        }

        with patch("app.tasks.experimental_tasks.MaskingParadigmTask") as mock_task_class:
            with patch(
                "app.tasks.experimental_tasks.trigger_webhook_on_completion"
            ) as mock_webhook:
                mock_task_instance = MagicMock()
                mock_task_instance.run_all_trials.return_value = {"accuracy": 0.8}
                mock_task_class.return_value = mock_task_instance
                mock_webhook.return_value = AsyncMock()

                mock_celery_task = MagicMock()
                mock_celery_task.request.id = "task_123"
                mock_celery_task.apgi_system = MagicMock()

                result = execute_masking_paradigm_task(session_id, parameters)

                assert result["status"] == "completed"
                assert result["task_type"] == "masking_paradigm"


class TestExecuteAttentionalBlinkTask:
    """Test Attentional Blink Task execution."""

    def test_execute_attentional_blink_task_success(self):
        """Test successful Attentional Blink task execution."""
        session_id = "session_123"
        parameters = {
            "stream_length": 10,
            "lags": [1, 2, 3],
        }

        mock_result = {
            "task_type": "attentional_blink",
            "session_id": session_id,
            "status": "completed",
            "results": {"blink_effect": True},
        }

        with patch("app.tasks.experimental_tasks.AttentionalBlinkTask") as mock_task_class:
            with patch(
                "app.tasks.experimental_tasks.trigger_webhook_on_completion"
            ) as mock_webhook:
                mock_task_instance = MagicMock()
                mock_task_instance.run_all_trials.return_value = {"blink_effect": True}
                mock_task_class.return_value = mock_task_instance
                mock_webhook.return_value = AsyncMock()

                mock_celery_task = MagicMock()
                mock_celery_task.request.id = "task_123"
                mock_celery_task.apgi_system = MagicMock()

                result = execute_attentional_blink_task(session_id, parameters)

                assert result["status"] == "completed"
                assert result["task_type"] == "attentional_blink"


class TestExecuteChangeBlindnessTask:
    """Test Change Blindness Task execution."""

    def test_execute_change_blindness_task_success(self):
        """Test successful Change Blindness task execution."""
        session_id = "session_123"
        parameters = {
            "image_size": (128, 128),
            "num_trials": 25,
        }

        mock_result = {
            "task_type": "change_blindness",
            "session_id": session_id,
            "status": "completed",
            "results": {"detection_rate": 0.6},
        }

        with patch("app.tasks.experimental_tasks.ChangeBlindnessTask") as mock_task_class:
            with patch(
                "app.tasks.experimental_tasks.trigger_webhook_on_completion"
            ) as mock_webhook:
                mock_task_instance = MagicMock()
                mock_task_instance.run_all_trials.return_value = {"detection_rate": 0.6}
                mock_task_class.return_value = mock_task_instance
                mock_webhook.return_value = AsyncMock()

                mock_celery_task = MagicMock()
                mock_celery_task.request.id = "task_123"
                mock_celery_task.apgi_system = MagicMock()

                result = execute_change_blindness_task(session_id, parameters)

                assert result["status"] == "completed"
                assert result["task_type"] == "change_blindness"


class TestExecuteBinocularRivalryTask:
    """Test Binocular Rivalry Task execution."""

    def test_execute_binocular_rivalry_task_success(self):
        """Test successful Binocular Rivalry task execution."""
        session_id = "session_123"
        parameters = {
            "pattern_size": (128, 128),
            "duration_seconds": 30.0,
        }

        mock_result = {
            "task_type": "binocular_rivalry",
            "session_id": session_id,
            "status": "completed",
            "results": {"rivalry_data": []},
        }

        with patch("app.tasks.experimental_tasks.BinocularRivalryTask") as mock_task_class:
            with patch(
                "app.tasks.experimental_tasks.trigger_webhook_on_completion"
            ) as mock_webhook:
                mock_task_instance = MagicMock()
                mock_task_instance.run_all_trials.return_value = {"rivalry_data": []}
                mock_task_class.return_value = mock_task_instance
                mock_webhook.return_value = AsyncMock()

                mock_celery_task = MagicMock()
                mock_celery_task.request.id = "task_123"
                mock_celery_task.apgi_system = MagicMock()

                result = execute_binocular_rivalry_task(session_id, parameters)

                assert result["status"] == "completed"
                assert result["task_type"] == "binocular_rivalry"
