"""
Unit tests for app/middleware/cors_config.py

Tests CORS middleware configuration with environment-based settings.
"""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_app() -> MagicMock:
    """Create a mock FastAPI app."""
    app = MagicMock()
    app.add_middleware = MagicMock()
    return app


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.cors_origins = ["http://localhost:3000", "http://localhost:8000"]
    settings.cors_allow_credentials = True
    settings.cors_allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    settings.cors_allow_headers = ["Authorization", "Content-Type", "X-CSRF-Token"]
    return settings


class TestConfigureCorsBasic:
    """Test basic CORS configuration."""

    def test_configure_cors_calls_add_middleware(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors calls app.add_middleware with CORSMiddleware."""
        from fastapi.middleware.cors import CORSMiddleware

        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            mock_app.add_middleware.assert_called_once()
            call_args = mock_app.add_middleware.call_args
            assert call_args[0][0] == CORSMiddleware

    def test_configure_cors_passes_origins(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors passes allow_origins from settings."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_origins"] == mock_settings.cors_origins

    def test_configure_cors_passes_credentials(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors passes allow_credentials from settings."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_credentials"] == mock_settings.cors_allow_credentials

    def test_configure_cors_passes_methods(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors passes allow_methods from settings."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_methods"] == mock_settings.cors_allow_methods

    def test_configure_cors_passes_headers(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors passes allow_headers from settings."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_headers"] == mock_settings.cors_allow_headers


class TestConfigureCorsExposedHeaders:
    """Test exposed headers configuration."""

    def test_configure_cors_exposes_rate_limit_headers(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors exposes rate limit headers."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            expose_headers = call_kwargs["expose_headers"]

            assert "X-RateLimit-Limit" in expose_headers
            assert "X-RateLimit-Remaining" in expose_headers
            assert "X-RateLimit-Reset" in expose_headers

    def test_configure_cors_max_age_set(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors sets max_age for preflight caching."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["max_age"] == 600


class TestConfigureCorsLogging:
    """Test logging behavior."""

    def test_configure_cors_logs_configuration(
        self, mock_app: MagicMock, mock_settings: MagicMock, caplog: Any
    ) -> None:
        """configure_cors logs the configuration."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            with caplog.at_level(logging.INFO):
                configure_cors(mock_app)

            # Check that configuration was logged
            assert any("CORS" in record.message for record in caplog.records)

    def test_configure_cors_logs_success(
        self, mock_app: MagicMock, mock_settings: MagicMock, caplog: Any
    ) -> None:
        """configure_cors logs successful configuration."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            with caplog.at_level(logging.INFO):
                configure_cors(mock_app)

            # Check that success message was logged
            assert any("successfully" in record.message.lower() for record in caplog.records)

    def test_configure_cors_logs_origins(
        self, mock_app: MagicMock, mock_settings: MagicMock, caplog: Any
    ) -> None:
        """configure_cors logs the configured origins."""
        from app.middleware.cors_config import configure_cors

        mock_settings.cors_origins = ["https://example.com", "https://app.example.com"]

        with patch("app.middleware.cors_config.settings", mock_settings):
            with caplog.at_level(logging.INFO):
                configure_cors(mock_app)

            # Check that origins were logged
            log_text = " ".join(record.message for record in caplog.records)
            assert "https://example.com" in log_text or "example.com" in log_text


class TestConfigureCorsWithDifferentSettings:
    """Test CORS configuration with various settings."""

    def test_configure_cors_with_single_origin(self, mock_app: MagicMock) -> None:
        """configure_cors works with a single origin."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["https://example.com"]
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_origins"] == ["https://example.com"]

    def test_configure_cors_with_wildcard_origin(self, mock_app: MagicMock) -> None:
        """configure_cors works with wildcard origin."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["*"]
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_origins"] == ["*"]

    def test_configure_cors_with_multiple_origins(self, mock_app: MagicMock) -> None:
        """configure_cors works with multiple origins."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = [
            "https://app1.example.com",
            "https://app2.example.com",
            "https://app3.example.com",
        ]
        settings.cors_allow_credentials = True
        settings.cors_allow_methods = ["GET", "POST", "PUT", "DELETE"]
        settings.cors_allow_headers = ["Authorization", "Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert len(call_kwargs["allow_origins"]) == 3

    def test_configure_cors_credentials_disabled(self, mock_app: MagicMock) -> None:
        """configure_cors works with credentials disabled."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["*"]
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_credentials"] is False

    def test_configure_cors_credentials_enabled(self, mock_app: MagicMock) -> None:
        """configure_cors works with credentials enabled."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["https://example.com"]
        settings.cors_allow_credentials = True
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = ["Authorization", "Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_credentials"] is True


class TestConfigureCorsMethodsAndHeaders:
    """Test methods and headers configuration."""

    def test_configure_cors_with_all_methods(self, mock_app: MagicMock) -> None:
        """configure_cors works with all HTTP methods."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["*"]
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        settings.cors_allow_headers = ["*"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert len(call_kwargs["allow_methods"]) == 7

    def test_configure_cors_with_custom_headers(self, mock_app: MagicMock) -> None:
        """configure_cors works with custom headers."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["https://example.com"]
        settings.cors_allow_credentials = True
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = [
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Custom-Header",
        ]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert "X-Custom-Header" in call_kwargs["allow_headers"]

    def test_configure_cors_with_minimal_methods(self, mock_app: MagicMock) -> None:
        """configure_cors works with minimal methods."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["https://example.com"]
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_methods"] == ["GET"]


class TestConfigureCorsEdgeCases:
    """Test edge cases."""

    def test_configure_cors_with_empty_origins_list(self, mock_app: MagicMock) -> None:
        """configure_cors works with empty origins list."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = []
        settings.cors_allow_credentials = False
        settings.cors_allow_methods = ["GET"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert call_kwargs["allow_origins"] == []

    def test_configure_cors_multiple_calls(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors can be called multiple times."""
        from app.middleware.cors_config import configure_cors

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)
            configure_cors(mock_app)

            assert mock_app.add_middleware.call_count == 2

    def test_configure_cors_with_localhost_origins(self, mock_app: MagicMock) -> None:
        """configure_cors works with localhost origins."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["http://localhost:3000", "http://localhost:8000"]
        settings.cors_allow_credentials = True
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = ["Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert "http://localhost:3000" in call_kwargs["allow_origins"]
            assert "http://localhost:8000" in call_kwargs["allow_origins"]

    def test_configure_cors_with_https_origins(self, mock_app: MagicMock) -> None:
        """configure_cors works with HTTPS origins."""
        from app.middleware.cors_config import configure_cors

        settings = MagicMock()
        settings.cors_origins = ["https://app.example.com", "https://api.example.com"]
        settings.cors_allow_credentials = True
        settings.cors_allow_methods = ["GET", "POST"]
        settings.cors_allow_headers = ["Authorization", "Content-Type"]

        with patch("app.middleware.cors_config.settings", settings):
            configure_cors(mock_app)

            call_kwargs = mock_app.add_middleware.call_args[1]
            assert all(origin.startswith("https://") for origin in call_kwargs["allow_origins"])

    def test_configure_cors_preserves_settings_object(
        self, mock_app: MagicMock, mock_settings: MagicMock
    ) -> None:
        """configure_cors does not modify the settings object."""
        from app.middleware.cors_config import configure_cors

        original_origins = mock_settings.cors_origins.copy()
        original_methods = mock_settings.cors_allow_methods.copy()

        with patch("app.middleware.cors_config.settings", mock_settings):
            configure_cors(mock_app)

            assert mock_settings.cors_origins == original_origins
            assert mock_settings.cors_allow_methods == original_methods
