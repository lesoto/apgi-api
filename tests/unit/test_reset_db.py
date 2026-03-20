"""Unit tests for reset_db.py utility module."""

import os
import importlib
from unittest.mock import patch, MagicMock
from psycopg2.errors import InsufficientPrivilege


class TestResetDatabase:
    """Test reset_db.py functionality."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_success(self, mock_connect):
        """Test successful database reset."""
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

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_insufficient_privilege_fallback(self, mock_connect):
        """Test fallback to clear tables when insufficient privileges."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # Set cursor on mock_cursor to return itself for chaining
        mock_cursor.execute.side_effect = [
            None,  # terminate connections succeeds
            None,  # drop succeeds
            InsufficientPrivilege("Insufficient privileges"),  # create fails
        ]

        with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
            from app.reset_db import recreate_database

            # Should handle the exception and call fallback
            recreate_database()

            # Verify fallback was called
            mock_clear_tables.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    @patch("app.reset_db._clear_all_tables", autospec=True)
    def test_recreate_database_connection_error(self, mock_clear_tables, mock_connect):
        """Test handling when connection fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_connect.side_effect = Exception("Connection failed")

        from app.reset_db import recreate_database

        # Should handle the exception and call fallback
        recreate_database()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_cursor_error(self, mock_connect):
        """Test handling when cursor creation fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_conn.cursor.side_effect = Exception("Cursor creation failed")

        with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
            from app.reset_db import recreate_database

            # Should handle the exception and call fallback
            recreate_database()

            # Verify fallback was called
            mock_clear_tables.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_execute_error(self, mock_connect):
        """Test handling when execute fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Execute failed")

        with patch("app.reset_db._clear_all_tables") as mock_clear_tables:
            from app.reset_db import recreate_database

            # Should handle the exception and call fallback
            recreate_database()

            # Verify fallback was called
            mock_clear_tables.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_recreate_database_terminate_connections_error(self, mock_connect):
        """Test handling when terminating connections fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Terminate failed")

        from app.reset_db import recreate_database

        # Should handle the exception and call fallback
        recreate_database()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    @patch("app.reset_db._clear_all_tables", autospec=True)
    def test_recreate_database_drop_error(self, mock_clear_tables, mock_connect):
        """Test handling when drop database fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,  # terminate connections succeeds
            Exception("Drop failed"),  # drop fails
        ]

        from app.reset_db import recreate_database

        # Should handle the exception and call fallback
        recreate_database()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    @patch("app.reset_db._clear_all_tables", autospec=True)
    def test_recreate_database_create_error(self, mock_clear_tables, mock_connect):
        """Test handling when create database fails."""
        import app.reset_db

        importlib.reload(app.reset_db)

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.set_isolation_level = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,  # terminate connections succeeds
            None,  # drop succeeds
            Exception("Create failed"),  # create fails
        ]

        from app.reset_db import recreate_database

        # Should handle the exception and call fallback
        recreate_database()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_clear_all_tables_success(self, mock_connect):
        """Test successful table clearing."""
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

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2.connect")
    def test_clear_all_tables_no_tables(self, mock_connect):
        """Test clearing when no tables exist."""
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
        mock_cursor.execute.assert_called()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()
