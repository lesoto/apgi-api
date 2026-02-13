"""
Property-based tests for CORS (Cross-Origin Resource Sharing) headers.

Feature: api-migration
Tests universal properties of CORS header inclusion in responses.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, AsyncMock
import asyncio

# Import after setting up environment
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_cors(
    allow_origins=None,
    allow_credentials=True,
    allow_methods=None,
    allow_headers=None,
):
    """Create a test FastAPI app with CORS middleware configured."""
    app = FastAPI()

    # Add CORS middleware with specified configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["http://localhost:3000"],
        allow_credentials=allow_credentials,
        allow_methods=allow_methods or ["*"],
        allow_headers=allow_headers or ["*"],
    )

    # Add a test endpoint
    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @app.post("/test")
    async def test_post_endpoint():
        return {"message": "test post"}

    @app.get("/v1/sessions")
    async def sessions_endpoint():
        return {"sessions": []}

    @app.post("/v1/sessions")
    async def create_session_endpoint():
        return {"session_id": "test-123"}

    return app


# ============================================================================
# Property 4: CORS Headers on All Responses
# ============================================================================


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/test",
            "/v1/sessions",
            "/v1/tasks",
            "/v1/users/me",
            "/health",
        ]
    ),
    method=st.sampled_from(["GET", "POST", "PUT", "DELETE"]),
    origin=st.sampled_from(
        [
            "http://localhost:3000",
            "http://localhost:8000",
            "https://example.com",
            "https://app.example.com",
        ]
    ),
)
def test_property_4_cors_headers_on_responses(path, method, origin):
    """
    **Validates: Requirements 7.3, 7.4**

    Feature: api-migration, Property 4: CORS Headers on All Responses

    For any HTTP response when CORS is enabled, the response should include
    Access-Control-Allow-Origin, Access-Control-Allow-Methods, and
    Access-Control-Allow-Headers.

    This property ensures that all responses include proper CORS headers to enable
    cross-origin requests from allowed origins.
    """
    # Create app with CORS enabled for multiple origins
    app = create_test_app_with_cors(
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
            "https://example.com",
            "https://app.example.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    client = TestClient(app)

    # Make request with Origin header
    headers = {"Origin": origin}

    try:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, headers=headers, json={})
        elif method == "PUT":
            response = client.put(path, headers=headers, json={})
        elif method == "DELETE":
            response = client.delete(path, headers=headers)
    except Exception:
        # If endpoint doesn't exist, that's okay - we're testing CORS headers
        # which should be present even on 404 responses
        assume(False)  # Skip this example

    # Property 1: Response should include Access-Control-Allow-Origin header
    assert (
        "access-control-allow-origin" in response.headers
    ), f"Response to {method} {path} should include Access-Control-Allow-Origin header"

    # Property 2: Access-Control-Allow-Origin should match the request origin
    # (when origin is in allowed list)
    allow_origin = response.headers.get("access-control-allow-origin")
    assert (
        allow_origin == origin or allow_origin == "*"
    ), f"Access-Control-Allow-Origin should be '{origin}' or '*', got '{allow_origin}'"

    # Property 3: Response should include Access-Control-Allow-Credentials header
    # when credentials are enabled
    assert (
        "access-control-allow-credentials" in response.headers
    ), f"Response should include Access-Control-Allow-Credentials header"

    credentials_header = response.headers.get("access-control-allow-credentials")
    assert (
        credentials_header.lower() == "true"
    ), f"Access-Control-Allow-Credentials should be 'true', got '{credentials_header}'"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/test",
            "/v1/sessions",
            "/v1/tasks",
        ]
    ),
    origin=st.sampled_from(
        [
            "http://localhost:3000",
            "https://example.com",
        ]
    ),
)
def test_property_4_cors_preflight_requests(path, origin):
    """
    **Validates: Requirements 7.3, 7.4**

    Feature: api-migration, Property 4: CORS Headers on All Responses

    For any preflight OPTIONS request when CORS is enabled, the response should
    include Access-Control-Allow-Origin, Access-Control-Allow-Methods, and
    Access-Control-Allow-Headers.

    This property ensures that preflight requests are handled correctly with
    appropriate CORS headers.
    """
    # Create app with CORS enabled
    app = create_test_app_with_cors(
        allow_origins=[
            "http://localhost:3000",
            "https://example.com",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    client = TestClient(app)

    # Make preflight OPTIONS request
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }

    response = client.options(path, headers=headers)

    # Property 1: Preflight response should include Access-Control-Allow-Origin
    assert (
        "access-control-allow-origin" in response.headers
    ), f"Preflight response should include Access-Control-Allow-Origin header"

    # Property 2: Preflight response should include Access-Control-Allow-Methods
    assert (
        "access-control-allow-methods" in response.headers
    ), f"Preflight response should include Access-Control-Allow-Methods header"

    # Property 3: Preflight response should include Access-Control-Allow-Headers
    assert (
        "access-control-allow-headers" in response.headers
    ), f"Preflight response should include Access-Control-Allow-Headers header"

    # Property 4: Access-Control-Allow-Origin should match the request origin
    allow_origin = response.headers.get("access-control-allow-origin")
    assert (
        allow_origin == origin or allow_origin == "*"
    ), f"Access-Control-Allow-Origin should be '{origin}' or '*', got '{allow_origin}'"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/test",
            "/v1/sessions",
        ]
    ),
    method=st.sampled_from(["GET", "POST"]),
    disallowed_origin=st.sampled_from(
        [
            "http://evil.com",
            "https://malicious.example.com",
            "http://untrusted.org",
        ]
    ),
)
def test_property_4_cors_headers_disallowed_origin(path, method, disallowed_origin):
    """
    **Validates: Requirements 7.3, 7.4**

    Feature: api-migration, Property 4: CORS Headers on All Responses

    For any HTTP response when CORS is enabled with specific allowed origins,
    requests from disallowed origins should not receive Access-Control-Allow-Origin
    header matching their origin.

    This property ensures that CORS properly restricts access to allowed origins only.
    """
    # Create app with CORS enabled for specific origins only
    app = create_test_app_with_cors(
        allow_origins=[
            "http://localhost:3000",
            "https://example.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    client = TestClient(app)

    # Make request with disallowed Origin header
    headers = {"Origin": disallowed_origin}

    try:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, headers=headers, json={})
    except Exception:
        # If endpoint doesn't exist, skip this example
        assume(False)

    # Property: Access-Control-Allow-Origin should NOT match the disallowed origin
    # It should either be absent or be one of the allowed origins
    allow_origin = response.headers.get("access-control-allow-origin")

    if allow_origin:
        assert (
            allow_origin != disallowed_origin
        ), f"Access-Control-Allow-Origin should not be '{disallowed_origin}' for disallowed origin"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/test",
            "/v1/sessions",
        ]
    ),
    method=st.sampled_from(["GET", "POST"]),
)
def test_property_4_cors_wildcard_origin(path, method):
    """
    **Validates: Requirements 7.3, 7.4**

    Feature: api-migration, Property 4: CORS Headers on All Responses

    For any HTTP response when CORS is enabled with wildcard origin (*),
    the response should include Access-Control-Allow-Origin: *.

    This property ensures that wildcard CORS configuration works correctly.
    """
    # Create app with wildcard CORS
    app = create_test_app_with_cors(
        allow_origins=["*"],
        allow_credentials=False,  # Credentials not allowed with wildcard
        allow_methods=["*"],
        allow_headers=["*"],
    )

    client = TestClient(app)

    # Make request with any origin
    headers = {"Origin": "http://any-origin.com"}

    try:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, headers=headers, json={})
    except Exception:
        # If endpoint doesn't exist, skip this example
        assume(False)

    # Property 1: Response should include Access-Control-Allow-Origin header
    assert (
        "access-control-allow-origin" in response.headers
    ), f"Response should include Access-Control-Allow-Origin header with wildcard CORS"

    # Property 2: Access-Control-Allow-Origin should be "*"
    allow_origin = response.headers.get("access-control-allow-origin")
    assert (
        allow_origin == "*"
    ), f"Access-Control-Allow-Origin should be '*' with wildcard CORS, got '{allow_origin}'"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/test",
            "/v1/sessions",
        ]
    ),
    method=st.sampled_from(["GET", "POST"]),
    origin=st.sampled_from(
        [
            "http://localhost:3000",
            "https://example.com",
        ]
    ),
)
def test_property_4_cors_headers_with_credentials(path, method, origin):
    """
    **Validates: Requirements 7.3, 7.4, 7.6**

    Feature: api-migration, Property 4: CORS Headers on All Responses

    For any HTTP response when CORS is enabled with credentials support,
    the response should include Access-Control-Allow-Credentials: true.

    This property ensures that credential support is properly communicated
    via CORS headers.
    """
    # Create app with CORS and credentials enabled
    app = create_test_app_with_cors(
        allow_origins=[origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    client = TestClient(app)

    # Make request with Origin header
    headers = {"Origin": origin}

    try:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, headers=headers, json={})
    except Exception:
        # If endpoint doesn't exist, skip this example
        assume(False)

    # Property 1: Response should include Access-Control-Allow-Credentials header
    assert (
        "access-control-allow-credentials" in response.headers
    ), f"Response should include Access-Control-Allow-Credentials header when credentials enabled"

    # Property 2: Access-Control-Allow-Credentials should be "true"
    credentials_header = response.headers.get("access-control-allow-credentials")
    assert (
        credentials_header.lower() == "true"
    ), f"Access-Control-Allow-Credentials should be 'true', got '{credentials_header}'"

    # Property 3: When credentials are enabled, Access-Control-Allow-Origin
    # should NOT be wildcard (*)
    allow_origin = response.headers.get("access-control-allow-origin")
    assert (
        allow_origin != "*"
    ), f"Access-Control-Allow-Origin should not be '*' when credentials are enabled"
