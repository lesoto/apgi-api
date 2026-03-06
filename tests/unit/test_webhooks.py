"""
Unit tests for webhook delivery routes.

Tests webhook delivery listing, retrieval, retry, and deletion endpoints.
Validates Requirements 8.1, 8.2, 8.3.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.routes.webhooks import (
    list_webhook_deliveries,
    get_webhook_delivery,
    retry_webhook_delivery,
    delete_webhook_delivery,
)
from app.services.auth_manager import TokenPayload


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_current_user():
    """Create a mock current user with admin permissions."""
    return TokenPayload(
        user_id="admin_user_123",
        username="admin",
        roles=["admin"],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def mock_webhook_delivery():
    """Create a mock webhook delivery database object."""
    delivery = MagicMock()
    delivery.delivery_id = "delivery_123"
    delivery.task_id = "task_456"
    delivery.webhook_url = "https://example.com/webhook"
    delivery.status = "pending"
    delivery.attempts = 1
    delivery.last_attempt_at = None
    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    delivery.response_status = None
    delivery.response_body = None
    delivery.error_message = None
    delivery.created_at = datetime.now(timezone.utc)
    delivery.retry_count = 5
    delivery.retry_delays = [5, 30, 300, 1800, 3600]
    return delivery


class TestListWebhookDeliveries:
    """Test webhook delivery listing."""

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_success(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test successful webhook delivery listing."""
        mock_db_session.query.return_value.count.return_value = 1
        mock_db_session.query.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_webhook_delivery
        ]

        result = await list_webhook_deliveries(None, 1, 10, mock_db_session, mock_current_user)

        assert len(result.deliveries) == 1
        assert result.deliveries[0].delivery_id == "delivery_123"
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_with_status_filter(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test webhook delivery listing with status filter."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_webhook_delivery
        ]

        result = await list_webhook_deliveries("pending", 1, 10, mock_db_session, mock_current_user)

        assert len(result.deliveries) == 1

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_invalid_status_filter(
        self, mock_db_session, mock_current_user
    ):
        """Test webhook delivery listing with invalid status filter."""
        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries("invalid", 1, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_database_error(self, mock_db_session, mock_current_user):
        """Test webhook delivery listing with database error."""
        mock_db_session.query.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries(None, 1, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


class TestGetWebhookDelivery:
    """Test webhook delivery retrieval."""

    @pytest.mark.asyncio
    async def test_get_webhook_delivery_success(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test successful webhook delivery retrieval."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        result = await get_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

        assert result.delivery_id == "delivery_123"
        assert result.task_id == "task_456"

    @pytest.mark.asyncio
    async def test_get_webhook_delivery_not_found(self, mock_db_session, mock_current_user):
        """Test webhook delivery retrieval when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_webhook_delivery("nonexistent", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404


class TestRetryWebhookDelivery:
    """Test webhook delivery retry."""

    @pytest.mark.asyncio
    async def test_retry_webhook_delivery_success(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test successful webhook delivery retry."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await retry_webhook_delivery(
                "delivery_123", mock_db_session, mock_current_user
            )

            assert result.delivery_id == "delivery_123"
            assert result.success

    @pytest.mark.asyncio
    async def test_retry_webhook_delivery_not_found(self, mock_db_session, mock_current_user):
        """Test webhook delivery retry when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await retry_webhook_delivery("nonexistent", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_webhook_delivery_already_delivered(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test webhook delivery retry when already delivered."""
        mock_webhook_delivery.status = "delivered"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        with pytest.raises(HTTPException) as exc_info:
            await retry_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_webhook_delivery_max_attempts(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test webhook delivery retry when max attempts exceeded."""
        mock_webhook_delivery.attempts = 5  # Assuming webhook_retry_limit is 5
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        with patch("app.routes.webhooks.settings") as mock_settings:
            mock_settings.webhook_retry_limit = 5

            with pytest.raises(HTTPException) as exc_info:
                await retry_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_webhook_delivery_error(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test webhook delivery retry with error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            side_effect=Exception("Delivery failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await retry_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

            assert exc_info.value.status_code == 500


class TestDeleteWebhookDelivery:
    """Test webhook delivery deletion."""

    @pytest.mark.asyncio
    async def test_delete_webhook_delivery_success(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test successful webhook delivery deletion."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )

        result = await delete_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

        assert result is None  # 204 No Content
        mock_db_session.delete.assert_called_once_with(mock_webhook_delivery)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_webhook_delivery_not_found(self, mock_db_session, mock_current_user):
        """Test webhook delivery deletion when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_webhook_delivery("nonexistent", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_webhook_delivery_database_error(
        self, mock_db_session, mock_current_user, mock_webhook_delivery
    ):
        """Test webhook delivery deletion with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_webhook_delivery("delivery_123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500
