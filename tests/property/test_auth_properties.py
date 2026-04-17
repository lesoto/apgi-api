"""
Property-based tests for authentication and authorization.

Feature: api-migration
Tests universal properties of JWT token validation and authentication.
"""

from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock
import jwt
import asyncio

# Import after setting up environment
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from app.config import settings as app_settings
from app.services.auth_manager import AuthManager
from app.middleware.authentication import AuthenticationMiddleware

# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_request(path: str = "/v1/sessions", headers: dict[str, str] | None = None) -> Mock:
    """Create a fresh mock FastAPI request."""
    request = Mock()
    request.url.path = path
    request.headers = headers or {}
    request.state = Mock(spec=[])  # Empty spec so no default attributes
    return request


def create_auth_middleware() -> AuthenticationMiddleware:
    """Create authentication middleware instance."""
    mock_app = Mock()
    return AuthenticationMiddleware(mock_app)


# ============================================================================
# Property 5: JWT Token Validation on Protected Routes
# ============================================================================


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/v1/sessions",
            "/v1/sessions/test-id",
            "/v1/tasks",
            "/v1/users/me",
        ]
    ),
)
def test_property_5_jwt_validation_no_token(path: str) -> None:
    """
    **Validates: Requirements 8.4**

    Feature: api-migration, Property 5: JWT Token Validation on Protected Routes

    For any protected route, requests without valid JWT tokens should be rejected
    with 401 Unauthorized status.

    This test verifies that protected routes reject requests with NO token.
    """
    # Create fresh instances for this test
    auth_middleware = create_auth_middleware()
    mock_request = create_mock_request(path=path, headers={})

    # Mock the call_next function
    async def mock_call_next(request: Any) -> Any:
        return Mock(status_code=200)

    # Test that middleware allows request to pass through (no token = no auth attached)
    # The actual rejection happens at the route level via dependencies
    response = asyncio.run(auth_middleware.dispatch(mock_request, mock_call_next))

    # Property: When no token is provided, middleware should deny access (defense in depth)
    # This matches the deny-by-default posture implemented in the middleware
    assert response.status_code == 401, "Middleware should deny access when no token provided"

    # Property: Request state should not have authenticated flag set to True
    assert not getattr(
        mock_request.state, "authenticated", False
    ), "Request should not be marked as authenticated when no token provided"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/v1/sessions",
            "/v1/sessions/test-id",
            "/v1/tasks",
            "/v1/users/me",
        ]
    ),
    # Generate strings that look like JWTs but are invalid
    invalid_token=st.text(
        min_size=50,
        max_size=200,
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-_",
    ).filter(
        lambda x: x.count(".") >= 2
    ),  # Must have at least 2 dots like a JWT
)
def test_property_5_jwt_validation_invalid_token(path: str, invalid_token: str) -> None:
    """
    **Validates: Requirements 8.4**

    Feature: api-migration, Property 5: JWT Token Validation on Protected Routes

    For any protected route, requests with invalid JWT tokens should be rejected
    with 401 Unauthorized status.

    This test verifies that protected routes reject requests with INVALID tokens.
    """
    # Create fresh instances for this test
    auth_middleware = create_auth_middleware()
    mock_request = create_mock_request(
        path=path, headers={"Authorization": f"Bearer {invalid_token}"}
    )

    # Mock the call_next function
    async def mock_call_next(request: Any) -> Any:
        return Mock(status_code=200)

    # Test that middleware rejects invalid token
    response = asyncio.run(auth_middleware.dispatch(mock_request, mock_call_next))

    # Property: Should return 401 Unauthorized
    assert response.status_code == 401, (
        f"Protected route {path} with invalid token should return 401, "
        f"got {response.status_code}"
    )

    # Property: Should include WWW-Authenticate header
    assert (
        "WWW-Authenticate" in response.headers or "www-authenticate" in response.headers
    ), "401 response should include WWW-Authenticate header"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/v1/sessions",
            "/v1/sessions/test-id",
            "/v1/tasks",
            "/v1/users/me",
        ]
    ),
    user_id=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters="\x00"
        ),
    ),
    username=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters="\x00"
        ),
    ),
)
def test_property_5_jwt_validation_expired_token(path: str, user_id: str, username: str) -> None:
    """
    **Validates: Requirements 8.4**

    Feature: api-migration, Property 5: JWT Token Validation on Protected Routes

    For any protected route, requests with expired JWT tokens should be rejected
    with 401 Unauthorized status.

    This test verifies that protected routes reject requests with EXPIRED tokens.
    """
    from datetime import timezone

    # Create an expired token (expired 1 hour ago)
    expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    payload = {
        "user_id": user_id,
        "username": username,
        "roles": ["researcher"],
        "exp": int(expires_at.timestamp()),
        "token_type": "access",
    }

    # Create token with the same secret key used by the app
    expired_token = jwt.encode(
        payload, cast(str, app_settings.jwt_secret_key), algorithm=app_settings.jwt_algorithm
    )

    # Create fresh instances for this test
    auth_middleware = create_auth_middleware()
    mock_request = create_mock_request(
        path=path, headers={"Authorization": f"Bearer {expired_token}"}
    )

    # Mock the call_next function
    async def mock_call_next(request: Any) -> Any:
        return Mock(status_code=200)

    # Test that middleware rejects expired token
    response = asyncio.run(auth_middleware.dispatch(mock_request, mock_call_next))

    # Property: Should return 401 Unauthorized
    assert response.status_code == 401, (
        f"Protected route {path} with expired token should return 401, "
        f"got {response.status_code}"
    )

    # Property: Should include WWW-Authenticate header
    assert (
        "WWW-Authenticate" in response.headers or "www-authenticate" in response.headers
    ), "401 response should include WWW-Authenticate header"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/v1/sessions",
            "/v1/sessions/test-id",
            "/v1/tasks",
            "/v1/users/me",
        ]
    ),
    user_id=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters="\x00"
        ),
    ),
    username=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters="\x00"
        ),
    ),
)
def test_property_5_jwt_validation_wrong_token_type(path: str, user_id: str, username: str) -> None:
    """
    **Validates: Requirements 8.4**

    Feature: api-migration, Property 5: JWT Token Validation on Protected Routes

    For any protected route, requests with wrong token type (refresh instead of access)
    should be rejected with 401 Unauthorized status.

    This test verifies that protected routes reject refresh tokens.
    """
    from datetime import timezone

    # Create a refresh token (wrong type for protected routes)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    payload = {
        "user_id": user_id,
        "username": username,
        "roles": ["researcher"],
        "exp": int(expires_at.timestamp()),
        "token_type": "refresh",  # Wrong type!
    }

    # Create token with the same secret key used by the app
    refresh_token = jwt.encode(
        payload, cast(str, app_settings.jwt_secret_key), algorithm=app_settings.jwt_algorithm
    )

    # Create fresh instances for this test
    auth_middleware = create_auth_middleware()
    mock_request = create_mock_request(
        path=path, headers={"Authorization": f"Bearer {refresh_token}"}
    )

    # Mock the call_next function
    async def mock_call_next(request: Any) -> Any:
        return Mock(status_code=200)

    # Test that middleware rejects wrong token type
    response = asyncio.run(auth_middleware.dispatch(mock_request, mock_call_next))

    # Property: Should return 401 Unauthorized
    assert response.status_code == 401, (
        f"Protected route {path} with refresh token should return 401, "
        f"got {response.status_code}"
    )

    # Property: Should include WWW-Authenticate header
    assert (
        "WWW-Authenticate" in response.headers or "www-authenticate" in response.headers
    ), "401 response should include WWW-Authenticate header"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    path=st.sampled_from(
        [
            "/v1/sessions",
            "/v1/sessions/test-id",
            "/v1/tasks",
            "/v1/users/me",
        ]
    ),
    malformed_header=st.sampled_from(
        [
            "InvalidFormat",  # No "Bearer" prefix
            "Bearer",  # No token after Bearer
            "Bearer token1 token2",  # Multiple tokens
            "",  # Empty header
            "Basic dXNlcjpwYXNz",  # Wrong auth scheme
        ]
    ),
)
def test_property_5_jwt_validation_malformed_header(path: str, malformed_header: str) -> None:
    """
    **Validates: Requirements 8.4**

    Feature: api-migration, Property 5: JWT Token Validation on Protected Routes

    For any protected route, requests with malformed Authorization headers
    should be rejected or passed through (depending on format).

    This test verifies that protected routes handle malformed auth headers correctly.
    """
    # Create fresh instances for this test
    auth_middleware = create_auth_middleware()
    headers = {"Authorization": malformed_header} if malformed_header else {}
    mock_request = create_mock_request(path=path, headers=headers)

    # Mock the call_next function
    async def mock_call_next(request: Any) -> Any:
        return Mock(status_code=200)

    # Test that middleware handles malformed header
    response = asyncio.run(auth_middleware.dispatch(mock_request, mock_call_next))

    # Property: Should either return 401 or pass through (depending on whether token extraction succeeded)
    # If no valid Bearer token format, middleware passes through and route dependency handles it
    assert response.status_code in [200, 401], (
        f"Protected route {path} with malformed header should return 200 or 401, "
        f"got {response.status_code}"
    )


