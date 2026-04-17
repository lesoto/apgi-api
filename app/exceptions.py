"""
Custom Exception Classes for APGI API

Defines custom exception hierarchy for consistent error handling across the API.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class APIError(Exception):
    """
    Base exception class for all API errors.

    Provides consistent error structure with error codes, messages, HTTP status codes,
    and additional details for debugging.

    Attributes:
        code: Machine-readable error code (e.g., "SESSION_NOT_FOUND")
        message: Human-readable error message
        status_code: HTTP status code to return
        details: Additional context about the error
    """

    def __init__(
        self, code: str, message: str, status_code: int, details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize API error.

        Args:
            code: Error code identifier
            message: Error message
            status_code: HTTP status code
            details: Optional additional error details
        """
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert exception to dictionary for JSON response.

        Args:
            request_id: Optional request ID for tracking

        Returns:
            Dictionary with error details
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "details": self.details,
            }
        }


# ============================================================================
# Session-related Exceptions (404, 409)
# ============================================================================


class SessionNotFoundError(APIError):
    """
    Exception raised when a requested session does not exist.

    HTTP Status: 404 Not Found
    """

    def __init__(self, session_id: str):
        """
        Initialize session not found error.

        Args:
            session_id: The session ID that was not found
        """
        super().__init__(
            code="SESSION_NOT_FOUND",
            message=f"Session with ID '{session_id}' does not exist",
            status_code=404,
            details={"session_id": session_id},
        )


class SessionStateConflictError(APIError):
    """
    Exception raised when a session operation conflicts with current state.

    For example, trying to start an already running session or pause a stopped session.

    HTTP Status: 409 Conflict
    """

    def __init__(self, session_id: str, current_state: str, attempted_action: str):
        """
        Initialize session state conflict error.

        Args:
            session_id: The session ID
            current_state: Current session state
            attempted_action: The action that was attempted
        """
        super().__init__(
            code="SESSION_STATE_CONFLICT",
            message=f"Cannot {attempted_action} session in state '{current_state}'",
            status_code=409,
            details={
                "session_id": session_id,
                "current_state": current_state,
                "attempted_action": attempted_action,
            },
        )


# ============================================================================
# Task-related Exceptions (404)
# ============================================================================


class TaskNotFoundError(APIError):
    """
    Exception raised when a requested task does not exist.

    HTTP Status: 404 Not Found
    """

    def __init__(self, task_id: str):
        """
        Initialize task not found error.

        Args:
            task_id: The task ID that was not found
        """
        super().__init__(
            code="TASK_NOT_FOUND",
            message=f"Task with ID '{task_id}' does not exist",
            status_code=404,
            details={"task_id": task_id},
        )


class InvalidTaskTypeError(APIError):
    """
    Exception raised when an invalid task type is specified.

    HTTP Status: 400 Bad Request
    """

    def __init__(self, task_type: str, valid_types: list[str]):
        """
        Initialize invalid task type error.

        Args:
            task_type: The invalid task type
            valid_types: List of valid task types
        """
        super().__init__(
            code="INVALID_TASK_TYPE",
            message=f"Task type '{task_type}' is not valid",
            status_code=400,
            details={"task_type": task_type, "valid_types": valid_types},
        )


# ============================================================================
# Validation Exceptions (400, 422)
# ============================================================================


class ValidationError(APIError):
    """
    Exception raised when request validation fails.

    HTTP Status: 422 Unprocessable Entity
    """

    def __init__(self, message: str, validation_errors: Optional[list[dict[str, Any]]] = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            validation_errors: List of specific validation errors
        """
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details={"validation_errors": validation_errors or []},
        )


class InvalidConfigurationError(APIError):
    """
    Exception raised when configuration is invalid.

    HTTP Status: 400 Bad Request
    """

    def __init__(self, message: str, config_errors: Optional[Dict[str, Any]] = None):
        """
        Initialize invalid configuration error.

        Args:
            message: Error message
            config_errors: Dictionary of configuration errors
        """
        super().__init__(
            code="INVALID_CONFIGURATION",
            message=message,
            status_code=400,
            details={"config_errors": config_errors or {}},
        )


# ============================================================================
# Authentication & Authorization Exceptions (401, 403)
# ============================================================================


class AuthenticationError(APIError):
    """
    Exception raised when authentication fails.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, message: str = "Authentication failed"):
        """
        Initialize authentication error.

        Args:
            message: Error message
        """
        super().__init__(code="AUTHENTICATION_FAILED", message=message, status_code=401, details={})


class InvalidTokenError(APIError):
    """
    Exception raised when JWT token is invalid.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, reason: str = "Token is invalid"):
        """
        Initialize invalid token error.

        Args:
            reason: Reason for token invalidity
        """
        super().__init__(
            code="INVALID_TOKEN", message=reason, status_code=401, details={"reason": reason}
        )


class ExpiredTokenError(APIError):
    """
    Exception raised when JWT token has expired.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, message: str = "Token has expired"):
        """
        Initialize expired token error.

        Args:
            message: Error message
        """
        super().__init__(code="TOKEN_EXPIRED", message=message, status_code=401, details={})


