"""
Tests for experimental_tasks.py when APGI system is unavailable.

These tests verify the graceful fallback behavior when apgi_system is not installed.
Note: Celery is mocked globally in conftest.py, so we test module structure and
error handling logic rather than calling task functions directly.
"""

import sys
import pytest
from unittest.mock import patch


# Make Celery mock return actual decorated function
def mock_celery_task_decorator(*args, bind=False, base=None, name=None, **kwargs):
    """Mock decorator that returns the actual function being decorated."""

    def decorator(func):
        func.name = name or func.__name__
        func.bind = bind
        func.base = base
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


@pytest.fixture(autouse=True, scope="module")
def mock_celery_app_task():
    """Make celery_app.task return actual decorated functions."""
    with patch("app.celery_app.celery_app.task", side_effect=mock_celery_task_decorator):
        yield


@pytest.fixture(autouse=True)
def clear_modules():
    """Clear module cache before each test to ensure fresh imports."""
    # Clear any cached import of experimental_tasks
    if "app.tasks.experimental_tasks" in sys.modules:
        del sys.modules["app.tasks.experimental_tasks"]
    if "app.tasks" in sys.modules:
        del sys.modules["app.tasks"]
    yield


class TestAPGITaskUnavailablePaths:
    """Test APGITask base class behavior when APGI unavailable."""

    def test_apgi_system_available_flag_is_false(self):
        """Test APGI_SYSTEM_AVAILABLE is False when apgi_system not installed."""
        from app.tasks import experimental_tasks

        # In the test environment, conftest.py mocks apgi_system as unavailable
        # The flag reflects the state at import time
        assert experimental_tasks.APGI_SYSTEM_AVAILABLE is False

    def test_apgi_task_classes_are_none_when_unavailable(self):
        """Test that APGI task classes are None when system unavailable."""
        from app.tasks import experimental_tasks

        # Only verify if APGI is actually unavailable in this environment
        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            # All task classes should be None when APGI unavailable
            assert experimental_tasks.AttentionalBlinkTask is None
            assert experimental_tasks.BinocularRivalryTask is None
            assert experimental_tasks.ChangeBlindnessTask is None
            assert experimental_tasks.IowaGamblingTask is None
            assert experimental_tasks.MaskingParadigmTask is None
            assert experimental_tasks.get_resource_path is None
            assert experimental_tasks.APGISystem is None


class TestAPGITaskBaseClass:
    """Test APGITask base class with mocked Celery."""

    def test_apgi_task_class_exists(self):
        """Test APGITask base class exists and can be instantiated."""
        from app.tasks.experimental_tasks import APGITask

        task = APGITask()
        # Task should be created successfully
        assert task is not None


class TestCeleryTaskFunctionsExist:
    """Test that Celery task functions are defined when APGI unavailable."""

    def test_execute_iowa_gambling_task_exists(self):
        """Test Iowa Gambling task function exists."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_iowa_gambling_task")
        # Verify it has Celery task attributes
        assert hasattr(experimental_tasks.execute_iowa_gambling_task, "name")
        assert hasattr(experimental_tasks.execute_iowa_gambling_task, "run")

    def test_execute_masking_paradigm_task_exists(self):
        """Test Masking Paradigm task function exists."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_masking_paradigm_task")
        assert hasattr(experimental_tasks.execute_masking_paradigm_task, "name")

    def test_execute_attentional_blink_task_exists(self):
        """Test Attentional Blink task function exists."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_attentional_blink_task")
        assert hasattr(experimental_tasks.execute_attentional_blink_task, "name")

    def test_execute_change_blindness_task_exists(self):
        """Test Change Blindness task function exists."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_change_blindness_task")
        assert hasattr(experimental_tasks.execute_change_blindness_task, "name")

    def test_execute_binocular_rivalry_task_exists(self):
        """Test Binocular Rivalry task function exists."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_binocular_rivalry_task")
        assert hasattr(experimental_tasks.execute_binocular_rivalry_task, "name")


class TestTriggerWebhookFunction:
    """Test trigger_webhook_on_completion function."""

    def test_trigger_webhook_is_async(self):
        """Test that trigger_webhook_on_completion is async."""
        import inspect
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        assert inspect.iscoroutinefunction(trigger_webhook_on_completion)

    def test_trigger_webhook_accepts_parameters(self):
        """Test trigger_webhook_on_completion accepts required parameters."""
        import inspect
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        sig = inspect.signature(trigger_webhook_on_completion)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "result" in params


class TestModuleImports:
    """Test module can be imported even when APGI unavailable."""

    def test_module_imports_successfully(self):
        """Test that experimental_tasks module imports without error."""
        # When running with mocked apgi_system from conftest.py,
        # the module imports successfully regardless of APGI availability
        from app.tasks import experimental_tasks

        assert experimental_tasks is not None
        assert hasattr(experimental_tasks, "APGI_SYSTEM_AVAILABLE")
        # The flag value depends on whether apgi_system was available at import time
        assert isinstance(experimental_tasks.APGI_SYSTEM_AVAILABLE, bool)
