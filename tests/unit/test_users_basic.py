"""Basic unit tests for user routes to establish coverage foundation.

Tests core functionality without complex schema validation.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.routes.users import (
    register_user,
    verify_email,
    get_current_user_profile,
    list_users,
    get_user_stats,
    delete_user,
    enroll_mfa,
    enable_mfa,
    disable_mfa,
    request_password_reset,
    confirm_password_reset,
)
from app.database.models import User
from app.models.schemas import (
    UserCreateRequest,
    PasswordResetEmailRequest,
    PasswordResetConfirmRequest,
    MFAEnableRequest,
    MFADisableRequest,
)
from app.services.authorization import TokenPayload


class TestUserRegistration:
    """Test user registration endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db):
        """Test successful user registration."""
        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.is_verified = False
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch("app.routes.users.secrets.token_urlsafe", return_value="verification_token"):
            result = await register_user(request, mock_db)

            assert result.user_id == 1
            assert result.username == "testuser"
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_user_validation_error(self, mock_db):
        """Test user registration with validation error."""
        request = UserCreateRequest(
            username="ab", email="test@example.com", password="SecurePass123!"  # Too short
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request, mock_db)
            assert exc_info.value.status_code == 400


class TestEmailVerification:
    """Test email verification endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_verify_email_success(self, mock_db):
        """Test successful email verification."""
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email_verification_token = "valid_token"
        mock_user.is_verified = False

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        result = await verify_email("valid_token", mock_db)

        assert result is True
        assert mock_user.is_verified is True

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("invalid_token", mock_db)
            assert exc_info.value.status_code == 404


class TestUserProfile:
    """Test user profile endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user token payload."""
        return TokenPayload(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    @pytest.mark.asyncio
    async def test_get_current_user_profile_success(self, mock_db, mock_current_user):
        """Test successful profile retrieval."""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_profile_not_found(self, mock_db, mock_current_user):
        """Test profile retrieval when user not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_profile(mock_current_user, mock_db)
            assert exc_info.value.status_code == 404


class TestUserList:
    """Test user list endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_db):
        """Test successful user listing."""
        mock_user1 = Mock(spec=User)
        mock_user1.id = 1
        mock_user1.username = "user1"

        mock_user2 = Mock(spec=User)
        mock_user2.id = 2
        mock_user2.username = "user2"

        # Mock count query
        mock_count_query = Mock()
        mock_count_query.scalar.return_value = 2
        # Mock list query
        mock_list_query = Mock()
        mock_list_query.offset.return_value.limit.return_value.all.return_value = [
            mock_user1,
            mock_user2,
        ]

        mock_db.query.side_effect = [mock_count_query, mock_list_query]

        result = await list_users(page=1, per_page=10, active_only=True, db=mock_db)

        assert len(result.users) == 2
        assert result.pagination.page == 1
        assert result.pagination.per_page == 10
        assert result.pagination.total == 2


class TestUserStats:
    """Test user statistics endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, mock_db):
        """Test successful user stats retrieval."""
        mock_count = Mock()
        mock_count.return_value = 100
        mock_active_count = Mock()
        mock_active_count.return_value = 80
        mock_verified_count = Mock()
        mock_verified_count.return_value = 60
        mock_created_today = Mock()
        mock_created_today.return_value = 5

        mock_db.query.side_effect = [
            mock_count,
            mock_active_count,
            mock_verified_count,
            mock_created_today,
        ]

        result = await get_user_stats(db=mock_db)

        assert result.total_users == 100
        assert result.active_users == 80
        assert result.verified_users == 60
        assert result.created_today == 5


class TestPasswordReset:
    """Test password reset endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_request_password_reset_success(self, mock_db):
        """Test successful password reset request."""
        request = PasswordResetEmailRequest(email="test@example.com")

        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_reset_token = "reset_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        with patch("app.routes.users.secrets.token_urlsafe", return_value="reset_token"):
            result = await request_password_reset(request, mock_db)

            assert result.message == "Password reset instructions have been sent to your email"

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, mock_db):
        """Test successful password reset confirmation."""
        request = PasswordResetConfirmRequest(token="valid_token", new_password="NewSecurePass123!")

        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.password_reset_token = "valid_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        result = await confirm_password_reset(request, mock_db)

        assert result.message == "Password has been reset successfully"


class TestUserDeletion:
    """Test user deletion endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_db):
        """Test successful user deletion."""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None

        result = await delete_user("user123", mock_db)

        assert result is None
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_db):
        """Test user deletion when user not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_user("nonexistent", mock_db)
            assert exc_info.value.status_code == 404


class TestMFA:
    """Test Multi-Factor Authentication endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user token payload."""
        return TokenPayload(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    @pytest.mark.asyncio
    async def test_enroll_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA enrollment."""
        request = MFAEnableRequest(code="123456")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        with patch("app.routes.users.pyotp.TOTP", return_value=Mock()) as mock_totp:
            mock_totp.provisioning_uri.return_value = "otpauth://test"
            mock_totp.secret = "test_secret"

            result = await enroll_mfa(mock_db, mock_current_user)

            assert result.secret_key == "test_secret"
            assert result.qr_code == "otpauth://test"

    @pytest.mark.asyncio
    async def test_enable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA enabling."""
        request = MFAEnableRequest(code="123456")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.mfa_secret = "test_secret"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        with patch("app.routes.users.pyotp.TOTP", return_value=Mock()) as mock_totp:
            mock_totp.verify.return_value = True

            result = await enable_mfa(request, mock_db, mock_current_user)

            assert result.message == "MFA has been enabled successfully"

    @pytest.mark.asyncio
    async def test_disable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA disabling."""
        request = MFADisableRequest(password="SecurePass123!")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.mfa_enabled = True
        mock_user.mfa_secret = "test_secret"
        mock_user.password_hash = "hashed_password"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        result = await disable_mfa(request, mock_db, mock_current_user)

        assert result.message == "MFA has been disabled successfully"
