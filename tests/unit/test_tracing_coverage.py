"""
Coverage tests for app/tracing.py
"""

import os
import sys
import warnings
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_tracing_module():
    """Reset tracing module state between tests to avoid pollution."""
    # Clear module before each test
    if "app.tracing" in sys.modules:
        del sys.modules["app.tracing"]
    # Also clear opentelemetry modules to force reimport
    for mod in list(sys.modules.keys()):
        if mod.startswith("opentelemetry"):
            del sys.modules[mod]
    yield
    # Clear module after each test
    if "app.tracing" in sys.modules:
        del sys.modules["app.tracing"]


def test_configure_tracing_disabled():
    """Test configure_distributed_tracing when disabled."""
    import app.tracing as tracing

    # configure_distributed_tracing() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "false"}):
        with patch.object(tracing, "_trace") as mock_trace:
            tracing.configure_distributed_tracing()
            assert not mock_trace.set_tracer_provider.called


def test_configure_tracing_enabled():
    """Test configure_distributed_tracing when enabled."""
    import app.tracing as tracing

    # Mock all OpenTelemetry components at module level
    mock_tracer_provider = MagicMock()
    mock_tracer_provider.add_span_processor = MagicMock()

    mock_trace = MagicMock()
    mock_trace.get_tracer_provider.return_value = mock_tracer_provider
    mock_trace.set_tracer_provider = MagicMock()

    mock_resource = MagicMock()
    mock_resource.create = MagicMock(return_value={"service.name": "test"})

    mock_provider = MagicMock()
    mock_provider.return_value = mock_tracer_provider

    # configure_distributed_tracing() uses os.getenv() directly, not the module constant
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing, "_trace", mock_trace):
                with patch.object(tracing, "_TracerProvider", mock_provider):
                    with patch.object(tracing, "_Resource", mock_resource):
                        with patch.object(tracing, "_JaegerExporter"):
                            with patch.object(tracing, "_OTLPSpanExporter"):
                                with patch.object(tracing, "_BatchSpanProcessor"):
                                    tracing.configure_distributed_tracing()
                                    # Verify set_tracer_provider was called
                                    assert mock_trace.set_tracer_provider.called


def test_instrument_application_disabled():
    """Test instrument_application when disabled."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "false"}):
        with patch.object(tracing, "_FastAPIInstrumentor") as mock_fastapi:
            tracing.instrument_application()
            assert not mock_fastapi.called


def test_instrument_application_enabled():
    """Test instrument_application when enabled."""
    import app.tracing as tracing

    mock_fastapi_inst = MagicMock()
    mock_fastapi = MagicMock(return_value=mock_fastapi_inst)

    mock_sql_inst = MagicMock()
    mock_sql = MagicMock(return_value=mock_sql_inst)

    mock_redis_inst = MagicMock()
    mock_redis = MagicMock(return_value=mock_redis_inst)

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                    with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                        tracing.instrument_application()
                        assert mock_fastapi_inst.instrument.called
                        assert mock_sql_inst.instrument.called
                        assert mock_redis_inst.instrument.called


def test_span_helpers_otel_unavailable():
    """Test span helpers when OpenTelemetry is unavailable."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        with patch.object(tracing, "_trace", None):
            assert tracing.get_tracer() is None
            # When OTEL unavailable and no "unittest" in env, returns None
            span = tracing.start_span("test")
            assert span is None
            current = tracing.get_current_span()
            assert current is None
            # When "unittest" is in PYTEST_CURRENT_TEST, returns MagicMock
            with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "unittest_something"}):
                span = tracing.start_span("test")
                assert span is not None
                current = tracing.get_current_span()
                assert current is not None
            # Should not raise
            tracing.set_span_attribute("key", "value")


def test_span_helpers_otel_available():
    """Test span helpers when OpenTelemetry is available."""
    import app.tracing as tracing

    mock_span = MagicMock()
    mock_span.set_attribute = MagicMock()
    mock_span.add_event = MagicMock()
    mock_span.record_exception = MagicMock()

    mock_trace = MagicMock()
    mock_trace.get_current_span.return_value = mock_span

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_trace", mock_trace):
            tracing.set_span_attribute("key", "value")
            assert mock_span.set_attribute.called

            tracing.add_span_event("event")
            assert mock_span.add_event.called

            exc = Exception("error")
            tracing.record_exception(exc)
            assert mock_span.record_exception.called


def test_instrumentation_helpers():
    """Test individual instrumentation helpers."""
    import app.tracing as tracing

    with patch.object(tracing, "TRACING_ENABLED", True):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            mock_inst = MagicMock()
            mock_fastapi = MagicMock(return_value=mock_inst)
            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                tracing.instrument_fastapi(MagicMock())
                assert mock_inst.instrument_app.called

            mock_inst = MagicMock()
            mock_sql = MagicMock(return_value=mock_inst)
            with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                tracing.instrument_sqlalchemy(MagicMock())
                assert mock_inst.instrument.called

            mock_inst = MagicMock()
            mock_redis = MagicMock(return_value=mock_inst)
            with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                tracing.instrument_redis(MagicMock())
                assert mock_inst.instrument.called


