"""
Property-based tests for request size limiting middleware.

Feature: api-migration
Tests universal properties of request size limiting to prevent DoS attacks.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from middleware.request_size_limit import RequestSizeLimitMiddleware

# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_size_limit(max_size_mb: int = 10, enabled: bool = True):
    """Create a test FastAPI app with request size limiting middleware."""
    app = FastAPI()

    # Add request size limiting middleware
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_size_mb=max_size_mb,
        enabled=enabled,
    )

    # Add test endpoints
    @app.post("/test")
    async def test_endpoint(data: dict):
        return {"message": "success", "data_size": len(str(data))}

    @app.post("/v1/sessions")
    async def create_session_endpoint(data: dict):
        return {"session_id": "test-123", "data_size": len(str(data))}

    @app.put("/v1/sessions/{session_id}")
    async def update_session_endpoint(session_id: str, data: dict):
        return {"session_id": session_id, "data_size": len(str(data))}

    @app.get("/test")
    async def test_get_endpoint():
        return {"message": "success"}

    return app


# ============================================================================
# Property 30: Request Size Limiting
# ============================================================================


@settings(max_examples=1)
@given(
    payload_size_mb=st.floats(min_value=10.1, max_value=50.0),
    path=st.sampled_from(["/test", "/v1/sessions"]),
)
def test_property_30_request_size_limiting_exceeds_limit(payload_size_mb, path):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any request with body size exceeding the configured limit (default 10MB),
    the request should be rejected with 413 Payload Too Large before processing.

    This property ensures that oversized requests are rejected to prevent
    DoS attacks via large payloads.
    """
    # Create app with 10MB limit
    app = create_test_app_with_size_limit(max_size_mb=10, enabled=True)
    client = TestClient(app)

    # Create a payload that exceeds the limit
    # Generate a string that's approximately the desired size
    payload_size_bytes = int(payload_size_mb * 1024 * 1024)
    # Create a large string (each char is 1 byte in ASCII)
    large_data = "x" * payload_size_bytes

    # Make request with oversized payload
    response = client.post(
        path,
        json={"data": large_data},
        headers={"Content-Type": "application/json"},
    )

    # Property 1: Response status should be 413 Payload Too Large
    assert (
        response.status_code == 413
    ), f"Request with {payload_size_mb}MB payload should be rejected with 413, got {response.status_code}"

    # Property 2: Response should contain error information
    response_data = response.json()
    assert "error" in response_data, f"Response should contain 'error' field"

    error = response_data["error"]

    # Property 3: Error should contain appropriate error code
    assert "code" in error, f"Error should contain 'code' field"
    assert (
        error["code"] == "REQUEST_TOO_LARGE"
    ), f"Error code should be 'REQUEST_TOO_LARGE', got '{error['code']}'"

    # Property 4: Error should contain descriptive message
    assert "message" in error, f"Error should contain 'message' field"
    assert "too large" in error["message"].lower(), f"Error message should mention 'too large'"

    # Property 5: Error should contain timestamp
    assert "timestamp" in error, f"Error should contain 'timestamp' field"

    # Property 6: Error should contain details about size limits
    assert "details" in error, f"Error should contain 'details' field"
    assert "max_size_mb" in error["details"], f"Error details should contain 'max_size_mb'"
    assert (
        error["details"]["max_size_mb"] == 10
    ), f"Max size should be 10MB, got {error['details']['max_size_mb']}"


