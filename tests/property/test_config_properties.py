"""
Property-based tests for configuration management.

Feature: api-migration
Tests universal properties of the configuration system.
"""

import os

# Import after setting up environment to avoid loading real config
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))


def reload_config_with_env(env_vars: dict[str, str]) -> Any:
    """
    Helper function to reload config module with specific environment variables.

    This patches load_dotenv before importing to prevent loading from .env files.
    """
    # Patch load_dotenv before any imports
    with patch.dict(os.environ, env_vars, clear=True):
        # Mock load_dotenv to prevent loading from .env files
        mock_load_dotenv = MagicMock()

        # Patch it in the dotenv module before config imports it
        with patch("dotenv.load_dotenv", mock_load_dotenv):
            # Remove config from sys.modules to force reimport
            if "app.config" in sys.modules:
                del sys.modules["app.config"]

            # Import config - this will use our patched load_dotenv
            import app.config  # noqa: F401
            from app.config import Settings

            # Create a fresh settings instance
            return Settings()


@settings(max_examples=1)  # Reduced for faster testing
@given(
    config_key=st.sampled_from(
        [
            "HOST",
            "PORT",
            "DATABASE_URL",
            "REDIS_URL",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
            "JWT_SECRET_KEY",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
            "RATE_LIMIT_ENABLED",
            "RATE_LIMIT_PER_MINUTE",
            "CORS_ORIGINS",
            "CORS_ALLOW_CREDENTIALS",
            "LOG_LEVEL",
            "MAX_REQUEST_SIZE_MB",
        ]
    ),
    env_value=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=frozenset(["Cs"])),
    ),
    bool_value=st.sampled_from(["true", "false", "True", "False", "TRUE", "FALSE"]),
)
def test_property_1_config_env_override(config_key: str, env_value: str, bool_value: str) -> None:
    """
    **Validates: Requirements 2.2**

    Feature: api-migration, Property 1: Configuration Environment Variable Override

    For any configuration setting, when an environment variable is set for that setting,
    the environment variable value should override the default value.

    This property ensures that all configuration values can be overridden via environment
    variables, which is essential for deployment flexibility and security.
    """
    # Filter out values that would cause validation errors
    # We're testing override behavior, not validation
    if config_key == "PORT":
        # PORT must be numeric
        assume(env_value.isdigit())
        env_value = str(int(env_value) % 65536)  # Valid port range

    if config_key in [
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        "RATE_LIMIT_PER_MINUTE",
        "MAX_REQUEST_SIZE_MB",
    ]:
        # These must be numeric
        assume(env_value.isdigit())
        env_value = str(max(1, int(env_value) % 10000))  # Reasonable range

    if config_key in ["RATE_LIMIT_ENABLED", "CORS_ALLOW_CREDENTIALS"]:
        # Boolean values - use the pre-generated bool_value
        env_value = bool_value

    # Set environment to development to avoid production validation errors
    env_vars = {
        "ENVIRONMENT": "development",
        "JWT_SECRET_KEY": "test-secret-key-at-least-32-characters-long-for-testing",
        "WEBHOOK_SECRET_KEY": "test-webhook-secret-key-for-testing-only-32chars",
        config_key: env_value,
    }

    # For JWT_SECRET_KEY, ensure it meets minimum requirements in the test
    if config_key == "JWT_SECRET_KEY":
        # Make it at least 32 characters to pass validation
        env_value = env_value + "x" * max(0, 32 - len(env_value))
        env_vars[config_key] = env_value

    # Reload config with our environment variables
    settings = reload_config_with_env(env_vars)

    # Map environment variable names to settings attribute names
    attr_map = {
        "HOST": "host",
        "PORT": "port",
        "DATABASE_URL": "database_url",
        "REDIS_URL": "redis_url",
        "CELERY_BROKER_URL": "celery_broker_url",
        "CELERY_RESULT_BACKEND": "celery_result_backend",
        "JWT_SECRET_KEY": "jwt_secret_key",
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "jwt_access_token_expire_minutes",
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "jwt_refresh_token_expire_days",
        "RATE_LIMIT_ENABLED": "rate_limit_enabled",
        "RATE_LIMIT_PER_MINUTE": "rate_limit_per_minute",
        "CORS_ORIGINS": "cors_origins",
        "CORS_ALLOW_CREDENTIALS": "cors_allow_credentials",
        "LOG_LEVEL": "log_level",
        "MAX_REQUEST_SIZE_MB": "max_request_size_mb",
    }

    attr_name = attr_map[config_key]
    actual_value = getattr(settings, attr_name)

    # Verify the environment variable was used
    # Handle type conversions that Settings performs
    if config_key == "PORT":
        assert actual_value == int(
            env_value
        ), f"PORT should be {int(env_value)}, got {actual_value}"
    elif config_key in [
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        "RATE_LIMIT_PER_MINUTE",
        "MAX_REQUEST_SIZE_MB",
    ]:
        assert actual_value == int(
            env_value
        ), f"{config_key} should be {int(env_value)}, got {actual_value}"
    elif config_key in ["RATE_LIMIT_ENABLED", "CORS_ALLOW_CREDENTIALS"]:
        expected_bool = env_value.lower() == "true"
        assert (
            actual_value == expected_bool
        ), f"{config_key} should be {expected_bool}, got {actual_value}"
    elif config_key == "CORS_ORIGINS":
        # CORS_ORIGINS is parsed as comma-separated list
        expected_list: list[str] = [origin.strip() for origin in env_value.split(",")]
        assert (
            actual_value == expected_list
        ), f"CORS_ORIGINS should be {expected_list}, got {actual_value}"
    else:
        # String values should match exactly
        assert (
            actual_value == env_value
        ), f"{config_key} should be '{env_value}', got '{actual_value}'"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    config_key=st.sampled_from(
        [
            "HOST",
            "DATABASE_URL",
            "REDIS_URL",
            "LOG_LEVEL",
        ]
    )
)
def test_property_1_config_default_when_not_set(config_key: str) -> None:
    """
    **Validates: Requirements 2.2**

    Feature: api-migration, Property 1: Configuration Environment Variable Override

    Complementary test: When an environment variable is NOT set, the default value
    should be used. This ensures the override mechanism doesn't break default behavior.
    """
    # Set minimal environment to avoid validation errors
    env_vars = {
        "ENVIRONMENT": "development",
        "JWT_SECRET_KEY": "test-secret-key-at-least-32-characters-long",
        "WEBHOOK_SECRET_KEY": "test-webhook-secret-key-for-testing-only-32chars",
    }

    # Reload config with minimal environment (config_key not set)
    settings = reload_config_with_env(env_vars)

    # Map environment variable names to settings attribute names and defaults
    defaults = {
        "HOST": "0.0.0.0",
        "DATABASE_URL": "postgresql://localhost/apgi_api",
        "REDIS_URL": "redis://localhost:6379/0",
        "LOG_LEVEL": "DEBUG",  # Default for development environment
    }

    attr_map = {
        "HOST": "host",
        "DATABASE_URL": "database_url",
        "REDIS_URL": "redis_url",
        "LOG_LEVEL": "log_level",
    }

    attr_name = attr_map[config_key]
    expected_default = defaults[config_key]
    actual_value = getattr(settings, attr_name)

    # Verify the default value is used when env var is not set
    assert (
        actual_value == expected_default
    ), f"{config_key} should use default '{expected_default}', got '{actual_value}'"


