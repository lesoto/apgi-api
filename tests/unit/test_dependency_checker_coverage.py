"""
Coverage tests for app/dependency_checker.py
"""

from unittest.mock import MagicMock, patch

import pytest

from app.dependency_checker import (
    check_dependencies,
    check_optional_dependencies,
    check_package_version,
    get_module_version,
    parse_version,
)


def test_get_module_version_success():
    """Test get_module_version success path."""
    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.__version__ = "1.2.3"
        mock_import.return_value = mock_module
        assert get_module_version("some-package") == "1.2.3"


def test_get_module_version_failure():
    """Test get_module_version failure path."""
    with patch("importlib.import_module", side_effect=ImportError()):
        assert get_module_version("non-existent") is None


def test_parse_version_edge_cases():
    """Test parse_version with various inputs."""
    assert parse_version(None) == (0, 0, 0)
    assert parse_version("") == (0, 0, 0)
    assert parse_version("invalid") == (0, 0, 0)
    assert parse_version("1") == (1, 0, 0)
    assert parse_version("1.2") == (1, 2, 0)
    assert parse_version("2.9.11 (extra info)") == (2, 9, 11)


def test_check_package_version_not_installed():
    """Test check_package_version when not installed."""
    with patch("app.dependency_checker.get_module_version", return_value=None):
        with patch("importlib.metadata.version", side_effect=Exception("Metadata error")):
            satisfied, version, error = check_package_version("pkg", "1.0.0")
            assert satisfied is False
            assert "Error checking package" in error


def test_check_package_version_mismatch():
    """Test check_package_version when version is too low."""
    with patch("app.dependency_checker.get_module_version", return_value="0.9.0"):
        satisfied, version, error = check_package_version("pkg", "1.0.0")
        assert satisfied is False
        assert "version 0.9.0 is installed" in error


def test_check_dependencies_fail_fast():
    """Test check_dependencies with fail_fast=True."""
    with patch("app.dependency_checker.check_package_version", return_value=(False, None, "error")):
        with pytest.raises(SystemExit) as excinfo:
            check_dependencies({"pkg": "1.0.0"}, fail_fast=True)
        assert excinfo.value.code == 1


def test_check_dependencies_multiple_errors():
    """Test check_dependencies with multiple errors and fail_fast=False."""
    results = [(False, None, "Missing"), (False, "0.8.0", "Mismatch")]
    with patch("app.dependency_checker.check_package_version", side_effect=results):
        assert check_dependencies({"p1": "1.0.0", "p2": "1.0.0"}, fail_fast=False) is False


def test_check_optional_dependencies():
    """Test check_optional_dependencies."""
    results = [(True, "1.0.0", None), (False, None, "error")]
    with patch("app.dependency_checker.check_package_version", side_effect=results):
        results_map = check_optional_dependencies({"p1": "1.0.0", "p2": "1.0.0"})
        assert results_map["p1"] is True
        assert results_map["p2"] is False
