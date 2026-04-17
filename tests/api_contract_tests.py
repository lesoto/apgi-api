"""
API Contract Tests

Tests to verify API contracts, including rate limiting headers, error responses, etc.
"""

from fastapi.testclient import TestClient


def test_rate_limit_headers_present(client: TestClient) -> None:
    """
    Test that rate limit headers are present in API responses.

    Note: This test will pass once rate limiting is implemented (MF-01).
    Currently, it serves as documentation of the expected behavior.
    """
    # Make a request to a public endpoint
    response = client.get("/health")

    # Assert rate limit headers are present
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers

    # Assert they are numeric
    limit = int(response.headers["X-RateLimit-Limit"])
    remaining = int(response.headers["X-RateLimit-Remaining"])
    reset = int(response.headers["X-RateLimit-Reset"])

    assert limit > 0
    assert remaining >= 0
    assert reset > 0


def test_rate_limit_headers_authenticated(client: TestClient, auth_headers: dict[str, str]) -> None:
    """
    Test that rate limit headers are present for authenticated requests.

    Note: This test will pass once rate limiting is implemented (MF-01).
    """
    # Make an authenticated request
    response = client.get("/v1/users/me", headers=auth_headers)

    # Assert rate limit headers are present
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers

    # Assert they are numeric
    limit = int(response.headers["X-RateLimit-Limit"])
    remaining = int(response.headers["X-RateLimit-Remaining"])
    reset = int(response.headers["X-RateLimit-Reset"])

    assert limit > 0
    assert remaining >= 0
    assert reset > 0


def test_error_response_format(client: TestClient) -> None:
    """
    Test that error responses follow the expected JSON format.
    """
    # Make a request that will fail (unauthorized)
    response = client.get("/v1/users/me")

    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "timestamp" in data["error"]


def test_cors_headers_present(client: TestClient) -> None:
    """
    Test that CORS headers are present in responses.
    """
    response = client.options("/health", headers={"Origin": "http://localhost:3000"})

    # Check for CORS headers
    cors_headers = [
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers",
        "Access-Control-Max-Age",
    ]

    for header in cors_headers:
        assert header in response.headers


def test_csrf_token_provided(client: TestClient) -> None:
    """
    Test that CSRF tokens are provided for safe methods.
    """
    response = client.get("/docs")

    # Should have CSRF token in cookie
    assert "csrf_token" in response.cookies
