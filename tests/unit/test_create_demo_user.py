"""
Unit tests for create_demo_user.py utility module.
"""

from unittest.mock import patch, MagicMock


class TestCreateDemoUser:
    """Test create_demo_user.py functionality."""

    def test_create_demo_user_success(self):
        """Test successful demo user creation."""
        with patch("app.create_demo_user.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Import and call the function
            from app.create_demo_user import create_demo_user

            create_demo_user()

            # Verify database operations were called
            mock_db.query.assert_called_once()
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()

    def test_create_demo_user_permission_error(self):
        """Test handling when permission is denied."""
        with patch("app.create_demo_user.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Mock auth manager to raise PermissionError
            with patch("app.create_demo_user.AuthManager") as mock_auth:
                mock_auth.return_value.hash_password.side_effect = PermissionError(
                    "Permission denied"
                )

                from app.create_demo_user import create_demo_user

                create_demo_user()

                # Verify rollback was called due to error
                mock_db.rollback.assert_called_once()
                mock_db.close.assert_called_once()

    def test_create_demo_user_database_error(self):
        """Test handling when database operation fails."""
        with patch("app.create_demo_user.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Mock database to raise RuntimeError
            mock_db.commit.side_effect = RuntimeError("Database operation failed")

            from app.create_demo_user import create_demo_user

            create_demo_user()

            # Verify rollback was called due to error
            mock_db.rollback.assert_called_once()
            mock_db.close.assert_called_once()
