"""Dependency checker utility for validating required packages on startup."""

import importlib
import importlib.metadata
import logging
import sys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PACKAGE_IMPORT_MAPPING = {
    "pyjwt": "jwt",
    "python-dotenv": "dotenv",
    "prometheus-client": "prometheus_client",
    "pydantic-settings": "pydantic_settings",
    "psycopg2-binary": "psycopg2",
}


def get_package_import_name(package_name: str) -> str:
    """Return the most likely Python module name for a distribution."""
    return PACKAGE_IMPORT_MAPPING.get(package_name, package_name.replace("-", "_"))


def get_module_version(package_name: str) -> Optional[str]:
    """Try to obtain version from the installed module before using metadata."""
    module_name = get_package_import_name(package_name)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None

    return getattr(module, "__version__", None)


# Critical dependencies required for API operation
REQUIRED_DEPENDENCIES = {
    "fastapi": "0.110.0",
    "uvicorn": "0.28.0",
    "starlette": "0.37.0",
    "pydantic": "2.8.0",
    "pydantic-settings": "2.3.0",
    "sqlalchemy": "2.0.30",
    "alembic": "1.13.0",
    "psycopg2-binary": "2.9.9",
    "redis": "5.0.1",
    "celery": "5.3.4",
    "pyjwt": "2.8.0",
    "bcrypt": "4.0.0",
    "prometheus-client": "0.19.0",
    "python-dotenv": "1.0.0",
}


def parse_version(version_str: Optional[str]) -> Tuple[int, ...]:
    """
    Parse version string into tuple of integers for comparison.

    Args:
        version_str: Version string like "1.2.3" or None

    Returns:
        Tuple of version components like (1, 2, 3) or (0, 0, 0) for invalid/None input
    """
    if not version_str:
        return (0, 0, 0)

    try:
        return tuple(int(x) for x in version_str.split(".")[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_package_version(
    package_name: str, minimum_version: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if a package is installed and meets minimum version requirement.

    Args:
        package_name: Name of the package to check
        minimum_version: Minimum required version string

    Returns:
        Tuple of (is_satisfied, installed_version, error_message)
    """
    installed_version: Optional[str] = None

    # Prefer reading the package's own version attribute before metadata-based discovery.
    installed_version = get_module_version(package_name)

    if installed_version is None:
        try:
            installed_version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            error_msg = f"Package '{package_name}' is not installed"
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error checking package '{package_name}': {str(e)}"
            return False, None, error_msg

    installed_tuple = parse_version(installed_version)
    required_tuple = parse_version(minimum_version)

    if installed_tuple >= required_tuple:
        return True, installed_version, None

    error_msg = (
        f"Package '{package_name}' version {installed_version} is installed, "
        f"but version {minimum_version} or higher is required"
    )
    return False, installed_version, error_msg


def check_dependencies(
    required_deps: Optional[Dict[str, str]] = None,
    fail_fast: bool = True,
) -> bool:
    """
    Validate that all required dependencies are installed with correct versions.

    Args:
        required_deps: Dictionary of package names to minimum versions.
                      If None, uses REQUIRED_DEPENDENCIES.
        fail_fast: If True, exit immediately on first missing dependency.
                  If False, check all dependencies and report all issues.

    Returns:
        True if all dependencies are satisfied, False otherwise

    Raises:
        SystemExit: If fail_fast is True and dependencies are missing
    """
    if required_deps is None:
        required_deps = REQUIRED_DEPENDENCIES

    logger.info("Checking required dependencies...")

    missing_packages: List[str] = []
    version_mismatches: List[str] = []
    all_satisfied = True

    for package_name, min_version in required_deps.items():
        is_satisfied, installed_version, error_msg = check_package_version(
            package_name, min_version
        )

        if not is_satisfied:
            all_satisfied = False

            if installed_version is None:
                missing_packages.append(package_name)
                logger.error(f"❌ {error_msg}")
            else:
                version_mismatches.append(package_name)
                logger.error(f"⚠️  {error_msg}")

            if fail_fast:
                logger.error("\nDependency check failed. Please install missing dependencies:")
                logger.error("  pip install -r requirements.txt")
                sys.exit(1)
        else:
            logger.debug(f"✓ {package_name} {installed_version} (>= {min_version})")

    if not all_satisfied:
        logger.error("\n" + "=" * 70)
        logger.error("DEPENDENCY CHECK FAILED")
        logger.error("=" * 70)

        if missing_packages:
            logger.error(f"\nMissing packages ({len(missing_packages)}):")
            for pkg in missing_packages:
                logger.error(f"  - {pkg}")

        if version_mismatches:
            logger.error(f"\nVersion mismatches ({len(version_mismatches)}):")
            for pkg in version_mismatches:
                min_ver = required_deps[pkg]
                logger.error(f"  - {pkg} (requires >= {min_ver})")

        logger.error("\nTo fix, run:")
        logger.error("  pip install -r requirements.txt")
        logger.error("=" * 70 + "\n")

        if fail_fast:
            sys.exit(1)

        return False

    logger.info(f"✓ All {len(required_deps)} required dependencies are satisfied")
    return True


def check_optional_dependencies(optional_deps: Dict[str, str]) -> Dict[str, bool]:
    """
    Check optional dependencies without failing.

    Args:
        optional_deps: Dictionary of package names to minimum versions

    Returns:
        Dictionary mapping package names to availability status
    """
    results = {}

    for package_name, min_version in optional_deps.items():
        is_satisfied, installed_version, error_msg = check_package_version(
            package_name, min_version
        )
        results[package_name] = is_satisfied

        if is_satisfied:
            logger.debug(f"✓ Optional: {package_name} {installed_version} (>= {min_version})")
        else:
            logger.debug(f"⚠️  Optional: {error_msg}")

    return results


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Run dependency check
    success = check_dependencies(fail_fast=False)
    sys.exit(0 if success else 1)
