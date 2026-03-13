"""
Unit tests for cli.py module.
"""

from unittest.mock import patch
from app.cli import migrate


class TestCLI:
    """Test cli.py functionality."""

    def test_cli_migrate_help(self):
        """Test CLI migrate help command."""
        with patch("sys.argv", ["cli.py", "migrate", "--help"]):
            with patch("app.cli.migrate") as mock_migrate:
                mock_migrate.return_value = None

                migrate()

                mock_migrate.assert_called_once()

    def test_cli_migrate_version(self):
        """Test CLI migrate version command."""
        with patch("sys.argv", ["cli.py", "migrate", "--version"]):
            with patch("app.cli.migrate") as mock_migrate:
                mock_migrate.return_value = None

                migrate()

                mock_migrate.assert_called_once()

    def test_cli_migrate_invalid_command(self):
        """Test CLI with invalid migrate command."""
        with patch("sys.argv", ["cli.py", "migrate", "--invalid"]):
            with patch("app.cli.migrate") as mock_migrate:
                mock_migrate.return_value = None

                migrate()

                mock_migrate.assert_called_once()

    def test_cli_main_no_args(self):
        """Test CLI with no arguments."""
        with patch("sys.argv", ["cli.py"]):
            with patch("app.cli.migrate") as mock_migrate:
                mock_migrate.return_value = None

                migrate()

                mock_migrate.assert_called_once()
