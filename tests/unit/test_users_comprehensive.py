"""
Comprehensive unit tests for user routes to achieve 100% coverage.

Tests for all endpoints, error conditions, and edge cases.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.routes.users import (
    register_user,
    verify_email,
    create_default_user,
    get_current_user_profile,
    list_users,
    get_user_stats,
    delete_user,
    enroll_mfa,
    enable_mfa,
    disable_mfa,
    verify_mfa_backup_code,
    regenerate_mfa_backup_codes,
    request_password_reset,
    confirm_password_reset,
)
from app.database.models import User
from app.models.schemas import (
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
    PasswordResetEmailRequest,
    PasswordResetEmailResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    UserStatsResponse,
    MFAEnrollResponse,
    MFADisableRequest,
    MFADisableResponse,
    MFAEnableRequest,
    MFAEnableResponse,
    MFABackupCodeVerifyRequest,
    MFABackupCodeVerifyResponse,
    MFABackupCodeRegenerateResponse,
    UsersListResponse,
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

        assert isinstance(result, UserCreateResponse)
        assert result.user_id == 1
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.is_active is True
        assert result.is_verified is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_validation_error(self, mock_db):
        """Test user registration with validation error."""
        request = UserCreateRequest(
            username="ab", email="test@example.com", password="SecurePass123!"  # Too short
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request, mock_db)
        assert exc_info.value.status_code == 400
        assert "Username must be 3-50 characters" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, mock_db):
        """Test user registration with duplicate username."""
        request = UserCreateRequest(
            username="existinguser", email="test@example.com", password="SecurePass123!"
        )

        # Mock existing user
        existing_user = Mock(spec=User)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request, mock_db)
        assert exc_info.value.status_code == 400
        assert "Username already exists" in str(exc_info.value.detail)


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
        mock_user.email_verification_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_user.is_verified = False

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        result = await verify_email("valid_token", mock_db)

        assert result is True
        mock_user.is_verified = True
        mock_user.email_verification_token = None
        mock_user.email_verification_expires = None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("invalid_token", mock_db)
        assert exc_info.value.status_code == 404
        assert "Invalid or expired verification token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_email_expired_token(self, mock_db):
        """Test email verification with expired token."""
        mock_user = Mock(spec=User)
        mock_user.email_verification_token = "expired_token"
        mock_user.email_verification_expires = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("expired_token", mock_db)
        assert exc_info.value.status_code == 404
        assert "Invalid or expired verification token" in str(exc_info.value.detail)


class TestDefaultUserCreation:
    """Test default user creation endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_create_default_user_success(self, mock_db):
        """Test successful default user creation."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "admin"
        mock_user.email = "admin@example.com"
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch("app.routes.users.secrets.token_urlsafe", return_value="token"):
            result = await create_default_user(mock_db)

        assert isinstance(result, UserCreateResponse)
        assert result.username == "admin"
        assert result.email == "admin@example.com"
        assert result.is_active is True
        assert result.is_verified is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_default_user_already_exists(self, mock_db):
        """Test default user creation when user already exists."""
        existing_user = Mock(spec=User)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        with pytest.raises(HTTPException) as exc_info:
            await create_default_user(mock_db)
        assert exc_info.value.status_code == 400
        assert "Default user already exists" in str(exc_info.value.detail)


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
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert isinstance(result, UserResponse)
        assert result.id == "user123"
        assert result.username == "testuser"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_profile_not_found(self, mock_db, mock_current_user):
        """Test profile retrieval when user not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_profile(mock_current_user, mock_db)
        assert exc_info.value.status_code == 404
        assert "User not found" in str(exc_info.value.detail)


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
        mock_user1.email = "user1@example.com"
        mock_user1.is_active = True

        mock_user2 = Mock(spec=User)
        mock_user2.id = 2
        mock_user2.username = "user2"
        mock_user2.email = "user2@example.com"
        mock_user2.is_active = True

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

        assert isinstance(result, UsersListResponse)
        assert len(result.users) == 2
        assert result.users[0].id == 1
        assert result.users[0].username == "user1"
        assert result.pagination.page == 1
        assert result.pagination.per_page == 10
        assert result.pagination.total == 2

    @pytest.mark.asyncio
    async def test_list_users_invalid_page(self, mock_db):
        """Test user listing with invalid page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=0, per_page=10, active_only=True, db=mock_db)
        assert exc_info.value.status_code == 400
        assert "Page must be >= 1" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_users_invalid_per_page(self, mock_db):
        """Test user listing with invalid per_page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=1, per_page=101, active_only=True, db=mock_db)
        assert exc_info.status_code == 400
        assert "Per page must be between 1 and 100" in str(exc_info.value.detail)


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

        assert isinstance(result, UserStatsResponse)
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

        assert isinstance(result, PasswordResetEmailResponse)
        assert result.message == "Password reset instructions have been sent to your email"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_request_password_reset_user_not_found(self, mock_db):
        """Test password reset request for non-existent user."""
        request = PasswordResetEmailRequest(email="nonexistent@example.com")

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await request_password_reset(request, mock_db)

        assert isinstance(result, PasswordResetEmailResponse)
        assert result.message == "Password reset instructions have been sent to your email"
        assert result.email == "nonexistent@example.com"

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

        assert isinstance(result, PasswordResetConfirmResponse)
        assert result.message == "Password has been reset successfully"
        assert mock_user.password_reset_token is None
        assert mock_user.password_reset_expires is None

    @pytest.mark.asyncio
    async def test_confirm_password_reset_invalid_token(self, mock_db):
        """Test password reset confirmation with invalid token."""
        request = PasswordResetConfirmRequest(
            token="invalid_token", new_password="NewSecurePass123!"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await confirm_password_reset(request, mock_db)
        assert exc_info.value.status_code == 404
        assert "Invalid or expired reset token" in str(exc_info.value.detail)


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
        assert "User not found" in str(exc_info.value.detail)


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
        mock_user = Mock(spec=User)
        mock_user.id = "user123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        with patch("app.routes.users.pyotp.TOTP", return_value=Mock()) as mock_totp:
            mock_totp.provisioning_uri.return_value = "otpauth://test"
            mock_totp.secret = "test_secret"

            result = await enroll_mfa(mock_db, mock_current_user)

            assert isinstance(result, MFAEnrollResponse)
            assert result.secret_key == "test_secret"
            assert result.qr_code == "otpauth://test"
            assert mock_user.mfa_secret == "test_secret"

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

            assert isinstance(result, MFAEnableResponse)
            assert result.message == "MFA has been enabled successfully"
            assert mock_user.mfa_enabled is True

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

        assert isinstance(result, MFADisableResponse)
        assert result.message == "MFA has been disabled successfully"
        assert mock_user.mfa_enabled is False
        assert mock_user.mfa_secret is None

    @pytest.mark.asyncio
    async def test_verify_mfa_backup_code_success(self, mock_db, mock_current_user):
        """Test successful MFA backup code verification."""
        request = MFABackupCodeVerifyRequest(backup_code="12345678")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.mfa_enabled = True
        mock_user.mfa_backup_codes = ["12345678", "87654321"]

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        result = await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert isinstance(result, MFABackupCodeVerifyResponse)
        assert result.message == "Backup code verified successfully"

    @pytest.mark.asyncio
    async def test_regenerate_mfa_backup_codes_success(self, mock_db, mock_current_user):
        """Test successful MFA backup codes regeneration."""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.mfa_enabled = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        with patch("app.routes.users.pyotp.TOTP", return_value=Mock()) as mock_totp:
            mock_totp.provisioning_uri.return_value = "otpauth://test"

            result = await regenerate_mfa_backup_codes(mock_db, mock_current_user)

            assert isinstance(result, MFABackupCodeRegenerateResponse)
            assert len(result.backup_codes) == 10
            assert "backup code" in result.backup_codes[0].lower()


class TestEdgeCases:
    """Test edge cases and error conditions."""

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
    async def test_get_user_by_id_success(self, mock_db):
        """Test getting user by ID."""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from app.routes.users import get_user

        result = await get_user("user123", mock_db)

        assert result.id == "user123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """Test getting user by ID when not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from app.routes.users import get_user

        with pytest.raises(HTTPException) as exc_info:
            await get_user("nonexistent", mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_update_user_success(self, mock_db, mock_current_user):
        """Test partial user update."""
        request = UserUpdateRequest(email="newemail@example.com")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.email = "oldemail@example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        from app.routes.users import partial_update_user

        result = await partial_update_user("user123", request, mock_db)

        assert result.email == "newemail@example.com"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_db):
        """Test full user update."""
        request = UserUpdateRequest(
            username="newusername", email="newemail@example.com", is_active=False
        )

        mock_user = Mock(spec=User)
        mock_user.id = "user123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        from app.routes.users import update_user

        result = await update_user("user123", request, mock_db)

        assert result.username == "newusername"
        assert result.email == "newemail@example.com"
        assert result.is_active is False
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_user_password_admin_success(self, mock_db):
        """Test admin password reset."""
        request = PasswordResetRequest(password="NewPassword123!")

        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.password_hash = "old_hash"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit.return_value = None

        from app.routes.users import reset_user_password

        result = await reset_user_password("user123", request, mock_db)

        assert isinstance(result, PasswordResetResponse)
        assert result.message == "Password has been reset successfully"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_user_operations(self, mock_db, mock_current_user):
        """Test concurrent user operations."""
        # Simulate concurrent profile requests
        from app.routes.users import get_current_user_profile

        tasks = [get_current_user_profile(mock_current_user, mock_db) for _ in range(3)]

        # Mock the database query to return the same user each time
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        import asyncio

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(result.id == "user123" for result in results)

    @pytest.mark.asyncio
    async def test_user_profile_with_missing_fields(self, mock_db, mock_current_user):
        """Test user profile with missing optional fields."""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"
        # Missing email, is_active, is_verified, created_at, updated_at

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert result.id == "user123"
        assert result.username == "testuser"
        # Default values should be used for missing fields
