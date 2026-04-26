"""
Unit tests for AuthManager service.

Covers: hash_password, verify_password, create_access_token, verify_token,
refresh_access_token, revoke_refresh_token, revoke_access_token, revoke_all_user_tokens.

Uses MagicMock for DB session and AsyncMock for Redis client.
"""

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from app.config import settings
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError
from app.services.auth_manager import AuthManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> MagicMock:
    """MagicMock database session."""
    return MagicMock()


@pytest.fixture
def redis() -> AsyncMock:
    """AsyncMock Redis client."""
    r = AsyncMock()
    r.exists = AsyncMock(return_value=False)
    r.setex = AsyncMock(return_value=True)
    return r


@pytest.fixture
def auth_manager(db: MagicMock) -> AuthManager:
    """AuthManager with MagicMock DB, no Redis."""
    from app.services.auth_manager import AuthManager

    return AuthManager(db)


@pytest.fixture
def auth_manager_with_redis(db: MagicMock, redis: AsyncMock) -> AuthManager:
    """AuthManager with MagicMock DB and AsyncMock Redis."""
    from app.services.auth_manager import AuthManager

    return AuthManager(db, redis_client=redis)


def _make_refresh_token_row(token_str: str, user_id: str, expired: bool = False) -> MagicMock:
    """Build a MagicMock RefreshToken DB row."""
    from app.services.auth_manager import AuthManager

    row = MagicMock()
    row.user_id = user_id
    row.token_hash = AuthManager.hash_password(token_str)
    import hashlib

    row.token_sha256 = hashlib.sha256(token_str.encode()).hexdigest()
    row.revoked = False
    if expired:
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        row.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    return row


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_returns_bcrypt_string(self, auth_manager: AuthManager) -> None:
        h = auth_manager.hash_password("secret")
        assert h.startswith("$2b$")

    def test_different_salts_produce_different_hashes(self, auth_manager: AuthManager) -> None:
        h1 = auth_manager.hash_password("secret")
        h2 = auth_manager.hash_password("secret")
        assert h1 != h2

    def test_empty_password_raises_value_error(self, auth_manager: AuthManager) -> None:
        with pytest.raises(ValueError, match="Password cannot be empty"):
            auth_manager.hash_password("")

    def test_static_method_callable_without_instance(self) -> None:
        from app.services.auth_manager import AuthManager

        h = AuthManager.hash_password("mypassword")
        assert h.startswith("$2b$")


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


