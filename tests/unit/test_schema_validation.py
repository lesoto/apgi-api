"""Unit tests for schema_validation.py middleware."""

import json
import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, Mock, AsyncMock
from app.middleware.schema_validation import ResponseSchemaValidationMiddleware


class TestResponseSchemaValidationMiddleware:
    """Test ResponseSchemaValidationMiddleware functionality."""

    @pytest.fixture
    def validation_middleware(self):
        mock_app = MagicMock()
        return ResponseSchemaValidationMiddleware(app=mock_app)

    def test_valid_json_schema(self, validation_middleware):
        """Test valid JSON schema validation."""
        with patch("app.middleware.schema_validation.json.loads") as mock_loads:
            mock_loads.return_value = {"valid": "data"}

            # Create mock ASGI scope
            mock_scope = MagicMock()
            mock_scope.receive = MagicMock(return_value={"type": "http.request"})
            mock_scope.receive.return_value = {"type": "http.response", "body": {"valid": "data"}}

            # Process valid request
            result = validation_middleware.process_request(mock_scope)

            # Should pass validation
            assert result["body"] == {"valid": "data"}

    def test_invalid_json_schema(self, validation_middleware):
        """Test invalid JSON schema validation."""
        with patch("app.middleware.schema_validation.json.loads") as mock_loads:
            mock_loads.side_effect = ValueError("Invalid JSON")

            # Create mock ASGI scope
            mock_scope = MagicMock()
            mock_scope.receive = MagicMock(return_value={"type": "http.request"})
            mock_scope.receive.return_value = {"type": "http.response", "body": "invalid"}

            # Process invalid request
            result = validation_middleware.process_request(mock_scope)

            # Should return validation error
            assert "error" in result["body"].lower()
            assert result["status_code"] == 400

    def test_missing_content_type(self, validation_middleware):
        """Test missing content-type validation."""
        with patch("app.middleware.schema_validation.json.loads") as mock_loads:
            mock_loads.return_value = {"valid": "data"}

            # Create mock ASGI scope with missing content-type
            mock_scope = MagicMock()
            mock_scope.receive = MagicMock(return_value={"type": "http.request"})
            mock_scope.receive.return_value = {"type": "http.response", "body": {"valid": "data"}}

            # Remove content-type from headers
            mock_scope.receive.side_effect = [
                {"type": "http.request", "headers": {}},
                {"type": "http.response", "body": {"valid": "data"}},
            ]

            # Process request without content-type
            result = validation_middleware.process_request(mock_scope)

            # Should return validation error
            assert "content-type" in result["body"].lower()
            assert result["status_code"] == 400

    def test_large_payload_validation(self, validation_middleware):
        """Test large payload size validation."""
        with patch("app.middleware.schema_validation.json.loads") as mock_loads:
            mock_loads.return_value = {"valid": "data"}

            # Create mock ASGI scope with large payload
            mock_scope = MagicMock()
            mock_scope.receive = MagicMock(
                return_value={
                    "type": "http.request",
                    "headers": {"content-length": "10000000"},  # 10MB
                }
            )
            mock_scope.receive.return_value = {
                "type": "http.response",
                "body": "x" * 1000000,  # Large payload
            }

            # Process large request
            result = validation_middleware.process_request(mock_scope)

            # Should return size validation error
            assert "too large" in result["body"].lower()
            assert result["status_code"] == 413


