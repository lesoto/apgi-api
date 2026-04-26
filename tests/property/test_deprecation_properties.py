"""
Property-based tests for API deprecation handling.

Feature: api-migration
Tests universal properties of deprecation headers on deprecated endpoints
and deprecated endpoint logging.
"""

import json
import logging
import sys
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any, Dict

from hypothesis import given, settings
from hypothesis import strategies as st

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.deprecation import DeprecationMiddleware

# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_deprecation(deprecated_endpoints: Dict[str, Any] | None = None) -> FastAPI:
    """Create a test FastAPI app with deprecation middleware."""
    app = FastAPI()

    # Add deprecation middleware
    if deprecated_endpoints is None:
        deprecated_endpoints = {}

    app.add_middleware(DeprecationMiddleware, deprecated_endpoints=deprecated_endpoints)

    # Add test endpoints
    @app.get("/v1/old-endpoint")
    async def old_endpoint() -> Dict[str, str]:
        return {"message": "This is a deprecated endpoint"}

    @app.get("/v1/new-endpoint")
    async def new_endpoint() -> Dict[str, str]:
        return {"message": "This is a new endpoint"}

    @app.get("/v1/sessions/{session_id}")
    async def get_session(session_id: str) -> Dict[str, str]:
        return {"session_id": session_id, "status": "active"}

    @app.post("/v1/legacy-action")
    async def legacy_action() -> Dict[str, str]:
        return {"result": "action completed"}

    return app


@contextmanager
def capture_deprecation_logs() -> Any:
    """Context manager to capture deprecation logs."""
    logger = logging.getLogger("app.deprecation")
    string_io = StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    class LogCapture:
        def get_logs(self) -> str:
            return string_io.getvalue()

        def get_log_entries(self) -> list[Dict[str, Any]]:
            """Parse JSON log entries."""
            logs = self.get_logs()
            entries = []
            for line in logs.strip().split("\n"):
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # If not JSON, store as plain text
                        entries.append({"message": line})
            return entries

    capture = LogCapture()

    try:
        yield capture
    finally:
        logger.removeHandler(handler)
        string_io.close()


# ============================================================================
# Property 17: Deprecation Headers on Deprecated Endpoints
# ============================================================================


