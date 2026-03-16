"""
Unit tests for app/tracing.py - OpenTelemetry distributed tracing configuration.

Tests the actual configure_distributed_tracing implementation and related utilities.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Import the module (conftest already mocked all otel modules)
# ---------------------------------------------------------------------------

import app.tracing as tracing_module


# ---------------------------------------------------------------------------
# Test: module-level state
# ---------------------------------------------------------------------------


class TestModuleState:
    """Tests for module-level variables and flags."""

    def test_opentelemetry_available_flag_exists(self):
        """OPENTELEMETRY_AVAILABLE is a bool attribute on the module."""
        assert hasattr(tracing_module, "OPENTELEMETRY_AVAILABLE")
        assert isinstance(tracing_module.OPENTELEMETRY_AVAILABLE, bool)

    def test_module_has_all_public_functions(self):
        """All three public functions are defined."""
        assert callable(tracing_module.configure_distributed_tracing)
        assert callable(tracing_module.instrument_application)
        assert callable(tracing_module.get_tracer)

    def test_module_level_none_variables(self):
        """All private module-level vars exist (may be None or mocked)."""
        for attr in [
            "_trace",
            "_TracerProvider",
            "_BatchSpanProcessor",
            "_JaegerExporter",
            "_OTLPSpanExporter",
            "_FastAPIInstrumentor",
            "_SQLAlchemyInstrumentor",
            "_RedisInstrumentor",
            "_Resource",
        ]:
            assert hasattr(tracing_module, attr)


# ---------------------------------------------------------------------------
# Test: configure_distributed_tracing()
# ---------------------------------------------------------------------------


class TestConfigureDistributedTracing:
    """Tests for configure_distributed_tracing()."""

    def test_returns_early_when_otel_not_available(self, capsys):
        """When OPENTELEMETRY_AVAILABLE=False, prints message and returns."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                result = tracing_module.configure_distributed_tracing()

        captured = capsys.readouterr()
        assert result is None
        assert "OpenTelemetry not available" in captured.out

    def test_returns_early_when_tracing_disabled(self):
        """When TRACING_ENABLED=false, function returns None without error."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", {"TRACING_ENABLED": "false"}, clear=False):
                result = tracing_module.configure_distributed_tracing()

        assert result is None

    def test_returns_early_when_tracing_not_set(self):
        """When TRACING_ENABLED is not set (defaults to 'false'), returns early."""
        env_without_tracing = {k: v for k, v in os.environ.items() if k != "TRACING_ENABLED"}
        env_without_tracing["TRACING_ENABLED"] = "false"
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", env_without_tracing, clear=True):
                result = tracing_module.configure_distributed_tracing()

        assert result is None

    def test_configure_enabled_sets_tracer_provider(self):
        """When enabled, set_tracer_provider is called once."""
        mock_trace = MagicMock()


class TestOpenTelemetryDependencyFailure:
    """Tests for OpenTelemetry dependency failure handling (Lines 39-59)."""

    def test_import_error_sets_opentelemetry_unavailable(self):
        """When ImportError occurs, OPENTELEMETRY_AVAILABLE is set to False."""
        import importlib
        import app.tracing

        # Reload the module to trigger import attempt
        with patch("app.tracing.trace", side_effect=ImportError("No module named 'opentelemetry'")):
            with patch("app.tracing.TracerProvider", side_effect=ImportError("No module")):
                with patch("app.tracing.BatchSpanProcessor", side_effect=ImportError("No module")):
                    with patch("app.tracing.JaegerExporter", side_effect=ImportError("No module")):
                        with patch(
                            "app.tracing.OTLPSpanExporter", side_effect=ImportError("No module")
                        ):
                            with patch(
                                "app.tracing.FastAPIInstrumentor",
                                side_effect=ImportError("No module"),
                            ):
                                with patch(
                                    "app.tracing.SQLAlchemyInstrumentor",
                                    side_effect=ImportError("No module"),
                                ):
                                    with patch(
                                        "app.tracing.RedisInstrumentor",
                                        side_effect=ImportError("No module"),
                                    ):
                                        with patch(
                                            "app.tracing.Resource",
                                            side_effect=ImportError("No module"),
                                        ):
                                            importlib.reload(app.tracing)

        assert app.tracing.OPENTELEMETRY_AVAILABLE is False

    def test_type_error_sets_opentelemetry_unavailable(self):
        """When TypeError occurs (Python 3.14 compatibility), OPENTELEMETRY_AVAILABLE is set to False."""
        import importlib
        import app.tracing

        # Reload the module to trigger import attempt
        with patch("app.tracing.trace", side_effect=TypeError("Type error")):
            importlib.reload(app.tracing)

        assert app.tracing.OPENTELEMETRY_AVAILABLE is False

    def test_warning_issued_on_import_failure(self):
        """When import fails, a warning is issued."""
        import importlib
        import app.tracing

        with patch("app.tracing.trace", side_effect=ImportError("No module")):
            with patch("app.tracing.TracerProvider", side_effect=ImportError("No module")):
                with patch("app.tracing.BatchSpanProcessor", side_effect=ImportError("No module")):
                    with patch("app.tracing.JaegerExporter", side_effect=ImportError("No module")):
                        with patch(
                            "app.tracing.OTLPSpanExporter", side_effect=ImportError("No module")
                        ):
                            with patch(
                                "app.tracing.FastAPIInstrumentor",
                                side_effect=ImportError("No module"),
                            ):
                                with patch(
                                    "app.tracing.SQLAlchemyInstrumentor",
                                    side_effect=ImportError("No module"),
                                ):
                                    with patch(
                                        "app.tracing.RedisInstrumentor",
                                        side_effect=ImportError("No module"),
                                    ):
                                        with patch(
                                            "app.tracing.Resource",
                                            side_effect=ImportError("No module"),
                                        ):
                                            with pytest.warns(
                                                ImportWarning, match="OpenTelemetry not available"
                                            ):
                                                importlib.reload(app.tracing)

    def test_module_variables_set_to_none_on_failure(self):
        """When import fails, module variables are set to None."""
        import importlib
        import app.tracing

        with patch("app.tracing.trace", side_effect=ImportError("No module")):
            with patch("app.tracing.TracerProvider", side_effect=ImportError("No module")):
                with patch("app.tracing.BatchSpanProcessor", side_effect=ImportError("No module")):
                    with patch("app.tracing.JaegerExporter", side_effect=ImportError("No module")):
                        with patch(
                            "app.tracing.OTLPSpanExporter", side_effect=ImportError("No module")
                        ):
                            with patch(
                                "app.tracing.FastAPIInstrumentor",
                                side_effect=ImportError("No module"),
                            ):
                                with patch(
                                    "app.tracing.SQLAlchemyInstrumentor",
                                    side_effect=ImportError("No module"),
                                ):
                                    with patch(
                                        "app.tracing.RedisInstrumentor",
                                        side_effect=ImportError("No module"),
                                    ):
                                        with patch(
                                            "app.tracing.Resource",
                                            side_effect=ImportError("No module"),
                                        ):
                                            importlib.reload(app.tracing)

        # Check that all module-level variables are None
        assert app.tracing._trace is None
        assert app.tracing._TracerProvider is None
        assert app.tracing._BatchSpanProcessor is None
        assert app.tracing._JaegerExporter is None
        assert app.tracing._OTLPSpanExporter is None
        assert app.tracing._FastAPIInstrumentor is None
        assert app.tracing._SQLAlchemyInstrumentor is None
        assert app.tracing._RedisInstrumentor is None
        assert app.tracing._Resource is None

    def test_partial_import_failure(self):
        """When only some imports fail, OPENTELEMETRY_AVAILABLE is still False."""
        import importlib
        import app.tracing

        # Some imports succeed, some fail
        mock_trace = MagicMock()
        mock_tracer_provider_cls = MagicMock()
        mock_provider_instance = MagicMock()
        mock_tracer_provider_cls.return_value = mock_provider_instance
        mock_trace.get_tracer_provider.return_value = mock_provider_instance

        with patch("app.tracing.trace", return_value=mock_trace):
            with patch("app.tracing.TracerProvider", side_effect=ImportError("No module")):
                importlib.reload(app.tracing)

        # Should still be unavailable if any import fails
        assert app.tracing.OPENTELEMETRY_AVAILABLE is False

        mock_resource = MagicMock()

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_ENDPOINT": "http://localhost:14268/api/traces",
            "OTLP_ENDPOINT": "http://localhost:4317",
            "TRACING_SERVICE_NAME": "test-service",
            "API_VERSION": "1.0.0",
            "OTLP_INSECURE": "true",
            "OTLP_HEADERS": "",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(tracing_module, "_TracerProvider", mock_tracer_provider_cls):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", MagicMock()):
                                with patch.object(tracing_module, "_Resource", mock_resource):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_trace.set_tracer_provider.assert_called_once()

    def test_configure_adds_two_span_processors(self):
        """configure_distributed_tracing adds span processors for Jaeger and OTLP."""
        import app.tracing as tracing_module

        mock_trace = MagicMock()
        mock_provider_instance = MagicMock()
        mock_tracer_provider_cls = MagicMock(return_value=mock_provider_instance)
        mock_trace.get_tracer_provider.return_value = mock_provider_instance

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_ENDPOINT": "http://jaeger:14268/api/traces",
            "OTLP_ENDPOINT": "http://otlp:4317",
            "TRACING_SERVICE_NAME": "svc",
            "API_VERSION": "1.0",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(tracing_module, "_TracerProvider", mock_tracer_provider_cls):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", MagicMock()):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        assert mock_provider_instance.add_span_processor.call_count == 2

    def test_configure_with_custom_jaeger_credentials(self):
        """Custom Jaeger username/password are passed to the exporter."""
        mock_jaeger_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_USERNAME": "myuser",
            "JAEGER_PASSWORD": "mypass",
            "OTLP_INSECURE": "false",
            "OTLP_HEADERS": "X-Custom=value",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", mock_jaeger_cls):
                            with patch.object(tracing_module, "_OTLPSpanExporter", MagicMock()):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        # JaegerExporter should have been called with the credentials
        mock_jaeger_cls.assert_called_once()
        call_kwargs = mock_jaeger_cls.call_args[1]
        assert call_kwargs.get("username") == "myuser"
        assert call_kwargs.get("password") == "mypass"

    def test_configure_enabled_uppercase_true(self):
        """TRACING_ENABLED='TRUE' (uppercase) triggers full setup."""
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {"TRACING_ENABLED": "TRUE"}

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", MagicMock()):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_trace.set_tracer_provider.assert_called_once()

    def test_configure_uses_resource_create(self):
        """Resource.create is called with service.name and service.version."""
        mock_resource = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "TRACING_SERVICE_NAME": "my-api",
            "API_VERSION": "3.0.0",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", MagicMock()):
                                with patch.object(tracing_module, "_Resource", mock_resource):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_resource.create.assert_called_once()
        resource_dict = mock_resource.create.call_args[0][0]
        assert resource_dict["service.name"] == "my-api"
        assert resource_dict["service.version"] == "3.0.0"


# ---------------------------------------------------------------------------
# Test: instrument_application()
# ---------------------------------------------------------------------------


class TestInstrumentApplication:
    """Tests for instrument_application()."""

    def test_returns_early_when_otel_not_available(self, capsys):
        """When OPENTELEMETRY_AVAILABLE=False, prints message and returns."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                result = tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert result is None
        assert "OpenTelemetry not available" in captured.out

    def test_returns_early_when_tracing_disabled(self):
        """TRACING_ENABLED=false causes early return."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", {"TRACING_ENABLED": "false"}, clear=False):
                result = tracing_module.instrument_application()

        assert result is None

    def test_instruments_core_libraries(self):
        """FastAPI, SQLAlchemy, Redis instrumentors are called."""
        mock_fastapi_inst = MagicMock()
        mock_sql_inst = MagicMock()
        mock_redis_inst = MagicMock()

        celery_mock = MagicMock()
        httpx_mock = MagicMock()

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", mock_fastapi_inst):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", mock_sql_inst):
                    with patch.object(tracing_module, "_RedisInstrumentor", mock_redis_inst):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": celery_mock,
                                    "opentelemetry.instrumentation.httpx": httpx_mock,
                                },
                            ):
                                tracing_module.instrument_application()

        mock_fastapi_inst.return_value.instrument.assert_called_once()
        mock_sql_inst.return_value.instrument.assert_called_once()
        mock_redis_inst.return_value.instrument.assert_called_once()

    def test_celery_instrumentation_success(self, capsys):
        """CeleryInstrumentor.instrument() is called and success message printed."""
        mock_celery_inst = MagicMock()
        celery_mod = MagicMock()
        celery_mod.CeleryInstrumentor = mock_celery_inst

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": celery_mod,
                                    "opentelemetry.instrumentation.httpx": MagicMock(),
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "Celery tracing instrumentation enabled" in captured.out

    def test_celery_import_error_handled(self, capsys):
        """ImportError for celery instrumentation is caught gracefully."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": None,  # causes ImportError
                                    "opentelemetry.instrumentation.httpx": MagicMock(),
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "Celery instrumentation not available" in captured.out

    def test_celery_general_exception_handled(self, capsys):
        """Non-ImportError exceptions during Celery setup are caught."""
        bad_celery = MagicMock()
        bad_celery.CeleryInstrumentor.side_effect = RuntimeError("crash!")

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": bad_celery,
                                    "opentelemetry.instrumentation.httpx": MagicMock(),
                                },
                            ):
                                tracing_module.instrument_application()  # must not raise

        captured = capsys.readouterr()
        assert "Failed to instrument Celery" in captured.out

    def test_httpx_instrumentation_success(self, capsys):
        """HTTPXClientInstrumentor.instrument() is called and success message printed."""
        mock_httpx_inst = MagicMock()
        httpx_mod = MagicMock()
        httpx_mod.HTTPXClientInstrumentor = mock_httpx_inst

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": MagicMock(),
                                    "opentelemetry.instrumentation.httpx": httpx_mod,
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "HTTPX client tracing instrumentation enabled" in captured.out

    def test_httpx_import_error_handled(self, capsys):
        """ImportError for HTTPX instrumentation is caught gracefully."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": MagicMock(),
                                    "opentelemetry.instrumentation.httpx": None,  # causes ImportError
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "HTTPX instrumentation not available" in captured.out

    def test_httpx_general_exception_handled(self, capsys):
        """Non-ImportError exceptions during HTTPX setup are caught."""
        bad_httpx = MagicMock()
        bad_httpx.HTTPXClientInstrumentor.side_effect = RuntimeError("crash!")

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": MagicMock(),
                                    "opentelemetry.instrumentation.httpx": bad_httpx,
                                },
                            ):
                                tracing_module.instrument_application()  # must not raise

        captured = capsys.readouterr()
        assert "Failed to instrument HTTPX" in captured.out


# ---------------------------------------------------------------------------
# Test: get_tracer()
# ---------------------------------------------------------------------------


class TestGetTracer:
    """Tests for get_tracer()."""

    def test_returns_none_when_otel_unavailable(self):
        """get_tracer() returns None when OPENTELEMETRY_AVAILABLE=False."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            result = tracing_module.get_tracer("my-component")

        assert result is None

    def test_returns_tracer_when_otel_available(self):
        """get_tracer() calls _trace.get_tracer() and returns its result."""
        mock_trace = MagicMock()
        expected_tracer = MagicMock()
        mock_trace.get_tracer.return_value = expected_tracer

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                result = tracing_module.get_tracer("my-component")

        assert result is expected_tracer
        mock_trace.get_tracer.assert_called_once_with("my-component")

    def test_returns_different_tracers_for_different_names(self):
        """Different component names produce different tracers."""
        mock_trace = MagicMock()
        tracer_a = MagicMock()
        tracer_b = MagicMock()
        mock_trace.get_tracer.side_effect = [tracer_a, tracer_b]

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                result_a = tracing_module.get_tracer("component-a")
                result_b = tracing_module.get_tracer("component-b")

        assert result_a is tracer_a
        assert result_b is tracer_b
        assert result_a is not result_b

    def test_get_tracer_with_empty_name(self):
        """get_tracer() works correctly with an empty string name."""
        mock_trace = MagicMock()
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                result = tracing_module.get_tracer("")

        assert result is mock_tracer
        mock_trace.get_tracer.assert_called_once_with("")
