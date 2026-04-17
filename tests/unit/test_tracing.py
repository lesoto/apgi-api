"""
Unit tests for app/tracing.py - OpenTelemetry distributed tracing configuration.

Tests the actual configure_distributed_tracing implementation and related utilities.
"""

from typing import Any
import os
import sys
import warnings
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

    def test_opentelemetry_available_flag_exists(self) -> None:
        """OPENTELEMETRY_AVAILABLE is a bool attribute on the module."""
        assert hasattr(tracing_module, "OPENTELEMETRY_AVAILABLE")
        assert isinstance(tracing_module.OPENTELEMETRY_AVAILABLE, bool)

    def test_module_has_all_public_functions(self) -> None:
        """All three public functions are defined."""
        assert callable(tracing_module.configure_distributed_tracing)
        assert callable(tracing_module.instrument_application)
        assert callable(tracing_module.get_tracer)

    def test_module_level_none_variables(self) -> None:
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

    def test_returns_early_when_otel_not_available(self, capsys: Any) -> None:
        """When OPENTELEMETRY_AVAILABLE=False, prints message and returns."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                tracing_module.configure_distributed_tracing()

        captured = capsys.readouterr()
        assert "OpenTelemetry not available" in captured.out

    def test_returns_early_when_tracing_disabled(self) -> None:
        """When TRACING_ENABLED=false, function returns None without error."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", {"TRACING_ENABLED": "false"}, clear=False):
                tracing_module.configure_distributed_tracing()

    def test_returns_early_when_tracing_not_set(self) -> None:
        """When TRACING_ENABLED is not set (defaults to 'false'), returns early."""
        env_without_tracing = {k: v for k, v in os.environ.items() if k != "TRACING_ENABLED"}
        env_without_tracing["TRACING_ENABLED"] = "false"
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", env_without_tracing, clear=True):
                tracing_module.configure_distributed_tracing()

    def test_configure_enabled_sets_mock_tracer_provider(self) -> None:
        """When enabled, set_tracer_provider is called once."""
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_ENDPOINT": "http://localhost:14268/api/mock_traces",
            "OTLP_ENDPOINT": "http://localhost:4317",
            "TRACING_SERVICE_NAME": "apgi-api",
            "API_VERSION": "1.0.0",
            "OTLP_INSECURE": "true",
            "OTLP_HEADERS": "",
        }

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

    def test_configure_adds_two_span_processors(self) -> None:
        """configure_distributed_tracing adds span processors for Jaeger and OTLP."""
        mock_trace = MagicMock()
        mock_provider_instance = MagicMock()
        mock_tracer_provider_cls = MagicMock(return_value=mock_provider_instance)
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider_instance

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_ENDPOINT": "http://jaeger:14268/api/mock_traces",
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

    def test_configure_with_custom_jaeger_credentials(self) -> None:
        """Custom Jaeger username/password are passed to the exporter."""
        mock_jaeger_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
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

        mock_jaeger_cls.assert_called_once()
        call_kwargs = mock_jaeger_cls.call_args[1]
        assert call_kwargs.get("username") == "myuser"
        assert call_kwargs.get("password") == "mypass"

    def test_configure_enabled_uppercase_true(self) -> None:
        """TRACING_ENABLED='TRUE' (uppercase) triggers full setup."""
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
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

    def test_configure_uses_resource_create(self) -> None:
        """Resource.create is called with service.name and service.version."""
        mock_resource = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
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
# Test: OpenTelemetry import failure (lines 39-59 in app/tracing.py)
# ---------------------------------------------------------------------------


def _make_otel_mocks() -> dict[str, MagicMock]:
    """Build a fresh set of sys.modules mocks for opentelemetry."""
    mocks = {}
    otel_modules = [
        "opentelemetry",
        "opentelemetry.mock_trace",
        "opentelemetry.sdk",
        "opentelemetry.sdk.mock_trace",
        "opentelemetry.sdk.mock_trace.export",
        "opentelemetry.sdk.resources",
        "opentelemetry.exporter",
        "opentelemetry.exporter.jaeger",
        "opentelemetry.exporter.jaeger.thrift",
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto",
        "opentelemetry.exporter.otlp.proto.grpc",
        "opentelemetry.exporter.otlp.proto.grpc.mock_trace_exporter",
        "opentelemetry.instrumentation",
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.sqlalchemy",
        "opentelemetry.instrumentation.redis",
        "opentelemetry.propagate",
        "opentelemetry.context",
    ]
    for name in otel_modules:
        m = MagicMock()
        mocks[name] = m
    return mocks


