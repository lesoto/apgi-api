"""Unit tests for create_demo_user.py utility module."""

import pytest
from unittest.mock import patch, MagicMock


class TestCreateDemoUser:
    """Test create_demo_user.py functionality."""

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_success(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test successful demo user creation."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_auth_instance = MagicMock()
        mock_auth_manager.return_value = mock_auth_instance
        mock_auth_instance.hash_password.return_value = "hashed_password"

        from app.create_demo_user import create_demo_user

        create_demo_user()

        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_existing_user_update_roles(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test updating existing user with missing roles."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_existing_user = MagicMock()
        mock_existing_user.roles = ["user"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_user

        from app.create_demo_user import create_demo_user

        create_demo_user()

        mock_db.commit.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_existing_user_has_roles(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test existing user already has required roles."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_existing_user = MagicMock()
        mock_existing_user.roles = ["user", "admin"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing_user

        from app.create_demo_user import create_demo_user

        create_demo_user()

        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_database_error(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test handling when database operation fails."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.side_effect = Exception("Database error")

        from app.create_demo_user import create_demo_user

        create_demo_user()

        mock_db.rollback.assert_called()
        mock_db.close.assert_called()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_session_error(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test handling when session creation fails."""
        mock_session_local.side_effect = Exception("Session error")

        from app.create_demo_user import create_demo_user

        with pytest.raises(Exception, match="Session error"):
            create_demo_user()

    @patch("app.create_demo_user.SessionLocal")
    @patch("app.create_demo_user.AuthManager")
    @patch("app.create_demo_user.User")
    def test_create_demo_user_query_error(
        self, mock_user: MagicMock, mock_auth_manager: MagicMock, mock_session_local: MagicMock
    ) -> None:
        """Test handling when query fails."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.side_effect = Exception("Query error")

        from app.create_demo_user import create_demo_user

        create_demo_user()

        mock_db.rollback.assert_called()
        mock_db.close.assert_called()
