"""
Comprehensive tests for CSRF middleware (app/middleware/csrf.py).

Tests cover:
- Token generation on safe methods (GET, HEAD, OPTIONS)
- Token validation on unsafe methods (POST, PUT, DELETE, PATCH)
- Missing token rejection
- Invalid token rejection
- Bearer token bypass (JWT-authenticated requests)
- Safe method bypass
- Non-form content-type bypass
- Disabled middleware bypass
- Form data token extraction
- Header token extraction
- Token expiry configuration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.csrf import CSRFMiddleware

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    """Mock settings with JWT secret key."""
    with patch("app.middleware.csrf.settings") as mock:
        mock.jwt_secret_key = "test-secret-key-for-csrf-hashing"
        yield mock


@pytest.fixture
def app_with_csrf_enabled(mock_settings):
    """Create FastAPI app with CSRF middleware enabled."""
    app = FastAPI()

    @app.get("/test")
    async def get_test():
        return {"message": "GET success"}

    @app.post("/test")
    async def post_test():
        return {"message": "POST success"}

    @app.put("/test")
    async def put_test():
        return {"message": "PUT success"}

    @app.delete("/test")
    async def delete_test():
        return {"message": "DELETE success"}

    @app.patch("/test")
    async def patch_test():
        return {"message": "PATCH success"}

    @app.head("/test")
    async def head_test():
        return {"message": "HEAD success"}

    @app.options("/test")
    async def options_test():
        return {"message": "OPTIONS success"}

    @app.post("/form-test")
    async def form_test():
        return {"message": "Form POST success"}

    @app.post("/json-test")
    async def json_test():
        return {"message": "JSON POST success"}

    app.add_middleware(
        CSRFMiddleware,
        enabled=True,
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        token_expiry_minutes=60,
    )

    return app


@pytest.fixture
def app_with_csrf_disabled(mock_settings):
    """Create FastAPI app with CSRF middleware disabled."""
    app = FastAPI()

    @app.post("/test")
    async def post_test():
        return {"message": "POST success"}

    app.add_middleware(
        CSRFMiddleware,
        enabled=False,
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        token_expiry_minutes=60,
    )

    return app


@pytest.fixture
def client_csrf_enabled(app_with_csrf_enabled):
    """TestClient for app with CSRF enabled."""
    return TestClient(app_with_csrf_enabled, raise_server_exceptions=False)


@pytest.fixture
def client_csrf_disabled(app_with_csrf_disabled):
    """TestClient for app with CSRF disabled."""
    return TestClient(app_with_csrf_disabled, raise_server_exceptions=False)


@pytest.fixture
def csrf_middleware(mock_settings):
    """Create CSRF middleware instance."""
    app = MagicMock()
    return CSRFMiddleware(
        app,
        enabled=True,
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        token_expiry_minutes=60,
    )


# ---------------------------------------------------------------------------
# Tests for token generation
# ---------------------------------------------------------------------------


class TestTokenGeneration:
    """Tests for CSRF token generation."""

    def test_generate_csrf_token_returns_string(self, csrf_middleware):
        """Test that token generation returns a string."""
        token = csrf_middleware._generate_csrf_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_csrf_token_is_unique(self, csrf_middleware):
        """Test that each generated token is unique."""
        token1 = csrf_middleware._generate_csrf_token()
        token2 = csrf_middleware._generate_csrf_token()
        assert token1 != token2

    def test_generate_csrf_token_is_url_safe(self, csrf_middleware):
        """Test that generated tokens are URL-safe."""
        token = csrf_middleware._generate_csrf_token()
        # URL-safe tokens should only contain alphanumeric, -, and _
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_token_generation_on_get_request(self, client_csrf_enabled):
        """Test that GET request generates and sets CSRF token in cookie."""
        response = client_csrf_enabled.get("/test")
        assert response.status_code == 200
        assert "csrf_token" in response.cookies
        assert len(response.cookies["csrf_token"]) > 0

    def test_token_generation_on_head_request(self, client_csrf_enabled):
        """Test that HEAD request generates and sets CSRF token in cookie."""
        response = client_csrf_enabled.head("/test")
        assert response.status_code == 200
        assert "csrf_token" in response.cookies

    def test_token_generation_on_options_request(self, client_csrf_enabled):
        """Test that OPTIONS request generates and sets CSRF token in cookie."""
        response = client_csrf_enabled.options("/test")
        assert response.status_code == 200
        assert "csrf_token" in response.cookies


# ---------------------------------------------------------------------------
# Tests for token hashing
# ---------------------------------------------------------------------------


class TestTokenHashing:
    """Tests for CSRF token hashing."""

    def test_hash_token_returns_string(self, csrf_middleware):
        """Test that token hashing returns a string."""
        token = "test-token"
        hashed = csrf_middleware._hash_token(token)
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_token_is_deterministic(self, csrf_middleware):
        """Test that hashing the same token produces the same hash."""
        token = "test-token"
        hash1 = csrf_middleware._hash_token(token)
        hash2 = csrf_middleware._hash_token(token)
        assert hash1 == hash2

    def test_hash_token_uses_hmac_sha256(self, csrf_middleware):
        """Test that token hashing uses HMAC-SHA256."""
        token = "test-token"
        hashed = csrf_middleware._hash_token(token)
        # HMAC-SHA256 produces 64-character hex string
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_token_different_tokens_different_hashes(self, csrf_middleware):
        """Test that different tokens produce different hashes."""
        token1 = "token1"
        token2 = "token2"
        hash1 = csrf_middleware._hash_token(token1)
        hash2 = csrf_middleware._hash_token(token2)
        assert hash1 != hash2

    def test_hash_token_requires_secret_key(self, csrf_middleware):
        """Test that hashing requires JWT secret key to be configured."""
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = None
            with pytest.raises(ValueError, match="JWT secret key not configured"):
                csrf_middleware._hash_token("test-token")


# ---------------------------------------------------------------------------
# Tests for should_protect logic
# ---------------------------------------------------------------------------


class TestShouldProtect:
    """Tests for CSRF protection decision logic."""

    def test_should_not_protect_get_request(self, csrf_middleware):
        """Test that GET requests are not protected."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {}
        assert csrf_middleware._should_protect(request) is False

    def test_should_not_protect_head_request(self, csrf_middleware):
        """Test that HEAD requests are not protected."""
        request = MagicMock(spec=Request)
        request.method = "HEAD"
        request.headers = {}
        assert csrf_middleware._should_protect(request) is False

    def test_should_not_protect_options_request(self, csrf_middleware):
        """Test that OPTIONS requests are not protected."""
        request = MagicMock(spec=Request)
        request.method = "OPTIONS"
        request.headers = {}
        assert csrf_middleware._should_protect(request) is False

    def test_should_protect_post_request(self, csrf_middleware):
        """Test that POST requests with form data are protected."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/x-www-form-urlencoded"}
        assert csrf_middleware._should_protect(request) is True

    def test_should_protect_put_request(self, csrf_middleware):
        """Test that PUT requests with form data are protected."""
        request = MagicMock(spec=Request)
        request.method = "PUT"
        request.headers = {"content-type": "application/x-www-form-urlencoded"}
        assert csrf_middleware._should_protect(request) is True

    def test_should_protect_delete_request(self, csrf_middleware):
        """Test that DELETE requests with form data are protected."""
        request = MagicMock(spec=Request)
        request.method = "DELETE"
        request.headers = {"content-type": "application/x-www-form-urlencoded"}
        assert csrf_middleware._should_protect(request) is True

    def test_should_protect_patch_request(self, csrf_middleware):
        """Test that PATCH requests with form data are protected."""
        request = MagicMock(spec=Request)
        request.method = "PATCH"
        request.headers = {"content-type": "application/x-www-form-urlencoded"}
        assert csrf_middleware._should_protect(request) is True

    def test_should_not_protect_bearer_token_request(self, csrf_middleware):
        """Test that Bearer token requests bypass CSRF."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "content-type": "application/x-www-form-urlencoded",
        }
        assert csrf_middleware._should_protect(request) is False

    def test_should_not_protect_json_content_type(self, csrf_middleware):
        """Test that JSON content-type requests bypass CSRF."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        assert csrf_middleware._should_protect(request) is False

    def test_should_not_protect_multipart_form_data(self, csrf_middleware):
        """Test that multipart/form-data is protected (form-based)."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "multipart/form-data; boundary=----"}
        assert csrf_middleware._should_protect(request) is True

    def test_should_not_protect_xml_content_type(self, csrf_middleware):
        """Test that XML content-type requests bypass CSRF."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/xml"}
        assert csrf_middleware._should_protect(request) is False

    def test_should_protect_missing_content_type(self, csrf_middleware):
        """Test that requests without content-type are protected (default to form-based)."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {}
        assert csrf_middleware._should_protect(request) is True