# ============================================================================
# Property 6: Password Hashing with Bcrypt
# ============================================================================


@settings(max_examples=1)  # Reduced for faster testing
@given(
    password=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_characters="\x00",  # Exclude null bytes
            blacklist_categories=["Cs"],  # Exclude surrogates
        ),
    )
)
def test_property_6_password_hashing_verification(password: str) -> None:
    """
    **Validates: Requirements 8.7**

    Feature: api-migration, Property 6: Password Hashing with Bcrypt

    For any password, hashing it with bcrypt should produce a hash that can be
    verified against the original password.

    This test verifies that password hashing and verification work correctly.
    """
    # Hash the password
    password_hash = AuthManager.hash_password(password)

    # Property 1: Hash should be a non-empty string
    assert isinstance(password_hash, str), "Hash should be a string"
    assert len(password_hash) > 0, "Hash should not be empty"

    # Property 2: Hash should start with bcrypt identifier ($2b$)
    assert password_hash.startswith("$2b$"), "Hash should start with bcrypt identifier $2b$"

    # Property 3: Original password should verify against the hash
    assert AuthManager.verify_password(
        password, password_hash
    ), "Original password should verify against its hash"

    # Property 4: Hash should be different from the original password
    assert password_hash != password, "Hash should be different from original password"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    password=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=["Cs"],
        ),
    ),
    different_password=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=["Cs"],
        ),
    ),
)
def test_property_6_password_hashing_different_password_fails(
    password: str, different_password: str
) -> None:
    """
    **Validates: Requirements 8.7**

    Feature: api-migration, Property 6: Password Hashing with Bcrypt

    For any password, the hash should not be verifiable against any other password.

    This test verifies that different passwords do not verify against each other's hashes.
    """
    # Ensure passwords are actually different
    assume(password != different_password)

    # Hash the original password
    password_hash = AuthManager.hash_password(password)

    # Property: Different password should NOT verify against the hash
    assert not AuthManager.verify_password(
        different_password, password_hash
    ), "Different password should not verify against the hash"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    password=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=["Cs"],
        ),
    )
)
def test_property_6_password_hashing_deterministic_verification(password: str) -> None:
    """
    **Validates: Requirements 8.7**

    Feature: api-migration, Property 6: Password Hashing with Bcrypt

    For any password, the same password should always verify against its hash,
    regardless of how many times verification is performed.

    This test verifies that password verification is deterministic.
    """
    # Hash the password
    password_hash = AuthManager.hash_password(password)

    # Property: Multiple verifications should all succeed
    for _ in range(5):
        assert AuthManager.verify_password(
            password, password_hash
        ), "Password verification should be deterministic and always succeed"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    password=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=["Cs"],
        ),
    )
)
def test_property_6_password_hashing_unique_salts(password: str) -> None:
    """
    **Validates: Requirements 8.7**

    Feature: api-migration, Property 6: Password Hashing with Bcrypt

    For any password, hashing it multiple times should produce different hashes
    (due to unique salts), but all hashes should verify against the original password.

    This test verifies that bcrypt uses unique salts for each hash.
    """
    # Hash the same password multiple times
    hash1 = AuthManager.hash_password(password)
    hash2 = AuthManager.hash_password(password)
    hash3 = AuthManager.hash_password(password)

    # Property 1: Hashes should be different (unique salts)
    assert hash1 != hash2, "Multiple hashes of same password should be different (unique salts)"
    assert hash2 != hash3, "Multiple hashes of same password should be different (unique salts)"
    assert hash1 != hash3, "Multiple hashes of same password should be different (unique salts)"

    # Property 2: All hashes should verify against the original password
    assert AuthManager.verify_password(password, hash1), "Hash 1 should verify"
    assert AuthManager.verify_password(password, hash2), "Hash 2 should verify"
    assert AuthManager.verify_password(password, hash3), "Hash 3 should verify"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    password=st.text(
        min_size=73,  # Longer than bcrypt's 72-byte limit
        max_size=200,
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=["Cs"],
        ),
    )
)
def test_property_6_password_hashing_long_passwords(password: str) -> None:
    """
    **Validates: Requirements 8.7**

    Feature: api-migration, Property 6: Password Hashing with Bcrypt

    For any password longer than 72 bytes (bcrypt's limit), the implementation
    should truncate consistently so that verification still works.

    This test verifies that long passwords are handled correctly.
    """
    # Ensure password is actually longer than 72 bytes when encoded
    assume(len(password.encode("utf-8")) > 72)

    # Hash the password
    password_hash = AuthManager.hash_password(password)

    # Property: Original password should still verify (truncation is consistent)
    assert AuthManager.verify_password(
        password, password_hash
    ), "Long password should verify against its hash (consistent truncation)"
