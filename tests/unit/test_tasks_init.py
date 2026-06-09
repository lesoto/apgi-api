"""
Unit tests for app/tasks/__init__.py
"""

from app.tasks import __all__, experimental_tasks


class TestTasksInit:
    """Test tasks/__init__.py imports."""

    def test_experimental_tasks_imported(self):
        """Test that experimental_tasks is imported."""
        assert experimental_tasks is not None

    def test_all_list_complete(self):
        """Test that __all__ contains expected items."""
        assert "experimental_tasks" in __all__

    def test_all_list_length(self):
        """Test that __all__ has the correct length."""
        assert len(__all__) == 1