class AuthorizationError(APIError):
    """
    Exception raised when user lacks required permissions.

    HTTP Status: 403 Forbidden
    """

    def __init__(self, resource: str, action: str, required_role: Optional[str] = None):
        """
        Initialize authorization error.

        Args:
            resource: The resource being accessed
            action: The action being attempted
            required_role: The role required for this action
        """
        details = {"resource": resource, "action": action}
        if required_role:
            details["required_role"] = required_role

        super().__init__(
            code="INSUFFICIENT_PERMISSIONS",
            message=f"Insufficient permissions to {action} {resource}",
            status_code=403,
            details=details,
        )


# ============================================================================
# User Management Exceptions (404, 409)
# ============================================================================


class UserNotFoundError(APIError):
    """
    Exception raised when a requested user does not exist.

    HTTP Status: 404 Not Found
    """

    def __init__(self, user_id: str):
        """
        Initialize user not found error.

        Args:
            user_id: The user identifier that was not found
        """
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"User with ID '{user_id}' not found",
            status_code=404,
            details={"user_id": user_id},
        )


# ============================================================================
# Rate Limiting Exceptions (429)
# ============================================================================


class RateLimitExceededError(APIError):
    """
    Exception raised when rate limit is exceeded.

    HTTP Status: 429 Too Many Requests
    """

    def __init__(self, limit: int, window_seconds: int, retry_after: int):
        """
        Initialize rate limit exceeded error.

        Args:
            limit: The rate limit that was exceeded
            window_seconds: The time window for the rate limit
            retry_after: Seconds until the client can retry
        """
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit of {limit} requests per {window_seconds} seconds exceeded",
            status_code=429,
            details={"limit": limit, "window_seconds": window_seconds, "retry_after": retry_after},
        )


# ============================================================================
# Resource Exceptions (503)
# ============================================================================


class ServiceUnavailableError(APIError):
    """
    Exception raised when a required service is unavailable.

    HTTP Status: 503 Service Unavailable
    """

    def __init__(self, service: str, reason: Optional[str] = None):
        """
        Initialize service unavailable error.

        Args:
            service: Name of the unavailable service
            reason: Optional reason for unavailability
        """
        message = f"Service '{service}' is currently unavailable"
        if reason:
            message += f": {reason}"

        super().__init__(
            code="SERVICE_UNAVAILABLE",
            message=message,
            status_code=503,
            details={"service": service, "reason": reason},
        )


class DatabaseError(APIError):
    """
    Exception raised when database operations fail.

    HTTP Status: 500 Internal Server Error
    """

    def __init__(self, operation: str, reason: Optional[str] = None):
        """
        Initialize database error.

        Args:
            operation: The database operation that failed
            reason: Optional reason for failure
        """
        message = f"Database operation '{operation}' failed"
        if reason:
            message += f": {reason}"

        super().__init__(
            code="DATABASE_ERROR",
            message=message,
            status_code=500,
            details={"operation": operation, "reason": reason},
        )


# ============================================================================
# Data Export Exceptions (400, 404)
# ============================================================================


class ExportFormatError(APIError):
    """
    Exception raised when an unsupported export format is requested.

    HTTP Status: 400 Bad Request
    """

    def __init__(self, format: str, supported_formats: list[str]):
        """
        Initialize export format error.

        Args:
            format: The unsupported format
            supported_formats: List of supported formats
        """
        super().__init__(
            code="UNSUPPORTED_EXPORT_FORMAT",
            message=f"Export format '{format}' is not supported",
            status_code=400,
            details={"requested_format": format, "supported_formats": supported_formats},
        )


class NoDataAvailableError(APIError):
    """
    Exception raised when no data is available for export.

    HTTP Status: 404 Not Found
    """

    def __init__(self, session_id: str, data_type: str):
        """
        Initialize no data available error.

        Args:
            session_id: The session ID
            data_type: Type of data that was requested
        """
        super().__init__(
            code="NO_DATA_AVAILABLE",
            message=f"No {data_type} data available for session '{session_id}'",
            status_code=404,
            details={"session_id": session_id, "data_type": data_type},
        )


# ============================================================================
# Internal Server Exceptions (500)
# ============================================================================


class InternalServerError(APIError):
    """
    Exception raised for unexpected internal server errors.

    HTTP Status: 500 Internal Server Error
    """

    def __init__(
        self, message: str = "An unexpected error occurred", error_id: Optional[str] = None
    ):
        """
        Initialize internal server error.

        Args:
            message: Error message
            error_id: Optional unique error identifier for tracking
        """
        details = {}
        if error_id:
            details["error_id"] = error_id

        super().__init__(
            code="INTERNAL_SERVER_ERROR", message=message, status_code=500, details=details
        )