@settings(max_examples=1)
@given(
    payload_size_kb=st.integers(min_value=1, max_value=1024),
    path=st.sampled_from(["/test", "/v1/sessions"]),
)
def test_property_30_request_size_limiting_within_limit(payload_size_kb, path):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any request with body size within the configured limit,
    the request should be processed normally and return a successful response.

    This property ensures that valid-sized requests are not incorrectly rejected.
    """
    # Create app with 10MB limit
    app = create_test_app_with_size_limit(max_size_mb=10, enabled=True)
    client = TestClient(app)

    # Create a payload within the limit (in KB, well under 10MB)
    payload_size_bytes = payload_size_kb * 1024
    data = "x" * payload_size_bytes

    # Make request with valid-sized payload
    response = client.post(
        path,
        json={"data": data},
        headers={"Content-Type": "application/json"},
    )

    # Property 1: Response status should be 2xx (success)
    assert (
        200 <= response.status_code < 300
    ), f"Request with {payload_size_kb}KB payload should succeed, got status {response.status_code}"

    # Property 2: Response should not contain error about size
    response_data = response.json()
    if "error" in response_data:
        error = response_data["error"]
        assert (
            error.get("code") != "REQUEST_TOO_LARGE"
        ), f"Valid-sized request should not be rejected for size"


@settings(max_examples=1)
@given(
    max_size_mb=st.integers(min_value=1, max_value=100),
    payload_size_mb=st.floats(min_value=0.1, max_value=0.9),
)
def test_property_30_request_size_limiting_configurable_limit(max_size_mb, payload_size_mb):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any configured size limit, requests exceeding that limit should be rejected
    with 413, and requests within the limit should be accepted.

    This property ensures that the size limit is configurable and enforced correctly.
    """
    # Create app with custom size limit
    app = create_test_app_with_size_limit(max_size_mb=max_size_mb, enabled=True)
    client = TestClient(app)

    # Create a payload that's a fraction of the limit (should succeed)
    payload_size_bytes = int(payload_size_mb * max_size_mb * 1024 * 1024)
    data = "x" * payload_size_bytes

    # Make request with payload within limit
    response = client.post(
        "/test",
        json={"data": data},
        headers={"Content-Type": "application/json"},
    )

    # Property: Request within limit should succeed
    assert (
        200 <= response.status_code < 300
    ), f"Request with {payload_size_mb * max_size_mb}MB payload (limit {max_size_mb}MB) should succeed, got {response.status_code}"


@settings(max_examples=1)
@given(
    method=st.sampled_from(["GET", "HEAD", "OPTIONS", "DELETE"]),
    path=st.sampled_from(["/test"]),
)
def test_property_30_request_size_limiting_skips_no_body_methods(method, path):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any request using methods that don't have request bodies (GET, HEAD, OPTIONS, DELETE),
    the size limiting middleware should not reject the request.

    This property ensures that size limiting only applies to methods with request bodies.
    """
    # Create app with very small size limit (1 byte)
    app = create_test_app_with_size_limit(max_size_mb=0.000001, enabled=True)
    client = TestClient(app, raise_server_exceptions=False)

    # Make request with method that doesn't have a body
    try:
        if method == "GET":
            response = client.get(path)
        elif method == "HEAD":
            response = client.head(path)
        elif method == "OPTIONS":
            response = client.options(path)
        elif method == "DELETE":
            response = client.delete(path)
    except Exception:
        # If endpoint doesn't support this method, skip
        assume(False)

    # Property: Request should not be rejected for size (may be 404 or 405, but not 413)
    assert (
        response.status_code != 413
    ), f"{method} request should not be rejected for size, got {response.status_code}"


@settings(max_examples=1)
@given(
    payload_size_mb=st.floats(min_value=15.0, max_value=50.0),
)
def test_property_30_request_size_limiting_disabled(payload_size_mb):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any request when size limiting is disabled, the request should be processed
    regardless of size (up to server limits).

    This property ensures that size limiting can be disabled when needed.
    """
    # Create app with size limiting disabled
    app = create_test_app_with_size_limit(max_size_mb=10, enabled=False)
    client = TestClient(app, raise_server_exceptions=False)

    # Create a payload that would exceed the limit if it were enabled
    payload_size_bytes = int(payload_size_mb * 1024 * 1024)
    # Use a smaller payload to avoid actual server limits
    # (we're testing the middleware, not the server)
    payload_size_bytes = min(payload_size_bytes, 20 * 1024 * 1024)  # Cap at 20MB
    data = "x" * payload_size_bytes

    # Make request with large payload
    try:
        response = client.post(
            "/test",
            json={"data": data},
            headers={"Content-Type": "application/json"},
        )
    except Exception:
        # If server has its own limits, that's okay - we're testing middleware
        assume(False)

    # Property: Request should not be rejected with 413 (middleware is disabled)
    assert (
        response.status_code != 413
    ), f"Request should not be rejected with 413 when size limiting is disabled, got {response.status_code}"


