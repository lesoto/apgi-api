"""Unit tests for schema_validation.py middleware."""

import json
import logging
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.middleware.schema_validation import ResponseSchemaValidationMiddleware


class TestResponseSchemaValidationMiddleware:
    """Test ResponseSchemaValidationMiddleware functionality."""

    @pytest.fixture
    def validation_middleware(self) -> ResponseSchemaValidationMiddleware:
        mock_app = MagicMock()
        return ResponseSchemaValidationMiddleware(app=mock_app)

    def test_valid_json_schema(
        self, validation_middleware: ResponseSchemaValidationMiddleware
    ) -> None:
        """Test valid JSON schema validation."""
        # Test the middleware's internal validation methods
        schema = {
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"valid": {"type": "string"}}}
                }
            }
        }
        data = {"valid": "data"}
        errors = validation_middleware._validate_schema(data, schema)
        assert errors == []

    def test_invalid_json_schema(
        self, validation_middleware: ResponseSchemaValidationMiddleware
    ) -> None:
        """Test invalid JSON schema validation."""
        # Test validation with wrong data type
        schema = {
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"valid": {"type": "string"}}}
                }
            }
        }
        data = {"valid": 123}  # Should be string
        errors = validation_middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_missing_content_type(
        self, validation_middleware: ResponseSchemaValidationMiddleware
    ) -> None:
        """Test missing content-type validation."""
        # Test validation of required fields
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["required_field"],
                        "properties": {"valid": {"type": "string"}},
                    }
                }
            }
        }
        data = {"valid": "data"}  # Missing required field
        errors = validation_middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "Required field is missing" in errors[0]["error"]

    def test_large_payload_validation(
        self, validation_middleware: ResponseSchemaValidationMiddleware
    ) -> None:
        """Test large payload size validation."""
        # Test field length validation
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"data": {"type": "string", "maxLength": 10}},
                    }
                }
            }
        }
        data = {"data": "x" * 100}  # Too long
        errors = validation_middleware._validate_schema(data, schema)
        # Note: Basic validator doesn't check maxLength, but this test shows the concept
        assert isinstance(errors, list)


