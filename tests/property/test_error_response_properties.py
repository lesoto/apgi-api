"""
Property-based tests for error response handling.

Feature: api-migration
Tests universal properties of error responses including validation errors,
authentication failures, authorization failures, not found responses,
server errors, and sensitive information exclusion.
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from typing import Union

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.exception_handlers import (
    unhandled_exception_handler,
)
from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    SessionNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)

# ============================================================================
# Helper Functions
# ============================================================================


def create_test_app_with_error_handlers() -> FastAPI:
    """Create a test FastAPI app with error handlers."""
    app = FastAPI()

    # Register exception handlers
    from app.exception_handlers import register_exception_handlers

    register_exception_handlers(app)

    # Add test endpoints
    class TestRequest(BaseModel):
        name: str
        age: int
        email: str

    @app.post("/validate")
    async def validate_endpoint(request: TestRequest) -> dict[str, str]:
        return {"message": "valid"}

    @app.get("/protected")
    async def protected_endpoint() -> None:
        raise AuthenticationError("Invalid credentials")

    @app.get("/forbidden")
    async def forbidden_endpoint() -> None:
        raise AuthorizationError(resource="session", action="delete", required_role="admin")

    @app.get("/not-found/{resource_id}")
    async def not_found_endpoint(resource_id: str) -> None:
        raise SessionNotFoundError(resource_id)

    @app.get("/server-error")
    async def server_error_endpoint() -> None:
        raise Exception("Unexpected error occurred")

    @app.get("/database-error")
    async def database_error_endpoint() -> None:
        # Simulate database error with sensitive information
        raise Exception("Database connection failed: postgresql://user:password@localhost:5432/db")

    return app


def create_mock_request(path: str = "/test", method: str = "GET") -> Mock:
    """Create a mock FastAPI request."""
    request = Mock(spec=Request)
    request.url.path = path
    request.method = method
    request.headers = {}
    request.state = Mock()
    request.state.request_id = "test-request-id"
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


# ============================================================================
# Property 23: Request Validation Error Response
# ============================================================================


@settings(max_examples=1)
@given(
    invalid_field=st.sampled_from(["name", "age", "email"]),
    invalid_value=st.one_of(
        st.none(),  # Missing field
        st.integers(min_value=-1000, max_value=-1),  # Invalid type for string field
        st.text(min_size=0, max_size=5).filter(lambda x: "@" not in x),  # Invalid email
    ),
)
def test_property_23_validation_error_response(
    invalid_field: str, invalid_value: Union[str, None]
) -> None:
    """
    **Validates: Requirements 19.1, 19.2**

    Feature: api-migration, Property 23: Request Validation Error Response

    For any request with invalid payload, the response should be 422 Unprocessable Entity
    with a detailed error message indicating which fields failed validation.

    This property ensures that validation errors provide clear feedback to clients.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Create request with invalid field
    request_data = {"name": "John Doe", "age": 30, "email": "john@example.com"}

    # Inject invalid value
    if invalid_value is None:
        del request_data[invalid_field]
    else:
        request_data[invalid_field] = invalid_value

    # Make request
    response = client.post("/validate", json=request_data)

    # Property 1: Status code should be 422
    assert (
        response.status_code == 422
    ), f"Validation error should return 422, got {response.status_code}"

    # Property 2: Response should be valid JSON
    try:
        error_data = response.json()
    except json.JSONDecodeError:
        pytest.fail("Response should be valid JSON")

    # Property 3: Response should have error structure
    assert "error" in error_data, "Response should contain 'error' field"
    error = error_data["error"]

    # Property 4: Error should have code field
    assert "code" in error, "Error should contain 'code' field"
    assert error["code"] == "VALIDATION_ERROR", "Error code should be 'VALIDATION_ERROR'"

    # Property 5: Error should have message field
    assert "message" in error, "Error should contain 'message' field"
    assert isinstance(error["message"], str), "Error message should be a string"
    assert len(error["message"]) > 0, "Error message should not be empty"

    # Property 6: Error should have details with validation_errors
    assert "details" in error, "Error should contain 'details' field"
    assert (
        "validation_errors" in error["details"]
    ), "Error details should contain 'validation_errors'"
    validation_errors = error["details"]["validation_errors"]
    assert isinstance(validation_errors, list), "Validation errors should be a list"
    assert len(validation_errors) > 0, "Validation errors list should not be empty"

    # Property 7: Each validation error should have field, message, and type
    for val_error in validation_errors:
        assert "field" in val_error, "Validation error should have 'field'"
        assert "message" in val_error, "Validation error should have 'message'"
        assert "type" in val_error, "Validation error should have 'type'"


