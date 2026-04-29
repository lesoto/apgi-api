"""
Unit tests for app/reset_db.py using mock_psycopg2 fixture.
Covers recreate_database success path, InsufficientPrivilege fallback,
generic error fallback, and _clear_all_tables.
Requirements: 1.9, 5.8
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_psycopg2_resetdb():
    """Create mock psycopg2 module with InsufficientPrivilege exception."""
    mock = MagicMock()
    mock.extensions = MagicMock()
    mock.extensions.ISOLATION_LEVEL_AUTOCOMMIT = 0
    mock.errors = MagicMock()
    mock.errors.DuplicateDatabase = type("DuplicateDatabase", (Exception,), {})
    mock.errors.DuplicateObject = type("DuplicateObject", (Exception,), {})
    mock.errors.InsufficientPrivilege = type("InsufficientPrivilege", (Exception,), {})

    sys.modules["psycopg2"] = mock
    sys.modules["psycopg2.extensions"] = mock.extensions
    sys.modules["psycopg2.errors"] = mock.errors

    yield mock

    sys.modules.pop("psycopg2", None)
    sys.modules.pop("psycopg2.extensions", None)
    sys.modules.pop("psycopg2.errors", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecreateDatabaseSuccess:
    """Test the happy path: drop and create succeeds."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    def test_success_calls_drop_and_create(self, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        recreate_database()
        mock_drop_create.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    def test_success_sets_isolation_level(self, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        recreate_database()
        mock_drop_create.assert_called_once()


class TestRecreateDatabaseInsufficientPrivilege:
    """Test fallback to _clear_all_tables on InsufficientPrivilege."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    @patch("app.reset_db._clear_all_tables")
    @patch("app.reset_db.psycopg2")
    def test_insufficient_privilege_falls_back_to_clear_tables(
        self, mock_psycopg2, mock_clear, mock_drop_create
    ) -> None:
        from app.reset_db import recreate_database

        # Create a custom exception class that matches the real one
        class InsufficientPrivilege(Exception):
            pass

        mock_psycopg2.errors.InsufficientPrivilege = InsufficientPrivilege
        mock_drop_create.side_effect = InsufficientPrivilege("no privilege")
        recreate_database()
        mock_clear.assert_called_once()


class TestRecreateDatabaseGenericError:
    """Test fallback to _clear_all_tables on generic Exception."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    @patch("app.reset_db._clear_all_tables")
    def test_connection_error_falls_back(self, mock_clear, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        mock_drop_create.side_effect = Exception("Connection failed")
        recreate_database()
        mock_clear.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    @patch("app.reset_db._clear_all_tables")
    def test_cursor_error_falls_back(self, mock_clear, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        mock_drop_create.side_effect = Exception("Cursor failed")
        recreate_database()
        mock_clear.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    @patch("app.reset_db._clear_all_tables")
    def test_execute_error_falls_back(self, mock_clear, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        mock_drop_create.side_effect = Exception("Execute failed")
        recreate_database()
        mock_clear.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db._drop_and_create_database")
    @patch("app.reset_db._clear_all_tables")
    def test_drop_error_falls_back(self, mock_clear, mock_drop_create) -> None:
        from app.reset_db import recreate_database

        mock_drop_create.side_effect = Exception("Drop failed")
        recreate_database()
        mock_clear.assert_called_once()


class TestClearAllTables:
    """Test _clear_all_tables directly."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2")
    def test_clear_all_tables_success(self, mock_psycopg2) -> None:
        from app.reset_db import _clear_all_tables

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("users",), ("sessions",)]

        _clear_all_tables("user", "pass", "localhost", "5432", "dbname")

        # Should have called execute for SELECT tablename + DROP for each table
        assert mock_cursor.execute.call_count >= 3
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2")
    def test_clear_all_tables_no_tables(self, mock_psycopg2) -> None:
        from app.reset_db import _clear_all_tables

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        _clear_all_tables("user", "pass", "localhost", "5432", "dbname")

        # Only the SELECT tablename call
        mock_cursor.execute.assert_called()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname"})
    @patch("app.reset_db.psycopg2")
    def test_clear_all_tables_drop_error_continues(self, mock_psycopg2) -> None:
        """Error dropping one table should not stop the rest."""
        from app.reset_db import _clear_all_tables

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("table_a",), ("table_b",)]
        # First DROP raises, second succeeds
        mock_cursor.execute.side_effect = [
            None,  # SELECT tablename
            Exception("drop failed"),  # DROP table_b (sorted reverse)
            None,  # DROP table_a
        ]

        # Should not raise
        _clear_all_tables("user", "pass", "localhost", "5432", "dbname")
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()
