"""
Unit tests for task registry functionality.
"""

from __future__ import annotations

from typing import Any, Callable, Generator
from unittest.mock import patch

import pytest


# Make Celery mock return actual decorated function
def mock_celery_task_decorator(
    *args: Any, bind: bool = False, base: Any = None, name: Any = None, **kwargs: Any
) -> Callable[..., Any]:
    """Mock decorator that returns the actual function being decorated."""

    def decorator(func: Any) -> Any:
        func.name = name or func.__name__
        func.bind = bind
        func.base = base
        return func

    if args and callable(args[0]):
        return decorator(args[0])  # type: ignore[no-any-return]
    return decorator


@pytest.fixture(autouse=True, scope="module")
def mock_celery_app_task() -> Generator[None, None, None]:
    """Make celery_app.task return actual decorated functions."""
    with patch("app.celery_app.celery_app.task", side_effect=mock_celery_task_decorator):
        yield


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

    def test_task_type_enum(self) -> None:
        """Test TaskType enum values."""
        assert TaskType.IOWA_GAMBLING.value == "iowa_gambling"
        assert TaskType.MASKING_PARADIGM.value == "masking_paradigm"
        assert TaskType.ATTENTIONAL_BLINK.value == "attentional_blink"
        assert TaskType.CHANGE_BLINDNESS.value == "change_blindness"
        assert TaskType.BINOCULAR_RIVALRY.value == "binocular_rivalry"

    def test_task_registry_mapping(self) -> None:
        """Test TASK_REGISTRY contains all task types."""
        assert len(TASK_REGISTRY) == 5
        for task_type in TaskType:
            assert task_type in TASK_REGISTRY
            assert TASK_REGISTRY[task_type].startswith("app.tasks.experimental_tasks.")

    def test_task_registry_specific_names(self) -> None:
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

    def test_task_functions_mapping(self) -> None:
        """Test TASK_FUNCTIONS contains all task types."""
        assert len(TASK_FUNCTIONS) == 5
        for task_type in TaskType:
            assert task_type in TASK_FUNCTIONS
            assert callable(TASK_FUNCTIONS[task_type])

    def test_task_functions_specific_functions(self) -> None:
        """Test TASK_FUNCTIONS has correct functions."""
        # Verify functions are callable (they're Celery task objects)
        # When Celery is globally mocked, these are MagicMock objects
        assert callable(TASK_FUNCTIONS[TaskType.IOWA_GAMBLING])
        assert callable(TASK_FUNCTIONS[TaskType.MASKING_PARADIGM])
        assert callable(TASK_FUNCTIONS[TaskType.ATTENTIONAL_BLINK])
        assert callable(TASK_FUNCTIONS[TaskType.CHANGE_BLINDNESS])
        assert callable(TASK_FUNCTIONS[TaskType.BINOCULAR_RIVALRY])

        # Verify the task names in registry match expected pattern
        assert "iowa_gambling" in TASK_REGISTRY[TaskType.IOWA_GAMBLING]
        assert "masking_paradigm" in TASK_REGISTRY[TaskType.MASKING_PARADIGM]
        assert "attentional_blink" in TASK_REGISTRY[TaskType.ATTENTIONAL_BLINK]
        assert "change_blindness" in TASK_REGISTRY[TaskType.CHANGE_BLINDNESS]
        assert "binocular_rivalry" in TASK_REGISTRY[TaskType.BINOCULAR_RIVALRY]

    def test_get_task_function_valid(self) -> None:
        """Test get_task_function with valid task type."""
        for task_type in TaskType:
            func = get_task_function(task_type)
            assert callable(func)
            assert func == TASK_FUNCTIONS[task_type]

    def test_get_task_function_invalid(self) -> None:
        """Test get_task_function with invalid task type."""
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_function("invalid_task")  # type: ignore

    def test_get_task_function_invalid_enum_value(self) -> None:
        """Test get_task_function with invalid enum value."""

        # Create an invalid enum-like object
        class InvalidTaskType:
            pass

        invalid_task = InvalidTaskType()
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_function(invalid_task)  # type: ignore

    def test_get_task_name_valid(self) -> None:
        """Test get_task_name with valid task type."""
        for task_type in TaskType:
            name = get_task_name(task_type)
            assert isinstance(name, str)
            assert name == TASK_REGISTRY[task_type]

    def test_get_task_name_invalid(self) -> None:
        """Test get_task_name with invalid task type."""
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_name("invalid_task")  # type: ignore[arg-type]

    def test_get_task_name_invalid_enum_value(self) -> None:
        """Test get_task_name with invalid enum value."""

        # Create an invalid enum-like object
        class InvalidTaskType:
            pass

        invalid_task = InvalidTaskType()
        with pytest.raises(ValueError, match="Unsupported task type"):
            get_task_name(invalid_task)  # type: ignore[arg-type]

    def test_list_available_tasks(self) -> None:
        """Test list_available_tasks returns all task types."""
        tasks = list_available_tasks()
        assert len(tasks) == 5
        for task_type in TaskType:
            assert task_type in tasks

    def test_list_available_tasks_is_list(self) -> None:
        """Test list_available_tasks returns a list."""
        tasks = list_available_tasks()
        assert isinstance(tasks, list)

    def test_validate_task_type_valid(self) -> None:
        """Test validate_task_type with valid string."""
        for task_type in TaskType:
            result = validate_task_type(task_type.value)
            assert result == task_type

    def test_validate_task_type_invalid(self) -> None:
        """Test validate_task_type with invalid string."""
        with pytest.raises(ValueError, match="Invalid task type"):
            validate_task_type("invalid_task")

    def test_validate_task_type_error_message(self) -> None:
        """Test validate_task_type error message includes available tasks."""
        with pytest.raises(ValueError) as exc_info:
            validate_task_type("nonexistent")

        error_msg = str(exc_info.value)
        assert "Invalid task type" in error_msg
        assert "Available tasks" in error_msg

    def test_task_type_enum_string_conversion(self) -> None:
        """Test TaskType enum can be converted to string."""
        task_type = TaskType.IOWA_GAMBLING
        assert str(task_type.value) == "iowa_gambling"

    def test_task_registry_and_functions_consistency(self) -> None:
        """Test that TASK_REGISTRY and TASK_FUNCTIONS have same keys."""
        assert set(TASK_REGISTRY.keys()) == set(TASK_FUNCTIONS.keys())

    def test_get_task_function_returns_same_as_dict_access(self) -> None:
        """Test that get_task_function returns same function as direct dict access."""
        for task_type in TaskType:
            func_via_getter = get_task_function(task_type)
            func_via_dict = TASK_FUNCTIONS[task_type]
            assert func_via_getter is func_via_dict

    def test_get_task_name_returns_same_as_dict_access(self) -> None:
        """Test that get_task_name returns same name as direct dict access."""
        for task_type in TaskType:
            name_via_getter = get_task_name(task_type)
            name_via_dict = TASK_REGISTRY[task_type]
            assert name_via_getter == name_via_dict