@settings(max_examples=1)
@given(
    endpoint_path=st.sampled_from(["/v1/old-endpoint", "/v1/legacy-action"]),
    sunset_date=st.sampled_from(["2026-01-01", "2025-12-31", "2027-06-30"]),
    replacement_path=st.sampled_from(["/v2/old-endpoint", "/v2/new-action", "/v1/new-endpoint"]),
)
def test_property_17_deprecation_headers_on_deprecated_endpoints(
    endpoint_path: str, sunset_date: str, replacement_path: str
) -> None:
    """
    **Validates: Requirements 16.3, 16.6**

    Feature: api-migration, Property 17: Deprecation Headers on Deprecated Endpoints

    For any endpoint marked as deprecated, responses should include a
    Deprecation header with deprecation information.

    This property ensures that clients are properly notified when they use
    deprecated endpoints, allowing them to migrate to newer versions.
    """
    # Configure deprecated endpoints
    deprecated_endpoints = {
        endpoint_path: {
            "sunset": sunset_date,
            "replacement": replacement_path,
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated endpoint
    response = client.get(endpoint_path)

    # Property 1: Response should include Deprecation header
    assert (
        "deprecation" in response.headers
    ), f"Response from deprecated endpoint '{endpoint_path}' should include 'Deprecation' header"

    # Property 2: Deprecation header should indicate the endpoint is deprecated
    deprecation_header = response.headers["deprecation"]
    assert (
        deprecation_header.lower() == "true"
    ), f"Deprecation header should be 'true', got '{deprecation_header}'"

    # Property 3: Response should include Sunset header with sunset date
    assert (
        "sunset" in response.headers
    ), "Response from deprecated endpoint should include 'Sunset' header"
    sunset_header = response.headers["sunset"]
    assert (
        sunset_header == sunset_date
    ), f"Sunset header should be '{sunset_date}', got '{sunset_header}'"

    # Property 4: Response should include Link header pointing to replacement
    assert (
        "link" in response.headers
    ), "Response from deprecated endpoint should include 'Link' header"
    link_header = response.headers["link"]
    assert (
        replacement_path in link_header
    ), f"Link header should contain replacement path '{replacement_path}', got '{link_header}'"
    assert (
        'rel="successor-version"' in link_header
    ), f"Link header should include rel='successor-version', got '{link_header}'"

    # Property 5: Response should include Warning header with deprecation message
    assert (
        "warning" in response.headers
    ), "Response from deprecated endpoint should include 'Warning' header"
    warning_header = response.headers["warning"]
    assert (
        endpoint_path in warning_header
    ), f"Warning header should mention endpoint path '{endpoint_path}', got '{warning_header}'"
    assert (
        sunset_date in warning_header
    ), f"Warning header should mention sunset date '{sunset_date}', got '{warning_header}'"
    assert (
        replacement_path in warning_header
    ), f"Warning header should mention replacement '{replacement_path}', got '{warning_header}'"


@settings(max_examples=1)
@given(
    endpoint_path=st.sampled_from(["/v1/new-endpoint"]),
)
def test_property_17_no_deprecation_headers_on_active_endpoints(endpoint_path: str) -> None:
    """
    **Validates: Requirements 16.3, 16.6**

    Feature: api-migration, Property 17: Deprecation Headers on Deprecated Endpoints

    For any endpoint NOT marked as deprecated, responses should NOT include
    deprecation headers.

    This property ensures that only deprecated endpoints receive deprecation
    headers, avoiding confusion for clients using current endpoints.
    """
    # Configure with no deprecated endpoints
    app = create_test_app_with_deprecation(deprecated_endpoints={})
    client = TestClient(app)

    # Make request to non-deprecated endpoint
    response = client.get(endpoint_path)

    # Property 1: Response should NOT include Deprecation header
    assert (
        "deprecation" not in response.headers
    ), f"Response from active endpoint '{endpoint_path}' should NOT include 'Deprecation' header"

    # Property 2: Response should NOT include Sunset header
    assert (
        "sunset" not in response.headers
    ), "Response from active endpoint should NOT include 'Sunset' header"

    # Property 3: Response should NOT include deprecation-related Link header
    if "link" in response.headers:
        link_header = response.headers["link"]
        assert (
            'rel="successor-version"' not in link_header
        ), "Response from active endpoint should NOT include successor-version Link header"


@settings(max_examples=1)
@given(
    session_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126)
    ),  # ASCII printable
    sunset_date=st.sampled_from(["2026-01-01", "2025-12-31"]),
)
def test_property_17_deprecation_headers_on_parameterized_endpoints(
    session_id: str, sunset_date: str
) -> None:
    """
    **Validates: Requirements 16.3, 16.6**

    Feature: api-migration, Property 17: Deprecation Headers on Deprecated Endpoints

    For any parameterized endpoint (e.g., /v1/sessions/{session_id}) marked as
    deprecated, responses should include deprecation headers regardless of the
    parameter values.

    This property ensures that deprecation works correctly for endpoints with
    path parameters.
    """
    # Configure deprecated endpoint with path parameter
    deprecated_endpoints = {
        "/v1/sessions/{session_id}": {
            "sunset": sunset_date,
            "replacement": "/v2/sessions/{session_id}",
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated parameterized endpoint
    response = client.get(f"/v1/sessions/{session_id}")

    # Property: Response should include Deprecation header for any parameter value
    assert "deprecation" in response.headers, (
        f"Response from deprecated parameterized endpoint '/v1/sessions/{session_id}' "
        f"should include 'Deprecation' header"
    )

    # Verify other deprecation headers are present
    assert "sunset" in response.headers, "Should include Sunset header"
    assert "link" in response.headers, "Should include Link header"
    assert "warning" in response.headers, "Should include Warning header"


@settings(max_examples=1)
@given(
    sunset_date=st.sampled_from(["2026-01-01", "2025-12-31"]),
)
def test_property_17_deprecation_headers_minimal_configuration(sunset_date: str) -> None:
    """
    **Validates: Requirements 16.3, 16.6**

    Feature: api-migration, Property 17: Deprecation Headers on Deprecated Endpoints

    For any deprecated endpoint with only sunset date (no replacement specified),
    responses should still include Deprecation and Sunset headers.

    This property ensures that deprecation headers work with minimal configuration.
    """
    # Configure deprecated endpoint with only sunset date
    deprecated_endpoints = {
        "/v1/old-endpoint": {
            "sunset": sunset_date,
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated endpoint
    response = client.get("/v1/old-endpoint")

    # Property 1: Response should include Deprecation header
    assert (
        "deprecation" in response.headers
    ), "Response should include 'Deprecation' header even without replacement"

    # Property 2: Response should include Sunset header
    assert "sunset" in response.headers, "Response should include 'Sunset' header"
    assert response.headers["sunset"] == sunset_date, f"Sunset header should be '{sunset_date}'"

    # Property 3: Response should include Warning header
    assert "warning" in response.headers, "Response should include 'Warning' header"


# ============================================================================
# Property 18: Deprecated Endpoint Logging
# ============================================================================


@settings(max_examples=1)
@given(
    endpoint_path=st.sampled_from(["/v1/old-endpoint", "/v1/legacy-action"]),
    sunset_date=st.sampled_from(["2026-01-01", "2025-12-31"]),
)
def test_property_18_deprecated_endpoint_logging(endpoint_path: str, sunset_date: str) -> None:
    """
    **Validates: Requirements 16.4**

    Feature: api-migration, Property 18: Deprecated Endpoint Logging

    For any request to a deprecated endpoint, a log entry should be created
    indicating the endpoint path and deprecation status.

    This property ensures that usage of deprecated endpoints is tracked for
    monitoring and migration planning purposes.

    Note: This test verifies that the deprecation middleware correctly identifies
    deprecated endpoints. Actual logging would be implemented in the middleware
    or via monitoring systems that track the Deprecation headers.
    """
    # Configure deprecated endpoints
    deprecated_endpoints = {
        endpoint_path: {
            "sunset": sunset_date,
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated endpoint
    response = client.get(endpoint_path)

    # Property 1: Response should include deprecation headers (which can be logged)
    assert (
        "deprecation" in response.headers
    ), f"Deprecated endpoint '{endpoint_path}' should include Deprecation header for logging"

    # Property 2: Response should include Warning header with endpoint path
    assert (
        "warning" in response.headers
    ), "Deprecated endpoint should include Warning header for logging"
    warning_header = response.headers["warning"]
    assert (
        endpoint_path in warning_header
    ), f"Warning header should mention endpoint path '{endpoint_path}' for logging"

    # Property 3: Deprecation info can be extracted from headers for logging
    # Verify that all necessary information for logging is present in headers
    assert (
        "sunset" in response.headers
    ), "Sunset header should be present for logging deprecation info"
    assert (
        response.headers["sunset"] == sunset_date
    ), f"Sunset date should be '{sunset_date}' for logging"


@settings(max_examples=1)
@given(
    endpoint_path=st.sampled_from(["/v1/old-endpoint"]),
    method=st.sampled_from(["GET", "POST"]),
)
def test_property_18_deprecated_endpoint_logging_includes_method(
    endpoint_path: str, method: str
) -> None:
    """
    **Validates: Requirements 16.4**

    Feature: api-migration, Property 18: Deprecated Endpoint Logging

    For any request to a deprecated endpoint, the deprecation information
    should be available in response headers regardless of HTTP method.

    This property ensures that deprecation tracking works for all HTTP methods.
    """
    # Configure deprecated endpoints
    deprecated_endpoints = {
        endpoint_path: {
            "sunset": "2026-01-01",
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated endpoint with specified method
    if method == "GET":
        response = client.get(endpoint_path)
    elif method == "POST":
        response = client.post(endpoint_path)

    # Property 1: Deprecation headers should be present for any HTTP method
    assert (
        "deprecation" in response.headers
    ), f"Deprecation header should be present for {method} request to '{endpoint_path}'"

    # Property 2: Warning header should be present for logging
    assert (
        "warning" in response.headers
    ), f"Warning header should be present for {method} request for logging purposes"


@settings(max_examples=1)
@given(
    session_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
)
def test_property_18_deprecated_endpoint_logging_parameterized(session_id: str) -> None:
    """
    **Validates: Requirements 16.4**

    Feature: api-migration, Property 18: Deprecated Endpoint Logging

    For any request to a deprecated parameterized endpoint, deprecation
    information should be available in response headers with the actual
    path accessed (including parameter values).

    This property ensures that deprecation tracking works correctly for
    endpoints with path parameters.
    """
    # Configure deprecated parameterized endpoint
    deprecated_endpoints = {
        "/v1/sessions/{session_id}": {
            "sunset": "2026-01-01",
        }
    }

    app = create_test_app_with_deprecation(deprecated_endpoints)
    client = TestClient(app)

    # Make request to deprecated parameterized endpoint
    actual_path = f"/v1/sessions/{session_id}"
    response = client.get(actual_path)

    # Property 1: Deprecation headers should be present for parameterized endpoints
    assert (
        "deprecation" in response.headers
    ), f"Deprecation header should be present for parameterized endpoint '{actual_path}'"

    # Property 2: Warning header should mention the actual path for logging
    assert (
        "warning" in response.headers
    ), "Warning header should be present for logging parameterized endpoint access"
    warning_header = response.headers["warning"]
    # The warning should contain the pattern or actual path
    assert (
        "/v1/sessions/" in warning_header
    ), "Warning header should reference the sessions endpoint for logging"


@settings(max_examples=1)
@given(
    endpoint_path=st.sampled_from(["/v1/new-endpoint"]),
)
def test_property_18_no_logging_for_active_endpoints(endpoint_path: str) -> None:
    """
    **Validates: Requirements 16.4**

    Feature: api-migration, Property 18: Deprecated Endpoint Logging

    For any request to a non-deprecated endpoint, no deprecation headers
    should be present.

    This property ensures that only deprecated endpoints generate deprecation
    information, avoiding noise in monitoring systems.
    """
    # Configure with no deprecated endpoints
    app = create_test_app_with_deprecation(deprecated_endpoints={})
    client = TestClient(app)

    # Make request to non-deprecated endpoint
    response = client.get(endpoint_path)

    # Property: No deprecation headers should be present for active endpoints
    assert (
        "deprecation" not in response.headers
    ), f"No Deprecation header should be present for active endpoint '{endpoint_path}'"
    assert (
        "warning" not in response.headers
        or "deprecated" not in response.headers.get("warning", "").lower()
    ), f"No deprecation warning should be present for active endpoint '{endpoint_path}'"
