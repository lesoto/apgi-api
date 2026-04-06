"""Test webhook tasks."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from app.tasks.webhook_tasks import process_pending_webhooks, _process_webhooks


class TestWebhookTasks:
    """Test webhook tasks functionality."""

    def test_process_pending_webhooks_task_exists(self):
        """Test that the Celery task is properly defined."""
        assert callable(process_pending_webhooks)
        # Celery tasks have a 'run' method or are callable directly
        assert hasattr(process_pending_webhooks, "run") or callable(process_pending_webhooks)

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_pending_webhooks_success(self, mock_session_local, mock_webhook_manager):
        """Test successful webhook processing."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=5)

        # Run the async function
        result = asyncio.run(_process_webhooks())

        # Verify results
        assert result == 5
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_pending_webhooks_exception(self, mock_session_local, mock_webhook_manager):
        """Test webhook processing with exception."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        test_exception = ValueError("Test webhook error")
        mock_manager.process_pending_deliveries = AsyncMock(side_effect=test_exception)

        # Run and expect exception
        with pytest.raises(ValueError, match="Test webhook error"):
            asyncio.run(_process_webhooks())

        # Verify cleanup even on exception
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_pending_webhooks_logging(self, mock_session_local, mock_webhook_manager):
        """Test that webhook processing is properly logged."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=3)

        with patch("app.tasks.webhook_tasks.logger") as mock_logger:
            asyncio.run(_process_webhooks())

            # Verify logging
            mock_logger.info.assert_called_once_with("Processed 3 pending webhooks")

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_pending_webhooks_error_logging(self, mock_session_local, mock_webhook_manager):
        """Test that webhook processing errors are properly logged."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        test_exception = ValueError("Test webhook error")
        mock_manager.process_pending_deliveries = AsyncMock(side_effect=test_exception)

        with patch("app.tasks.webhook_tasks.logger") as mock_logger:
            with pytest.raises(ValueError):
                asyncio.run(_process_webhooks())

            # Verify error logging
            mock_logger.error.assert_called_once_with(
                "Error processing webhooks: Test webhook error"
            )

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_webhooks_closes_database(self, mock_session_local, mock_webhook_manager):
        """Test that database connection is always closed."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=1)

        # Run the function
        asyncio.run(_process_webhooks())

        # Verify database is closed regardless of success/failure
        assert mock_db.close.call_count == 1

    @patch("app.tasks.webhook_tasks.WebhookManager")
    @patch("app.tasks.webhook_tasks.SessionLocal")
    def test_process_webhooks_manager_parameters(self, mock_session_local, mock_webhook_manager):
        """Test that WebhookManager is called with correct parameters."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=2)

        # Run the function
        asyncio.run(_process_webhooks())

        # Verify WebhookManager instantiation
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
