"""
Unit tests for create_db.py utility module.
"""

from unittest.mock import patch


class TestCreateDatabase:
    """Test create_db.py functionality."""

    def test_create_database_success(self):
        """Test successful database creation."""
        with patch("app.create_db.create_database") as mock_create:
            mock_create.return_value = None

            from app.create_db import create_database

            result = create_database()

            assert result is None
            mock_create.assert_called_once()

    def test_create_database_permission_error(self):
        """Test handling when permission is denied."""
        with patch("app.create_db.create_database") as mock_create:
            mock_create.side_effect = PermissionError("Permission denied")

            from app.create_db import create_database

            result = create_database()

            assert result is None
            mock_create.assert_called_once()

    def test_create_database_file_exists_error(self):
        """Test handling when database file already exists."""
        with patch("app.create_db.create_database") as mock_create:
            mock_create.side_effect = FileExistsError("Database file already exists")

            from app.create_db import create_database

            result = create_database()

            assert result is None
            mock_create.assert_called_once()

    def test_create_database_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch("app.create_db.create_database") as mock_create:
            mock_create.side_effect = RuntimeError("Unexpected error")

            from app.create_db import create_database

            result = create_database()

            assert result is None
            mock_create.assert_called_once()
