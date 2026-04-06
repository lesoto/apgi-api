"""Test task executor service."""

import pytest
from unittest.mock import MagicMock, patch
import uuid

from app.services.task_executor import (
    TaskExecutor,
    retry_with_backoff,
)
from app.database.models import TaskStatus


class TestTaskExecutor:
    """Test task executor functionality."""

    def test_task_map_exists(self):
        """Test that TASK_MAP is properly defined."""
        assert hasattr(TaskExecutor, "TASK_MAP")
        assert "iowa_gambling" in TaskExecutor.TASK_MAP
        assert "masking_paradigm" in TaskExecutor.TASK_MAP
        assert "attentional_blink" in TaskExecutor.TASK_MAP
        assert "change_blindness" in TaskExecutor.TASK_MAP
        assert "binocular_rivalry" in TaskExecutor.TASK_MAP

    def test_allowed_task_types(self):
        """Test that ALLOWED_TASK_TYPES is properly defined."""
        assert hasattr(TaskExecutor, "ALLOWED_TASK_TYPES")
        assert "iowa_gambling" in TaskExecutor.ALLOWED_TASK_TYPES
        assert "masking_paradigm" in TaskExecutor.ALLOWED_TASK_TYPES
        assert len(TaskExecutor.ALLOWED_TASK_TYPES) == 5

    def test_task_info_exists(self):
        """Test that TASK_INFO is properly defined."""
        assert hasattr(TaskExecutor, "TASK_INFO")
        assert "iowa_gambling" in TaskExecutor.TASK_INFO
        assert TaskExecutor.TASK_INFO["iowa_gambling"]["name"] == "Iowa Gambling Task"
        assert "parameters" in TaskExecutor.TASK_INFO["iowa_gambling"]

    async def test_list_available_tasks(self):
        """Test listing available tasks."""
        task_executor = TaskExecutor()
        result = await task_executor.list_available_tasks()

        assert "tasks" in result
        assert len(result["tasks"]) == 5
        task_names = [task["name"] for task in result["tasks"]]
        assert "Iowa Gambling Task" in task_names
        assert "Masking Paradigm Task" in task_names

    async def test_submit_task_success(self):
        """Test successful task submission."""
        session_id = "session123"
        task_type = "iowa_gambling"
        parameters = {"num_trials": 50, "initial_balance": 1000}
        user_id = "user123"
        task_executor = TaskExecutor()

        with patch("app.services.task_executor.get_db_context") as mock_db:
            mock_session = MagicMock()
            mock_task = MagicMock()
            mock_task.id = uuid.uuid4()
            mock_task.status = TaskStatus.PENDING
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.return_value.__aenter__.return_value = mock_session
            mock_db.return_value.__aexit__.return_value = None

            with patch("app.services.task_executor.async_retry_with_backoff") as mock_retry:
                mock_retry.return_value = uuid.uuid4()

                result = await task_executor.submit_task(session_id, task_type, parameters, user_id)

        # Task ID is now a UUID string (not prefixed with "task_")
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify it's a valid UUID format
        try:
            uuid.UUID(result)
        except ValueError:
            pytest.fail("Result is not a valid UUID string")

    async def test_submit_task_invalid_type(self):
        """Test task submission with invalid task type."""
        session_id = "session123"
        task_type = "invalid_task"
        parameters = {"param1": "value1"}
        user_id = "user123"
        task_executor = TaskExecutor()

        with pytest.raises(ValueError, match="Invalid task type"):
            await task_executor.submit_task(session_id, task_type, parameters, user_id)

    async def test_submit_task_dependency_cycle(self):
        """Test task submission with dependency cycle detection via TaskDependency table."""
        session_id = "session123"
        task_type = "iowa_gambling"
        parameters = {"num_trials": 50}
        user_id = "user123"
        task_executor = TaskExecutor()

        with patch("app.services.task_executor.get_db_context") as mock_db:
            mock_session = MagicMock()
            mock_task = MagicMock()
            mock_task.id = uuid.uuid4()
            mock_task.status = TaskStatus.PENDING
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task
            # Mock TaskDependency query to return a cycle
            mock_dep = MagicMock()
            mock_dep.prerequisite_task_id = "task-a"  # Self-reference creates cycle
            mock_session.query.return_value.filter.return_value.all.side_effect = [
                [mock_dep],  # First call for cycle check
                [],  # Second call for can_start check
            ]
            mock_db.return_value.__aenter__.return_value = mock_session
            mock_db.return_value.__aexit__.return_value = None

            # Mock _has_cycle to return True to simulate cycle detection
            with patch.object(task_executor, "_has_cycle", return_value=True):
                with pytest.raises(ValueError, match="Task dependency cycle detected"):
                    await task_executor.submit_task(session_id, task_type, parameters, user_id)

    def test_has_cycle_detection(self):
        """Test cycle detection in dependencies via TaskDependency table."""
        task_executor = TaskExecutor()
        # Simple cycle: A -> B -> A
        task_a = MagicMock()
        task_a.id = "A"
        task_a.dependencies = ["B"]

        task_b = MagicMock()
        task_b.id = "B"
        task_b.dependencies = ["A"]

        with patch("app.services.task_executor.get_db_context") as mock_db:
            mock_session = MagicMock()
            # Mock TaskDependency queries - A depends on B, B depends on A (cycle)
            mock_dep_a = MagicMock()
            mock_dep_a.prerequisite_task_id = "B"
            mock_dep_b = MagicMock()
            mock_dep_b.prerequisite_task_id = "A"
            mock_dep_c = MagicMock()  # No more deps
            mock_session.query.return_value.filter.return_value.all.side_effect = [
                [mock_dep_a],  # A depends on B
                [mock_dep_b],  # B depends on A (cycle!)
            ]
            mock_db.return_value.__enter__.return_value = mock_session
            mock_db.return_value.__exit__.return_value = None

            # Test cycle detection - should detect the cycle
            has_cycle = task_executor._has_cycle("A")

        assert has_cycle is True

    def test_no_cycle_detection(self):
        """Test no cycle in dependencies via TaskDependency table."""
        task_executor = TaskExecutor()
        # Simple chain: A -> B -> C (no cycle)
        task_a = MagicMock()
        task_a.id = "A"
        task_a.dependencies = ["B"]

        task_b = MagicMock()
        task_b.id = "B"
        task_b.dependencies = ["C"]

        task_c = MagicMock()
        task_c.id = "C"
        task_c.dependencies = []

        with patch("app.services.task_executor.get_db_context") as mock_db:
            mock_session = MagicMock()
            # Mock TaskDependency queries - chain A -> B -> C
            # Each _has_cycle call queries dependencies, and it's recursive
            # A calls _has_cycle(A) -> queries deps for A (B) -> calls _has_cycle(B)
            # B queries deps for B (C) -> calls _has_cycle(C)
            # C queries deps for C (none) -> returns False
            mock_dep_a = MagicMock()
            mock_dep_a.prerequisite_task_id = "B"
            mock_dep_b = MagicMock()
            mock_dep_b.prerequisite_task_id = "C"
            # Provide enough values for all queries across multiple _has_cycle calls
            mock_session.query.return_value.filter.return_value.all.side_effect = [
                [mock_dep_a],  # A depends on B (first _has_cycle(A) call)
                [mock_dep_b],  # B depends on C
                [],  # C has no dependencies
                [mock_dep_b],  # B depends on C (second _has_cycle(B) call)
                [],  # C has no dependencies
                [],  # C has no dependencies (third _has_cycle(C) call)
            ]
            mock_db.return_value.__enter__.return_value = mock_session
            mock_db.return_value.__exit__.return_value = None

            # Test no cycle detection for A
            has_cycle_a = task_executor._has_cycle("A")
            # B should also have no cycle
            has_cycle_b = task_executor._has_cycle("B")
            # C has no dependencies, so definitely no cycle
            has_cycle_c = task_executor._has_cycle("C")

        assert has_cycle_a is False
        assert has_cycle_b is False
        assert has_cycle_c is False  # C has no dependencies, so no cycle


