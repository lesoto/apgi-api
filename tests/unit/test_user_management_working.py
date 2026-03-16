"""
Working tests for user management service to achieve coverage.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.user_management import UserManagementService
from app.exceptions import UserNotFoundError, ValidationError
from app.database.models import User


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.commit = Mock()
    db.rollback = Mock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager."""
    manager = Mock()
    manager.hash_password = Mock(return_value="hashed_password")
    manager.revoke_all_user_tokens = Mock()
    return manager


@pytest.fixture
def mock_user_model():
    """Mock user model."""
    user = Mock()
    user.user_id = "user123"
    user.username = "testuser"
    user.email = "test@example.com"
    user.password_hash = "hashed_password"
    user.roles = ["viewer"]
    user.is_active = True
    user.is_deleted = False
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.last_login = None
    user.mfa_secret = None
    user.mfa_enabled = False
    user.mfa_backup_codes = None
    return user


class TestUserManagementService:
    """Test UserManagementService class."""

    def test_init(self, mock_db, mock_auth_manager):
        """Test service initialization."""
        service = UserManagementService(mock_db)
        assert service.db == mock_db
        assert service.auth_manager == mock_auth_manager


class TestPasswordValidation:
    """Test password validation."""

    def test_validate_password_complexity_success(self):
        """Test successful password validation."""
        service = UserManagementService(Mock())

        # Valid password with all required characters
        service._validate_password_complexity("SecurePass123!")

    def test_validate_password_complexity_too_short(self):
        """Test password validation with too short password."""
        service = UserManagementService(Mock())

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("short")
        assert "at least 12 characters" in str(exc_info.value)

    def test_validate_password_complexity_no_uppercase(self):
        """Test password validation without uppercase."""
        service = UserManagementService(Mock())

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("lowercase123!")
        assert "uppercase" in str(exc_info.value)

    def test_validate_password_complexity_no_lowercase(self):
        """Test password validation without lowercase."""
        service = UserManagementService(Mock())

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("UPPERCASE123!")
        assert "lowercase" in str(exc_info.value)

    def test_validate_password_complexity_no_digit(self):
        """Test password validation without digit."""
        service = UserManagementService(Mock())

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("NoDigits!")
        assert "digit" in str(exc_info.value)

    def test_validate_password_complexity_no_special(self):
        """Test password validation without special character."""
        service = UserManagementService(Mock())

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("NoSpecialChars")
        assert "special character" in str(exc_info.value)


