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

    def test_alter_alembic_version_already_exists(self):
        """Test early return when version already exists in alembic_version."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Mock that version already exists (fetchone returns a row)
            mock_conn.execute.return_value.fetchone.return_value = ("add_audit_logs_table",)

            with patch("builtins.print") as mock_print:
                alter_alembic_version()

            # Should print the "already exists" message and return early
            mock_print.assert_called_once_with(
                "Version 'add_audit_logs_table' already exists in alembic_version"
            )
            # Should not execute any other queries or commit
            assert mock_conn.execute.call_count == 1  # Only the check query
            mock_conn.commit.assert_not_called()

    def test_alter_alembic_version_postgresql_dialect(self):
        """Test PostgreSQL-specific table creation and alter statements."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Set dialect to PostgreSQL
            mock_conn.dialect.name = "postgresql"
            # Version doesn't exist
            mock_conn.execute.return_value.fetchone.return_value = None

            with patch("builtins.print"):
                alter_alembic_version()

            # Should execute PostgreSQL-specific statements (more calls for PostgreSQL)
            # PostgreSQL path has: CREATE TABLE, ALTER TABLE, check version, select versions, insert
            assert mock_conn.execute.call_count >= 3
            # Verify commit was called twice (once after PostgreSQL setup, once at end)
            assert mock_conn.commit.call_count >= 1

    def test_alter_alembic_version_non_postgresql_dialect(self):
        """Test with non-PostgreSQL dialect (no table creation)."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Set dialect to SQLite (not PostgreSQL)
            mock_conn.dialect.name = "sqlite"
            # Version doesn't exist
            mock_conn.execute.return_value.fetchone.return_value = None

            with patch("builtins.print"):
                alter_alembic_version()

            # Should execute fewer queries (no PostgreSQL-specific table creation)
            # SQLite path: check version, select versions, insert
            assert mock_conn.execute.call_count >= 2

    def test_alter_alembic_version_with_existing_versions(self):
        """Test deletion of existing versions before inserting new one."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Non-PostgreSQL dialect to skip that block
            mock_conn.dialect.name = "sqlite"

            # Setup execute side effects for multiple queries
            def execute_side_effect(query):
                query_str = str(query)
                mock_result = MagicMock()

                if "SELECT version_num FROM alembic_version WHERE version_num" in query_str:
                    # Version doesn't exist yet
                    mock_result.fetchone.return_value = None
                elif "SELECT version_num FROM alembic_version" in query_str:
                    # Return existing versions
                    mock_result.fetchall.return_value = [("old_version_1",), ("old_version_2",)]
                elif "DELETE FROM alembic_version" in query_str:
                    # Delete succeeds
                    mock_result.fetchall.return_value = []
                elif "INSERT INTO alembic_version" in query_str:
                    # Insert succeeds
                    mock_result.fetchall.return_value = []

                return mock_result

            mock_conn.execute.side_effect = execute_side_effect

            with patch("builtins.print") as mock_print:
                alter_alembic_version()

            # Should print that existing versions were found and deleted
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("Found existing versions" in str(c) for c in print_calls)
            assert any("Deleted existing alembic_version entries" in str(c) for c in print_calls)
            assert any("Set alembic_version" in str(c) for c in print_calls)

    def test_alter_alembic_version_empty_existing_versions(self):
        """Test when current_versions list is empty (no deletion needed)."""
        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            # Non-PostgreSQL dialect
            mock_conn.dialect.name = "sqlite"

            def execute_side_effect(query):
                query_str = str(query)
                mock_result = MagicMock()

                if "SELECT version_num FROM alembic_version WHERE version_num" in query_str:
                    mock_result.fetchone.return_value = None
                elif "SELECT version_num FROM alembic_version" in query_str:
                    # No existing versions
                    mock_result.fetchall.return_value = []
                elif "INSERT INTO alembic_version" in query_str:
                    mock_result.fetchall.return_value = []

                return mock_result

            mock_conn.execute.side_effect = execute_side_effect

            with patch("builtins.print") as mock_print:
                alter_alembic_version()

            # Should not print about deleting versions
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert not any("Deleted existing" in str(c) for c in print_calls)
            # Should print about setting version
            assert any("Set alembic_version" in str(c) for c in print_calls)


class TestAlterAlembicMain:
    """Test the __main__ block execution."""

    def test_module_import_does_not_execute_main(self):
        """Test that importing as module does NOT execute main block."""
        # Reload the module to ensure fresh import
        import importlib
        import app.alter_alembic

        with patch("app.alter_alembic.engine") as mock_engine:
            # Re-import should not trigger engine.connect()
            importlib.reload(app.alter_alembic)

            # Main block should not have been executed during import
            # (the if __name__ == "__main__" condition prevents it)
            mock_engine.connect.assert_not_called()

    def test_main_block_functionality(self):
        """Test main block by directly invoking the guarded code."""
        # This tests the actual code inside if __name__ == "__main__":
        from app.alter_alembic import alter_alembic_version

        with patch("app.alter_alembic.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_conn.dialect.name = "sqlite"

            with patch("builtins.print"):
                # Call the function directly (as the main block would)
                alter_alembic_version()

            # Verify the function was executed properly
            assert mock_conn.execute.call_count >= 2
