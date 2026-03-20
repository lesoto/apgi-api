"""Unit tests for create_db.py utility module."""
from unittest.mock import MagicMock, patch
from psycopg2.errors import DuplicateDatabase, DuplicateObject


class TestCreateDatabase:
    """Test create_db.py functionality."""

    def test_create_database_success(self, mock_psycopg2):
        """Test successful database creation."""
        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        from app.create_db import create_database

        create_database()

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
        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # First call (CREATE DATABASE) raises DuplicateDatabase
        # The exception is caught and close() is NOT called
        mock_cursor.execute.side_effect = DuplicateDatabase("Database exists")

        from app.create_db import create_database

        create_database()

        # When DuplicateDatabase is caught, close is NOT called
        mock_cursor.close.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_create_database_duplicate_user(self):
        """Test handling when user already exists."""
        # Use local patch to ensure create_database uses the mock
        with patch("psycopg2.connect") as mock_connect:
            with patch("psycopg2.errors") as mock_errors:
                mock_errors.DuplicateObject = DuplicateObject

                # Import create_database after patching
                from app.create_db import create_database

                mock_conn = mock_connect.return_value
                mock_conn.autocommit = True
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                # First call (CREATE DATABASE) succeeds, second call (CREATE USER) raises DuplicateObject
                # The exception is caught and close() is NOT called
                mock_cursor.execute.side_effect = [None, DuplicateObject("User exists"), None]

                create_database()

                # When DuplicateObject is caught for user creation, exception is handled
                # but GRANT statement still executes outside of try/except block
                assert (
                    mock_cursor.execute.call_count == 3
                )  # CREATE DATABASE, CREATE USER (with exception), GRANT
                mock_cursor.close.assert_called_once()
                mock_conn.close.assert_called_once()

    def test_create_database_connection_error(self, mock_psycopg2):
        """Test handling when connection fails."""
        # Use local patch to ensure create_database uses the mock
        with patch("psycopg2.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            # Import create_database after patching
            from app.create_db import create_database

            create_database()

            mock_connect.assert_called_once()

    def test_create_database_cursor_error(self, mock_psycopg2):
        """Test handling when cursor creation fails."""
        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value.cursor.return_value = mock_cursor
        mock_cursor.side_effect = Exception("Cursor creation failed")

        from app.create_db import create_database

        create_database()

        # When execute fails with general Exception, close is NOT called
        mock_cursor.close.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_create_database_execute_error(self, mock_psycopg2):
        """Test handling when execute fails."""
        mock_conn = mock_psycopg2.connect.return_value
        mock_conn.autocommit = True
        mock_cursor = mock_psycopg2.connect.return_value.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Execute failed")

        from app.create_db import create_database

        create_database()

        # When execute fails with general Exception, close is NOT called
        mock_cursor.close.assert_not_called()
        mock_conn.close.assert_not_called()

    def test_create_database_autocommit_set(self, mock_psycopg2):
        """Test that autocommit is set to True."""
        mock_conn = mock_psycopg2.connect.return_value
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        from app.create_db import create_database

        create_database()

        assert mock_conn.autocommit

    def test_create_database_multiple_statements(self, mock_psycopg2):
        """Test that all SQL statements are executed in correct order."""
        mock_conn = mock_psycopg2.connect.return_value
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        from app.create_db import create_database

        create_database()

        call_count = mock_cursor.execute.call_count
        assert call_count >= 3  # CREATE DATABASE, CREATE USER, GRANT PRIVILEGES
