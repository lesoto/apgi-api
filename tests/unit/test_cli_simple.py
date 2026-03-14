"""
Simple unit tests for cli.py module.
"""

from click.testing import CliRunner


def test_cli_group_exists():
    """Test that CLI group exists."""
    from app.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "APGI API command-line interface" in result.output


def test_migrate_command_exists():
    """Test that migrate command exists."""
    from app.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["migrate", "--help"])
    assert result.exit_code == 0
    assert "Run database migrations" in result.output


def test_worker_command_exists():
    """Test that worker command exists."""
    from app.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["worker", "--help"])
    assert result.exit_code == 0
    assert "Start Celery worker" in result.output


def test_seed_command_exists():
    """Test that seed command exists."""
    from app.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["seed", "--help"])
    assert result.exit_code == 0
    assert "Seed database with test data" in result.output


def test_clear_seed_data_command_exists():
    """Test that clear-seed-data command exists."""
    from app.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["clear-seed-data", "--help"])
    assert result.exit_code == 0
    assert "Clear all seeded test data" in result.output
