"""
Unit tests for webhook manager service.

Tests webhook delivery creation, validation, and processing.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from app.services.webhook_manager import WebhookManager


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def webhook_manager():
    """Create a WebhookManager instance."""
    return WebhookManager()


@pytest.fixture
def mock_webhook_delivery():
    """Create a mock webhook delivery database object."""
    delivery = MagicMock()
    delivery.delivery_id = "delivery_123"
    delivery.task_id = "task_456"
    delivery.webhook_url = "https://example.com/webhook"
    delivery.payload = {"event": "task_completed", "task_id": "task_456"}
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.retry_count = 5
    delivery.retry_delays = [5, 30, 300, 1800, 3600]
    delivery.next_retry_at = datetime.now(timezone.utc)
    delivery.last_attempt_at = None
    delivery.response_status = None
    delivery.response_body = None
    delivery.error_message = None
    return delivery


class TestValidateWebhookUrl:
    """Test webhook URL validation."""

    def test_validate_webhook_url_valid_https(self):
        """Test validation of valid HTTPS URL."""
        WebhookManager._validate_webhook_url("https://example.com/webhook")

    def test_validate_webhook_url_valid_http(self):
        """Test validation of valid HTTP URL."""
        WebhookManager._validate_webhook_url("http://example.com/webhook")

    def test_validate_webhook_url_invalid_scheme(self):
        """Test validation rejects invalid scheme."""
        with pytest.raises(ValueError, match="Only HTTP and HTTPS URLs are allowed"):
            WebhookManager._validate_webhook_url("ftp://example.com/webhook")

    def test_validate_webhook_url_no_hostname(self):
        """Test validation rejects URL without hostname."""
        with pytest.raises(ValueError, match="Invalid URL: no hostname"):
            WebhookManager._validate_webhook_url("https:///webhook")

    @patch("socket.getaddrinfo")
    def test_validate_webhook_url_private_ip(self, mock_getaddrinfo):
        """Test validation blocks private IP addresses."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("192.168.1.1", 0))]

        with pytest.raises(ValueError, match="URL points to private/internal IP address"):
            WebhookManager._validate_webhook_url("http://192.168.1.1/webhook")

    @patch("socket.getaddrinfo")
    def test_validate_webhook_url_cloud_metadata(self, mock_getaddrinfo):
        """Test validation blocks cloud metadata endpoints."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("169.254.169.254", 0))]

        with pytest.raises(ValueError, match="Access to cloud metadata.*blocked"):
            WebhookManager._validate_webhook_url("http://169.254.169.254/webhook")

    @patch("socket.getaddrinfo")
    def test_validate_webhook_url_blocked_hostname(self, mock_getaddrinfo):
        """Test validation blocks blocked hostnames."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]

        with pytest.raises(ValueError, match="Access to cloud metadata endpoint.*is blocked"):
            WebhookManager._validate_webhook_url("http://metadata.google.internal/webhook")


class TestCreateWebhookDelivery:
    """Test webhook delivery creation."""

    @pytest.mark.asyncio
    async def test_create_webhook_delivery_success(self, webhook_manager, mock_db_session):
        """Test successful webhook delivery creation."""
        task_id = "task_123"
        webhook_url = "https://example.com/webhook"
        payload = {"event": "task_completed"}

        with patch("app.services.webhook_manager.WebhookDelivery") as mock_delivery_class:
            mock_delivery = MagicMock()
            mock_delivery_class.return_value = mock_delivery

            result = await webhook_manager.create_webhook_delivery(
                mock_db_session, task_id, webhook_url, payload
            )

            assert isinstance(result, str)
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_webhook_delivery_invalid_url(self, webhook_manager, mock_db_session):
        """Test webhook delivery creation with invalid URL."""
        task_id = "task_123"
        webhook_url = "ftp://example.com/webhook"
        payload = {"event": "task_completed"}

        with pytest.raises(ValueError, match="Only HTTP and HTTPS URLs are allowed"):
            await webhook_manager.create_webhook_delivery(
                mock_db_session, task_id, webhook_url, payload
            )

    @pytest.mark.asyncio
    async def test_create_webhook_delivery_database_error(self, webhook_manager, mock_db_session):
        """Test webhook delivery creation with database error."""
        task_id = "task_123"
        webhook_url = "https://example.com/webhook"
        payload = {"event": "task_completed"}

        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await webhook_manager.create_webhook_delivery(
                mock_db_session, task_id, webhook_url, payload
            )


