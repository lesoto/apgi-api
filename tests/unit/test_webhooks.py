"""
Unit tests for webhook delivery routes.

Tests webhook delivery listing, retrieval, retry, and deletion endpoints.
Validates Requirements 3.5, 3.15.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from starlette.testclient import TestClient

from app.routes.webhooks import (
    list_webhook_deliveries,
    get_webhook_delivery,
    retry_webhook_delivery,
    delete_webhook_delivery,
    list_dead_letter_deliveries,
    retry_dead_letter_delivery,
    purge_dead_letter_delivery,
)
from app.services.auth_manager import TokenPayload
from app.database.connection import get_db

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def mock_dead_letter_delivery():
    """Create a mock dead-letter webhook delivery database object."""
    delivery = MagicMock()
    delivery.delivery_id = "dl_delivery_456"
    delivery.task_id = "task_789"
    delivery.webhook_url = "https://example.com/webhook"
    delivery.status = "dead_letter"
    delivery.attempts = 5
    delivery.last_attempt_at = datetime.now(timezone.utc) - timedelta(hours=1)
    delivery.next_retry_at = None
    delivery.response_status = 500
    delivery.response_body = "Internal Server Error"
    delivery.error_message = "Max retries exceeded"
    delivery.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    return delivery


from contextlib import asynccontextmanager


@asynccontextmanager
async def noop_lifespan(app):
    yield


ADMIN_USER = TokenPayload(
    user_id="admin_user_123",
    username="admin",
    roles=["admin"],
    exp=datetime.now(timezone.utc) + timedelta(hours=1),
)


@pytest.fixture
def client(mock_db_session):
    """TestClient with dependency overrides for route-level tests."""
    from app.main import create_app
    from app.services.authorization import get_current_user

    app = create_app(test_mode=True)
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# TestListWebhookDeliveries — direct function calls
# ---------------------------------------------------------------------------


class TestListWebhookDeliveries:
    """Test webhook delivery listing via direct function calls."""

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
    async def test_list_webhook_deliveries_page_less_than_one(
        self, mock_db_session, mock_current_user
    ):
        """Test webhook delivery listing with page < 1."""
        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries(None, 0, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_per_page_too_small(
        self, mock_db_session, mock_current_user
    ):
        """Test webhook delivery listing with per_page < 1."""
        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries(None, 1, 0, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_per_page_too_large(
        self, mock_db_session, mock_current_user
    ):
        """Test webhook delivery listing with per_page > 100."""
        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries(None, 1, 101, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_database_error(self, mock_db_session, mock_current_user):
        """Test webhook delivery listing with database error."""
        mock_db_session.query.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await list_webhook_deliveries(None, 1, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# TestGetWebhookDelivery — direct function calls
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestRetryWebhookDelivery — direct function calls
# ---------------------------------------------------------------------------


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
        mock_webhook_delivery.attempts = 5
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


# ---------------------------------------------------------------------------
# TestDeleteWebhookDelivery — direct function calls
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestListDeadLetterDeliveries — direct function calls
# ---------------------------------------------------------------------------


class TestListDeadLetterDeliveries:
    """Test dead-letter webhook delivery listing."""

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_success(
        self, mock_db_session, mock_current_user, mock_dead_letter_delivery
    ):
        """Test successful dead-letter delivery listing."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_dead_letter_delivery
        ]

        result = await list_dead_letter_deliveries(1, 10, mock_db_session, mock_current_user)

        assert len(result.deliveries) == 1
        assert result.deliveries[0].delivery_id == "dl_delivery_456"
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_empty(self, mock_db_session, mock_current_user):
        """Test dead-letter delivery listing with no results."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 0
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = (
            []
        )

        result = await list_dead_letter_deliveries(1, 10, mock_db_session, mock_current_user)

        assert len(result.deliveries) == 0
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_page_less_than_one(
        self, mock_db_session, mock_current_user
    ):
        """Test dead-letter delivery listing with page < 1."""
        with pytest.raises(HTTPException) as exc_info:
            await list_dead_letter_deliveries(0, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_per_page_too_small(
        self, mock_db_session, mock_current_user
    ):
        """Test dead-letter delivery listing with per_page < 1."""
        with pytest.raises(HTTPException) as exc_info:
            await list_dead_letter_deliveries(1, 0, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_per_page_too_large(
        self, mock_db_session, mock_current_user
    ):
        """Test dead-letter delivery listing with per_page > 100."""
        with pytest.raises(HTTPException) as exc_info:
            await list_dead_letter_deliveries(1, 101, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_dead_letter_deliveries_database_error(
        self, mock_db_session, mock_current_user
    ):
        """Test dead-letter delivery listing with database error."""
        mock_db_session.query.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await list_dead_letter_deliveries(1, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# TestRetryDeadLetterDelivery — direct function calls
# ---------------------------------------------------------------------------


class TestRetryDeadLetterDelivery:
    """Test dead-letter webhook delivery retry."""

    @pytest.mark.asyncio
    async def test_retry_dead_letter_delivery_success(
        self, mock_db_session, mock_current_user, mock_dead_letter_delivery
    ):
        """Test successful dead-letter delivery retry."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )

        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await retry_dead_letter_delivery(
                "dl_delivery_456", mock_db_session, mock_current_user
            )

            assert result.delivery_id == "dl_delivery_456"
            assert result.success is True

    @pytest.mark.asyncio
    async def test_retry_dead_letter_delivery_not_found(self, mock_db_session, mock_current_user):
        """Test dead-letter delivery retry when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await retry_dead_letter_delivery("nonexistent", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_dead_letter_delivery_error(
        self, mock_db_session, mock_current_user, mock_dead_letter_delivery
    ):
        """Test dead-letter delivery retry with delivery error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )

        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            side_effect=Exception("Delivery failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await retry_dead_letter_delivery(
                    "dl_delivery_456", mock_db_session, mock_current_user
                )

            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# TestPurgeDeadLetterDelivery — direct function calls
