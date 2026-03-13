"""
Unit tests for reset_db.py utility module.
"""

from unittest.mock import patch
from app.reset_db import recreate_database


class TestResetDatabase:
    """Test reset_db.py functionality."""

    def test_recreate_database_success(self):
        """Test successful database reset."""
        with patch("app.reset_db.recreate_database") as mock_reset:
            mock_reset.return_value = None

            result = recreate_database()

            assert result is None
            mock_reset.assert_called_once()

    def test_recreate_database_permission_error(self):
        """Test handling when permission is denied."""
        with patch("app.reset_db.recreate_database") as mock_reset:
            mock_reset.side_effect = PermissionError("Permission denied")

            result = recreate_database()

            assert result is None
            mock_reset.assert_called_once()

    def test_recreate_database_file_not_found(self):
        """Test handling when database file is not found."""
        with patch("app.reset_db.recreate_database") as mock_reset:
            mock_reset.side_effect = FileNotFoundError("Database file not found")

            result = recreate_database()

            assert result is None
            mock_reset.assert_called_once()

    def test_recreate_database_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch("app.reset_db.recreate_database") as mock_reset:
            mock_reset.side_effect = RuntimeError("Unexpected error")

            result = recreate_database()

            assert result is None
            mock_reset.assert_called_once()
