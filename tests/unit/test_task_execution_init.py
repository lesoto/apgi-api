"""
Unit tests for task_execution __init__ module.
Requirements: 4.7, 5.1
"""

from app.services.task_execution import (
    DependencyManager,
    TaskExecutor,
    TaskStrategy,
    TaskStrategyRegistry,
    TaskSubmitter,
)


class TestTaskExecutionImports:
    """Test that all expected exports are available."""

    def test_dependency_manager_imported(self) -> None:
        """DependencyManager is exported."""
        assert DependencyManager is not None

    def test_task_executor_imported(self) -> None:
        """TaskExecutor is exported."""
        assert TaskExecutor is not None

    def test_task_strategy_imported(self) -> None:
        """TaskStrategy is exported."""
        assert TaskStrategy is not None

    def test_task_strategy_registry_imported(self) -> None:
        """TaskStrategyRegistry is exported."""
        assert TaskStrategyRegistry is not None

    def test_task_submitter_imported(self) -> None:
        """TaskSubmitter is exported."""
        assert TaskSubmitter is not None


class TestTaskExecutionAll:
    """Test __all__ export list."""

    def test_all_defined(self) -> None:
        """__all__ is defined in module."""
        from app.services.task_execution import __all__

        assert __all__ is not None
        assert len(__all__) == 5

    def test_all_contains_expected(self) -> None:
        """__all__ contains expected exports."""
        from app.services.task_execution import __all__

        assert "TaskExecutor" in __all__
        assert "TaskStrategy" in __all__
        assert "TaskStrategyRegistry" in __all__
        assert "DependencyManager" in __all__
        assert "TaskSubmitter" in __all__