class TestOpenTelemetryImportFailure:
    """Tests for the except branch when OpenTelemetry imports fail (lines 39-59)."""

    def test_import_error_sets_unavailable(self) -> None:
        """When jaeger.thrift import fails, OPENTELEMETRY_AVAILABLE becomes False."""
        mocks = _make_otel_mocks()
        # Make jaeger.thrift raise ImportError when accessed
        mocks["opentelemetry.exporter.jaeger.thrift"] = None  # type: ignore[assignment]

        # Remove app.tracing from sys.modules so it gets re-imported
        sys.modules.pop("app.tracing", None)

        with patch.dict("sys.modules", mocks):
            import app.tracing as fresh_module

            result = fresh_module.OPENTELEMETRY_AVAILABLE

        # Restore
        sys.modules.pop("app.tracing", None)
        assert result is False

    def test_import_error_issues_warning(self) -> None:
        """When import fails, an ImportWarning is issued."""
        mocks = _make_otel_mocks()
        mocks["opentelemetry.exporter.jaeger.thrift"] = None  # type: ignore[assignment]

        sys.modules.pop("app.tracing", None)

        with patch.dict("sys.modules", mocks):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                import app.tracing  # noqa: F401

        sys.modules.pop("app.tracing", None)

        import_warnings = [w for w in caught if issubclass(w.category, ImportWarning)]
        assert any("OpenTelemetry not available" in str(w.message) for w in import_warnings)

    def test_import_error_leaves_jaeger_exporter_none(self, capsys: Any) -> None:
        """When jaeger.thrift import fails, _JaegerExporter remains None and OPENTELEMETRY_AVAILABLE is False."""
        mocks = _make_otel_mocks()
        mocks["opentelemetry.exporter.jaeger.thrift"] = None  # type: ignore[assignment]

        sys.modules.pop("app.tracing", None)

        with patch.dict("sys.modules", mocks):
            import app.tracing as fresh_module

        sys.modules.pop("app.tracing", None)

        # The import of JaegerExporter fails, so it stays None
        assert fresh_module._JaegerExporter is None
        # And the module is marked unavailable
        assert fresh_module.OPENTELEMETRY_AVAILABLE is False

    def test_type_error_sets_unavailable(self) -> None:
        """When TypeError occurs (Python 3.14 compat), OPENTELEMETRY_AVAILABLE becomes False."""
        mocks = _make_otel_mocks()

        # Create a custom class that raises TypeError when JaegerExporter is accessed
        class BadJaegerModule:
            def __getattr__(self, name: str) -> Any:
                if name == "JaegerExporter":
                    raise TypeError("compat")
                return MagicMock()

        mocks["opentelemetry.exporter.jaeger.thrift"] = BadJaegerModule()  # type: ignore[assignment]

        sys.modules.pop("app.tracing", None)

        with patch.dict("sys.modules", mocks):
            import app.tracing as fresh_module

        sys.modules.pop("app.tracing", None)
        assert fresh_module.OPENTELEMETRY_AVAILABLE is False


# ---------------------------------------------------------------------------
# Test: instrument_application()
# ---------------------------------------------------------------------------


class TestInstrumentApplication:
    """Tests for instrument_application()."""

    def test_returns_early_when_otel_not_available(self, capsys: Any) -> None:
        """When OPENTELEMETRY_AVAILABLE=False, prints message and returns."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "OpenTelemetry not available" in captured.out

    def test_returns_early_when_tracing_disabled(self) -> None:
        """TRACING_ENABLED=false causes early return."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", {"TRACING_ENABLED": "false"}, clear=False):
                tracing_module.instrument_application()

    def test_instruments_core_libraries(self) -> None:
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

    def test_celery_instrumentation_success(self, capsys: Any) -> None:
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

    def test_celery_import_error_handled(self, capsys: Any) -> None:
        """ImportError for celery instrumentation is caught gracefully."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", MagicMock()):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", MagicMock()):
                    with patch.object(tracing_module, "_RedisInstrumentor", MagicMock()):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": None,
                                    "opentelemetry.instrumentation.httpx": MagicMock(),
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "Celery instrumentation not available" in captured.out

    def test_celery_general_exception_handled(self, capsys: Any) -> None:
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
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "Failed to instrument Celery" in captured.out

    def test_httpx_instrumentation_success(self, capsys: Any) -> None:
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

    def test_httpx_import_error_handled(self, capsys: Any) -> None:
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
                                    "opentelemetry.instrumentation.httpx": None,
                                },
                            ):
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "HTTPX instrumentation not available" in captured.out

    def test_httpx_general_exception_handled(self, capsys: Any) -> None:
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
                                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "Failed to instrument HTTPX" in captured.out


# ---------------------------------------------------------------------------
# Test: get_tracer()
# ---------------------------------------------------------------------------


class TestGetTracer:
    """Tests for get_tracer()."""

    def test_returns_none_when_otel_unavailable(self) -> None:
        """get_tracer() returns None when OPENTELEMETRY_AVAILABLE=False."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            result = tracing_module.get_tracer("my-component")

        assert result is None

    def test_returns_mock_tracer_when_otel_available(self) -> None:
        """get_tracer() calls _trace.get_tracer() and returns its result."""
        mock_trace = MagicMock()
        expected_tracer = MagicMock()
        mock_trace.get_tracer.return_value = expected_tracer

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                result = tracing_module.get_tracer("my-component")

        assert result is expected_tracer
        mock_trace.get_tracer.assert_called_once_with("my-component")

    def test_returns_different_mock_tracers_for_different_names(self) -> None:
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

    def test_get_tracer_with_empty_name(self) -> None:
        """get_tracer() works correctly with an empty string name."""
        mock_trace = MagicMock()
        tracer = MagicMock()
        mock_trace.get_tracer.return_value = tracer

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                result = tracing_module.get_tracer("")

        assert result is tracer
        mock_trace.get_tracer.assert_called_once_with("")


