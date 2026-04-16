"""Unit tests for create_db.py utility module."""

import importlib
from unittest.mock import MagicMock


class TestCreateDatabase:
    """Test create_db.py functionality."""

    def test_create_database_success(self, mock_psycopg2):
        """Test successful database creation."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        create_db_mod.create_database()

        mock_psycopg2.connect.assert_called_once_with(
            host="localhost",
            port=5432,
            user="postgres",
            database="postgres",
        )
        # Check that execute was called at least 3 times (CREATE DATABASE, CREATE USER, GRANT)
        assert mock_cursor.execute.call_count >= 3
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_database_duplicate_database(self, mock_psycopg2):
        """Test handling when database already exists."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # First call (CREATE DATABASE) raises DuplicateDatabase
        # The exception is caught and close() is NOT called (no finally block)
        mock_cursor.execute.side_effect = mock_psycopg2.errors.DuplicateDatabase("Database exists")

        create_db_mod.create_database()

        # When DuplicateDatabase is caught, close is NOT called
        mock_cursor.close.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_create_database_duplicate_user(self, mock_psycopg2):
        """Test handling when user already exists."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,
            mock_psycopg2.errors.DuplicateObject("User exists"),
            None,
        ]

        create_db_mod.create_database()

        # CREATE DATABASE, CREATE USER (with exception), GRANT
        assert mock_cursor.execute.call_count == 3
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_database_connection_error(self, mock_psycopg2):
        """Test handling when connection fails."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_psycopg2.connect.side_effect = Exception("Connection failed")

        create_db_mod.create_database()

        mock_psycopg2.connect.assert_called_once()

    def test_create_database_cursor_error(self, mock_psycopg2: MagicMock) -> None:
        """Test handling when cursor creation fails."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_conn.cursor.side_effect = Exception("Cursor creation failed")

        create_db_mod.create_database()

        # Exception falls to outer except block; no finally, so close is NOT called
        mock_conn.close.assert_not_called()

    def test_create_database_execute_error(self, mock_psycopg2: MagicMock) -> None:
        """Test handling when execute fails with a generic exception."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Execute failed")

        create_db_mod.create_database()

        # When execute fails with general Exception, close is NOT called (no finally block)
        mock_cursor.close.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_create_database_autocommit_set(self, mock_psycopg2: MagicMock) -> None:
        """Test that autocommit is set to True."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        create_db_mod.create_database()

        assert mock_conn.autocommit

    def test_create_database_multiple_statements(self, mock_psycopg2: MagicMock) -> None:
        """Test that all SQL statements are executed in correct order."""
        import app.create_db as create_db_mod

        importlib.reload(create_db_mod)

        mock_conn = mock_psycopg2.connect.return_value
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        create_db_mod.create_database()

        call_count = mock_cursor.execute.call_count
        assert call_count >= 3  # CREATE DATABASE, CREATE USER, GRANT PRIVILEGES
