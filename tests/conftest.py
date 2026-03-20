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
from hypothesis import settings, HealthCheck  # noqa: E402

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

settings.register_profile(
    "dev",
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "thorough",
    max_examples=1000,
    deadline=None,
)

# Load "ci" when running in CI, otherwise "dev" for faster local iteration.
settings.load_profile("ci" if os.getenv("CI") else "dev")

# ── Shared fixtures ──────────────────────────────────────────────────────────
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

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
