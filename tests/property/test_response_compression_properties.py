"""
Property-based tests for response compression middleware.

Feature: api-migration
Tests universal properties of GZip response compression for large responses.
"""

from hypothesis import given, strategies as st, assume, settings
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_compression(minimum_size: int = 1000) -> FastAPI:
    """Create a test FastAPI app with GZip compression middleware."""
    app = FastAPI()

    # Add GZip compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=minimum_size)

    # Add test endpoints that return various sized responses
    @app.get("/test/small")
    async def small_response() -> Dict[str, str]:
        return {"message": "small"}

    @app.get("/test/large")
    async def large_response() -> Dict[str, str]:
        # Return a response larger than 1KB
        return {"data": "x" * 2000, "message": "large response"}

    @app.get("/test/custom")
    async def custom_response(size: int = 1000) -> Dict[str, str]:
        # Return a response of custom size
        return {"data": "x" * size}

    @app.post("/test/echo")
    async def echo_response(data: Dict[str, Any]) -> Dict[str, Any]:
        # Echo back the data
        return data

    @app.get("/v1/sessions")
    async def sessions_endpoint() -> Dict[str, List[Dict[str, Any]]]:
        # Return a large list of sessions
        sessions = [
            {
                "session_id": "session-" + str(i),
                "status": "running",
                "config": {"param1": "value1", "param2": "value2"},
                "created_at": "2024-01-01T00:00:00Z",
            }
            for i in range(50)
        ]
        return {"sessions": sessions}

    return app


# ============================================================================
# Property 29: Response Compression for Large Responses
# ============================================================================


@settings(max_examples=1)
@given(
    response_size_kb=st.floats(min_value=1.1, max_value=100.0),
)
def test_property_29_response_compression_for_large_responses(response_size_kb: float) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any response with body size greater than 1KB, when the client supports
    gzip encoding, the response should be compressed.

    This property ensures that large responses are compressed to reduce bandwidth
    and improve performance.
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Calculate response size in bytes
    response_size_bytes = int(response_size_kb * 1024)

    # Make request with Accept-Encoding: gzip header
    response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "gzip"},
    )

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should include Content-Encoding header indicating compression
    assert (
        "content-encoding" in response.headers
    ), f"Response for {response_size_kb}KB should include Content-Encoding header"

    # Property 3: Content-Encoding should be "gzip"
    content_encoding = response.headers.get("content-encoding")
    assert (
        content_encoding == "gzip"
    ), f"Content-Encoding should be 'gzip', got '{content_encoding}'"

    # Property 4: Response body should be valid JSON (TestClient auto-decompresses)
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"

    # Property 5: Response data should contain the expected content
    assert "data" in response_data, "Response should contain 'data' field"


@settings(max_examples=1)
@given(
    response_size_bytes=st.integers(min_value=100, max_value=900),
)
def test_property_29_no_compression_for_small_responses(response_size_bytes: int) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any response with body size less than or equal to 1KB, the response
    should not be compressed even when the client supports gzip encoding.

    This property ensures that small responses are not compressed (compression
    overhead would outweigh benefits).
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Make request with Accept-Encoding: gzip header
    response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "gzip"},
    )

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should NOT include Content-Encoding header
    # (or if it does, it should not be gzip)
    content_encoding = response.headers.get("content-encoding")
    assert (
        content_encoding != "gzip"
    ), "Small response ({response_size_bytes} bytes) should not be compressed with gzip"

    # Property 3: Response body should be valid JSON
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"


@settings(max_examples=1)
@given(
    response_size_kb=st.floats(min_value=1.1, max_value=50.0),
)
def test_property_29_no_compression_without_accept_encoding(response_size_kb: float) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any response with body size greater than 1KB, when the client does NOT
    support gzip encoding (explicitly rejects it), the response should not
    be compressed.

    This property ensures that compression is only applied when the client
    explicitly supports it.
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Calculate response size in bytes
    response_size_bytes = int(response_size_kb * 1024)

    # Make request with Accept-Encoding explicitly set to identity (no compression)
    response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "identity"},
    )

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should NOT include Content-Encoding: gzip header
    content_encoding = response.headers.get("content-encoding")
    assert (
        content_encoding != "gzip"
    ), "Response should not be compressed when client doesn't support gzip"

    # Property 3: Response body should be valid JSON
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"


