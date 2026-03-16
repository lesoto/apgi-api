"""
Unit tests for user management routes.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.exceptions import UserNotFoundError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def mock_user_service():
    """Mock user management service."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_current_user():
    """Mock current user token payload."""
    user = MagicMock()
    user.user_id = "user123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.roles = ["viewer"]
    return user


@pytest.fixture
def mock_admin_user():
    """Mock admin user token payload."""
    user = MagicMock()
    user.user_id = "admin123"
    user.username = "admin"
    user.email = "admin@example.com"
    user.roles = ["admin"]
    return user


@pytest.fixture
def mock_user_model():
    """Mock user model."""
    user = MagicMock()
    user.user_id = "user123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.password_hash = "hashed_password"
    user.roles = ["viewer"]
    user.is_active = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.last_login = None
    user.mfa_secret = None
    user.mfa_enabled = False
    user.mfa_backup_codes = None
    user.email_verification_token = None
    user.email_verification_expires_at = None
    return user


class TestUserRegistration:
    """Tests for user registration endpoints."""

    @patch("app.routes.users.get_user_management_service")
    async def test_register_user_success(self, mock_get_service, mock_db, mock_user_model):
        """Test successful user registration."""
        mock_service = MagicMock()
        mock_service.create_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import register_user, UserCreateRequest

        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        result = await register_user(request, mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        mock_service.create_user.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_register_user_duplicate_username(self, mock_get_service, mock_db):
        """Test registration with duplicate username."""
        mock_service = MagicMock()
        mock_service.create_user.side_effect = ValueError("Username already exists")
        mock_get_service.return_value = mock_service

        from app.routes.users import register_user, UserCreateRequest

        request = UserCreateRequest(
            username="existinguser", email="test@example.com", password="Secur3P@ss!"
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request, mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_email_success(self, mock_get_service, mock_db, mock_user_model):
        """Test successful email verification."""
        mock_user_model.email_verification_token = "valid_token"
        mock_user_model.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=1
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_model

        from app.routes.users import verify_email

        result = await verify_email("valid_token", mock_db)

        assert result["message"] == "Email verified successfully. You can now log in."
        assert mock_user_model.is_active is True
        mock_db.commit.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_email_invalid_token(self, mock_get_service, mock_db):
        """Test email verification with invalid token."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from app.routes.users import verify_email

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("invalid_token", mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestUserManagement:
    """Tests for user management endpoints."""

    @patch("app.routes.users.get_user_management_service")
    async def test_list_users_success(
        self, mock_get_service, mock_db, mock_user_model, mock_current_user
    ):
        """Test successful user listing."""
        mock_service = MagicMock()
        mock_service.list_users.return_value = [mock_user_model]
        mock_service.get_user_stats.return_value = {
            "total_users": 1,
            "active_users": 1,
            "inactive_users": 0,
            "role_counts": {"viewer": 1},
            "total_sessions": 0,
            "active_sessions": 0,
        }
        mock_get_service.return_value = mock_service

        from app.routes.users import list_users

        result = await list_users(page=1, per_page=10, active_only=True, db=mock_db)

        assert len(result.users) == 1
        assert result.users[0].user_id == "user123"
        assert result.pagination.page == 1

    @patch("app.routes.users.get_user_management_service")
    async def test_list_users_invalid_page(self, mock_get_service, mock_db):
        """Test user listing with invalid page number."""
        from app.routes.users import list_users

        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=0, per_page=10, active_only=True, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_get_current_user_profile_success(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test getting current user profile."""
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import get_current_user_profile

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"

    @patch("app.routes.users.get_user_management_service")
    async def test_get_current_user_profile_not_found(
        self, mock_get_service, mock_db, mock_current_user
    ):
        """Test getting current user profile when user not found."""
        mock_service = MagicMock()
        mock_service.get_user.return_value = None
        mock_get_service.return_value = mock_service

        from app.routes.users import get_current_user_profile

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_profile(mock_current_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.users.get_user_management_service")
    async def test_get_user_stats_success(self, mock_get_service, mock_db):
        """Test getting user statistics."""
        mock_service = MagicMock()
        mock_service.get_user_stats.return_value = {
            "total_users": 100,
            "active_users": 80,
            "inactive_users": 20,
            "role_counts": {"viewer": 70, "admin": 10},
            "total_sessions": 500,
            "active_sessions": 50,
        }
        mock_get_service.return_value = mock_service

        from app.routes.users import get_user_stats

        result = await get_user_stats(mock_db)

        assert result.total_users == 100
        assert result.active_users == 80
        assert result.inactive_users == 20

    @patch("app.routes.users.get_user_management_service")
    async def test_get_user_success(self, mock_get_service, mock_db, mock_user_model):
        """Test getting user by ID."""
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import get_user

        result = await get_user("user123", mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"

    @patch("app.routes.users.get_user_management_service")
    async def test_get_user_not_found(self, mock_get_service, mock_db):
        """Test getting non-existent user."""
        mock_service = MagicMock()
        mock_service.get_user.return_value = None
        mock_get_service.return_value = mock_service

        from app.routes.users import get_user

        with pytest.raises(HTTPException) as exc_info:
            await get_user("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestUserUpdate:
    """Tests for user update endpoints."""

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_partial_update_user_as_admin(
        self, mock_has_permission, mock_get_service, mock_db, mock_admin_user, mock_user_model
    ):
        """Test partial user update as admin."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.update_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import partial_update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=["admin"], password=None, is_active=None
        )

        result = await partial_update_user("user123", request, mock_db, mock_admin_user)

        assert result.email == "newemail@example.com"
        mock_service.update_user.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_partial_update_user_unauthorized(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test partial user update when unauthorized."""
        mock_has_permission.return_value = False
        mock_get_service.return_value = MagicMock()

        from app.routes.users import partial_update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", password=None, roles=None, is_active=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await partial_update_user("otheruser", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_update_user_success(
        self, mock_has_permission, mock_get_service, mock_db, mock_admin_user, mock_user_model
    ):
        """Test full user update."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.update_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=["admin"], password=None, is_active=None
        )

        result = await update_user("user123", request, mock_db, mock_admin_user)

        assert result.email == "newemail@example.com"
        mock_service.update_user.assert_called_once()


class TestPasswordReset:
    """Tests for password reset endpoints."""

    @patch("app.routes.users.get_user_management_service")
    async def test_request_password_reset_success(self, mock_get_service, mock_db):
        """Test successful password reset request."""
        mock_service = MagicMock()
        mock_service.request_password_reset.return_value = None
        mock_get_service.return_value = mock_service

        from app.routes.users import request_password_reset, PasswordResetEmailRequest

        request = PasswordResetEmailRequest(email="test@example.com")

        result = await request_password_reset(request, mock_db)

        assert "password reset link" in result.message.lower()

    @patch("app.routes.users.get_user_management_service")
    async def test_request_password_reset_user_not_found(self, mock_get_service, mock_db):
        """Test password reset request for non-existent user."""
        from app.exceptions import UserNotFoundError

        mock_service = MagicMock()
        mock_service.request_password_reset.side_effect = UserNotFoundError("user123")
        mock_get_service.return_value = mock_service

        from app.routes.users import request_password_reset, PasswordResetEmailRequest

        request = PasswordResetEmailRequest(email="nonexistent@example.com")

        result = await request_password_reset(request, mock_db)

        # Should still return success message to avoid email enumeration
        assert "password reset link" in result.message.lower()

    @patch("app.routes.users.get_user_management_service")
    async def test_confirm_password_reset_success(self, mock_get_service, mock_db):
        """Test successful password reset confirmation."""
        mock_service = MagicMock()
        mock_service.confirm_password_reset.return_value = None
        mock_get_service.return_value = mock_service

        from app.routes.users import confirm_password_reset, PasswordResetConfirmRequest

        request = PasswordResetConfirmRequest(token="valid_token", new_password="N3wS3cur3!")

        result = await confirm_password_reset(request, mock_db)

        assert "Password has been reset" in result.message

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_reset_user_password_success(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test successful user password reset."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.reset_password.return_value = None
        mock_get_service.return_value = mock_service

        from app.routes.users import reset_user_password, PasswordResetRequest

        request = PasswordResetRequest(new_password="N3wS3cur3!")

        result = await reset_user_password("user123", request, mock_db, mock_current_user)

        assert result.user_id == "user123"
        assert "Password reset successfully" in result.message


class TestMFA:
    """Tests for Multi-Factor Authentication endpoints."""

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enroll_mfa_success(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test successful MFA enrollment."""
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        mock_auth_manager = MagicMock()
        mock_auth_manager.generate_mfa_secret.return_value = "JBSWY3DPEHPK3PXP"
        mock_auth_manager.get_mfa_qr_url.return_value = (
            "otpauth://totp/testuser?secret=JBSWY3DPEHPK3PXP"
        )
        mock_auth_manager_class.return_value = mock_auth_manager

        from app.routes.users import enroll_mfa

        result = await enroll_mfa(mock_db, mock_current_user)

        assert result.secret == "JBSWY3DPEHPK3PXP"
        assert result.qr_code_url == "otpauth://totp/testuser?secret=JBSWY3DPEHPK3PXP"
        assert len(result.backup_codes) == 10
        assert mock_user_model.mfa_enabled is False

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enable_mfa_success(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test successful MFA enable."""
        mock_user_model.mfa_secret = "JBSWY3DPEHPK3PXP"
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        mock_auth_manager = MagicMock()
        mock_auth_manager.verify_mfa_code.return_value = True
        mock_auth_manager_class.return_value = mock_auth_manager

        from app.routes.users import enable_mfa, MFAEnableRequest

        request = MFAEnableRequest(code="123456")

        result = await enable_mfa(request, mock_db, mock_current_user)

        assert "MFA enabled successfully" in result.message
        assert mock_user_model.mfa_enabled is True

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enable_mfa_invalid_code(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA enable with invalid code."""
        mock_user_model.mfa_secret = "JBSWY3DPEHPK3PXP"
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        mock_auth_manager = MagicMock()
        mock_auth_manager.verify_mfa_code.return_value = False
        mock_auth_manager_class.return_value = mock_auth_manager

        from app.routes.users import enable_mfa, MFAEnableRequest

        request = MFAEnableRequest(code="000000")

        with pytest.raises(HTTPException) as exc_info:
            await enable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_disable_mfa_success(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test successful MFA disable."""
        mock_user_model.mfa_enabled = True
        mock_user_model.password_hash = "hashed_password"
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        mock_auth_manager = MagicMock()
        mock_auth_manager.verify_password.return_value = True
        mock_auth_manager_class.return_value = mock_auth_manager

        from app.routes.users import disable_mfa, MFADisableRequest

        request = MFADisableRequest(password="Curr3ntP@ss!")

        result = await disable_mfa(request, mock_db, mock_current_user)

        assert "MFA disabled successfully" in result.message
        assert mock_user_model.mfa_enabled is False

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_mfa_backup_code_success(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test successful MFA backup code verification."""
        import hashlib

        mock_user_model.mfa_enabled = True
        backup_code = "ABC123DEF456"
        hashed_code = hashlib.sha256(backup_code.encode()).hexdigest()
        mock_user_model.mfa_backup_codes = [hashed_code]
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import verify_mfa_backup_code, MFABackupCodeVerifyRequest

        request = MFABackupCodeVerifyRequest(code=backup_code)

        result = await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert "Backup code verified" in result.message

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_mfa_backup_code_invalid(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code verification with invalid code."""
        mock_user_model.mfa_enabled = True
        mock_user_model.mfa_backup_codes = ["hash1", "hash2"]
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import verify_mfa_backup_code, MFABackupCodeVerifyRequest

        request = MFABackupCodeVerifyRequest(code="WRONGCODE")

        with pytest.raises(HTTPException) as exc_info:
            await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_regenerate_mfa_backup_codes_success(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test successful MFA backup code regeneration."""
        mock_user_model.mfa_enabled = True
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import regenerate_mfa_backup_codes

        result = await regenerate_mfa_backup_codes(mock_db, mock_current_user)

        assert len(result.backup_codes) == 10
        assert "Backup codes regenerated" in result.message


class TestUserDeletion:
    """Tests for user deletion endpoint."""

    @patch("app.routes.users.get_user_management_service")
    async def test_delete_user_success(self, mock_get_service, mock_db):
        """Test successful user deletion."""
        mock_service = MagicMock()
        mock_service.delete_user.return_value = True
        mock_get_service.return_value = mock_service

        from app.routes.users import delete_user

        result = await delete_user("user123", mock_db)

        assert result is None
        mock_service.delete_user.assert_called_once_with("user123")

    @patch("app.routes.users.get_user_management_service")
    async def test_delete_user_not_found(self, mock_get_service, mock_db):
        """Test deleting non-existent user."""
        mock_service = MagicMock()
        mock_service.delete_user.return_value = False
        mock_get_service.return_value = mock_service

        from app.routes.users import delete_user

        with pytest.raises(HTTPException) as exc_info:
            await delete_user("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.users.get_user_management_service")
    async def test_register_user_internal_error(self, mock_get_service, mock_db):
        """Test registration with internal error."""
        mock_service = MagicMock()
        mock_service.create_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import register_user, UserCreateRequest

        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_user(request, mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_email_expired_token(self, mock_get_service, mock_db, mock_user_model):
        """Test email verification with expired token."""
        mock_user_model.email_verification_token = "expired_token"
        mock_user_model.email_verification_expires_at = datetime.now(timezone.utc) - timedelta(
            hours=1
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_model

        from app.routes.users import verify_email

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("expired_token", mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_email_db_error(self, mock_get_service, mock_db, mock_user_model):
        """Test email verification with database error."""
        mock_user_model.email_verification_token = "valid_token"
        mock_user_model.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=1
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.commit.side_effect = Exception("Database error")

        from app.routes.users import verify_email

        with pytest.raises(HTTPException) as exc_info:
            await verify_email("valid_token", mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_create_default_user_success(self, mock_get_service, mock_db, mock_user_model):
        """Test successful default user creation."""
        mock_service = MagicMock()
        mock_service.create_default_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import create_default_user

        result = await create_default_user(mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"
        assert "Default user created" in result.message

    @patch("app.routes.users.get_user_management_service")
    async def test_create_default_user_error(self, mock_get_service, mock_db):
        """Test default user creation with error."""
        mock_service = MagicMock()
        mock_service.create_default_user.side_effect = Exception("Creation error")
        mock_get_service.return_value = mock_service

        from app.routes.users import create_default_user

        with pytest.raises(HTTPException) as exc_info:
            await create_default_user(mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    async def test_list_users_invalid_per_page(self, mock_get_service, mock_db):
        """Test user listing with invalid per_page."""
        from app.routes.users import list_users

        with pytest.raises(HTTPException) as exc_info:
            await list_users(page=1, per_page=101, active_only=True, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_list_users_with_inactive(self, mock_get_service, mock_db, mock_user_model):
        """Test user listing including inactive users."""
        mock_service = MagicMock()
        mock_service.list_users.return_value = [mock_user_model]
        mock_service.get_user_stats.return_value = {
            "total_users": 1,
            "active_users": 1,
            "inactive_users": 0,
            "role_counts": {"viewer": 1},
            "total_sessions": 0,
            "active_sessions": 0,
        }
        mock_get_service.return_value = mock_service

        from app.routes.users import list_users

        result = await list_users(page=1, per_page=10, active_only=False, db=mock_db)

        assert len(result.users) == 1
        assert result.pagination.total == 1

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_partial_update_user_as_owner(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test partial user update as owner."""
        mock_has_permission.return_value = False
        mock_service = MagicMock()
        mock_service.update_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import partial_update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=None, password=None, is_active=None
        )

        result = await partial_update_user("user123", request, mock_db, mock_current_user)

        assert result.email == "newemail@example.com"
        mock_service.update_user.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_partial_update_user_not_found(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test partial user update when user not found."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.update_user.side_effect = ValueError("User not found")
        mock_get_service.return_value = mock_service

        from app.routes.users import partial_update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=["admin"], password=None, is_active=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await partial_update_user("user123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_update_user_as_owner(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test full user update as owner."""
        mock_has_permission.return_value = False
        mock_service = MagicMock()
        mock_service.update_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=None, password=None, is_active=None
        )

        result = await update_user("user123", request, mock_db, mock_current_user)

        assert result.email == "newemail@example.com"

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_update_user_not_found(
        self, mock_has_permission, mock_get_service, mock_db, mock_admin_user
    ):
        """Test update user when user not found."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.update_user.side_effect = UserNotFoundError("user123")
        mock_get_service.return_value = mock_service

        from app.routes.users import update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=["admin"], password=None, is_active=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_user("user123", request, mock_db, mock_admin_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_update_user_internal_error(
        self, mock_has_permission, mock_get_service, mock_db, mock_admin_user
    ):
        """Test update user with internal error."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.update_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import update_user, UserUpdateRequest

        request = UserUpdateRequest(
            email="newemail@example.com", roles=["admin"], password=None, is_active=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_user("user123", request, mock_db, mock_admin_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    async def test_request_password_reset_internal_error(self, mock_get_service, mock_db):
        """Test password reset request with internal error."""
        mock_service = MagicMock()
        mock_service.request_password_reset.side_effect = Exception("Email error")
        mock_get_service.return_value = mock_service

        from app.routes.users import request_password_reset, PasswordResetEmailRequest

        request = PasswordResetEmailRequest(email="test@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await request_password_reset(request, mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    async def test_confirm_password_reset_invalid_token(self, mock_get_service, mock_db):
        """Test password reset confirmation with invalid token."""
        from app.exceptions import ValidationError

        mock_service = MagicMock()
        mock_service.confirm_password_reset.side_effect = ValidationError("Invalid token")
        mock_get_service.return_value = mock_service

        from app.routes.users import confirm_password_reset, PasswordResetConfirmRequest

        request = PasswordResetConfirmRequest(token="invalid_token", new_password="N3wS3cur3!")

        with pytest.raises(HTTPException) as exc_info:
            await confirm_password_reset(request, mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.users.get_user_management_service")
    async def test_confirm_password_reset_internal_error(self, mock_get_service, mock_db):
        """Test password reset confirmation with internal error."""
        mock_service = MagicMock()
        mock_service.confirm_password_reset.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import confirm_password_reset, PasswordResetConfirmRequest

        request = PasswordResetConfirmRequest(token="valid_token", new_password="N3wS3cur3!")

        with pytest.raises(HTTPException) as exc_info:
            await confirm_password_reset(request, mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_reset_user_password_unauthorized(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test user password reset when unauthorized."""
        mock_has_permission.return_value = False
        mock_get_service.return_value = MagicMock()

        from app.routes.users import reset_user_password, PasswordResetRequest

        request = PasswordResetRequest(new_password="N3wS3cur3!")

        with pytest.raises(HTTPException) as exc_info:
            await reset_user_password("otheruser", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_reset_user_password_not_found(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test user password reset when user not found."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.reset_password.side_effect = UserNotFoundError("user123")
        mock_get_service.return_value = mock_service

        from app.routes.users import reset_user_password, PasswordResetRequest

        request = PasswordResetRequest(new_password="N3wS3cur3!")

        with pytest.raises(HTTPException) as exc_info:
            await reset_user_password("user123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.has_permission")
    async def test_reset_user_password_internal_error(
        self, mock_has_permission, mock_get_service, mock_db, mock_current_user
    ):
        """Test user password reset with internal error."""
        mock_has_permission.return_value = True
        mock_service = MagicMock()
        mock_service.reset_password.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import reset_user_password, PasswordResetRequest

        request = PasswordResetRequest(new_password="N3wS3cur3!")

        with pytest.raises(HTTPException) as exc_info:
            await reset_user_password("user123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enroll_mfa_internal_error(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user
    ):
        """Test MFA enrollment with internal error."""
        mock_service = MagicMock()
        mock_service.get_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import enroll_mfa

        with pytest.raises(HTTPException) as exc_info:
            await enroll_mfa(mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enable_mfa_not_enrolled(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA enable when not enrolled."""
        mock_user_model.mfa_secret = None
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import enable_mfa, MFAEnableRequest

        request = MFAEnableRequest(code="123456")

        with pytest.raises(HTTPException) as exc_info:
            await enable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "MFA not enrolled" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_enable_mfa_internal_error(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA enable with internal error."""
        mock_user_model.mfa_secret = "JBSWY3DPEHPK3PXP"
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import enable_mfa, MFAEnableRequest

        request = MFAEnableRequest(code="123456")

        with pytest.raises(HTTPException) as exc_info:
            await enable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_disable_mfa_not_enabled(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA disable when not enabled."""
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import disable_mfa, MFADisableRequest

        request = MFADisableRequest(password="Curr3ntP@ss!")

        with pytest.raises(HTTPException) as exc_info:
            await disable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "MFA is not enabled" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_disable_mfa_invalid_password(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA disable with invalid password."""
        mock_user_model.mfa_enabled = True
        mock_user_model.password_hash = "hashed_password"
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        mock_auth_manager = MagicMock()
        mock_auth_manager.verify_password.return_value = False
        mock_auth_manager_class.return_value = mock_auth_manager

        from app.routes.users import disable_mfa, MFADisableRequest

        request = MFADisableRequest(password="WrongP@ss!")

        with pytest.raises(HTTPException) as exc_info:
            await disable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid password" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    @patch("app.routes.users.AuthManager")
    async def test_disable_mfa_internal_error(
        self, mock_auth_manager_class, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA disable with internal error."""
        mock_user_model.mfa_enabled = True
        mock_user_model.password_hash = "hashed_password"
        mock_service = MagicMock()
        mock_service.get_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import disable_mfa, MFADisableRequest

        request = MFADisableRequest(password="Curr3ntP@ss!")

        with pytest.raises(HTTPException) as exc_info:
            await disable_mfa(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_mfa_backup_code_not_enabled(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code verification when MFA not enabled."""
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import verify_mfa_backup_code, MFABackupCodeVerifyRequest

        request = MFABackupCodeVerifyRequest(code="ABC123")

        with pytest.raises(HTTPException) as exc_info:
            await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "MFA is not enabled" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_mfa_backup_code_no_codes(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code verification when no backup codes."""
        mock_user_model.mfa_enabled = True
        mock_user_model.mfa_backup_codes = None
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import verify_mfa_backup_code, MFABackupCodeVerifyRequest

        request = MFABackupCodeVerifyRequest(code="ABC123")

        with pytest.raises(HTTPException) as exc_info:
            await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "No backup codes" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    async def test_verify_mfa_backup_code_internal_error(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code verification with internal error."""
        mock_user_model.mfa_enabled = True
        mock_user_model.mfa_backup_codes = ["hash1"]
        mock_service = MagicMock()
        mock_service.get_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import verify_mfa_backup_code, MFABackupCodeVerifyRequest

        request = MFABackupCodeVerifyRequest(code="ABC123")

        with pytest.raises(HTTPException) as exc_info:
            await verify_mfa_backup_code(request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_regenerate_mfa_backup_codes_not_enabled(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code regeneration when not enabled."""
        mock_user_model.mfa_enabled = False
        mock_service = MagicMock()
        mock_service.get_user.return_value = mock_user_model
        mock_get_service.return_value = mock_service

        from app.routes.users import regenerate_mfa_backup_codes

        with pytest.raises(HTTPException) as exc_info:
            await regenerate_mfa_backup_codes(mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "MFA must be enabled" in exc_info.value.detail

    @patch("app.routes.users.get_user_management_service")
    async def test_regenerate_mfa_backup_codes_internal_error(
        self, mock_get_service, mock_db, mock_current_user, mock_user_model
    ):
        """Test MFA backup code regeneration with internal error."""
        mock_user_model.mfa_enabled = True
        mock_service = MagicMock()
        mock_service.get_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import regenerate_mfa_backup_codes

        with pytest.raises(HTTPException) as exc_info:
            await regenerate_mfa_backup_codes(mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    @patch("app.routes.users.get_user_management_service")
    async def test_delete_user_internal_error(self, mock_get_service, mock_db):
        """Test user deletion with internal error."""
        mock_service = MagicMock()
        mock_service.delete_user.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        from app.routes.users import delete_user

        with pytest.raises(HTTPException) as exc_info:
            await delete_user("user123", mock_db)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
