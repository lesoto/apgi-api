"""
Unit tests for alter_alembic.py utility module.
"""

from unittest.mock import patch
from app.alter_alembic import alter_alembic_version


class TestAlterAlembicVersion:
    """Test alter_alembic.py functionality."""

    def test_alter_alembic_version_success(self):
        """Test successful version alteration."""
        with patch("app.alter_alembic.alter_alembic_version") as mock_alter:
            mock_alter.return_value = "2.0.0"

            result = alter_alembic_version()

            assert result == "2.0.0"
            mock_alter.assert_called_once_with("2.0.0")

    def test_alter_alembic_version_file_not_found(self):
        """Test handling when alembic.ini file is not found."""
        with patch("app.alter_alembic.alter_alembic_version") as mock_alter:
            mock_alter.side_effect = FileNotFoundError("alembic.ini not found")

            result = alter_alembic_version()

            assert result is None
            mock_alter.assert_called_once_with("2.0.0")

    def test_alter_alembic_version_permission_error(self):
        """Test handling when permission denied."""
        with patch("app.alter_alembic.alter_alembic_version") as mock_alter:
            mock_alter.side_effect = PermissionError("Permission denied")

            result = alter_alembic_version()

            assert result is None
            mock_alter.assert_called_once_with("2.0.0")

    def test_alter_alembic_version_invalid_format(self):
        """Test handling when version format is invalid."""
        with patch("app.alter_alembic.alter_alembic_version") as mock_alter:
            mock_alter.return_value = "invalid.version.format"

            result = alter_alembic_version()

            assert result is None
            mock_alter.assert_called_once_with("2.0.0")
