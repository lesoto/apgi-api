"""
Comprehensive tests for task_execution module.
Covers: dependency_manager, task_executor, task_strategies, task_submitter
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.database.models import Task, TaskDependency, TaskStatus
from app.services.task_execution.dependency_manager import DependencyManager
from app.services.task_execution.task_executor import TaskExecutor
from app.services.task_execution.task_strategies import (
    IowaGamblingStrategy,
    ParameterSchema,
    TaskStrategyRegistry,
    get_task_strategy_registry,
)
from app.services.task_execution.task_submitter import TaskSubmitter, async_retry_with_backoff


class TestDependencyManager:
    """Test dependency manager module."""

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_success(self, mock_get_db):
        """Test can_start_task when all dependencies are satisfied."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        # Setup dependencies
        dep = TaskDependency(
            dependent_task_id="task-1",
            prerequisite_task_id="task-2",
            dependency_type="success",
        )
        mock_db.query.return_value.filter.return_value.all.return_value = [dep]

        # Setup prerequisite task
        prereq = Task(task_id="task-2", status=TaskStatus.COMPLETED.value)
        mock_db.query.return_value.filter.return_value.first.return_value = prereq

        assert manager.can_start_task("task-1") is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_can_start_task_failure_dep(self, mock_get_db):
        """Test can_start_task with failure dependency."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        dep = TaskDependency(
            dependent_task_id="task-1",
            prerequisite_task_id="task-2",
            dependency_type="failure",
        )
        mock_db.query.return_value.filter.return_value.all.return_value = [dep]

        # Prerequisite failed
        prereq = Task(task_id="task-2", status=TaskStatus.FAILED.value)
        mock_db.query.return_value.filter.return_value.first.return_value = prereq

        assert manager.can_start_task("task-1") is True

        # Prerequisite completed (so dependency NOT satisfied)
        prereq.status = TaskStatus.COMPLETED.value
        assert manager.can_start_task("task-1") is False

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_has_cycle_detected(self, mock_get_db):
        """Test cycle detection."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        # Task 1 depends on Task 2
        dep1 = TaskDependency(dependent_task_id="task-1", prerequisite_task_id="task-2")
        # Task 2 depends on Task 1
        dep2 = TaskDependency(dependent_task_id="task-2", prerequisite_task_id="task-1")

        # Mock the query behavior using a side effect sequence for the filter calls
        mock_db.query.return_value.filter.side_effect = [
            MagicMock(all=MagicMock(return_value=[dep1])),
            MagicMock(all=MagicMock(return_value=[dep2])),
        ]

        assert manager.has_cycle("task-1") is True

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_get_dependency_chain(self, mock_get_db):
        """Test retrieving full dependency chain."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        dep = TaskDependency(dependent_task_id="task-1", prerequisite_task_id="task-2")
        mock_db.query.return_value.filter.return_value.all.return_value = [dep]

        chain = manager.get_dependency_chain("task-1")
        assert "task-2" in chain

    @patch("app.services.task_execution.dependency_manager.get_db_context")
    def test_validate_new_dependency_cycle(self, mock_get_db):
        """Test validating new dependency throws if cycle created."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        manager = DependencyManager()

        # Task 2 already depends on Task 1
        dep = TaskDependency(dependent_task_id="task-2", prerequisite_task_id="task-1")
        mock_db.query.return_value.filter.return_value.all.return_value = [dep]

        # Trying to make Task 1 depend on Task 2 should fail
        with pytest.raises(ValueError, match="would create a cycle"):
            manager.validate_new_dependency("task-1", "task-2")


