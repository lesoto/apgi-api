"""
Tests for tracing middleware.

Tests for distributed tracing configuration and instrumentation.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock OpenTelemetry before importing
sys.modules["opentelemetry"] = MagicMock()
sys.modules["opentelemetry.trace"] = MagicMock()
sys.modules["opentelemetry.sdk.trace"] = MagicMock()
sys.modules["opentelemetry.sdk.trace.export"] = MagicMock()
sys.modules["opentelemetry.sdk.resources"] = MagicMock()
sys.modules["opentelemetry.instrumentation"] = MagicMock()
sys.modules["opentelemetry.instrumentation.fastapi"] = MagicMock()
sys.modules["opentelemetry.instrumentation.sqlalchemy"] = MagicMock()
sys.modules["opentelemetry.instrumentation.redis"] = MagicMock()
sys.modules["opentelemetry.exporter.jaeger.thrift"] = MagicMock()
sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = MagicMock()

from app.middleware.tracing import (
    configure_distributed_tracing,
    _server_request_hook,
    _client_request_hook,
    _client_response_hook,
    instrument_application,
)


class TestConfigureDistributedTracing:
    """Tests for configure_distributed_tracing function."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", False)
    def test_configure_when_opentelemetry_not_available(self):
        """Test that configuration is skipped when OpenTelemetry is not available."""
        configure_distributed_tracing()
        # Should not raise any error and should return early

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    def test_configure_with_console_exporter(
        self,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with console exporter enabled."""
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()

        configure_distributed_tracing(
            enable_console_exporter=True,
            service_name="test-service",
            service_version="2.0.0",
        )

        # Verify resource was created with correct attributes
        mock_resource.create.assert_called_once()
        call_args = mock_resource.create.call_args[0][0]
        assert "service_name" in call_args or "SERVICE_NAME" in str(call_args)

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.JaegerExporter")
    def test_configure_with_jaeger_exporter(
        self,
        mock_jaeger_exporter,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with Jaeger exporter."""
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()
        mock_jaeger_exporter.return_value = MagicMock()

        configure_distributed_tracing(
            jaeger_endpoint="localhost:6831",
            service_name="test-service",
        )

        # Verify Jaeger exporter was created
        mock_jaeger_exporter.assert_called_once()
        call_kwargs = mock_jaeger_exporter.call_args[1]
        assert "agent_host_name" in call_kwargs
        assert "agent_port" in call_kwargs

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.OTLPSpanExporter")
    def test_configure_with_otlp_exporter(
        self,
        mock_otlp_exporter,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with OTLP exporter."""
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()
        mock_otlp_exporter.return_value = MagicMock()

        configure_distributed_tracing(
            otlp_endpoint="localhost:4317",
            service_name="test-service",
        )

        # Verify OTLP exporter was created
        mock_otlp_exporter.assert_called_once()
        call_kwargs = mock_otlp_exporter.call_args[1]
        assert "endpoint" in call_kwargs
        assert "insecure" in call_kwargs

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    def test_configure_with_custom_sampling_rate(
        self,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with custom sampling rate."""
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()

        configure_distributed_tracing(
            sampling_rate=0.5,
            service_name="test-service",
        )

        # Configuration should succeed with custom sampling rate
        mock_resource.create.assert_called_once()

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.logger")
    def test_configure_with_exception(
        self,
        mock_logger,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test that exceptions are logged and re-raised."""
        mock_resource.create.side_effect = Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            configure_distributed_tracing()

        mock_logger.error.assert_called_once()


class TestServerRequestHook:
    """Tests for _server_request_hook function."""

    def test_hook_with_route_info(self):
        """Test hook adds route information to span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock()
        mock_scope.get.return_value = MagicMock(path="/test/path")

        _server_request_hook(mock_span, mock_scope)

        mock_span.set_attribute.assert_called()
        call_args = mock_span.set_attribute.call_args
        assert "http.route" in str(call_args)

    def test_hook_with_user_info(self):
        """Test hook adds user information to span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.username = "testuser"
        mock_scope = MagicMock()
        mock_scope.get.side_effect = [None, mock_user]

        _server_request_hook(mock_span, mock_scope)

        # Should set user attributes
        assert mock_span.set_attribute.call_count >= 2

    def test_hook_when_span_not_recording(self):
        """Test hook does nothing when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False
        mock_scope = MagicMock()

        _server_request_hook(mock_span, mock_scope)

        mock_span.set_attribute.assert_not_called()

    def test_hook_with_no_scope_get(self):
        """Test hook handles scope without get method."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock(spec=[])

        _server_request_hook(mock_span, mock_scope)

        # Should not raise error
        mock_span.set_attribute.assert_not_called()


class TestClientRequestHook:
    """Tests for _client_request_hook function."""

    def test_hook_adds_method_and_url(self):
        """Test hook adds HTTP method and URL to span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        _client_request_hook(mock_span, "GET", "http://example.com")

        assert mock_span.set_attribute.call_count == 2

    def test_hook_when_span_not_recording(self):
        """Test hook does nothing when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        _client_request_hook(mock_span, "GET", "http://example.com")

        mock_span.set_attribute.assert_not_called()


class TestClientResponseHook:
    """Tests for _client_response_hook function."""

    def test_hook_adds_response_complete(self):
        """Test hook marks response as complete."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        _client_response_hook(mock_span, {}, "body")

        mock_span.set_attribute.assert_called_once_with("http.response_complete", True)

    def test_hook_when_span_not_recording(self):
        """Test hook does nothing when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        _client_response_hook(mock_span, {}, "body")

        mock_span.set_attribute.assert_not_called()


class TestInstrumentApplication:
    """Tests for instrument_application function."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", False)
    @patch("app.middleware.tracing.logger")
    def test_instrument_when_opentelemetry_not_available(self, mock_logger):
        """Test instrumentation is skipped when OpenTelemetry is not available."""
        instrument_application()
        mock_logger.warning.assert_called_once()

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.settings")
    @patch("app.middleware.tracing.logger")
    def test_instrument_with_settings(self, mock_configure, mock_settings, mock_logger):
        """Test instrumentation uses settings."""
        mock_settings.tracing_service_name = "api-service"
        mock_settings.tracing_service_version = "1.0.0"
        mock_settings.jaeger_endpoint = "localhost:6831"
        mock_settings.otlp_endpoint = None
        mock_settings.tracing_console_exporter = False
        mock_settings.tracing_sampling_rate = 1.0

        instrument_application()

        mock_configure.assert_called_once()
        call_kwargs = mock_configure.call_args[1]
        assert call_kwargs["service_name"] == "api-service"
        assert call_kwargs["service_version"] == "1.0.0"

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.settings")
    @patch("app.middleware.tracing.logger")
    def test_instrument_handles_import_error(self, mock_logger, mock_settings, mock_configure):
        """Test instrumentation handles ImportError gracefully."""
        mock_configure.side_effect = ImportError("Module not found")

        instrument_application()

        mock_logger.warning.assert_called_once()

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.settings")
    @patch("app.middleware.tracing.logger")
    def test_instrument_handles_generic_exception(self, mock_logger, mock_settings, mock_configure):
        """Test instrumentation handles generic exceptions."""
        mock_configure.side_effect = Exception("Test error")

        instrument_application()

        mock_logger.error.assert_called_once()