class TestRetryWithBackoff:
    """Test retry_with_backoff decorator function."""

    def test_retry_success_on_first_attempt(self):
        """Test successful function on first attempt."""
        mock_func = MagicMock(return_value="success")

        result = retry_with_backoff(mock_func)

        assert result == "success"
        mock_func.assert_called_once()

    def test_retry_success_after_attempts(self):
        """Test function succeeds after some retries."""
        call_count = 0

        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = retry_with_backoff(failing_func, max_retries=3)

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_attempts(self):
        """Test function fails after all retries."""

        def always_failing_func():
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError, match="Permanent failure"):
            retry_with_backoff(always_failing_func, max_retries=2)

    def test_retry_with_custom_delay(self):
        """Test retry with custom delay parameters."""
        call_count = 0

        def timing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        with patch("time.sleep") as mock_sleep:
            retry_with_backoff(timing_func, max_retries=2, base_delay=0.1, backoff_factor=2.0)

        # Verify sleep was called with correct delays
        # The function sleeps with base_delay (0.1) first, then updates delay for next attempt
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(0.1)  # First sleep is base_delay before update

    def test_retry_respects_max_delay(self):
        """Test retry respects maximum delay limit."""
        call_count = 0

        def slow_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Temporary failure")

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                retry_with_backoff(
                    slow_failing_func,
                    max_retries=4,
                    base_delay=10.0,
                    max_delay=15.0,
                    backoff_factor=2.0,
                )

        # Verify sleep never exceeds max_delay
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        for delay in sleep_calls:
            assert delay <= 15.0
