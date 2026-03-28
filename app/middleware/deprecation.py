"""
Deprecation Warning Middleware

Adds deprecation headers to responses from deprecated endpoints.
"""

from typing import Any, Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class DeprecationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds Deprecation headers to deprecated endpoints.

    Requirements: 16.3, 16.4, 16.6
    """

    def __init__(self, app, deprecated_endpoints: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Initialize deprecation middleware.

        Args:
            app: The ASGI application
            deprecated_endpoints: Dictionary mapping endpoint paths to deprecation info
                                 Format: {"/v1/endpoint": {"sunset": "2026-01-01", "replacement": "/v2/endpoint"}}
        """
        super().__init__(app)
        self.deprecated_endpoints = deprecated_endpoints or {}

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """
        Process request and add deprecation headers if endpoint is deprecated.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response with deprecation headers if applicable
        """
        # Get the response from the next middleware/handler
        response = await call_next(request)

        # Check if the endpoint is deprecated
        path = request.url.path
        deprecation_info = self._get_deprecation_info(path)

        if deprecation_info:
            # Add Deprecation header (RFC 8594)
            response.headers["Deprecation"] = "true"

            # Add Sunset header if sunset date is specified
            if "sunset" in deprecation_info:
                response.headers["Sunset"] = deprecation_info["sunset"]

            # Add Link header pointing to replacement if specified
            if "replacement" in deprecation_info:
                response.headers["Link"] = (
                    f'<{deprecation_info["replacement"]}>; rel="successor-version"'
                )

            # Add custom warning header with deprecation message
            warning_msg = self._build_warning_message(path, deprecation_info)
            response.headers["Warning"] = warning_msg

        return response

    def _get_deprecation_info(self, path: str) -> Optional[Dict[str, str]]:
        """
        Get deprecation info for a given path.

        Args:
            path: The endpoint path

        Returns:
            Deprecation info if endpoint is deprecated, None otherwise
        """
        # Check exact match first
        if path in self.deprecated_endpoints:
            return self.deprecated_endpoints[path]

        # Check for pattern matches (e.g., /v1/sessions/{session_id})
        for deprecated_path, info in self.deprecated_endpoints.items():
            if self._path_matches(path, deprecated_path):
                return info

        return None

    def _path_matches(self, actual_path: str, pattern_path: str) -> bool:
        """
        Check if actual path matches a pattern path.

        Args:
            actual_path: The actual request path
            pattern_path: The pattern path (may contain {param} placeholders)

        Returns:
            True if paths match, False otherwise
        """
        # Simple pattern matching for path parameters
        actual_parts = actual_path.split("/")
        pattern_parts = pattern_path.split("/")

        if len(actual_parts) != len(pattern_parts):
            return False

        for actual, pattern in zip(actual_parts, pattern_parts):
            # If pattern part is a parameter (e.g., {session_id}), it matches anything
            if pattern.startswith("{") and pattern.endswith("}"):
                continue
            # Otherwise, parts must match exactly
            if actual != pattern:
                return False

        return True

    def _build_warning_message(self, path: str, deprecation_info: Dict[str, str]) -> str:
        """
        Build a warning message for deprecated endpoint.

        Args:
            path: The endpoint path
            deprecation_info: Deprecation information

        Returns:
            Warning message string (ASCII-safe for HTTP headers)
        """
        # Ensure path is ASCII-safe for HTTP headers (latin-1 encoding)
        try:
            safe_path = path.encode("latin-1").decode("latin-1")
        except UnicodeEncodeError:
            # If path contains non-latin-1 characters, use URL encoding
            safe_path = path.encode("ascii", errors="backslashreplace").decode("ascii")

        msg = f'299 - "Deprecated API endpoint: {safe_path}"'

        if "sunset" in deprecation_info:
            msg += f' "Sunset date: {deprecation_info["sunset"]}"'

        if "replacement" in deprecation_info:
            replacement = deprecation_info["replacement"]
            try:
                safe_replacement = replacement.encode("latin-1").decode("latin-1")
            except UnicodeEncodeError:
                safe_replacement = replacement.encode("ascii", errors="backslashreplace").decode(
                    "ascii"
                )
            msg += f' "Use {safe_replacement} instead"'

        return msg

    def update_deprecated_endpoints(self, deprecated_endpoints: Dict[str, Dict[str, str]]):
        """
        Update the deprecated endpoints configuration.

        Args:
            deprecated_endpoints: New deprecated endpoints configuration
        """
        self.deprecated_endpoints = deprecated_endpoints