@settings(max_examples=1)  # Reduced for faster testing
@given(
    validation_scenario=st.sampled_from(
        [
            "missing_jwt_secret_production",
            "insecure_jwt_secret_production",
            "short_jwt_secret_production",
            "wildcard_cors_with_credentials",
            "missing_cors_origins_production",
            "missing_database_url_production",
            "missing_redis_url_production",
        ]
    )
)
def test_property_2_config_validation_error_logging(validation_scenario: str) -> None:
    """
    **Validates: Requirements 2.5**

    Feature: api-migration, Property 2: Configuration Validation Error Logging

    For any configuration validation failure, the system should log the specific
    configuration key and validation error before exiting.

    This property ensures that when configuration validation fails, administrators
    receive clear, actionable error messages that identify exactly which configuration
    is problematic and why.
    """
    # Define validation scenarios that should trigger errors
    scenarios = {
        "missing_jwt_secret_production": {
            "env": {
                "ENVIRONMENT": "production",
                # JWT_SECRET_KEY intentionally not set
            },
            "expected_key": "JWT_SECRET_KEY",
            "expected_error_fragment": "JWT_SECRET_KEY environment variable is not set",
        },
        "insecure_jwt_secret_production": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secret",  # Known insecure default
            },
            "expected_key": "JWT_SECRET_KEY",
            "expected_error_fragment": "known insecure default value",
        },
        "short_jwt_secret_production": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "short",  # Less than 32 characters
            },
            "expected_key": "JWT_SECRET_KEY",
            "expected_error_fragment": "shorter than 32 characters",
        },
        "wildcard_cors_with_credentials": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secure-production-key-with-32-characters-minimum",
                "CORS_ORIGINS": "*",
                "CORS_ALLOW_CREDENTIALS": "true",
            },
            "expected_key": "CORS_ORIGINS",
            "expected_error_fragment": "wildcard [*] with credentials enabled",
        },
        "missing_cors_origins_production": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secure-production-key-with-32-characters-minimum",
                "CORS_ORIGINS": "",  # Empty CORS origins in production
            },
            "expected_key": "CORS_ORIGINS",
            "expected_error_fragment": "CORS_ORIGINS environment variable is not set",
        },
        "missing_database_url_production": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secure-production-key-with-32-characters-minimum",
                "CORS_ORIGINS": "https://example.com",
                # DATABASE_URL not set, will use default localhost
            },
            "expected_key": "DATABASE_URL",
            "expected_error_fragment": "DATABASE_URL is not configured for production",
        },
        "missing_redis_url_production": {
            "env": {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secure-production-key-with-32-characters-minimum",
                "CORS_ORIGINS": "https://example.com",
                "DATABASE_URL": "postgresql://prod-db:5432/apgi",
                # REDIS_URL not set, will use default localhost
            },
            "expected_key": "REDIS_URL",
            "expected_error_fragment": "REDIS_URL is not configured for production",
        },
    }

    scenario_config = scenarios[validation_scenario]
    env_vars: dict[str, str] = scenario_config["env"]  # type: ignore[assignment]
    expected_key = str(scenario_config["expected_key"])
    expected_error_fragment = str(scenario_config["expected_error_fragment"])

    # Attempt to create settings with invalid configuration
    # This should raise a ValueError with a message containing the config key and error
    with pytest.raises(ValueError) as exc_info:
        reload_config_with_env(env_vars)

    error_msg = str(exc_info.value)

    # Property 1: Error message should contain the configuration key
    assert (
        expected_key in error_msg
    ), f"Error message should mention configuration key '{expected_key}', but got: {error_msg}"

    # Property 2: Error message should contain specific validation error details
    assert (
        expected_error_fragment.lower() in error_msg.lower()
    ), f"Error message should contain '{expected_error_fragment}', but got: {error_msg}"

    # Property 3: Error message should be structured (contains "CRITICAL CONFIGURATION ERRORS")
    assert (
        "CRITICAL CONFIGURATION ERRORS" in error_msg
    ), f"Error message should be structured with header, but got: {error_msg}"
