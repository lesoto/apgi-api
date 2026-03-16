"""Simple unit tests for user routes to achieve basic coverage.

Focuses on testing function calls and error paths without complex schema validation.
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
    get_user,
    partial_update_user,
    update_user,
    request_password_reset,
    confirm_password_reset,
    reset_user_password,
    enroll_mfa,
    enable_mfa,
    disable_mfa,
    verify_mfa_backup_code,
    regenerate_mfa_backup_codes,
    delete_user,
)
from app.database.models import User
from app.models.schemas import (
    UserCreateRequest,
    PasswordResetEmailRequest,
    PasswordResetConfirmRequest,
    MFAEnableRequest,
    MFADisableRequest,
    MFABackupCodeVerifyRequest,
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

        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.user_id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.now(timezone.utc)

        mock_user_service.create_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await register_user(request, mock_db)

            assert result.user_id == "1"
            assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, mock_db):
        """Test user registration with duplicate username."""
        request = UserCreateRequest(
            username="existinguser", email="test@example.com", password="SecurePass123!"
        )

        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.create_user.side_effect = Exception("Username already exists")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
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
        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.verify_email.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await verify_email("valid_token", mock_db)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.verify_email.side_effect = Exception("Invalid token")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
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
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    @pytest.mark.asyncio
    async def test_get_current_user_profile_success(self, mock_db, mock_current_user):
        """Test successful profile retrieval."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"

        mock_user_service.get_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await get_current_user_profile(mock_current_user, mock_db)

            assert result.user_id == "user123"
            assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_profile_not_found(self, mock_db, mock_current_user):
        """Test profile retrieval when user not found."""
        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.get_user.side_effect = Exception("User not found")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
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
        # Mock the user service
        mock_user_service = Mock()
        mock_user1 = Mock(spec=User)
        mock_user1.id = 1
        mock_user1.username = "user1"

        mock_user2 = Mock(spec=User)
        mock_user2.id = 2
        mock_user2.username = "user2"

        mock_user_service.list_users.return_value = ([mock_user1, mock_user2], 2)

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await list_users(page=1, per_page=10, active_only=True, db=mock_db)

            assert len(result.users) == 2
            assert result.pagination.page == 1
            assert result.pagination.per_page == 10
            assert result.pagination.total == 2

    @pytest.mark.asyncio
    async def test_list_users_invalid_page(self, mock_db):
        """Test user listing with invalid page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=0, per_page=10, active_only=True, db=mock_db)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_users_invalid_per_page(self, mock_db):
        """Test user listing with invalid per_page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=1, per_page=101, active_only=True, db=mock_db)
            assert exc_info.value.status_code == 400


class TestUserStats:
    """Test user statistics endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, mock_db):
        """Test successful user stats retrieval."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.get_user_stats.return_value = {
            "total_users": 100,
            "active_users": 80,
            "verified_users": 60,
            "created_today": 5,
        }

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
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

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.request_password_reset.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await request_password_reset(request, mock_db)

            assert result.message == "Password reset instructions have been sent to your email"

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, mock_db):
        """Test successful password reset confirmation."""
        request = PasswordResetConfirmRequest(token="valid_token", new_password="NewSecurePass123!")

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.confirm_password_reset.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await confirm_password_reset(request, mock_db)

            assert result.message == "Password has been reset successfully"

    @pytest.mark.asyncio
    async def test_confirm_password_reset_invalid_token(self, mock_db):
        """Test password reset confirmation with invalid token."""
        request = PasswordResetConfirmRequest(
            token="invalid_token", new_password="NewSecurePass123!"
        )

        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.confirm_password_reset.side_effect = Exception("Invalid token")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            with pytest.raises(HTTPException) as exc_info:
                await confirm_password_reset(request, mock_db)
                assert exc_info.value.status_code == 404


