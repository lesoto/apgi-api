"""
Unit tests for create_db.py utility module.
"""

from unittest.mock import patch, MagicMock
import pytest
import psycopg2


@pytest.fixture
def create_db_module():
    """Fixture that imports the create_db module with mocked dependencies."""
    with patch("app.create_db.psycopg2"):
        from app import create_db
    return create_db


class TestCreateDatabase:
    """Test create_db.py functionality."""

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_success(self, mock_connect, create_db_module):
        """Test successful database creation."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        create_db_module.create_database()

        mock_cursor.execute.assert_called()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_duplicate_database(self, mock_connect, create_db_module):
        """Test handling when database already exists."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            psycopg2.errors.DuplicateDatabase("Database exists"),
            None,
            None,
        ]

        create_db_module.create_database()

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_duplicate_user(self, mock_connect, create_db_module):
        """Test handling when user already exists."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,
            psycopg2.errors.DuplicateObject("User exists"),
            None,
        ]

        create_db_module.create_database()

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_connection_error(self, mock_connect, create_db_module):
        """Test handling when connection fails."""
        mock_connect.side_effect = Exception("Connection failed")

        create_db_module.create_database()

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_cursor_error(self, mock_connect, create_db_module):
        """Test handling when cursor creation fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.autocommit = True
        mock_conn.cursor.side_effect = Exception("Cursor creation failed")

        create_db_module.create_database()

    @patch("app.create_db.psycopg2.connect")
    def test_create_database_execute_error(self, mock_connect, create_db_module):
        """Test handling when execute fails."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Execute failed")

        create_db_module.create_database()
