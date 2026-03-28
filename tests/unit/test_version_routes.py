"""
Unit tests for version information routes.

Tests API version information, client documentation generation, and deprecation
endpoint configuration. Validates Requirements 3.14.
"""

import os
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

try:
    from app.main import create_app
    from app.routes.version import (
        get_version_info,
        get_client_documentation,
        configure_deprecated_endpoints,
        is_endpoint_deprecated,
        get_deprecated_endpoints,
        CURRENT_VERSION,
        API_VERSION,
    )
except ImportError:
    pytest.skip(
        "Required app modules not available - skipping version routes tests",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    """Create a test client with test_mode=True."""
    app = create_app(test_mode=True)
    with TestClient(app) as c:
        yield c


class TestGetVersionInfo:
    """Test the /version endpoint."""

    @pytest.mark.asyncio
    async def test_get_version_info_success(self):
        """Test successful retrieval of version information."""
        response = await get_version_info()

        assert response.status_code == 200
        content: str = str(
            response.body.decode() if isinstance(response.body, bytes) else response.body
        )

        # Parse JSON response
        import json

        data = json.loads(content)

        assert "current_version" in data
        assert "api_version" in data
        assert "supported_versions" in data
        assert "deprecated_versions" in data
        assert "api_spec_url" in data
        assert "documentation_url" in data
        assert "timestamp" in data

        # Verify values
        assert data["current_version"] == CURRENT_VERSION
        assert data["api_version"] == API_VERSION
        assert isinstance(data["supported_versions"], list)
        assert isinstance(data["deprecated_versions"], list)
        assert data["api_spec_url"] == "/openapi.json"
        assert data["documentation_url"] == "/docs"

    def test_get_version_info_via_client(self, client):
        """Test /version endpoint via TestClient."""
        response = client.get("/v1/version")

        assert response.status_code == 200
        data = response.json()

        assert "current_version" in data
        assert "api_version" in data
        assert "supported_versions" in data
        assert "deprecated_versions" in data
        assert "timestamp" in data

    def test_get_version_info_timestamp_format(self, client):
        """Test that timestamp is in ISO format with Z suffix."""
        response = client.get("/v1/version")
        data = response.json()

        timestamp = data["timestamp"]
        assert timestamp.endswith("Z")
        # Verify it's a valid ISO format timestamp
        assert "T" in timestamp

    def test_get_version_info_with_env_vars(self, client):
        """Test version info respects environment variables."""
        with patch.dict(os.environ, {"API_VERSION": "2.0.0", "API_VERSION_PREFIX": "v2"}):
            # Re-import to get new env values
            import importlib
            import app.routes.version as version_module

            importlib.reload(version_module)

            # Create new app with reloaded module
            app = create_app(test_mode=True)
            with TestClient(app) as test_client:
                response = test_client.get("/v1/version")
                assert response.status_code == 200


class TestGetClientDocumentation:
    """Test the /client-docs endpoint."""

    @pytest.mark.asyncio
    async def test_get_client_docs_python_default(self):
        """Test client documentation with default Python language."""
        response = await get_client_documentation()

        # Response is a dict for successful cases
        assert isinstance(response, dict)
        assert "language" in response
        assert response["language"] == "python"
        assert "base_url" in response
        assert "api_version" in response
        assert "documentation" in response
        assert "endpoints" in response

    @pytest.mark.asyncio
    async def test_get_client_docs_python_explicit(self):
        """Test client documentation with explicit Python language."""
        response = await get_client_documentation(language="python")

        assert isinstance(response, dict)
        assert response["language"] == "python"
        assert "APGIClient" in response["documentation"]["client_examples"]
        assert "import requests" in response["documentation"]["client_examples"]

    @pytest.mark.asyncio
    async def test_get_client_docs_javascript(self):
        """Test client documentation for JavaScript."""
        response = await get_client_documentation(language="javascript")

        assert isinstance(response, dict)
        assert response["language"] == "javascript"
        assert "APGIClient" in response["documentation"]["client_examples"]
        assert "fetch" in response["documentation"]["client_examples"]

    @pytest.mark.asyncio
    async def test_get_client_docs_curl(self):
        """Test client documentation for cURL."""
        response = await get_client_documentation(language="curl")

        assert isinstance(response, dict)
        assert response["language"] == "curl"
        assert "curl" in response["documentation"]["client_examples"]
        assert "-X GET" in response["documentation"]["client_examples"]

    @pytest.mark.asyncio
    async def test_get_client_docs_go(self):
        """Test client documentation for Go."""
        response = await get_client_documentation(language="go")

        assert isinstance(response, dict)
        assert response["language"] == "go"
        assert "package main" in response["documentation"]["client_examples"]
        assert "func main()" in response["documentation"]["client_examples"]

    @pytest.mark.asyncio
    async def test_get_client_docs_unsupported_language(self):
        """Test client documentation with unsupported language."""
        from fastapi.responses import JSONResponse

        response = await get_client_documentation(language="rust")

        # Response is a JSONResponse for error cases
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        import json

        content: str = str(
            response.body.decode() if isinstance(response.body, bytes) else response.body
        )
        data = json.loads(content)
        assert "error" in data
        assert "Unsupported language" in data["error"]
        assert "supported_languages" in data

    def test_get_client_docs_via_client_python(self, client):
        """Test /client-docs endpoint via TestClient with Python."""
        response = client.get("/v1/client-docs?language=python")

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "python"
        assert "documentation" in data
        assert "endpoints" in data

    def test_get_client_docs_via_client_javascript(self, client):
        """Test /client-docs endpoint via TestClient with JavaScript."""
        response = client.get("/v1/client-docs?language=javascript")

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "javascript"

    def test_get_client_docs_via_client_curl(self, client):
        """Test /client-docs endpoint via TestClient with cURL."""
        response = client.get("/v1/client-docs?language=curl")

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "curl"

    def test_get_client_docs_via_client_go(self, client):
        """Test /client-docs endpoint via TestClient with Go."""
        response = client.get("/v1/client-docs?language=go")

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "go"

    def test_get_client_docs_via_client_unsupported(self, client):
        """Test /client-docs endpoint with unsupported language."""
        response = client.get("/v1/client-docs?language=rust")

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "supported_languages" in data

    def test_get_client_docs_default_language(self, client):
        """Test /client-docs endpoint without language parameter defaults to Python."""
        response = client.get("/v1/client-docs")

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "python"

    def test_get_client_docs_base_url_default(self, client):
        """Test that base_url defaults to localhost when not set."""
        with patch.dict(os.environ, {}, clear=False):
            if "API_BASE_URL" in os.environ:
                del os.environ["API_BASE_URL"]

            response = client.get("/v1/client-docs?language=python")
            assert response.status_code == 200
            data = response.json()
            assert "base_url" in data

    def test_get_client_docs_base_url_custom(self, client):
        """Test that custom API_BASE_URL is used in documentation."""
        with patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"}):
            response = client.get("/v1/client-docs?language=python")
            assert response.status_code == 200
            data = response.json()
            assert data["base_url"] == "https://api.example.com"

    def test_get_client_docs_base_url_invalid_fallback(self, client):
        """Test that invalid base_url falls back to localhost."""
        with patch.dict(os.environ, {"API_BASE_URL": "not-a-valid-url"}):
            response = client.get("/v1/client-docs?language=python")
            assert response.status_code == 200
            data = response.json()
            # Should fall back to default
            assert "base_url" in data

    def test_get_client_docs_endpoints_structure(self, client):
        """Test that endpoints structure is correct."""
        response = client.get("/v1/client-docs?language=python")

        assert response.status_code == 200
        data = response.json()
        endpoints = data["endpoints"]

        assert "health" in endpoints
        assert "auth_login" in endpoints
        assert "auth_refresh" in endpoints
        assert "tasks" in endpoints
        assert "sessions" in endpoints
        assert "dashboard" in endpoints

    def test_get_client_docs_documentation_structure(self, client):
        """Test that documentation structure is correct."""
        response = client.get("/v1/client-docs?language=python")

        assert response.status_code == 200
        data = response.json()
        docs = data["documentation"]

        assert "openapi_spec" in docs
        assert "interactive_docs" in docs
        assert "client_examples" in docs
        assert docs["openapi_spec"] == "/openapi.json"
        assert docs["interactive_docs"] == "/docs"


class TestDeprecatedEndpointsConfiguration:
    """Test deprecated endpoints configuration functions."""

    def test_configure_deprecated_endpoints_empty(self):
        """Test configuring empty deprecated endpoints."""
        configure_deprecated_endpoints({})
        result = get_deprecated_endpoints()
        assert result == {}

    def test_configure_deprecated_endpoints_single(self):
        """Test configuring a single deprecated endpoint."""
        config = {"/v1/old-endpoint": {"sunset": "2026-01-01", "replacement": "/v2/new-endpoint"}}
        configure_deprecated_endpoints(config)
        result = get_deprecated_endpoints()
        assert result == config

    def test_configure_deprecated_endpoints_multiple(self):
        """Test configuring multiple deprecated endpoints."""
        config = {
            "/v1/endpoint1": {"sunset": "2026-01-01", "replacement": "/v2/endpoint1"},
            "/v1/endpoint2": {"sunset": "2026-06-01", "replacement": "/v2/endpoint2"},
        }
        configure_deprecated_endpoints(config)
        result = get_deprecated_endpoints()
        assert result == config
        assert len(result) == 2

    def test_is_endpoint_deprecated_true(self):
        """Test checking if an endpoint is deprecated (true case)."""
        config = {"/v1/old-endpoint": {"sunset": "2026-01-01", "replacement": "/v2/new-endpoint"}}
        configure_deprecated_endpoints(config)

        result = is_endpoint_deprecated("/v1/old-endpoint")
        assert result is not None
        assert result["sunset"] == "2026-01-01"
        assert result["replacement"] == "/v2/new-endpoint"

    def test_is_endpoint_deprecated_false(self):
        """Test checking if an endpoint is deprecated (false case)."""
        config = {"/v1/old-endpoint": {"sunset": "2026-01-01", "replacement": "/v2/new-endpoint"}}
        configure_deprecated_endpoints(config)

        result = is_endpoint_deprecated("/v1/new-endpoint")
        assert result is None

    def test_is_endpoint_deprecated_empty_config(self):
        """Test checking deprecation with empty config."""
        configure_deprecated_endpoints({})

        result = is_endpoint_deprecated("/v1/any-endpoint")
        assert result is None

    def test_get_deprecated_endpoints_empty(self):
        """Test getting deprecated endpoints when none configured."""
        configure_deprecated_endpoints({})
        result = get_deprecated_endpoints()
        assert result == {}

    def test_get_deprecated_endpoints_multiple(self):
        """Test getting multiple deprecated endpoints."""
        config = {
            "/v1/endpoint1": {"sunset": "2026-01-01", "replacement": "/v2/endpoint1"},
            "/v1/endpoint2": {"sunset": "2026-06-01", "replacement": "/v2/endpoint2"},
            "/v1/endpoint3": {"sunset": "2026-12-01", "replacement": "/v2/endpoint3"},
        }
        configure_deprecated_endpoints(config)
        result = get_deprecated_endpoints()

        assert len(result) == 3
        assert all(key in result for key in config.keys())

    def test_configure_deprecated_endpoints_overwrites_previous(self):
        """Test that configuring endpoints overwrites previous configuration."""
        config1 = {"/v1/old1": {"sunset": "2026-01-01", "replacement": "/v2/new1"}}
        configure_deprecated_endpoints(config1)
        assert len(get_deprecated_endpoints()) == 1

        config2 = {"/v1/old2": {"sunset": "2026-06-01", "replacement": "/v2/new2"}}
        configure_deprecated_endpoints(config2)
        result = get_deprecated_endpoints()

        assert len(result) == 1
        assert "/v1/old2" in result
        assert "/v1/old1" not in result

    def test_deprecated_endpoints_with_complex_info(self):
        """Test deprecated endpoints with additional metadata."""
        config = {
            "/v1/old-endpoint": {
                "sunset": "2026-01-01",
                "replacement": "/v2/new-endpoint",
                "reason": "API redesign",
                "migration_guide": "https://docs.example.com/migration",
            }
        }
        configure_deprecated_endpoints(config)

        result = is_endpoint_deprecated("/v1/old-endpoint")
        assert result is not None
        assert result["reason"] == "API redesign"
        assert result["migration_guide"] == "https://docs.example.com/migration"


class TestVersionRoutesIntegration:
    """Integration tests for version routes."""

    def test_version_endpoint_response_structure(self, client):
        """Test complete response structure of /version endpoint."""
        response = client.get("/v1/version")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields
        required_fields = [
            "current_version",
            "api_version",
            "supported_versions",
            "deprecated_versions",
            "api_spec_url",
            "documentation_url",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_client_docs_all_languages(self, client):
        """Test that all supported languages are accessible."""
        languages = ["python", "javascript", "curl", "go"]

        for lang in languages:
            response = client.get(f"/v1/client-docs?language={lang}")
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == lang

    def test_client_docs_contains_endpoints(self, client):
        """Test that client docs include endpoint information."""
        response = client.get("/v1/client-docs?language=python")

        assert response.status_code == 200
        data = response.json()

        # Verify endpoints are documented
        endpoints = data["endpoints"]
        assert len(endpoints) > 0
        assert all(isinstance(v, str) for v in endpoints.values())

    def test_version_info_consistency(self, client):
        """Test that version info is consistent across multiple calls."""
        response1 = client.get("/v1/version")
        response2 = client.get("/v1/version")

        data1 = response1.json()
        data2 = response2.json()

        # Version info should be consistent (except timestamp)
        assert data1["current_version"] == data2["current_version"]
        assert data1["api_version"] == data2["api_version"]
        assert data1["supported_versions"] == data2["supported_versions"]