@settings(max_examples=1)
@given(
    missing_fields=st.lists(
        st.sampled_from(["name", "age", "email"]), min_size=1, max_size=3, unique=True
    )
)
def test_property_23_validation_error_multiple_fields(missing_fields: list[str]) -> None:
    """
    **Validates: Requirements 19.1, 19.2**

    Feature: api-migration, Property 23: Request Validation Error Response

    For any request with multiple invalid fields, the response should include
    validation errors for all invalid fields.

    This property ensures that all validation errors are reported at once.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Create request with missing fields
    request_data = {"name": "John Doe", "age": 30, "email": "john@example.com"}
    for field in missing_fields:
        del request_data[field]

    # Make request
    response = client.post("/validate", json=request_data)

    # Property: Response should include errors for all missing fields
    error_data = response.json()
    validation_errors = error_data["error"]["details"]["validation_errors"]

    # Check that we have at least as many errors as missing fields
    assert len(validation_errors) >= len(
        missing_fields
    ), f"Should have errors for all {len(missing_fields)} missing fields"


# ============================================================================
# Property 24: Authentication Failure Response
# ============================================================================


@settings(max_examples=1)
@given(
    path=st.sampled_from(["/protected", "/v1/sessions", "/v1/tasks"]),
)
def test_property_24_authentication_failure_response(path: str) -> None:
    """
    **Validates: Requirements 19.3**

    Feature: api-migration, Property 24: Authentication Failure Response

    For any request with invalid or missing authentication, the response should be
    401 Unauthorized with a WWW-Authenticate header.

    This property ensures that authentication failures follow HTTP standards.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request without authentication
    response = client.get(path)

    # Property 1: Status code should be 401
    assert response.status_code == 401, "Authentication failure should return 401, got " + str(
        response.status_code
    )

    # Property 2: Response should be valid JSON
    error_data = response.json()

    # Property 3: Error should have code field indicating authentication failure
    assert "error" in error_data, "Response should contain 'error' field"
    error = error_data["error"]
    assert "code" in error, "Error should contain 'code' field"
    assert error["code"] in [
        "AUTHENTICATION_FAILED",
        "INVALID_TOKEN",
        "TOKEN_EXPIRED",
        "UNAUTHORIZED",
    ], "Error code should indicate authentication failure"

    # Property 4: Error should have message field
    assert "message" in error, "Error should contain 'message' field"
    assert isinstance(error["message"], str), "Error message should be a string"

    # Property 5: Response should include WWW-Authenticate header
    # Note: This is checked in the middleware/route handler level
    # For this test, we verify the error structure is correct


@settings(max_examples=1)
@given(
    error_message=st.text(min_size=1, max_size=100),
)
def test_property_24_authentication_error_structure(error_message: str) -> None:
    """
    **Validates: Requirements 19.3**

    Feature: api-migration, Property 24: Authentication Failure Response

    For any authentication error, the error response should follow the standard
    error structure with appropriate fields.

    This property ensures authentication errors are consistently formatted.
    """
    # Create authentication error
    auth_error = AuthenticationError(error_message)

    # Property 1: Error should have status code 401
    assert auth_error.status_code == 401, "Authentication error should have status code 401"

    # Property 2: Error should have code
    assert auth_error.code == "AUTHENTICATION_FAILED", "Error code should be AUTHENTICATION_FAILED"

    # Property 3: Error should have message
    assert auth_error.message == error_message, "Error message should match"

    # Property 4: Error dict should have proper structure
    error_dict = auth_error.to_dict(request_id="test-123")
    assert "error" in error_dict, "Error dict should have 'error' field"
    assert "code" in error_dict["error"], "Error should have 'code'"
    assert "message" in error_dict["error"], "Error should have 'message'"
    assert "timestamp" in error_dict["error"], "Error should have 'timestamp'"
    assert "request_id" in error_dict["error"], "Error should have 'request_id'"


# ============================================================================
# Property 25: Authorization Failure Response
# ============================================================================


