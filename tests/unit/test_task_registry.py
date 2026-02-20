"""
Unit tests for task registry functionality.
"""

import pytest

from app.tasks.task_registry import (
    TaskType,
    TASK_REGISTRY,
    TASK_FUNCTIONS,
    get_task_function,
    get_task_name,
    list_available_tasks,
    validate_task_type,
)


class TestTaskRegistry:
    """Test task registry functionality."""

    def test_task_type_enum(self):
        """Test TaskType enum values."""
        assert TaskType.IOWA_GAMBLING.value == "iowa_gambling"
        assert TaskType.MASKING_PARADIGM.value == "masking_paradigm"
        assert TaskType.ATTENTIONAL_BLINK.value == "attentional_blink"
        assert TaskType.CHANGE_BLINDNESS.value == "change_blindness"
        assert TaskType.BINOCULAR_RIVALRY.value == "binocular_rivalry"

    def test_task_registry_mapping(self):
        """Test TASK_REGISTRY contains all task types."""
        assert len(TASK_REGISTRY) == 5
        for task_type in TaskType:
            assert task_type in TASK_REGISTRY
            assert TASK_REGISTRY[task_type].startswith("app.tasks.experimental_tasks.")

    def test_task_functions_mapping(self):
        """Test TASK_FUNCTIONS contains all task types."""
        assert len(TASK_FUNCTIONS) == 5
        for task_type in TaskType:
            assert task_type in TASK_FUNCTIONS
            assert callable(TASK_FUNCTIONS[task_type])

    def test_get_task_function_valid(self):
        """Test get_task_function with valid task type."""
        for task_type in TaskType:
            func = get_task_function(task_type)
            assert callable(func)
            assert func == TASK_FUNCTIONS[task_type]

    def test_get_task_function_invalid(self):
        """Test get_task_function with invalid task type."""
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_function("invalid_task")  # type: ignore[arg-type]

    def test_get_task_name_valid(self):
        """Test get_task_name with valid task type."""
        for task_type in TaskType:
            name = get_task_name(task_type)
            assert isinstance(name, str)
            assert name == TASK_REGISTRY[task_type]

    def test_get_task_name_invalid(self):
        """Test get_task_name with invalid task type."""
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_name("invalid_task")  # type: ignore[arg-type]

    def test_list_available_tasks(self):
        """Test list_available_tasks returns all task types."""
        tasks = list_available_tasks()
        assert len(tasks) == 5
        for task_type in TaskType:
            assert task_type in tasks

    def test_validate_task_type_valid(self):
        """Test validate_task_type with valid string."""
        for task_type in TaskType:
            result = validate_task_type(task_type.value)
            assert result == task_type

    def test_validate_task_type_invalid(self):
        """Test validate_task_type with invalid string."""
        with pytest.raises(ValueError, match="Invalid task type"):
            validate_task_type("invalid_task")
