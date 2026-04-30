"""
Unit tests for CLI scripts to achieve 100% coverage.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


class TestCreateDB:
    """Test create_db.py script."""

    def test_create_database_success(self) -> None:
        """Test successful database creation."""
        from app.create_db import create_database

        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.autocommit = True

            create_database()

            # Verify database creation was attempted
            mock_cursor.execute.assert_called()
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_create_database_duplicate_user(self) -> None:
        """Test database creation when user already exists."""
        from app.create_db import create_database

        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.autocommit = True
            mock_conn.cursor.return_value = mock_cursor

            # Simulate duplicate user error
            import psycopg2.errors as psycopg2_errors  # noqa: F401

            mock_cursor.execute.side_effect = [
                None,  # CREATE DATABASE succeeds
                psycopg2_errors.DuplicateObject("User already exists"),  # CREATE USER fails
                None,  # GRANT PRIVILEGES succeeds
            ]

            create_database()

            # Should handle duplicate user gracefully
            assert mock_cursor.execute.call_count >= 2

    def test_create_database_duplicate_database(self) -> None:
        """Test database creation when database already exists."""
        from app.create_db import create_database

        with patch("psycopg2.connect") as mock_connect:
            import psycopg2.errors as psycopg2_errors  # noqa: F401

            mock_connect.side_effect = psycopg2_errors.DuplicateDatabase("Database exists")

            create_database()

            # Should handle duplicate database gracefully
            mock_connect.assert_called_once()

    def test_create_database_generic_error(self) -> None:
        """Test database creation with generic error."""
        from app.create_db import create_database

        with patch("psycopg2.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            create_database()

            # Should handle error gracefully
            mock_connect.assert_called_once()


class TestCreateDemoUser:
    """Test create_demo_user.py script."""

    def test_create_demo_user_new_user(self) -> None:
        """Test creating a new demo user."""
        from app.create_demo_user import create_demo_user

        with patch("app.create_demo_user.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None

            with patch("app.create_demo_user.AuthManager") as mock_auth_manager:
                mock_auth = MagicMock()
                mock_auth.hash_password.return_value = "hashed_password"
                mock_auth_manager.return_value = mock_auth

                create_demo_user()

                # Verify user creation - the actual code uses db.add(User(...))
                assert mock_session.add.called
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_create_demo_user_existing_user_with_roles(self) -> None:
        """Test when demo user already exists with correct roles."""
        from app.create_demo_user import create_demo_user

        with patch("app.create_demo_user.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_user = MagicMock()
            mock_user.roles = ["user", "admin"]
            mock_session.query.return_value.filter.return_value.first.return_value = mock_user

            create_demo_user()

            # Should not commit since user already has correct roles
            mock_session.commit.assert_not_called()
            mock_session.close.assert_called_once()

    def test_create_demo_user_existing_user_without_roles(self) -> None:
        """Test when demo user exists but missing roles."""
        from app.create_demo_user import create_demo_user

        with patch("app.create_demo_user.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_user = MagicMock()
            mock_user.roles = ["user"]  # Missing admin role
            mock_session.query.return_value.filter.return_value.first.return_value = mock_user

            create_demo_user()

            # Should update roles - the actual code sets roles = ["user", "admin"]
            assert mock_user.roles == ["user", "admin"]
            mock_session.commit.assert_called_once()

    def test_create_demo_user_error_handling(self) -> None:
        """Test error handling in create_demo_user."""
        from app.create_demo_user import create_demo_user

        with patch("app.create_demo_user.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.side_effect = Exception("Database error")

            create_demo_user()

            # Should handle error and rollback
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestResetDB:
    """Test reset_db.py script."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_recreate_database_success(self) -> None:
        """Test successful database recreation."""
        from app.reset_db import recreate_database

        with patch("app.reset_db._drop_and_create_database") as mock_drop_create:
            recreate_database()

            mock_drop_create.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_recreate_database_insufficient_privilege(self) -> None:
        """Test database recreation with insufficient privilege."""
        from app.reset_db import recreate_database

        with patch("app.reset_db._drop_and_create_database") as mock_drop_create:
            import psycopg2.errors as psycopg2_errors  # noqa: F401

            mock_drop_create.side_effect = psycopg2_errors.InsufficientPrivilege(
                "Permission denied"
            )

            with patch("app.reset_db._clear_all_tables") as mock_clear:
                recreate_database()

                mock_clear.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_recreate_database_generic_error(self) -> None:
        """Test database recreation with generic error."""
        from app.reset_db import recreate_database

        with patch("app.reset_db._drop_and_create_database") as mock_drop_create:
            mock_drop_create.side_effect = Exception("Generic error")

            with patch("app.reset_db._clear_all_tables") as mock_clear:
                recreate_database()

                mock_clear.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_drop_and_create_database(self) -> None:
        """Test _drop_and_create_database function."""
        from app.reset_db import _drop_and_create_database

        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            _drop_and_create_database("user", "pass", "localhost", "5432", "testdb")

            # Verify database operations
            assert mock_cursor.execute.call_count >= 3  # terminate, drop, create
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_clear_all_tables(self) -> None:
        """Test _clear_all_tables function."""
        from app.reset_db import _clear_all_tables

        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [("table1",), ("table2",)]

            _clear_all_tables("user", "pass", "localhost", "5432", "testdb")

            # Verify table clearing
            mock_cursor.execute.assert_called()
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_reset_db_missing_database_url(self) -> None:
        """Test reset_db with missing DATABASE_URL."""
        from app.reset_db import _parse_database_url

        # Save original DATABASE_URL
        original_url = os.environ.get("DATABASE_URL")

        try:
            # Clear DATABASE_URL temporarily
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]

            with pytest.raises(ValueError, match="DATABASE_URL environment variable not set"):
                _parse_database_url()
        finally:
            # Restore original DATABASE_URL
            if original_url is not None:
                os.environ["DATABASE_URL"] = original_url

    def test_reset_db_invalid_database_url(self) -> None:
        """Test reset_db with invalid DATABASE_URL format."""
        from app.reset_db import _parse_database_url

        # Save original DATABASE_URL
        original_url = os.environ.get("DATABASE_URL")

        try:
            with patch.dict(os.environ, {"DATABASE_URL": "invalid-url"}, clear=False):
                with pytest.raises(ValueError, match="Invalid DATABASE_URL format"):
                    _parse_database_url()
        finally:
            # Restore original DATABASE_URL
            if original_url is not None:
                os.environ["DATABASE_URL"] = original_url

    def test_get_db_params(self) -> None:
        """Test get_db_params function."""
        from app.reset_db import get_db_params

        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"}
        ):
            user, password, host, port, db = get_db_params()
            assert user == "user"
            assert password == "pass"
            assert host == "localhost"
            assert port == "5432"
            assert db == "testdb"


