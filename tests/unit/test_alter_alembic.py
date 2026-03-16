"""
Unit tests for alter_alembic.py utility module.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.alter_alembic import alter_alembic_version


class TestAlterAlembicVersion:
    """Test alter_alembic.py functionality."""

    def test_alter_alembic_version_success(self):
        """Test successful version alteration when version doesn't exist."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Mock that version doesn't exist
            mock_conn.execute.return_value.fetchone.return_value = None

            alter_alembic_version()

            assert mock_conn.execute.call_count >= 2  # Check version and insert
            mock_conn.commit.assert_called_once()

    def test_alter_alembic_version_database_error(self):
        """Test handling when database operation fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # First execute succeeds (check version), second fails
            mock_conn.execute.side_effect = [
                MagicMock(fetchone=MagicMock(return_value=None)),
                Exception("Database error"),
            ]

            with patch("builtins.print"):  # Suppress error output
                with pytest.raises(Exception, match="Database error"):
                    alter_alembic_version()

            assert mock_conn.execute.call_count >= 1

    def test_alter_alembic_version_connection_error(self):
        """Test handling when connection fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_engine.connect.side_effect = Exception("Connection failed")

            with patch("builtins.print"):  # Suppress error output
                with pytest.raises(Exception, match="Connection failed"):
                    alter_alembic_version()

    def test_alter_alembic_version_commit_error(self):
        """Test handling when commit fails."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Version doesn't exist, but commit fails
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_conn.commit.side_effect = Exception("Commit failed")

            with patch("builtins.print"):  # Suppress error output
                with pytest.raises(Exception, match="Commit failed"):
                    alter_alembic_version()

            assert mock_conn.execute.call_count >= 1
            mock_conn.commit.assert_called_once()
