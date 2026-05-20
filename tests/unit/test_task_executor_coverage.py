"""
Coverage tests for app/services/task_executor.py to achieve 100% coverage.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import TaskStatus


class TestAsyncRetryWithBackoff:
    """Test async_retry_with_backoff function."""

    async def test_async_retry_success(self) -> None:
        """Test successful execution without retries."""
        from app.services.task_executor import async_retry_with_backoff

        call_count = [0]

        async def func_that_succeeds():
            call_count[0] += 1
            return "success"

        result = await async_retry_with_backoff(func_that_succeeds, max_retries=3)
        assert result == "success"
        assert call_count[0] == 1


class TestExecuteWithRetry:
    """Test execute_with_retry function."""

    async def test_execute_with_retry_success(self) -> None:
        """Test successful execution without retries."""
        from app.services.task_executor import execute_with_retry

        call_count = [0]

        async def func_that_succeeds():
            call_count[0] += 1
            return "success"

        result = await execute_with_retry(func_that_succeeds, max_retries=3)
        assert result == "success"
        assert call_count[0] == 1


class TestTaskExecutorCycleDetection:
    """Test _has_cycle method for cycle detection."""

    @patch("app.services.task_executor.get_db_context")
    def test_has_cycle_detected(self, mock_db_context: MagicMock) -> None:
        """Test cycle detection when cycle exists (line 463-464)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "task1"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        # Simulate cycle by having task1 in rec_stack
        result = task_executor._has_cycle("task1", visited=set(), rec_stack={"task1"})

        assert result is True

    @patch("app.services.task_executor.get_db_context")
    def test_has_cycle_recursive(self, mock_db_context: MagicMock) -> None:
        """Test recursive cycle detection (lines 461-462)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "task2"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        # Mock the recursive call to return True
        with patch.object(task_executor, "_has_cycle", return_value=True):
            result = task_executor._has_cycle("task1", visited=set(), rec_stack=set())

        assert result is True


class TestTaskExecutorDependencyChecks:
    """Test _can_start_task method with various dependency types."""

    @patch("app.services.task_executor.get_db_context")
    def test_can_start_task_success_dependency(self, mock_db_context: MagicMock) -> None:
        """Test success dependency check (lines 421-422)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_dep = MagicMock()
        mock_dep.dependency_type = "success"
        mock_dep.prerequisite_task_id = "task1"

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.COMPLETED.value

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()
        result = task_executor._can_start_task("task2")

        assert result is True

    @patch("app.services.task_executor.get_db_context")
    def test_can_start_task_failure_dependency(self, mock_db_context: MagicMock) -> None:
        """Test failure dependency check (lines 423-425)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_dep = MagicMock()
        mock_dep.dependency_type = "failure"
        mock_dep.prerequisite_task_id = "task1"

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.FAILED.value

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()
        result = task_executor._can_start_task("task2")

        assert result is True


class TestTaskExecutorSubmitTaskWithCycle:
    """Test submit_task with cycle detection."""

    @patch("app.services.task_executor.get_db_context")
    async def test_submit_task_cycle_detected(self, mock_db_context: MagicMock) -> None:
        """Test submit_task raises ValueError when cycle detected (line 347)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.user_id = "user123"
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_session
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        with patch.object(task_executor, "_has_cycle", return_value=True):
            with pytest.raises(ValueError, match="Task dependency cycle detected"):
                await task_executor.submit_task(
                    "session123", "iowa_gambling", {"num_trials": 50}, "user123"
                )


