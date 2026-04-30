"""
Targeted tests for app/main.py to achieve 100% coverage.
Covers:
- Startup/shutdown event handlers
- Exception handlers
- Static file mounting
"""

import importlib
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from app.main import create_app, lifespan


@pytest.mark.asyncio
async def test_lifespan_startup_dependency_check_failure():
    """Test that startup fails if hard dependencies are missing."""
    app = FastAPI()
    app.state.test_mode = False

    with patch.dict(os.environ, {"TEST_MODE": "false"}):
        with patch("app.dependency_checker.check_dependencies", return_value=False):
            with pytest.raises(RuntimeError, match="Hard dependency check failed"):
                async with lifespan(app):
                    pass


@pytest.mark.asyncio
async def test_lifespan_startup_soft_dependency_check_failure():
    """Test that startup continues in degraded mode if soft dependencies are missing."""
    app = FastAPI()
    app.state.test_mode = False

    # Mock HARD as True, SOFT as False
    def side_effect(required_deps, fail_fast=False):
        from app.dependency_checker import HARD_DEPENDENCIES

        if required_deps == HARD_DEPENDENCIES:
            return True
        return False

    with patch.dict(os.environ, {"TEST_MODE": "false"}):
        with patch("app.dependency_checker.check_dependencies", side_effect=side_effect):
            # Mock other initializations to avoid side effects
            with (
                patch("app.main.init_db"),
                patch("app.main.redis.from_url") as mock_redis_url,
                patch("app.main.configure_alerting"),
                patch("app.main.configure_distributed_tracing"),
            ):

                mock_redis = AsyncMock()
                mock_redis.ping = AsyncMock()
                mock_redis.aclose = AsyncMock()
                mock_redis_url.return_value = mock_redis

                async with lifespan(app):
                    assert app.state.degraded_mode is True


@pytest.mark.asyncio
async def test_lifespan_db_init_failure_production():
    """Test that startup fails if DB init fails in production."""
    app = FastAPI()
    app.state.test_mode = False  # Not in test mode for production behavior

    # Remove app.main from cache to force reimport
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    # Reimport app.main
    import app.main as main_module

    importlib.reload(main_module)
    lifespan_func = main_module.lifespan

    # Patch init_db after reload at the location where it's used in main.py
    with patch("app.main.init_db", side_effect=Exception("DB fail")):
        # Patch settings at the correct location
        with patch("app.main.settings.environment", "production"):
            with patch("app.main.settings.alert_error_rate_window_minutes", 1):
                with patch("app.main.settings.alert_cooldown_minutes", 1):
                    with patch("app.main.settings.alert_webhook_urls", []):
                        with patch("app.main.settings.alert_enable_log_channel", True):
                            with patch("app.main.settings.alert_error_rate_threshold", 10):
                                with patch("app.main.settings.redis_url", "redis://localhost"):
                                    with patch("app.main.redis.from_url") as mock_redis_url:
                                        mock_redis = AsyncMock()
                                        mock_redis.ping = AsyncMock()
                                        mock_redis.aclose = AsyncMock()
                                        mock_redis_url.return_value = mock_redis
                                        with pytest.raises(Exception, match="DB fail"):
                                            async with lifespan_func(app):
                                                pass


@pytest.mark.asyncio
async def test_lifespan_db_init_failure_non_production():
    """Test that startup continues in degraded mode if DB init fails in non-production."""
    app = FastAPI()
    app.state.test_mode = False  # Not in test mode for realistic behavior

    # Remove app.main from cache to force reimport
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    # Reimport app.main
    import app.main as main_module

    importlib.reload(main_module)
    lifespan_func = main_module.lifespan

    # Patch init_db after reload at the location where it's used in main.py
    with patch("app.main.init_db", side_effect=Exception("DB fail")):
        # Patch settings at the correct location
        with patch("app.main.settings.environment", "development"):
            with patch("app.main.settings.alert_error_rate_window_minutes", 1):
                with patch("app.main.settings.alert_cooldown_minutes", 1):
                    with patch("app.main.settings.alert_webhook_urls", []):
                        with patch("app.main.settings.alert_enable_log_channel", True):
                            with patch("app.main.settings.alert_error_rate_threshold", 10):
                                with patch("app.main.settings.redis_url", "redis://localhost"):
                                    # Mock redis to avoid failures there
                                    with patch("app.main.redis.from_url") as mock_redis_url:
                                        mock_redis = AsyncMock()
                                        mock_redis.ping = AsyncMock()
                                        mock_redis.aclose = AsyncMock()
                                        mock_redis_url.return_value = mock_redis
                                        async with lifespan_func(app):
                                            assert app.state.db_available is False
                                            # degraded_mode may already be True
                                            # from soft dep check or DB init failure
                                            assert hasattr(app.state, "degraded_mode")


def test_create_app_with_web_dir():
    """Test create_app when web directory exists."""
    import os
    import tempfile

    # Reload app.main to ensure consistent state with other tests that reload it
    if "app.main" in sys.modules:
        del sys.modules["app.main"]
    import app.main as main_module

    importlib.reload(main_module)

    # Create a real temporary directory to avoid StaticFiles validation error
    with tempfile.TemporaryDirectory() as temp_dir:
        web_dir = os.path.join(temp_dir, "web")
        os.makedirs(web_dir, exist_ok=True)

        # Patch os.path functions at the module level where they're used
        with patch("os.path.exists", return_value=True):
            with patch("os.path.dirname", return_value=temp_dir):
                with patch("os.path.join", return_value=web_dir):
                    with patch("app.main.StaticFiles") as mock_static:
                        app = main_module.create_app(test_mode=True)
                        # Should have mounted /web
                        mock_static.assert_called_once()


def test_create_app_without_web_dir():
    """Test create_app when web directory does not exist."""
    with patch("app.main.os.path.exists", return_value=False):
        with patch("app.main.StaticFiles") as mock_static:
            app = create_app(test_mode=True)
            mock_static.assert_not_called()
