"""
Unit tests for tracing configuration.

Tests OpenTelemetry distributed tracing setup and instrumentation.
"""

from unittest.mock import patch, MagicMock

# Remove the top import
# from app.tracing import configure_distributed_tracing, instrument_application, get_tracer


class TestTracingConfiguration:
    """Test tracing configuration functionality."""

    def test_configure_distributed_tracing_disabled(self):
        """Test that tracing configuration does nothing when disabled."""
        from app.tracing import configure_distributed_tracing

        with patch.dict("os.environ", {"TRACING_ENABLED": "false"}):
            # Should not raise any exceptions
            configure_distributed_tracing()

    def test_configure_distributed_tracing_enabled_opentelemetry_available(self):
        """Test tracing configuration when enabled and OpenTelemetry is available."""
        from app.tracing import configure_distributed_tracing

        with patch.dict(
            "os.environ",
            {
                "TRACING_ENABLED": "true",
                "JAEGER_ENDPOINT": "http://localhost:14268/api/traces",
                "OTLP_ENDPOINT": "http://localhost:4317",
                "TRACING_SERVICE_NAME": "test-service",
                "API_VERSION": "1.0.0",
            },
        ):
            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": MagicMock(),
                    "opentelemetry.trace": MagicMock(),
                    "opentelemetry.sdk.trace": MagicMock(),
                    "opentelemetry.sdk.trace.export": MagicMock(),
                    "opentelemetry.exporter.jaeger.thrift": MagicMock(),
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
                    "opentelemetry.sdk.resources": MagicMock(),
                    "opentelemetry.instrumentation.fastapi": MagicMock(),
                    "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
                    "opentelemetry.instrumentation.redis": MagicMock(),
                },
            ), patch("app.tracing.OPENTELEMETRY_AVAILABLE", True), patch(
                "opentelemetry.trace.set_tracer_provider"
            ) as mock_set_provider, patch(
                "opentelemetry.sdk.trace.TracerProvider"
            ) as mock_provider_class, patch(
                "opentelemetry.sdk.trace.export.BatchSpanProcessor"
            ) as mock_processor_class, patch(
                "opentelemetry.sdk.resources.Resource.create"
            ) as mock_resource_create:
                mock_provider = MagicMock()
                mock_provider_class.return_value = mock_provider

                configure_distributed_tracing()

                mock_set_provider.assert_called_once()
                mock_provider_class.assert_called_once()
                mock_processor_class.assert_called()  # Called twice for Jaeger and OTLP

    def test_configure_distributed_tracing_opentelemetry_not_available(self):
        """Test tracing configuration when OpenTelemetry is not available."""
        from app.tracing import configure_distributed_tracing

        with patch("app.tracing.OPENTELEMETRY_AVAILABLE", False):
            # Should not raise any exceptions
            configure_distributed_tracing()

    def test_instrument_application_disabled(self):
        """Test that application instrumentation does nothing when disabled."""
        from app.tracing import instrument_application

        with patch.dict("os.environ", {"TRACING_ENABLED": "false"}):
            # Should not raise any exceptions
            instrument_application()

    def test_instrument_application_enabled_opentelemetry_available(self):
        """Test application instrumentation when enabled and OpenTelemetry is available."""
        from app.tracing import instrument_application

        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}):
            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": MagicMock(),
                    "opentelemetry.trace": MagicMock(),
                    "opentelemetry.sdk.trace": MagicMock(),
                    "opentelemetry.sdk.trace.export": MagicMock(),
                    "opentelemetry.exporter.jaeger.thrift": MagicMock(),
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
                    "opentelemetry.sdk.resources": MagicMock(),
                    "opentelemetry.instrumentation.fastapi": MagicMock(),
                    "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
                    "opentelemetry.instrumentation.redis": MagicMock(),
                },
            ), patch("app.tracing.OPENTELEMETRY_AVAILABLE", True), patch(
                "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument"
            ) as mock_fastapi, patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sql_class, patch(
                "opentelemetry.instrumentation.redis.RedisInstrumentor"
            ) as mock_redis_class:
                mock_sql_instance = MagicMock()
                mock_sql_class.return_value = mock_sql_instance
                mock_redis_instance = MagicMock()
                mock_redis_class.return_value = mock_redis_instance

                instrument_application()

                mock_fastapi.assert_called_once()
                mock_sql_instance.instrument.assert_called_once()
                mock_redis_instance.instrument.assert_called_once()

    def test_instrument_application_opentelemetry_not_available(self):
        """Test application instrumentation when OpenTelemetry is not available."""
        from app.tracing import instrument_application

        with patch("app.tracing.OPENTELEMETRY_AVAILABLE", False):
            # Should not raise any exceptions
            instrument_application()

    def test_get_tracer_opentelemetry_available(self):
        """Test getting tracer when OpenTelemetry is available."""
        from app.tracing import get_tracer

        with patch("app.tracing.OPENTELEMETRY_AVAILABLE", True), patch(
            "opentelemetry.trace.get_tracer"
        ) as mock_get_tracer:
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            result = get_tracer("test_component")

            assert result == mock_tracer
            mock_get_tracer.assert_called_once_with("test_component")

    def test_get_tracer_opentelemetry_not_available(self):
        """Test getting tracer when OpenTelemetry is not available."""
        from app.tracing import get_tracer

        with patch("app.tracing.OPENTELEMETRY_AVAILABLE", False):
            result = get_tracer("test_component")

            assert result is None