class TestResponseSchemaValidationMiddlewareAdditional:
    """Test ResponseSchemaValidationMiddleware functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.openapi_schema = {
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

    def test_init_default(self):
        """Test middleware initialization with defaults."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app)
        assert middleware.app == app
        assert middleware.openapi_schema is None
        assert middleware.enabled is True
        assert middleware.fail_on_error is False
        assert middleware._schema_cache == {}

    def test_init_with_params(self):
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
    async def test_dispatch_disabled(self):
        """Test dispatch when validation is disabled."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app, enabled=False)
        request = Mock()
        call_next = AsyncMock(return_value=Mock())

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once_with(request)
        assert response == call_next.return_value

    @pytest.mark.asyncio
    async def test_dispatch_schema_load_failure(self):
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
    async def test_dispatch_successful_validation(self):
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
    async def test_dispatch_non_validatable_status(self):
        """Test dispatch with 5xx status (not validated)."""
        app = Mock()
        middleware = ResponseSchemaValidationMiddleware(app, openapi_schema=self.openapi_schema)
        request = Mock()
        response = Mock()
        response.status_code = 500
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)
        assert result == response

    def test_get_response_schema_exact_match(self):
        """Test getting response schema with exact path match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/api/test", "get", 200)
        assert schema is not None
        assert "content" in schema

    def test_get_response_schema_parametric_match(self):
        """Test getting response schema with path parameter match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/api/test/123", "get", 200)
        assert schema is not None
        assert "content" in schema

    def test_get_response_schema_no_match(self):
        """Test getting response schema with no match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        schema = middleware._get_response_schema("/nonexistent", "get", 200)
        assert schema is None

    def test_get_response_schema_default_response(self):
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

    def test_find_matching_path_exact(self):
        """Test finding matching path with exact match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/api/test")
        assert path_item is not None

    def test_find_matching_path_parametric(self):
        """Test finding matching path with parameters."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/api/test/123")
        assert path_item is not None

    def test_find_matching_path_no_match(self):
        """Test finding matching path with no match."""
        middleware = ResponseSchemaValidationMiddleware(Mock(), openapi_schema=self.openapi_schema)
        path_item = middleware._find_matching_path("/nonexistent/path")
        assert path_item is None

    @pytest.mark.asyncio
    async def test_get_response_body_regular_response(self):
        """Test getting response body from regular response."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        response.body = b'{"test": "data"}'

        body = await middleware._get_response_body(response)
        assert body == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_get_response_body_empty_body(self):
        """Test getting response body when empty."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        response.body = b""

        body = await middleware._get_response_body(response)
        assert body is None

    @pytest.mark.asyncio
    async def test_get_response_body_streaming_response(self):
        """Test getting response body from streaming response."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        response.body_iterator = AsyncMock()
        response.body_iterator.__aiter__ = AsyncMock(return_value=iter([b"chunk1", b"chunk2"]))

        body = await middleware._get_response_body(response)
        assert body == b"chunk1chunk2".decode()

    @pytest.mark.asyncio
    async def test_get_response_body_no_body_attr(self):
        """Test getting response body when no body attribute."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        response = Mock()
        # No body or body_iterator

        body = await middleware._get_response_body(response)
        assert body is None

    def test_validate_schema_valid_object(self):
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

    def test_validate_schema_missing_required(self):
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

    def test_validate_schema_wrong_type(self):
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

    def test_validate_schema_array_items(self):
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

    def test_validate_schema_string_pattern(self):
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

    def test_validate_field_string_type(self):
        """Test validating string field type."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field("test", {"type": "string"}, "field")
        assert errors == []

    def test_validate_field_wrong_type(self):
        """Test validating field with wrong type."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(123, {"type": "string"}, "field")
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_validate_field_array_items(self):
        """Test validating array field items."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(
            [1, 2], {"type": "array", "items": {"type": "string"}}, "field"
        )
        assert len(errors) == 2  # Both items are wrong type

    def test_validate_field_object_properties(self):
        """Test validating object field properties."""
        middleware = ResponseSchemaValidationMiddleware(Mock())
        errors = middleware._validate_field(
            {"prop": 123}, {"type": "object", "properties": {"prop": {"type": "string"}}}, "field"
        )
        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_log_validation_failure(self):
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
    async def test_validate_response_with_empty_body(self):
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
    async def test_validate_response_invalid_json(self):
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
    async def test_validate_response_validation_error(self):
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
    async def test_validate_response_no_schema(self):
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
from typing import Dict, Any
from unittest.mock import MagicMock as _MagicMock, AsyncMock as _AsyncMock


class TestSchemaValidationMiddlewareExtra:
    """Additional tests merged from test_schema_validation_middleware.py."""

    @pytest.mark.asyncio
    async def test_dispatch_loads_openapi_schema_from_app(self):
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
    async def test_validate_response_with_status_range(self):
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
    async def test_validate_response_with_nested_object(self):
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

    def test_validate_field_with_number_type(self):
        """Test field validation with number type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(123.45, {"type": "number"}, "field")
        assert errors == []

    def test_validate_field_with_boolean_type(self):
        """Test field validation with boolean type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(True, {"type": "boolean"}, "field")
        assert errors == []

    def test_validate_field_with_integer_type(self):
        """Test field validation with integer type."""
        middleware = ResponseSchemaValidationMiddleware(_MagicMock())
        errors = middleware._validate_field(42, {"type": "integer"}, "field")
        assert errors == []

    def test_find_matching_path_multi_segment_params(self):
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
