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

    def test_task_registry_specific_names(self):
        """Test TASK_REGISTRY has correct task names."""
        assert (
            TASK_REGISTRY[TaskType.IOWA_GAMBLING]
            == "app.tasks.experimental_tasks.execute_iowa_gambling_task"
        )
        assert (
            TASK_REGISTRY[TaskType.MASKING_PARADIGM]
            == "app.tasks.experimental_tasks.execute_masking_paradigm_task"
        )
        assert (
            TASK_REGISTRY[TaskType.ATTENTIONAL_BLINK]
            == "app.tasks.experimental_tasks.execute_attentional_blink_task"
        )
        assert (
            TASK_REGISTRY[TaskType.CHANGE_BLINDNESS]
            == "app.tasks.experimental_tasks.execute_change_blindness_task"
        )
        assert (
            TASK_REGISTRY[TaskType.BINOCULAR_RIVALRY]
            == "app.tasks.experimental_tasks.execute_binocular_rivalry_task"
        )

    def test_task_functions_mapping(self):
        """Test TASK_FUNCTIONS contains all task types."""
        assert len(TASK_FUNCTIONS) == 5
        for task_type in TaskType:
            assert task_type in TASK_FUNCTIONS
            assert callable(TASK_FUNCTIONS[task_type])

    def test_task_functions_specific_functions(self):
        """Test TASK_FUNCTIONS has correct functions."""
        from app.tasks.experimental_tasks import (
            execute_iowa_gambling_task,
            execute_masking_paradigm_task,
            execute_attentional_blink_task,
            execute_change_blindness_task,
            execute_binocular_rivalry_task,
        )

        assert TASK_FUNCTIONS[TaskType.IOWA_GAMBLING] == execute_iowa_gambling_task
        assert TASK_FUNCTIONS[TaskType.MASKING_PARADIGM] == execute_masking_paradigm_task
        assert TASK_FUNCTIONS[TaskType.ATTENTIONAL_BLINK] == execute_attentional_blink_task
        assert TASK_FUNCTIONS[TaskType.CHANGE_BLINDNESS] == execute_change_blindness_task
        assert TASK_FUNCTIONS[TaskType.BINOCULAR_RIVALRY] == execute_binocular_rivalry_task

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

    def test_get_task_function_invalid_enum_value(self):
        """Test get_task_function with invalid enum value."""

        # Create an invalid enum-like object
        class InvalidTaskType:
            pass

        invalid_task = InvalidTaskType()
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_function(invalid_task)  # type: ignore[arg-type]

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

    def test_get_task_name_invalid_enum_value(self):
        """Test get_task_name with invalid enum value."""

        # Create an invalid enum-like object
        class InvalidTaskType:
            pass

        invalid_task = InvalidTaskType()
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_name(invalid_task)  # type: ignore[arg-type]

    def test_list_available_tasks(self):
        """Test list_available_tasks returns all task types."""
        tasks = list_available_tasks()
        assert len(tasks) == 5
        for task_type in TaskType:
            assert task_type in tasks

    def test_list_available_tasks_is_list(self):
        """Test list_available_tasks returns a list."""
        tasks = list_available_tasks()
        assert isinstance(tasks, list)

    def test_validate_task_type_valid(self):
        """Test validate_task_type with valid string."""
        for task_type in TaskType:
            result = validate_task_type(task_type.value)
            assert result == task_type

    def test_validate_task_type_invalid(self):
        """Test validate_task_type with invalid string."""
        with pytest.raises(ValueError, match="Invalid task type"):
            validate_task_type("invalid_task")

    def test_validate_task_type_error_message(self):
        """Test validate_task_type error message includes available tasks."""
        with pytest.raises(ValueError) as exc_info:
            validate_task_type("nonexistent")

        error_msg = str(exc_info.value)
        assert "Invalid task type" in error_msg
        assert "Available tasks" in error_msg

    def test_task_type_enum_string_conversion(self):
        """Test TaskType enum can be converted to string."""
        task_type = TaskType.IOWA_GAMBLING
        assert str(task_type.value) == "iowa_gambling"

    def test_task_registry_and_functions_consistency(self):
        """Test that TASK_REGISTRY and TASK_FUNCTIONS have same keys."""
        assert set(TASK_REGISTRY.keys()) == set(TASK_FUNCTIONS.keys())

    def test_get_task_function_returns_same_as_dict_access(self):
        """Test that get_task_function returns same function as direct dict access."""
        for task_type in TaskType:
            func_via_getter = get_task_function(task_type)
            func_via_dict = TASK_FUNCTIONS[task_type]
            assert func_via_getter is func_via_dict

    def test_get_task_name_returns_same_as_dict_access(self):
        """Test that get_task_name returns same name as direct dict access."""
        for task_type in TaskType:
            name_via_getter = get_task_name(task_type)
            name_via_dict = TASK_REGISTRY[task_type]
            assert name_via_getter == name_via_dict