class TestVerifyPassword:
    def test_correct_password_returns_true(self, auth_manager: AuthManager) -> None:
        h = auth_manager.hash_password("correct")
        assert auth_manager.verify_password("correct", h) is True

    def test_wrong_password_returns_false(self, auth_manager: AuthManager) -> None:
        h = auth_manager.hash_password("correct")
        assert auth_manager.verify_password("wrong", h) is False

    def test_empty_plain_password_returns_false(self, auth_manager: AuthManager) -> None:
        h = auth_manager.hash_password("correct")
        # bcrypt.checkpw with empty bytes should return False (not raise)
        result = auth_manager.verify_password("", h)
        assert result is False

    def test_round_trip(self, auth_manager: AuthManager) -> None:
        """hash then verify returns True (requirement 2.13)."""
        password = "P@ssw0rd!123"
        assert auth_manager.verify_password(password, auth_manager.hash_password(password))

    def test_different_passwords_do_not_cross_verify(self, auth_manager: AuthManager) -> None:
        """Different passwords must not cross-verify (requirement 2.14)."""
        h = auth_manager.hash_password("password_a")
        assert auth_manager.verify_password("password_b", h) is False


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_returns_jwt_string(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", ["admin"])
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_payload_contains_user_fields(self, auth_manager: AuthManager) -> None:
        """Decoded payload must contain user_id, username, roles (requirement 2.15)."""
        token = auth_manager.create_access_token("uid1", "alice", ["admin", "viewer"])
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["user_id"] == "uid1"
        assert payload["username"] == "alice"
        assert payload["roles"] == ["admin", "viewer"]
        assert payload["token_type"] == "access"

    def test_payload_has_jti(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", [])
        payload = jwt.decode(token, options={"verify_signature": False})
        assert "jti" in payload and payload["jti"]

    def test_token_is_verifiable_with_secret(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", [])
        payload = jwt.decode(
            token, cast(str, settings.jwt_secret_key), algorithms=[settings.jwt_algorithm]
        )
        assert payload["user_id"] == "uid1"

    def test_expiration_is_set(self, auth_manager: AuthManager) -> None:
        before = datetime.now(timezone.utc)
        token = auth_manager.create_access_token("uid1", "alice", [])
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = before + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        assert abs((exp - expected).total_seconds()) < 60

    def test_empty_roles_allowed(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", [])
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["roles"] == []


# ---------------------------------------------------------------------------
# verify_token
# ---------------------------------------------------------------------------


class TestVerifyToken:
    @pytest.mark.asyncio
    async def test_valid_access_token_returns_payload(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", ["admin"])
        payload = await auth_manager.verify_token(token, expected_type="access")
        assert payload.user_id == "uid1"
        assert payload.username == "alice"
        assert payload.roles == ["admin"]
        assert payload.token_type == "access"

    @pytest.mark.asyncio
    async def test_valid_refresh_token_returns_payload(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_refresh_token("uid1", "alice", ["viewer"])
        payload = await auth_manager.verify_token(token, expected_type="refresh")
        assert payload.user_id == "uid1"
        assert payload.token_type == "refresh"

    @pytest.mark.asyncio
    async def test_expired_token_raises_expired_error(self, auth_manager: AuthManager) -> None:
        expired = jwt.encode(
            {
                "user_id": "uid1",
                "username": "alice",
                "roles": [],
                "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
                "token_type": "access",
            },
            cast(str, settings.jwt_secret_key),
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ExpiredTokenError):
            await auth_manager.verify_token(expired, expected_type="access")

    @pytest.mark.asyncio
    async def test_tampered_token_raises_invalid_error(self, auth_manager: AuthManager) -> None:
        """Tampered signature must raise InvalidTokenError (requirement 9.1)."""
        import base64
        import json

        token = auth_manager.create_access_token("uid1", "alice", [])
        header, payload_b64, sig = token.split(".")
        raw = base64.urlsafe_b64decode(payload_b64 + "==")
        data = json.loads(raw)
        data["user_id"] = "hacker"
        new_payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        tampered = f"{header}.{new_payload}.{sig}"
        with pytest.raises(InvalidTokenError):
            await auth_manager.verify_token(tampered, expected_type="access")

    @pytest.mark.asyncio
    async def test_wrong_secret_raises_invalid_error(self, auth_manager: AuthManager) -> None:
        bad_token = jwt.encode(
            {
                "user_id": "uid1",
                "username": "alice",
                "roles": [],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "token_type": "access",
            },
            "wrong-secret",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(InvalidTokenError):
            await auth_manager.verify_token(bad_token, expected_type="access")

    @pytest.mark.asyncio
    async def test_wrong_token_type_raises_invalid_error(self, auth_manager: AuthManager) -> None:
        refresh = auth_manager.create_refresh_token("uid1", "alice", [])
        with pytest.raises(InvalidTokenError, match="token type"):
            await auth_manager.verify_token(refresh, expected_type="access")

    @pytest.mark.asyncio
    async def test_malformed_token_raises_invalid_error(self, auth_manager: AuthManager) -> None:
        for bad in ["not.a.jwt", "invalid", "", "a.b"]:
            with pytest.raises(InvalidTokenError):
                await auth_manager.verify_token(bad, expected_type="access")

    @pytest.mark.asyncio
    async def test_revoked_token_raises_invalid_error(
        self, auth_manager_with_redis: AuthManager, redis: AsyncMock
    ) -> None:
        """Token whose JTI is in the Redis blocklist must be rejected."""
        redis.exists = AsyncMock(return_value=True)
        token = auth_manager_with_redis.create_access_token("uid1", "alice", [])
        with pytest.raises(InvalidTokenError, match="revoked"):
            await auth_manager_with_redis.verify_token(token, expected_type="access")

    @pytest.mark.asyncio
    async def test_missing_user_id_field_raises_invalid_error(
        self, auth_manager: AuthManager
    ) -> None:
        bad = jwt.encode(
            {
                "username": "alice",
                "roles": [],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "token_type": "access",
            },
            cast(str, settings.jwt_secret_key),
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(InvalidTokenError):
            await auth_manager.verify_token(bad, expected_type="access")


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_valid_refresh_token_returns_new_tokens(self, auth_manager: AuthManager) -> None:
        user_id = "uid1"
        username = "alice"
        roles = ["admin"]

        refresh_token = auth_manager.create_refresh_token(user_id, username, roles)
        db_row = _make_refresh_token_row(refresh_token, user_id)

        # DB query returns the row
        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]

        result = await auth_manager.refresh_access_token(refresh_token)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert result["expires_in"] > 0
        # Old token should be marked revoked
        assert db_row.revoked is True

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_raises_error(self, auth_manager: AuthManager) -> None:
        with pytest.raises((InvalidTokenError, AuthenticationError)):
            await auth_manager.refresh_access_token("not.a.valid.token")

    @pytest.mark.asyncio
    async def test_revoked_refresh_token_raises_authentication_error(
        self, auth_manager: AuthManager
    ) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])

        # DB returns no matching row (token revoked / not found)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(AuthenticationError, match="Invalid or revoked"):
            await auth_manager.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_expired_db_refresh_token_raises_expired_error(
        self, auth_manager: AuthManager
    ) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])
        db_row = _make_refresh_token_row(refresh_token, user_id, expired=True)

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]

        with pytest.raises(ExpiredTokenError):
            await auth_manager.refresh_access_token(refresh_token)

    @pytest.mark.asyncio
    async def test_db_commit_failure_raises_and_rolls_back(self, auth_manager: AuthManager) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])
        db_row = _make_refresh_token_row(refresh_token, user_id)

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]

        with pytest.raises(Exception):
            await auth_manager.refresh_access_token(refresh_token)

        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# revoke_refresh_token
