"""
Comprehensive unit tests for app/exceptions.py to achieve ≥80% coverage.

Tests cover:
- All custom exception classes
- Exception instantiation with various arguments
- Exception inheritance hierarchy
- Exception message formatting and attributes
- Exception raising and catching in realistic scenarios
- to_dict() method with and without request_id
"""

import pytest
from datetime import datetime
from app.exceptions import (
    APIError,
    SessionNotFoundError,
    SessionStateConflictError,
    TaskNotFoundError,
    InvalidTaskTypeError,
    ValidationError,
    InvalidConfigurationError,
    AuthenticationError,
    InvalidTokenError,
    ExpiredTokenError,
    AuthorizationError,
    UserNotFoundError,
    RateLimitExceededError,
    ServiceUnavailableError,
    DatabaseError,
    ExportFormatError,
    NoDataAvailableError,
    InternalServerError,
)


class TestAPIErrorBase:
    """Test base APIError class."""

    def test_api_error_initialization(self) -> None:
        """Test APIError initialization with all parameters."""
        error = APIError(
            code="TEST_ERROR",
            message="Test error message",
            status_code=400,
            details={"key": "value"},
        )
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.status_code == 400
        assert error.details == {"key": "value"}
        assert str(error) == "Test error message"

    def test_api_error_initialization_without_details(self) -> None:
        """Test APIError initialization without details."""
        error = APIError(code="TEST_ERROR", message="Test error", status_code=500)
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error"
        assert error.status_code == 500
        assert error.details == {}

    def test_api_error_is_exception(self) -> None:
        """Test that APIError is an Exception."""
        error = APIError("CODE", "message", 400)
        assert isinstance(error, Exception)

    def test_api_error_to_dict_with_request_id(self) -> None:
        """Test to_dict() method with request_id."""
        error = APIError(
            code="TEST_CODE", message="Test message", status_code=400, details={"field": "value"}
        )
        result = error.to_dict(request_id="req_12345")

        assert "error" in result
        assert result["error"]["code"] == "TEST_CODE"
        assert result["error"]["message"] == "Test message"
        assert result["error"]["request_id"] == "req_12345"
        assert result["error"]["details"] == {"field": "value"}
        assert "timestamp" in result["error"]

    def test_api_error_to_dict_without_request_id(self) -> None:
        """Test to_dict() method without request_id."""
        error = APIError(code="TEST_CODE", message="Test message", status_code=400)
        result = error.to_dict()

        assert result["error"]["request_id"] is None
        assert "timestamp" in result["error"]

    def test_api_error_to_dict_timestamp_format(self) -> None:
        """Test that to_dict() includes valid ISO timestamp."""
        error = APIError("CODE", "message", 400)
        result = error.to_dict()

        timestamp_str = result["error"]["timestamp"]
        assert timestamp_str.endswith("Z")
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(timestamp_str.rstrip("Z"))


class TestSessionExceptions:
    """Test session-related exceptions."""

    def test_session_not_found_error(self) -> None:
        """Test SessionNotFoundError initialization."""
        error = SessionNotFoundError("session_123")

        assert error.code == "SESSION_NOT_FOUND"
        assert "session_123" in error.message
        assert error.status_code == 404
        assert error.details["session_id"] == "session_123"

    def test_session_not_found_error_inheritance(self) -> None:
        """Test SessionNotFoundError inherits from APIError."""
        error = SessionNotFoundError("session_123")
        assert isinstance(error, APIError)
        assert isinstance(error, Exception)

    def test_session_state_conflict_error(self) -> None:
        """Test SessionStateConflictError initialization."""
        error = SessionStateConflictError(
            session_id="session_456", current_state="running", attempted_action="start"
        )

        assert error.code == "SESSION_STATE_CONFLICT"
        assert "running" in error.message
        assert "start" in error.message
        assert error.status_code == 409
        assert error.details["session_id"] == "session_456"
        assert error.details["current_state"] == "running"
        assert error.details["attempted_action"] == "start"

    def test_session_state_conflict_error_inheritance(self) -> None:
        """Test SessionStateConflictError inherits from APIError."""
        error = SessionStateConflictError("id", "state", "action")
        assert isinstance(error, APIError)


