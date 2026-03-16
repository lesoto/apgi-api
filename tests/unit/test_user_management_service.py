"""Simple unit tests for user management service to achieve basic coverage.

Focuses on testing service methods and error paths without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.services.user_management import (
    UserManagementService,
    get_user_management_service,
)
from app.database.models import User
from app.exceptions import UserNotFoundError


class TestUserManagementService:
    """Test user management service."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_service(self, mock_db):
        """Mock user management service."""
        return UserManagementService(mock_db)

    def test_get_user_management_service(self, mock_db):
        """Test getting user management service instance."""
        service = get_user_management_service(mock_db)
        assert isinstance(service, UserManagementService)
        assert service.db == mock_db

    def test_validate_password_complexity_success(self, mock_service):
        """Test successful password complexity validation."""
        # Should not raise exception
        mock_service._validate_password_complexity("SecurePass123!")

    def test_validate_password_complexity_too_short(self, mock_service):
        """Test password complexity validation with too short password."""
        with pytest.raises(ValueError) as exc_info:
            mock_service._validate_password_complexity("short")
            assert "at least 8 characters" in str(exc_info.value)

    def test_validate_password_complexity_no_uppercase(self, mock_service):
        """Test password complexity validation without uppercase."""
        with pytest.raises(ValueError) as exc_info:
            mock_service._validate_password_complexity("lowercase123!")
            assert "uppercase" in str(exc_info.value)

    def test_validate_password_complexity_no_lowercase(self, mock_service):
        """Test password complexity validation without lowercase."""
        with pytest.raises(ValueError) as exc_info:
            mock_service._validate_password_complexity("UPPERCASE123!")
            assert "lowercase" in str(exc_info.value)

    def test_validate_password_complexity_no_digit(self, mock_service):
        """Test password complexity validation without digit."""
        with pytest.raises(ValueError) as exc_info:
            mock_service._validate_password_complexity("NoDigits!")
            assert "digit" in str(exc_info.value)

    def test_validate_password_complexity_no_special(self, mock_service):
        """Test password complexity validation without special character."""
        with pytest.raises(ValueError) as exc_info:
            mock_service._validate_password_complexity("NoSpecialChars123")
            assert "special character" in str(exc_info.value)

    def test_create_user_success(self, mock_service):
        """Test successful user creation."""
        # Mock database operations
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.is_verified = False
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)

        mock_service.db.add.return_value = None
        mock_service.db.commit.return_value = None
        mock_service.db.refresh.return_value = None

        with patch("app.services.user_management.secrets.token_urlsafe", return_value="token"):
            result = mock_service.create_user(
                username="testuser",
                email="test@example.com",
                password="SecurePass123!",
                roles=["user"],
            )

            assert result.user_id == "user123"
            assert result.username == "testuser"
            assert result.email == "test@example.com"
            mock_service.db.add.assert_called_once()
            mock_service.db.commit.assert_called_once()

    def test_create_user_duplicate_username(self, mock_service):
        """Test user creation with duplicate username."""
        # Mock database to raise exception for duplicate username
        mock_service.db.add.side_effect = Exception("Username already exists")

        with pytest.raises(Exception) as exc_info:
            mock_service.create_user(
                username="existinguser",
                email="test@example.com",
                password="SecurePass123!",
                roles=["user"],
            )
            assert "Username already exists" in str(exc_info.value)

    def test_create_default_user_success(self, mock_service):
        """Test successful default user creation."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.username = "admin"
        mock_user.email = "admin@example.com"
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.updated_at = datetime.now(timezone.utc)

        mock_service.db.add.return_value = None
        mock_service.db.commit.return_value = None
        mock_service.db.refresh.return_value = None

        with patch("app.services.user_management.secrets.token_urlsafe", return_value="token"):
            result = mock_service.create_default_user(
                username="admin", email="admin@example.com", password="SecurePass123!"
            )

            assert result.user_id == "user123"
            assert result.username == "admin"
            assert result.is_verified is True

    def test_list_users_success(self, mock_service):
        """Test successful user listing."""
        mock_user1 = Mock(spec=User)
        mock_user1.id = 1
        mock_user1.username = "user1"

        mock_user2 = Mock(spec=User)
        mock_user2.id = 2
        mock_user2.username = "user2"

        mock_query = Mock()
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_user1,
            mock_user2,
        ]
        mock_service.db.query.return_value = mock_query

        result = mock_service.list_users(skip=0, limit=10, active_only=True)

        assert len(result) == 2
        assert result[0].username == "user1"

    def test_list_users_include_inactive(self, mock_service):
        """Test user listing including inactive users."""
        mock_query = Mock()
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_service.db.query.return_value = mock_query

        result = mock_service.list_users(skip=0, limit=10, active_only=False)

        assert isinstance(result, list)

    def test_get_user_success(self, mock_service):
        """Test successful user retrieval."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.username = "testuser"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query

        result = mock_service.get_user("user123")

        assert result.user_id == "user123"
        assert result.username == "testuser"

    def test_get_user_not_found(self, mock_service):
        """Test user retrieval when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            mock_service.get_user("nonexistent")
            assert "User with ID nonexistent not found" in str(exc_info.value)

    def test_update_user_success(self, mock_service):
        """Test successful user update."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.email = "old@example.com"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query
        mock_service.db.commit.return_value = None

        result = mock_service.update_user(
            user_id="user123", email="new@example.com", is_active=False
        )

        assert result.user_id == "user123"
        assert result.email == "new@example.com"
        assert result.is_active is False
        mock_service.db.commit.assert_called_once()

    def test_update_user_not_found(self, mock_service):
        """Test user update when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            mock_service.update_user("nonexistent")
            assert "User with ID nonexistent not found" in str(exc_info.value)

    def test_request_password_reset_success(self, mock_service):
        """Test successful password reset request."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.email = "test@example.com"
        mock_user.password_reset_token = "reset_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query
        mock_service.db.commit.return_value = None

        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="reset_token"
        ):
            mock_service.request_password_reset("test@example.com")

            assert mock_user.password_reset_token == "reset_token"
            mock_service.db.commit.assert_called_once()

    def test_request_password_reset_user_not_found(self, mock_service):
        """Test password reset request when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        # Should not raise exception for security reasons
        mock_service.request_password_reset("nonexistent@example.com")

    def test_confirm_password_reset_success(self, mock_service):
        """Test successful password reset confirmation."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.password_reset_token = "valid_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query
        mock_service.db.commit.return_value = None

        result = mock_service.confirm_password_reset("valid_token", "NewPassword123!")

        assert result is True
        assert mock_user.password_reset_token is None
        assert mock_user.password_reset_expires is None
        mock_service.db.commit.assert_called_once()

    def test_confirm_password_reset_invalid_token(self, mock_service):
        """Test password reset confirmation with invalid token."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        with pytest.raises(Exception) as exc_info:
            mock_service.confirm_password_reset("invalid_token", "NewPassword123!")
            assert "Invalid or expired" in str(exc_info.value)

    def test_confirm_password_reset_expired_token(self, mock_service):
        """Test password reset confirmation with expired token."""
        mock_user = Mock(spec=User)
        mock_user.password_reset_token = "expired_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query

        with pytest.raises(Exception) as exc_info:
            mock_service.confirm_password_reset("expired_token", "NewPassword123!")
            assert "Invalid or expired" in str(exc_info.value)

    def test_reset_password_success(self, mock_service):
        """Test successful password reset."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"
        mock_user.email = "test@example.com"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query
        mock_service.db.commit.return_value = None

        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="reset_token"
        ):
            result = mock_service.reset_password("user123")

            assert result == "reset_token"
            assert mock_user.password_reset_token == "reset_token"

    def test_reset_password_user_not_found(self, mock_service):
        """Test password reset when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            mock_service.reset_password("nonexistent")
            assert "User with ID nonexistent not found" in str(exc_info.value)

    def test_delete_user_success(self, mock_service):
        """Test successful user deletion."""
        mock_user = Mock(spec=User)
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_service.db.query.return_value = mock_query
        mock_service.db.commit.return_value = None

        result = mock_service.delete_user("user123")

        assert result is True
        assert mock_user.is_deleted is True
        mock_service.db.commit.assert_called_once()

    def test_delete_user_not_found(self, mock_service):
        """Test user deletion when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_service.db.query.return_value = mock_query

        with pytest.raises(UserNotFoundError) as exc_info:
            mock_service.delete_user("nonexistent")
            assert "User with ID nonexistent not found" in str(exc_info.value)

    def test_get_user_stats_success(self, mock_service):
        """Test successful user statistics retrieval."""
        # Mock database queries
        mock_count_query = Mock()
        mock_count_query.scalar.return_value = 100

        mock_active_count_query = Mock()
        mock_active_count_query.scalar.return_value = 80

        mock_verified_count_query = Mock()
        mock_verified_count_query.scalar.return_value = 60

        mock_created_today_query = Mock()
        mock_created_today_query.scalar.return_value = 5

        mock_service.db.query.side_effect = [
            mock_count_query,
            mock_active_count_query,
            mock_verified_count_query,
            mock_created_today_query,
        ]

        result = mock_service.get_user_stats()

        assert result["total_users"] == 100
        assert result["active_users"] == 80
        assert result["verified_users"] == 60
        assert result["created_today"] == 5

    def test_send_verification_email_success(self, mock_service):
        """Test successful verification email sending."""
        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="verification_token"
        ):
            # Should not raise exception
            mock_service._send_verification_email("test@example.com", "verification_token")

    def test_send_verification_email_failure(self, mock_service):
        """Test verification email sending failure."""
        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="verification_token"
        ):
            with patch(
                "app.services.user_management.smtplib.SMTP", side_effect=Exception("SMTP error")
            ):
                # Should not raise exception
                mock_service._send_verification_email("test@example.com", "verification_token")

    def test_send_password_reset_email_success(self, mock_service):
        """Test successful password reset email sending."""
        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="reset_token"
        ):
            # Should not raise exception
            mock_service._send_password_reset_email("test@example.com", "reset_token")

    def test_send_password_reset_email_failure(self, mock_service):
        """Test password reset email sending failure."""
        with patch(
            "app.services.user_management.secrets.token_urlsafe", return_value="reset_token"
        ):
            with patch(
                "app.services.user_management.smtplib.SMTP", side_effect=Exception("SMTP error")
            ):
                # Should not raise exception
                mock_service._send_password_reset_email("test@example.com", "reset_token")
