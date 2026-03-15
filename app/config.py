"""
Standalone API Configuration

Configuration settings for the standalone APGI REST API.
"""

import os
import warnings
from typing import List, Optional, Dict
from urllib.parse import urlparse

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

        # Validate environment
        ALLOWED_ENVIRONMENTS = ["development", "staging", "production", "prod"]
        if self.environment not in ALLOWED_ENVIRONMENTS:
            raise ValueError(
                f"Invalid ENVIRONMENT: {self.environment}. Must be one of {ALLOWED_ENVIRONMENTS}"
            )

        # API Settings
        self.api_title: str = "APGI System API"
        self.api_version: str = "1.0.0"
        self.api_description: str = "REST API for consciousness modeling"

        # Base URL for generating links
        self.base_url: str = os.getenv("BASE_URL", "https://localhost:8000")

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

        # Database Connection Pool Settings
        self.pool_size: int = int(os.getenv("POOL_SIZE", "20"))
        self.max_overflow: int = int(os.getenv("MAX_OVERFLOW", "30"))
        self.pool_timeout: int = int(os.getenv("POOL_TIMEOUT", "30"))
        self.pool_recycle: int = int(os.getenv("POOL_RECYCLE", "3600"))

        # Redis Settings
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Health Check Settings
        self.health_critical_services: List[str] = [
            s.strip() for s in os.getenv("HEALTH_CRITICAL_SERVICES", "redis,database").split(",")
        ]
        self.health_connectivity_threshold: float = float(
            os.getenv("HEALTH_CONNECTIVITY_THRESHOLD", "0.1")
        )
        self.health_query_threshold: float = float(os.getenv("HEALTH_QUERY_THRESHOLD", "0.5"))

        # Celery Settings
        self.celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        self.celery_result_backend: str = os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
        )

        # Cache TTL Settings
        self.cache_default_ttl: int = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
        self.cache_session_ttl_multiplier: int = int(
            os.getenv("CACHE_SESSION_TTL_MULTIPLIER", "24")
        )  # 24 hours
        self.cache_user_ttl_multiplier: int = int(
            os.getenv("CACHE_USER_TTL_MULTIPLIER", "2")
        )  # 2 hours
        self.cache_task_ttl_multiplier: int = int(
            os.getenv("CACHE_TASK_TTL_MULTIPLIER", "6")
        )  # 6 hours

        # Authentication Settings
        self.jwt_secret_key: Optional[str] = os.getenv("JWT_SECRET_KEY")
        self.cursor_signing_key: Optional[str] = os.getenv("CURSOR_SIGNING_KEY")
        self.webhook_secret_key: Optional[str] = os.getenv("WEBHOOK_SECRET_KEY")
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
        self.max_sessions_per_user: int = int(os.getenv("MAX_SESSIONS_PER_USER", "50"))

        # CORS Settings
        self.cors_origins: List[str] = self._parse_cors_origins()
        self.cors_allow_credentials: bool = (
            os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
        )
        cors_methods_env = os.getenv("CORS_ALLOW_METHODS")
        if cors_methods_env:
            self.cors_allow_methods: List[str] = [
                method.strip() for method in cors_methods_env.split(",") if method.strip()
            ]
        else:
            self.cors_allow_methods = [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS",
                "HEAD",
            ]
        cors_headers_env = os.getenv("CORS_ALLOW_HEADERS")
        if cors_headers_env:
            self.cors_allow_headers: List[str] = [
                header.strip() for header in cors_headers_env.split(",") if header.strip()
            ]
        else:
            # Explicit allowlist avoids the wildcard + credentials CORS spec conflict
            # (browsers reject credentialed requests when server returns Allow-Headers: *).
            self.cors_allow_headers = [
                "Authorization",
                "Content-Type",
                "X-CSRF-Token",
                "X-API-Key",
                "Idempotency-Key",
                "Accept",
                "Origin",
            ]

        # Logging Settings
        self.log_level: str = os.getenv("LOG_LEVEL", self._get_default_log_level())

        # Validate log level
        ALLOWED_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in ALLOWED_LOG_LEVELS:
            raise ValueError(
                f"Invalid LOG_LEVEL: {self.log_level}. Must be one of {ALLOWED_LOG_LEVELS}"
            )

        # Schema Validation Settings
        self.schema_validation_enabled: bool = (
            os.getenv("SCHEMA_VALIDATION_ENABLED", "true").lower() == "true"
        )
        self.schema_validation_fail_on_error: bool = (
            os.getenv("SCHEMA_VALIDATION_FAIL_ON_ERROR", "false").lower() == "true"
        )

        # Alerting Settings
        self.alert_webhook_urls: List[str] = (
            [url.strip() for url in os.getenv("ALERT_WEBHOOK_URLS", "").split(",") if url.strip()]
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

        # Email Settings for notifications and password reset
        self.smtp_server: Optional[str] = os.getenv("SMTP_SERVER")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username: Optional[str] = os.getenv("SMTP_USERNAME")
        self.smtp_password: Optional[str] = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "noreply@apgi-api.com")

        # Request Size Limiting
        self.max_request_size_mb: int = int(os.getenv("MAX_REQUEST_SIZE_MB", "10"))
        self.request_size_limit_enabled: bool = (
            os.getenv("REQUEST_SIZE_LIMIT_ENABLED", "true").lower() == "true"
        )

        # Webhook Settings
        self.webhook_retry_limit: int = int(os.getenv("WEBHOOK_RETRY_LIMIT", "5"))

        # Export Size Limiting
        self.max_export_mb: int = int(os.getenv("MAX_EXPORT_MB", "10"))
        self.max_export_points: int = int(os.getenv("MAX_EXPORT_POINTS", "100000"))

        # Task Execution Settings
        self.task_timeout_seconds: int = int(os.getenv("TASK_TIMEOUT_SECONDS", "3600"))

        # CSRF Protection Settings
        self.csrf_protection_enabled: bool = (
            os.getenv("CSRF_PROTECTION_ENABLED", "true").lower() == "true"
        )

        # Performance Profiling Settings
        self.profiling_enabled: bool = os.getenv("PROFILING_ENABLED", "false").lower() == "true"
        self.profiling_memory_enabled: bool = (
            os.getenv("PROFILING_MEMORY_ENABLED", "false").lower() == "true"
        )
        self.profiling_snapshot_interval_seconds: int = int(
            os.getenv("PROFILING_SNAPSHOT_INTERVAL_SECONDS", "60")
        )
        self.profiling_max_snapshots: int = int(os.getenv("PROFILING_MAX_SNAPSHOTS", "1000"))

        # Database Sharding Settings
        self.database_shards_enabled: bool = (
            os.getenv("DATABASE_SHARDS_ENABLED", "false").lower() == "true"
        )
        self.database_shards_count: int = int(os.getenv("DATABASE_SHARDS_COUNT", "1"))
        self.database_shard_key: str = os.getenv("DATABASE_SHARD_KEY", "user_id")
        self.database_shard_urls: Dict[int, str] = {}

        # Individual shard URLs (for when sharding is enabled)
        # These will be used by the sharding service
        for i in range(10):  # Support up to 10 shards for now
            shard_url = os.getenv(f"DATABASE_SHARD_{i}_URL")
            if shard_url:
                self.database_shard_urls[i] = shard_url

        # Stripe Settings
        self.stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
        self.stripe_publishable_key: str = os.getenv(
            "STRIPE_PUBLISHABLE_KEY", "pk_test_placeholder"
        )
        # Stripe webhook endpoint secret — required for signature verification.
        # Generate via Stripe dashboard → Webhooks → your endpoint → Signing secret.
        self.stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")

        # Validate security settings after initialization
        self.__post_init__()

    def _parse_cors_origins(self) -> List[str]:
        """Parse CORS origins from environment variable."""
        cors_origins_env = os.getenv("CORS_ORIGINS")
        if cors_origins_env:
            return [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
        # Default origins for development
        if self.environment == "development":
            return ["http://localhost:3000", "http://localhost:8000"]
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
            errors.append(
                "JWT_SECRET_KEY environment variable is not set. "
                "This is required for secure JWT token generation."
            )
        else:
            # Check for known insecure default values (using prefix/fuzzy matching)
            insecure_prefixes = [
                "your-secret-key",
                "your-cursor-signing-key",
                "your-webhook-secret-key",
                "secret",
                "default-secret",
                "change-me",
                "insecure-key",
                "development-secret-key",
                "test-secret",
                "example-secret",
            ]
            insecure_defaults = [
                "your-secret-key-change-in-production",
                "secret",
                "default-secret",
                "change-me",
                "insecure-key",
                "development-secret-key-change-in-production-32-chars-min",
            ]

            jwt_key_lower = self.jwt_secret_key.lower()
            is_insecure = jwt_key_lower in [d.lower() for d in insecure_defaults] or any(
                jwt_key_lower.startswith(prefix) for prefix in insecure_prefixes
            )
            if is_insecure:
                errors.append(
                    "JWT_SECRET_KEY is set to a known insecure default value. "
                    "This allows attackers to forge JWT tokens and bypass authentication."
                )

            # Validate minimum key length
            if len(self.jwt_secret_key) < 32:
                errors.append(
                    "JWT_SECRET_KEY is shorter than 32 characters. "
                    "Short keys are vulnerable to brute force attacks. "
                    "Use a secure, random key with at least 32 characters."
                )

        # Validate cursor signing key
        if not self.cursor_signing_key:
            errors.append(
                "CURSOR_SIGNING_KEY environment variable is not set. "
                "This is required for secure cursor signing in pagination."
            )
        else:
            # Check for known insecure default values
            if self.cursor_signing_key.lower() in [d.lower() for d in insecure_defaults]:
                errors.append(
                    "CURSOR_SIGNING_KEY is set to a known insecure default value. "
                    "This allows attackers to forge pagination cursors."
                )

            # Validate minimum key length
            if len(self.cursor_signing_key) < 32:
                errors.append(
                    "CURSOR_SIGNING_KEY is shorter than 32 characters. "
                    "Short keys are vulnerable to brute force attacks. "
                    "Use a secure, random key with at least 32 characters."
                )

        # Validate webhook secret key
        if not self.webhook_secret_key:
            if is_production:
                errors.append(
                    "WEBHOOK_SECRET_KEY environment variable is not set. "
                    "This is required for secure webhook signature verification in production."
                )
            else:
                warnings.warn(
                    "SECURITY WARNING: WEBHOOK_SECRET_KEY environment variable is not set. "
                    "Webhook signature verification will be disabled. Set WEBHOOK_SECRET_KEY for development/testing.",
                    UserWarning,
                )
        else:
            # Check for known insecure default values
            if self.webhook_secret_key.lower() in [d.lower() for d in insecure_defaults]:
                errors.append(
                    "WEBHOOK_SECRET_KEY is set to a known insecure default value. "
                    "This allows attackers to forge webhook signatures."
                )

            # Validate minimum key length
            if len(self.webhook_secret_key) < 32:
                errors.append(
                    "WEBHOOK_SECRET_KEY is shorter than 32 characters. "
                    "Short keys are vulnerable to brute force attacks. "
                    "Use a secure, random key with at least 32 characters."
                )

        # Validate CORS origins
        if self.cors_origins == ["*"] or "*" in self.cors_origins:
            if self.cors_allow_credentials:
                errors.append(
                    "CORS origins are set to wildcard [*] with credentials enabled. "
                    "This allows any origin to access the API with credentials, enabling CSRF attacks. "
                    "Either set CORS_ORIGINS to specific allowed origins, or set CORS_ALLOW_CREDENTIALS=false."
                )
            elif is_production:
                errors.append(
                    "CORS origins are set to wildcard [*] in production. "
                    "This allows any origin to access the API. "
                    "Set CORS_ORIGINS environment variable to specific allowed origins for production."
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

        # Validate BASE_URL for production (used in password reset and verification emails)
        if is_production:
            if self.base_url == "https://localhost:8000" or "localhost" in self.base_url:
                errors.append(
                    "BASE_URL is set to localhost in production. "
                    "Set BASE_URL environment variable to the public API base URL "
                    "(e.g. https://api.yourdomain.com) so that password reset and "
                    "email verification links are reachable."
                )

        # Validate Stripe keys for production
        if is_production:
            if (
                self.stripe_secret_key == "sk_test_placeholder"
                or not self.stripe_secret_key.startswith("sk_live_")
            ):
                errors.append(
                    "STRIPE_SECRET_KEY is not configured for production or is using a test placeholder. "
                    "Set STRIPE_SECRET_KEY environment variable with a valid production Stripe secret key."
                )
            if (
                self.stripe_publishable_key == "pk_test_placeholder"
                or not self.stripe_publishable_key.startswith("pk_live_")
            ):
                errors.append(
                    "STRIPE_PUBLISHABLE_KEY is not configured for production or is using a test placeholder. "
                    "Set STRIPE_PUBLISHABLE_KEY environment variable with a valid production Stripe publishable key."
                )
            if not self.stripe_webhook_secret:
                errors.append(
                    "STRIPE_WEBHOOK_SECRET is not configured for production. "
                    "Set STRIPE_WEBHOOK_SECRET to your Stripe webhook signing secret to enable "
                    "webhook signature verification."
                )

        # Validate URL formats
        try:
            parsed = urlparse(self.database_url)
            if not parsed.scheme or not parsed.netloc:
                errors.append("DATABASE_URL is not a valid URL format.")
        except Exception:
            errors.append("DATABASE_URL is not a valid URL.")

        try:
            parsed = urlparse(self.redis_url)
            if not parsed.scheme or not parsed.netloc:
                errors.append("REDIS_URL is not a valid URL format.")
        except Exception:
            errors.append("REDIS_URL is not a valid URL.")

        try:
            parsed = urlparse(self.celery_broker_url)
            if not parsed.scheme or not parsed.netloc:
                errors.append("CELERY_BROKER_URL is not a valid URL format.")
        except Exception:
            errors.append("CELERY_BROKER_URL is not a valid URL.")

        # If there are critical errors in production, fail fast
        if errors and is_production:
            error_message = "CRITICAL CONFIGURATION ERRORS:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            raise ValueError(error_message)


# Global settings instance
settings = Settings()
