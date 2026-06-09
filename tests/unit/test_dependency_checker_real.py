"""
Unit tests for dependency_checker.py that execute real code paths.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.dependency_checker import (
    HARD_DEPENDENCIES,
    SOFT_DEPENDENCIES,
    check_dependencies,
    check_optional_dependencies,
    check_package_version,
    get_module_version,
    get_package_import_name,
    parse_version,
)


class TestGetPackageImportName:
    """Test get_package_import_name function."""

    def test_get_package_import_name_mapping(self):
        """Test package name mapping."""
        assert get_package_import_name("pyjwt") == "jwt"
        assert get_package_import_name("python-dotenv") == "dotenv"
        assert get_package_import_name("prometheus-client") == "prometheus_client"
        assert get_package_import_name("pydantic-settings") == "pydantic_settings"
        assert get_package_import_name("psycopg2-binary") == "psycopg2"

    def test_get_package_import_name_default(self):
        """Test default package name conversion."""
        assert get_package_import_name("fastapi") == "fastapi"
        assert get_package_import_name("some-package") == "some_package"


class TestGetModuleVersion:
    """Test get_module_version function."""

    def test_get_module_version_success(self):
        """Test successful module version retrieval."""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.__version__ = "1.2.3"
            mock_import.return_value = mock_module
            assert get_module_version("some-package") == "1.2.3"

    def test_get_module_version_no_version_attr(self):
        """Test module without __version__ attribute."""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            del mock_module.__version__
            mock_import.return_value = mock_module
            assert get_module_version("some-package") is None

    def test_get_module_version_import_error(self):
        """Test module import failure."""
        with patch("importlib.import_module", side_effect=ImportError()):
            assert get_module_version("non-existent") is None

    def test_get_module_version_generic_exception(self):
        """Test generic exception during import."""
        with patch("importlib.import_module", side_effect=Exception("Import failed")):
            assert get_module_version("some-package") is None


class TestParseVersion:
    """Test parse_version function."""

    def test_parse_version_none(self):
        """Test parsing None."""
        assert parse_version(None) == (0, 0, 0)

    def test_parse_version_empty_string(self):
        """Test parsing empty string."""
        assert parse_version("") == (0, 0, 0)

    def test_parse_version_simple(self):
        """Test parsing simple version."""
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_parse_version_two_parts(self):
        """Test parsing version with two parts."""
        assert parse_version("1.2") == (1, 2, 0)

    def test_parse_version_one_part(self):
        """Test parsing version with one part."""
        assert parse_version("1") == (1, 0, 0)

    def test_parse_version_with_extras(self):
        """Test parsing version with extra info."""
        assert parse_version("2.9.11 (dt dec pq3 ext lo64)") == (2, 9, 11)
        assert parse_version("1.0.0rc1") == (1, 0, 0)
        assert parse_version("3.2.1-beta") == (3, 2, 1)

    def test_parse_version_invalid(self):
        """Test parsing invalid version."""
        assert parse_version("invalid") == (0, 0, 0)
        assert parse_version("a.b.c") == (0, 0, 0)

    def test_parse_version_value_error(self):
        """Test parsing version with very large numbers."""
        # Python int can handle arbitrarily large numbers, so this doesn't raise ValueError
        # The implementation extracts numeric parts and converts them to int
        assert parse_version(
            "999999999999999999999.999999999999999999999.999999999999999999999"
        ) == (999999999999999999999, 999999999999999999999, 999999999999999999999)


class TestCheckPackageVersion:
    """Test check_package_version function."""

    def test_check_package_version_satisfied(self):
        """Test when package version is satisfied."""
        with patch("app.dependency_checker.get_module_version", return_value="1.2.3"):
            satisfied, version, error = check_package_version("pkg", "1.0.0")
            assert satisfied is True
            assert version == "1.2.3"
            assert error is None

    def test_check_package_version_not_satisfied(self):
        """Test when package version is too low."""
        with patch("app.dependency_checker.get_module_version", return_value="0.9.0"):
            satisfied, version, error = check_package_version("pkg", "1.0.0")
            assert satisfied is False
            assert version == "0.9.0"
            assert "version 0.9.0 is installed" in error

    def test_check_package_version_not_found_module(self):
        """Test when package not found via module."""
        with patch("app.dependency_checker.get_module_version", return_value=None):
            with patch("importlib.metadata.version", side_effect=Exception("PackageNotFoundError")):
                satisfied, version, error = check_package_version("pkg", "1.0.0")
                assert satisfied is False
                assert version is None
                assert "Error checking package" in error

    def test_check_package_version_not_found_metadata(self):
        """Test when package not found via metadata."""
        with patch("app.dependency_checker.get_module_version", return_value=None):
            with patch("importlib.metadata.version", side_effect=Exception("PackageNotFoundError")):
                satisfied, version, error = check_package_version("pkg", "1.0.0")
                assert satisfied is False
                assert version is None
                assert "Error checking package" in error

    def test_check_package_version_metadata_fallback(self):
        """Test metadata fallback when module version is None."""
        with patch("app.dependency_checker.get_module_version", return_value=None):
            with patch("importlib.metadata.version", return_value="2.0.0"):
                satisfied, version, error = check_package_version("pkg", "1.0.0")
                assert satisfied is True
                assert version == "2.0.0"
                assert error is None


class TestCheckDependencies:
    """Test check_dependencies function."""

    def test_check_dependencies_all_satisfied(self):
        """Test when all dependencies are satisfied."""
        with patch(
            "app.dependency_checker.check_package_version", return_value=(True, "1.0.0", None)
        ):
            result = check_dependencies({"pkg1": "1.0.0", "pkg2": "2.0.0"}, fail_fast=False)
            assert result is True

    def test_check_dependencies_missing_package_fail_fast(self):
        """Test missing package with fail_fast=True."""
        with patch(
            "app.dependency_checker.check_package_version",
            return_value=(False, None, "Package not found"),
        ):
            with pytest.raises(SystemExit) as excinfo:
                check_dependencies({"pkg": "1.0.0"}, fail_fast=True)
            assert excinfo.value.code == 1

    def test_check_dependencies_missing_package_no_fail_fast(self):
        """Test missing package with fail_fast=False."""
        with patch(
            "app.dependency_checker.check_package_version",
            return_value=(False, None, "Package not found"),
        ):
            result = check_dependencies({"pkg": "1.0.0"}, fail_fast=False)
            assert result is False

    def test_check_dependencies_version_mismatch(self):
        """Test version mismatch."""
        with patch(
            "app.dependency_checker.check_package_version",
            return_value=(False, "0.9.0", "Version mismatch"),
        ):
            result = check_dependencies({"pkg": "1.0.0"}, fail_fast=False)
            assert result is False

    def test_check_dependencies_multiple_errors(self):
        """Test multiple dependency errors."""
        results = [(False, None, "Missing"), (False, "0.8.0", "Mismatch")]
        with patch("app.dependency_checker.check_package_version", side_effect=results):
            result = check_dependencies({"p1": "1.0.0", "p2": "1.0.0"}, fail_fast=False)
            assert result is False

    def test_check_dependencies_uses_default(self):
        """Test using default REQUIRED_DEPENDENCIES when None passed."""
        with patch(
            "app.dependency_checker.check_package_version", return_value=(True, "1.0.0", None)
        ):
            result = check_dependencies(None, fail_fast=False)
            assert result is True

    def test_check_dependencies_logs_success(self):
        """Test that successful check logs appropriately."""
        with patch(
            "app.dependency_checker.check_package_version", return_value=(True, "1.0.0", None)
        ):
            with patch("app.dependency_checker.logger") as mock_logger:
                check_dependencies({"pkg": "1.0.0"}, fail_fast=False)
                # Should log info about checking and success
                assert mock_logger.info.called


class TestCheckOptionalDependencies:
    """Test check_optional_dependencies function."""

    def test_check_optional_dependencies_all_available(self):
        """Test when all optional dependencies are available."""
        results = [(True, "1.0.0", None), (True, "2.0.0", None)]
        with patch("app.dependency_checker.check_package_version", side_effect=results):
            result = check_optional_dependencies({"p1": "1.0.0", "p2": "2.0.0"})
            assert result["p1"] is True
            assert result["p2"] is True

    def test_check_optional_dependencies_mixed(self):
        """Test mixed availability."""
        results = [(True, "1.0.0", None), (False, None, "error")]
        with patch("app.dependency_checker.check_package_version", side_effect=results):
            result = check_optional_dependencies({"p1": "1.0.0", "p2": "1.0.0"})
            assert result["p1"] is True
            assert result["p2"] is False

    def test_check_optional_dependencies_none_available(self):
        """Test when none are available."""
        results = [(False, None, "error"), (False, None, "error")]
        with patch("app.dependency_checker.check_package_version", side_effect=results):
            result = check_optional_dependencies({"p1": "1.0.0", "p2": "1.0.0"})
            assert result["p1"] is False
            assert result["p2"] is False


class TestConstants:
    """Test module constants."""

    def test_hard_dependencies_defined(self):
        """Test HARD_DEPENDENCIES is defined."""
        assert isinstance(HARD_DEPENDENCIES, dict)
        assert len(HARD_DEPENDENCIES) > 0
        assert "fastapi" in HARD_DEPENDENCIES
        assert "uvicorn" in HARD_DEPENDENCIES

    def test_soft_dependencies_defined(self):
        """Test SOFT_DEPENDENCIES is defined."""
        assert isinstance(SOFT_DEPENDENCIES, dict)
        assert len(SOFT_DEPENDENCIES) > 0
        assert "redis" in SOFT_DEPENDENCIES
        assert "celery" in SOFT_DEPENDENCIES

    def test_required_dependencies_union(self):
        """Test REQUIRED_DEPENDENCIES is union of hard and soft."""
        from app.dependency_checker import REQUIRED_DEPENDENCIES

        assert isinstance(REQUIRED_DEPENDENCIES, dict)
        assert len(REQUIRED_DEPENDENCIES) == len(HARD_DEPENDENCIES) + len(SOFT_DEPENDENCIES)