class TestTaskExceptions:
    """Test task-related exceptions."""

    def test_task_not_found_error(self) -> None:
        """Test TaskNotFoundError initialization."""
        error = TaskNotFoundError("task_789")

        assert error.code == "TASK_NOT_FOUND"
        assert "task_789" in error.message
        assert error.status_code == 404
        assert error.details["task_id"] == "task_789"

    def test_task_not_found_error_inheritance(self) -> None:
        """Test TaskNotFoundError inherits from APIError."""
        error = TaskNotFoundError("task_789")
        assert isinstance(error, APIError)

    def test_invalid_task_type_error(self) -> None:
        """Test InvalidTaskTypeError initialization."""
        valid_types = ["type1", "type2", "type3"]
        error = InvalidTaskTypeError("invalid_type", valid_types)

        assert error.code == "INVALID_TASK_TYPE"
        assert "invalid_type" in error.message
        assert error.status_code == 400
        assert error.details["task_type"] == "invalid_type"
        assert error.details["valid_types"] == valid_types

    def test_invalid_task_type_error_inheritance(self) -> None:
        """Test InvalidTaskTypeError inherits from APIError."""
        error = InvalidTaskTypeError("bad", [])
        assert isinstance(error, APIError)


class TestValidationExceptions:
    """Test validation-related exceptions."""

    def test_validation_error(self) -> None:
        """Test ValidationError initialization."""
        validation_errors = [
            {"field": "email", "message": "Invalid email"},
            {"field": "password", "message": "Too short"},
        ]
        error = ValidationError("Validation failed", validation_errors)

        assert error.code == "VALIDATION_ERROR"
        assert error.message == "Validation failed"
        assert error.status_code == 422
        assert error.details["validation_errors"] == validation_errors

    def test_validation_error_without_errors_list(self) -> None:
        """Test ValidationError without validation_errors."""
        error = ValidationError("Validation failed")

        assert error.code == "VALIDATION_ERROR"
        assert error.details["validation_errors"] == []

    def test_validation_error_inheritance(self) -> None:
        """Test ValidationError inherits from APIError."""
        error = ValidationError("message")
        assert isinstance(error, APIError)

    def test_invalid_configuration_error(self) -> None:
        """Test InvalidConfigurationError initialization."""
        config_errors = {"jwt_secret": "Too short", "db_url": "Invalid"}
        error = InvalidConfigurationError("Config invalid", config_errors)

        assert error.code == "INVALID_CONFIGURATION"
        assert error.message == "Config invalid"
        assert error.status_code == 400
        assert error.details["config_errors"] == config_errors

    def test_invalid_configuration_error_without_errors(self) -> None:
        """Test InvalidConfigurationError without config_errors."""
        error = InvalidConfigurationError("Config invalid")

        assert error.details["config_errors"] == {}

    def test_invalid_configuration_error_inheritance(self) -> None:
        """Test InvalidConfigurationError inherits from APIError."""
        error = InvalidConfigurationError("message")
        assert isinstance(error, APIError)


