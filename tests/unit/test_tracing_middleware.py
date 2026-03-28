"""Tests for tracing middleware."""

from unittest.mock import MagicMock, patch
import sys
import pytest

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
    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", False)
    def test_configure_when_opentelemetry_not_available(self):
        configure_distributed_tracing()

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
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()
        configure_distributed_tracing(
            enable_console_exporter=True, service_name="test-service", service_version="2.0.0"
        )
        mock_resource.create.assert_called_once()


class TestServerRequestHook:
    def test_hook_with_route_info(self):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/test/path"
        mock_scope.get.side_effect = lambda key, default=None: (
            mock_route if key == "route" else default
        )
        _server_request_hook(mock_span, mock_scope)
        mock_span.set_attribute.assert_called()


class TestClientRequestHook:
    def test_hook_adds_method_and_url(self):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        _client_request_hook(mock_span, "GET", "http://example.com")
        assert mock_span.set_attribute.call_count == 2


class TestClientResponseHook:
    def test_hook_adds_response_complete(self):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        _client_response_hook(mock_span, {}, "body")
        mock_span.set_attribute.assert_called_once_with("http.response_complete", True)


class TestInstrumentApplication:
    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", False)
    @patch("app.middleware.tracing.logger")
    def test_instrument_when_opentelemetry_not_available(self, mock_logger):
        instrument_application()
        mock_logger.warning.assert_called_once()


