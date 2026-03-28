"""
Root conftest.py — sets all required environment variables BEFORE any app import,
registers Hypothesis profiles, and provides shared SQLite in-memory fixtures.
"""

import os

# ── Environment variables ────────────────────────────────────────────────────
# These MUST be set before any app module is imported so that app.config.Settings()
# can construct without raising ValueError.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-32chars!")
os.environ.setdefault("CURSOR_SIGNING_KEY", "test-cursor-key-that-is-long-enough-32chars!")
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test-webhook-key-that-is-long-enough-32c!")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

# ── Hypothesis profiles ──────────────────────────────────────────────────────
import hypothesis  # noqa: E402
from hypothesis import settings, HealthCheck  # noqa: E402

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    phases=[hypothesis.Phase.generate, hypothesis.Phase.shrink],
)

settings.register_profile(
    "dev",
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    phases=[hypothesis.Phase.generate, hypothesis.Phase.shrink],
)

settings.register_profile(
    "thorough",
    max_examples=1000,
    deadline=None,
    phases=[hypothesis.Phase.generate, hypothesis.Phase.shrink],
)

# Load "ci" when running in CI, otherwise "dev" for faster local iteration.
settings.load_profile("ci" if os.getenv("CI") else "dev")

# ── Global mocks for optional dependencies ──────────────────────────────────
# Mock optional dependencies that commonly cause test failures
import warnings
from unittest.mock import MagicMock

# Mock OpenTelemetry modules
otel_modules = {
    "opentelemetry": MagicMock(),
    "opentelemetry.trace": MagicMock(),
    "opentelemetry.sdk.trace": MagicMock(),
    "opentelemetry.sdk.trace.export": MagicMock(),
    "opentelemetry.exporter.jaeger.thrift": MagicMock(),
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
    "opentelemetry.instrumentation.fastapi": MagicMock(),
    "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
    "opentelemetry.instrumentation.redis": MagicMock(),
    "opentelemetry.sdk.resources": MagicMock(),
}

# Mock apgi_system modules
apgi_modules = {
    "apgi_system": MagicMock(),
    "apgi_system.experiments": MagicMock(),
    "apgi_system.experiments.tasks": MagicMock(),
    "apgi_system.platform_utils": MagicMock(),
    "apgi_system.system": MagicMock(),
}

# Mock other problematic dependencies
other_modules = {
    "celery": MagicMock(),
    "kombu": MagicMock(),
    "billiard": MagicMock(),
}

# Apply all mocks to sys.modules
import sys

for module_name, module_mock in {**otel_modules, **apgi_modules, **other_modules}.items():
    sys.modules[module_name] = module_mock

# Suppress warnings about missing optional dependencies
warnings.filterwarnings("ignore", category=ImportWarning)

# ── Shared fixtures ──────────────────────────────────────────────────────────
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from unittest.mock import patch, MagicMock  # noqa: E402

_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db_engine():
    """SQLite in-memory engine, one per test function."""
    engine = create_engine(
        _TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """SQLAlchemy session bound to the in-memory SQLite engine."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_environment():
    """Set test environment variables."""
    original_env = {}
    test_vars = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": _TEST_DATABASE_URL,
        "REDIS_URL": "redis://localhost:6379/1",  # Different DB for tests
        "JWT_SECRET_KEY": "test_secret_key_that_is_long_enough_for_testing_32chars",
        "LOG_LEVEL": "DEBUG",
    }

    # Store original values and set test values
    for key, value in test_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_vars

    # Restore original values
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_database_connection():
    """Mock database connection for tests that don't need actual DB."""
    with (
        patch("app.database.connection.engine") as mock_engine,
        patch("app.database.connection.SessionLocal") as mock_session,
    ):
        # Mock engine
        mock_engine.return_value = MagicMock()

        # Mock session
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        yield mock_engine, mock_session, mock_session_instance
