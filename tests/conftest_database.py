"""
Test configuration and fixtures for database testing.

Provides test-specific database configuration using SQLite in-memory
database to avoid dependency on PostgreSQL during testing.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator, Any

# Test database URL using SQLite in-memory database
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db_engine() -> Generator[Any, Any, None]:
    """Create a test database engine using SQLite in-memory database."""
    engine = create_engine(
        TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}  # SQLite specific
    )
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine) -> Generator[Any, Any, None]:
    """Create a test database session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_database_connection() -> Generator[tuple[Any, Any, Any], Any, None]:
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


@pytest.fixture
def test_environment() -> Generator[dict[str, str], Any, None]:
    """Set test environment variables."""
    original_env = {}
    test_vars = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": TEST_DATABASE_URL,
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
