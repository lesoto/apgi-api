"""
Unit tests for app/reset_db.py using mock_psycopg2 fixture.
Covers recreate_database success path, InsufficientPrivilege fallback,
generic error fallback, and _clear_all_tables.
Requirements: 1.9, 5.8
"""

import importlib
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_URL = "postgresql://user:pass@localhost:5432/dbname"


def _load_reset_db(mock_psycopg2: MagicMock) -> Any:
    """Reload app.reset_db with mock_psycopg2 in sys.modules and DATABASE_URL set."""
    # Ensure InsufficientPrivilege is a real exception class (required for except clause)
    if not (
        isinstance(mock_psycopg2.errors.InsufficientPrivilege, type)
        and issubclass(mock_psycopg2.errors.InsufficientPrivilege, BaseException)
    ):
        mock_psycopg2.errors.InsufficientPrivilege = type("InsufficientPrivilege", (Exception,), {})

    # Ensure dotenv doesn't interfere
    with patch.dict(os.environ, {"DATABASE_URL": _DB_URL}):
        with patch.dict(
            sys.modules,
            {
                "psycopg2": mock_psycopg2,
                "psycopg2.extensions": mock_psycopg2.extensions,
                "psycopg2.errors": mock_psycopg2.errors,
                "dotenv": MagicMock(),
            },
        ):
            # Remove cached module so reload picks up the patched psycopg2
            sys.modules.pop("app.reset_db", None)
            import app.reset_db as mod

            importlib.reload(mod)
            return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecreateDatabaseSuccess:
    """Test the happy path: drop and create succeeds."""

    def test_success_calls_drop_and_create(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.return_value = None

        mod.recreate_database()

        # connect was called (at least once for _drop_and_create_database)
        assert mock_psycopg2.connect.call_count >= 1
        # cursor.execute called for: terminate connections, DROP, CREATE
        assert mock_cursor.execute.call_count >= 3
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    def test_success_sets_isolation_level(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mod.recreate_database()

        mock_conn.set_isolation_level.assert_called()


class TestRecreateDatabaseInsufficientPrivilege:
    """Test fallback to _clear_all_tables on InsufficientPrivilege."""

    def test_insufficient_privilege_falls_back_to_clear_tables(
        self, mock_psycopg2: MagicMock
    ) -> None:
        mod = _load_reset_db(mock_psycopg2)

        # Make InsufficientPrivilege a real exception subclass
        InsufficientPrivilege = type("InsufficientPrivilege", (Exception,), {})
        mock_psycopg2.errors.InsufficientPrivilege = InsufficientPrivilege

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # Raise InsufficientPrivilege on CREATE DATABASE
        mock_cursor.execute.side_effect = [
            None,  # terminate connections
            None,  # DROP DATABASE
            InsufficientPrivilege("no privilege"),  # CREATE DATABASE
        ]

        with patch.object(mod, "_clear_all_tables") as mock_clear:
            mod.recreate_database()
            mock_clear.assert_called_once()


class TestRecreateDatabaseGenericError:
    """Test fallback to _clear_all_tables on generic Exception."""

    def test_connection_error_falls_back(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)
        mock_psycopg2.connect.side_effect = Exception("Connection failed")

        with patch.object(mod, "_clear_all_tables") as mock_clear:
            mod.recreate_database()
            mock_clear.assert_called_once()

    def test_cursor_error_falls_back(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.side_effect = Exception("Cursor failed")

        with patch.object(mod, "_clear_all_tables") as mock_clear:
            mod.recreate_database()
            mock_clear.assert_called_once()

    def test_execute_error_falls_back(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Execute failed")

        with patch.object(mod, "_clear_all_tables") as mock_clear:
            mod.recreate_database()
            mock_clear.assert_called_once()

    def test_drop_error_falls_back(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = [
            None,  # terminate connections
            Exception("Drop failed"),  # DROP DATABASE
        ]

        with patch.object(mod, "_clear_all_tables") as mock_clear:
            mod.recreate_database()
            mock_clear.assert_called_once()


class TestClearAllTables:
    """Test _clear_all_tables directly."""

    def test_clear_all_tables_success(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("users",), ("sessions",)]

        mod._clear_all_tables()

        # Should have called execute for SELECT tablename + DROP for each table
        assert mock_cursor.execute.call_count >= 3
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    def test_clear_all_tables_no_tables(self, mock_psycopg2: MagicMock) -> None:
        mod = _load_reset_db(mock_psycopg2)

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        mod._clear_all_tables()

        # Only the SELECT tablename call
        mock_cursor.execute.assert_called()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()

    def test_clear_all_tables_drop_error_continues(self, mock_psycopg2: MagicMock) -> None:
        """Error dropping one table should not stop the rest."""
        mod = _load_reset_db(mock_psycopg2)

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
        mod._clear_all_tables()
        mock_cursor.close.assert_called()
        mock_conn.close.assert_called()