class TestDeliverWebhook:
    """Test webhook delivery."""

    @pytest.mark.asyncio
    async def test_deliver_webhook_not_found(self, webhook_manager, mock_db_session):
        """Test webhook delivery when delivery not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = await webhook_manager.deliver_webhook(mock_db_session, "nonexistent")

        assert not result

    @pytest.mark.asyncio
    async def test_deliver_webhook_already_delivered(
        self, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test webhook delivery when already delivered."""
        mock_webhook_delivery.status = "delivered"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        result = await webhook_manager.deliver_webhook(mock_db_session, "delivery_123")

        assert result

    @pytest.mark.asyncio
    async def test_deliver_webhook_max_attempts(
        self, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test webhook delivery when max attempts exceeded."""
        mock_webhook_delivery.attempts = 5
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        with patch(
            "app.services.webhook_manager.alert_manager", new_callable=AsyncMock
        ) as mock_alert_manager:
            result = await webhook_manager.deliver_webhook(mock_db_session, "delivery_123")

            assert not result
            assert mock_webhook_delivery.status == "dead_letter"
            mock_alert_manager.trigger_custom_alert.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_deliver_webhook_success(
        self, mock_client_session_class, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test successful webhook delivery."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        mock_session = MagicMock()
        mock_client_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session.post.return_value = mock_cm

        result = await webhook_manager.deliver_webhook(mock_db_session, "delivery_123")

        assert result
        assert mock_webhook_delivery.status == "delivered"
        assert mock_webhook_delivery.response_status == 200
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_deliver_webhook_failure_retry(
        self, mock_client_session_class, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test webhook delivery failure with retry scheduling."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        mock_session = MagicMock()
        mock_client_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session.post.return_value = mock_cm

        result = await webhook_manager.deliver_webhook(mock_db_session, "delivery_123")

        assert not result
        assert mock_webhook_delivery.status == "pending"  # Not changed yet
        assert mock_webhook_delivery.attempts == 1
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_deliver_webhook_timeout(
        self, mock_client_session_class, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test webhook delivery timeout."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        mock_session = MagicMock()
        mock_client_session_class.return_value.__aenter__.return_value = mock_session

        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = asyncio.TimeoutError()
        mock_session.post.return_value = mock_cm

        result = await webhook_manager.deliver_webhook(mock_db_session, "delivery_123")

        assert not result
        assert mock_webhook_delivery.attempts == 1
        assert mock_webhook_delivery.error_message == "Timeout"
        mock_db_session.commit.assert_called_once()


class TestProcessPendingDeliveries:
    """Test processing pending deliveries."""

    @pytest.mark.asyncio
    async def test_process_pending_deliveries(
        self, webhook_manager, mock_db_session, mock_webhook_delivery
    ):
        """Test processing pending deliveries."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            mock_webhook_delivery
        ]

        with patch.object(
            webhook_manager, "deliver_webhook", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = True

            result = await webhook_manager.process_pending_deliveries(mock_db_session)

            assert result == 1
            mock_deliver.assert_called_once_with(mock_db_session, "delivery_123")


class TestWebhookManagerLifecycle:
    """Test webhook manager lifecycle."""

    def test_context_manager(self, webhook_manager):
        """Test webhook manager as async context manager."""

        async def test():
            async with webhook_manager:
                assert webhook_manager.session is None  # Not opened yet
            # Should be closed
            assert webhook_manager.session is None

        asyncio.run(test())

    def test_close(self, webhook_manager):
        """Test closing webhook manager."""

        async def test():
            mock_session = AsyncMock()
            webhook_manager.session = mock_session
            await webhook_manager.close()
            mock_session.close.assert_called_once()
            assert webhook_manager.session is None

        asyncio.run(test())
