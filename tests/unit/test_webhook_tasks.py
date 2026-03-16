"""Tests for webhook_tasks.py module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestWebhookTasks:
    """Test suite for webhook_tasks module."""

    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    def test_process_pending_webhooks_success(self, mock_webhook_manager, mock_session_local):
        """Test successful processing of pending webhooks."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=5)

        from app.tasks.webhook_tasks import process_pending_webhooks

        result = process_pending_webhooks()

        assert result == 5
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    def test_process_pending_webhooks_zero_processed(
        self, mock_webhook_manager, mock_session_local
    ):
        """Test processing when no webhooks are pending."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=0)

        from app.tasks.webhook_tasks import process_pending_webhooks

        result = process_pending_webhooks()

        assert result == 0
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    def test_process_pending_webhooks_exception(self, mock_webhook_manager, mock_session_local):
        """Test handling when webhook processing raises an exception."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(
            side_effect=Exception("Processing failed")
        )

        from app.tasks.webhook_tasks import process_pending_webhooks

        with pytest.raises(Exception, match="Processing failed"):
            process_pending_webhooks()

        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    def test_process_pending_webhooks_multiple_processed(
        self, mock_webhook_manager, mock_session_local
    ):
        """Test processing multiple webhooks."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=10)

        from app.tasks.webhook_tasks import process_pending_webhooks

        result = process_pending_webhooks()

        assert result == 10
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    def test_process_pending_webhooks_database_error(
        self, mock_webhook_manager, mock_session_local
    ):
        """Test handling when database session creation fails."""
        mock_session_local.side_effect = Exception("Database connection failed")

        from app.tasks.webhook_tasks import process_pending_webhooks

        with pytest.raises(Exception, match="Database connection failed"):
            process_pending_webhooks()

    @pytest.mark.asyncio
    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    async def test_process_webhooks_async_success(self, mock_webhook_manager, mock_session_local):
        """Test the async _process_webhooks function directly."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(return_value=3)

        from app.tasks.webhook_tasks import _process_webhooks

        result = await _process_webhooks()

        assert result == 3
        mock_session_local.assert_called_once()
        mock_webhook_manager.assert_called_once()
        mock_manager.process_pending_deliveries.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.tasks.webhook_tasks.SessionLocal")
    @patch("app.tasks.webhook_tasks.WebhookManager")
    async def test_process_webhooks_async_exception(self, mock_webhook_manager, mock_session_local):
        """Test the async _process_webhooks function with exception."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_manager = MagicMock()
        mock_webhook_manager.return_value = mock_manager
        mock_manager.process_pending_deliveries = AsyncMock(side_effect=Exception("Webhook error"))

        from app.tasks.webhook_tasks import _process_webhooks

        with pytest.raises(Exception, match="Webhook error"):
            await _process_webhooks()

        mock_db.close.assert_called_once()

    def test_process_pending_webhooks_task_name(self):
        """Test that the Celery task has the correct name."""
        from app.tasks.webhook_tasks import process_pending_webhooks

        assert process_pending_webhooks.name == "process_pending_webhooks"
