"""
Unit tests for reset_db.py utility module.
"""

from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def reset_db_module():
    """Fixture that imports the reset_db module with mocked dependencies."""
    with patch("app.reset_db.psycopg2"):
        from app import reset_db
    return reset_db


class TestResetDatabase:
    """Test reset_db.py functionality."""

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_success(self, mock_connect, reset_db_module):
        """Test successful database reset."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        reset_db_module.recreate_database()

        mock_cursor.execute.assert_called()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_connection_error(self, mock_connect, reset_db_module):
        """Test handling when connection fails."""
        mock_connect.side_effect = Exception("Connection failed")

        reset_db_module.recreate_database()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_cursor_error(self, mock_connect, reset_db_module):
        """Test handling when cursor creation fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_conn.cursor.side_effect = Exception("Cursor creation failed")

        reset_db_module.recreate_database()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_execute_error(self, mock_connect, reset_db_module):
        """Test handling when execute fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Execute failed")

        reset_db_module.recreate_database()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_terminate_connections_error(self, mock_connect, reset_db_module):
        """Test handling when terminating connections fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            Exception("Terminate failed"),
            None,
            None,
        ]

        reset_db_module.recreate_database()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_drop_error(self, mock_connect, reset_db_module):
        """Test handling when drop database fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,
            Exception("Drop failed"),
        ]

        reset_db_module.recreate_database()

    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_create_error(self, mock_connect, reset_db_module):
        """Test handling when create database fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,
            None,
            Exception("Create failed"),
        ]

        reset_db_module.recreate_database()