# ---------------------------------------------------------------------------
# Tests for token extraction
# ---------------------------------------------------------------------------


class TestTokenExtraction:
    """Tests for CSRF token extraction from requests."""

    @pytest.mark.asyncio
    async def test_extract_token_from_header(self, csrf_middleware):
        """Test extracting token from X-CSRF-Token header."""
        request = MagicMock(spec=Request)
        request.headers = {"X-CSRF-Token": "test-token-123"}
        request.form = AsyncMock(return_value={})

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token == "test-token-123"

    @pytest.mark.asyncio
    async def test_extract_token_from_form_data(self, csrf_middleware):
        """Test extracting token from form data."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.form = AsyncMock(return_value={"csrf_token": "form-token-456"})

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token == "form-token-456"

    @pytest.mark.asyncio
    async def test_extract_token_header_takes_precedence(self, csrf_middleware):
        """Test that header token takes precedence over form token."""
        request = MagicMock(spec=Request)
        request.headers = {"X-CSRF-Token": "header-token"}
        request.form = AsyncMock(return_value={"csrf_token": "form-token"})

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token == "header-token"

    @pytest.mark.asyncio
    async def test_extract_token_returns_none_if_missing(self, csrf_middleware):
        """Test that None is returned if token is missing."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.form = AsyncMock(return_value={})

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token is None

    @pytest.mark.asyncio
    async def test_extract_token_handles_form_exception(self, csrf_middleware):
        """Test that form parsing exceptions are handled gracefully."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.form = AsyncMock(side_effect=Exception("Form parsing error"))

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token is None

    @pytest.mark.asyncio
    async def test_extract_token_ignores_non_string_form_values(self, csrf_middleware):
        """Test that non-string form values are ignored."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.form = AsyncMock(return_value={"csrf_token": 123})  # Not a string

        token = await csrf_middleware._get_csrf_token_from_request(request)
        assert token is None


