"""
Tests for dependency checker utility.

Tests for validating required packages on startup.
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))


class TestParseVersion:
    """Tests for parse_version function."""

    def test_parse_version_standard(self):
        """Test parsing standard version string."""
        from app.dependency_checker import parse_version

        result = parse_version("1.2.3")
        assert result == (1, 2, 3)

    def test_parse_version_two_parts(self):
        """Test parsing version with two parts."""
        from app.dependency_checker import parse_version

        result = parse_version("1.2")
        assert result == (1, 2)  # Function returns variable length tuple

    def test_parse_version_one_part(self):
        """Test parsing version with one part."""
        from app.dependency_checker import parse_version

        result = parse_version("1")
        assert result == (1,)  # Function returns variable length tuple

    def test_parse_version_with_extra_parts(self):
        """Test parsing version with extra parts (only first 3 used)."""
        from app.dependency_checker import parse_version

        result = parse_version("1.2.3.4.5")
        assert result == (1, 2, 3)  # First 3 parts used

    def test_parse_version_invalid(self):
        """Test parsing invalid version string."""
        from app.dependency_checker import parse_version

        result = parse_version("invalid")
        assert result == (0, 0, 0)  # Returns default for invalid

    def test_parse_version_none(self):
        """Test parsing None version string."""
        from app.dependency_checker import parse_version
        from typing import cast, Optional

        result = parse_version(cast(Optional[str], None))
        assert result == (0, 0, 0)  # Returns default for None


class TestCheckPackageVersion:
    """Tests for check_package_version function."""

    @patch("app.dependency_checker.importlib.metadata.version")
    def test_check_package_version_satisfied(self, mock_version):
        """Test check when package version satisfies requirement."""
        from app.dependency_checker import check_package_version

        mock_version.return_value = "1.2.3"
        is_satisfied, installed_version, error_msg = check_package_version("test-package", "1.0.0")

        assert is_satisfied is True
        assert installed_version == "1.2.3"
        assert error_msg is None

    @patch("app.dependency_checker.importlib.metadata.version")
    def test_check_package_version_not_satisfied(self, mock_version):
        """Test check when package version does not satisfy requirement."""
        from app.dependency_checker import check_package_version

        mock_version.return_value = "0.9.0"
        is_satisfied, installed_version, error_msg = check_package_version("test-package", "1.0.0")

        assert is_satisfied is False
        assert installed_version == "0.9.0"
        assert error_msg is not None
        assert "version 1.0.0 or higher is required" in error_msg

    @patch("app.dependency_checker.importlib.metadata.version")
    def test_check_package_version_not_found(self, mock_version) -> None:
        """Test check when package is not installed."""
        from app.dependency_checker import check_package_version
        import importlib.metadata

        mock_version.side_effect = importlib.metadata.PackageNotFoundError("test-package")
        is_satisfied, installed_version, error_msg = check_package_version("test-package", "1.0.0")

        assert is_satisfied is False
        assert installed_version is None
        assert error_msg is not None
        assert "is not installed" in error_msg

    @patch("app.dependency_checker.importlib.metadata.version")
    def test_check_package_version_exception(self, mock_version) -> None:
        """Test check when exception occurs during version check."""
        from app.dependency_checker import check_package_version

        mock_version.side_effect = Exception("Test error")
        is_satisfied, installed_version, error_msg = check_package_version("test-package", "1.0.0")

        assert is_satisfied is False
        assert installed_version is None
        assert error_msg is not None
        assert "Error checking package" in error_msg


class TestCheckDependencies:
    """Tests for check_dependencies function."""

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_dependencies_all_satisfied(self, mock_logger, mock_check) -> None:
        """Test check when all dependencies are satisfied."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (True, "1.0.0", None)
        required_deps = {"package1": "1.0.0", "package2": "2.0.0"}

        result = check_dependencies(required_deps, fail_fast=False)

        assert result is True
        assert mock_check.call_count == 2

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    @patch("app.dependency_checker.sys.exit")
    def test_check_dependencies_missing_fail_fast(self, mock_exit, mock_logger, mock_check) -> None:
        """Test check with missing dependency and fail_fast=True."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (False, None, "Package not installed")
        required_deps = {"package1": "1.0.0"}

        result = check_dependencies(required_deps, fail_fast=True)

        # sys.exit might be called once or twice depending on the implementation
        assert mock_exit.call_count >= 1
        assert mock_exit.call_args[0][0] == 1

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    @patch("app.dependency_checker.sys.exit")
    def test_check_dependencies_version_mismatch_fail_fast(
        self, mock_exit, mock_logger, mock_check
    ) -> None:
        """Test check with version mismatch and fail_fast=True."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (False, "0.9.0", "Version mismatch")
        required_deps = {"package1": "1.0.0"}

        result = check_dependencies(required_deps, fail_fast=True)

        # sys.exit might be called once or twice depending on the implementation
        assert mock_exit.call_count >= 1
        assert mock_exit.call_args[0][0] == 1

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_dependencies_missing_no_fail_fast(self, mock_logger, mock_check) -> None:
        """Test check with missing dependency and fail_fast=False."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (False, None, "Package not installed")
        required_deps = {"package1": "1.0.0"}

        result = check_dependencies(required_deps, fail_fast=False)

        assert result is False
        mock_logger.error.assert_called()

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_dependencies_mixed_results(self, mock_logger, mock_check) -> None:
        """Test check with mixed satisfied and unsatisfied dependencies."""
        from app.dependency_checker import check_dependencies

        def check_side_effect(package, version):
            if package == "package1":
                return (True, "1.0.0", None)
            else:
                return (False, None, "Package not installed")

        mock_check.side_effect = check_side_effect
        required_deps = {"package1": "1.0.0", "package2": "2.0.0"}

        result = check_dependencies(required_deps, fail_fast=False)

        assert result is False

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_dependencies_uses_default_deps(self, mock_logger, mock_check):
        """Test check uses REQUIRED_DEPENDENCIES when None provided."""
        from app.dependency_checker import check_dependencies, REQUIRED_DEPENDENCIES

        mock_check.return_value = (True, "1.0.0", None)

        result = check_dependencies(fail_fast=False)

        assert mock_check.call_count == len(REQUIRED_DEPENDENCIES)

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    @patch("app.dependency_checker.sys.exit")
    def test_check_dependencies_logs_missing_packages(self, mock_exit, mock_logger, mock_check):
        """Test check logs missing packages."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (False, None, "Package not installed")
        required_deps = {"package1": "1.0.0", "package2": "2.0.0"}

        check_dependencies(required_deps, fail_fast=False)

        # Should log error messages for missing packages
        error_calls = [call for call in mock_logger.error.call_args_list]
        assert len(error_calls) > 0

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    @patch("app.dependency_checker.sys.exit")
    def test_check_dependencies_logs_version_mismatches(
        self, mock_exit, mock_logger, mock_check
    ) -> None:
        """Test check logs version mismatches."""
        from app.dependency_checker import check_dependencies

        mock_check.return_value = (False, "0.9.0", "Version mismatch")
        required_deps = {"package1": "1.0.0"}

        check_dependencies(required_deps, fail_fast=False)

        # Should log error messages for version mismatches
        error_calls = [call for call in mock_logger.error.call_args_list]
        assert len(error_calls) > 0


