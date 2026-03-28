"""
Fixtures for security tests.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def test_user_token():
    """Create a test user and return their token."""
    return "test-token-12345"


@pytest.fixture
def db():
    """Mock database session for security tests."""
    mock_db = MagicMock()
    yield mock_db
