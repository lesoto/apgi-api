"""
Root conftest.py — sets all required environment variables BEFORE any app import,
registers Hypothesis profiles, and provides shared SQLite in-memory fixtures.
"""

import os
from typing import Any, Callable, Generator

# ── Environment variables ────────────────────────────────────────────────────
# These MUST be set before any app module is imported so that app.config.Settings()
# can construct without raising ValueError.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-32chars!")
os.environ.setdefault("CURSOR_SIGNING_KEY", "test-cursor-key-that-is-long-enough-32chars!")
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test-webhook-key-that-is-long-enough-32c!")
os.environ.setdefault("PII_ENCRYPTION_KEY", "lN_kr45h0MBU1IsgDfv-KKTb_CzurLv6th8gkekEzWM=")
os.environ.setdefault("AUDIT_SIGNING_KEY", "test-audit-signing-key-that-is-long-enough-32c!")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("TEST_MODE", "true")

# ── Hypothesis profiles ──────────────────────────────────────────────────────
import hypothesis  # noqa: E402
from hypothesis import HealthCheck, settings  # noqa: E402

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


# ── Mock structured logging BEFORE app import ─────────────────────────────
# This must be done before any app module is imported to prevent logging conflicts
from unittest.mock import patch

patch("app.middleware.logging.configure_structured_logging", lambda *args, **kwargs: None).start()


# ── Logging configuration for tests ─────────────────────────────────────────────
import logging

import pytest


@pytest.fixture
def reset_logging() -> Generator[None, None, None]:
    """Reset logging configuration to prevent LogRecord conflicts.

    Use this fixture only when necessary, as it interferes with caplog.
    """
    # Remove all handlers from root logger
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    # Reset log level
    original_level = root_logger.level
    root_logger.setLevel(logging.WARNING)

    yield

    # Restore original state
    root_logger.setLevel(original_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    for handler in original_handlers:
        root_logger.addHandler(handler)


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
# Create a custom Celery mock that returns actual decorated functions
def mock_celery_task_decorator(
    *args: Any, bind: bool = False, base: Any = None, name: str | None = None, **kwargs: Any
) -> Callable[..., Any]:
    """Mock decorator that returns the actual function being decorated."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.name = name or func.__name__  # type: ignore[attr-defined]
        func.bind = bind  # type: ignore[attr-defined]
        func.base = base  # type: ignore[attr-defined]
        return func

    if args and callable(args[0]):
        # Used as @celery_app.task without parentheses
        return decorator(args[0])
    return decorator


class MockCeleryTask:
    """Mock Celery Task base class."""

    pass


class MockCelery:
    """Mock Celery class that returns actual decorated functions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.conf = MagicMock()
        self.conf.task_routes = {}
        self.conf.beat_schedule = {}
        self.conf.update = MagicMock()
        self.tasks: dict[str, Any] = {}  # Add tasks registry
        self.send_task = MagicMock()
        self.control = MagicMock()  # Add control for revoke, etc.
        self.pool = MagicMock()  # Add pool for acquire, etc.

    def task(
        self,
        *args: Any,
        bind: bool = False,
        base: Any = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        """Return actual decorated function."""
        return mock_celery_task_decorator(*args, bind=bind, base=base, name=name, **kwargs)


class MockCeleryModule:
    """Mock celery module with MockCelery class."""

    Celery = MockCelery
    Task = MockCeleryTask
    shared_task = mock_celery_task_decorator
    result = MagicMock()
    states = MagicMock()


other_modules = {
    "celery": MockCeleryModule(),
    "kombu": MagicMock(),
    "billiard": MagicMock(),
}

# Apply all mocks to sys.modules
import sys

for module_name, module_mock in {**otel_modules, **apgi_modules, **other_modules}.items():
    sys.modules[module_name] = module_mock  # type: ignore[assignment]

# Suppress warnings about missing optional dependencies
warnings.filterwarnings("ignore", category=ImportWarning)

from unittest.mock import MagicMock, patch  # noqa: E402

# ── Shared fixtures ──────────────────────────────────────────────────────────
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db_engine() -> Generator[Any, None, None]:
    """SQLite in-memory engine, one per test function."""
    engine = create_engine(
        _TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine: Any) -> Generator[Any, None, None]:
    """SQLAlchemy session bound to the in-memory SQLite engine."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_environment() -> Generator[dict[str, str], None, None]:
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
def mock_database_connection() -> Generator[tuple[Any, Any, Any], None, None]:
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
