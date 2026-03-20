"""Unit tests for reset_db.py utility module."""

import importlib
from unittest.mock import patch, MagicMock
from psycopg2.errors import InsufficientPrivilege


class TestResetDatabase:
    """Test reset_db.py functionality."""

    def test_recreate_database_success(self):
        """Test successful database reset."""
        with patch("app.reset_db.psycopg2.connect") as mock_connect:
            with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
                import app.reset_db

                importlib.reload(app.reset_db)

                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_conn.set_isolation_level = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor

                from app.reset_db import recreate_database

                # Should complete successfully without exceptions
                recreate_database()

                # Verify the drop and create operations were called
                assert mock_cursor.execute.call_count >= 2
                mock_cursor.close.assert_called()
                mock_conn.close.assert_called()

    def test_recreate_database_insufficient_privilege_fallback(self):
        """Test fallback to clear tables when insufficient privileges."""
        with patch("app.reset_db.psycopg2.connect") as mock_connect:
            with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
                import app.reset_db

                importlib.reload(app.reset_db)

                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_conn.set_isolation_level = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor

                # Set cursor execute to raise InsufficientPrivilege on CREATE DATABASE
                mock_cursor.execute.side_effect = [
                    None,  # terminate connections succeeds
                    None,  # drop succeeds
                    InsufficientPrivilege("Insufficient privileges"),  # create fails
                ]

                from app.reset_db import recreate_database

                # Should handle the exception and call fallback
                recreate_database()

                # Verify fallback was called
                mock_clear_tables.assert_called_once()

    def test_recreate_database_connection_error(self):
        """Test handling when connection fails."""
        with patch("app.reset_db.psycopg2.connect") as mock_connect:
            with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
                import app.reset_db

                importlib.reload(app.reset_db)

                mock_connect.side_effect = Exception("Connection failed")

                from app.reset_db import recreate_database

                # Should handle the exception and call fallback
                recreate_database()

                # Verify fallback was called
                mock_clear_tables.assert_called_once()

    def test_clear_all_tables_success(self):
        """Test successful table clearing."""
        with patch("app.reset_db.psycopg2.connect") as mock_connect:
            import app.reset_db

            importlib.reload(app.reset_db)

            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.set_isolation_level = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [("table1",), ("table2",)]

            from app.reset_db import _clear_all_tables

            _clear_all_tables()

            # Verify table listing and drop operations
            assert mock_cursor.execute.call_count >= 2
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_clear_all_tables_no_tables(self):
        """Test clearing when no tables exist."""
        with patch("app.reset_db.psycopg2.connect") as mock_connect:
            import app.reset_db

            importlib.reload(app.reset_db)

            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.set_isolation_level = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            from app.reset_db import _clear_all_tables

            _clear_all_tables()

            # Verify table listing was called
            assert mock_cursor.execute.assert_called()
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()
