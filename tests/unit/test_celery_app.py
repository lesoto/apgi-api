"""
Comprehensive test suite for celery_app.py

Tests _validate_celery_urls function in isolation since conftest.py mocks celery_app.
"""

import sys
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_celery_mock() -> Generator[None, None, None]:
    """Clear the conftest.py mock so we can test the real module."""
    # Remove the mock from sys.modules
    original_mock = sys.modules.pop("app.celery_app", None)

    # Also remove app.config to ensure fresh import chain
    sys.modules.pop("app.celery_app", None)

    yield

    # Restore the mock after test (conftest.py expects it)
    if original_mock is not None:
        sys.modules["app.celery_app"] = original_mock


class TestValidateCeleryUrls:
    """Test _validate_celery_urls function."""

    def test_validate_celery_urls_valid_redis(self, clear_celery_mock: Any) -> None:
        """Test validation passes with valid redis URL."""
        # Import after clearing the mock
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = "redis://localhost:6379/1"

        with patch("app.celery_app.settings", mock_settings):
            _validate_celery_urls()

    def test_validate_celery_urls_valid_redis_socket(self, clear_celery_mock: Any) -> None:
        """Test validation passes with redis+socket URL."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis+socket:///tmp/redis.sock"
        mock_settings.celery_result_backend = "redis+socket:///tmp/redis.sock"

        with patch("app.celery_app.settings", mock_settings):
            _validate_celery_urls()

    def test_validate_celery_urls_missing_broker(self, clear_celery_mock: Any) -> None:
        """Test validation fails when broker URL is empty."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = ""
        mock_settings.celery_result_backend = "redis://localhost:6379/1"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery broker URL is not configured"):
                _validate_celery_urls()

    def test_validate_celery_urls_missing_backend(self, clear_celery_mock: Any) -> None:
        """Test validation fails when backend URL is empty."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = ""

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery backend URL is not configured"):
                _validate_celery_urls()

    def test_validate_celery_urls_none_broker(self, clear_celery_mock: Any) -> None:
        """Test validation fails when broker URL is None."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = None
        mock_settings.celery_result_backend = "redis://localhost:6379/1"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery broker URL is not configured"):
                _validate_celery_urls()

    def test_validate_celery_urls_none_backend(self, clear_celery_mock: Any) -> None:
        """Test validation fails when backend URL is None."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = None

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery backend URL is not configured"):
                _validate_celery_urls()

    def test_validate_celery_urls_invalid_scheme_broker(self, clear_celery_mock: Any) -> None:
        """Test validation fails with invalid broker scheme."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "amqp://localhost:5672"
        mock_settings.celery_result_backend = "redis://localhost:6379/1"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery broker URL must use redis scheme"):
                _validate_celery_urls()

    def test_validate_celery_urls_invalid_scheme_backend(self, clear_celery_mock: Any) -> None:
        """Test validation fails with invalid backend scheme."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = "mongodb://localhost:27017"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery backend URL must use redis scheme"):
                _validate_celery_urls()

    def test_validate_celery_urls_invalid_broker_url_no_hostname(
        self, clear_celery_mock: Any
    ) -> None:
        """Test validation fails when broker URL has no hostname or path."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://"
        mock_settings.celery_result_backend = "redis://localhost:6379/1"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery broker URL is invalid"):
                _validate_celery_urls()

    def test_validate_celery_urls_invalid_backend_url_no_hostname(
        self, clear_celery_mock: Any
    ) -> None:
        """Test validation fails when backend URL has no hostname or path."""
        from app.celery_app import _validate_celery_urls

        mock_settings = MagicMock()
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = "redis://"

        with patch("app.celery_app.settings", mock_settings):
            with pytest.raises(ValueError, match="Celery backend URL is invalid"):
                _validate_celery_urls()


class TestModuleLevel:
    """Test module-level code behavior."""

    def test_validate_function_exists(self, clear_celery_mock: Any) -> None:
        """Test that _validate_celery_urls function exists."""
        from app.celery_app import _validate_celery_urls

        assert callable(_validate_celery_urls)


class TestGetQueueDepth:
    """Test get_queue_depth function."""

    def test_get_queue_depth_success(self, clear_celery_mock: Any) -> None:
        """Test get_queue_depth successfully returns count."""
        from app.celery_app import get_queue_depth

        mock_conn = MagicMock()
        mock_conn.default_channel.client.llen.return_value = 5

        with patch("app.celery_app.celery_app.pool.acquire") as mock_acquire:
            mock_acquire.return_value.__enter__.return_value = mock_conn

            assert get_queue_depth("celery") == 5
            mock_conn.default_channel.client.llen.assert_called_once_with("celery")

    def test_get_queue_depth_exception(self, clear_celery_mock: Any) -> None:
        """Test get_queue_depth returns 0 on exception."""
        from app.celery_app import get_queue_depth

        with patch("app.celery_app.celery_app.pool.acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("Redis connection error")

            assert get_queue_depth("celery") == 0
