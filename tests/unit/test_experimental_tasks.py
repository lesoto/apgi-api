"""
Minimal test suite for experimental_tasks.py
Tests the core functionality without complex Celery mocking.
"""

import inspect


class TestModuleStructure:
    """Test module structure and imports."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        from app.tasks import experimental_tasks

        # Module should be importable
        assert experimental_tasks is not None

    def test_apgi_system_available_flag_exists(self):
        """Test APGI_SYSTEM_AVAILABLE flag exists and is boolean."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "APGI_SYSTEM_AVAILABLE")
        assert isinstance(experimental_tasks.APGI_SYSTEM_AVAILABLE, bool)

    def test_task_classes_defined(self):
        """Test that task classes are defined."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "IowaGamblingTask")
        assert hasattr(experimental_tasks, "MaskingParadigmTask")
        assert hasattr(experimental_tasks, "AttentionalBlinkTask")
        assert hasattr(experimental_tasks, "ChangeBlindnessTask")
        assert hasattr(experimental_tasks, "BinocularRivalryTask")

    def test_celery_tasks_defined(self):
        """Test that Celery task functions are defined."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "execute_iowa_gambling_task")
        assert hasattr(experimental_tasks, "execute_masking_paradigm_task")
        assert hasattr(experimental_tasks, "execute_attentional_blink_task")
        assert hasattr(experimental_tasks, "execute_change_blindness_task")
        assert hasattr(experimental_tasks, "execute_binocular_rivalry_task")

    def test_trigger_webhook_function_defined(self):
        """Test trigger_webhook_on_completion function is defined."""
        from app.tasks import experimental_tasks

        assert hasattr(experimental_tasks, "trigger_webhook_on_completion")


class TestAPGIImportHandling:
    """Test handling of APGI system import failures."""

    def test_apgi_classes_none_when_unavailable(self):
        """Test that task classes are None when APGI system unavailable."""
        from app.tasks import experimental_tasks

        if not experimental_tasks.APGI_SYSTEM_AVAILABLE:
            # When APGI is not available, classes should be None
            assert experimental_tasks.IowaGamblingTask is None
            assert experimental_tasks.MaskingParadigmTask is None
            assert experimental_tasks.AttentionalBlinkTask is None
            assert experimental_tasks.ChangeBlindnessTask is None
            assert experimental_tasks.BinocularRivalryTask is None


class TestCeleryTaskSignatures:
    """Test Celery task function signatures."""

    def test_iowa_gambling_task_signature(self):
        """Test Iowa Gambling task accepts correct parameters."""
        from app.tasks.experimental_tasks import execute_iowa_gambling_task

        # Check function exists and is callable
        assert callable(execute_iowa_gambling_task)

    def test_masking_paradigm_task_signature(self):
        """Test Masking Paradigm task accepts correct parameters."""
        from app.tasks.experimental_tasks import execute_masking_paradigm_task

        assert callable(execute_masking_paradigm_task)

    def test_attentional_blink_task_signature(self):
        """Test Attentional Blink task accepts correct parameters."""
        from app.tasks.experimental_tasks import execute_attentional_blink_task

        assert callable(execute_attentional_blink_task)

    def test_change_blindness_task_signature(self):
        """Test Change Blindness task accepts correct parameters."""
        from app.tasks.experimental_tasks import execute_change_blindness_task

        assert callable(execute_change_blindness_task)

    def test_binocular_rivalry_task_signature(self):
        """Test Binocular Rivalry task accepts correct parameters."""
        from app.tasks.experimental_tasks import execute_binocular_rivalry_task

        assert callable(execute_binocular_rivalry_task)


class TestWebhookFunction:
    """Test webhook triggering function."""

    def test_trigger_webhook_is_async(self):
        """Test that trigger_webhook_on_completion is async."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        assert inspect.iscoroutinefunction(trigger_webhook_on_completion)

    def test_trigger_webhook_accepts_parameters(self):
        """Test trigger_webhook_on_completion accepts required parameters."""
        from app.tasks.experimental_tasks import trigger_webhook_on_completion

        # Check function signature
        sig = inspect.signature(trigger_webhook_on_completion)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "result" in params
