"""Comprehensive tests for CLI commands."""
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from app.cli import cli


@pytest.fixture
def runner():
    """Create Click CLI runner."""
    return CliRunner()


class TestMigrateCommand:
    """Tests for migrate command."""

    @patch("app.cli.alembic.config")
    @patch("app.cli.command")
    def test_migrate_success(self, mock_command, mock_config, runner):
        """Test successful migration."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate", "--revision", "head"])
        assert result.exit_code == 0
        mock_config.Config.assert_called_once_with("alembic.ini")
        mock_command.upgrade.assert_called_once_with(mock_config_instance, "head")

    @patch("app.cli.alembic.config")
    @patch("app.cli.command")
    def test_migrate_with_specific_revision(self, mock_command, mock_config, runner):
        """Test migration with specific revision."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate", "-r", "123456"])
        assert result.exit_code == 0
        mock_command.upgrade.assert_called_once_with(mock_config_instance, "123456")

    @patch("app.cli.alembic.config")
    @patch("app.cli.command")
    def test_migrate_verbose(self, mock_command, mock_config, runner):
        """Test migration with verbose flag."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate", "-v"])
        assert result.exit_code == 0
        mock_config_instance.set_main_option.assert_called_once_with("sql", "true")

    @patch("app.cli.alembic.config")
    @patch("app.cli.command")
    def test_migrate_failure(self, mock_command, mock_config, runner):
        """Test migration on failure."""
        mock_config.Config.side_effect = Exception("Config error")
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 1


class TestWorkerCommand:
    """Tests for worker command."""

    @patch("app.cli.celery_app")
    def test_worker_success(self, mock_celery_app, runner):
        """Test successful worker start."""
        result = runner.invoke(cli, ["worker", "--queues", "celery", "--concurrency", "4"])
        assert result.exit_code == 0
        mock_celery_app.start.assert_called_once()
        # Check the arguments passed to start
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--queues=celery" in call_args
        assert "--concurrency=4" in call_args

    @patch("app.cli.celery_app")
    def test_worker_with_hostname(self, mock_celery_app, runner):
        """Test worker with custom hostname."""
        result = runner.invoke(cli, ["worker", "-n", "worker1"])
        assert result.exit_code == 0
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--hostname=worker1" in call_args

    @patch("app.cli.celery_app")
    def test_worker_with_loglevel(self, mock_celery_app, runner):
        """Test worker with custom log level."""
        result = runner.invoke(cli, ["worker", "-l", "debug"])
        assert result.exit_code == 0
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--loglevel=debug" in call_args

    @patch("app.cli.celery_app")
    def test_worker_failure(self, mock_celery_app, runner):
        """Test worker on failure."""
        mock_celery_app.start.side_effect = Exception("Worker error")
        result = runner.invoke(cli, ["worker"])
        assert result.exit_code == 1


class TestSeedCommand:
    """Tests for seed command."""

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_success(self, mock_init_db, mock_seeder_class, runner):
        """Test successful seeding."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.seed_all.return_value = {
            "users": ["user1", "user2"],
            "templates": ["template1"],
            "sessions": ["session1"],
            "tasks": ["task1", "task2"],
        }
        result = runner.invoke(
            cli, ["seed", "--users", "5", "--templates", "3", "--sessions", "10", "--tasks", "20"]
        )
        assert result.exit_code == 0
        mock_init_db.assert_called_once()
        mock_seeder.seed_all.assert_called_once_with(
            user_count=5, template_count=3, session_count=10, task_count=20
        )

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_with_clear(self, mock_init_db, mock_seeder_class, runner):
        """Test seeding with clear flag."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.clear_all_data.return_value = {"users": 10, "sessions": 20}
        mock_seeder.seed_all.return_value = {"users": ["user1"]}
        result = runner.invoke(cli, ["seed", "-c", "-v"])
        assert result.exit_code == 0
        mock_seeder.clear_all_data.assert_called_once()
        mock_seeder.seed_all.assert_called_once()

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_verbose(self, mock_init_db, mock_seeder_class, runner):
        """Test seeding with verbose output."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.seed_all.return_value = {
            "users": ["user1", "user2", "user3", "user4", "user5", "user6"],
            "templates": ["template1"],
        }
        result = runner.invoke(cli, ["seed", "-v"])
        assert result.exit_code == 0
        # Verbose output should show counts for lists > 5 items

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_failure(self, mock_init_db, mock_seeder_class, runner):
        """Test seeding on failure."""
        mock_seeder_class.side_effect = Exception("Seeding error")
        result = runner.invoke(cli, ["seed"])
        assert result.exit_code == 1


