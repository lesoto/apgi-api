"""
Response Schema Validation Middleware

Validates API responses against OpenAPI schemas to ensure contract compliance.
Logs validation failures for monitoring and debugging.
"""

import json
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.middleware.logging import StructuredLogger

logger = StructuredLogger(__name__)


class ResponseSchemaValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates API responses against OpenAPI schemas.

    This middleware intercepts responses and validates them against the
    OpenAPI specification to ensure API contract compliance. Validation
    failures are logged but do not block the response (fail-open approach
    to avoid breaking production).

    Attributes:
        app: The ASGI application
        openapi_schema: The OpenAPI schema dictionary
        enabled: Whether validation is enabled
        fail_on_error: Whether to return 500 on validation failure (default: False)
    """

    def __init__(
        self,
        app: ASGIApp,
        openapi_schema: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        fail_on_error: bool = False,
    ):
        """
        Initialize the response schema validation middleware.

        Args:
            app: The ASGI application
            openapi_schema: OpenAPI schema dictionary (if None, will be fetched from app)
            enabled: Whether to enable validation
            fail_on_error: Whether to fail requests on validation errors
        """
        super().__init__(app)
        self.openapi_schema = openapi_schema
        self.enabled = enabled
        self.fail_on_error = fail_on_error
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

        if enabled:
            logger.info(
                "Response schema validation middleware initialized",
                component="middleware",
                fail_on_error=fail_on_error,
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and validate response against schema.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            The response from the handler
        """
        # Skip validation if disabled
        if not self.enabled:
            return await call_next(request)

        # Get OpenAPI schema if not already loaded
        if self.openapi_schema is None:
            try:
                self.openapi_schema = request.app.openapi()
            except Exception as e:
                logger.error(
                    "Failed to load OpenAPI schema", component="schema_validation", error=str(e)
                )
                # Continue without validation if schema can't be loaded
                return await call_next(request)

        # Process request
        response = await call_next(request)

        # Only validate successful responses (2xx and 4xx)
        # Skip validation for 5xx errors as they may not match schema
        if 200 <= response.status_code < 500:
            await self._validate_response(request, response)

        return response

    async def _validate_response(self, request: Request, response: Response) -> None:
        """
        Validate response against OpenAPI schema.

        Args:
            request: The request object
            response: The response object
        """
        try:
            # Extract path and method
            path = request.url.path
            method = request.method.lower()

            # Get schema for this endpoint
            schema = self._get_response_schema(path, method, response.status_code)

            if schema is None:
                # No schema defined for this endpoint/status code
                logger.debug(
                    "No schema defined for endpoint",
                    component="schema_validation",
                    path=path,
                    method=method,
                    status_code=response.status_code,
                )
                return

            # Get response body
            response_body = await self._get_response_body(response)

            if response_body is None:
                # Empty response body
                if schema.get("content"):
                    # Schema expects content but response is empty
                    self._log_validation_failure(
                        request=request,
                        response=response,
                        error="Response body is empty but schema expects content",
                        schema=schema,
                    )
                return

            # Parse JSON response
            try:
                response_data = json.loads(response_body)
            except json.JSONDecodeError as e:
                self._log_validation_failure(
                    request=request,
                    response=response,
                    error=f"Response is not valid JSON: {str(e)}",
                    schema=schema,
                )
                return

            # Validate response structure
            validation_errors = self._validate_schema(response_data, schema)

            if validation_errors:
                self._log_validation_failure(
                    request=request,
                    response=response,
                    error="Response does not match schema",
                    schema=schema,
                    validation_errors=validation_errors,
                )

        except Exception as e:
            logger.error(
                "Error during response validation",
                component="schema_validation",
                error=str(e),
                path=request.url.path,
                method=request.method,
            )

    def _get_response_schema(
        self, path: str, method: str, status_code: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get response schema for a specific endpoint and status code.

        Args:
            path: The request path
            method: The HTTP method
            status_code: The response status code

        Returns:
            Schema dictionary or None if not found
        """
        # Check cache first
        cache_key = f"{method}:{path}:{status_code}"
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]

        if not self.openapi_schema or "paths" not in self.openapi_schema:
            return None

        # Find matching path in OpenAPI spec
        # Try exact match first
        path_item = self.openapi_schema["paths"].get(path)

        # If no exact match, try to match path parameters
        if path_item is None:
            path_item = self._find_matching_path(path)

        if path_item is None:
            return None

        # Get operation for this method
        operation = path_item.get(method)
        if operation is None:
            return None

        # Get response schema for this status code
        responses = operation.get("responses", {})

        # Try exact status code match
        status_str = str(status_code)
        response_schema = responses.get(status_str)

        # Try default response
        if response_schema is None:
            response_schema = responses.get("default")

        # Try status code range (e.g., "2XX")
        if response_schema is None:
            status_range = f"{status_str[0]}XX"
            response_schema = responses.get(status_range)

        # Cache the result
        self._schema_cache[cache_key] = response_schema

        return response_schema

    def _find_matching_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Find matching path in OpenAPI spec, handling path parameters.

        Args:
            path: The request path

        Returns:
            Path item dictionary or None
        """
        if not self.openapi_schema or "paths" not in self.openapi_schema:
            return None

        path_parts = path.strip("/").split("/")

        for spec_path, path_item in self.openapi_schema["paths"].items():
            spec_parts = spec_path.strip("/").split("/")

            # Must have same number of parts
            if len(spec_parts) != len(path_parts):
                continue

            # Check if all parts match (considering parameters)
            match = True
            for spec_part, path_part in zip(spec_parts, path_parts):
                # Path parameter (e.g., {session_id})
                if spec_part.startswith("{") and spec_part.endswith("}"):
                    continue
                # Exact match required
                elif spec_part != path_part:
                    match = False
                    break

            if match:
                return path_item

        return None

    async def _get_response_body(self, response: Response) -> Optional[str]:
        """
        Extract response body as string.

        Args:
            response: The response object

        Returns:
            Response body as string or None
        """
        # Check if response has body
        if not hasattr(response, "body"):
            return None

        body = response.body

        if body is None or len(body) == 0:
            return None

        # Decode bytes to string
        if isinstance(body, bytes):
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return None

        return str(body)

    def _validate_schema(self, data: Any, schema: Dict[str, Any]) -> list:
        """
        Validate data against schema.

        This is a basic validation that checks for required fields and types.
        For production use, consider using a library like jsonschema or pydantic.

        Args:
            data: The data to validate
            schema: The schema to validate against

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[Dict[str, Any]] = []

        # Get content schema
        content = schema.get("content", {})

        # Check for JSON content
        json_content = content.get("application/json", {})
        if not json_content:
            # No JSON schema defined
            return errors

        # Get schema definition
        schema_def = json_content.get("schema", {})

        # Basic validation: check if data is dict when schema expects object
        if schema_def.get("type") == "object":
            if not isinstance(data, dict):
                errors.append(
                    {"field": "$", "error": f"Expected object, got {type(data).__name__}"}
                )
                return errors

            # Check required fields
            required = schema_def.get("required", [])
            for field in required:
                if field not in data:
                    errors.append({"field": field, "error": "Required field is missing"})

            # Check properties
            properties = schema_def.get("properties", {})
            for field, field_schema in properties.items():
                if field in data:
                    field_errors = self._validate_field(data[field], field_schema, field)
                    errors.extend(field_errors)

        return errors

    def _validate_field(self, value: Any, schema: Dict[str, Any], field_path: str) -> list:
        """
        Validate a single field against its schema.

        Args:
            value: The field value
            schema: The field schema
            field_path: The field path for error reporting

        Returns:
            List of validation errors
        """
        errors = []

        # Check type
        expected_type = schema.get("type")
        if expected_type:
            type_map = {
                "string": str,
                "integer": int,
                "number": (int, float),
                "boolean": bool,
                "array": list,
                "object": dict,
            }

            expected_python_type = type_map.get(expected_type)
            if (
                expected_python_type
                and expected_python_type != object
                and not isinstance(value, expected_python_type)  # type: ignore[arg-type]
            ):
                errors.append(
                    {
                        "field": field_path,
                        "error": f"Expected {expected_type}, got {type(value).__name__}",
                    }
                )

        return errors

    def _log_validation_failure(
        self,
        request: Request,
        response: Response,
        error: str,
        schema: Dict[str, Any],
        validation_errors: Optional[list] = None,
    ) -> None:
        """
        Log response validation failure.

        Args:
            request: The request object
            response: The response object
            error: Error description
            schema: The schema that was violated
            validation_errors: List of specific validation errors
        """
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            "Response schema validation failed",
            component="schema_validation",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            error=error,
            validation_errors=validation_errors or [],
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
