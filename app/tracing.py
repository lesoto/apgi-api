"""
OpenTelemetry Distributed Tracing Configuration

Provides distributed tracing capabilities for the APGI API.
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.trace import set_tracer_provider


def configure_distributed_tracing():
    """
    Configure OpenTelemetry distributed tracing for the application.

    Sets up tracing with Jaeger and OTLP exporters based on environment configuration.
    """
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
            resource=trace.Resource.create(
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

    trace.get_tracer_provider().add_span_processor(span_processor_jaeger)
    trace.get_tracer_provider().add_span_processor(span_processor_otlp)


def instrument_application():
    """
    Instrument the application with OpenTelemetry auto-instrumentation.

    This should be called after the FastAPI app is created but before it starts serving requests.
    """
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
        OpenTelemetry tracer instance
    """
    return trace.get_tracer(name)