# ---------------------------------------------------------------------------


class TestRevokeRefreshToken:
    @pytest.mark.asyncio
    async def test_valid_token_is_revoked(self, auth_manager: AuthManager) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])
        db_row = _make_refresh_token_row(refresh_token, user_id)

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]

        result = await auth_manager.revoke_refresh_token(refresh_token)

        assert result is True
        assert db_row.revoked is True
        auth_manager.db.commit.assert_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_token_not_in_db_returns_false(self, auth_manager: AuthManager) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])

        auth_manager.db.query.return_value.filter.return_value.first.return_value = None  # type: ignore[attr-defined]

        result = await auth_manager.revoke_refresh_token(refresh_token)
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_token_returns_false(self, auth_manager: AuthManager) -> None:
        result = await auth_manager.revoke_refresh_token("not.a.valid.token")
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_token_returns_false(self, auth_manager: AuthManager) -> None:
        expired = jwt.encode(
            {
                "user_id": "uid1",
                "username": "alice",
                "roles": [],
                "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
                "token_type": "refresh",
            },
            cast(str, settings.jwt_secret_key),
            algorithm=settings.jwt_algorithm,
        )
        result = await auth_manager.revoke_refresh_token(expired)
        assert result is False

    @pytest.mark.asyncio
    async def test_db_commit_failure_returns_false(self, auth_manager: AuthManager) -> None:
        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])
        db_row = _make_refresh_token_row(refresh_token, user_id)

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]

        result = await auth_manager.revoke_refresh_token(refresh_token)
        assert result is False
        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# revoke_access_token (Redis-based)
# ---------------------------------------------------------------------------


class TestRevokeAccessToken:
    @pytest.mark.asyncio
    async def test_revokes_token_with_redis(self, auth_manager_with_redis: AuthManager) -> None:
        token = auth_manager_with_redis.create_access_token("uid1", "alice", [])
        result = await auth_manager_with_redis.revoke_access_token(token)
        assert result is True
        auth_manager_with_redis.redis.setex.assert_called_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_no_redis_returns_false(self, auth_manager: AuthManager) -> None:
        token = auth_manager.create_access_token("uid1", "alice", [])
        result = await auth_manager.revoke_access_token(token)
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_token_raises_invalid_token_error(
        self, auth_manager_with_redis: AuthManager
    ) -> None:
        with pytest.raises(InvalidTokenError):
            await auth_manager_with_redis.revoke_access_token("not.a.valid.token")

    @pytest.mark.asyncio
    async def test_token_without_jti_returns_true(
        self, auth_manager_with_redis: AuthManager
    ) -> None:
        """Token with no JTI field still returns True (expires naturally)."""
        no_jti_token = jwt.encode(
            {
                "user_id": "uid1",
                "username": "alice",
                "roles": [],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "token_type": "access",
                # no jti
            },
            cast(str, settings.jwt_secret_key),
            algorithm=settings.jwt_algorithm,
        )
        result = await auth_manager_with_redis.revoke_access_token(no_jti_token)
        assert result is True


# ---------------------------------------------------------------------------
# revoke_all_user_tokens
# ---------------------------------------------------------------------------