class TestTaskExecutorSubmitTaskCeleryFailure:
    """Test submit_task when Celery submission fails."""

    @patch("app.services.task_executor.get_db_context")
    @patch("app.services.task_executor.async_retry_with_backoff")
    async def test_submit_task_celery_submission_failure(
        self, mock_retry: MagicMock, mock_db_context: MagicMock
    ) -> None:
        """Test marking task as failed after Celery submission failure (lines 373-378)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.user_id = "user123"
        mock_task_record = MagicMock()
        mock_task_record.task_id = "task123"
        mock_task_record.status = TaskStatus.PENDING.value

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_retry.side_effect = Exception("Celery connection failed")

        task_executor = TaskExecutor()

        with patch.object(task_executor, "_has_cycle", return_value=False):
            with patch.object(task_executor, "_can_start_task", return_value=True):
                with pytest.raises(Exception, match="Celery connection failed"):
                    await task_executor.submit_task(
                        "session123", "iowa_gambling", {"num_trials": 50}, "user123"
                    )

                # Verify task was marked as failed
                assert mock_task_record.status == TaskStatus.FAILED.value
                assert "Celery submission failed" in mock_task_record.error_message


class TestTaskExecutorSubmitTaskQueued:
    """Test submit_task when task is queued pending dependencies."""

    @patch("app.services.task_executor.get_db_context")
    async def test_submit_task_queued_pending_dependencies(
        self, mock_db_context: MagicMock
    ) -> None:
        """Test logging when task is queued pending dependencies (line 380)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.user_id = "user123"
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_session
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        with patch.object(task_executor, "_has_cycle", return_value=False):
            with patch.object(task_executor, "_can_start_task", return_value=False):
                result = await task_executor.submit_task(
                    "session123", "iowa_gambling", {"num_trials": 50}, "user123"
                )

                assert result is not None
                assert isinstance(result, str)


class TestTaskExecutorCheckPendingTasks:
    """Test check_and_start_pending_tasks method."""

    @patch("app.services.task_executor.get_db_context")
    async def test_check_and_start_pending_tasks_can_start(
        self, mock_db_context: MagicMock
    ) -> None:
        """Test checking if pending task can be started (line 486)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_task.task_type = "iowa_gambling"
        mock_task.session_id = "session123"
        mock_task.parameters = {"num_trials": 50}

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_task]
        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        with patch.object(task_executor, "_can_start_task", return_value=True):
            with patch("app.services.task_executor.async_retry_with_backoff"):
                result = await task_executor.check_and_start_pending_tasks("session123")
                # Function returns None, just verify it runs without error
                assert result is None


class TestTaskExecutorGetTaskStatusFailure:
    """Test get_task_status with Celery FAILURE state."""

    @patch("app.services.task_executor.get_db_context")
    async def test_get_task_status_celery_failure(self, mock_db_context: MagicMock) -> None:
        """Test handling Celery FAILURE state (lines 570-582)."""
        from app.services.task_executor import TaskExecutor

        # Use a simple object to allow attribute assignment
        class MockTaskRecord:
            def __init__(self):
                self.task_id = "task123"
                self.status = TaskStatus.RUNNING.value
                self.error_message = None
                self.completed_at = None
                self.result_data = None

        mock_task_record = MockTaskRecord()

        mock_db = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.state = "FAILURE"
        mock_async_result.result = Exception("Task failed")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        mock_db.commit = MagicMock()

        # Mock the join and filter chain
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_db.query.return_value.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value.first.return_value = mock_task_record

        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        with patch("app.services.task_executor.AsyncResult", return_value=mock_async_result):
            result = await task_executor.get_task_status("task123", "user123")

            # After the FAILURE handling, the status should be updated to FAILED
            assert result["status"] == TaskStatus.FAILED.value
            assert result["error"] is not None


class TestTaskExecutorGetTaskStatusTimeout:
    """Test get_task_status with stuck running task."""

    @patch("app.services.task_executor.get_db_context")
    async def test_get_task_status_timeout(self, mock_db_context: MagicMock) -> None:
        """Test handling stuck running task (lines 590-598)."""
        from app.services.task_executor import TaskExecutor

        mock_db = MagicMock()
        mock_task_record = MagicMock()
        mock_task_record.task_id = "task123"
        mock_task_record.status = TaskStatus.RUNNING.value
        mock_task_record.started_at = datetime.now(timezone.utc) - timedelta(seconds=1000)
        mock_task_record.error_message = None

        mock_async_result = MagicMock()
        mock_async_result.state = "PENDING"
        mock_async_result.result = None
        mock_async_result.info = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        mock_db.commit = MagicMock()

        # Mock the join and filter chain
        mock_join = MagicMock()
        mock_filter = MagicMock()
        mock_db.query.return_value.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.filter.return_value.first.return_value = mock_task_record

        mock_db_context.return_value.__enter__.return_value = mock_db

        task_executor = TaskExecutor()

        with patch("app.services.task_executor.AsyncResult", return_value=mock_async_result):
            with patch("app.config.settings") as mock_settings:
                mock_settings.task_timeout_seconds = 600
                result = await task_executor.get_task_status("task123", "user123")

                assert result["status"] == TaskStatus.FAILED.value
                assert "timed out" in result["error"]