# ---------------------------------------------------------------------------


class TestPurgeDeadLetterDelivery:
    """Test dead-letter webhook delivery purge."""

    @pytest.mark.asyncio
    async def test_purge_dead_letter_delivery_success(
        self, mock_db_session, mock_current_user, mock_dead_letter_delivery
    ):
        """Test successful dead-letter delivery purge."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )

        result = await purge_dead_letter_delivery(
            "dl_delivery_456", mock_db_session, mock_current_user
        )

        assert result is None  # 204 No Content
        mock_db_session.delete.assert_called_once_with(mock_dead_letter_delivery)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_purge_dead_letter_delivery_not_found(self, mock_db_session, mock_current_user):
        """Test dead-letter delivery purge when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await purge_dead_letter_delivery("nonexistent", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_purge_dead_letter_delivery_database_error(
        self, mock_db_session, mock_current_user, mock_dead_letter_delivery
    ):
        """Test dead-letter delivery purge with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await purge_dead_letter_delivery("dl_delivery_456", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# HTTP-level tests via TestClient (covers route registration + dependency paths)
# ---------------------------------------------------------------------------


class TestWebhookRoutesHTTP:
    """HTTP-level tests using TestClient to cover route wiring and response codes."""

    def test_list_deliveries_200(self, client, mock_db_session, mock_webhook_delivery):
        """GET /v1/webhooks/deliveries returns 200."""
        mock_db_session.query.return_value.count.return_value = 1
        mock_db_session.query.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_webhook_delivery
        ]
        response = client.get("/v1/webhooks/deliveries")
        assert response.status_code == 200

    def test_list_deliveries_with_status_filter_200(
        self, client, mock_db_session, mock_webhook_delivery
    ):
        """GET /v1/webhooks/deliveries?status_filter=pending returns 200."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_webhook_delivery
        ]
        response = client.get("/v1/webhooks/deliveries?status_filter=pending")
        assert response.status_code == 200

    def test_list_deliveries_invalid_status_400(self, client, mock_db_session):
        """GET /v1/webhooks/deliveries?status_filter=bad returns 400."""
        response = client.get("/v1/webhooks/deliveries?status_filter=bad")
        assert response.status_code == 400

    def test_list_deliveries_invalid_page_400(self, client, mock_db_session):
        """GET /v1/webhooks/deliveries?page=0 returns 400."""
        response = client.get("/v1/webhooks/deliveries?page=0")
        assert response.status_code == 400

    def test_list_deliveries_invalid_per_page_400(self, client, mock_db_session):
        """GET /v1/webhooks/deliveries?per_page=200 returns 400."""
        response = client.get("/v1/webhooks/deliveries?per_page=200")
        assert response.status_code == 400

    def test_list_deliveries_db_error_500(self, client, mock_db_session):
        """GET /v1/webhooks/deliveries returns 500 on db error."""
        mock_db_session.query.side_effect = Exception("db error")
        response = client.get("/v1/webhooks/deliveries")
        assert response.status_code == 500

    def test_get_delivery_200(self, client, mock_db_session, mock_webhook_delivery):
        """GET /v1/webhooks/deliveries/{id} returns 200."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        response = client.get("/v1/webhooks/deliveries/delivery_123")
        assert response.status_code == 200

    def test_get_delivery_404(self, client, mock_db_session):
        """GET /v1/webhooks/deliveries/{id} returns 404 when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        response = client.get("/v1/webhooks/deliveries/nonexistent")
        assert response.status_code == 404

    def test_retry_delivery_200(self, client, mock_db_session, mock_webhook_delivery):
        """POST /v1/webhooks/deliveries/{id}/retry returns 200."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.post("/v1/webhooks/deliveries/delivery_123/retry")
        assert response.status_code == 200

    def test_retry_delivery_404(self, client, mock_db_session):
        """POST /v1/webhooks/deliveries/{id}/retry returns 404 when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        response = client.post("/v1/webhooks/deliveries/nonexistent/retry")
        assert response.status_code == 404

    def test_retry_delivery_400_already_delivered(
        self, client, mock_db_session, mock_webhook_delivery
    ):
        """POST /v1/webhooks/deliveries/{id}/retry returns 400 when already delivered."""
        mock_webhook_delivery.status = "delivered"
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        response = client.post("/v1/webhooks/deliveries/delivery_123/retry")
        assert response.status_code == 400

    def test_retry_delivery_400_max_attempts(self, client, mock_db_session, mock_webhook_delivery):
        """POST /v1/webhooks/deliveries/{id}/retry returns 400 when max attempts exceeded."""
        mock_webhook_delivery.attempts = 100
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        with patch("app.routes.webhooks.settings") as mock_settings:
            mock_settings.webhook_retry_limit = 5
            response = client.post("/v1/webhooks/deliveries/delivery_123/retry")
        assert response.status_code == 400

    def test_retry_delivery_500_on_error(self, client, mock_db_session, mock_webhook_delivery):
        """POST /v1/webhooks/deliveries/{id}/retry returns 500 on delivery error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            response = client.post("/v1/webhooks/deliveries/delivery_123/retry")
        assert response.status_code == 500

    def test_delete_delivery_204(self, client, mock_db_session, mock_webhook_delivery):
        """DELETE /v1/webhooks/deliveries/{id} returns 204."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        response = client.delete("/v1/webhooks/deliveries/delivery_123")
        assert response.status_code == 204

    def test_delete_delivery_404(self, client, mock_db_session):
        """DELETE /v1/webhooks/deliveries/{id} returns 404 when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        response = client.delete("/v1/webhooks/deliveries/nonexistent")
        assert response.status_code == 404

    def test_delete_delivery_500_on_error(self, client, mock_db_session, mock_webhook_delivery):
        """DELETE /v1/webhooks/deliveries/{id} returns 500 on db error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_webhook_delivery
        )
        mock_db_session.commit.side_effect = Exception("db error")
        response = client.delete("/v1/webhooks/deliveries/delivery_123")
        assert response.status_code == 500

    def test_list_dead_letter_200(self, client, mock_db_session, mock_dead_letter_delivery):
        """GET /v1/webhooks/dead-letter returns 200."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_dead_letter_delivery
        ]
        response = client.get("/v1/webhooks/dead-letter")
        assert response.status_code == 200

    def test_list_dead_letter_invalid_page_400(self, client, mock_db_session):
        """GET /v1/webhooks/dead-letter?page=0 returns 400."""
        response = client.get("/v1/webhooks/dead-letter?page=0")
        assert response.status_code == 400

    def test_list_dead_letter_invalid_per_page_400(self, client, mock_db_session):
        """GET /v1/webhooks/dead-letter?per_page=0 returns 400."""
        response = client.get("/v1/webhooks/dead-letter?per_page=0")
        assert response.status_code == 400

    def test_list_dead_letter_per_page_too_large_400(self, client, mock_db_session):
        """GET /v1/webhooks/dead-letter?per_page=200 returns 400."""
        response = client.get("/v1/webhooks/dead-letter?per_page=200")
        assert response.status_code == 400

    def test_list_dead_letter_db_error_500(self, client, mock_db_session):
        """GET /v1/webhooks/dead-letter returns 500 on db error."""
        mock_db_session.query.side_effect = Exception("db error")
        response = client.get("/v1/webhooks/dead-letter")
        assert response.status_code == 500

    def test_retry_dead_letter_200(self, client, mock_db_session, mock_dead_letter_delivery):
        """POST /v1/webhooks/dead-letter/{id}/retry returns 200."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )
        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.post("/v1/webhooks/dead-letter/dl_delivery_456/retry")
        assert response.status_code == 200

    def test_retry_dead_letter_404(self, client, mock_db_session):
        """POST /v1/webhooks/dead-letter/{id}/retry returns 404 when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        response = client.post("/v1/webhooks/dead-letter/nonexistent/retry")
        assert response.status_code == 404

    def test_retry_dead_letter_500_on_error(
        self, client, mock_db_session, mock_dead_letter_delivery
    ):
        """POST /v1/webhooks/dead-letter/{id}/retry returns 500 on delivery error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )
        with patch(
            "app.routes.webhooks.WebhookManager.deliver_webhook",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            response = client.post("/v1/webhooks/dead-letter/dl_delivery_456/retry")
        assert response.status_code == 500

    def test_purge_dead_letter_204(self, client, mock_db_session, mock_dead_letter_delivery):
        """DELETE /v1/webhooks/dead-letter/{id} returns 204."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )
        response = client.delete("/v1/webhooks/dead-letter/dl_delivery_456")
        assert response.status_code == 204

    def test_purge_dead_letter_404(self, client, mock_db_session):
        """DELETE /v1/webhooks/dead-letter/{id} returns 404 when not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        response = client.delete("/v1/webhooks/dead-letter/nonexistent")
        assert response.status_code == 404

    def test_purge_dead_letter_500_on_error(
        self, client, mock_db_session, mock_dead_letter_delivery
    ):
        """DELETE /v1/webhooks/dead-letter/{id} returns 500 on db error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_dead_letter_delivery
        )
        mock_db_session.commit.side_effect = Exception("db error")
        response = client.delete("/v1/webhooks/dead-letter/dl_delivery_456")
        assert response.status_code == 500
