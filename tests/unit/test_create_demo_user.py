"""
Unit tests for create_demo_user.py utility module.
"""

from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def create_demo_user_module():
    """Fixture that imports the create_demo_user module with mocked dependencies."""
    with patch("app.create_demo_user.SessionLocal"), patch(
        "app.create_demo_user.AuthManager"
    ), patch("app.create_demo_user.User"):
        from app import create_demo_user
    return create_demo_user


class TestCreateDemoUser:
    """Test create_demo_user.py functionality."""

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_success(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test successful demo user creation."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_auth_instance = MagicMock()
        mock_auth_manager.return_value = mock_auth_instance
        mock_auth_instance.hash_password.return_value = "hashed_password"

        create_demo_user_module.create_demo_user()

        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_existing_user_update_roles(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test updating existing user with missing roles."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_existing_user = MagicMock()
        mock_existing_user.roles = ["user"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_user

        create_demo_user_module.create_demo_user()

        mock_db.commit.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_existing_user_has_roles(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test existing user already has required roles."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_existing_user = MagicMock()
        mock_existing_user.roles = ["user", "admin"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_user

        create_demo_user_module.create_demo_user()

        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_database_error(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test handling when database operation fails."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.side_effect = Exception("Database error")

        create_demo_user_module.create_demo_user()

        mock_db.rollback.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_session_error(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test handling when session creation fails."""
        mock_session_local.side_effect = Exception("Session error")

        create_demo_user_module.create_demo_user()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_query_error(
        self, mock_user, mock_auth_manager, mock_session_local, create_demo_user_module
    ):
        """Test handling when query fails."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.side_effect = Exception("Query error")

        create_demo_user_module.create_demo_user()

        mock_db.rollback.assert_called()
        mock_db.close.assert_called()