class TestRevokeAllUserTokens:
    def test_revokes_all_active_tokens(self, auth_manager: AuthManager) -> None:
        rows = [MagicMock(revoked=False), MagicMock(revoked=False), MagicMock(revoked=False)]
        auth_manager.db.query.return_value.filter.return_value.all.return_value = rows  # type: ignore[attr-defined]

        count = auth_manager.revoke_all_user_tokens("uid1")

        assert count == 3
        for row in rows:
            assert row.revoked is True
        auth_manager.db.commit.assert_called_once()  # type: ignore[attr-defined]

    def test_no_tokens_returns_zero(self, auth_manager: AuthManager) -> None:
        auth_manager.db.query.return_value.filter.return_value.all.return_value = []  # type: ignore[attr-defined]
        count = auth_manager.revoke_all_user_tokens("uid1")
        assert count == 0

    def test_db_query_failure_raises_and_rolls_back(self, auth_manager: AuthManager) -> None:
        auth_manager.db.query.return_value.filter.return_value.all.side_effect = Exception(  # type: ignore[attr-defined]
            "DB error"
        )
        with pytest.raises(Exception):
            auth_manager.revoke_all_user_tokens("uid1")
        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]

    def test_db_commit_failure_raises_and_rolls_back(self, auth_manager: AuthManager) -> None:
        rows = [MagicMock(revoked=False)]
        auth_manager.db.query.return_value.filter.return_value.all.return_value = rows  # type: ignore[attr-defined]
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]

        with pytest.raises(Exception):
            auth_manager.revoke_all_user_tokens("uid1")
        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# MFA methods
# ---------------------------------------------------------------------------


class TestMfaMethods:
    def test_generate_mfa_secret_returns_string(self, auth_manager: AuthManager) -> None:
        secret = auth_manager.generate_mfa_secret()
        assert isinstance(secret, str)

    def test_get_mfa_qr_url_is_called(self, auth_manager: AuthManager) -> None:
        # pyotp is mocked; just verify the method runs without error
        auth_manager.get_mfa_qr_url("alice", "JBSWY3DPEHPK3PXP")

    def test_verify_mfa_code_is_called(self, auth_manager: AuthManager) -> None:
        # pyotp is mocked; just verify the method runs without error
        auth_manager.verify_mfa_code("JBSWY3DPEHPK3PXP", "123456")


# ---------------------------------------------------------------------------
# constant_time_compare
# ---------------------------------------------------------------------------


class TestConstantTimeCompare:
    def test_equal_strings_return_true(self) -> None:
        from app.services.auth_manager import AuthManager

        assert AuthManager.constant_time_compare("abc", "abc") is True

    def test_different_strings_return_false(self) -> None:
        from app.services.auth_manager import AuthManager

        assert AuthManager.constant_time_compare("abc", "xyz") is False


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------


