"""
Standalone API Configuration

Configuration settings for the standalone APGI REST API.
"""

import os
import warnings
from typing import List

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """
    API configuration settings.

    Settings can be overridden via environment variables.
    """

    def __init__(self):
        # Environment Detection
        self.environment: str = os.getenv("ENVIRONMENT", "development")

        # API Settings
        self.api_title: str = "APGI System API"
        self.api_version: str = "1.0.0"
        self.api_description: str = "REST API for consciousness modeling"

        # Server Settings
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.reload: bool = (
            os.getenv("RELOAD", "true").lower() == "true"
            if self.environment == "development"
            else False
        )

        # Database Settings
        self.database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/apgi_api")

        # Redis Settings
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Celery Settings
        self.celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        self.celery_result_backend: str = os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
        )

        # Authentication Settings
        self.jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
        self.jwt_algorithm: str = "HS256"
        self.jwt_access_token_expire_minutes: int = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.jwt_refresh_token_expire_days: int = int(
            os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )

        # Rate Limiting Settings
        self.rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

        # CORS Settings
        self.cors_origins: List[str] = self._parse_cors_origins()
        self.cors_allow_credentials: bool = (
            os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
        )
        self.cors_allow_methods: List[str] = (
            os.getenv("CORS_ALLOW_METHODS", "*").split(",")
            if os.getenv("CORS_ALLOW_METHODS")
            else ["*"]
        )
        self.cors_allow_headers: List[str] = (
            os.getenv("CORS_ALLOW_HEADERS", "*").split(",")
            if os.getenv("CORS_ALLOW_HEADERS")
            else ["*"]
        )

        # Logging Settings
        self.log_level: str = os.getenv("LOG_LEVEL", self._get_default_log_level())

        # Schema Validation Settings
        self.schema_validation_enabled: bool = (
            os.getenv("SCHEMA_VALIDATION_ENABLED", "true").lower() == "true"
        )
        self.schema_validation_fail_on_error: bool = (
            os.getenv("SCHEMA_VALIDATION_FAIL_ON_ERROR", "false").lower() == "true"
        )

        # Alerting Settings
        self.alert_webhook_urls: List[str] = (
            os.getenv("ALERT_WEBHOOK_URLS", "").split(",")
            if os.getenv("ALERT_WEBHOOK_URLS")
            else []
        )
        self.alert_enable_log_channel: bool = (
            os.getenv("ALERT_ENABLE_LOG_CHANNEL", "true").lower() == "true"
        )
        self.alert_error_rate_threshold: int = int(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "10"))
        self.alert_error_rate_window_minutes: int = int(
            os.getenv("ALERT_ERROR_RATE_WINDOW_MINUTES", "1")
        )
        self.alert_cooldown_minutes: int = int(os.getenv("ALERT_COOLDOWN_MINUTES", "5"))

        # Request Size Limiting
        self.max_request_size_mb: int = int(os.getenv("MAX_REQUEST_SIZE_MB", "10"))

        # Validate security settings after initialization
        self.__post_init__()

    def _parse_cors_origins(self) -> List[str]:
        """Parse CORS origins from environment variable."""
        cors_origins_env = os.getenv("CORS_ORIGINS")
        if cors_origins_env:
            return [origin.strip() for origin in cors_origins_env.split(",")]
        # Default origins for development
        if self.environment == "development":
            return ["http://localhost:3000", "http://localhost:8000"]
        # No default for production - must be explicitly configured
        return []

    def _get_default_log_level(self) -> str:
        """Get default log level based on environment."""
        if self.environment == "development":
            return "DEBUG"
        elif self.environment == "staging":
            return "INFO"
        elif self.environment in ["production", "prod"]:
            return "WARNING"
        return "INFO"

    def __post_init__(self):
        """Validate critical security settings after initialization."""
        errors = []

        # Environment-specific validation
        is_production = self.environment.lower() in ["production", "prod"]

        # Validate JWT secret key
        if not self.jwt_secret_key:
            if is_production:
                errors.append(
                    "JWT_SECRET_KEY environment variable is not set for production. "
                    "This is required for secure JWT token generation."
                )
            else:
                # Development mode - provide a secure default with warning
                self.jwt_secret_key = "development-secret-key-change-in-production-32-chars-min"
                warnings.warn(
                    "DEVELOPMENT WARNING: JWT_SECRET_KEY not set, using development default. "
                    "This is insecure and should NOT be used in production. "
                    "Set JWT_SECRET_KEY environment variable for production deployment.",
                    UserWarning,
                )

        # Check for known insecure default values
        if self.jwt_secret_key:
            insecure_defaults = [
                "your-secret-key-change-in-production",
                "secret",
                "default-secret",
                "change-me",
                "insecure-key",
            ]

            if self.jwt_secret_key.lower() in [d.lower() for d in insecure_defaults]:
                if is_production:
                    errors.append(
                        "JWT_SECRET_KEY is set to a known insecure default value in production. "
                        "This allows attackers to forge JWT tokens and bypass authentication."
                    )
                else:
                    warnings.warn(
                        "DEVELOPMENT WARNING: JWT_SECRET_KEY is set to a known insecure default value. "
                        "This should be changed before any production deployment.",
                        UserWarning,
                    )

            # Validate minimum key length
            if len(self.jwt_secret_key) < 32:
                if is_production:
                    errors.append(
                        "JWT_SECRET_KEY is shorter than 32 characters in production. "
                        "Short keys are vulnerable to brute force attacks. "
                        "Use a secure, random key with at least 32 characters."
                    )
                else:
                    warnings.warn(
                        "DEVELOPMENT WARNING: JWT_SECRET_KEY is shorter than 32 characters. "
                        "This should be fixed before production deployment.",
                        UserWarning,
                    )

        # Validate CORS origins
        if self.cors_origins == ["*"] or "*" in self.cors_origins:
            if self.cors_allow_credentials:
                errors.append(
                    "CORS origins are set to wildcard [*] with credentials enabled. "
                    "This allows any origin to access the API with credentials, enabling CSRF attacks. "
                    "Either set CORS_ORIGINS to specific allowed origins, or set CORS_ALLOW_CREDENTIALS=false."
                )
            else:
                warnings.warn(
                    "SECURITY WARNING: CORS origins are set to wildcard [*]. "
                    "This allows any origin to access the API. "
                    "Set CORS_ORIGINS environment variable to specific allowed origins for production.",
                    UserWarning,
                )
        elif not self.cors_origins and is_production:
            errors.append(
                "CORS_ORIGINS environment variable is not set for production. "
                "Explicitly configure allowed origins for security."
            )

        # Validate database URL for production
        if is_production:
            if not self.database_url or self.database_url == "postgresql://localhost/apgi_api":
                errors.append(
                    "DATABASE_URL is not configured for production. "
                    "Set DATABASE_URL environment variable with production database connection string."
                )
            elif not self.database_url.startswith(
                "postgresql://"
            ) and not self.database_url.startswith("postgres://"):
                warnings.warn(
                    "DATABASE_URL does not appear to be a PostgreSQL connection string. "
                    "Ensure you are using the correct database URL format.",
                    UserWarning,
                )

        # Validate Redis URL for production
        if is_production:
            if not self.redis_url or self.redis_url == "redis://localhost:6379/0":
                errors.append(
                    "REDIS_URL is not configured for production. "
                    "Set REDIS_URL environment variable with production Redis connection string."
                )

        # If there are critical errors in production, fail fast
        if errors:
            error_message = "CRITICAL CONFIGURATION ERRORS:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            raise ValueError(error_message)


# Global settings instance
settings = Settings()
