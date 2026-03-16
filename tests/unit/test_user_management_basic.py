"""
Basic working tests for user management service to achieve coverage.
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.services.user_management import UserManagementService
from app.exceptions import ValidationError


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
        assert result["total_sessions"] == 5
        assert result["active_sessions"] == 3

    def test_get_user_management_service(self, mock_db):
        """Test service factory function."""
        from app.services.user_management import get_user_management_service

        service = get_user_management_service(mock_db)
        assert isinstance(service, UserManagementService)
        assert service.db == mock_db
