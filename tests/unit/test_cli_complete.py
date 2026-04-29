"""
Additional unit tests for CLI to achieve 100% coverage.

Covers:
- Exception handling in migrate command
- Exception handling in worker command
- Exception handling in seed command
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner


class TestCLIMigrateExceptions:
    """Test exception handling in migrate command."""

    @patch("alembic.command.upgrade")
    def test_migrate_exception(self, mock_upgrade: MagicMock) -> None:
        """Test that migrate command handles exceptions."""
        from app.cli import migrate

        mock_upgrade.side_effect = Exception("Migration failed")

        runner = CliRunner()
        result = runner.invoke(migrate, ["--revision", "head"])

        assert result.exit_code == 1
        assert "Migration failed" in result.output or result.exit_code == 1


class TestCLIWorkerExceptions:
    """Test exception handling in worker command."""

    @patch("app.celery_app.celery_app")
    def test_worker_exception(self, mock_celery: MagicMock) -> None:
        """Test that worker command handles exceptions."""
        from app.cli import worker

        mock_celery.start.side_effect = Exception("Worker failed")

        runner = CliRunner()
        result = runner.invoke(worker, ["--queues", "celery"])

        assert result.exit_code == 1


class TestCLISeedExceptions:
    """Test exception handling in seed command."""

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_seed_exception(self, mock_seeding_service: MagicMock, mock_init_db: MagicMock) -> None:
        """Test that seed command handles exceptions."""
        from app.cli import seed

        mock_init_db.side_effect = Exception("DB connection failed")

        runner = CliRunner()
        result = runner.invoke(seed, ["--users", "5"])

        assert result.exit_code == 1

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_seed_negative_count(
        self, mock_seeding_service: MagicMock, mock_init_db: MagicMock
    ) -> None:
        """Test that seed command handles negative counts."""
        from app.cli import seed

        runner = CliRunner()
        result = runner.invoke(seed, ["--users", "-1"])

        assert result.exit_code == 1


class TestCLIClearSeedDataExceptions:
    """Test exception handling in clear_seed_data command."""

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_clear_seed_data_exception(
        self, mock_seeding_service: MagicMock, mock_init_db: MagicMock
    ) -> None:
        """Test that clear_seed_data command handles exceptions."""
        from app.cli import clear_seed_data

        mock_seeding_service.return_value.clear_all_data.side_effect = Exception("Clear failed")

        runner = CliRunner()
        result = runner.invoke(clear_seed_data, ["--confirm"])

        assert result.exit_code == 1

    def test_clear_seed_data_no_confirm(self) -> None:
        """Test that clear_seed_data requires confirmation."""
        from app.cli import clear_seed_data

        runner = CliRunner()
        result = runner.invoke(clear_seed_data)

        assert result.exit_code == 1


class TestCLIVerboseOutput:
    """Test verbose output in CLI commands."""

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_seed_verbose_output(
        self, mock_seeding_service: MagicMock, mock_init_db: MagicMock
    ) -> None:
        """Test verbose output in seed command."""
        from app.cli import seed

        mock_seeder = MagicMock()
        mock_seeder.seed_all.return_value = {"users": ["user1", "user2"], "templates": []}
        mock_seeding_service.return_value = mock_seeder

        runner = CliRunner()
        result = runner.invoke(seed, ["--users", "2", "--verbose"])

        # Should complete successfully
        assert result.exit_code == 0

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_seed_clear_verbose(
        self, mock_seeding_service: MagicMock, mock_init_db: MagicMock
    ) -> None:
        """Test verbose output with clear flag."""
        from app.cli import seed

        mock_seeder = MagicMock()
        mock_seeder.clear_all_data.return_value = {"users": 5, "sessions": 3}
        mock_seeding_service.return_value = mock_seeder

        runner = CliRunner()
        result = runner.invoke(seed, ["--users", "2", "--clear", "--verbose"])

        assert result.exit_code == 0


class TestCLIMigrateVerbose:
    """Test verbose flag in migrate command."""

    @patch("alembic.command.upgrade")
    def test_migrate_verbose(self, mock_upgrade: MagicMock) -> None:
        """Test migrate with verbose flag."""
        from app.cli import migrate

        runner = CliRunner()
        result = runner.invoke(migrate, ["--revision", "head", "--verbose"])

        assert result.exit_code == 0


class TestCLIWorkerOptions:
    """Test various worker options."""

    @patch("app.celery_app.celery_app")
    def test_worker_with_hostname(self, mock_celery: MagicMock) -> None:
        """Test worker with custom hostname."""
        from app.cli import worker

        runner = CliRunner()
        result = runner.invoke(worker, ["--hostname", "worker1@localhost"])

        assert result.exit_code == 0
        # Verify hostname was passed to celery
        call_args = mock_celery.start.call_args[0][0]
        assert any("--hostname=worker1@localhost" in arg for arg in call_args)

    @patch("app.celery_app.celery_app")
    def test_worker_default_options(self, mock_celery: MagicMock) -> None:
        """Test worker with default options."""
        from app.cli import worker

        runner = CliRunner()
        result = runner.invoke(worker)

        assert result.exit_code == 0
        call_args = mock_celery.start.call_args[0][0]
        assert "worker" in call_args
        assert any("--queues=celery" in arg for arg in call_args)
        assert any("--concurrency=1" in arg for arg in call_args)
        assert any("--loglevel=info" in arg for arg in call_args)


class TestCLISeedEdgeCases:
    """Test edge cases in seed command."""

    @patch("app.database.connection.init_db")
    @patch("app.services.seeding_service.DatabaseSeedingService")
    def test_seed_zero_counts(
        self, mock_seeding_service: MagicMock, mock_init_db: MagicMock
    ) -> None:
        """Test seed with zero counts."""
        from app.cli import seed

        mock_seeder = MagicMock()
        mock_seeder.seed_all.return_value = {}
        mock_seeding_service.return_value = mock_seeder

        runner = CliRunner()
        result = runner.invoke(seed, ["--users", "0", "--sessions", "0"])

        assert result.exit_code == 0
