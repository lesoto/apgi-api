"""
Unit tests for alter_alembic.py utility module.
"""

from unittest.mock import patch, MagicMock
from app.alter_alembic import alter_alembic_version


class TestAlterAlembicVersion:
    """Test alter_alembic.py functionality."""

    def test_alter_alembic_version_success(self):
        """Test successful version alteration."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            alter_alembic_version()

            mock_conn.execute.assert_called_once()
            mock_conn.commit.assert_called_once()

    def test_alter_alembic_version_database_error(self):
        """Test handling when database operation fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.execute.side_effect = Exception("Database error")

            alter_alembic_version()

            mock_conn.execute.assert_called_once()

    def test_alter_alembic_version_connection_error(self):
        """Test handling when connection fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_engine.connect.side_effect = Exception("Connection failed")

            alter_alembic_version()

    def test_alter_alembic_version_commit_error(self):
        """Test handling when commit fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.commit.side_effect = Exception("Commit failed")

            alter_alembic_version()

            mock_conn.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
