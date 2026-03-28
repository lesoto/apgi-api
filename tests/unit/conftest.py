"""
Unit test conftest — sys.modules patches for psycopg2, opentelemetry, and app.celery_app.

All fixtures are autouse=True and function-scoped to prevent state leakage between tests.

Module-level patches (applied before any test file is imported by pytest):
- pyotp: not installed in this environment; patched so auth_manager.py can be imported.
"""

import sys
from unittest.mock import MagicMock, patch
import pytest

# ---------------------------------------------------------------------------
# Module-level sys.modules patches — must happen before pytest collects tests
# ---------------------------------------------------------------------------

# pyotp is not installed; patch it so app.services.auth_manager can be imported
if "pyotp" not in sys.modules:
    _pyotp_mock = MagicMock()
    _pyotp_mock.TOTP = MagicMock()
    _pyotp_mock.random_base32 = MagicMock(return_value="JBSWY3DPEHPK3PXP")
    sys.modules["pyotp"] = _pyotp_mock

# stripe is not installed; patch it so app.routes.payments can be imported
if "stripe" not in sys.modules:
    _stripe_mock = MagicMock()
    _stripe_mock.error = MagicMock()
    _stripe_mock.error.SignatureVerificationError = type(
        "SignatureVerificationError", (Exception,), {}
    )
    _stripe_mock.error.StripeError = type("StripeError", (Exception,), {})
    _stripe_mock.Webhook = MagicMock()
    _stripe_mock.PaymentIntent = MagicMock()
    sys.modules["stripe"] = _stripe_mock
    sys.modules["stripe.error"] = _stripe_mock.error


@pytest.fixture(scope="function")
def mock_psycopg2():
    """Patch psycopg2 and sub-modules into sys.modules before any test imports them."""
    mock = MagicMock()
    mock.extensions = MagicMock()
    mock.extensions.ISOLATION_LEVEL_AUTOCOMMIT = 0
    mock.errors = MagicMock()
    mock.errors.DuplicateDatabase = type("DuplicateDatabase", (Exception,), {})
    mock.errors.DuplicateObject = type("DuplicateObject", (Exception,), {})
    mock.errors.InsufficientPrivilege = type("InsufficientPrivilege", (Exception,), {})

    sys.modules["psycopg2"] = mock
    sys.modules["psycopg2.extensions"] = mock.extensions
    sys.modules["psycopg2.errors"] = mock.errors

    yield mock

    sys.modules.pop("psycopg2", None)
    sys.modules.pop("psycopg2.extensions", None)
    sys.modules.pop("psycopg2.errors", None)


@pytest.fixture(autouse=True, scope="function")
def mock_opentelemetry():
    """Patch all opentelemetry sub-modules into sys.modules."""
    otel_modules = [
        "opentelemetry",
        "opentelemetry.trace",
        "opentelemetry.sdk",
        "opentelemetry.sdk.trace",
        "opentelemetry.sdk.trace.export",
        "opentelemetry.exporter",
        "opentelemetry.exporter.jaeger",
        "opentelemetry.exporter.jaeger.thrift",
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto",
        "opentelemetry.exporter.otlp.proto.grpc",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.instrumentation",
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.sqlalchemy",
        "opentelemetry.instrumentation.redis",
        "opentelemetry.instrumentation.celery",
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.propagate",
        "opentelemetry.context",
        "opentelemetry.sdk.resources",
    ]

    mocks = {}
    for name in otel_modules:
        m = MagicMock()
        mocks[name] = m
        sys.modules[name] = m

    yield mocks

    for name in otel_modules:
        sys.modules.pop(name, None)


@pytest.fixture(autouse=True, scope="function")
def mock_celery_app():
    """Patch app.celery_app into sys.modules to prevent broker connection at import time."""
    mock = MagicMock()
    sys.modules["app.celery_app"] = mock

    yield mock

    sys.modules.pop("app.celery_app", None)


@pytest.fixture(autouse=True, scope="function")
def mock_shared_task():
    """Patch celery.shared_task to return a decorator that preserves the function."""

    def shared_task_decorator(name=None, **kwargs):
        def decorator(func):
            func.name = name or func.__name__
            return func

        return decorator

    with patch("celery.shared_task", side_effect=shared_task_decorator):
        yield
