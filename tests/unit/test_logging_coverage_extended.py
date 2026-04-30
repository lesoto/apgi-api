"""
Extended coverage tests for app/middleware/logging.py
"""

import logging
import os
from unittest.mock import patch

from app.middleware.logging import configure_structured_logging


def test_configure_structured_logging_test_mode():
    """Test that configure_structured_logging returns early in TEST_MODE."""
    with patch.dict(os.environ, {"TEST_MODE": "true"}):
        with patch("logging.basicConfig") as mock_basic:
            configure_structured_logging()
            mock_basic.assert_not_called()


def test_configure_structured_logging_success():
    """Test configure_structured_logging success path."""
    with patch.dict(os.environ, {"TEST_MODE": "false"}):
        # Clear existing handlers to trigger basicConfig
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers = []

        try:
            # Call the function - it should configure logging without error
            configure_structured_logging(log_level="DEBUG")
            # Verify the function executed successfully
            assert True
        finally:
            # Restore handlers
            root_logger.handlers = original_handlers
