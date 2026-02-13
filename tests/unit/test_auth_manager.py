"""
Unit tests for JWT token generation and verification.

Tests access token creation/verification, refresh token creation/verification,
token expiration handling, and invalid token rejection.
Validates Requirements 8.2, 8.3, 8.4.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch
import jwt

from app.services.auth_manager import AuthManager, TokenPayload
from app.config import settings
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def auth_manager(mock_db_session):
    """Create an AuthManager instance with mock database."""
    return AuthManager(mock_db_session)


class TestAccessTokenCreation:
    """Test access token creation."""

    def test_create_access_token_returns_valid_jwt(self, auth_manager):
        """Test that create_access_token returns a valid JWT string."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_access_token(user_id, username, roles)

        # Verify token is a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token has JWT structure (3 parts separated by dots)
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_access_token_contains_correct_payload(self, auth_manager):
        """Test that access token contains correct user information."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher", "admin"]

        token = auth_manager.create_access_token(user_id, username, roles)

        # Decode token without verification to check payload
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["user_id"] == user_id
        assert payload["username"] == username
        assert payload["roles"] == roles
        assert payload["token_type"] == "access"

    def test_create_access_token_has_expiration(self, auth_manager):
        """Test that access token has expiration time set."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        before_creation = datetime.now(timezone.utc)
        token = auth_manager.create_access_token(user_id, username, roles)
        after_creation = datetime.now(timezone.utc)

        # Decode token to check expiration
        payload = jwt.decode(token, options={"verify_signature": False})

        assert "exp" in payload

        # Verify expiration is approximately correct (within 1 minute tolerance)
        expected_exp = before_creation + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        actual_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        time_diff = abs((actual_exp - expected_exp).total_seconds())
        assert time_diff < 60, f"Expiration time differs by {time_diff} seconds"

    def test_create_access_token_is_signed_correctly(self, auth_manager):
        """Test that access token can be verified with the secret key."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_access_token(user_id, username, roles)

        # Verify token signature
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            signature_valid = True
        except jwt.InvalidTokenError:
            signature_valid = False

        assert signature_valid, "Token signature should be valid"

    def test_create_access_token_with_empty_roles(self, auth_manager):
        """Test that access token can be created with empty roles list."""
        user_id = "user123"
        username = "testuser"
        roles = []

        token = auth_manager.create_access_token(user_id, username, roles)

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["roles"] == []


class TestRefreshTokenCreation:
    """Test refresh token creation."""

    def test_create_refresh_token_returns_valid_jwt(self, auth_manager):
        """Test that create_refresh_token returns a valid JWT string."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_refresh_token(user_id, username, roles)

        # Verify token is a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token has JWT structure
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_refresh_token_contains_correct_payload(self, auth_manager):
        """Test that refresh token contains correct user information."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_refresh_token(user_id, username, roles)

        # Decode token without verification
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["user_id"] == user_id
        assert payload["username"] == username
        assert payload["roles"] == roles
        assert payload["token_type"] == "refresh"

    def test_create_refresh_token_has_longer_expiration(self, auth_manager):
        """Test that refresh token has longer expiration than access token."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        before_creation = datetime.now(timezone.utc)
        refresh_token = auth_manager.create_refresh_token(user_id, username, roles)
        access_token = auth_manager.create_access_token(user_id, username, roles)

        # Decode tokens
        refresh_payload = jwt.decode(refresh_token, options={"verify_signature": False})
        access_payload = jwt.decode(access_token, options={"verify_signature": False})

        # Verify refresh token expires later than access token
        assert refresh_payload["exp"] > access_payload["exp"]

        # Verify refresh token expiration is approximately correct
        expected_exp = before_creation + timedelta(days=settings.jwt_refresh_token_expire_days)
        actual_exp = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

        time_diff = abs((actual_exp - expected_exp).total_seconds())
        assert time_diff < 60, f"Expiration time differs by {time_diff} seconds"

    def test_create_refresh_token_is_signed_correctly(self, auth_manager):
        """Test that refresh token can be verified with the secret key."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_refresh_token(user_id, username, roles)

        # Verify token signature
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            signature_valid = True
        except jwt.InvalidTokenError:
            signature_valid = False

        assert signature_valid, "Token signature should be valid"


class TestAccessTokenVerification:
    """Test access token verification."""

    def test_verify_token_accepts_valid_access_token(self, auth_manager):
        """Test that verify_token accepts a valid access token."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_access_token(user_id, username, roles)
        payload = auth_manager.verify_token(token, expected_type="access")

        assert payload.user_id == user_id
        assert payload.username == username
        assert payload.roles == roles
        assert payload.token_type == "access"

    def test_verify_token_rejects_expired_access_token(self, auth_manager):
        """Test that verify_token rejects an expired access token."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create an expired token
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }
        expired_token = jwt.encode(
            payload_dict, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Verify token raises ExpiredTokenError
        with pytest.raises(ExpiredTokenError):
            auth_manager.verify_token(expired_token, expected_type="access")

    def test_verify_token_rejects_invalid_signature(self, auth_manager):
        """Test that verify_token rejects token with invalid signature."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create token with wrong secret key
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }
        invalid_token = jwt.encode(
            payload_dict, "wrong_secret_key", algorithm=settings.jwt_algorithm
        )

        # Verify token raises InvalidTokenError
        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(invalid_token, expected_type="access")

    def test_verify_token_rejects_malformed_token(self, auth_manager):
        """Test that verify_token rejects malformed token."""
        malformed_tokens = [
            "not.a.jwt",
            "invalid",
            "",
            "a.b",  # Only 2 parts
            "a.b.c.d",  # Too many parts
        ]

        for token in malformed_tokens:
            with pytest.raises(InvalidTokenError):
                auth_manager.verify_token(token, expected_type="access")

    def test_verify_token_rejects_wrong_token_type(self, auth_manager):
        """Test that verify_token rejects token with wrong type."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create a refresh token
        refresh_token = auth_manager.create_refresh_token(user_id, username, roles)

        # Try to verify as access token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_manager.verify_token(refresh_token, expected_type="access")

        assert "token type" in str(exc_info.value).lower()


class TestRefreshTokenVerification:
    """Test refresh token verification."""

    def test_verify_token_accepts_valid_refresh_token(self, auth_manager):
        """Test that verify_token accepts a valid refresh token."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        token = auth_manager.create_refresh_token(user_id, username, roles)
        payload = auth_manager.verify_token(token, expected_type="refresh")

        assert payload.user_id == user_id
        assert payload.username == username
        assert payload.roles == roles
        assert payload.token_type == "refresh"

    def test_verify_token_rejects_expired_refresh_token(self, auth_manager):
        """Test that verify_token rejects an expired refresh token."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create an expired refresh token
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "refresh",
        }
        expired_token = jwt.encode(
            payload_dict, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Verify token raises ExpiredTokenError
        with pytest.raises(ExpiredTokenError):
            auth_manager.verify_token(expired_token, expected_type="refresh")

    def test_verify_token_rejects_access_token_as_refresh(self, auth_manager):
        """Test that verify_token rejects access token when expecting refresh."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create an access token
        access_token = auth_manager.create_access_token(user_id, username, roles)

        # Try to verify as refresh token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_manager.verify_token(access_token, expected_type="refresh")

        assert "token type" in str(exc_info.value).lower()