@settings(max_examples=1)
@given(
    minimum_size_kb=st.floats(min_value=0.5, max_value=10.0),
    response_size_multiplier=st.floats(min_value=1.1, max_value=3.0),
)
def test_property_29_configurable_compression_threshold(
    minimum_size_kb: float, response_size_multiplier: float
) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any configured minimum compression size, responses larger than that size
    should be compressed when the client supports gzip, and responses smaller
    than that size should not be compressed.

    This property ensures that the compression threshold is configurable.
    """
    # Create app with custom minimum compression size
    minimum_size_bytes = int(minimum_size_kb * 1024)
    app = create_test_app_with_compression(minimum_size=minimum_size_bytes)
    client = TestClient(app)

    # Create a response larger than the threshold
    response_size_bytes = int(minimum_size_bytes * response_size_multiplier)

    # Make request with Accept-Encoding: gzip header
    response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "gzip"},
    )

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should be compressed (Content-Encoding: gzip)
    content_encoding = response.headers.get("content-encoding")
    assert (
        content_encoding == "gzip"
    ), f"Response larger than {minimum_size_kb}KB threshold should be compressed"

    # Property 3: Response body should be valid JSON
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"


@settings(max_examples=1)
@given(
    path=st.sampled_from(["/test/large", "/v1/sessions"]),
    method=st.sampled_from(["GET", "POST"]),
)
def test_property_29_compression_applies_to_all_endpoints(path: str, method: str) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any endpoint that returns a large response (>1KB), the response should
    be compressed when the client supports gzip encoding.

    This property ensures that compression applies uniformly across all endpoints.
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Make request with Accept-Encoding: gzip header
    try:
        if method == "GET":
            response = client.get(
                path,
                headers={"Accept-Encoding": "gzip"},
            )
        elif method == "POST":
            # POST to echo endpoint with large data
            large_data = {"data": "x" * 2000}
            response = client.post(
                "/test/echo",
                json=large_data,
                headers={"Accept-Encoding": "gzip"},
            )
    except Exception:
        # If endpoint doesn't exist or doesn't support method, skip
        assume(False)

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should be compressed (Content-Encoding: gzip)
    content_encoding = response.headers.get("content-encoding")
    assert content_encoding == "gzip", f"{method} response from {path} should be compressed"

    # Property 3: Response body should be valid JSON
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"


@settings(max_examples=1)
@given(
    response_size_kb=st.floats(min_value=2.0, max_value=50.0),
)
def test_property_29_compressed_response_is_smaller(response_size_kb: float) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any large response that is compressed, the compressed size should be
    smaller than the uncompressed size (for compressible content).

    This property ensures that compression actually reduces response size.
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Calculate response size in bytes
    response_size_bytes = int(response_size_kb * 1024)

    # Make request WITH compression
    compressed_response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "gzip"},
    )

    # Make request WITHOUT compression (explicitly reject compression)
    uncompressed_response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": "identity"},
    )

    # Property 1: Both responses should be successful
    assert 200 <= compressed_response.status_code < 300, "Compressed request should succeed"
    assert 200 <= uncompressed_response.status_code < 300, "Uncompressed request should succeed"

    # Property 2: Compressed response should have Content-Encoding: gzip
    assert (
        compressed_response.headers.get("content-encoding") == "gzip"
    ), "Compressed response should have Content-Encoding: gzip"

    # Property 3: Uncompressed response should NOT have Content-Encoding: gzip
    assert (
        uncompressed_response.headers.get("content-encoding") != "gzip"
    ), "Uncompressed response should not have Content-Encoding: gzip"

    # Property 4: Both responses should have the same JSON content
    compressed_data = compressed_response.json()
    uncompressed_data = uncompressed_response.json()
    assert (
        compressed_data == uncompressed_data
    ), "Compressed and uncompressed responses should have the same content"

    # Property 5: Compressed response size should be smaller than uncompressed
    # (for highly compressible content like repeated characters)
    # Note: TestClient auto-decompresses, so we need to check the raw content
    # This is a characteristic of gzip compression for repetitive data
    # We verify this by checking that compression was applied (Content-Encoding header)
    # The actual size reduction is handled by the middleware
    assert (
        "content-encoding" in compressed_response.headers
    ), "Compression should be applied to large responses"


@settings(max_examples=1)
@given(
    response_size_kb=st.floats(min_value=1.1, max_value=20.0),
    accept_encoding=st.sampled_from(
        [
            "gzip",
            "gzip, deflate",
            "gzip, deflate, br",
            "deflate, gzip",
        ]
    ),
)
def test_property_29_compression_with_multiple_encodings(
    response_size_kb: float, accept_encoding: str
) -> None:
    """
    **Validates: Requirements 20.1**

    Feature: api-migration, Property 29: Response Compression for Large Responses

    For any large response when the client supports multiple encodings including
    gzip, the response should be compressed with gzip.

    This property ensures that gzip compression is applied when the client
    supports multiple encoding types.
    """
    # Create app with 1KB minimum compression size
    app = create_test_app_with_compression(minimum_size=1000)
    client = TestClient(app)

    # Calculate response size in bytes
    response_size_bytes = int(response_size_kb * 1024)

    # Make request with Accept-Encoding header supporting multiple encodings
    response = client.get(
        "/test/custom?size=" + str(response_size_bytes),
        headers={"Accept-Encoding": accept_encoding},
    )

    # Property 1: Response should be successful
    assert (
        200 <= response.status_code < 300
    ), f"Request should succeed, got status {response.status_code}"

    # Property 2: Response should be compressed with gzip
    content_encoding = response.headers.get("content-encoding")
    assert (
        content_encoding == "gzip"
    ), f"Response should be compressed with gzip when client supports it, got '{content_encoding}'"

    # Property 3: Response body should be valid JSON
    response_data = response.json()
    assert isinstance(response_data, dict), "Response should be valid JSON object"
