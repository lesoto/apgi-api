"""
Fixtures for security tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def test_user_token(client):
    """Create a test user and return their token."""
    # Create a test user
    response = client.post(
        "/v1/users/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
        },
    )
    assert response.status_code == 201

    # Login to get token
    response = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def db():
    """Mock database session for security tests."""
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    yield mock_db
