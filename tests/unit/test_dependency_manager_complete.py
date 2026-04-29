"""
Additional unit tests for DependencyManager to achieve 100% coverage.

Covers:
- Failure dependency type handling
- Exception handling paths
- Edge cases
"""

from unittest.mock import MagicMock, patch

import pytest

from app.database.models import TaskStatus
from app.services.task_execution.dependency_manager import DependencyManager


class TestCanStartTaskFailureDependency:
    """Test can_start_task with failure dependency type."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_failure_dependency_met(self, mock_db_context: MagicMock) -> None:
        """Task with failed prerequisite for failure dependency can start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_dep = MagicMock()
        mock_dep.dependency_type = "failure"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.FAILED.value
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_failure_dependency_not_met(self, mock_db_context: MagicMock) -> None:
        """Task with completed prerequisite for failure dependency cannot start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_dep = MagicMock()
        mock_dep.dependency_type = "failure"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.COMPLETED.value  # Not failed
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is False

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_success_dependency(self, mock_db_context: MagicMock) -> None:
        """Task with success dependency type."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_dep = MagicMock()
        mock_dep.dependency_type = "success"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.COMPLETED.value
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is True


class TestCanStartTaskExceptionHandling:
    """Test exception handling in can_start_task."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_exception_returns_false(self, mock_db_context: MagicMock) -> None:
        """Exception during can_start_task returns False."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("DB error")

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is False

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_missing_prereq_logs_error(self, mock_db_context: MagicMock) -> None:
        """Missing prerequisite logs error and returns False."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "missing_prereq"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        # Return None for missing prerequisite
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.services.task_execution.dependency_manager.logger") as mock_logger:
            manager = DependencyManager()
            result = manager.can_start_task("task123")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "missing_prereq" in mock_logger.error.call_args[0][0]


class TestHasCycleExceptionHandling:
    """Test exception handling in has_cycle."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_has_cycle_exception_returns_true(self, mock_db_context: MagicMock) -> None:
        """Exception during has_cycle returns True (safe default)."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("DB error")

        manager = DependencyManager()
        result = manager.has_cycle("task123")
        # Returns True on exception as a safe default (assume cycle exists)
        assert result is True


class TestHasCycleComplexScenarios:
    """Test has_cycle with more complex scenarios."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_has_cycle_chain_detection(self, mock_db_context: MagicMock) -> None:
        """Detect cycle in longer chain."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Actually let's do it simpler with explicit mock returns
        manager = DependencyManager()

        # First call returns task2 as prereq of task3
        # Second call returns task1 as prereq of task2
        # Third call returns task3 as prereq of task1 (cycle!)
        dep1 = MagicMock()
        dep1.prerequisite_task_id = "task2"
        dep2 = MagicMock()
        dep2.prerequisite_task_id = "task1"
        dep3 = MagicMock()
        dep3.prerequisite_task_id = "task3"  # self-reference when checking task1

        side_effects = [[dep1], [dep2], [dep3]]
        mock_db.query.return_value.filter.return_value.all.side_effect = side_effects

        result = manager.has_cycle("task3")
        assert result is True


class TestGetDependencyChainEdgeCases:
    """Test get_dependency_chain edge cases."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependency_chain_exception_returns_empty(self, mock_db_context: MagicMock) -> None:
        """Exception during get_dependency_chain returns empty list."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("DB error")

        manager = DependencyManager()
        result = manager.get_dependency_chain("task123")
        assert result == []

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependency_chain_avoids_duplicates(self, mock_db_context: MagicMock) -> None:
        """Dependency chain avoids duplicate entries."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Create a diamond dependency pattern
        # task4 depends on task2 and task3
        # task2 and task3 both depend on task1
        # task1 should only appear once in chain

        dep1 = MagicMock()
        dep1.prerequisite_task_id = "task2"
        dep2 = MagicMock()
        dep2.prerequisite_task_id = "task3"

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [dep1, dep2],  # task4's deps
            [],  # task2 has no deps
            [dep1],  # task3 depends on task2
            [],  # task2 already visited
        ]

        manager = DependencyManager()
        result = manager.get_dependency_chain("task4")

        # task2 should appear only once even though reached twice
        assert result.count("task2") == 1


class TestGetDependentTasksExceptionHandling:
    """Test exception handling in get_dependent_tasks."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependent_tasks_exception_returns_empty(self, mock_db_context: MagicMock) -> None:
        """Exception during get_dependent_tasks returns empty list."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.side_effect = Exception("DB error")

        manager = DependencyManager()
        result = manager.get_dependent_tasks("task123")
        assert result == []


class TestValidateNewDependencyExceptionHandling:
    """Test exception handling in validate_new_dependency."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_validate_new_dependency_exception_raises_value_error(
        self, mock_db_context: MagicMock
    ) -> None:
        """Exception during validate_new_dependency raises ValueError."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        with patch.object(manager, "get_dependency_chain", side_effect=Exception("DB error")):
            with pytest.raises(ValueError):
                manager.validate_new_dependency("task1", "task2")


class TestGetReadyTasksExceptionHandling:
    """Test exception handling in get_ready_tasks."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_ready_tasks_exception_returns_empty(self, mock_db_context: MagicMock) -> None:
        """Exception during get_ready_tasks returns empty list."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = (
            Exception("DB error")
        )

        manager = DependencyManager()
        result = manager.get_ready_tasks("session123")
        assert result == []

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_ready_tasks_can_start_exception(self, mock_db_context: MagicMock) -> None:
        """Exception in can_start_task during get_ready_tasks is handled."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task
        ]

        manager = DependencyManager()

        with patch.object(manager, "can_start_task", side_effect=Exception("Check failed")):
            # Should not raise, just skip the task
            result = manager.get_ready_tasks("session123")
            assert result == []
