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
            clear=True,
        ):
            # Mock all OpenTelemetry modules
            mock_opentelemetry = MagicMock()
            mock_trace = MagicMock()
            mock_sdk_trace = MagicMock()
            mock_export = MagicMock()
            mock_jaeger_exporter = MagicMock()
            mock_otlp_exporter = MagicMock()
            mock_resources = MagicMock()
            mock_fastapi_inst = MagicMock()
            mock_sqlalchemy_inst = MagicMock()
            mock_redis_inst = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": mock_opentelemetry,
                    "opentelemetry.trace": mock_trace,
                    "opentelemetry.sdk.trace": mock_sdk_trace,
                    "opentelemetry.sdk.trace.export": mock_export,
                    "opentelemetry.exporter.jaeger.thrift": mock_jaeger_exporter,
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_otlp_exporter,
                    "opentelemetry.sdk.resources": mock_resources,
                    "opentelemetry.instrumentation.fastapi": mock_fastapi_inst,
                    "opentelemetry.instrumentation.sqlalchemy": mock_sqlalchemy_inst,
                    "opentelemetry.instrumentation.redis": mock_redis_inst,
                },
                clear=True,
            ):
                mock_set_provider = MagicMock()
                mock_provider_class = MagicMock()
                mock_processor_class = MagicMock()
                mock_resource_create = MagicMock()

                mock_trace.set_tracer_provider = mock_set_provider
                mock_sdk_trace.TracerProvider = mock_provider_class
                mock_export.BatchSpanProcessor = mock_processor_class
                mock_resources.Resource.create = mock_resource_create

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

        with patch.dict("os.environ", {"TRACING_ENABLED": "true"}, clear=True):
            # Mock all OpenTelemetry modules
            mock_opentelemetry = MagicMock()
            mock_trace = MagicMock()
            mock_sdk_trace = MagicMock()
            mock_export = MagicMock()
            mock_jaeger_exporter = MagicMock()
            mock_otlp_exporter = MagicMock()
            mock_resources = MagicMock()
            mock_fastapi_inst = MagicMock()
            mock_sqlalchemy_inst = MagicMock()
            mock_redis_inst = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry": mock_opentelemetry,
                    "opentelemetry.trace": mock_trace,
                    "opentelemetry.sdk.trace": mock_export,
                    "opentelemetry.exporter.jaeger.thrift": mock_jaeger_exporter,
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_otlp_exporter,
                    "opentelemetry.sdk.resources": mock_resources,
                    "opentelemetry.instrumentation.fastapi": mock_fastapi_inst,
                    "opentelemetry.instrumentation.sqlalchemy": mock_sqlalchemy_inst,
                    "opentelemetry.instrumentation.redis": mock_redis_inst,
                },
                clear=True,
            ):
                mock_fastapi = MagicMock()
                mock_sql_class = MagicMock()
                mock_redis_class = MagicMock()

                mock_fastapi_inst.FastAPIInstrumentor = MagicMock()
                mock_fastapi_inst.FastAPIInstrumentor.instrument = mock_fastapi
                mock_sqlalchemy_inst.SQLAlchemyInstrumentor = mock_sql_class
                mock_redis_inst.RedisInstrumentor = mock_redis_class

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

        # Mock OpenTelemetry modules
        mock_opentelemetry = MagicMock()
        mock_trace = MagicMock()

        with patch.dict(
            "sys.modules",
            {"opentelemetry": mock_opentelemetry, "opentelemetry.trace": mock_trace},
            clear=True,
        ):
            mock_get_tracer = MagicMock()
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer
            mock_trace.get_tracer = mock_get_tracer

            result = get_tracer("test_component")

            assert result == mock_tracer
            mock_get_tracer.assert_called_once_with("test_component")

    def test_get_tracer_opentelemetry_not_available(self):
        """Test getting tracer when OpenTelemetry is not available."""
        from app.tracing import get_tracer

        with patch("app.tracing.OPENTELEMETRY_AVAILABLE", False):
            result = get_tracer("test_component")

            assert result is None
