"""Unit tests for UserManagementService.

Covers user CRUD operations, role management, and user validation.
Requirements: 2.9
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import IntegrityError
from app.services.user_management import UserManagementService
from app.exceptions import UserNotFoundError, ValidationError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager."""
    with patch("app.services.user_management.AuthManager") as mock:
        manager = mock.return_value
        manager.hash_password = MagicMock(return_value="hashed_password")
        manager.revoke_all_user_tokens = MagicMock(return_value=1)
        yield manager


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
    user.is_deleted = False
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.last_login = None
    user.mfa_secret = None
    user.mfa_enabled = False
    user.mfa_backup_codes = None
    user.email_verification_token = None
    user.email_verification_expires_at = None
    user.password_reset_token = None
    user.password_reset_expires_at = None
    return user


class TestPasswordValidation:
    """Tests for password validation."""

    def test_validate_password_complexity_success(self, mock_db, mock_auth_manager):
        """Test successful password validation."""
        service = UserManagementService(mock_db)

        # Should not raise
        service._validate_password_complexity("SecurePass123!")

    def test_validate_password_complexity_too_short(self, mock_db, mock_auth_manager):
        """Test password validation with too short password."""
        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("Short1!")

        assert "at least 12 characters" in str(exc_info.value)

    def test_validate_password_complexity_no_uppercase(self, mock_db, mock_auth_manager):
        """Test password validation without uppercase."""
        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("lowercase123!")

        assert "uppercase" in str(exc_info.value)

    def test_validate_password_complexity_no_lowercase(self, mock_db, mock_auth_manager):
        """Test password validation without lowercase."""
        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("UPPERCASE123!")

        assert "lowercase" in str(exc_info.value)

    def test_validate_password_complexity_no_digit(self, mock_db, mock_auth_manager):
        """Test password validation without digit."""
        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("NoDigitsExtraChars!")

        assert "digit" in str(exc_info.value)

    def test_validate_password_complexity_no_special(self, mock_db, mock_auth_manager):
        """Test password validation without special character."""
        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service._validate_password_complexity("NoSpecial123")

        assert "special character" in str(exc_info.value)