class TestConfigureDistributedTracingSuccessPath:
    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_logs_success_message(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        mock_resource.create.return_value = MagicMock()
        mock_trace.get_tracer_provider.return_value = MagicMock()
        configure_distributed_tracing(
            service_name="test-service",
            service_version="1.0.0",
            enable_console_exporter=False,
            sampling_rate=0.5,
        )
        assert mock_logger.info.call_count >= 1


class TestModuleLevelImports:
    def test_jaeger_exporter_import_failure_handling(self):
        import app.middleware.tracing as tracing_module

        assert hasattr(tracing_module, "JAEGER_EXPORTER_AVAILABLE")
        assert isinstance(tracing_module.JAEGER_EXPORTER_AVAILABLE, bool)
        assert hasattr(tracing_module, "OPENTELEMETRY_AVAILABLE")
        assert isinstance(tracing_module.OPENTELEMETRY_AVAILABLE, bool)


class TestConfigureDistributedTracingWithJaeger:
    """Test Jaeger exporter configuration."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.JAEGER_EXPORTER_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.JaegerExporter")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_with_jaeger_endpoint(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_jaeger_exporter,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with Jaeger endpoint."""
        mock_resource.create.return_value = MagicMock()
        mock_tracer_provider_instance = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_tracer_provider_instance

        configure_distributed_tracing(
            service_name="test-service",
            service_version="1.0.0",
            jaeger_endpoint="localhost:6831",
        )

        mock_jaeger_exporter.assert_called_once()
        assert mock_logger.info.call_count >= 1

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.JAEGER_EXPORTER_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.JaegerExporter")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_with_jaeger_endpoint_with_port(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_jaeger_exporter,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with Jaeger endpoint including port."""
        mock_resource.create.return_value = MagicMock()
        mock_tracer_provider_instance = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_tracer_provider_instance

        configure_distributed_tracing(
            service_name="test-service",
            service_version="1.0.0",
            jaeger_endpoint="jaeger.example.com:6831",
        )

        # Verify JaegerExporter was called with parsed host and port
        mock_jaeger_exporter.assert_called_once()
        call_kwargs = mock_jaeger_exporter.call_args[1]
        assert call_kwargs["agent_host_name"] == "jaeger.example.com"
        assert call_kwargs["agent_port"] == 6831

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.JAEGER_EXPORTER_AVAILABLE", False)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_with_jaeger_endpoint_not_available(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration when Jaeger endpoint is configured but exporter not available."""
        mock_resource.create.return_value = MagicMock()
        mock_tracer_provider_instance = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_tracer_provider_instance

        configure_distributed_tracing(
            service_name="test-service",
            service_version="1.0.0",
            jaeger_endpoint="localhost:6831",
        )

        # Should log warning about Jaeger not available
        warning_logged = any("Jaeger" in str(call) for call in mock_logger.warning.call_args_list)
        assert warning_logged


class TestConfigureDistributedTracingWithOTLP:
    """Test OTLP exporter configuration."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.OTLPSpanExporter")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_with_otlp_endpoint(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_otlp_exporter,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test configuration with OTLP endpoint."""
        mock_resource.create.return_value = MagicMock()
        mock_tracer_provider_instance = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_tracer_provider_instance

        configure_distributed_tracing(
            service_name="test-service",
            service_version="1.0.0",
            otlp_endpoint="localhost:4317",
        )

        mock_otlp_exporter.assert_called_once()
        call_kwargs = mock_otlp_exporter.call_args[1]
        assert call_kwargs["endpoint"] == "localhost:4317"
        assert call_kwargs["insecure"] is True


class TestServerRequestHookEdgeCases:
    """Test edge cases for server request hook."""

    def test_hook_with_no_route_info(self):
        """Test hook when route info is not available."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock()
        mock_scope.get.return_value = None

        _server_request_hook(mock_span, mock_scope)

        # Should not raise an exception
        assert mock_span.is_recording.called

    def test_hook_with_user_info(self):
        """Test hook when user info is available."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.username = "testuser"

        def scope_get(key, default=None):
            if key == "user":
                return mock_user
            return default

        mock_scope.get.side_effect = scope_get

        _server_request_hook(mock_span, mock_scope)

        # Should set user attributes
        assert mock_span.set_attribute.called

    def test_hook_with_span_not_recording(self):
        """Test hook when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False
        mock_scope = MagicMock()

        _server_request_hook(mock_span, mock_scope)

        # Should not set attributes if not recording
        mock_span.set_attribute.assert_not_called()

    def test_hook_with_scope_not_callable(self):
        """Test hook when scope.get is not callable."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_scope = MagicMock()
        mock_scope.get = None  # Not callable

        _server_request_hook(mock_span, mock_scope)

        # Should handle gracefully
        assert mock_span.is_recording.called


class TestClientRequestHookEdgeCases:
    """Test edge cases for client request hook."""

    def test_hook_with_span_not_recording(self):
        """Test hook when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        _client_request_hook(mock_span, "POST", "http://example.com/api")

        # Should not set attributes if not recording
        mock_span.set_attribute.assert_not_called()

    def test_hook_with_various_methods(self):
        """Test hook with various HTTP methods."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            _client_request_hook(mock_span, method, "http://example.com")

        # Should be called for each method
        assert mock_span.set_attribute.call_count >= 10


class TestClientResponseHookEdgeCases:
    """Test edge cases for client response hook."""

    def test_hook_with_span_not_recording(self):
        """Test hook when span is not recording."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        _client_response_hook(mock_span, {"content-type": "application/json"}, "response body")

        # Should not set attributes if not recording
        mock_span.set_attribute.assert_not_called()

    def test_hook_with_empty_response_body(self):
        """Test hook with empty response body."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        _client_response_hook(mock_span, {}, "")

        mock_span.set_attribute.assert_called_once_with("http.response_complete", True)


class TestInstrumentApplicationWithSettings:
    """Test instrument_application with various settings."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.logger")
    def test_instrument_application_calls_configure(self, mock_logger, mock_configure):
        """Test that instrument_application calls configure_distributed_tracing."""
        with patch("app.middleware.tracing.settings") as mock_settings:
            mock_settings.tracing_service_name = "test-service"
            mock_settings.tracing_service_version = "1.0.0"
            mock_settings.jaeger_endpoint = None
            mock_settings.otlp_endpoint = None
            mock_settings.tracing_console_exporter = False
            mock_settings.tracing_sampling_rate = 1.0

            instrument_application()

            mock_configure.assert_called_once()

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.logger")
    def test_instrument_application_with_custom_settings(self, mock_logger, mock_configure):
        """Test instrument_application with custom settings."""
        with patch("app.middleware.tracing.settings") as mock_settings:
            mock_settings.tracing_service_name = "custom-service"
            mock_settings.tracing_service_version = "2.0.0"
            mock_settings.jaeger_endpoint = "localhost:6831"
            mock_settings.otlp_endpoint = "localhost:4317"
            mock_settings.tracing_console_exporter = True
            mock_settings.tracing_sampling_rate = 0.5

            instrument_application()

            mock_configure.assert_called_once()
            call_kwargs = mock_configure.call_args[1]
            assert call_kwargs["service_name"] == "custom-service"
            assert call_kwargs["service_version"] == "2.0.0"

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.logger")
    def test_instrument_application_logs_completion(self, mock_logger, mock_configure):
        """Test that instrument_application logs completion."""
        with patch("app.middleware.tracing.settings") as mock_settings:
            mock_settings.tracing_service_name = "test-service"
            mock_settings.tracing_service_version = "1.0.0"
            mock_settings.jaeger_endpoint = None
            mock_settings.otlp_endpoint = None
            mock_settings.tracing_console_exporter = False
            mock_settings.tracing_sampling_rate = 1.0

            instrument_application()

            # Should log completion
            assert mock_logger.info.called

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.logger")
    def test_instrument_application_handles_import_error(self, mock_logger, mock_configure):
        """Test that instrument_application handles ImportError."""
        mock_configure.side_effect = ImportError("OpenTelemetry not available")

        with patch("app.middleware.tracing.settings") as mock_settings:
            mock_settings.tracing_service_name = "test-service"
            mock_settings.tracing_service_version = "1.0.0"
            mock_settings.jaeger_endpoint = None
            mock_settings.otlp_endpoint = None
            mock_settings.tracing_console_exporter = False
            mock_settings.tracing_sampling_rate = 1.0

            instrument_application()

            # Should log warning
            assert mock_logger.warning.called

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.configure_distributed_tracing")
    @patch("app.middleware.tracing.logger")
    def test_instrument_application_handles_generic_exception(self, mock_logger, mock_configure):
        """Test that instrument_application handles generic exceptions."""
        mock_configure.side_effect = Exception("Configuration failed")

        with patch("app.middleware.tracing.settings") as mock_settings:
            mock_settings.tracing_service_name = "test-service"
            mock_settings.tracing_service_version = "1.0.0"
            mock_settings.jaeger_endpoint = None
            mock_settings.otlp_endpoint = None
            mock_settings.tracing_console_exporter = False
            mock_settings.tracing_sampling_rate = 1.0

            instrument_application()

            # Should log error
            assert mock_logger.error.called


class TestConfigureDistributedTracingErrorHandling:
    """Test error handling in configure_distributed_tracing."""

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.logger")
    def test_configure_handles_exception(
        self, mock_logger, mock_resource, mock_tracer_provider, mock_trace
    ):
        """Test that configure_distributed_tracing handles exceptions."""
        mock_resource.create.side_effect = Exception("Resource creation failed")

        with pytest.raises(Exception):
            configure_distributed_tracing(service_name="test-service")

        # Should log error
        assert mock_logger.error.called

    @patch("app.middleware.tracing.OPENTELEMETRY_AVAILABLE", True)
    @patch("app.middleware.tracing.trace")
    @patch("app.middleware.tracing.TracerProvider")
    @patch("app.middleware.tracing.Resource")
    @patch("app.middleware.tracing.BatchSpanProcessor")
    @patch("app.middleware.tracing.FastAPIInstrumentor")
    @patch("app.middleware.tracing.SQLAlchemyInstrumentor")
    @patch("app.middleware.tracing.RedisInstrumentor")
    @patch("app.middleware.tracing.logger")
    def test_configure_handles_sqlalchemy_instrumentation_error(
        self,
        mock_logger,
        mock_redis_inst,
        mock_sqlalchemy_inst,
        mock_fastapi_inst,
        mock_batch_processor,
        mock_resource,
        mock_tracer_provider,
        mock_trace,
    ):
        """Test that configure_distributed_tracing handles SQLAlchemy instrumentation errors."""
        mock_resource.create.return_value = MagicMock()
        mock_tracer_provider_instance = MagicMock()
        mock_trace.get_tracer_provider.return_value = mock_tracer_provider_instance
        mock_sqlalchemy_inst.return_value.instrument.side_effect = Exception(
            "SQLAlchemy instrumentation failed"
        )

        configure_distributed_tracing(service_name="test-service")

        # Should log warning about SQLAlchemy failure
        warning_logged = any(
            "SQLAlchemy" in str(call) for call in mock_logger.warning.call_args_list
        )
        assert warning_logged