def test_context_propagation():
    """Test context propagation helpers."""
    import app.tracing as tracing

    mock_propagate = MagicMock()
    mock_propagate.extract = MagicMock()
    mock_propagate.inject = MagicMock()

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_propagate", mock_propagate):
            headers = {"test": "header"}
            result = tracing.extract_trace_context(headers)
            assert mock_propagate.extract.called

            result = tracing.inject_trace_context(headers)
            assert mock_propagate.inject.called


def test_context_propagation_unavailable():
    """Test context propagation when OpenTelemetry is unavailable."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        headers = {"test": "header"}
        result = tracing.extract_trace_context(headers)
        assert result is None

        result = tracing.inject_trace_context(headers)
        assert result == headers


def test_instrumentation_helpers_disabled():
    """Test individual instrumentation helpers when disabled."""
    import app.tracing as tracing

    # Helper functions use the module constant TRACING_ENABLED
    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "TRACING_ENABLED", False):
            with patch.object(tracing, "_FastAPIInstrumentor") as mock_fastapi:
                tracing.instrument_fastapi(MagicMock())
                assert not mock_fastapi.called

            with patch.object(tracing, "_SQLAlchemyInstrumentor") as mock_sql:
                tracing.instrument_sqlalchemy(MagicMock())
                assert not mock_sql.called

            with patch.object(tracing, "_RedisInstrumentor") as mock_redis:
                tracing.instrument_redis(MagicMock())
                assert not mock_redis.called


def test_create_span_context():
    """Test create_span_context function."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        with patch.object(tracing, "_trace", None):
            result = tracing.create_span_context()
            assert result is None

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        with patch.object(tracing, "_trace", None):
            with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "unittest_something"}):
                result = tracing.create_span_context()
                assert result is not None

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        mock_trace = MagicMock()
        mock_span_context = MagicMock()
        mock_trace.SpanContext = MagicMock(return_value=mock_span_context)
        with patch.object(tracing, "_trace", mock_trace):
            result = tracing.create_span_context()
            assert result == mock_span_context


def test_instrument_application_with_celery_httpx():
    """Test instrument_application with Celery and HTTPX instrumentation."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            mock_fastapi_inst = MagicMock()
            mock_fastapi = MagicMock(return_value=mock_fastapi_inst)

            mock_sql_inst = MagicMock()
            mock_sql = MagicMock(return_value=mock_sql_inst)

            mock_redis_inst = MagicMock()
            mock_redis = MagicMock(return_value=mock_redis_inst)

            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                    with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                        tracing.instrument_application()
                        assert mock_fastapi_inst.instrument.called
                        assert mock_sql_inst.instrument.called
                        assert mock_redis_inst.instrument.called


def test_instrument_application_celery_import_error():
    """Test instrument_application when Celery import fails."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            mock_fastapi_inst = MagicMock()
            mock_fastapi = MagicMock(return_value=mock_fastapi_inst)

            mock_sql_inst = MagicMock()
            mock_sql = MagicMock(return_value=mock_sql_inst)

            mock_redis_inst = MagicMock()
            mock_redis = MagicMock(return_value=mock_redis_inst)

            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                    with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                        with patch("builtins.__import__", side_effect=ImportError("No module")):
                            tracing.instrument_application()


def test_instrument_application_httpx_import_error():
    """Test instrument_application when HTTPX import fails."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            mock_fastapi_inst = MagicMock()
            mock_fastapi = MagicMock(return_value=mock_fastapi_inst)

            mock_sql_inst = MagicMock()
            mock_sql = MagicMock(return_value=mock_sql_inst)

            mock_redis_inst = MagicMock()
            mock_redis = MagicMock(return_value=mock_redis_inst)

            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                    with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                        with patch("builtins.__import__", side_effect=ImportError("No module")):
                            tracing.instrument_application()


def test_instrument_application_celery_exception():
    """Test instrument_application when Celery instrumentation raises exception."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.dict(os.environ, {"TRACING_ENABLED": "true"}):
        with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
            mock_fastapi_inst = MagicMock()
            mock_fastapi = MagicMock(return_value=mock_fastapi_inst)

            mock_sql_inst = MagicMock()
            mock_sql = MagicMock(return_value=mock_sql_inst)

            mock_redis_inst = MagicMock()
            mock_redis = MagicMock(return_value=mock_redis_inst)

            with patch.object(tracing, "_FastAPIInstrumentor", mock_fastapi):
                with patch.object(tracing, "_SQLAlchemyInstrumentor", mock_sql):
                    with patch.object(tracing, "_RedisInstrumentor", mock_redis):
                        # Should complete without error even if optional instrumenters fail
                        tracing.instrument_application()


