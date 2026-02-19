"""
OpenTelemetry Distributed Tracing Configuration

Provides distributed tracing capabilities for the APGI API.
"""

import os
import warnings

# Handle OpenTelemetry compatibility issues with Python 3.14
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.resources import Resource

    OPENTELEMETRY_AVAILABLE = True
except (ImportError, TypeError) as e:
    # Handle Python 3.14 compatibility issues
    OPENTELEMETRY_AVAILABLE = False
    warnings.warn(
        f"OpenTelemetry not available: {str(e)}. "
        "Distributed tracing will be disabled. "
        "This may be due to Python 3.14 compatibility issues.",
        ImportWarning,
    )


def configure_distributed_tracing():
    """
    Configure OpenTelemetry distributed tracing for the application.

    Sets up tracing with Jaeger and OTLP exporters based on environment configuration.
    """
    if not OPENTELEMETRY_AVAILABLE:
        print("OpenTelemetry not available, skipping tracing configuration")
        return

    # Get tracing configuration from environment
    tracing_enabled = os.getenv("TRACING_ENABLED", "false").lower() == "true"
    jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    service_name = os.getenv("TRACING_SERVICE_NAME", "apgi-api")
    service_version = os.getenv("API_VERSION", "1.0.0")

    if not tracing_enabled:
        return

    # Set up tracer provider
    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create(
                {
                    "service.name": service_name,
                    "service.version": service_version,
                }
            )
        )
    )

    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=14268,
    )

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )

    # Add span processors
    span_processor_jaeger = BatchSpanProcessor(jaeger_exporter)
    span_processor_otlp = BatchSpanProcessor(otlp_exporter)

    tracer_provider = trace.get_tracer_provider()
    tracer_provider.add_span_processor(span_processor_jaeger)
    tracer_provider.add_span_processor(span_processor_otlp)


def instrument_application():
    """
    Instrument the application with OpenTelemetry auto-instrumentation.

    This should be called after the FastAPI app is created but before it starts serving requests.
    """
    if not OPENTELEMETRY_AVAILABLE:
        print("OpenTelemetry not available, skipping application instrumentation")
        return

    tracing_enabled = os.getenv("TRACING_ENABLED", "false").lower() == "true"

    if not tracing_enabled:
        return

    # Instrument FastAPI
    FastAPIInstrumentor.instrument()

    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument()

    # Instrument Redis
    RedisInstrumentor().instrument()


def get_tracer(name: str):
    """
    Get a tracer instance for manual instrumentation.

    Args:
        name: Name of the tracer component

    Returns:
        OpenTelemetry tracer instance or None if not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    return trace.get_tracer(name)