class TestCLICommands:
    """Test CLI commands in cli.py."""

    def test_cli_group_no_command(self) -> None:
        """Test CLI group when no subcommand is invoked."""
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli)

        # Should show help and exit with code 2
        assert result.exit_code == 2
        assert "APGI API command-line interface" in result.output

    def test_migrate_command_success(self) -> None:
        """Test migrate command with success."""
        from app.cli import cli

        with patch("alembic.config.Config") as mock_config:
            with patch("alembic.command.upgrade") as mock_upgrade:
                runner = CliRunner()
                result = runner.invoke(cli, ["migrate", "--revision", "head"])

                assert result.exit_code == 0
                mock_config.assert_called_once()
                mock_upgrade.assert_called_once()

    def test_migrate_command_verbose(self) -> None:
        """Test migrate command with verbose flag."""
        from app.cli import cli

        with patch("alembic.config.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config
            with patch("alembic.command.upgrade") as mock_upgrade:
                runner = CliRunner()
                result = runner.invoke(cli, ["migrate", "--verbose"])

                assert result.exit_code == 0
                mock_config.set_main_option.assert_called_once_with("sql", "true")

    def test_migrate_command_failure(self) -> None:
        """Test migrate command with failure."""
        from app.cli import cli

        with patch("alembic.config.Config") as mock_config:
            with patch("alembic.command.upgrade") as mock_upgrade:
                mock_upgrade.side_effect = Exception("Migration failed")
                runner = CliRunner()
                result = runner.invoke(cli, ["migrate"])

                assert result.exit_code == 1

    def test_worker_command_success(self) -> None:
        """Test worker command with success."""
        from app.cli import cli

        with patch("app.celery_app.celery_app") as mock_celery:
            runner = CliRunner()
            result = runner.invoke(cli, ["worker"])

            assert result.exit_code == 0
            mock_celery.start.assert_called_once()

    def test_worker_command_with_options(self) -> None:
        """Test worker command with all options."""
        from app.cli import cli

        with patch("app.celery_app.celery_app") as mock_celery:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "worker",
                    "--queues",
                    "default",
                    "--concurrency",
                    "4",
                    "--loglevel",
                    "debug",
                    "--hostname",
                    "worker1",
                ],
            )

            assert result.exit_code == 0
            mock_celery.start.assert_called_once()

    def test_worker_command_failure(self) -> None:
        """Test worker command with failure."""
        from app.cli import cli

        with patch("app.celery_app.celery_app") as mock_celery:
            mock_celery.start.side_effect = Exception("Worker failed")
            runner = CliRunner()
            result = runner.invoke(cli, ["worker"])

            assert result.exit_code == 1

    def test_seed_command_success(self) -> None:
        """Test seed command with success."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            with patch("app.services.seeding_service.DatabaseSeedingService") as mock_seeder_class:
                mock_seeder = MagicMock()
                mock_seeder.seed_all.return_value = {"users": [], "templates": []}
                mock_seeder_class.return_value = mock_seeder

                runner = CliRunner()
                result = runner.invoke(cli, ["seed"])

                assert result.exit_code == 0
                mock_init_db.assert_called_once()
                mock_seeder.seed_all.assert_called_once()

    def test_seed_command_with_clear(self) -> None:
        """Test seed command with clear flag."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            with patch("app.services.seeding_service.DatabaseSeedingService") as mock_seeder_class:
                mock_seeder = MagicMock()
                mock_seeder.clear_all_data.return_value = {"users": 5}
                mock_seeder.seed_all.return_value = {"users": [], "templates": []}
                mock_seeder_class.return_value = mock_seeder

                runner = CliRunner()
                result = runner.invoke(cli, ["seed", "--clear"])

                assert result.exit_code == 0
                mock_seeder.clear_all_data.assert_called_once()

    def test_seed_command_negative_counts(self) -> None:
        """Test seed command with negative counts (should fail)."""
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["seed", "--users", "-1"])

        assert result.exit_code == 1

    def test_seed_command_verbose(self) -> None:
        """Test seed command with verbose flag."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            with patch("app.services.seeding_service.DatabaseSeedingService") as mock_seeder_class:
                mock_seeder = MagicMock()
                mock_seeder.seed_all.return_value = {"users": [1, 2, 3, 4, 5, 6]}
                mock_seeder_class.return_value = mock_seeder

                runner = CliRunner()
                result = runner.invoke(cli, ["seed", "--verbose"])

                assert result.exit_code == 0

    def test_seed_command_failure(self) -> None:
        """Test seed command with failure."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            mock_init_db.side_effect = Exception("Database error")

            runner = CliRunner()
            result = runner.invoke(cli, ["seed"])

            assert result.exit_code == 1

    def test_clear_seed_data_without_confirm(self) -> None:
        """Test clear_seed_data command without confirm flag."""
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["clear-seed-data"])

        assert result.exit_code == 1
        # The error message is logged to stderr, not in output
        # Just check that it exits with error code 1

    def test_clear_seed_data_with_confirm(self) -> None:
        """Test clear_seed_data command with confirm flag."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            with patch("app.services.seeding_service.DatabaseSeedingService") as mock_seeder_class:
                mock_seeder = MagicMock()
                mock_seeder.clear_all_data.return_value = {"users": 10, "sessions": 20}
                mock_seeder_class.return_value = mock_seeder

                runner = CliRunner()
                result = runner.invoke(cli, ["clear-seed-data", "--confirm"])

                assert result.exit_code == 0
                mock_seeder.clear_all_data.assert_called_once()

    def test_clear_seed_data_failure(self) -> None:
        """Test clear_seed_data command with failure."""
        from app.cli import cli

        with patch("app.database.connection.init_db") as mock_init_db:
            mock_init_db.side_effect = Exception("Database error")

            runner = CliRunner()
            result = runner.invoke(cli, ["clear-seed-data", "--confirm"])

            assert result.exit_code == 1
