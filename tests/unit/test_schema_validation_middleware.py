"""
Tests for schema validation middleware.

Tests for response schema validation against OpenAPI schemas.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request, Response
import json


@pytest.fixture
def mock_app():
    """Mock FastAPI application."""
    app = MagicMock()
    app.openapi = MagicMock(
        return_value={
            "paths": {
                "/test": {
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
                                                "name": {"type": "string"},
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
    )
    return app


@pytest.fixture
def middleware(mock_app):
    """Create middleware instance."""
    from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

    return ResponseSchemaValidationMiddleware(mock_app, enabled=True)


@pytest.fixture
def mock_request():
    """Mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = "/test"
    request.method = "GET"
    request.app = MagicMock()
    request.state = MagicMock()
    request.state.request_id = "test-123"
    return request


class TestResponseSchemaValidationMiddleware:
    """Tests for ResponseSchemaValidationMiddleware class."""

    def test_init_with_openapi_schema(self, mock_app):
        """Test initialization with OpenAPI schema."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        schema = {"paths": {}}
        middleware = ResponseSchemaValidationMiddleware(mock_app, openapi_schema=schema)

        assert middleware.openapi_schema == schema
        assert middleware.enabled is True
        assert middleware.fail_on_error is False

    def test_init_disabled(self, mock_app):
        """Test initialization with validation disabled."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=False)

        assert middleware.enabled is False

    def test_init_with_fail_on_error(self, mock_app):
        """Test initialization with fail_on_error enabled."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        middleware = ResponseSchemaValidationMiddleware(mock_app, fail_on_error=True)

        assert middleware.fail_on_error is True

    @pytest.mark.asyncio
    async def test_dispatch_when_disabled(self, middleware, mock_request):
        """Test dispatch skips validation when disabled."""
        middleware.enabled = False
        call_next = AsyncMock(return_value=Response(status_code=200))

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_with_5xx_response(self, middleware, mock_request):
        """Test dispatch skips validation for 5xx responses."""
        call_next = AsyncMock(return_value=Response(status_code=500))

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 500
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_loads_openapi_schema(self, mock_request):
        """Test dispatch loads OpenAPI schema if not already loaded."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app = MagicMock()
        mock_app.openapi = MagicMock(return_value={"paths": {}})
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True, openapi_schema=None)

        mock_request.app = mock_app
        call_next = AsyncMock(return_value=Response(status_code=200))

        await middleware.dispatch(mock_request, call_next)

        mock_app.openapi.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_handles_openapi_load_error(self, mock_request):
        """Test dispatch handles OpenAPI schema load errors gracefully."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app = MagicMock()
        mock_app.openapi = MagicMock(side_effect=Exception("Load error"))
        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True, openapi_schema=None)

        mock_request.app = mock_app
        call_next = AsyncMock(return_value=Response(status_code=200))

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_validate_response_with_valid_data(self, middleware, mock_request):
        """Test validation passes with valid response data."""
        response_data = {"id": 1, "name": "test"}
        response = Response(
            content=json.dumps(response_data).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_missing_required_field(self, middleware, mock_request):
        """Test validation logs error for missing required field."""
        response_data = {"id": 1}  # Missing 'name' field
        response = Response(
            content=json.dumps(response_data).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Should still return response but log validation failure
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_wrong_type(self, middleware, mock_request):
        """Test validation logs error for wrong field type."""
        response_data = {"id": "not-an-int", "name": "test"}
        response = Response(
            content=json.dumps(response_data).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Should still return response but log validation failure
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_invalid_json(self, middleware, mock_request):
        """Test validation handles invalid JSON gracefully."""
        response = Response(
            content=b"not valid json",
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Should still return response but log validation failure
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_empty_body(self, middleware, mock_request):
        """Test validation handles empty response body."""
        response = Response(content=b"", status_code=200, media_type="application/json")

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        # Should still return response but log validation failure
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_no_schema_defined(self, middleware, mock_request):
        """Test validation skips when no schema is defined."""
        mock_request.url.path = "/undefined"
        response = Response(
            content=json.dumps({"data": "test"}).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_path_parameters(self, mock_app, mock_request):
        """Test validation handles path parameters correctly."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
            "paths": {
                "/test/{id}": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test/123"
        response = Response(
            content=json.dumps({"id": 123}).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_default_response(self, mock_app, mock_request):
        """Test validation uses default response when specific status not found."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "default": {
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"
        response = Response(
            content=json.dumps({"data": "test"}).encode(),
            status_code=201,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 201

    @pytest.mark.asyncio
    async def test_validate_response_with_status_range(self, mock_app, mock_request):
        """Test validation uses status range when specific status not found."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"
        response = Response(
            content=json.dumps({"data": "test"}).encode(),
            status_code=201,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 201

    @pytest.mark.asyncio
    async def test_validate_response_with_nested_object(self, mock_app, mock_request):
        """Test validation handles nested objects."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"
        response = Response(
            content=json.dumps({"user": {"id": 1, "name": "test"}}).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_array(self, mock_app, mock_request):
        """Test validation handles array types."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
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
                                                "items": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"
        response = Response(
            content=json.dumps({"items": ["a", "b", "c"]}).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_pattern_validation(self, mock_app, mock_request):
        """Test validation handles pattern matching."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
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
                                                "email": {
                                                    "type": "string",
                                                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"
        response = Response(
            content=json.dumps({"email": "test@example.com"}).encode(),
            status_code=200,
            media_type="application/json",
        )

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_response_with_streaming_response(self, mock_app, mock_request):
        """Test validation handles streaming responses."""
        from app.middleware.schema_validation import ResponseSchemaValidationMiddleware

        mock_app.openapi.return_value = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
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

        middleware = ResponseSchemaValidationMiddleware(mock_app, enabled=True)
        mock_request.url.path = "/test"

        # Create streaming response
        async def body_iterator():
            yield b'{"data": "test"}'

        response = MagicMock(spec=Response)
        response.status_code = 200
        response.body_iterator = body_iterator()

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 200

    def test_get_response_schema_uses_cache(self, middleware):
        """Test schema retrieval uses cache."""
        middleware.openapi_schema = {
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

        # First call
        schema1 = middleware._get_response_schema("/test", "get", 200)
        # Second call should use cache
        schema2 = middleware._get_response_schema("/test", "get", 200)

        assert schema1 is not None
        assert schema1 == schema2

    def test_find_matching_path_with_parameters(self, middleware):
        """Test path matching handles parameters."""
        middleware.openapi_schema = {
            "paths": {
                "/users/{id}": {"get": {"responses": {}}},
                "/users/{id}/posts/{post_id}": {"get": {"responses": {}}},
            }
        }

        # Should match /users/{id}
        result = middleware._find_matching_path("/users/123")
        assert result is not None

        # Should match /users/{id}/posts/{post_id}
        result = middleware._find_matching_path("/users/123/posts/456")
        assert result is not None

        # Should not match
        result = middleware._find_matching_path("/users")
        assert result is None

    def test_validate_field_with_string(self, middleware):
        """Test field validation with string type."""
        schema = {"type": "string"}
        errors = middleware._validate_field("test", schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_wrong_string_type(self, middleware):
        """Test field validation fails with wrong string type."""
        schema = {"type": "string"}
        errors = middleware._validate_field(123, schema, "field")

        assert len(errors) == 1
        assert "Expected string" in errors[0]["error"]

    def test_validate_field_with_integer(self, middleware):
        """Test field validation with integer type."""
        schema = {"type": "integer"}
        errors = middleware._validate_field(123, schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_number(self, middleware):
        """Test field validation with number type."""
        schema = {"type": "number"}
        errors = middleware._validate_field(123.45, schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_boolean(self, middleware):
        """Test field validation with boolean type."""
        schema = {"type": "boolean"}
        errors = middleware._validate_field(True, schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_array(self, middleware):
        """Test field validation with array type."""
        schema = {"type": "array", "items": {"type": "string"}}
        errors = middleware._validate_field(["a", "b"], schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_object(self, middleware):
        """Test field validation with object type."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        errors = middleware._validate_field({"name": "test"}, schema, "field")

        assert len(errors) == 0

    def test_validate_field_with_pattern_mismatch(self, middleware):
        """Test field validation fails with pattern mismatch."""
        schema = {"type": "string", "pattern": r"^\d+$"}
        errors = middleware._validate_field("abc", schema, "field")

        assert len(errors) == 1
        assert "does not match pattern" in errors[0]["error"]
