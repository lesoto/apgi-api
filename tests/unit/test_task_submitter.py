"""
Unit tests for TaskSubmitter covering task validation, Celery submission, and retry logic.
Requirements: 4.7, 5.1
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.task_execution.task_submitter import TaskSubmitter, async_retry_with_backoff


class TestAsyncRetryWithBackoff:
    """Test async retry with backoff function."""

    async def test_retry_succeeds_on_first_attempt(self) -> None:
        """Function succeeds on first attempt."""
        call_count = 0

        async def func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_retry_with_backoff(func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    async def test_retry_succeeds_on_second_attempt(self) -> None:
        """Function succeeds after one retry."""
        call_count = 0

        async def func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            return "success"

        result = await async_retry_with_backoff(func, max_retries=3)
        assert result == "success"
        assert call_count == 2

    async def test_retry_exhausts_retries(self) -> None:
        """Function fails after all retries."""
        call_count = 0

        async def func() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await async_retry_with_backoff(func, max_retries=2)

        assert call_count == 3  # Initial + 2 retries

    async def test_retry_custom_delay(self) -> None:
        """Respects custom delay parameters."""
        call_count = 0

        async def func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            return "success"

        result = await async_retry_with_backoff(
            func, max_retries=3, base_delay=0.1, backoff_factor=2.0
        )
        assert result == "success"


class TestTaskSubmitterInit:
    """Test TaskSubmitter initialization."""

    def test_submitter_initialization(self) -> None:
        """Submitter initializes with strategy registry."""
        submitter = TaskSubmitter()
        assert submitter.strategy_registry is not None
        assert len(submitter._task_map) == 5


class TestValidateTaskType:
    """Test task type validation."""

    def test_validate_task_type_valid(self) -> None:
        """Valid task type passes validation."""
        submitter = TaskSubmitter()
        result = submitter.validate_task_type("iowa_gambling")
        assert result is True

    def test_validate_task_type_invalid(self) -> None:
        """Invalid task type raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="Invalid task type"):
            submitter.validate_task_type("invalid_type")


class TestValidatePriority:
    """Test priority validation."""

    def test_validate_priority_valid(self) -> None:
        """Valid priority passes validation."""
        submitter = TaskSubmitter()
        result = submitter.validate_priority(5)
        assert result is True

    def test_validate_priority_too_low(self) -> None:
        """Priority below 1 raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="Priority must be between"):
            submitter.validate_priority(0)

    def test_validate_priority_too_high(self) -> None:
        """Priority above 10 raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="Priority must be between"):
            submitter.validate_priority(11)

    def test_validate_priority_boundary(self) -> None:
        """Boundary values are valid."""
        submitter = TaskSubmitter()
        assert submitter.validate_priority(1) is True
        assert submitter.validate_priority(10) is True


class TestValidateParameters:
    """Test parameter validation."""

    def test_validate_parameters_valid(self) -> None:
        """Valid parameters pass validation."""
        submitter = TaskSubmitter()
        result = submitter.validate_parameters("iowa_gambling", {"num_trials": 50})
        assert result["num_trials"] == 50

    def test_validate_parameters_invalid_type(self) -> None:
        """Invalid task type raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="No strategy found"):
            submitter.validate_parameters("invalid_type", {})


class TestCreateTaskRecord:
    """Test task record creation."""

    @patch("app.services.task_execution.task_submitter.get_db_context")
    def test_create_task_record(self, mock_db_context: MagicMock) -> None:
        """Create task record in database."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        submitter.create_task_record(
            task_id="task123",
            session_id="session123",
            task_type="iowa_gambling",
            parameters={"num_trials": 50},
            priority=5,
            webhook_url=None,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestSubmitToCelery:
    """Test Celery submission."""

    @patch("app.services.task_execution.task_submitter.celery_app")
    @patch("app.services.task_execution.task_submitter.asyncio.to_thread")
    async def test_submit_to_celery_success(
        self, mock_to_thread: MagicMock, mock_celery: MagicMock
    ) -> None:
        """Successful submission to Celery."""
        mock_result = MagicMock()
        mock_to_thread.return_value = mock_result

        submitter = TaskSubmitter()
        result = await submitter.submit_to_celery(
            "task123", "iowa_gambling", "session123", {"num_trials": 50}
        )

        assert result == mock_result

    @patch("app.services.task_execution.task_submitter.celery_app")
    @patch("app.services.task_execution.task_submitter.asyncio.to_thread")
    async def test_submit_to_celery_invalid_type(
        self, mock_to_thread: MagicMock, mock_celery: MagicMock
    ) -> None:
        """Invalid task type raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="No Celery task mapping"):
            await submitter.submit_to_celery("task123", "invalid_type", "session123", {})


class TestMarkTaskFailed:
    """Test marking task as failed."""

    @patch("app.services.task_execution.task_submitter.get_db_context")
    def test_mark_task_failed(self, mock_db_context: MagicMock) -> None:
        """Mark task as failed in database."""
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        submitter.mark_task_failed("task123", "Test error")

        assert mock_task.status == "failed"
        assert mock_task.error_message == "Test error"
        mock_db.commit.assert_called_once()

    @patch("app.services.task_execution.task_submitter.get_db_context")
    def test_mark_task_failed_not_found(self, mock_db_context: MagicMock) -> None:
        """Task not found doesn't error."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        submitter.mark_task_failed("task123", "Test error")  # No error


