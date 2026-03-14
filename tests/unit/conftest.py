"""
Conftest for database utility tests.

Sets up mocks for dependencies before modules are imported.
"""

import sys
from unittest.mock import MagicMock
import pytest


@pytest.fixture(autouse=True)
def mock_psycopg2():
    """Mock psycopg2 for database utility tests."""
    mock_psycopg2 = MagicMock()
    mock_psycopg2.errors = MagicMock()
    mock_psycopg2.errors.DuplicateDatabase = Exception
    mock_psycopg2.errors.DuplicateObject = Exception
    mock_psycopg2.extensions = MagicMock()
    mock_psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT = 0
    sys.modules["psycopg2"] = mock_psycopg2
    sys.modules["psycopg2.extensions"] = mock_psycopg2.extensions
    sys.modules["psycopg2.errors"] = mock_psycopg2.errors
    yield
    # Cleanup
    sys.modules.pop("psycopg2", None)
    sys.modules.pop("psycopg2.extensions", None)
    sys.modules.pop("psycopg2.errors", None)


@pytest.fixture(autouse=True)
def mock_database_dependencies():
    """Mock database dependencies for utility tests."""
    # Mock database connection and models
    sys.modules["app.database.connection"] = MagicMock()
    sys.modules["app.database.models"] = MagicMock()
    sys.modules["app.services.auth_manager"] = MagicMock()
    yield
    # Cleanup
    sys.modules.pop("app.database.connection", None)
    sys.modules.pop("app.database.models", None)
    sys.modules.pop("app.services.auth_manager", None)


@pytest.fixture(autouse=True)
def mock_opentelemetry():
    """Mock OpenTelemetry for tracing tests."""
    mock_trace = MagicMock()
    mock_sdk = MagicMock()
    mock_export = MagicMock()
    mock_resources = MagicMock()
    mock_instrumentation = MagicMock()

    sys.modules["opentelemetry"] = MagicMock()
    sys.modules["opentelemetry.trace"] = mock_trace
    sys.modules["opentelemetry.sdk.trace"] = mock_sdk
    sys.modules["opentelemetry.sdk.trace.export"] = mock_export
    sys.modules["opentelemetry.sdk.resources"] = mock_resources
    sys.modules["opentelemetry.instrumentation"] = mock_instrumentation
    sys.modules["opentelemetry.instrumentation.fastapi"] = MagicMock()
    sys.modules["opentelemetry.instrumentation.sqlalchemy"] = MagicMock()
    sys.modules["opentelemetry.instrumentation.redis"] = MagicMock()
    sys.modules["opentelemetry.instrumentation.celery"] = MagicMock()
    sys.modules["opentelemetry.instrumentation.httpx"] = MagicMock()
    sys.modules["opentelemetry.exporter.jaeger.thrift"] = MagicMock()
    sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = MagicMock()

    yield
    # Cleanup
    for module in list(sys.modules.keys()):
        if module.startswith("opentelemetry"):
            sys.modules.pop(module, None)