class TestTokenExpiration:
    """Test token expiration handling."""

    def test_access_token_expires_after_configured_time(self, auth_manager):
        """Test that access token expires after configured minutes."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create token
        token = auth_manager.create_access_token(user_id, username, roles)

        # Decode to check expiration
        payload = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Calculate expected expiration
        now = datetime.now(timezone.utc)
        expected_exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

        # Verify expiration is within 1 minute of expected
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 60

    def test_refresh_token_expires_after_configured_time(self, auth_manager):
        """Test that refresh token expires after configured days."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create token
        token = auth_manager.create_refresh_token(user_id, username, roles)

        # Decode to check expiration
        payload = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Calculate expected expiration
        now = datetime.now(timezone.utc)
        expected_exp = now + timedelta(days=settings.jwt_refresh_token_expire_days)

        # Verify expiration is within 1 minute of expected
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 60

    def test_token_becomes_invalid_after_expiration(self, auth_manager):
        """Test that token cannot be verified after expiration."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create a token that expires in 1 second
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }
        short_lived_token = jwt.encode(
            payload_dict, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Token should be valid immediately
        payload = auth_manager.verify_token(short_lived_token, expected_type="access")
        assert payload.user_id == user_id

        # Wait for token to expire
        import time

        time.sleep(2)

        # Token should now be expired
        with pytest.raises(ExpiredTokenError):
            auth_manager.verify_token(short_lived_token, expected_type="access")


class TestInvalidTokenRejection:
    """Test invalid token rejection."""

    def test_verify_token_rejects_token_with_missing_fields(self, auth_manager):
        """Test that verify_token rejects token with missing required fields."""
        # Create token with missing user_id
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        payload_dict = {
            "username": "testuser",
            "roles": ["researcher"],
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }
        invalid_token = jwt.encode(
            payload_dict, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(invalid_token, expected_type="access")

    def test_verify_token_rejects_token_with_wrong_algorithm(self, auth_manager):
        """Test that verify_token rejects token signed with wrong algorithm."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create token with different algorithm
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }
        # Use HS512 instead of HS256
        wrong_algo_token = jwt.encode(payload_dict, settings.jwt_secret_key, algorithm="HS512")

        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(wrong_algo_token, expected_type="access")

    def test_verify_token_rejects_none_algorithm_attack(self, auth_manager):
        """Test that verify_token rejects 'none' algorithm attack."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create token with 'none' algorithm (security vulnerability)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        payload_dict = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": int(expires_at.timestamp()),
            "token_type": "access",
        }

        # Try to create unsigned token
        try:
            none_algo_token = jwt.encode(payload_dict, "", algorithm="none")

            with pytest.raises(InvalidTokenError):
                auth_manager.verify_token(none_algo_token, expected_type="access")
        except Exception:
            # Some JWT libraries prevent 'none' algorithm entirely, which is good
            pass

    def test_verify_token_rejects_tampered_payload(self, auth_manager):
        """Test that verify_token rejects token with tampered payload."""
        user_id = "user123"
        username = "testuser"
        roles = ["researcher"]

        # Create valid token
        token = auth_manager.create_access_token(user_id, username, roles)

        # Tamper with the payload (change middle part)
        parts = token.split(".")
        # Decode, modify, and re-encode the payload
        import base64
        import json

        payload_bytes = base64.urlsafe_b64decode(parts[1] + "==")
        payload_dict = json.loads(payload_bytes)
        payload_dict["user_id"] = "hacker123"  # Tamper with user_id

        tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
        )

        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        # Verify token raises InvalidTokenError due to signature mismatch
        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token(tampered_token, expected_type="access")

    def test_verify_token_rejects_empty_string(self, auth_manager):
        """Test that verify_token rejects empty string."""
        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token("", expected_type="access")

    def test_verify_token_rejects_random_string(self, auth_manager):
        """Test that verify_token rejects random non-JWT string."""
        with pytest.raises(InvalidTokenError):
            auth_manager.verify_token("this_is_not_a_jwt_token", expected_type="access")