class TestTaskStrategies:
    """Test task strategies module."""

    def test_parameter_schema(self):
        """Test ParameterSchema dataclass."""
        schema = ParameterSchema(name="p1", param_type="int", default=1, description="desc")
        assert schema.name == "p1"
        assert schema.default == 1

    def test_iowa_gambling_strategy(self):
        """Test IowaGamblingStrategy validation."""
        strategy = IowaGamblingStrategy()
        params = {"num_trials": 50, "deck_selection_strategy": "random"}
        validated = strategy.validate_parameters(params)
        assert validated["num_trials"] == 50
        assert validated["initial_balance"] == 2000  # Default

        with pytest.raises(ValueError, match="num_trials must be a positive integer"):
            strategy.validate_parameters({"num_trials": 0})

        with pytest.raises(ValueError, match="Invalid deck_selection_strategy"):
            strategy.validate_parameters({"deck_selection_strategy": "invalid"})

    def test_strategy_registry(self):
        """Test TaskStrategyRegistry."""
        registry = TaskStrategyRegistry()
        assert registry.is_valid_task_type("iowa_gambling")
        assert not registry.is_valid_task_type("non-existent")

        strategy = registry.get("iowa_gambling")
        assert isinstance(strategy, IowaGamblingStrategy)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(IowaGamblingStrategy())

    def test_get_task_strategy_registry_singleton(self):
        """Test registry singleton getter."""
        r1 = get_task_strategy_registry()
        r2 = get_task_strategy_registry()
        assert r1 is r2


class TestTaskSubmitter:
    """Test task submitter module."""

    @pytest.mark.asyncio
    @patch("app.services.task_execution.task_submitter.get_db_context")
    async def test_submit_task(self, mock_get_db):
        """Test submit_task creates DB record."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        submitter = TaskSubmitter()
        task_id = await submitter.submit_task(
            session_id="session-1",
            task_type="iowa_gambling",
            parameters={"num_trials": 10},
            user_id="user-1",
        )

        assert uuid.UUID(task_id)
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_async_retry_with_backoff_success(self):
        """Test retry helper success."""
        mock_func = MagicMock(side_effect=[Exception("fail"), "success"])

        async def func():
            return mock_func()

        result = await async_retry_with_backoff(func, max_retries=1, base_delay=0.01)
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry_with_backoff_failure(self):
        """Test retry helper exhaustion."""

        async def func():
            raise ValueError("permanent fail")

        with pytest.raises(ValueError, match="permanent fail"):
            await async_retry_with_backoff(func, max_retries=1, base_delay=0.01)

    @patch("app.services.task_execution.task_submitter.get_db_context")
    def test_mark_task_failed(self, mock_get_db):
        """Test marking task as failed."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        task = Task(task_id="t1", status=TaskStatus.PENDING.value)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        submitter = TaskSubmitter()
        submitter.mark_task_failed("t1", "some error")

        assert task.status == TaskStatus.FAILED.value
        assert task.error_message == "some error"
        assert task.completed_at is not None


class TestTaskExecutor:
    """Test task executor module."""

    @patch("app.services.task_execution.task_executor.get_db_context")
    @patch("app.services.task_execution.task_executor.TaskSubmitter")
    @pytest.mark.asyncio
    async def test_submit_task_orchestration(self, mock_submitter_class, mock_get_db):
        """Test TaskExecutor.submit_task orchestration."""
        mock_submitter = mock_submitter_class.return_value
        # Use an async mock for the async method
        from unittest.mock import AsyncMock

        mock_submitter.submit_task = AsyncMock(return_value="task-1")
        mock_submitter.start_task_immediately = AsyncMock()

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        # Mock session record for ownership validation
        mock_session = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        executor = TaskExecutor()
        executor.dependency_manager = MagicMock()
        executor.dependency_manager.has_cycle.return_value = False
        executor.dependency_manager.can_start_task.return_value = True

        task_id = await executor.submit_task(
            session_id="session-1",
            task_type="iowa_gambling",
            parameters={},
            user_id="user-1",
        )

        assert task_id == "task-1"
        assert mock_submitter.start_task_immediately.called

    @patch("app.services.task_execution.task_executor.get_db_context")
    @patch("app.services.task_execution.task_executor.AsyncResult")
    @pytest.mark.asyncio
    async def test_get_task_status(self, mock_async_result, mock_get_db):
        """Test retrieving task status."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock DB record
        task = Task(task_id="t1", status=TaskStatus.RUNNING.value, result_data={"score": 100})
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            task
        )

        # Mock Celery result
        mock_res = mock_async_result.return_value
        mock_res.state = "SUCCESS"

        executor = TaskExecutor()
        status = await executor.get_task_status("t1", "user-1")

        assert status["status"] == TaskStatus.RUNNING.value
        assert status["state"] == "SUCCESS"
        assert status["result"] == {"score": 100}