class TestAuthenticationExceptions:
    """Test authentication and authorization exceptions."""

    def test_authentication_error_default_message(self) -> None:
        """Test AuthenticationError with default message."""
        error = AuthenticationError()

        assert error.code == "AUTHENTICATION_FAILED"
        assert error.message == "Authentication failed"
        assert error.status_code == 401
        assert error.details == {}

    def test_authentication_error_custom_message(self) -> None:
        """Test AuthenticationError with custom message."""
        error = AuthenticationError("Invalid credentials")

        assert error.message == "Invalid credentials"
        assert error.code == "AUTHENTICATION_FAILED"

    def test_authentication_error_inheritance(self) -> None:
        """Test AuthenticationError inherits from APIError."""
        error = AuthenticationError()
        assert isinstance(error, APIError)

    def test_invalid_token_error_default_reason(self) -> None:
        """Test InvalidTokenError with default reason."""
        error = InvalidTokenError()

        assert error.code == "INVALID_TOKEN"
        assert error.message == "Token is invalid"
        assert error.status_code == 401
        assert error.details["reason"] == "Token is invalid"

    def test_invalid_token_error_custom_reason(self) -> None:
        """Test InvalidTokenError with custom reason."""
        error = InvalidTokenError("Signature mismatch")

        assert error.message == "Signature mismatch"
        assert error.details["reason"] == "Signature mismatch"

    def test_invalid_token_error_inheritance(self) -> None:
        """Test InvalidTokenError inherits from APIError."""
        error = InvalidTokenError()
        assert isinstance(error, APIError)

    def test_expired_token_error_default_message(self) -> None:
        """Test ExpiredTokenError with default message."""
        error = ExpiredTokenError()

        assert error.code == "TOKEN_EXPIRED"
        assert error.message == "Token has expired"
        assert error.status_code == 401

    def test_expired_token_error_custom_message(self) -> None:
        """Test ExpiredTokenError with custom message."""
        error = ExpiredTokenError("Token expired 1 hour ago")

        assert error.message == "Token expired 1 hour ago"

    def test_expired_token_error_inheritance(self) -> None:
        """Test ExpiredTokenError inherits from APIError."""
        error = ExpiredTokenError()
        assert isinstance(error, APIError)

    def test_authorization_error_with_role(self) -> None:
        """Test AuthorizationError with required_role."""
        error = AuthorizationError(resource="admin_panel", action="access", required_role="admin")

        assert error.code == "INSUFFICIENT_PERMISSIONS"
        assert "access" in error.message
        assert "admin_panel" in error.message
        assert error.status_code == 403
        assert error.details["resource"] == "admin_panel"
        assert error.details["action"] == "access"
        assert error.details["required_role"] == "admin"

    def test_authorization_error_without_role(self) -> None:
        """Test AuthorizationError without required_role."""
        error = AuthorizationError(resource="document", action="delete")

        assert error.code == "INSUFFICIENT_PERMISSIONS"
        assert "required_role" not in error.details

    def test_authorization_error_inheritance(self) -> None:
        """Test AuthorizationError inherits from APIError."""
        error = AuthorizationError("resource", "action")
        assert isinstance(error, APIError)


class TestUserExceptions:
    """Test user management exceptions."""

    def test_user_not_found_error(self) -> None:
        """Test UserNotFoundError initialization."""
        error = UserNotFoundError("user_123")

        assert error.code == "USER_NOT_FOUND"
        assert "user_123" in error.message
        assert error.status_code == 404
        assert error.details["user_id"] == "user_123"

    def test_user_not_found_error_inheritance(self) -> None:
        """Test UserNotFoundError inherits from APIError."""
        error = UserNotFoundError("user_123")
        assert isinstance(error, APIError)


class TestRateLimitException:
    """Test rate limiting exception."""

    def test_rate_limit_exceeded_error(self) -> None:
        """Test RateLimitExceededError initialization."""
        error = RateLimitExceededError(limit=100, window_seconds=60, retry_after=30)

        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert "100" in error.message
        assert "60" in error.message
        assert error.status_code == 429
        assert error.details["limit"] == 100
        assert error.details["window_seconds"] == 60
        assert error.details["retry_after"] == 30

    def test_rate_limit_exceeded_error_inheritance(self) -> None:
        """Test RateLimitExceededError inherits from APIError."""
        error = RateLimitExceededError(100, 60, 30)
        assert isinstance(error, APIError)