# ---------------------------------------------------------------------------
# Additional comprehensive tests for edge cases and initialization paths
# ---------------------------------------------------------------------------


class TestConfigurationEdgeCases:
    """Tests for edge cases in configuration."""

    def test_configure_with_missing_env_vars_uses_defaults(self) -> None:
        """Missing env vars use sensible defaults."""
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {"TRACING_ENABLED": "true"}

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

    def test_configure_with_otlp_insecure_false(self) -> None:
        """OTLP_INSECURE=false is passed correctly to exporter."""
        mock_otlp_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "OTLP_INSECURE": "false",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", mock_otlp_cls):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_otlp_cls.assert_called_once()
        call_kwargs = mock_otlp_cls.call_args[1]
        assert call_kwargs.get("insecure") is False

    def test_configure_with_otlp_headers(self) -> None:
        """OTLP_HEADERS are passed to the exporter."""
        mock_otlp_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "OTLP_HEADERS": "Authorization=Bearer token123",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", mock_otlp_cls):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_otlp_cls.assert_called_once()
        call_kwargs = mock_otlp_cls.call_args[1]
        assert call_kwargs.get("headers") == "Authorization=Bearer token123"

    def test_configure_with_custom_jaeger_endpoint(self) -> None:
        """Custom JAEGER_ENDPOINT is passed to the exporter."""
        mock_jaeger_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "JAEGER_ENDPOINT": "http://custom-jaeger:14268/api/traces",
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

        mock_jaeger_cls.assert_called_once()
        call_kwargs = mock_jaeger_cls.call_args[1]
        assert call_kwargs.get("collector_endpoint") == "http://custom-jaeger:14268/api/traces"

    def test_configure_with_custom_otlp_endpoint(self) -> None:
        """Custom OTLP_ENDPOINT is passed to the exporter."""
        mock_otlp_cls = MagicMock()
        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_trace.set_tracer_provider = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_provider

        env = {
            "TRACING_ENABLED": "true",
            "OTLP_ENDPOINT": "http://custom-otlp:4317",
        }

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_trace", mock_trace):
                with patch.object(
                    tracing_module, "_TracerProvider", MagicMock(return_value=mock_provider)
                ):
                    with patch.object(tracing_module, "_BatchSpanProcessor", MagicMock()):
                        with patch.object(tracing_module, "_JaegerExporter", MagicMock()):
                            with patch.object(tracing_module, "_OTLPSpanExporter", mock_otlp_cls):
                                with patch.object(tracing_module, "_Resource", MagicMock()):
                                    with patch.dict("os.environ", env, clear=True):
                                        tracing_module.configure_distributed_tracing()

        mock_otlp_cls.assert_called_once()
        call_kwargs = mock_otlp_cls.call_args[1]
        assert call_kwargs.get("endpoint") == "http://custom-otlp:4317"


class TestInstrumentationEdgeCases:
    """Tests for edge cases in instrumentation."""

    def test_instrument_with_all_modules_available(self) -> None:
        """All instrumentation modules are called when available."""
        mock_fastapi = MagicMock()
        mock_sqlalchemy = MagicMock()
        mock_redis = MagicMock()
        mock_celery = MagicMock()
        mock_httpx = MagicMock()

        celery_mod = MagicMock()
        celery_mod.CeleryInstrumentor = mock_celery
        httpx_mod = MagicMock()
        httpx_mod.HTTPXClientInstrumentor = mock_httpx

        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing_module, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing_module, "_SQLAlchemyInstrumentor", mock_sqlalchemy):
                    with patch.object(tracing_module, "_RedisInstrumentor", mock_redis):
                        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                            with patch.dict(
                                "sys.modules",
                                {
                                    "opentelemetry.instrumentation.celery": celery_mod,
                                    "opentelemetry.instrumentation.httpx": httpx_mod,
                                },
                            ):
                                tracing_module.instrument_application()

        mock_fastapi.return_value.instrument.assert_called_once()
        mock_sqlalchemy.return_value.instrument.assert_called_once()
        mock_redis.return_value.instrument.assert_called_once()
        mock_celery.return_value.instrument.assert_called_once()
        mock_httpx.return_value.instrument.assert_called_once()

    def test_instrument_returns_early_when_otel_unavailable(self, capsys: Any) -> None:
        """instrument_application returns early when OPENTELEMETRY_AVAILABLE=False."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", False):
            with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=False):
                tracing_module.instrument_application()

        captured = capsys.readouterr()
        assert "OpenTelemetry not available" in captured.out

    def test_instrument_returns_early_when_tracing_disabled(self) -> None:
        """instrument_application returns early when TRACING_ENABLED=false."""
        with patch.object(tracing_module, "OPENTELEMETRY_AVAILABLE", True):
            with patch.dict("os.environ", {"TRACING_ENABLED": "false"}, clear=False):
                tracing_module.instrument_application()