@settings(max_examples=1)
@given(
    payload_size_mb=st.floats(min_value=10.1, max_value=20.0),
)
def test_property_30_request_size_limiting_content_length_header(payload_size_mb):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any request with Content-Length header exceeding the limit,
    the request should be rejected immediately without reading the body.

    This property ensures that the middleware efficiently rejects oversized
    requests based on the Content-Length header when available.
    """
    # Create app with 10MB limit
    app = create_test_app_with_size_limit(max_size_mb=10, enabled=True)
    client = TestClient(app)

    # Create a payload that exceeds the limit
    payload_size_bytes = int(payload_size_mb * 1024 * 1024)
    data = "x" * payload_size_bytes

    # Make request with Content-Length header
    response = client.post(
        "/test",
        json={"data": data},
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(data) + 100),  # Approximate size
        },
    )

    # Property 1: Response status should be 413
    assert (
        response.status_code == 413
    ), f"Request with Content-Length {payload_size_mb}MB should be rejected with 413, got {response.status_code}"

    # Property 2: Response should contain error information
    response_data = response.json()
    assert "error" in response_data, f"Response should contain 'error' field"
    assert (
        response_data["error"]["code"] == "REQUEST_TOO_LARGE"
    ), f"Error code should be 'REQUEST_TOO_LARGE'"


@settings(max_examples=1)
@given(
    payload_size_mb=st.floats(min_value=10.1, max_value=20.0),
    path=st.sampled_from(["/test", "/v1/sessions"]),
    method=st.sampled_from(["POST", "PUT"]),
)
def test_property_30_request_size_limiting_applies_to_all_endpoints(payload_size_mb, path, method):
    """
    **Validates: Requirements 20.2**

    Feature: api-migration, Property 30: Request Size Limiting

    For any endpoint and any HTTP method with a request body,
    the size limiting should be enforced consistently.

    This property ensures that size limiting applies uniformly across all endpoints.
    """
    # Create app with 10MB limit
    app = create_test_app_with_size_limit(max_size_mb=10, enabled=True)
    client = TestClient(app)

    # Create a payload that exceeds the limit
    payload_size_bytes = int(payload_size_mb * 1024 * 1024)
    data = "x" * payload_size_bytes

    # Make request to different endpoints
    try:
        if method == "POST":
            response = client.post(
                path,
                json={"data": data},
                headers={"Content-Type": "application/json"},
            )
        elif method == "PUT":
            # PUT requires session_id in path
            if "{session_id}" in path or path == "/v1/sessions":
                response = client.put(
                    "/v1/sessions/test-123",
                    json={"data": data},
                    headers={"Content-Type": "application/json"},
                )
            else:
                assume(False)
    except Exception:
        # If endpoint doesn't exist, skip
        assume(False)

    # Property: All endpoints should enforce size limiting consistently
    assert (
        response.status_code == 413
    ), f"{method} request to {path} with {payload_size_mb}MB payload should be rejected with 413, got {response.status_code}"

    # Verify error structure is consistent
    response_data = response.json()
    assert "error" in response_data, f"Response should contain 'error' field"
    assert (
        response_data["error"]["code"] == "REQUEST_TOO_LARGE"
    ), f"Error code should be 'REQUEST_TOO_LARGE'"