class TestCreateUser:
    """Test user creation."""

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.secrets")
    def test_create_user_success(
        self, mock_settings, mock_secrets, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test successful user creation."""
        # Mock settings
        mock_settings.require_email_verification = False
        mock_settings.smtp_server = None
        mock_settings.base_url = "http://example.com"
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_username = None
        mock_settings.smtp_password = None
        mock_settings.smtp_port = 587

        # Mock secrets
        mock_secrets.token_urlsafe.return_value = "verification_token"

        service = UserManagementService(mock_db)

        with patch.object(service, "_send_verification_email"):
            result = service.create_user(
                username="testuser", email="test@example.com", password="SecurePass123!"
            )

            assert result.username == "testuser"
            assert result.email == "test@example.com"
            assert result.roles == ["viewer"]
            assert result.is_active is True  # No email verification required
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.secrets")
    def test_create_user_with_roles(
        self, mock_settings, mock_secrets, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test user creation with custom roles."""
        mock_settings.require_email_verification = False
        mock_settings.smtp_server = None
        mock_secrets.token_urlsafe.return_value = "verification_token"

        service = UserManagementService(mock_db)

        with patch.object(service, "_send_verification_email"):
            result = service.create_user(
                username="adminuser",
                email="admin@example.com",
                password="SecurePass123!",
                roles=["admin", "viewer"],
            )

            assert result.roles == ["admin", "viewer"]

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.secrets")
    def test_create_user_duplicate(
        self, mock_settings, mock_secrets, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test user creation with duplicate username/email."""
        mock_settings.require_email_verification = False
        mock_settings.smtp_server = None
        mock_secrets.token_urlsafe.return_value = "verification_token"

        service = UserManagementService(mock_db)
        mock_db.add.side_effect = Exception("Duplicate entry")

        with pytest.raises(ValidationError) as exc_info:
            service.create_user(
                username="existinguser", email="existing@example.com", password="SecurePass123!"
            )
        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.secrets")
    def test_create_user_db_error(
        self, mock_settings, mock_secrets, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test user creation with database error."""
        mock_settings.require_email_verification = False
        mock_settings.smtp_server = None
        mock_secrets.token_urlsafe.return_value = "verification_token"

        service = UserManagementService(mock_db)
        mock_db.add.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            service.create_user(
                username="testuser", email="test@example.com", password="SecurePass123!"
            )
        mock_db.rollback.assert_called_once()


class TestCreateDefaultUser:
    """Test default user creation."""

    def test_create_default_user_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful default user creation."""
        service = UserManagementService(mock_db)

        result = service.create_default_user(
            username="admin", email="admin@example.com", password="SecurePass123!"
        )

        assert result.username == "admin"
        assert result.email == "admin@example.com"
        assert result.roles == ["user"]
        assert result.is_active is True
        assert result.email_verification_token is None
        assert result.email_verification_expires_at is None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_default_user_duplicate(self, mock_db, mock_auth_manager, mock_user_model):
        """Test default user creation with duplicate."""
        service = UserManagementService(mock_db)
        mock_db.add.side_effect = Exception("Duplicate entry")

        with pytest.raises(ValidationError) as exc_info:
            service.create_default_user(
                username="existing", email="existing@example.com", password="SecurePass123!"
            )
        assert "already exists" in str(exc_info.value)


class TestListUsers:
    """Test user listing."""

    def test_list_users_all(self, mock_db, mock_user_model):
        """Test listing all users."""
        service = UserManagementService(mock_db)

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_user_model
        ]
        mock_db.query.return_value = mock_query

        result = service.list_users()

        assert len(result) == 1
        mock_query.filter.assert_called_once_with(User.is_deleted.is_(False))

    def test_list_users_active_only(self, mock_db, mock_user_model):
        """Test listing only active users."""
        service = UserManagementService(mock_db)

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_user_model
        ]
        mock_db.query.return_value = mock_query

        result = service.list_users(active_only=True)

        assert len(result) == 1
        mock_query.filter.assert_called_with(User.is_deleted.is_(False))
        mock_query.filter.assert_called_with(User.is_active)

    def test_list_users_pagination(self, mock_db, mock_user_model):
        """Test user listing with pagination."""
        service = UserManagementService(mock_db)

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_user_model
        ]
        mock_db.query.return_value = mock_query

        result = service.list_users(skip=10, limit=5)

        mock_query.offset.assert_called_with(10)
        mock_query.limit.assert_called_with(5)


class TestGetUser:
    """Test user retrieval."""

    def test_get_user_success(self, mock_db, mock_user_model):
        """Test successful user retrieval."""
        service = UserManagementService(mock_db)

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        result = service.get_user("user123")

        assert result.user_id == "user123"

    def test_get_user_not_found(self, mock_db):
        """Test user retrieval when user not found."""
        service = UserManagementService(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            service.get_user("nonexistent")
        assert "not found" in str(exc_info.value)


class TestUpdateUser:
    """Test user updates."""

    def test_update_user_success(self, mock_db, mock_user_model, mock_auth_manager):
        """Test successful user update."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        result = service.update_user(
            user_id="user123",
            email="newemail@example.com",
            password="NewSecurePass123!",
            roles=["admin"],
            is_active=True,
        )

        assert result.email == "newemail@example.com"
        assert result.roles == ["admin"]
        assert result.is_active is True
        mock_db.commit.assert_called_once()

    def test_update_user_email_duplicate(self, mock_db, mock_user_model, mock_auth_manager):
        """Test user update with duplicate email."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        mock_db.commit.side_effect = Exception("Email already exists")

        with pytest.raises(ValidationError) as exc_info:
            service.update_user("user123", email="duplicate@example.com")
        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    def test_update_user_not_found(self, mock_db):
        """Test user update when user not found."""
        service = UserManagementService(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            service.update_user("nonexistent", email="new@example.com")
        assert "not found" in str(exc_info.value)


class TestPasswordReset:
    """Test password reset functionality."""

    def test_request_password_reset_success(self, mock_db, mock_user_model):
        """Test successful password reset request."""
        service = UserManagementService(mock_db)

        # Mock user lookup
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        with patch.object(service, "_send_password_reset_email"):
            service.request_password_reset("test@example.com")

        assert mock_user_model.password_reset_token is not None
        assert mock_user_model.password_reset_expires_at is not None
        mock_db.commit.assert_called_once()

    def test_request_password_reset_user_not_found(self, mock_db):
        """Test password reset when user not found."""
        service = UserManagementService(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            service.request_password_reset("nonexistent@example.com")
        assert "not found" in str(exc_info.value)

    def test_confirm_password_reset_success(self, mock_db, mock_user_model, mock_auth_manager):
        """Test successful password reset confirmation."""
        service = UserManagementService(mock_db)

        # Mock user lookup
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value = mock_query

        with patch.object(service, "_send_password_reset_email"):
            service.confirm_password_reset("valid_token", "NewSecurePass123!")

        assert mock_user_model.password_hash == "hashed_password"
        assert mock_user_model.password_reset_token is None
        mock_db.commit.assert_called_once()

    def test_confirm_password_reset_invalid_token(self, mock_db, mock_user_model):
        """Test password reset confirmation with invalid token."""
        service = UserManagementService(mock_db)

        # Mock user lookup - no matching token
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError) as exc_info:
            service.confirm_password_reset("invalid_token", "NewSecurePass123!")
        assert "Invalid or expired" in str(exc_info.value)

    def test_reset_password_with_new_password(self, mock_db, mock_user_model, mock_auth_manager):
        """Test password reset with new password."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        result = service.reset_password("user123", "NewSecurePass123!")

        assert result == "Password reset successfully"
        assert mock_user_model.password_hash == "hashed_password"
        mock_db.commit.assert_called_once()

    def test_reset_password_send_token(self, mock_db, mock_user_model):
        """Test password reset that generates and sends token."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        with patch.object(service, "_send_password_reset_email") as mock_send_email:
            result = service.reset_password("user123")

        assert result == "Password reset initiated. Check your email for the reset link."
        mock_db.commit.assert_called_once()
        mock_send_email.assert_called_once()


class TestEmailSending:
    """Test email sending functionality."""

    @patch("app.services.user_management.settings")
    def test_send_password_reset_email_no_smtp(self, mock_settings):
        """Test password reset email when SMTP not configured."""
        service = UserManagementService(Mock())

        mock_settings.smtp_server = None

        service._send_password_reset_email("test@example.com", "reset_token")

        # Should not raise exception, just log warning

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.smtplib")
    def test_send_password_reset_email_success(self, mock_settings, mock_smtplib):
        """Test successful password reset email sending."""
        service = UserManagementService(Mock())

        # Mock settings
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.base_url = "http://example.com"

        # Mock SMTP server
        mock_server = Mock()
        mock_server.starttls.return_value = Mock()
        mock_server.login.return_value = None
        mock_server.sendmail.return_value = None
        mock_server.quit.return_value = None

        service._send_password_reset_email("test@example.com", "reset_token")

        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.smtplib")
    def test_send_verification_email_no_smtp(self, mock_settings):
        """Test verification email when SMTP not configured."""
        service = UserManagementService(Mock())

        mock_settings.smtp_server = None

        service._send_verification_email("test@example.com", "verification_token")

        # Should not raise exception, just log warning

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.smtplib")
    def test_send_verification_email_success(self, mock_settings, mock_smtplib):
        """Test successful verification email sending."""
        service = UserManagementService(Mock())

        # Mock settings
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.base_url = "http://example.com"

        # Mock SMTP server
        mock_server = Mock()
        mock_server.starttls.return_value = Mock()
        mock_server.login.return_value = None
        mock_server.sendmail.return_value = None
        mock_server.quit.return_value = None

        service._send_verification_email("test@example.com", "verification_token")

        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()


class TestDeleteUser:
    """Test user deletion."""

    def test_delete_user_success(self, mock_db, mock_user_model):
        """Test successful user deletion."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user_model
        mock_db.query.return_value = mock_query

        result = service.delete_user("user123")

        assert result is True
        assert mock_user_model.is_deleted is True
        mock_db.commit.assert_called_once()

    def test_delete_user_not_found(self, mock_db):
        """Test user deletion when user not found."""
        service = UserManagementService(mock_db)

        # Mock get_user call
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            service.delete_user("nonexistent")
        assert "not found" in str(exc_info.value)


class TestGetUserStats:
    """Test user statistics."""

    def test_get_user_stats_success(self, mock_db):
        """Test successful user statistics retrieval."""
        service = UserManagementService(mock_db)

        # Mock user queries
        mock_query1 = Mock()
        mock_query1.filter.return_value.count.return_value = 10
        mock_db.query.return_value = mock_query1

        mock_query2 = Mock()
        mock_query2.filter.return_value.count.return_value = 8
        mock_db.query.return_value = mock_query2

        mock_query3 = Mock()
        mock_query3.filter.return_value.count.return_value = 5
        mock_db.query.return_value = mock_query3

        mock_query4 = Mock()
        mock_query4.filter.return_value.count.return_value = 3
        mock_db.query.return_value = mock_query4

        # Mock users for role counting
        mock_user1 = MagicMock()
        mock_user1.roles = ["viewer"]
        mock_user2 = MagicMock()
        mock_user2.roles = ["admin", "viewer"]
        mock_query5 = Mock()
        mock_query5.all.return_value = [mock_user1, mock_user2]
        mock_db.query.return_value = mock_query5

        result = service.get_user_stats()

        assert result["total_users"] == 10
        assert result["active_users"] == 8
        assert result["inactive_users"] == 2
        assert result["role_counts"] == {("admin", "viewer"): 1, ("viewer",): 1}
        assert result["total_sessions"] == 5
        assert result["active_sessions"] == 3


class TestGetUserManagementService:
    """Test user management service factory function."""

    def test_get_user_management_service(self, mock_db):
        """Test service factory function."""
        from app.services.user_management import get_user_management_service

        service = get_user_management_service(mock_db)
        assert isinstance(service, UserManagementService)
        assert service.db == mock_db