class TestResourceExceptions:
    """Test resource-related exceptions."""

    def test_service_unavailable_error_with_reason(self) -> None:
        """Test ServiceUnavailableError with reason."""
        error = ServiceUnavailableError(service="redis", reason="Connection refused")

        assert error.code == "SERVICE_UNAVAILABLE"
        assert "redis" in error.message
        assert "Connection refused" in error.message
        assert error.status_code == 503
        assert error.details["service"] == "redis"
        assert error.details["reason"] == "Connection refused"

    def test_service_unavailable_error_without_reason(self) -> None:
        """Test ServiceUnavailableError without reason."""
        error = ServiceUnavailableError(service="database")

        assert error.code == "SERVICE_UNAVAILABLE"
        assert "database" in error.message
        assert error.details["service"] == "database"
        assert error.details["reason"] is None

    def test_service_unavailable_error_inheritance(self) -> None:
        """Test ServiceUnavailableError inherits from APIError."""
        error = ServiceUnavailableError("service")
        assert isinstance(error, APIError)

    def test_database_error_with_reason(self) -> None:
        """Test DatabaseError with reason."""
        error = DatabaseError(operation="insert_user", reason="Unique constraint violation")

        assert error.code == "DATABASE_ERROR"
        assert "insert_user" in error.message
        assert "Unique constraint violation" in error.message
        assert error.status_code == 500
        assert error.details["operation"] == "insert_user"
        assert error.details["reason"] == "Unique constraint violation"

    def test_database_error_without_reason(self) -> None:
        """Test DatabaseError without reason."""
        error = DatabaseError(operation="query_sessions")

        assert error.code == "DATABASE_ERROR"
        assert "query_sessions" in error.message
        assert error.details["operation"] == "query_sessions"
        assert error.details["reason"] is None

    def test_database_error_inheritance(self) -> None:
        """Test DatabaseError inherits from APIError."""
        error = DatabaseError("operation")
        assert isinstance(error, APIError)


class TestExportExceptions:
    """Test data export exceptions."""

    def test_export_format_error(self) -> None:
        """Test ExportFormatError initialization."""
        supported = ["csv", "json", "xml"]
        error = ExportFormatError("pdf", supported)

        assert error.code == "UNSUPPORTED_EXPORT_FORMAT"
        assert "pdf" in error.message
        assert error.status_code == 400
        assert error.details["requested_format"] == "pdf"
        assert error.details["supported_formats"] == supported

    def test_export_format_error_inheritance(self) -> None:
        """Test ExportFormatError inherits from APIError."""
        error = ExportFormatError("format", [])
        assert isinstance(error, APIError)

    def test_no_data_available_error(self) -> None:
        """Test NoDataAvailableError initialization."""
        error = NoDataAvailableError(session_id="session_999", data_type="metrics")

        assert error.code == "NO_DATA_AVAILABLE"
        assert "metrics" in error.message
        assert "session_999" in error.message
        assert error.status_code == 404
        assert error.details["session_id"] == "session_999"
        assert error.details["data_type"] == "metrics"

    def test_no_data_available_error_inheritance(self) -> None:
        """Test NoDataAvailableError inherits from APIError."""
        error = NoDataAvailableError("session", "type")
        assert isinstance(error, APIError)


class TestInternalServerError:
    """Test internal server error exception."""

    def test_internal_server_error_default_message(self) -> None:
        """Test InternalServerError with default message."""
        error = InternalServerError()

        assert error.code == "INTERNAL_SERVER_ERROR"
        assert error.message == "An unexpected error occurred"
        assert error.status_code == 500
        assert error.details == {}

    def test_internal_server_error_custom_message(self) -> None:
        """Test InternalServerError with custom message."""
        error = InternalServerError("Something went wrong")

        assert error.message == "Something went wrong"

    def test_internal_server_error_with_error_id(self) -> None:
        """Test InternalServerError with error_id."""
        error = InternalServerError(message="Critical failure", error_id="err_abc123")

        assert error.message == "Critical failure"
        assert error.details["error_id"] == "err_abc123"

    def test_internal_server_error_without_error_id(self) -> None:
        """Test InternalServerError without error_id."""
        error = InternalServerError("message")

        assert "error_id" not in error.details

    def test_internal_server_error_inheritance(self) -> None:
        """Test InternalServerError inherits from APIError."""
        error = InternalServerError()
        assert isinstance(error, APIError)


