"""
Unit tests for cli.py module.
"""

from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import sys


class TestCLIMigrate:
    """Test CLI migrate command."""

    @patch("builtins.open")
    def test_migrate_with_revision(self, mock_open):
        """Test migrate command with specific revision."""
        # Mock alembic imports
        mock_config = MagicMock()
        mock_command = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "alembic": MagicMock(config=MagicMock(Config=mock_config)),
                "alembic.command": mock_command,
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["migrate", "--revision", "head"])
            assert result.exit_code == 0

    @patch("builtins.open")
    def test_migrate_with_verbose(self, mock_open):
        """Test migrate command with verbose output."""
        # Mock alembic imports
        mock_config = MagicMock()
        mock_command = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "alembic": MagicMock(config=MagicMock(Config=mock_config)),
                "alembic.command": mock_command,
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["migrate", "--verbose"])
            assert result.exit_code == 0

    @patch("builtins.open")
    def test_migrate_failure(self, mock_open):
        """Test migrate command handles errors gracefully."""
        # Mock alembic imports
        mock_config = MagicMock()
        mock_command = MagicMock()
        mock_command.side_effect = Exception("Migration failed")
        with patch.dict(
            sys.modules,
            {
                "alembic": MagicMock(config=MagicMock(Config=mock_config)),
                "alembic.command": mock_command,
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["migrate"])
            assert result.exit_code == 1


class TestCLIWorker:
    """Test CLI worker command."""

    def test_worker_with_defaults(self):
        """Test worker command with default parameters."""
        # Mock celery_app
        mock_celery = MagicMock()
        mock_celery.start = MagicMock()

        with patch.dict(sys.modules, {"app.celery_app": mock_celery}):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["worker"])
            assert result.exit_code == 0

    def test_worker_with_custom_params(self):
        """Test worker command with custom parameters."""
        # Mock celery_app
        mock_celery = MagicMock()
        mock_celery.start = MagicMock()

        with patch.dict(sys.modules, {"app.celery_app": mock_celery}):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(
                cli, ["worker", "--queues", "default", "--concurrency", "4", "--loglevel", "debug"]
            )
            assert result.exit_code == 0

    def test_worker_with_hostname(self):
        """Test worker command with custom hostname."""
        # Mock celery_app
        mock_celery = MagicMock()
        mock_celery.start = MagicMock()

        with patch.dict(sys.modules, {"app.celery_app": mock_celery}):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["worker", "--hostname", "worker1"])
            assert result.exit_code == 0

    def test_worker_failure(self):
        """Test worker command handles errors gracefully."""
        # Mock celery_app
        mock_celery = MagicMock()
        mock_celery.start.side_effect = Exception("Worker failed")

        with patch.dict(sys.modules, {"app.celery_app": mock_celery}):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["worker"])
            assert result.exit_code == 1


class TestCLISeed:
    """Test CLI seed command."""

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_seed_with_defaults(self, mock_init, mock_seeder):
        """Test seed command with default parameters."""
        mock_seeder_instance = MagicMock()
        mock_seeder.return_value = mock_seeder_instance
        mock_seeder_instance.seed_all.return_value = {"users": [], "templates": []}

        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["seed"])
            assert result.exit_code == 0

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_seed_with_clear(self, mock_init, mock_seeder):
        """Test seed command with clear flag."""
        mock_seeder_instance = MagicMock()
        mock_seeder.return_value = mock_seeder_instance
        mock_seeder_instance.clear_all_data.return_value = {"users": 0}
        mock_seeder_instance.seed_all.return_value = {"users": []}
        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["seed", "--clear"])
            assert result.exit_code == 0

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_seed_with_verbose(self, mock_init, mock_seeder):
        """Test seed command with verbose output."""
        mock_seeder_instance = MagicMock()
        mock_seeder.return_value = mock_seeder_instance
        mock_seeder_instance.seed_all.return_value = {
            "users": ["user1", "user2", "user3", "user4", "user5", "user6"]
        }

        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["seed", "--verbose"])
            assert result.exit_code == 0

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_seed_with_custom_counts(self, mock_init, mock_seeder):
        """Test seed command with custom counts."""
        mock_seeder_instance = MagicMock()
        mock_seeder.return_value = mock_seeder_instance
        mock_seeder_instance.seed_all.return_value = {"users": [], "templates": []}

        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "seed",
                    "--users",
                    "20",
                    "--templates",
                    "10",
                    "--sessions",
                    "30",
                    "--tasks",
                    "100",
                ],
            )
            assert result.exit_code == 0

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_seed_failure(self, mock_init, mock_seeder):
        """Test seed command handles errors gracefully."""
        mock_init.side_effect = Exception("Seeding failed")
        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["seed"])
            assert result.exit_code == 1


class TestCLIClearSeed:
    """Test CLI clear_seed_data command."""

    def test_clear_seed_data_without_confirm(self):
        """Test clear_seed_data without confirm flag."""
        from app.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["clear-seed-data"])
        assert result.exit_code == 1

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_clear_seed_data_with_confirm(self, mock_init, mock_seeder):
        """Test clear_seed_data with confirm flag."""
        mock_seeder_instance = MagicMock()
        mock_seeder.return_value = mock_seeder_instance
        mock_seeder_instance.clear_all_data.return_value = {"users": 10, "sessions": 20}
        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["clear-seed-data", "--confirm"])
            assert result.exit_code == 0

    @patch("app.services.seeding_service.DatabaseSeedingService")
    @patch("app.database.connection.init_db")
    def test_clear_seed_data_failure(self, mock_init, mock_seeder):
        """Test clear_seed_data handles errors gracefully."""
        mock_init.side_effect = Exception("Clear failed")
        with patch.dict(
            sys.modules,
            {
                "app.services.seeding_service.DatabaseSeedingService": mock_seeder,
                "app.database.connection": MagicMock(init_db=mock_init),
            },
        ):
            from app.cli import cli

            runner = CliRunner()
            result = runner.invoke(cli, ["clear-seed-data", "--confirm"])
            assert result.exit_code == 1