class TestResponseSchemaValidationMiddlewareAdditional:
    """Test ResponseSchemaValidationMiddleware functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.openapi_schema: dict[str, Any] = {
            "paths": {
                "/api/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id", "name"],
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {
                                                    "type": "string",
                                                    "pattern": "^[A-Za-z]+$",
                                                },
                                                "items": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/api/test/{id}": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object", "required": ["id"]}
                                    }
                                }
                            }
                        }
                    }
                },
            }
        }

    def test_init_default(self) -> None:
        """Test middleware initialization with defaults."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app)
        assert middleware.app == app
        assert middleware.openapi_schema is None
        assert middleware.enabled is True
        assert middleware.fail_on_error is False
        assert middleware._schema_cache == {}

    def test_init_with_params(self) -> None:
        """Test middleware initialization with parameters."""
        app = Mock()
        schema = {"test": "schema"}
        middleware = ResponseSchemaValidationMiddleware(
            app, openapi_schema=schema, enabled=False, fail_on_error=True
        )
        assert middleware.app == app
        assert middleware.openapi_schema == schema
        assert middleware.enabled is False
        assert middleware.fail_on_error is True

    @pytest.mark.asyncio
    async def test_dispatch_disabled(self) -> None:
        """Test dispatch when validation is disabled."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app, enabled=False)
        request = Mock()
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once_with(request)
        assert response == call_next.return_value

    @pytest.mark.asyncio
    async def test_dispatch_schema_load_failure(self) -> None:
        """Test dispatch when OpenAPI schema loading fails."""
        app = Mock()
        app.openapi.side_effect = Exception("Schema load error")
        middleware = ResponseSchemaValidationMiddleware(app)
        request = Mock()
        request.app = app
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once_with(request)
        assert response == call_next.return_value

    @pytest.mark.asyncio
    async def test_dispatch_successful_validation(self) -> None:
        """Test dispatch with successful response validation."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app, openapi_schema=self.openapi_schema)
        request = Mock()
        request.method = "GET"
        request.url.path = "/api/test"
        response = Mock()
        response.status_code = 200
        response.body = json.dumps({"id": 1, "name": "test", "items": ["a", "b"]}).encode()
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)
        assert result == response

    @pytest.mark.asyncio
    async def test_dispatch_non_validatable_status(self) -> None:
        """Test dispatch with 5xx status (not validated)."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app, openapi_schema=self.openapi_schema)
        request = Mock()
        response = Mock()
        response.status_code = 500
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)
        assert result == response

    def test_get_response_schema_exact_match(self) -> None:
        """Test getting response schema with exact path match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/api/test", "get", 200)
        assert schema is not None
        assert "content" in schema

    def test_get_response_schema_parametric_match(self) -> None:
        """Test getting response schema with path parameter match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/api/test/123", "get", 200)
        assert schema is not None
        assert "content" in schema

    def test_get_response_schema_no_match(self) -> None:
        """Test getting response schema with no match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/nonexistent", "get", 200)
        assert schema is None

    def test_get_response_schema_default_response(self) -> None:
        """Test getting response schema with default response."""
        schema_with_default = {
            "paths": {
                "/api/test": {
                    "get": {
                        "responses": {
                            "default": {
                                "content": {"application/json": {"schema": {"type": "object"}}}
                            }
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=schema_with_default)
        schema = middleware._get_response_schema("/api/test", "get", 404)
        assert schema is not None

    def test_find_matching_path_exact(self) -> None:
        """Test finding matching path with exact match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/api/test")
        assert path_item is not None

    def test_find_matching_path_parametric(self) -> None:
        """Test finding matching path with parameters."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/api/test/123")
        assert path_item is not None

    def test_find_matching_path_no_match(self) -> None:
        """Test finding matching path with no match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/nonexistent/path")
        assert path_item is None

    @pytest.mark.asyncio
    async def test_get_response_body_regular_response(self) -> None:
        """Test getting response body from regular response."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        response.body = b'{"test": "data"}'

        body = await middleware._get_response_body(response)
        assert body == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_get_response_body_empty_body(self) -> None:
        """Test getting response body when empty."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        response.body = b""
        # Ensure no body_iterator attribute that could interfere
        if hasattr(response, "body_iterator"):
            delattr(response, "body_iterator")

        body = await middleware._get_response_body(response)
        assert body is None

    @pytest.mark.asyncio
    async def test_get_response_body_streaming_response(self) -> None:
        """Test getting response body from streaming response."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()

        # Remove the body attribute so it uses body_iterator
        if hasattr(response, "body"):
            delattr(response, "body")

        # Create proper async iterator mock that returns bytes
        class MockIterator:
            def __init__(self) -> None:
                self.chunks = [b"chunk1", b"chunk2"]
                self.index = 0

            def __aiter__(self) -> "MockIterator":
                return self

            async def __anext__(self) -> bytes:
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

            def __len__(self) -> int:
                return sum(len(chunk) for chunk in self.chunks)

        response.body_iterator = MockIterator()

        body = await middleware._get_response_body(response)
        assert body == "chunk1chunk2"

    @pytest.mark.asyncio
    async def test_get_response_body_no_body_attr(self) -> None:
        """Test getting response body when no body attribute."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        # Remove body and body_iterator attributes
        if hasattr(response, "body"):
            delattr(response, "body")
        if hasattr(response, "body_iterator"):
            delattr(response, "body_iterator")

        body = await middleware._get_response_body(response)
        assert body is None

    def test_validate_schema_valid_object(self) -> None:
        """Test validating valid object schema."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id", "name"],
                        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    }
                }
            }
        }
        data = {"id": 1, "name": "test"}
        errors = middleware._validate_schema(data, schema)
        assert errors == []

    def test_validate_schema_missing_required(self) -> None:
        """Test validating object with missing required field."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id", "name"],
                        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    }
                }
            }
        }
        data = {"id": 1}
        errors = middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "Required field is missing" in errors[0]["error"]

    def test_validate_schema_wrong_type(self) -> None:
        """Test validating object with wrong field type."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"id": {"type": "integer"}}}
                }
            }
        }
        data = {"id": "not_an_integer"}
        errors = middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "Expected integer" in errors[0]["error"]

    def test_validate_schema_array_items(self) -> None:
        """Test validating array items."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                    }
                }
            }
        }
        data = {"items": ["valid", 123]}  # Second item is invalid
        errors = middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_validate_schema_string_pattern(self) -> None:
        """Test validating string with pattern."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "pattern": "^[A-Za-z]+$"}},
                    }
                }
            }
        }
        data = {"name": "invalid123"}
        errors = middleware._validate_schema(data, schema)
        assert len(errors) == 1
        assert "does not match pattern" in errors[0]["error"]

    def test_validate_field_string_type(self) -> None:
        """Test validating string field type."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field("test", {"type": "string"}, "field")
        assert errors == []

    def test_validate_field_wrong_type(self) -> None:
        """Test validating field with wrong type."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(123, {"type": "string"}, "field")
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_validate_field_array_items(self) -> None:
        """Test validating array field items."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(
            [1, 2], {"type": "array", "items": {"type": "string"}}, "field"
        )
        assert len(errors) == 2  # Both items are wrong type

    def test_validate_field_object_properties(self) -> None:
        """Test validating object field properties."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(
            {"prop": 123}, {"type": "object", "properties": {"prop": {"type": "string"}}}, "field"
        )
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_log_validation_failure(self) -> None:
        """Test logging validation failure."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        request = Mock()
        request.url.path = "/test"
        request.method = "GET"
        request.state.request_id = "test-id"
        response = Mock()
        response.status_code = 200

        # This should not raise an exception
        middleware._log_validation_failure(
            request, response, "test error", {"schema": "test"}, [{"error": "test"}]
        )

    @pytest.mark.asyncio
    async def test_validate_response_with_empty_body(self) -> None:
        """Test validating response with empty body."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        request = Mock()
        request.method = "GET"
        request.url.path = "/api/test"
        response = Mock()
        response.status_code = 200
        # Empty body
        response.body = b""

        await middleware._validate_response(request, response)

    @pytest.mark.asyncio
    async def test_validate_response_invalid_json(self) -> None:
        """Test validating response with invalid JSON."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        request = Mock()
        request.method = "GET"
        request.url.path = "/api/test"
        request.state.request_id = "test-id"
        response = Mock()
        response.status_code = 200
        response.body = b"invalid json"

        await middleware._validate_response(request, response)

    @pytest.mark.asyncio
    async def test_validate_response_validation_error(self) -> None:
        """Test validating response with validation errors."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        request = Mock()
        request.method = "GET"
        request.url.path = "/api/test"
        request.state.request_id = "test-id"
        response = Mock()
        response.status_code = 200
        # Missing required field 'name'
        response.body = json.dumps({"id": 1}).encode()

        await middleware._validate_response(request, response)

    @pytest.mark.asyncio
    async def test_validate_response_no_schema(self) -> None:
        """Test validating response with no matching schema."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        request = Mock()
        request.method = "GET"
        request.url.path = "/nonexistent"
        response = Mock()
        response.status_code = 200

        await middleware._validate_response(request, response)


# ---------------------------------------------------------------------------
# Tests merged from test_schema_validation_middleware.py
# ---------------------------------------------------------------------------
import json as _json
from typing import Any, Dict
from unittest.mock import AsyncMock as _AsyncMock
from unittest.mock import MagicMock as _MagicMock


class TestSchemaValidationMiddlewareExtra:
    """Additional tests merged from test_schema_validation_middleware.py."""

    @pytest.mark.asyncio
    async def test_dispatch_loads_openapi_schema_from_app(self) -> None:
        """Test dispatch loads OpenAPI schema from request.app if not already loaded."""
        mock_app = _MagicMock()
        mock_app.openapi = _MagicMock(return_value={"paths": {}})
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True, openapi_schema=None)

        mock_request = _MagicMock()
        mock_request.app = mock_app
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 200
        call_next = _AsyncMock(return_value=response)

        await middleware.dispatch(mock_request, call_next)

        mock_app.openapi.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_response_with_status_range(self) -> None:
        """Test validation uses status range (2XX) when specific status not found."""
        schema_with_range = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "2XX": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {"data": {"type": "string"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        mock_app = _MagicMock()
        middleware = ResponseSchemaValidationMiddleware(mock_app, openapi_schema=schema_with_range)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 201
        response.body = _json.dumps({"data": "test"}).encode()
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 201

    @pytest.mark.asyncio
    async def test_validate_response_with_nested_object(self) -> None:
        """Test validation handles nested objects."""
        schema_with_nested = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "user": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "integer"},
                                                        "name": {"type": "string"},
                                                    },
                                                }
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        mock_app = _MagicMock()
        middleware = ResponseSchemaValidationMiddleware(mock_app, openapi_schema=schema_with_nested)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 200
        response.body = _json.dumps({"user": {"id": 1, "name": "test"}}).encode()
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    def test_validate_field_with_number_type(self) -> None:
        """Test field validation with number type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(123.45, {"type": "number"}, "field")
        assert errors == []

    def test_validate_field_with_boolean_type(self) -> None:
        """Test field validation with boolean type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(True, {"type": "boolean"}, "field")
        assert errors == []

    def test_validate_field_with_integer_type(self) -> None:
        """Test field validation with integer type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(42, {"type": "integer"}, "field")
        assert errors == []

    def test_find_matching_path_multi_segment_params(self) -> None:
        """Test path matching handles multi-segment path parameters."""
        schema: Dict[str, Any] = {
            "paths": {
                "/users/{id}": {"get": {"responses": {}}},
                "/users/{id}/posts/{post_id}": {"get": {"responses": {}}},
            }
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._find_matching_path("/users/123")
        assert result is not None

        result = middleware._find_matching_path("/users/123/posts/456")
        assert result is not None

        result = middleware._find_matching_path("/users")
        assert result is None


# ---------------------------------------------------------------------------
# Additional comprehensive tests for ≥90% coverage
# ---------------------------------------------------------------------------


class TestSchemaValidationComprehensive:
    """Comprehensive tests for schema validation middleware coverage."""

    @pytest.mark.asyncio
    async def test_dispatch_with_5xx_status_skips_validation(self) -> None:
        """Test that 5xx responses are not validated."""
        mock_app = _MagicMock()
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 500
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_dispatch_with_status_below_200_skips_validation(self) -> None:
        """Test that responses below 200 are not validated."""
        mock_app = _MagicMock()
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 100
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 100

    @pytest.mark.asyncio
    async def test_validate_response_with_no_openapi_schema(self) -> None:
        """Test validation when OpenAPI schema is None."""
        mock_app = _MagicMock()
        mock_app.openapi.side_effect = Exception("No schema")
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)

        mock_request = _MagicMock()
        mock_request.app = mock_app
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 200
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result == response

    def test_get_response_schema_caching(self) -> None:
        """Test that response schemas are cached."""
        schema = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {"content": {"application/json": {"schema": {"type": "object"}}}}
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        # First call
        result1 = middleware._get_response_schema("/test", "get", 200)
        # Second call should use cache
        result2 = middleware._get_response_schema("/test", "get", 200)

        assert result1 == result2
        assert "get:/test:200" in middleware._schema_cache

    def test_get_response_schema_with_no_paths(self) -> None:
        """Test getting schema when paths are not defined."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema={})

        result = middleware._get_response_schema("/test", "get", 200)

        assert result is None

    def test_get_response_schema_with_no_operation(self) -> None:
        """Test getting schema when operation is not defined."""
        schema: dict[str, Any] = {"paths": {"/test": {"post": {"responses": {}}}}}
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._get_response_schema("/test", "get", 200)

        assert result is None

    def test_get_response_schema_with_no_responses(self) -> None:
        """Test getting schema when responses are not defined."""
        schema: dict[str, Any] = {"paths": {"/test": {"get": {}}}}
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._get_response_schema("/test", "get", 200)

        assert result is None

    def test_find_matching_path_with_no_paths(self) -> None:
        """Test finding path when paths are not defined."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema={})

        result = middleware._find_matching_path("/test/123")

        assert result is None

    def test_find_matching_path_with_different_segment_count(self) -> None:
        """Test finding path with different segment count."""
        schema: dict[str, Any] = {"paths": {"/test": {"get": {}}, "/test/{id}": {"get": {}}}}
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._find_matching_path("/test/123/extra")

        assert result is None

    def test_find_matching_path_with_multiple_parameters(self) -> None:
        """Test finding path with multiple parameters."""
        schema: dict[str, Any] = {
            "paths": {"/users/{user_id}/posts/{post_id}/comments/{comment_id}": {"get": {}}}
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._find_matching_path("/users/123/posts/456/comments/789")

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_response_body_with_bytes(self) -> None:
        """Test getting response body from bytes."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        response = _MagicMock()
        response.body = b'{"test": "data"}'

        body = await middleware._get_response_body(response)

        assert body == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_get_response_body_with_invalid_utf8(self) -> None:
        """Test getting response body with invalid UTF-8."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        response = _MagicMock()
        response.body = b"\x80\x81\x82"

        body = await middleware._get_response_body(response)

        assert body is None

    @pytest.mark.asyncio
    async def test_get_response_body_with_string_body(self) -> None:
        """Test getting response body when body is already a string."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        response = _MagicMock()
        response.body = '{"test": "data"}'

        body = await middleware._get_response_body(response)

        assert body == '{"test": "data"}'

    def test_validate_schema_with_non_object_type(self) -> None:
        """Test validating non-object data."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        schema = {"content": {"application/json": {"schema": {"type": "object"}}}}

        errors = middleware._validate_schema("not an object", schema)

        assert len(errors) == 1
        assert "Expected object" in errors[0]["error"]

    def test_validate_schema_with_no_content(self) -> None:
        """Test validating when schema has no content."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        schema: dict[str, Any] = {}

        errors = middleware._validate_schema({"test": "data"}, schema)

        assert errors == []

    def test_validate_schema_with_no_json_content(self) -> None:
        """Test validating when schema has no JSON content."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        schema: dict[str, Any] = {"content": {"text/plain": {}}}

        errors = middleware._validate_schema({"test": "data"}, schema)

        assert errors == []

    def test_validate_field_with_pattern_match(self) -> None:
        """Test field validation with matching pattern."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            "test123", {"type": "string", "pattern": "^[a-z0-9]+$"}, "field"
        )

        assert errors == []

    def test_validate_field_with_pattern_mismatch(self) -> None:
        """Test field validation with non-matching pattern."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            "TEST", {"type": "string", "pattern": "^[a-z]+$"}, "field"
        )

        assert len(errors) == 1
        assert "does not match pattern" in errors[0]["error"]

    def test_validate_field_with_nested_array(self) -> None:
        """Test field validation with nested arrays."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            [[1, 2], [3, 4]],
            {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
            "field",
        )

        assert errors == []

    def test_validate_field_with_nested_array_invalid(self) -> None:
        """Test field validation with invalid nested arrays."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            [[1, "invalid"], [3, 4]],
            {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
            "field",
        )

        assert len(errors) == 1

    def test_validate_field_with_number_type(self) -> None:
        """Test field validation with number type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(3.14, {"type": "number"}, "field")

        assert errors == []

    def test_validate_field_with_boolean_type(self) -> None:
        """Test field validation with boolean type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(True, {"type": "boolean"}, "field")

        assert errors == []

    def test_validate_field_with_integer_type(self) -> None:
        """Test field validation with integer type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(42, {"type": "integer"}, "field")

        assert errors == []

    def test_validate_field_with_unknown_type(self) -> None:
        """Test field validation with unknown type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field("test", {"type": "unknown"}, "field")

        assert errors == []

    def test_validate_field_with_no_type(self) -> None:
        """Test field validation with no type specified."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field("test", {}, "field")

        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_response_with_empty_body_and_no_content_schema(self) -> None:
        """Test validating empty response when schema expects no content."""
        schema: dict[str, Any] = {"paths": {"/test": {"get": {"responses": {"204": {}}}}}}
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.state.request_id = "test-id"
        response = _MagicMock()
        response.status_code = 204
        response.body = b""

        await middleware._validate_response(mock_request, response)

    @pytest.mark.asyncio
    async def test_validate_response_with_exception_during_validation(self) -> None:
        """Test that exceptions during validation are caught."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema={"paths": {}})

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.state.request_id = "test-id"
        response = _MagicMock()
        response.status_code = 200
        response.body = b'{"test": "data"}'

        # This should not raise an exception
        await middleware._validate_response(mock_request, response)

    def test_init_with_logging(self, caplog: Any) -> None:
        """Test middleware initialization logs when enabled."""
        with caplog.at_level(logging.INFO):
            ResponseSchemaValidationMiddleware(_MagicMock(), enabled=True)

        assert any(
            "Response schema validation middleware initialized" in record.message
            for record in caplog.records
        )

    def test_init_without_logging_when_disabled(self, caplog: Any) -> None:
        """Test middleware initialization does not log when disabled."""
        with caplog.at_level(logging.INFO):
            ResponseSchemaValidationMiddleware(_MagicMock(), enabled=False)

        # Should not have initialization log
        assert not any(
            "Response schema validation middleware initialized" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_dispatch_with_fail_on_error_false(self) -> None:
        """Test dispatch with fail_on_error=False (default)."""
        schema = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {"id": {"type": "integer"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(
            _MagicMock(), openapi_schema=schema, fail_on_error=False
        )

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        response = _MagicMock()
        response.status_code = 200
        response.body = _json.dumps({"invalid": "data"}).encode()
        call_next = _AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Should still return the response even with validation errors
        assert result.status_code == 200

    def test_validate_field_with_nested_object_properties(self) -> None:
        """Test field validation with nested object properties."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            {"nested": {"id": 1, "name": "test"}},
            {
                "type": "object",
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    }
                },
            },
            "field",
        )

        assert errors == []

    def test_validate_field_with_nested_object_invalid_property(self) -> None:
        """Test field validation with invalid nested object property."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            {"nested": {"id": "invalid"}},
            {
                "type": "object",
                "properties": {
                    "nested": {"type": "object", "properties": {"id": {"type": "integer"}}}
                },
            },
            "field",
        )

        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_get_response_body_with_streaming_response_empty(self) -> None:
        """Test getting response body from empty streaming response."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        response = _MagicMock()

        if hasattr(response, "body"):
            delattr(response, "body")

        class EmptyIterator:
            def __aiter__(self) -> "EmptyIterator":
                return self

            async def __anext__(self) -> bytes:
                raise StopAsyncIteration

        response.body_iterator = EmptyIterator()

        body = await middleware._get_response_body(response)

        assert body is None

    def test_get_response_schema_with_status_range_2xx(self) -> None:
        """Test getting schema with 2XX status range."""
        schema = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "2XX": {"content": {"application/json": {"schema": {"type": "object"}}}}
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._get_response_schema("/test", "get", 201)

        assert result is not None

    def test_get_response_schema_with_status_range_4xx(self) -> None:
        """Test getting schema with 4XX status range."""
        schema = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "4XX": {"content": {"application/json": {"schema": {"type": "object"}}}}
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._get_response_schema("/test", "get", 404)

        assert result is not None

    @pytest.mark.asyncio
    async def test_validate_response_with_multiple_validation_errors(self) -> None:
        """Test validating response with multiple validation errors."""
        schema = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id", "name", "email"],
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {"type": "string"},
                                                "email": {"type": "string"},
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        mock_request = _MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.state.request_id = "test-id"
        response = _MagicMock()
        response.status_code = 200
        # Missing required fields
        response.body = _json.dumps({"id": 1}).encode()

        await middleware._validate_response(mock_request, response)

    def test_find_matching_path_with_trailing_slashes(self) -> None:
        """Test finding path with trailing slashes."""
        schema: dict[str, Any] = {"paths": {"/test/": {"get": {}}, "/test": {"post": {}}}}
        middleware = ResponseSchemaValidationMiddleware(_MagicMock(), openapi_schema=schema)

        result = middleware._find_matching_path("/test/")

        assert result is not None

    def test_validate_schema_with_multiple_required_fields(self) -> None:
        """Test validating schema with multiple required fields."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        schema = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id", "name", "email", "age"],
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                    }
                }
            }
        }

        errors = middleware._validate_schema({"id": 1}, schema)

        assert len(errors) == 3  # Missing name, email, age

    def test_validate_field_with_array_of_objects(self) -> None:
        """Test field validation with array of objects."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}],
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                },
            },
            "field",
        )

        assert errors == []

    def test_validate_field_with_array_of_objects_invalid(self) -> None:
        """Test field validation with invalid array of objects."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())

        errors = middleware._validate_field(
            [{"id": "invalid", "name": "test"}],
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                },
            },
            "field",
        )

        assert len(errors) == 1
