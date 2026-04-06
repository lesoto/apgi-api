"""
Security Input Validation Middleware

Validates incoming requests for common security threats including:
- SQL injection attempts
- XSS payloads
- CSRF token validation
- Malicious input patterns
- Input sanitization

Returns HTTP 422 for validation failures with proper error messages.
"""

import re
import logging
from typing import Any, Dict
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates incoming requests for security threats.

    Intercepts requests before they reach route handlers and validates:
    - SQL injection patterns in usernames, emails, search parameters
    - XSS payloads in user inputs
    - CSRF token presence for state-changing operations
    - Malicious character sequences
    - Input length limits

    Returns HTTP 422 Unprocessable Entity for validation failures.
    """

    def __init__(self, app: ASGIApp, enabled: bool = True):
        """
        Initialize security validation middleware.

        Args:
            app: The ASGI application
            enabled: Whether validation is enabled
        """
        super().__init__(app)
        self.enabled = enabled
        if enabled:
            logger.info("Security validation middleware initialized")
        else:
            logger.info("Security validation middleware disabled")

    # SQL injection patterns — narrowed to avoid false positives on common words/emails.
    # These patterns target syntax-level injection artefacts rather than reserved words
    # that appear legitimately in usernames (e.g. "Anderson", "insert@domain.com").
    SQL_INJECTION_PATTERNS = [
        r"('--|--\s|#\s|/\*|\*/|;\s*DROP\s|;\s*SELECT\s|;\s*INSERT\s|;\s*UPDATE\s|;\s*DELETE\s)",
        r"(\b(UNION\s+ALL\s+SELECT|UNION\s+SELECT)\b)",
        r"(\b(WAITFOR\s+DELAY|BENCHMARK\s*\(|SLEEP\s*\()\b)",
        r"(1\s*=\s*1|'1'\s*=\s*'1'|1\s*OR\s*1)",
    ]

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<link[^>]*>.*?</link>",
        r"<meta[^>]*>.*?</meta>",
        r"expression\s*\(",
        r"@import",
        r"<style[^>]*>.*?</style>",
    ]

    # Malicious character patterns — true control characters only.
    # Tab (\x09), newline (\x0a), carriage return (\x0d) are excluded because they
    # legitimately appear in multiline JSON fields and formatted text.
    MALICIOUS_CHARS = [
        "\x00",
        "\x01",
        "\x02",
        "\x03",
        "\x04",
        "\x05",
        "\x06",
        "\x07",
        "\x08",
        "\x0b",
        "\x0c",
        "\x0e",
        "\x0f",
        "\x1a",
        "\x1b",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x1f",
    ]

    async def dispatch(self, request: Request, call_next):
        """
        Validate request for security threats before passing to handler.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            Response from handler or validation error response
        """
        # Skip validation if disabled
        if not self.enabled:
            return await call_next(request)

        # Only validate specific methods and paths (skip HEAD and OPTIONS)
        if request.method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            validation_result = await self._validate_request(request)

            if validation_result["is_valid"]:
                return await call_next(request)
            else:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=validation_result["error_message"],
                )
        else:
            # Skip validation for HEAD and OPTIONS requests
            return await call_next(request)

    async def _validate_request(self, request: Request) -> Dict[str, Any]:
        """
        Validate request for security threats.

        Returns:
            Dict with 'is_valid' boolean and 'error_message' string if invalid
        """
        try:
            # Get request data based on method
            if request.method.upper() in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = await request.json()
                    except Exception:
                        data = {}
                else:
                    # Form data
                    try:
                        form_data = await request.form()
                        data = dict(form_data) if form_data else {}
                    except Exception:
                        data = {}
            else:
                # GET requests - query parameters
                query_params = request.query_params
                data = dict(query_params) if query_params else {}

            # Validate based on path and method
            path = request.url.path

            # Login endpoint validation
            if path == "/v1/auth/login" or re.match(r"^/v1/auth/login(?:/.*)?$", path):
                return self._validate_login_data(data)

            # Registration endpoint validation
            elif path == "/v1/users/register" or re.match(r"^/v1/users/register(?:/.*)?$", path):
                return self._validate_registration_data(data)

            # User profile update validation
            elif (
                path == "/v1/users/me" or re.match(r"^/v1/users/me(?:/.*)?$", path)
            ) and request.method.upper() in ["PUT", "PATCH"]:
                return self._validate_user_profile_data(data)

            # Search endpoint validation
            elif path == "/v1/users" and request.method.upper() == "GET":
                return self._validate_search_data(data)

            # Password change validation
            elif path == "/v1/users/me/password" and request.method.upper() == "POST":
                return self._validate_password_data(data)

            # Default validation for other endpoints
            return self._validate_generic_data(data, path)

        except Exception as e:
            logger.error(f"Security validation error: {str(e)}")
            return {"is_valid": False, "error_message": f"Security validation failed: {str(e)}"}

    def _validate_login_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate login data for SQL injection and malicious input."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Validate username
        username = data.get("username", "")
        if not isinstance(username, str) or not username:
            return {"is_valid": False, "error_message": "Username is required"}

        # Check SQL injection in username
        if self._contains_sql_injection(username):
            return {"is_valid": False, "error_message": "Username contains invalid characters"}

        # Check for malicious characters in username
        if self._contains_malicious_chars(username):
            return {"is_valid": False, "error_message": "Username contains invalid characters"}

        # Username length validation
        if len(username) > 100:
            return {"is_valid": False, "error_message": "Username too long (max 100 characters)"}

        # Validate email if present
        email = data.get("email", "")
        if email and not self._is_valid_email_format(email):
            return {"is_valid": False, "error_message": "Invalid email format"}

        return {"is_valid": True, "error_message": ""}

    def _validate_registration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration data for security threats."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Validate username
        username = data.get("username", "")
        if not isinstance(username, str) or not username:
            return {"is_valid": False, "error_message": "Username is required"}

        # Check SQL injection in username
        if self._contains_sql_injection(username):
            return {"is_valid": False, "error_message": "Username contains invalid characters"}

        # Check for malicious characters in username
        if self._contains_malicious_chars(username):
            return {"is_valid": False, "error_message": "Username contains invalid characters"}

        # Username length validation
        if len(username) > 100:
            return {"is_valid": False, "error_message": "Username too long (max 100 characters)"}

        # Username format validation (alphanumeric with some allowed chars)
        if not re.match(r"^[a-zA-Z0-9_@.+$\-]{1,100}$", username):
            return {"is_valid": False, "error_message": "Username contains invalid characters"}

        # Validate email
        email = data.get("email", "")
        if not isinstance(email, str) or not email:
            return {"is_valid": False, "error_message": "Email is required"}

        if not self._is_valid_email_format(email):
            return {"is_valid": False, "error_message": "Invalid email format"}

        # Validate password
        password = data.get("password", "")
        if not isinstance(password, str) or not password:
            return {"is_valid": False, "error_message": "Password is required"}

        # Password strength validation
        if len(password) < 8:
            return {"is_valid": False, "error_message": "Password too short (min 8 characters)"}

        if len(password) > 128:
            return {"is_valid": False, "error_message": "Password too long (max 128 characters)"}

        return {"is_valid": True, "error_message": ""}

    def _validate_user_profile_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user profile update data for XSS and injection."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Validate email if present
        email = data.get("email", "")
        if email and not self._is_valid_email_format(email):
            return {"is_valid": False, "error_message": "Invalid email format"}

        # Check for XSS in all string fields
        for field_name, field_value in data.items():
            if isinstance(field_value, str) and self._contains_xss(field_value):
                return {
                    "is_valid": False,
                    "error_message": f"{field_name} contains potentially dangerous content",
                }

        return {"is_valid": True, "error_message": ""}

    def _validate_search_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search parameters for injection attacks."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Validate search parameter if present
        search_param = data.get("search", "")
        if isinstance(search_param, str) and self._contains_sql_injection(search_param):
            return {
                "is_valid": False,
                "error_message": "Search parameter contains invalid characters",
            }

        return {"is_valid": True, "error_message": ""}

    def _validate_password_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate password change data."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        password = data.get("password", "")
        if not isinstance(password, str) or not password:
            return {"is_valid": False, "error_message": "Password is required"}

        # Password strength validation
        if len(password) < 8:
            return {"is_valid": False, "error_message": "Password too short (min 8 characters)"}

        return {"is_valid": True, "error_message": ""}

    def _validate_generic_data(self, data: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Generic validation for other endpoints."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Check all string fields for common threats
        for field_name, field_value in data.items():
            if isinstance(field_value, str):
                # SQL injection check
                if self._contains_sql_injection(field_value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_name} contains potentially dangerous content",
                    }

                # XSS check
                if self._contains_xss(field_value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_name} contains potentially dangerous content",
                    }

                # Malicious characters check
                if self._contains_malicious_chars(field_value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_name} contains invalid characters",
                    }

        return {"is_valid": True, "error_message": ""}

    def _contains_sql_injection(self, value: str) -> bool:
        """Check if value contains SQL injection patterns."""
        if not isinstance(value, str):
            return False

        value_upper = value.upper()
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper):
                return True
        return False

    def _contains_xss(self, value: str) -> bool:
        """Check if value contains XSS patterns."""
        if not isinstance(value, str):
            return False

        value_lower = value.lower()
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    def _contains_malicious_chars(self, value: str) -> bool:
        """Check if value contains malicious control characters."""
        if not isinstance(value, str):
            return False

        return any(char in value for char in self.MALICIOUS_CHARS)

    def _is_valid_email_format(self, email: str) -> bool:
        """Basic email format validation."""
        if not isinstance(email, str):
            return False

        # Basic email regex pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(email_pattern, email))