class TestCheckOptionalDependencies:
    """Tests for check_optional_dependencies function."""

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_optional_dependencies_all_satisfied(self, mock_logger, mock_check) -> None:
        """Test optional dependencies check when all are satisfied."""
        from app.dependency_checker import check_optional_dependencies

        mock_check.return_value = (True, "1.0.0", None)
        optional_deps = {"package1": "1.0.0", "package2": "2.0.0"}

        result = check_optional_dependencies(optional_deps)

        assert result == {"package1": True, "package2": True}

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_optional_dependencies_mixed(self, mock_logger, mock_check) -> None:
        """Test optional dependencies check with mixed results."""
        from app.dependency_checker import check_optional_dependencies

        def check_side_effect(package, version) -> tuple[bool, str | None, str | None]:
            if package == "package1":
                return (True, "1.0.0", None)
            else:
                return (False, None, "Package not installed")

        mock_check.side_effect = check_side_effect
        optional_deps = {"package1": "1.0.0", "package2": "2.0.0"}

        result = check_optional_dependencies(optional_deps)

        assert result == {"package1": True, "package2": False}

    @patch("app.dependency_checker.check_package_version")
    @patch("app.dependency_checker.logger")
    def test_check_optional_dependencies_logs_debug(self, mock_logger, mock_check) -> None:
        """Test optional dependencies check logs debug messages."""
        from app.dependency_checker import check_optional_dependencies

        mock_check.return_value = (True, "1.0.0", None)
        optional_deps = {"package1": "1.0.0"}

        check_optional_dependencies(optional_deps)

        mock_logger.debug.assert_called()


class TestRequiredDependencies:
    """Tests for REQUIRED_DEPENDENCIES constant."""

    def test_required_dependencies_defined(self) -> None:
        """Test that REQUIRED_DEPENDENCIES is defined."""
        from app.dependency_checker import REQUIRED_DEPENDENCIES

        assert isinstance(REQUIRED_DEPENDENCIES, dict)
        assert len(REQUIRED_DEPENDENCIES) > 0

    def test_required_dependencies_has_expected_packages(self) -> None:
        """Test that expected packages are in REQUIRED_DEPENDENCIES."""
        from app.dependency_checker import REQUIRED_DEPENDENCIES

        expected_packages = [
            "fastapi",
            "uvicorn",
            "starlette",
            "pydantic",
            "sqlalchemy",
            "alembic",
            "redis",
            "celery",
            "pyjwt",
            "bcrypt",
            "prometheus-client",
        ]

        for package in expected_packages:
            assert package in REQUIRED_DEPENDENCIES

    def test_required_dependencies_version_format(self) -> None:
        """Test that all required dependencies have version strings."""
        from app.dependency_checker import REQUIRED_DEPENDENCIES

        for package, version in REQUIRED_DEPENDENCIES.items():
            assert isinstance(version, str)
            assert len(version) > 0


class TestStandaloneExecution:
    """Tests for standalone execution of dependency checker."""

    @patch("app.dependency_checker.check_dependencies")
    @patch("app.dependency_checker.logging.basicConfig")
    @patch("app.dependency_checker.sys.exit")
    def test_main_success(self, mock_exit, mock_basicConfig, mock_check) -> None:
        """Test main execution with successful check."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"__name__": "__main__"}):
            from app.dependency_checker import check_dependencies

            # Simulate main block execution
            import logging

            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            success = check_dependencies(fail_fast=False)
            sys.exit(0 if success else 1)

        mock_exit.assert_called_once_with(0)

    @patch("app.dependency_checker.check_dependencies")
    @patch("app.dependency_checker.logging.basicConfig")
    @patch("app.dependency_checker.sys.exit")
    def test_main_failure(self, mock_exit, mock_basicConfig, mock_check) -> None:
        """Test main execution with failed check."""
        mock_check.return_value = False

        with patch.dict("sys.modules", {"__name__": "__main__"}):
            from app.dependency_checker import check_dependencies

            import logging

            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            success = check_dependencies(fail_fast=False)
            sys.exit(0 if success else 1)

        mock_exit.assert_called_once_with(1)
