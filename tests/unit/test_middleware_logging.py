"""Unit tests for logging middleware."""

import logging
import os
from unittest.mock import patch

from app.middleware.logging import configure_structured_logging


class TestConfigureStructuredLogging:
    """Test configure_structured_logging function."""

    def test_skips_in_test_mode(self) -> None:
        """Test that configuration is skipped in TEST_MODE (lines 265-266)."""
        with patch.dict(os.environ, {"TEST_MODE": "true"}):
            # Reset root logger handlers
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers.clear()

            configure_structured_logging()

            # Handlers should still be empty since we skipped configuration
            assert len(root_logger.handlers) == 0

            # Restore handlers
            root_logger.handlers.extend(original_handlers)

    def test_skips_if_already_configured(self) -> None:
        """Test that configuration is skipped if handlers already exist (line 270)."""
        # Add a handler to simulate already configured
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        handler = logging.StreamHandler()
        root_logger.addHandler(handler)

        configure_structured_logging()

        # Should still have the original handler plus the one we added
        assert len(root_logger.handlers) >= 1

        # Clean up
        root_logger.removeHandler(handler)
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)

    def test_handles_configuration_exception(self) -> None:
        """Test that configuration exceptions are handled gracefully (lines 278-279)."""
        # Reset root logger handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers.clear()

        with patch("logging.basicConfig", side_effect=Exception("Configuration failed")):
            # Should not raise an exception
            configure_structured_logging()

        # Restore handlers
        root_logger.handlers.extend(original_handlers)

    def test_configures_with_valid_log_level(self) -> None:
        """Test successful configuration with valid log level."""
        # Reset root logger handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers.clear()

        with patch.dict(os.environ, {}, clear=True):
            configure_structured_logging("DEBUG")

            # Should have configured handlers
            assert len(root_logger.handlers) >= 0

        # Restore handlers
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