class TestSubmitTask:
    """Test task submission workflow."""

    @patch("app.services.task_execution.task_submitter.get_db_context")
    async def test_submit_task_valid(self, mock_db_context: MagicMock) -> None:
        """Submit valid task."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        task_id = await submitter.submit_task(
            session_id="session123",
            task_type="iowa_gambling",
            parameters={"num_trials": 50},
            user_id="user123",
            priority=5,
        )

        assert task_id is not None
        assert len(task_id) > 0

    async def test_submit_task_invalid_type(self) -> None:
        """Invalid task type raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="Invalid task type"):
            await submitter.submit_task(
                session_id="session123",
                task_type="invalid_type",
                parameters={},
                user_id="user123",
            )

    async def test_submit_task_invalid_priority(self) -> None:
        """Invalid priority raises error."""
        submitter = TaskSubmitter()
        with pytest.raises(ValueError, match="Priority must be between"):
            await submitter.submit_task(
                session_id="session123",
                task_type="iowa_gambling",
                parameters={},
                user_id="user123",
                priority=15,
            )


class TestStartTaskImmediately:
    """Test immediate task start."""

    @patch("app.services.task_execution.task_submitter.get_db_context")
    @patch.object(TaskSubmitter, "submit_to_celery")
    async def test_start_task_immediately_success(
        self, mock_submit: MagicMock, mock_db_context: MagicMock
    ) -> None:
        """Successfully start task immediately."""
        mock_result = MagicMock()
        mock_submit.return_value = mock_result
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        await submitter.start_task_immediately(
            "task123", "iowa_gambling", "session123", {"num_trials": 50}
        )

        mock_submit.assert_called_once()

    @patch("app.services.task_execution.task_submitter.get_db_context")
    @patch.object(TaskSubmitter, "submit_to_celery")
    async def test_start_task_immediately_failure(
        self, mock_submit: MagicMock, mock_db_context: MagicMock
    ) -> None:
        """Handle submission failure."""
        mock_submit.side_effect = Exception("Submission failed")
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        with pytest.raises(Exception, match="Submission failed"):
            await submitter.start_task_immediately(
                "task123", "iowa_gambling", "session123", {"num_trials": 50}
            )

        assert mock_task.status == "failed"


class TestRetryTask:
    """Test task retry."""

    @patch("app.services.task_execution.task_submitter.get_db_context")
    @patch.object(TaskSubmitter, "submit_to_celery")
    async def test_retry_task_success(
        self, mock_submit: MagicMock, mock_db_context: MagicMock
    ) -> None:
        """Successfully retry task."""
        mock_result = MagicMock()
        mock_submit.return_value = mock_result
        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        result = await submitter.retry_task(
            "task123", "iowa_gambling", "session123", {"num_trials": 50}
        )

        assert result == mock_result
        assert mock_task.status == "pending"
        assert mock_task.error_message is None

    @patch("app.services.task_execution.task_submitter.get_db_context")
    @patch.object(TaskSubmitter, "submit_to_celery")
    async def test_retry_task_not_found(
        self, mock_submit: MagicMock, mock_db_context: MagicMock
    ) -> None:
        """Task not found doesn't error."""
        mock_result = MagicMock()
        mock_submit.return_value = mock_result
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        result = await submitter.retry_task(
            "task123", "iowa_gambling", "session123", {"num_trials": 50}
        )

        assert result == mock_result