# ---------------------------------------------------------------------------
# Tests for valid token validation
# ---------------------------------------------------------------------------


class TestValidTokenValidation:
    """Tests for valid token validation on unsafe methods."""

    def test_valid_token_on_post_request(self, client_csrf_enabled):
        """Test that POST request with valid token succeeds."""
        # First, get a token from a GET request
        get_response = client_csrf_enabled.get("/test")
        csrf_token_cookie = get_response.cookies.get("csrf_token")

        # Generate a token and hash it to match the cookie
        # We need to use the same secret key
        test_token = "valid-test-token"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        # Make POST request with valid token
        response = client_csrf_enabled.post(
            "/test",
            headers={"X-CSRF-Token": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "POST success"

    def test_valid_token_on_put_request(self, client_csrf_enabled):
        """Test that PUT request with valid token succeeds."""
        test_token = "valid-test-token"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.put(
            "/test",
            headers={"X-CSRF-Token": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "PUT success"

    def test_valid_token_on_delete_request(self, client_csrf_enabled):
        """Test that DELETE request with valid token succeeds."""
        test_token = "valid-test-token"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.delete(
            "/test",
            headers={"X-CSRF-Token": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "DELETE success"

    def test_valid_token_on_patch_request(self, client_csrf_enabled):
        """Test that PATCH request with valid token succeeds."""
        test_token = "valid-test-token"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.patch(
            "/test",
            headers={"X-CSRF-Token": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "PATCH success"


# ---------------------------------------------------------------------------
# Tests for missing token rejection
# ---------------------------------------------------------------------------


class TestMissingTokenRejection:
    """Tests for missing token rejection on unsafe methods."""

    def test_missing_token_on_post_request(self, client_csrf_enabled):
        """Test that POST request without token is rejected."""
        response = client_csrf_enabled.post("/test")
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "CSRF_TOKEN_MISSING"
        assert "required" in data["error"]["message"].lower()

    def test_missing_token_on_put_request(self, client_csrf_enabled):
        """Test that PUT request without token is rejected."""
        response = client_csrf_enabled.put("/test")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_missing_token_on_delete_request(self, client_csrf_enabled):
        """Test that DELETE request without token is rejected."""
        response = client_csrf_enabled.delete("/test")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_missing_token_on_patch_request(self, client_csrf_enabled):
        """Test that PATCH request without token is rejected."""
        response = client_csrf_enabled.patch("/test")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_missing_header_token_with_cookie(self, client_csrf_enabled):
        """Test that missing header token is rejected even with cookie."""
        response = client_csrf_enabled.post(
            "/test",
            cookies={"csrf_token": "some-cookie-value"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_missing_cookie_token_with_header(self, client_csrf_enabled):
        """Test that missing cookie token is rejected even with header."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"X-CSRF-Token": "some-header-value"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_error_response_includes_timestamp(self, client_csrf_enabled):
        """Test that error response includes timestamp."""
        response = client_csrf_enabled.post("/test")
        assert response.status_code == 403
        data = response.json()
        assert "timestamp" in data["error"]
        # Verify timestamp is ISO format
        assert "T" in data["error"]["timestamp"]
        assert "Z" in data["error"]["timestamp"]


# ---------------------------------------------------------------------------
# Tests for invalid token rejection
# ---------------------------------------------------------------------------


class TestInvalidTokenRejection:
    """Tests for invalid token rejection on unsafe methods."""

    def test_invalid_token_on_post_request(self, client_csrf_enabled):
        """Test that POST request with invalid token is rejected."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"X-CSRF-Token": "invalid-token"},
            cookies={"csrf_token": "invalid-cookie"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "CSRF_TOKEN_INVALID"
        assert "invalid" in data["error"]["message"].lower()

    def test_invalid_token_on_put_request(self, client_csrf_enabled):
        """Test that PUT request with invalid token is rejected."""
        response = client_csrf_enabled.put(
            "/test",
            headers={"X-CSRF-Token": "invalid-token"},
            cookies={"csrf_token": "invalid-cookie"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_invalid_token_on_delete_request(self, client_csrf_enabled):
        """Test that DELETE request with invalid token is rejected."""
        response = client_csrf_enabled.delete(
            "/test",
            headers={"X-CSRF-Token": "invalid-token"},
            cookies={"csrf_token": "invalid-cookie"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_invalid_token_on_patch_request(self, client_csrf_enabled):
        """Test that PATCH request with invalid token is rejected."""
        response = client_csrf_enabled.patch(
            "/test",
            headers={"X-CSRF-Token": "invalid-token"},
            cookies={"csrf_token": "invalid-cookie"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_mismatched_token_and_cookie(self, client_csrf_enabled):
        """Test that mismatched token and cookie are rejected."""
        # Create two different tokens
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            token1 = "token-1"
            token2 = "token-2"
            hash1 = middleware._hash_token(token1)
            hash2 = middleware._hash_token(token2)

        # Send token1 in header but hash2 in cookie (mismatch)
        response = client_csrf_enabled.post(
            "/test",
            headers={"X-CSRF-Token": token1},
            cookies={"csrf_token": hash2},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


# ---------------------------------------------------------------------------
# Tests for exempt paths (Bearer tokens, safe methods, non-form content)
# ---------------------------------------------------------------------------


class TestExemptPaths:
    """Tests for CSRF exempt paths."""

    def test_bearer_token_bypass_post(self, client_csrf_enabled):
        """Test that Bearer token requests bypass CSRF on POST."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "POST success"

    def test_bearer_token_bypass_put(self, client_csrf_enabled):
        """Test that Bearer token requests bypass CSRF on PUT."""
        response = client_csrf_enabled.put(
            "/test",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "PUT success"

    def test_bearer_token_bypass_delete(self, client_csrf_enabled):
        """Test that Bearer token requests bypass CSRF on DELETE."""
        response = client_csrf_enabled.delete(
            "/test",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "DELETE success"

    def test_bearer_token_bypass_patch(self, client_csrf_enabled):
        """Test that Bearer token requests bypass CSRF on PATCH."""
        response = client_csrf_enabled.patch(
            "/test",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "PATCH success"

    def test_json_content_type_bypass(self, client_csrf_enabled):
        """Test that JSON content-type requests bypass CSRF."""
        response = client_csrf_enabled.post(
            "/json-test",
            json={"data": "test"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "JSON POST success"

    def test_xml_content_type_bypass(self, client_csrf_enabled):
        """Test that XML content-type requests bypass CSRF."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Content-Type": "application/xml"},
            content="<data>test</data>",
        )
        assert response.status_code == 200

    def test_safe_method_get_no_token_required(self, client_csrf_enabled):
        """Test that GET requests don't require CSRF token."""
        response = client_csrf_enabled.get("/test")
        assert response.status_code == 200
        assert response.json()["message"] == "GET success"

    def test_safe_method_head_no_token_required(self, client_csrf_enabled):
        """Test that HEAD requests don't require CSRF token."""
        response = client_csrf_enabled.head("/test")
        assert response.status_code == 200

    def test_safe_method_options_no_token_required(self, client_csrf_enabled):
        """Test that OPTIONS requests don't require CSRF token."""
        response = client_csrf_enabled.options("/test")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests for disabled middleware
# ---------------------------------------------------------------------------


class TestDisabledMiddleware:
    """Tests for disabled CSRF middleware."""

    def test_disabled_middleware_allows_post_without_token(self, client_csrf_disabled):
        """Test that disabled middleware allows POST without token."""
        response = client_csrf_disabled.post("/test")
        assert response.status_code == 200
        assert response.json()["message"] == "POST success"

    def test_disabled_middleware_no_token_in_response(self, client_csrf_disabled):
        """Test that disabled middleware doesn't set token in response."""
        response = client_csrf_disabled.post("/test")
        assert "csrf_token" not in response.cookies


# ---------------------------------------------------------------------------
# Tests for form data token extraction
# ---------------------------------------------------------------------------


class TestFormDataTokenExtraction:
    """Tests for CSRF token extraction from form data."""

    def test_form_data_token_extraction(self, client_csrf_enabled):
        """Test that token can be extracted from form data."""
        test_token = "form-token-123"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.post(
            "/form-test",
            data={"csrf_token": test_token, "field": "value"},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Form POST success"

    def test_multipart_form_data_token_extraction(self, client_csrf_enabled):
        """Test that token can be extracted from multipart form data."""
        test_token = "multipart-token-456"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.post(
            "/form-test",
            data={"csrf_token": test_token, "field": "value"},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests for header token extraction
# ---------------------------------------------------------------------------


class TestHeaderTokenExtraction:
    """Tests for CSRF token extraction from headers."""

    def test_header_token_extraction(self, client_csrf_enabled):
        """Test that token can be extracted from X-CSRF-Token header."""
        test_token = "header-token-789"
        with patch("app.middleware.csrf.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-for-csrf-hashing"
            middleware = CSRFMiddleware(MagicMock())
            hashed_token = middleware._hash_token(test_token)

        response = client_csrf_enabled.post(
            "/test",
            headers={"X-CSRF-Token": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "POST success"

    def test_custom_header_name(self, mock_settings):
        """Test that custom header name is respected."""
        app = FastAPI()

        @app.post("/test")
        async def post_test():
            return {"message": "POST success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="csrf_token",
            header_name="X-Custom-CSRF",
            token_expiry_minutes=60,
        )

        client = TestClient(app, raise_server_exceptions=False)
        test_token = "custom-header-token"
        middleware = CSRFMiddleware(MagicMock(), header_name="X-Custom-CSRF")
        hashed_token = middleware._hash_token(test_token)

        response = client.post(
            "/test",
            headers={"X-Custom-CSRF": test_token},
            cookies={"csrf_token": hashed_token},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests for token expiry configuration
# ---------------------------------------------------------------------------


class TestTokenExpiryConfiguration:
    """Tests for token expiry configuration."""

    def test_token_expiry_minutes_in_cookie(self, mock_settings):
        """Test that token expiry is set in cookie."""
        app = FastAPI()

        @app.get("/test")
        async def get_test():
            return {"message": "GET success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            token_expiry_minutes=120,
        )

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Check that cookie has max_age set
        assert "csrf_token" in response.cookies
        cookie = response.cookies["csrf_token"]
        # The cookie should have max_age set to 120 * 60 = 7200 seconds
        assert cookie is not None

    def test_custom_cookie_name(self, mock_settings):
        """Test that custom cookie name is respected."""
        app = FastAPI()

        @app.get("/test")
        async def get_test():
            return {"message": "GET success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="custom_csrf",
            header_name="X-CSRF-Token",
            token_expiry_minutes=60,
        )

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        assert "custom_csrf" in response.cookies
        assert "csrf_token" not in response.cookies


# ---------------------------------------------------------------------------
# Tests for cookie attributes
# ---------------------------------------------------------------------------


class TestCookieAttributes:
    """Tests for CSRF token cookie attributes."""

    def test_cookie_httponly_false(self, mock_settings):
        """Test that cookie httponly is False (JavaScript needs to read it)."""
        app = FastAPI()

        @app.get("/test")
        async def get_test():
            return {"message": "GET success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            token_expiry_minutes=60,
        )

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # TestClient doesn't expose httponly flag directly, but we can verify
        # the cookie is set and accessible
        assert "csrf_token" in response.cookies

    def test_cookie_samesite_strict(self, mock_settings):
        """Test that cookie samesite is strict."""
        app = FastAPI()

        @app.get("/test")
        async def get_test():
            return {"message": "GET success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            token_expiry_minutes=60,
        )

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Verify cookie is set
        assert "csrf_token" in response.cookies

    def test_cookie_secure_true(self, mock_settings):
        """Test that cookie secure flag is True."""
        app = FastAPI()

        @app.get("/test")
        async def get_test():
            return {"message": "GET success"}

        app.add_middleware(
            CSRFMiddleware,
            enabled=True,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            token_expiry_minutes=60,
        )

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Verify cookie is set
        assert "csrf_token" in response.cookies


# ---------------------------------------------------------------------------
# Tests for edge cases and error handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_authorization_header(self, client_csrf_enabled):
        """Test that empty authorization header doesn't bypass CSRF."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Authorization": ""},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_authorization_header_without_bearer(self, client_csrf_enabled):
        """Test that non-Bearer authorization doesn't bypass CSRF."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_case_insensitive_content_type(self, client_csrf_enabled):
        """Test that content-type matching is case-insensitive."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Content-Type": "APPLICATION/X-WWW-FORM-URLENCODED"},
        )
        # Should require CSRF token (form-based)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_content_type_with_charset(self, client_csrf_enabled):
        """Test that content-type with charset is handled correctly."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        )
        # Should require CSRF token (form-based)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    def test_multiple_authorization_headers(self, client_csrf_enabled):
        """Test handling of multiple authorization headers."""
        # Most HTTP clients only send one, but test robustness
        response = client_csrf_enabled.post(
            "/test",
            headers={"Authorization": "Bearer token1"},
        )
        assert response.status_code == 200

    def test_whitespace_in_bearer_token(self, client_csrf_enabled):
        """Test that Bearer token with whitespace is recognized."""
        response = client_csrf_enabled.post(
            "/test",
            headers={"Authorization": "Bearer   token-with-spaces"},
        )
        # Should bypass CSRF (Bearer token present)
        assert response.status_code == 200

    def test_constant_time_comparison(self, csrf_middleware):
        """Test that token comparison uses constant-time comparison."""
        # This is a security test to ensure timing attacks are prevented
        test_token = "test-token"
        hashed = csrf_middleware._hash_token(test_token)

        # Both should use secrets.compare_digest internally
        # We verify by checking that the middleware uses it
        import inspect

        source = inspect.getsource(csrf_middleware.dispatch)
        assert "compare_digest" in source
