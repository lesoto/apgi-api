"""
Fixtures for security tests.
"""

from typing import Generator
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def test_user_token() -> str:
    """Create a test user and return their token."""
    return "test-token-12345"


@pytest.fixture
def db() -> Generator[MagicMock, None, None]:
    """Mock database session for security tests."""
    mock_db = MagicMock()
    yield mock_db