class TestCreateUser:
    """Tests for create_user method."""

    @patch("app.services.user_management.settings")
    def test_create_user_success(self, mock_settings, mock_db, mock_auth_manager, mock_user_model):
        """Test successful user creation."""
        mock_settings.smtp_server = None  # No SMTP - skip email sending
        mock_settings.require_email_verification = False  # Auto-activate
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user_model.user_id = "user123"

        with patch("app.services.user_management.User", return_value=mock_user_model):
            service = UserManagementService(mock_db)

            user = service.create_user("testuser", "test@example.com", "SecurePass123!")

            assert user.user_id == "user123"
            assert user.username == "testuser"
            assert user.email == "test@example.com"
            mock_db.commit.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_create_user_default_roles(
        self, mock_settings, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test user creation with default roles."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.require_email_verification = False
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user_model.user_id = "user123"
        mock_user_model.roles = ["viewer"]

        with patch("app.services.user_management.User", return_value=mock_user_model):
            service = UserManagementService(mock_db)

            user = service.create_user("testuser", "test@example.com", "SecurePass123!")

            assert user.roles == ["viewer"]

    @patch("app.services.user_management.settings")
    def test_create_user_with_roles(
        self, mock_settings, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test user creation with custom roles."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.require_email_verification = False
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user_model.user_id = "user123"
        mock_user_model.roles = ["admin"]

        with patch("app.services.user_management.User", return_value=mock_user_model):
            service = UserManagementService(mock_db)

            user = service.create_user(
                "testuser", "test@example.com", "SecurePass123!", roles=["admin"]
            )

            assert user.roles == ["admin"]

    @patch("app.services.user_management.settings")
    def test_create_user_duplicate(self, mock_settings, mock_db, mock_auth_manager):
        """Test user creation with duplicate username/email."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.require_email_verification = False
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.side_effect = IntegrityError("INSERT", {}, Exception("Duplicate"))

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.create_user("existinguser", "test@example.com", "SecurePass123!")

        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_create_user_db_error(self, mock_settings, mock_db, mock_auth_manager):
        """Test user creation with database error."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.require_email_verification = False
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.create_user("testuser", "test@example.com", "SecurePass123!")

        assert "Database error" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_create_user_no_smtp(self, mock_settings, mock_db, mock_auth_manager, mock_user_model):
        """Test user creation without SMTP."""
        mock_settings.smtp_server = None
        mock_settings.require_email_verification = True
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.add.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_user_model.user_id = "user123"
        mock_user_model.is_active = False

        with patch("app.services.user_management.User", return_value=mock_user_model):
            service = UserManagementService(mock_db)

            user = service.create_user("testuser", "test@example.com", "SecurePass123!")

            assert user.is_active is False  # type: ignore[comparison-overlap]  # Not activated without SMTP


class TestCreateDefaultUser:
    """Tests for create_default_user method."""

    def test_create_default_user_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful default user creation."""
        mock_db.add.return_value = None
        mock_user_model.user_id = "user123"
        mock_user_model.username = "admin"
        mock_user_model.email = "admin@example.com"
        mock_user_model.roles = ["user"]
        mock_user_model.is_active = True
        mock_user_model.email_verification_token = None

        service = UserManagementService(mock_db)

        # Patch User class to return our mock_user_model
        with patch("app.services.user_management.User", return_value=mock_user_model):
            user = service.create_default_user("admin", "admin@example.com", "SecurePass123!")

            assert user.user_id == "user123"
            assert user.username == "admin"
            assert user.is_active is True  # type: ignore[comparison-overlap]  # Pre-activated
            assert user.email_verification_token is None

    def test_create_default_user_duplicate(self, mock_db, mock_auth_manager):
        """Test default user creation with duplicate."""
        mock_db.add.side_effect = IntegrityError("INSERT", {}, Exception("Duplicate"))

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.create_default_user("admin", "admin@example.com", "SecurePass123!")

        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    def test_create_default_user_error(self, mock_db, mock_auth_manager):
        """Test default user creation with error."""
        mock_db.add.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.create_default_user("admin", "admin@example.com", "SecurePass123!")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()


class TestListUsers:
    """Tests for list_users method."""

    def test_list_users_all(self, mock_db, mock_auth_manager, mock_user_model):
        """Test listing all users."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_user_model]
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        users = service.list_users(skip=0, limit=10, active_only=False)

        assert len(users) == 1
        assert users[0].user_id == "user123"

    def test_list_users_active_only(self, mock_db, mock_auth_manager, mock_user_model):
        """Test listing active users only."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_user_model]
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        users = service.list_users(skip=0, limit=10, active_only=True)

        assert len(users) == 1

    def test_list_users_pagination(self, mock_db, mock_auth_manager, mock_user_model):
        """Test user listing with pagination."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_user_model]
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        users = service.list_users(skip=10, limit=10, active_only=True)

        mock_query.offset.assert_called_once_with(10)
        mock_query.limit.assert_called_once_with(10)

    def test_list_users_result_length_le_limit(self, mock_db, mock_auth_manager, mock_user_model):
        """Test that list_users returns at most `limit` users (pagination invariant)."""
        limit = 3
        users_returned = [mock_user_model] * 2  # fewer than limit

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = users_returned
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        users = service.list_users(skip=0, limit=limit, active_only=False)

        assert len(users) <= limit

    def test_list_users_empty(self, mock_db, mock_auth_manager):
        """Test list_users returns empty list when no users match."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        users = service.list_users(skip=0, limit=10)

        assert users == []
        assert len(users) <= 10


class TestGetUser:
    """Tests for get_user method."""

    def test_get_user_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful user retrieval."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        user = service.get_user("user123")

        assert user.user_id == "user123"

    def test_get_user_not_found(self, mock_db, mock_auth_manager):
        """Test get_user when user not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.get_user("user123")

        assert "not found" in str(exc_info.value).lower()

    def test_get_user_deleted(self, mock_db, mock_auth_manager, mock_user_model):
        """Test get_user when user is deleted."""
        # When a user is deleted, the query should return None because of the filter
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.get_user("user123")

        assert "not found" in str(exc_info.value).lower()


class TestUpdateUser:
    """Tests for update_user method."""

    def test_update_user_email(self, mock_db, mock_auth_manager, mock_user_model):
        """Test updating user email."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        user = service.update_user("user123", email="newemail@example.com")

        assert user.email == "newemail@example.com"
        mock_db.commit.assert_called_once()

    def test_update_user_password(self, mock_db, mock_auth_manager, mock_user_model):
        """Test updating user password."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        user = service.update_user("user123", password="NewSecure123!")

        assert user.password_hash == "hashed_password"
        mock_db.commit.assert_called_once()

    def test_update_user_roles(self, mock_db, mock_auth_manager, mock_user_model):
        """Test updating user roles."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        user = service.update_user("user123", roles=["admin"])

        assert user.roles == ["admin"]
        mock_db.commit.assert_called_once()

    def test_update_user_is_active(self, mock_db, mock_auth_manager, mock_user_model):
        """Test updating user active status."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        user = service.update_user("user123", is_active=False)

        assert user.is_active is False  # type: ignore[comparison-overlap]
        mock_db.commit.assert_called_once()

    def test_update_user_not_found(self, mock_db, mock_auth_manager):
        """Test update_user when user not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.update_user("user123", email="newemail@example.com")

        assert "not found" in str(exc_info.value).lower()

    def test_update_user_duplicate_email(self, mock_db, mock_auth_manager, mock_user_model):
        """Test update_user with duplicate email."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = IntegrityError("UPDATE", {}, Exception("Duplicate"))

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.update_user("user123", email="existing@example.com")

        assert "already exists" in str(exc_info.value)
        mock_db.rollback.assert_called_once()

    def test_update_user_db_error(self, mock_db, mock_auth_manager, mock_user_model):
        """Test update_user with database error."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.update_user("user123", email="newemail@example.com")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()


class TestRequestPasswordReset:
    """Tests for request_password_reset method."""

    def test_request_password_reset_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful password reset request."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        with patch.object(service, "_send_password_reset_email") as mock_send:
            service.request_password_reset("test@example.com")

        assert mock_user_model.password_reset_token is not None
        assert mock_user_model.password_reset_expires_at is not None
        mock_db.commit.assert_called_once()

    def test_request_password_reset_not_found(self, mock_db, mock_auth_manager):
        """Test password reset request when user not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.request_password_reset("notfound@example.com")

        assert "not found" in str(exc_info.value).lower()

    @patch("app.services.user_management.settings")
    def test_request_password_reset_send_email(
        self, mock_settings, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test password reset request sends email."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        with patch.object(service, "_send_password_reset_email") as mock_send:
            service.request_password_reset("test@example.com")
            mock_send.assert_called_once()

    def test_request_password_reset_error(self, mock_db, mock_auth_manager, mock_user_model):
        """Test password reset request with error."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.request_password_reset("test@example.com")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()


class TestConfirmPasswordReset:
    """Tests for confirm_password_reset method."""

    def test_confirm_password_reset_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful password reset confirmation."""
        mock_user_model.password_reset_token = "hashed_token"
        mock_user_model.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        service.confirm_password_reset("valid_token", "NewSecure123!")

        assert mock_user_model.password_hash == "hashed_password"
        assert mock_user_model.password_reset_token is None
        mock_db.commit.assert_called_once()

    def test_confirm_password_reset_invalid_token(self, mock_db, mock_auth_manager):
        """Test password reset confirmation with invalid token."""
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.confirm_password_reset("invalid_token", "NewSecure123!")

        assert "Invalid or expired" in str(exc_info.value)

    def test_confirm_password_reset_expired_token(
        self, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test password reset confirmation with expired token."""
        mock_user_model.password_reset_token = "hashed_token"
        mock_user_model.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.confirm_password_reset("expired_token", "NewSecure123!")

        assert "Invalid or expired" in str(exc_info.value)

    def test_confirm_password_reset_invalid_password(
        self, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test password reset confirmation with invalid password."""
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        with pytest.raises(ValidationError) as exc_info:
            service.confirm_password_reset("valid_token", "short")

        assert "Password must be" in str(exc_info.value)

    def test_confirm_password_reset_error(self, mock_db, mock_auth_manager, mock_user_model):
        """Test password reset confirmation with error."""
        mock_user_model.password_reset_token = "hashed_token"
        mock_user_model.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.confirm_password_reset("valid_token", "NewSecure123!")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()

    def test_confirm_password_reset_token_revocation_failure(
        self, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test password reset confirmation when token revocation fails (lines 351-352)."""
        mock_user_model.password_reset_token = "hashed_token"
        mock_user_model.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        # Token revocation raises but password reset should still succeed
        mock_auth_manager.revoke_all_user_tokens.side_effect = Exception("Revocation failed")

        service = UserManagementService(mock_db)

        # Should not raise — revocation failure is swallowed
        service.confirm_password_reset("valid_token", "NewSecure123!")

        mock_db.commit.assert_called_once()


class TestResetPassword:
    """Tests for reset_password method."""

    def test_reset_password_with_new_password(self, mock_db, mock_auth_manager, mock_user_model):
        """Test reset password with new password."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        result = service.reset_password("user123", "NewSecure123!")

        assert result == "Password reset successfully"
        assert mock_user_model.password_hash == "hashed_password"
        mock_db.commit.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_reset_password_send_token(
        self, mock_settings, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test reset password sends token when no password provided."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)
        with patch.object(service, "_send_password_reset_email") as mock_send:
            result = service.reset_password("user123")

            assert "reset initiated" in result.lower()
            mock_send.assert_called_once()

    def test_reset_password_not_found(self, mock_db, mock_auth_manager):
        """Test reset password when user not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.reset_password("user123", "NewSecure123!")

        assert "not found" in str(exc_info.value).lower()

    def test_reset_password_error(self, mock_db, mock_auth_manager, mock_user_model):
        """Test reset password with error."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.reset_password("user123", "NewSecure123!")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()

    def test_reset_password_revocation_failure(self, mock_db, mock_auth_manager, mock_user_model):
        """Test reset password when token revocation fails (lines 447-448)."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        # Revocation raises but password reset should still succeed
        mock_auth_manager.revoke_all_user_tokens.side_effect = Exception("Revocation failed")

        service = UserManagementService(mock_db)

        result = service.reset_password("user123", "NewSecure123!")

        assert result == "Password reset successfully"
        mock_db.commit.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_reset_password_no_password_commit_error(
        self, mock_settings, mock_db, mock_auth_manager, mock_user_model
    ):
        """Test reset password without new_password when commit fails (lines 475-478)."""
        mock_settings.smtp_server = None
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.reset_password("user123")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()


class TestSendPasswordResetEmail:
    """Tests for _send_password_reset_email method."""

    @patch("app.services.user_management.settings")
    def test_send_password_reset_email_no_smtp(self, mock_settings, mock_db, mock_auth_manager):
        """Test send password reset email when SMTP not configured raises ServiceUnavailableError."""
        from app.exceptions import ServiceUnavailableError

        mock_settings.smtp_server = None

        service = UserManagementService(mock_db)

        with pytest.raises(ServiceUnavailableError):
            service._send_password_reset_email("test@example.com", "reset_token")

    @patch("app.services.user_management.settings")
    @patch("smtplib.SMTP")
    @patch("ssl.create_default_context")
    def test_send_password_reset_email_success(
        self, mock_ssl, mock_smtp, mock_settings, mock_db, mock_auth_manager
    ):
        """Test successful password reset email sending."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.base_url = "https://example.com"

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        service = UserManagementService(mock_db)

        service._send_password_reset_email("test@example.com", "reset_token")

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.services.user_management.settings")
    @patch("smtplib.SMTP")
    @patch("ssl.create_default_context")
    def test_send_password_reset_email_error(
        self, mock_ssl, mock_smtp, mock_settings, mock_db, mock_auth_manager
    ):
        """Test password reset email sending with SMTP error raises ServiceUnavailableError."""
        from app.exceptions import ServiceUnavailableError

        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.base_url = "https://example.com"

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.sendmail.side_effect = Exception("SMTP error")

        service = UserManagementService(mock_db)

        with pytest.raises(ServiceUnavailableError):
            service._send_password_reset_email("test@example.com", "reset_token")


class TestSendVerificationEmail:
    """Tests for _send_verification_email method."""

    @patch("app.services.user_management.settings")
    def test_send_verification_email_no_smtp(self, mock_settings, mock_db, mock_auth_manager):
        """Test send verification email when SMTP not configured raises ServiceUnavailableError."""
        from app.exceptions import ServiceUnavailableError

        mock_settings.smtp_server = None

        service = UserManagementService(mock_db)

        with pytest.raises(ServiceUnavailableError):
            service._send_verification_email("test@example.com", "verification_token")

    @patch("app.services.user_management.settings")
    @patch("smtplib.SMTP")
    @patch("ssl.create_default_context")
    def test_send_verification_email_success(
        self, mock_ssl, mock_smtp, mock_settings, mock_db, mock_auth_manager
    ):
        """Test successful verification email sending."""
        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_settings.smtp_username = None
        mock_settings.smtp_password = None

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        service = UserManagementService(mock_db)

        service._send_verification_email("test@example.com", "verification_token")

        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.services.user_management.settings")
    @patch("smtplib.SMTP")
    @patch("ssl.create_default_context")
    def test_send_verification_email_error(
        self, mock_ssl, mock_smtp, mock_settings, mock_db, mock_auth_manager
    ):
        """Test verification email sending with SMTP error raises ServiceUnavailableError."""
        from app.exceptions import ServiceUnavailableError

        mock_settings.smtp_server = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.base_url = "https://example.com"
        mock_settings.smtp_username = None
        mock_settings.smtp_password = None

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.sendmail.side_effect = Exception("SMTP error")

        service = UserManagementService(mock_db)

        with pytest.raises(ServiceUnavailableError):
            service._send_verification_email("test@example.com", "verification_token")


class TestDeleteUser:
    """Tests for delete_user method."""

    def test_delete_user_success(self, mock_db, mock_auth_manager, mock_user_model):
        """Test successful user deletion."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )

        service = UserManagementService(mock_db)

        result = service.delete_user("user123")

        assert result is True
        assert mock_user_model.is_deleted is True
        mock_db.commit.assert_called_once()

    def test_delete_user_not_found(self, mock_db, mock_auth_manager):
        """Test delete user when user not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        service = UserManagementService(mock_db)

        with pytest.raises(UserNotFoundError) as exc_info:
            service.delete_user("user123")

        assert "not found" in str(exc_info.value).lower()

    def test_delete_user_error(self, mock_db, mock_auth_manager, mock_user_model):
        """Test delete user with error."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user_model
        )
        mock_db.commit.side_effect = Exception("Database error")

        service = UserManagementService(mock_db)

        with pytest.raises(Exception) as exc_info:
            service.delete_user("user123")

        assert "Database error" in str(exc_info)
        mock_db.rollback.assert_called_once()


class TestGetUserStats:
    """Tests for get_user_stats method."""

    def test_get_user_stats(self, mock_db, mock_user_model):
        """Test getting user statistics."""
        # Setup mocks for multiple queries
        mock_queries = []
        for _ in range(5):
            mq = MagicMock()
            mq.filter.return_value = mq
            mock_queries.append(mq)

        # 1. total_users count
        mock_queries[0].count.return_value = 5
        # 2. active_users count
        mock_queries[1].count.return_value = 3
        # 3. users for role counts
        mock_queries[2].all.return_value = [mock_user_model]
        # 4. total_sessions count
        mock_queries[3].count.return_value = 10
        # 5. active_sessions count
        mock_queries[4].count.return_value = 5

        mock_db.query.side_effect = mock_queries

        service = UserManagementService(mock_db)
        stats = service.get_user_stats()

        assert stats["total_users"] == 5
        assert stats["active_users"] == 3
        assert stats["inactive_users"] == 2
        assert "role_counts" in stats
        assert stats["total_sessions"] == 10
        assert stats["active_sessions"] == 5

    def test_get_user_stats_empty(self, mock_db):
        """Test getting user stats when no users."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        service = UserManagementService(mock_db)
        stats = service.get_user_stats()

        assert stats["total_users"] == 0
        assert stats["active_users"] == 0
        assert stats["inactive_users"] == 0
        assert stats["role_counts"] == {}


class TestGetUserManagementService:
    """Tests for get_user_management_service function."""

    def test_get_user_management_service(self, mock_db):
        """Test getting user management service instance."""
        from app.services.user_management import get_user_management_service

        service = get_user_management_service(mock_db)

        assert isinstance(service, UserManagementService)
        assert service.db == mock_db
