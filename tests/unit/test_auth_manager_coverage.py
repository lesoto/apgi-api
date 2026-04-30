"""
Coverage tests for app/services/auth_manager.py
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import RefreshToken, User
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError
from app.services.auth_manager import AuthManager


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def auth_manager(mock_db):
    return AuthManager(db=mock_db)


def test_hash_password_empty():
    """Test hash_password with empty password."""
    with pytest.raises(ValueError, match="Password cannot be empty"):
        AuthManager.hash_password("")


def test_verify_password_success():
    """Test verify_password success."""
    pwd = "password123"
    hashed = AuthManager.hash_password(pwd)
    assert AuthManager.verify_password(pwd, hashed) is True


def test_mfa_methods():
    """Test MFA helper methods."""
    secret = AuthManager.generate_mfa_secret()
    assert len(secret) > 0
    url = AuthManager.get_mfa_qr_url("user", secret)
    assert "user" in url
    assert "APGI" in url


@pytest.mark.asyncio
async def test_verify_token_invalid_type(auth_manager):
    """Test verify_token with wrong type."""
    token = auth_manager.create_access_token("uid", "user", ["role"])
    with pytest.raises(InvalidTokenError, match="Invalid token type"):
        await auth_manager.verify_token(token, expected_type="refresh")


@pytest.mark.asyncio
async def test_verify_token_expired(auth_manager):
    """Test verify_token with expired token."""
    auth_manager.access_token_expire_minutes = -1
    token = auth_manager.create_access_token("uid", "user", ["role"])
    with pytest.raises(ExpiredTokenError):
        await auth_manager.verify_token(token)


@pytest.mark.asyncio
async def test_revoke_access_token_no_redis(auth_manager):
    """Test revoke_access_token when Redis is missing."""
    auth_manager.redis = None
    assert await auth_manager.revoke_access_token("token") is False


@pytest.mark.asyncio
async def test_revoke_access_token_success(auth_manager):
    """Test revoke_access_token success path."""
    auth_manager.redis = AsyncMock()
    token = auth_manager.create_access_token("uid", "user", ["role"])
    assert await auth_manager.revoke_access_token(token) is True
    auth_manager.redis.setex.assert_called_once()


def test_authenticate_user_locked(auth_manager, mock_db):
    """Test authenticate_user when account is locked."""
    user = User(username="user", locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
    mock_db.query.return_value.filter.return_value.first.return_value = user

    with pytest.raises(AuthenticationError, match="locked"):
        auth_manager.authenticate_user("user", "pwd")


def test_authenticate_user_inactive(auth_manager, mock_db):
    """Test authenticate_user when account is inactive."""
    user = User(username="user", is_active=False, locked_until=None)
    mock_db.query.return_value.filter.return_value.first.return_value = user

    with pytest.raises(AuthenticationError, match="activation"):
        auth_manager.authenticate_user("user", "pwd")


def test_authenticate_user_mfa_required(auth_manager, mock_db):
    """Test authenticate_user when MFA is enabled but code missing."""
    hashed = AuthManager.hash_password("pwd")
    user = User(
        username="user", password_hash=hashed, is_active=True, locked_until=None, mfa_enabled=True
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    with pytest.raises(AuthenticationError, match="MFA code required"):
        auth_manager.authenticate_user("user", "pwd")


@pytest.mark.asyncio
async def test_refresh_access_token_invalid_db_token(auth_manager, mock_db):
    """Test refresh_access_token when token not in DB."""
    # Create valid refresh token
    token = auth_manager.create_refresh_token("uid", "user", ["role"])

    # Mock DB query to return None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(AuthenticationError, match="Invalid or revoked refresh token"):
        await auth_manager.refresh_access_token(token)


@pytest.mark.asyncio
async def test_revoke_refresh_token_not_found(auth_manager, mock_db):
    """Test revoke_refresh_token when token not found in DB."""
    token = auth_manager.create_refresh_token("uid", "user", ["role"])
    mock_db.query.return_value.filter.return_value.first.return_value = None

    assert await auth_manager.revoke_refresh_token(token) is False


def test_revoke_all_user_tokens(auth_manager, mock_db):
    """Test revoke_all_user_tokens."""
    token1 = MagicMock(spec=RefreshToken)
    token2 = MagicMock(spec=RefreshToken)
    mock_db.query.return_value.filter.return_value.all.return_value = [token1, token2]

    count = auth_manager.revoke_all_user_tokens("uid")
    assert count == 2
    assert token1.revoked is True
    assert token2.revoked is True
    assert mock_db.commit.called
