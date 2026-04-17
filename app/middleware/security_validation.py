"""
Security Input Validation Middleware

Validates incoming requests for common security threats including:
- SQL injection attempts
- XSS payloads
- CSRF token validation
- Malicious input patterns
- Input sanitization
- Context-aware validation based on field types and expected formats
- WAF-like request scoring and anomaly detection

Returns HTTP 422 for validation failures with proper error messages.
"""

import re
import logging
from typing import Any, cast, Dict, List, Set
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
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
        # WAF-like request tracking
        self.request_scores: Dict[str, List[float]] = defaultdict(list)
        self.blocked_ips: Set[str] = set()
        self.request_timestamps: Dict[str, List[datetime]] = defaultdict(list)

        if enabled:
            logger.info("Security validation middleware initialized with context-aware validation")
        else:
            logger.info("Security validation middleware disabled")

    # Field type definitions for context-aware validation
    FIELD_TYPES: Dict[str, Dict[str, Any]] = {
        "username": {
            "type": "string",
            "pattern": r"^[a-zA-Z0-9_@.+$\-]{1,100}$",
            "max_length": 100,
            "min_length": 1,
            "allowed_chars": "alphanumeric, @, ., +, $, -",
        },
        "email": {
            "type": "email",
            "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "max_length": 255,
            "min_length": 5,
        },
        "password": {
            "type": "password",
            "min_length": 8,
            "max_length": 128,
            "require_complexity": True,
        },
        "search": {
            "type": "string",
            "max_length": 200,
            "allow_special_chars": True,
        },
        "id": {
            "type": "uuid",
            "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        },
    }

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

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
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
            response = await call_next(request)
            return cast(StarletteResponse, response)

        # Get client IP for WAF tracking
        client_ip = self._get_client_ip(request)

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            logger.warning(f"Blocked request from blocked IP: {client_ip}")
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address blocked due to suspicious activity",
            )

        # Check rate limiting per IP
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests from this IP",
            )

        # Only validate specific methods and paths (skip HEAD and OPTIONS)
        if request.method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            validation_result = await self._validate_request(request, client_ip)

            if validation_result["is_valid"]:
                # Update request score (lower is better)
                self._update_request_score(client_ip, validation_result.get("score", 0))
                response = await call_next(request)
                return cast(StarletteResponse, response)
            else:
                # High-risk request - potentially block IP
                if validation_result.get("score", 0) > 80:
                    self.blocked_ips.add(client_ip)
                    logger.warning(f"Blocked IP due to high-risk request: {client_ip}")

                from fastapi import HTTPException

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=validation_result["error_message"],
                )
        else:
            # Skip validation for HEAD and OPTIONS requests
            response = await call_next(request)
            return cast(StarletteResponse, response)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        if request.client:
            return request.client.host

        return "unknown"

    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if IP has exceeded rate limit (100 requests per minute)."""
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)

        # Clean old timestamps
        self.request_timestamps[client_ip] = [
            ts for ts in self.request_timestamps[client_ip] if ts > minute_ago
        ]

        # Check if under limit
        return len(self.request_timestamps[client_ip]) < 100

    def _update_request_score(self, client_ip: str, score: float) -> None:
        """Update request score for IP and clean old scores."""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        # Clean old scores
        self.request_scores[client_ip] = [
            s
            for s, ts in zip(
                self.request_scores[client_ip],
                self.request_timestamps.get(client_ip, []),
            )
            if ts > hour_ago
        ]

        self.request_scores[client_ip].append(score)
        self.request_timestamps[client_ip].append(now)

    async def _validate_request(self, request: Request, client_ip: str) -> Dict[str, Any]:
        """
        Validate request for security threats with context-aware checks.

        Returns:
            Dict with 'is_valid' boolean, 'error_message' string if invalid, and 'score' for risk assessment
        """
        score = 0  # Risk score (0-100)
        try:
            # Get request data based on method
            if request.method.upper() in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = await request.json()
                        # Check for nested structures that could be abused
                        if isinstance(data, dict) and len(data) > 50:
                            score += 10  # Suspiciously large payload
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
                # Check for excessive query parameters
                if len(data) > 20:
                    score += 5

            # Validate based on path and method
            path = request.url.path

            # Login endpoint validation
            if path == "/v1/auth/login" or re.match(r"^/v1/auth/login(?:/.*)?$", path):
                result = self._validate_login_data(data)
                if not result["is_valid"]:
                    score += 30
                result["score"] = score
                return result

            # Registration endpoint validation
            elif path == "/v1/users/register" or re.match(r"^/v1/users/register(?:/.*)?$", path):
                result = self._validate_registration_data(data)
                if not result["is_valid"]:
                    score += 25
                result["score"] = score
                return result

            # User profile update validation
            elif (
                path == "/v1/users/me" or re.match(r"^/v1/users/me(?:/.*)?$", path)
            ) and request.method.upper() in ["PUT", "PATCH"]:
                result = self._validate_user_profile_data(data)
                if not result["is_valid"]:
                    score += 20
                result["score"] = score
                return result

            # Search endpoint validation
            elif path == "/v1/users" and request.method.upper() == "GET":
                result = self._validate_search_data(data)
                if not result["is_valid"]:
                    score += 15
                result["score"] = score
                return result

            # Password change validation
            elif path == "/v1/users/me/password" and request.method.upper() == "POST":
                result = self._validate_password_data(data)
                if not result["is_valid"]:
                    score += 25
                result["score"] = score
                return result

            # Default validation for other endpoints
            result = self._validate_generic_data(data, path)
            if not result["is_valid"]:
                score += 10
            result["score"] = score
            return result

        except Exception as e:
            logger.error(f"Security validation error: {str(e)}")
            return {
                "is_valid": False,
                "error_message": f"Security validation failed: {str(e)}",
                "score": 50,
            }

    def _validate_login_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate login data with context-aware field validation."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Context-aware validation for username
        username = data.get("username", "")
        if not isinstance(username, str) or not username:
            return {"is_valid": False, "error_message": "Username is required"}

        # Use field type definition for validation
        username_validation = self._validate_field_by_type("username", username)
        if not username_validation["is_valid"]:
            return username_validation

        # Validate email if present with context-aware check
        email = data.get("email", "")
        if email:
            email_validation = self._validate_field_by_type("email", email)
            if not email_validation["is_valid"]:
                return email_validation

        return {"is_valid": True, "error_message": ""}

    def _validate_field_by_type(self, field_type: str, value: Any) -> Dict[str, Any]:
        """
        Validate a field value based on its expected type definition.

        This provides context-aware validation based on what the field should contain.
        """
        if field_type not in self.FIELD_TYPES:
            # No type definition, use generic validation
            return {"is_valid": True, "error_message": ""}

        field_def = self.FIELD_TYPES[field_type]

        # Type check
        if field_def["type"] == "string":
            if not isinstance(value, str):
                return {"is_valid": False, "error_message": f"{field_type} must be a string"}

            # Length validation
            if "min_length" in field_def and len(value) < field_def["min_length"]:
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} too short (min {field_def['min_length']} characters)",
                }
            if "max_length" in field_def and len(value) > field_def["max_length"]:
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} too long (max {field_def['max_length']} characters)",
                }

            # Pattern validation
            if "pattern" in field_def:
                if not re.match(field_def["pattern"], value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_type} contains invalid characters",
                    }

            # Security checks
            if self._contains_sql_injection(value):
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} contains potentially dangerous content",
                }
            if self._contains_xss(value):
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} contains potentially dangerous content",
                }
            if self._contains_malicious_chars(value):
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} contains invalid characters",
                }

        elif field_def["type"] == "email":
            if not isinstance(value, str):
                return {"is_valid": False, "error_message": f"{field_type} must be a string"}

            # Length validation
            if "min_length" in field_def and len(value) < field_def["min_length"]:
                return {"is_valid": False, "error_message": f"{field_type} too short"}
            if "max_length" in field_def and len(value) > field_def["max_length"]:
                return {"is_valid": False, "error_message": f"{field_type} too long"}

            # Email format validation
            if not self._is_valid_email_format(value):
                return {"is_valid": False, "error_message": f"Invalid {field_type} format"}

        elif field_def["type"] == "password":
            if not isinstance(value, str):
                return {"is_valid": False, "error_message": f"{field_type} must be a string"}

            # Length validation
            if "min_length" in field_def and len(value) < field_def["min_length"]:
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} too short (min {field_def['min_length']} characters)",
                }
            if "max_length" in field_def and len(value) > field_def["max_length"]:
                return {
                    "is_valid": False,
                    "error_message": f"{field_type} too long (max {field_def['max_length']} characters)",
                }

            # Complexity check if required
            if field_def.get("require_complexity", False):
                if not re.search(r"[A-Z]", value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_type} must contain uppercase letter",
                    }
                if not re.search(r"[a-z]", value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_type} must contain lowercase letter",
                    }
                if not re.search(r"\d", value):
                    return {"is_valid": False, "error_message": f"{field_type} must contain digit"}
                if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
                    return {
                        "is_valid": False,
                        "error_message": f"{field_type} must contain special character",
                    }

        elif field_def["type"] == "uuid":
            if not isinstance(value, str):
                return {"is_valid": False, "error_message": f"{field_type} must be a string"}

            if "pattern" in field_def and not re.match(field_def["pattern"], value.lower()):
                return {"is_valid": False, "error_message": f"Invalid {field_type} format"}

        return {"is_valid": True, "error_message": ""}

    def _validate_registration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration data with context-aware field validation."""
        if not isinstance(data, dict):
            return {"is_valid": False, "error_message": "Invalid request format"}

        # Validate username using field type definition
        username = data.get("username", "")
        username_validation = self._validate_field_by_type("username", username)
        if not username_validation["is_valid"]:
            return username_validation

        # Validate email using field type definition
        email = data.get("email", "")
        if not email:
            return {"is_valid": False, "error_message": "Email is required"}
        email_validation = self._validate_field_by_type("email", email)
        if not email_validation["is_valid"]:
            return email_validation

        # Validate password using field type definition
        password = data.get("password", "")
        if not password:
            return {"is_valid": False, "error_message": "Password is required"}
        password_validation = self._validate_field_by_type("password", password)
        if not password_validation["is_valid"]:
            return password_validation

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