class TestExceptionRaisingAndCatching:
    """Test exception raising and catching patterns."""

    def test_raise_and_catch_session_not_found(self) -> None:
        """Test raising and catching SessionNotFoundError."""
        with pytest.raises(SessionNotFoundError) as exc_info:
            raise SessionNotFoundError("session_123")

        assert exc_info.value.code == "SESSION_NOT_FOUND"
        assert exc_info.value.status_code == 404

    def test_raise_and_catch_as_api_error(self) -> None:
        """Test catching specific exception as APIError."""
        with pytest.raises(APIError) as exc_info:
            raise TaskNotFoundError("task_456")

        assert exc_info.value.code == "TASK_NOT_FOUND"

    def test_raise_and_catch_as_exception(self) -> None:
        """Test catching exception as base Exception."""
        with pytest.raises(Exception) as exc_info:
            raise ValidationError("Invalid input")

        assert isinstance(exc_info.value, APIError)

    def test_multiple_exception_types(self) -> None:
        """Test handling multiple exception types."""
        exceptions = [
            SessionNotFoundError("s1"),
            TaskNotFoundError("t1"),
            AuthenticationError("auth failed"),
        ]

        for exc in exceptions:
            assert isinstance(exc, APIError)
            assert hasattr(exc, "code")
            assert hasattr(exc, "message")
            assert hasattr(exc, "status_code")
            assert hasattr(exc, "details")

    def test_exception_message_in_str(self) -> None:
        """Test that exception message is in str representation."""
        error = ValidationError("Field validation failed")
        assert "Field validation failed" in str(error)

    def test_exception_details_preservation(self) -> None:
        """Test that exception details are preserved through raise/catch."""
        original_details = {"field": "email", "reason": "invalid"}
        error = ValidationError("Validation failed", [original_details])

        with pytest.raises(ValidationError) as exc_info:
            raise error

        assert exc_info.value.details["validation_errors"][0] == original_details


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_api_error(self) -> None:
        """Test that all custom exceptions inherit from APIError."""
        exceptions = [
            SessionNotFoundError("s"),
            SessionStateConflictError("s", "state", "action"),
            TaskNotFoundError("t"),
            InvalidTaskTypeError("t", []),
            ValidationError("msg"),
            InvalidConfigurationError("msg"),
            AuthenticationError(),
            InvalidTokenError(),
            ExpiredTokenError(),
            AuthorizationError("r", "a"),
            UserNotFoundError("u"),
            RateLimitExceededError(1, 1, 1),
            ServiceUnavailableError("s"),
            DatabaseError("op"),
            ExportFormatError("f", []),
            NoDataAvailableError("s", "t"),
            InternalServerError(),
        ]

        for exc in exceptions:
            assert isinstance(exc, APIError)
            assert isinstance(exc, Exception)

    def test_all_exceptions_have_required_attributes(self) -> None:
        """Test that all exceptions have required attributes."""
        exceptions = [
            SessionNotFoundError("s"),
            TaskNotFoundError("t"),
            ValidationError("msg"),
            AuthenticationError(),
            UserNotFoundError("u"),
        ]

        for exc in exceptions:
            assert hasattr(exc, "code")
            assert hasattr(exc, "message")
            assert hasattr(exc, "status_code")
            assert hasattr(exc, "details")
            assert hasattr(exc, "to_dict")
            assert callable(exc.to_dict)


class TestExceptionToDict:
    """Test to_dict() method across all exception types."""

    def test_session_not_found_to_dict(self) -> None:
        """Test SessionNotFoundError.to_dict()."""
        error = SessionNotFoundError("session_123")
        result = error.to_dict("req_001")

        assert result["error"]["code"] == "SESSION_NOT_FOUND"
        assert result["error"]["request_id"] == "req_001"
        assert result["error"]["details"]["session_id"] == "session_123"

    def test_validation_error_to_dict(self) -> None:
        """Test ValidationError.to_dict()."""
        errors = [{"field": "email"}]
        error = ValidationError("Invalid", errors)
        result = error.to_dict()

        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["details"]["validation_errors"] == errors

    def test_authorization_error_to_dict(self) -> None:
        """Test AuthorizationError.to_dict()."""
        error = AuthorizationError("resource", "action", "admin")
        result = error.to_dict("req_002")

        assert result["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
        assert result["error"]["details"]["required_role"] == "admin"

    def test_rate_limit_error_to_dict(self) -> None:
        """Test RateLimitExceededError.to_dict()."""
        error = RateLimitExceededError(100, 60, 30)
        result = error.to_dict()

        assert result["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert result["error"]["details"]["limit"] == 100
        assert result["error"]["details"]["retry_after"] == 30

    def test_internal_server_error_to_dict(self) -> None:
        """Test InternalServerError.to_dict()."""
        error = InternalServerError("Critical", "err_123")
        result = error.to_dict("req_003")

        assert result["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert result["error"]["details"]["error_id"] == "err_123"