class TestAuthenticateUser:
    def _make_user(
        self,
        password: str,
        is_active: bool = True,
        locked: bool = False,
        mfa_enabled: bool = False,
        fail_count: int = 0,
    ) -> MagicMock:
        from app.services.auth_manager import AuthManager

        user = MagicMock()
        user.username = "alice"
        user.password_hash = AuthManager.hash_password(password)
        user.is_active = is_active
        user.mfa_enabled = mfa_enabled
        user.failed_login_attempts = fail_count
        if locked:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        else:
            user.locked_until = None
        return user

    def test_returns_user_on_success(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct")
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        result = auth_manager.authenticate_user("alice", "correct")
        assert result is user

    def test_returns_none_when_user_not_found(self, auth_manager: AuthManager) -> None:
        auth_manager.db.query.return_value.filter.return_value.first.return_value = None  # type: ignore[attr-defined]
        result = auth_manager.authenticate_user("nobody", "pass")
        assert result is None

    def test_raises_when_account_locked(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", locked=True)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        with pytest.raises(AuthenticationError, match="locked"):
            auth_manager.authenticate_user("alice", "correct")

    def test_raises_when_account_inactive(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", is_active=False)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        with pytest.raises(AuthenticationError, match="pending activation"):
            auth_manager.authenticate_user("alice", "correct")

    def test_returns_none_on_wrong_password(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct")
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        result = auth_manager.authenticate_user("alice", "wrong")
        assert result is None

    def test_locks_account_after_5_failures(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", fail_count=4)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        auth_manager.authenticate_user("alice", "wrong")
        assert user.locked_until is not None

    def test_wrong_password_db_commit_failure_still_returns_none(
        self, auth_manager: AuthManager
    ) -> None:
        user = self._make_user("correct")
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]
        result = auth_manager.authenticate_user("alice", "wrong")
        assert result is None
        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]

    def test_raises_when_mfa_required_but_not_provided(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", mfa_enabled=True)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        with pytest.raises(AuthenticationError, match="MFA code required"):
            auth_manager.authenticate_user("alice", "correct")

    def test_raises_on_invalid_mfa_code(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", mfa_enabled=True)
        user.mfa_secret = "JBSWY3DPEHPK3PXP"
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        # verify_mfa_code is mocked via pyotp mock to return False
        with patch("app.services.auth_manager.AuthManager.verify_mfa_code", return_value=False):
            with pytest.raises(AuthenticationError, match="Invalid MFA code"):
                auth_manager.authenticate_user("alice", "correct", mfa_code="000000")

    def test_successful_login_resets_failed_attempts(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct", fail_count=2)
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        auth_manager.authenticate_user("alice", "correct")
        assert user.failed_login_attempts == 0

    def test_successful_login_db_commit_failure_still_returns_user(
        self, auth_manager: AuthManager
    ) -> None:
        user = self._make_user("correct")
        auth_manager.db.query.return_value.filter.return_value.first.return_value = user  # type: ignore[attr-defined]
        # First commit (for successful login) fails
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]
        result = auth_manager.authenticate_user("alice", "correct")
        assert result is user


# ---------------------------------------------------------------------------
# create_tokens_for_user
# ---------------------------------------------------------------------------


class TestCreateTokensForUser:
    def _make_user(
        self, password: str = "correct", fail_count: int = 0, mfa_enabled: bool = False
    ) -> MagicMock:
        user = MagicMock()
        user.user_id = "uid1"
        user.username = "alice"
        user.roles = ["admin"]
        return user

    def test_returns_token_dict(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct")
        result = auth_manager.create_tokens_for_user(user)
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert result["expires_in"] > 0
        auth_manager.db.add.assert_called_once()  # type: ignore[attr-defined]
        auth_manager.db.commit.assert_called_once()  # type: ignore[attr-defined]

    def test_remember_me_extends_refresh_expiry(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct")
        result = auth_manager.create_tokens_for_user(user, remember_me=True)
        # 30 days * 24 * 60 * 60
        assert result["refresh_expires_in"] == 30 * 24 * 60 * 60

    def test_db_commit_failure_raises_and_rolls_back(self, auth_manager: AuthManager) -> None:
        user = self._make_user("correct")
        auth_manager.db.commit.side_effect = Exception("DB error")  # type: ignore[attr-defined]
        with pytest.raises(Exception):
            auth_manager.create_tokens_for_user(user)
        auth_manager.db.rollback.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# refresh_access_token — hash mismatch branch
# ---------------------------------------------------------------------------


class TestRefreshAccessTokenHashMismatch:
    @pytest.mark.asyncio
    async def test_hash_mismatch_raises_authentication_error(
        self, auth_manager: AuthManager
    ) -> None:
        """When token_hash doesn't match, db_token is set to None → AuthenticationError."""
        from app.services.auth_manager import AuthManager

        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])

        # Row exists but with a WRONG hash (simulates hash mismatch)
        db_row = MagicMock()
        db_row.user_id = user_id
        db_row.token_hash = AuthManager.hash_password("different_token")
        import hashlib

        db_row.token_sha256 = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_row.revoked = False
        db_row.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]

        with pytest.raises(AuthenticationError, match="Invalid or revoked"):
            await auth_manager.refresh_access_token(refresh_token)


# ---------------------------------------------------------------------------
# revoke_refresh_token — hash mismatch branch
# ---------------------------------------------------------------------------


class TestRevokeRefreshTokenHashMismatch:
    @pytest.mark.asyncio
    async def test_hash_mismatch_returns_false(self, auth_manager: AuthManager) -> None:
        """When token_hash doesn't match, db_token is set to None → returns False."""
        from app.services.auth_manager import AuthManager as AM

        user_id = "uid1"
        refresh_token = auth_manager.create_refresh_token(user_id, "alice", [])

        db_row = MagicMock()
        db_row.user_id = user_id
        db_row.token_hash = AM.hash_password("different_token")
        import hashlib

        db_row.token_sha256 = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_row.revoked = False

        auth_manager.db.query.return_value.filter.return_value.first.return_value = db_row  # type: ignore[attr-defined]

        result = await auth_manager.revoke_refresh_token(refresh_token)
        assert result is False


# ---------------------------------------------------------------------------
# revoke_access_token — exception branch
# ---------------------------------------------------------------------------


class TestRevokeAccessTokenException:
    @pytest.mark.asyncio
    async def test_redis_exception_returns_false(
        self, auth_manager_with_redis: AuthManager, redis: AsyncMock
    ) -> None:
        """If Redis raises an unexpected exception, returns False."""
        redis.setex = AsyncMock(side_effect=Exception("Redis down"))
        token = auth_manager_with_redis.create_access_token("uid1", "alice", [])
        result = await auth_manager_with_redis.revoke_access_token(token)
        assert result is False