class TestUserDeletion:
    """Test user deletion endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_db):
        """Test successful user deletion."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.delete_user.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await delete_user("user123", mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_db):
        """Test user deletion when user not found."""
        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.delete_user.side_effect = Exception("User not found")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
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
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    @pytest.mark.asyncio
    async def test_enroll_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA enrollment."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.enroll_mfa.return_value = {
            "secret_key": "test_secret",
            "qr_code": "otpauth://test",
        }

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await enroll_mfa(mock_db, mock_current_user)

            assert result.secret_key == "test_secret"
            assert result.qr_code == "otpauth://test"

    @pytest.mark.asyncio
    async def test_enable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA enabling."""
        request = MFAEnableRequest(code="123456")

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.enable_mfa.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await enable_mfa(request, mock_db, mock_current_user)

            assert result.message == "MFA has been enabled successfully"

    @pytest.mark.asyncio
    async def test_disable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA disabling."""
        request = MFADisableRequest(password="SecurePass123!")

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.disable_mfa.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await disable_mfa(request, mock_db, mock_current_user)

            assert result.message == "MFA has been disabled successfully"

    @pytest.mark.asyncio
    async def test_verify_mfa_backup_code_success(self, mock_db, mock_current_user):
        """Test successful MFA backup code verification."""
        request = MFABackupCodeVerifyRequest(code="12345678")

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.verify_backup_code.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await verify_mfa_backup_code(request, mock_db, mock_current_user)

            assert result.message == "Backup code verified successfully"

    @pytest.mark.asyncio
    async def test_regenerate_mfa_backup_codes_success(self, mock_db, mock_current_user):
        """Test successful MFA backup codes regeneration."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.regenerate_backup_codes.return_value = ["code1", "code2", "code3"]

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await regenerate_mfa_backup_codes(mock_db, mock_current_user)

            assert len(result.backup_codes) == 3


class TestOtherEndpoints:
    """Test other user endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_create_default_user_success(self, mock_db):
        """Test successful default user creation."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.user_id = 1
        mock_user.username = "admin"
        mock_user.email = "admin@example.com"
        mock_user.created_at = datetime.now(timezone.utc)

        mock_user_service.create_default_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await create_default_user(mock_db)

            assert result.user_id == "1"
            assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        """Test getting user by ID."""
        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "testuser"

        mock_user_service.get_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await get_user("user123", mock_db)

            assert result.user_id == "user123"
            assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """Test getting user by ID when not found."""
        # Mock the user service to raise exception
        mock_user_service = Mock()
        mock_user_service.get_user.side_effect = Exception("User not found")

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            with pytest.raises(HTTPException) as exc_info:
                await get_user("nonexistent", mock_db)
                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_update_user_success(self, mock_db):
        """Test partial user update."""
        from app.models.schemas import UserUpdateRequest

        request = UserUpdateRequest(email="newemail@example.com")

        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.email = "newemail@example.com"

        mock_user_service.update_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await partial_update_user("user123", request, mock_db)

            assert result.email == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_db):
        """Test full user update."""
        from app.models.schemas import UserUpdateRequest

        request = UserUpdateRequest(
            username="newusername", email="newemail@example.com", is_active=False
        )

        # Mock the user service
        mock_user_service = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.username = "newusername"
        mock_user.email = "newemail@example.com"
        mock_user.is_active = False

        mock_user_service.update_user.return_value = mock_user

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await update_user("user123", request, mock_db)

            assert result.username == "newusername"
            assert result.email == "newemail@example.com"
            assert result.is_active is False

    @pytest.mark.asyncio
    async def test_reset_user_password_admin_success(self, mock_db):
        """Test admin password reset."""
        from app.models.schemas import PasswordResetRequest

        request = PasswordResetRequest(password="NewPassword123!")

        # Mock the user service
        mock_user_service = Mock()
        mock_user_service.reset_user_password.return_value = True

        with patch("app.routes.users.get_user_management_service", return_value=mock_user_service):
            result = await reset_user_password("user123", request, mock_db)

            assert result.message == "Password has been reset successfully"
