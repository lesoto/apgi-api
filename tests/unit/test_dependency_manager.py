"""
Unit tests for DependencyManager covering cycle detection, prerequisite checking, and dependency chain management.
Requirements: 4.7, 5.1
"""

from unittest.mock import MagicMock, patch

from app.services.task_execution.dependency_manager import DependencyManager


class TestDependencyManagerInit:
    """Test DependencyManager initialization."""

    def test_manager_initialization(self) -> None:
        """Manager initializes with empty cache."""
        manager = DependencyManager()
        assert len(manager._cycle_check_cache) == 0


class TestCanStartTask:
    """Test checking if task can start based on dependencies."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_no_dependencies(self, mock_db_context: MagicMock) -> None:
        """Task with no dependencies can start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_with_completed_prereq(self, mock_db_context: MagicMock) -> None:
        """Task with completed prerequisite can start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock dependency
        mock_dep = MagicMock()
        mock_dep.dependency_type = "completion"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        # Mock prerequisite task
        mock_prereq = MagicMock()
        mock_prereq.status = "completed"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_with_pending_prereq(self, mock_db_context: MagicMock) -> None:
        """Task with pending prerequisite cannot start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock dependency
        mock_dep = MagicMock()
        mock_dep.dependency_type = "completion"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        # Mock prerequisite task
        mock_prereq = MagicMock()
        mock_prereq.status = "pending"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is False

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_missing_prereq(self, mock_db_context: MagicMock) -> None:
        """Task with missing prerequisite cannot start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock dependency
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "missing_task"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        # Mock missing prerequisite
        mock_db.query.return_value.filter.return_value.first.return_value = None

        manager = DependencyManager()
        result = manager.can_start_task("task123")
        assert result is False


class TestHasCycle:
    """Test cycle detection in dependency graph."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_has_cycle_no_cycle(self, mock_db_context: MagicMock) -> None:
        """No cycle in simple dependency chain."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        manager = DependencyManager()
        result = manager.has_cycle("task123")
        assert result is False

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_has_cycle_self_loop(self, mock_db_context: MagicMock) -> None:
        """Detect self-referencing cycle."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock self-referencing dependency
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "task123"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        manager = DependencyManager()
        result = manager.has_cycle("task123")
        assert result is True


class TestGetDependencyChain:
    """Test getting dependency chain for a task."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependency_chain_no_deps(self, mock_db_context: MagicMock) -> None:
        """Empty chain for task with no dependencies."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        manager = DependencyManager()
        chain = manager.get_dependency_chain("task123")
        assert chain == []

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependency_chain_with_deps(self, mock_db_context: MagicMock) -> None:
        """Get chain with dependencies."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock dependency
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "prereq1"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        manager = DependencyManager()
        chain = manager.get_dependency_chain("task123")
        assert "prereq1" in chain


class TestGetDependentTasks:
    """Test getting tasks that depend on a given task."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependent_tasks_no_dependents(self, mock_db_context: MagicMock) -> None:
        """No tasks depend on this task."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        manager = DependencyManager()
        dependents = manager.get_dependent_tasks("task123")
        assert dependents == []

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependent_tasks_with_dependents(self, mock_db_context: MagicMock) -> None:
        """Get tasks that depend on this task."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock dependent tasks
        mock_dep1 = MagicMock()
        mock_dep1.dependent_task_id = "task1"
        mock_dep2 = MagicMock()
        mock_dep2.dependent_task_id = "task2"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep1, mock_dep2]

        manager = DependencyManager()
        dependents = manager.get_dependent_tasks("task123")
        assert "task1" in dependents
        assert "task2" in dependents


class TestValidateNewDependency:
    """Test validating new dependencies for cycles."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_validate_new_dependency_valid(self, mock_db_context: MagicMock) -> None:
        """Valid dependency doesn't create cycle."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        manager = DependencyManager()
        result = manager.validate_new_dependency("task1", "task2")
        assert result is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_validate_new_dependency_creates_cycle(self, mock_db_context: MagicMock) -> None:
        """Dependency that creates cycle raises error."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock existing chain that includes dependent
        mock_db.query.return_value.filter.return_value.all.return_value = []
        # Simulate chain containing task1
        manager = DependencyManager()
        with patch.object(manager, "get_dependency_chain", return_value=["task1"]):
            try:
                manager.validate_new_dependency("task1", "task2")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "cycle" in str(e).lower()


class TestGetReadyTasks:
    """Test getting tasks ready to start in a session."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_ready_tasks_no_tasks(self, mock_db_context: MagicMock) -> None:
        """No pending tasks in session."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        manager = DependencyManager()
        ready = manager.get_ready_tasks("session123")
        assert ready == []

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_ready_tasks_with_ready_task(self, mock_db_context: MagicMock) -> None:
        """Get tasks that can start."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock pending task
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task
        ]

        manager = DependencyManager()
        with patch.object(manager, "can_start_task", return_value=True):
            ready = manager.get_ready_tasks("session123")
            assert len(ready) == 1
            assert ready[0].task_id == "task123"

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_ready_tasks_blocked_by_deps(self, mock_db_context: MagicMock) -> None:
        """Tasks blocked by dependencies not included."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db

        # Mock pending task
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task
        ]

        manager = DependencyManager()
        with patch.object(manager, "can_start_task", return_value=False):
            ready = manager.get_ready_tasks("session123")
            assert len(ready) == 0