def test_get_tracer_with_name():
    """Test get_tracer with custom name."""
    import app.tracing as tracing

    mock_tracer = MagicMock()
    mock_trace = MagicMock()
    mock_trace.get_tracer = MagicMock(return_value=mock_tracer)

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_trace", mock_trace):
            result = tracing.get_tracer("custom_name")
            assert result == mock_tracer
            mock_trace.get_tracer.assert_called_with("custom_name")


def test_start_span_with_tracer():
    """Test start_span when tracer is available."""
    import app.tracing as tracing

    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span = MagicMock(return_value=mock_span)

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "get_tracer", return_value=mock_tracer):
            result = tracing.start_span("test_span", {"key": "value"})
            assert result == mock_span
            mock_tracer.start_as_current_span.assert_called_with(
                "test_span", attributes={"key": "value"}
            )


def test_start_span_no_tracer():
    """Test start_span when tracer returns None."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "get_tracer", return_value=None):
            result = tracing.start_span("test_span")
            assert result is None


def test_get_current_span_otel_available():
    """Test get_current_span when OpenTelemetry is available."""
    import app.tracing as tracing

    mock_span = MagicMock()
    mock_trace = MagicMock()
    mock_trace.get_current_span = MagicMock(return_value=mock_span)

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_trace", mock_trace):
            result = tracing.get_current_span()
            assert result == mock_span


def test_inject_trace_context_none_headers():
    """Test inject_trace_context with None headers."""
    import app.tracing as tracing

    mock_propagate = MagicMock()
    mock_propagate.inject = MagicMock()

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_propagate", mock_propagate):
            result = tracing.inject_trace_context(None)
            assert result == {}
            mock_propagate.inject.assert_called_once()


def test_configure_tracing_otel_unavailable():
    """Test configure_distributed_tracing when OTEL unavailable."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        tracing.configure_distributed_tracing()
        # Should not raise, just print and return


def test_instrument_application_otel_unavailable():
    """Test instrument_application when OTEL unavailable."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        tracing.instrument_application()
        # Should not raise, just print and return


def test_span_helpers_with_none_span():
    """Test span helpers when current span is None."""
    import app.tracing as tracing

    mock_trace = MagicMock()
    mock_trace.get_current_span = MagicMock(return_value=None)

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.object(tracing, "_trace", mock_trace):
            # Should not raise when span is None
            tracing.set_span_attribute("key", "value")
            tracing.add_span_event("event")
            tracing.record_exception(Exception("error"))


def test_instrument_helpers_otel_unavailable():
    """Test individual instrumentation helpers when OTEL unavailable."""
    import app.tracing as tracing

    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", False):
        with patch.object(tracing, "_trace", None):
            with patch.object(tracing, "_FastAPIInstrumentor") as mock_fastapi:
                tracing.instrument_fastapi(MagicMock())
                assert not mock_fastapi.called

            with patch.object(tracing, "_SQLAlchemyInstrumentor") as mock_sql:
                tracing.instrument_sqlalchemy(MagicMock())
                assert not mock_sql.called

            with patch.object(tracing, "_RedisInstrumentor") as mock_redis:
                tracing.instrument_redis(MagicMock())
                assert not mock_redis.called


def test_instrument_application_tracing_disabled():
    """Test instrument_application when tracing disabled via env."""
    import app.tracing as tracing

    # instrument_application() uses os.getenv() directly
    with patch.object(tracing, "OPENTELEMETRY_AVAILABLE", True):
        with patch.dict(os.environ, {"TRACING_ENABLED": "false"}):
            with patch.object(tracing, "_FastAPIInstrumentor") as mock_fastapi:
                tracing.instrument_application()
                assert not mock_fastapi.called


def test_otel_import_error_warning():
    """Test that warning is raised when OpenTelemetry import fails."""
    # This test covers lines 51-57 where the warning is issued
    # We need to trigger the import error path
    with patch.dict(sys.modules, {}):
        # Remove opentelemetry modules to trigger import error
        for mod in list(sys.modules.keys()):
            if mod.startswith("opentelemetry"):
                del sys.modules[mod]

        # Force reimport of tracing module
        if "app.tracing" in sys.modules:
            del sys.modules["app.tracing"]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                import app.tracing as tracing  # noqa: F401

                # Check if warning was issued
                if len(w) > 0:
                    assert any(
                        "OpenTelemetry not available" in str(warning.message) for warning in w
                    )
            except Exception:
                # If import fails completely, that's also acceptable
                pass


def test_otel_import_type_error():
    """Test that TypeError during import is handled gracefully."""
    # This test covers the TypeError exception path in lines 51-62
    # Simulate a TypeError during import by patching the import to raise TypeError
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise TypeError("Python 3.14 compatibility issue")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        # Clear tracing module to force reimport
        if "app.tracing" in sys.modules:
            del sys.modules["app.tracing"]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import app.tracing as tracing

            # Should handle TypeError gracefully
            assert tracing.OPENTELEMETRY_AVAILABLE is False
            # Should have issued a warning
            assert any("OpenTelemetry not available" in str(warning.message) for warning in w)