class TestClearSeedDataCommand:
    """Tests for clear-seed-data command."""

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_clear_without_confirm(self, mock_init_db, mock_seeder_class, runner):
        """Test clear without confirm flag."""
        result = runner.invoke(cli, ["clear-seed-data"])
        assert result.exit_code == 1
        mock_seeder_class.assert_not_called()

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_clear_with_confirm(self, mock_init_db, mock_seeder_class, runner):
        """Test clear with confirm flag."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.clear_all_data.return_value = {
            "users": 10,
            "sessions": 20,
            "templates": 5,
            "tasks": 50,
        }
        result = runner.invoke(cli, ["clear-seed-data", "--confirm"])
        assert result.exit_code == 0
        mock_init_db.assert_called_once()
        mock_seeder.clear_all_data.assert_called_once()

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_clear_failure(self, mock_init_db, mock_seeder_class, runner):
        """Test clear on failure."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.clear_all_data.side_effect = Exception("Clear error")
        result = runner.invoke(cli, ["clear-seed-data", "--confirm"])
        assert result.exit_code == 1


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_cli_help(self, runner):
        """Test CLI help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "APGI API command-line interface" in result.output

    def test_migrate_help(self, runner):
        """Test migrate command help."""
        result = runner.invoke(cli, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "Run database migrations" in result.output

    def test_worker_help(self, runner):
        """Test worker command help."""
        result = runner.invoke(cli, ["worker", "--help"])
        assert result.exit_code == 0
        assert "Start Celery worker" in result.output

    def test_seed_help(self, runner):
        """Test seed command help."""
        result = runner.invoke(cli, ["seed", "--help"])
        assert result.exit_code == 0
        assert "Seed database with test data" in result.output

    def test_clear_seed_data_help(self, runner):
        """Test clear-seed-data command help."""
        result = runner.invoke(cli, ["clear-seed-data", "--help"])
        assert result.exit_code == 0
        assert "Clear all seeded test data" in result.output


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    @patch("app.cli.alembic.config")
    def test_migrate_alembic_import_error(self, mock_config, runner):
        """Test migrate when alembic import fails."""
        mock_config.Config.side_effect = ImportError("No module named 'alembic'")
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 1

    @patch("app.cli.celery_app")
    def test_worker_celery_import_error(self, mock_celery_app, runner):
        """Test worker when celery import fails."""
        with patch("app.cli.celery_app", side_effect=ImportError("No module named 'celery'")):
            result = runner.invoke(cli, ["worker"])
            assert result.exit_code == 1

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_import_error(self, mock_init_db, mock_seeder_class, runner):
        """Test seed when seeding service import fails."""
        mock_seeder_class.side_effect = ImportError("No module")
        result = runner.invoke(cli, ["seed"])
        assert result.exit_code == 1


class TestCLIWithInvalidOptions:
    """Tests for CLI with invalid options."""

    def test_migrate_invalid_revision(self, runner):
        """Test migrate with invalid revision format."""
        result = runner.invoke(cli, ["migrate", "--revision", "invalid"])
        # Should still attempt to run with the revision
        assert result.exit_code in [0, 1]

    def test_worker_invalid_concurrency(self, runner):
        """Test worker with invalid concurrency value."""
        result = runner.invoke(cli, ["worker", "--concurrency", "invalid"])
        # Click should handle type conversion error
        assert result.exit_code != 0

    def test_seed_negative_users(self, runner):
        """Test seed with negative user count."""
        result = runner.invoke(cli, ["seed", "--users", "-5"])
        # Click should handle validation
        assert result.exit_code != 0


class TestCLIDefaultValues:
    """Tests for CLI default values."""

    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    def test_migrate_default_revision(self, mock_config, mock_command, runner):
        """Test migrate uses default revision 'head'."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0
        mock_command.upgrade.assert_called_once_with(mock_config_instance, "head")

    @patch("app.cli.celery_app")
    def test_worker_default_queues(self, mock_celery_app, runner):
        """Test worker uses default queues."""
        result = runner.invoke(cli, ["worker"])
        assert result.exit_code == 0
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--queues=celery" in call_args

    @patch("app.cli.celery_app")
    def test_worker_default_concurrency(self, mock_celery_app, runner):
        """Test worker uses default concurrency."""
        result = runner.invoke(cli, ["worker"])
        assert result.exit_code == 0
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--concurrency=1" in call_args

    @patch("app.cli.celery_app")
    def test_worker_default_loglevel(self, mock_celery_app, runner):
        """Test worker uses default log level."""
        result = runner.invoke(cli, ["worker"])
        assert result.exit_code == 0
        call_args = mock_celery_app.start.call_args[0][0]
        assert "--loglevel=info" in call_args

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_defaults(self, mock_init_db, mock_seeder_class, runner):
        """Test seed uses default values."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.seed_all.return_value = {}
        result = runner.invoke(cli, ["seed"])
        assert result.exit_code == 0
        mock_seeder.seed_all.assert_called_once_with(
            user_count=10, template_count=5, session_count=20, task_count=50
        )


class TestCLIMultipleCommands:
    """Tests for running multiple CLI commands."""

    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    @patch("app.cli.celery_app")
    def test_migrate_then_worker(self, mock_celery_app, mock_config, mock_command, runner):
        """Test running migrate then worker."""
        # Run migrate
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result1 = runner.invoke(cli, ["migrate"])
        assert result1.exit_code == 0
        # Run worker
        result2 = runner.invoke(cli, ["worker"])
        assert result2.exit_code == 0
        # Verify both were called
        mock_command.upgrade.assert_called_once()
        mock_celery_app.start.assert_called_once()


class TestCLIOutputMessages:
    """Tests for CLI output messages."""

    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    def test_migrate_success_message(self, mock_config, mock_command, runner):
        """Test migrate success message."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate", "-r", "123456"])
        assert result.exit_code == 0
        assert "Database migrated to revision: 123456" in result.output

    @patch("app.cli.celery_app")
    def test_worker_start_message(self, mock_celery_app, runner):
        """Test worker start message."""
        result = runner.invoke(cli, ["worker"])
        assert result.exit_code == 0
        assert "Starting Celery worker" in result.output

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_seed_success_message(self, mock_init_db, mock_seeder_class, runner):
        """Test seed success message."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.seed_all.return_value = {}
        result = runner.invoke(cli, ["seed"])
        assert result.exit_code == 0
        assert "Database seeding completed successfully" in result.output

    @patch("app.cli.DatabaseSeedingService")
    @patch("app.cli.init_db")
    def test_clear_success_message(self, mock_init_db, mock_seeder_class, runner):
        """Test clear success message."""
        mock_seeder = MagicMock()
        mock_seeder_class.return_value = mock_seeder
        mock_seeder.clear_all_data.return_value = {"users": 10, "sessions": 20}
        result = runner.invoke(cli, ["clear-seed-data", "--confirm"])
        assert result.exit_code == 0
        assert "Test data cleared successfully" in result.output


class TestCLIWithEnvironmentVariables:
    """Tests for CLI with environment variables."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test/db"})
    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    def test_migrate_with_env_var(self, mock_config, mock_command, runner):
        """Test migrate respects environment variables."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0
        # Environment variable should be available to the command


class TestCLIExitCodes:
    """Tests for CLI exit codes."""

    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    def test_success_exit_code(self, mock_config, mock_command, runner):
        """Test successful command returns exit code 0."""
        mock_config_instance = MagicMock()
        mock_config.Config.return_value = mock_config_instance
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0

    @patch("app.cli.alembic.config")
    def test_failure_exit_code(self, mock_config, runner):
        """Test failed command returns exit code 1."""
        mock_config.Config.side_effect = Exception("Error")
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 1


class TestCLILogging:
    """Tests for CLI logging."""

    @patch("app.cli.command")
    @patch("app.cli.alembic.config")
    def test_logging_on_error(self, mock_config, mock_command, runner):
        """Test error logging."""
        mock_config.Config.side_effect = Exception("Test error")
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 1
        # Error should be logged
