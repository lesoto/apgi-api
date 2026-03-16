"""
Simple working tests for user management service to achieve coverage.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from app.services.user_management import UserManagementService
from app.exceptions import UserNotFoundError, ValidationError


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


class TestUserManagementService:
    """Test UserManagementService class."""

    def test_init(self, mock_db, mock_auth_manager):
        """Test service initialization."""
        service = UserManagementService(mock_db)
        assert service.db == mock_db
        assert service.auth_manager == mock_auth_manager

    def test_validate_password_complexity_success(self):
        """Test successful password validation."""
        service = UserManagementService(Mock())
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

    @patch("app.services.user_management.settings")
    @patch("app.services.user_management.secrets")
    def test_create_user_success(self, mock_settings, mock_secrets, mock_db, mock_auth_manager):
        """Test successful user creation."""
        mock_settings.require_email_verification = False
        mock_settings.smtp_server = None
        mock_secrets.token_urlsafe.return_value = "verification_token"

        service = UserManagementService(mock_db)

        with patch.object(service, "_send_verification_email"):
            result = service.create_user(
                username="testuser", email="test@example.com", password="SecurePass123!"
            )

            assert result.username == "testuser"
            assert result.email == "test@example.com"
            assert result.roles == ["viewer"]
            assert result.is_active is True
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_create_default_user_success(self, mock_db, mock_auth_manager):
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

    def test_list_users_all(self, mock_db):
        """Test listing all users."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_user
        ]
        mock_db.query.return_value = mock_query

        result = service.list_users()

        assert len(result) == 1
        mock_query.filter.assert_called_once()

    def test_get_user_success(self, mock_db):
        """Test successful user retrieval."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
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

    def test_update_user_success(self, mock_db, mock_auth_manager):
        """Test successful user update."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
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

    def test_request_password_reset_success(self, mock_db):
        """Test successful password reset request."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        with patch.object(service, "_send_password_reset_email"):
            service.request_password_reset("test@example.com")

        assert mock_user.password_reset_token is not None
        assert mock_user.password_reset_expires_at is not None
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

    def test_confirm_password_reset_success(self, mock_db, mock_auth_manager):
        """Test successful password reset confirmation."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_user
        )
        mock_db.query.return_value = mock_query

        service.confirm_password_reset("valid_token", "NewSecurePass123!")

        assert mock_user.password_hash == "hashed_password"
        assert mock_user.password_reset_token is None
        mock_db.commit.assert_called_once()

    def test_confirm_password_reset_invalid_token(self, mock_db):
        """Test password reset confirmation with invalid token."""
        service = UserManagementService(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError) as exc_info:
            service.confirm_password_reset("invalid_token", "NewSecurePass123!")
        assert "Invalid or expired" in str(exc_info.value)

    def test_reset_password_with_new_password(self, mock_db, mock_auth_manager):
        """Test password reset with new password."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.email = "test@example.com"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = service.reset_password("user123", "NewSecurePass123!")

        assert result == "Password reset successfully"
        assert mock_user.password_hash == "hashed_password"
        mock_db.commit.assert_called_once()

    def test_reset_password_send_token(self, mock_db):
        """Test password reset that generates and sends token."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.email = "test@example.com"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        with patch.object(service, "_send_password_reset_email") as mock_send_email:
            result = service.reset_password("user123")

        assert result == "Password reset initiated. Check your email for the reset link."
        mock_db.commit.assert_called_once()
        mock_send_email.assert_called_once()

    @patch("app.services.user_management.settings")
    def test_send_password_reset_email_no_smtp(self, mock_settings):
        """Test password reset email when SMTP not configured."""
        service = UserManagementService(Mock())
        mock_settings.smtp_server = None

        service._send_password_reset_email("test@example.com", "reset_token")

    @patch("app.services.user_management.settings")
    def test_send_verification_email_no_smtp(self, mock_settings):
        """Test verification email when SMTP not configured."""
        service = UserManagementService(Mock())
        mock_settings.smtp_server = None

        service._send_verification_email("test@example.com", "verification_token")

    def test_delete_user_success(self, mock_db):
        """Test successful user deletion."""
        service = UserManagementService(mock_db)

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = service.delete_user("user123")

        assert result is True
        assert mock_user.is_deleted is True
        mock_db.commit.assert_called_once()

    def test_delete_user_not_found(self, mock_db):
        """Test user deletion when user not found."""
        service = UserManagementService(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            service.delete_user("nonexistent")
        assert "not found" in str(exc_info.value)

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

    def test_get_user_management_service(self, mock_db):
        """Test service factory function."""
        from app.services.user_management import get_user_management_service

        service = get_user_management_service(mock_db)
        assert isinstance(service, UserManagementService)
        assert service.db == mock_db