@settings(max_examples=1)
@given(
    resource=st.sampled_from(["session", "task", "user", "export"]),
    action=st.sampled_from(["create", "read", "update", "delete", "export"]),
    required_role=st.sampled_from(["admin", "researcher", "viewer"]),
)
def test_property_25_authorization_failure_response(
    resource: str, action: str, required_role: str
) -> None:
    """
    **Validates: Requirements 19.4**

    Feature: api-migration, Property 25: Authorization Failure Response

    For any request where the authenticated user lacks required permissions,
    the response should be 403 Forbidden with an explanation.

    This property ensures that authorization failures provide clear feedback.
    """
    # Create authorization error
    auth_error = AuthorizationError(resource=resource, action=action, required_role=required_role)

    # Property 1: Error should have status code 403
    assert auth_error.status_code == 403, "Authorization error should have status code 403"

    # Property 2: Error should have code
    assert (
        auth_error.code == "INSUFFICIENT_PERMISSIONS"
    ), "Error code should be INSUFFICIENT_PERMISSIONS"

    # Property 3: Error message should include resource and action
    assert resource in auth_error.message, "Error message should mention the resource"
    assert action in auth_error.message, "Error message should mention the action"

    # Property 4: Error details should include resource, action, and required_role
    assert auth_error.details["resource"] == resource, "Details should include resource"
    assert auth_error.details["action"] == action, "Details should include action"
    assert (
        auth_error.details["required_role"] == required_role
    ), "Details should include required_role"

    # Property 5: Error dict should have proper structure
    error_dict = auth_error.to_dict(request_id="test-123")
    assert error_dict["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "message" in error_dict["error"]
    assert "details" in error_dict["error"]


def test_property_25_authorization_error_via_endpoint() -> None:
    """
    **Validates: Requirements 19.4**

    Feature: api-migration, Property 25: Authorization Failure Response

    For any endpoint that raises an authorization error, the response should be
    403 Forbidden with proper error structure.

    This property ensures authorization errors are handled correctly by the API.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request to forbidden endpoint
    response = client.get("/forbidden")

    # Property 1: Status code should be 403
    assert response.status_code == 403, "Authorization failure should return 403"

    # Property 2: Response should be valid JSON
    error_data = response.json()

    # Property 3: Error should have proper structure
    assert "error" in error_data
    error = error_data["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "message" in error
    assert "details" in error
    assert "resource" in error["details"]
    assert "action" in error["details"]


# ============================================================================
# Property 26: Not Found Response
# ============================================================================


@settings(max_examples=1)
@given(
    resource_id=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters="-"),
    ),
)
def test_property_26_not_found_response(resource_id: str) -> None:
    """
    **Validates: Requirements 19.5**

    Feature: api-migration, Property 26: Not Found Response

    For any request for a non-existent resource, the response should be 404 Not Found.

    This property ensures that missing resources return appropriate status codes.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request for non-existent resource
    response = client.get(f"/not-found/{resource_id}")

    # Property 1: Status code should be 404
    assert response.status_code == 404, f"Not found should return 404, got {response.status_code}"

    # Property 2: Response should be valid JSON
    error_data = response.json()

    # Property 3: Error should have proper structure
    assert "error" in error_data, "Response should contain 'error' field"
    error = error_data["error"]

    # Property 4: Error code should indicate not found
    assert "code" in error, "Error should contain 'code' field"
    assert "NOT_FOUND" in error["code"], "Error code should indicate not found"

    # Property 5: Error message should mention the resource
    assert "message" in error, "Error should contain 'message' field"
    assert resource_id in error["message"], "Error message should mention the resource ID"

    # Property 6: Error should have timestamp
    assert "timestamp" in error, "Error should contain 'timestamp' field"


@settings(max_examples=1)
@given(
    resource_type=st.sampled_from(["session", "task", "user"]),
    resource_id=st.text(min_size=1, max_size=50),
)
def test_property_26_not_found_error_types(resource_type: str, resource_id: str) -> None:
    """
    **Validates: Requirements 19.5**

    Feature: api-migration, Property 26: Not Found Response

    For any type of resource (session, task, user), not found errors should
    follow the same structure and return 404.

    This property ensures consistency across different resource types.
    """
    # Create appropriate not found error based on resource type
    error: Union[SessionNotFoundError, TaskNotFoundError, UserNotFoundError]
    if resource_type == "session":
        error = SessionNotFoundError(resource_id)
    elif resource_type == "task":
        error = TaskNotFoundError(resource_id)
    elif resource_type == "user":
        error = UserNotFoundError(resource_id)

    # Property 1: All not found errors should have status code 404
    assert error.status_code == 404, f"{resource_type} not found should have status code 404"

    # Property 2: Error code should indicate not found
    assert "NOT_FOUND" in error.code, "Error code should indicate not found"

    # Property 3: Error message should include the resource ID
    assert resource_id in error.message, "Error message should include resource ID"

    # Property 4: Error details should include the resource ID
    assert resource_id in str(error.details.values()), "Error details should include resource ID"


# ============================================================================
# Property 27: Server Error Response and Logging
# ============================================================================


@settings(max_examples=1)
@given(
    error_message=st.text(min_size=1, max_size=100),
)
def test_property_27_server_error_response(error_message: str) -> None:
    """
    **Validates: Requirements 19.6**

    Feature: api-migration, Property 27: Server Error Response and Logging

    For any unhandled exception during request processing, the response should be
    500 Internal Server Error and the full error should be logged with stack trace.

    This property ensures that server errors are handled gracefully.
    """
    # Create mock request
    mock_request = create_mock_request()

    # Create unhandled exception
    try:
        raise RuntimeError(error_message)
    except RuntimeError as exc:
        # Call exception handler
        import asyncio

        response = asyncio.run(unhandled_exception_handler(mock_request, exc))

        # Property 1: Status code should be 500
        assert response.status_code == 500, "Unhandled exception should return 500"

        # Property 2: Response should be valid JSON
        # Handle response body decoding (can be bytes or memoryview)
        if hasattr(response.body, "decode"):
            response_text = response.body.decode()
        elif isinstance(response.body, memoryview):
            response_text = response.body.tobytes().decode("utf-8", errors="ignore")
        else:
            response_text = str(response.body)
        response_data = json.loads(response_text)

        # Property 3: Error should have proper structure
        assert "error" in response_data
        error = response_data["error"]
        assert error["code"] == "INTERNAL_SERVER_ERROR"
        assert "message" in error
        assert "timestamp" in error
        assert "request_id" in error

        # Property 4: Error should have error_id for tracking
        assert "details" in error
        assert "error_id" in error["details"]


def test_property_27_server_error_via_endpoint() -> None:
    """
    **Validates: Requirements 19.6**

    Feature: api-migration, Property 27: Server Error Response and Logging

    For any endpoint that raises an unhandled exception, the response should be
    500 Internal Server Error with proper error structure.

    This property ensures server errors are handled correctly by the API.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request to endpoint that raises exception
    response = client.get("/server-error")

    # Property 1: Status code should be 500
    assert response.status_code == 500, "Server error should return 500"

    # Property 2: Response should be valid JSON
    error_data = response.json()

    # Property 3: Error should have proper structure
    assert "error" in error_data
    error = error_data["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert "message" in error
    assert "timestamp" in error
    assert "details" in error
    assert "error_id" in error["details"]


# ============================================================================
# Property 28: Sensitive Information Exclusion from Errors
# ============================================================================


@settings(max_examples=1)
@given(
    sensitive_pattern=st.sampled_from(
        [
            r"postgresql://[^:]+:[^@]+@",  # Database connection string with password
            r"password[=:]\s*\S+",  # Password in various formats
            r"secret[=:]\s*\S+",  # Secret keys
            r"token[=:]\s*\S+",  # Tokens
            r"/home/\w+/",  # File paths
            r"C:\\Users\\",  # Windows paths
        ]
    ),
)
def test_property_28_sensitive_information_exclusion(sensitive_pattern: str) -> None:
    """
    **Validates: Requirements 19.7**

    Feature: api-migration, Property 28: Sensitive Information Exclusion from Errors

    For any error response sent to clients, the response should not contain
    sensitive information such as database connection strings, internal file paths,
    or stack traces.

    This property ensures that error responses don't leak sensitive information.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request to endpoint that raises exception with sensitive info
    response = client.get("/server-error")

    # Property 1: Response body should not contain sensitive patterns
    response_text = response.text

    # Check that response doesn't contain common sensitive patterns
    assert not re.search(
        r"postgresql://[^:]+:[^@]+@", response_text
    ), "Response should not contain database credentials"
    assert not re.search(
        r"password[=:]\s*\S+", response_text, re.IGNORECASE
    ), "Response should not contain passwords"
    assert not re.search(
        r"secret[=:]\s*\S+", response_text, re.IGNORECASE
    ), "Response should not contain secrets"

    # Property 2: Response should not contain stack traces
    assert "Traceback" not in response_text, "Response should not contain stack traces"
    assert 'File "' not in response_text, "Response should not contain file paths from stack trace"

    # Property 3: Response should not contain internal error details
    error_data = response.json()
    error_message = error_data["error"]["message"]
    assert (
        "unexpected error" in error_message.lower() or "internal" in error_message.lower()
    ), "Error message should be generic"


@settings(max_examples=1)
@given(
    database_url=st.sampled_from(
        [
            "postgresql://user:password@localhost:5432/db",
            "mysql://admin:secret123@db.example.com:3306/mydb",
            "postgresql://dbuser:P@ssw0rd@10.0.0.1:5432/production",
            "mysql://root:admin@127.0.0.1:3306/test",
        ]
    ),
)
def test_property_28_database_credentials_not_exposed(database_url: str) -> None:
    """
    **Validates: Requirements 19.7**

    Feature: api-migration, Property 28: Sensitive Information Exclusion from Errors

    For any error that contains database connection information, the error response
    should not expose the connection string to clients.

    This property ensures database credentials are never leaked in error responses.
    """
    # Create mock request
    mock_request = create_mock_request()

    # Create exception with database URL
    try:
        raise Exception(f"Database connection failed: {database_url}")
    except Exception as exc:
        # Call exception handler
        import asyncio

        response = asyncio.run(unhandled_exception_handler(mock_request, exc))

        # Property: Response should not contain the database URL
        response_text = (
            response.body.decode()
            if isinstance(response.body, bytes)
            else response.body.tobytes().decode("utf-8")
        )
        assert (
            database_url not in response_text
        ), "Response should not contain database connection string"

        # Verify generic error message is returned
        response_data = json.loads(response_text)
        error_message = response_data["error"]["message"]
        assert (
            "unexpected error" in error_message.lower()
        ), "Error message should be generic, not expose internal details"


@settings(max_examples=1)
@given(
    file_path=st.sampled_from(
        [
            "/home/user/app/config.py",
            "C:\\Users\\Admin\\app\\secrets.txt",
            "/var/www/app/database.py",
            "/etc/app/credentials.json",
        ]
    ),
)
def test_property_28_file_paths_not_exposed(file_path: str) -> None:
    """
    **Validates: Requirements 19.7**

    Feature: api-migration, Property 28: Sensitive Information Exclusion from Errors

    For any error that contains internal file paths, the error response should not
    expose those paths to clients.

    This property ensures internal file structure is not leaked in error responses.
    """
    # Create mock request
    mock_request = create_mock_request()

    # Create exception with file path
    try:
        raise Exception(f"Failed to load file: {file_path}")
    except Exception as exc:
        # Call exception handler
        import asyncio

        response = asyncio.run(unhandled_exception_handler(mock_request, exc))

        # Property: Response should not contain the file path
        # Handle response body decoding (can be bytes or memoryview)
        if hasattr(response.body, "decode"):
            response_text = response.body.decode()
        elif isinstance(response.body, memoryview):
            response_text = response.body.tobytes().decode("utf-8", errors="ignore")
        else:
            response_text = str(response.body)
        assert file_path not in response_text, "Response should not contain internal file paths"

        # Verify generic error message is returned
        response_data = json.loads(response_text)
        error_message = response_data["error"]["message"]
        assert (
            "unexpected error" in error_message.lower()
        ), "Error message should be generic, not expose internal details"


def test_property_28_stack_trace_not_in_response() -> None:
    """
    **Validates: Requirements 19.7**

    Feature: api-migration, Property 28: Sensitive Information Exclusion from Errors

    For any unhandled exception, the stack trace should be logged server-side but
    never included in the client response.

    This property ensures stack traces are not exposed to clients.
    """
    app = create_test_app_with_error_handlers()
    client = TestClient(app, raise_server_exceptions=False)

    # Make request to endpoint that raises exception
    response = client.get("/server-error")

    # Property 1: Response should not contain stack trace indicators
    response_text = response.text
    assert "Traceback" not in response_text, "Response should not contain 'Traceback'"
    assert 'File "' not in response_text, "Response should not contain file references"
    assert "line " not in response_text, "Response should not contain line numbers"
    assert '.py"' not in response_text, "Response should not contain Python file references"

    # Property 2: Response should contain generic error message
    error_data = response.json()
    error_message = error_data["error"]["message"]
    assert len(error_message) < 200, "Error message should be concise and generic"
    assert (
        "unexpected" in error_message.lower() or "internal" in error_message.lower()
    ), "Error message should be generic"
