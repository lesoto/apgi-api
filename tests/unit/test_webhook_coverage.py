"""
Coverage tests for app/services/webhook_manager.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.models import WebhookDelivery
from app.services.webhook_manager import WebhookManager


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.__enter__.return_value = db
    return db


@pytest.mark.asyncio
async def test_webhook_manager_validate_url_success():
    with patch("socket.getaddrinfo") as mock_getaddr:
        mock_getaddr.return_value = [(None, None, None, None, ("93.184.216.34", 80))]

        resolved = WebhookManager._validate_webhook_url("https://example.com/callback")
        assert resolved == "93.184.216.34"


@pytest.mark.asyncio
async def test_webhook_manager_validate_url_private():
    with patch("socket.getaddrinfo") as mock_getaddr:
        mock_getaddr.return_value = [(None, None, None, None, ("127.0.0.1", 80))]

        with pytest.raises(ValueError, match="private/internal IP address"):
            WebhookManager._validate_webhook_url("http://localhost")


@pytest.mark.asyncio
async def test_webhook_manager_create_delivery(mock_db):
    wm = WebhookManager()
    with patch.object(wm, "_validate_webhook_url", return_value="1.2.3.4"):
        delivery_id = await wm.create_webhook_delivery(mock_db, "t1", "https://ok.com", {"p": 1})
        assert delivery_id is not None
        assert mock_db.add.called


@pytest.mark.asyncio
async def test_webhook_manager_deliver_success(mock_db):
    wm = WebhookManager()
    delivery = MagicMock(spec=WebhookDelivery)
    delivery.delivery_id = "d1"
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.retry_count = 5
    delivery.payload = {"a": 1}
    delivery.webhook_url = "https://ok.com/hook"
    delivery.resolved_ip = "1.2.3.4"

    mock_db.query.return_value.filter.return_value.first.return_value = delivery

    with (
        patch("app.services.webhook_manager.settings") as mock_settings,
        patch("aiohttp.ClientSession.post") as mock_post,
    ):

        mock_settings.webhook_secret_key = "secret"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text.return_value = "OK"
        mock_post.return_value.__aenter__.return_value = mock_resp

        success = await wm.deliver_webhook(mock_db, "d1")
        assert success is True
        assert delivery.status == "delivered"


@pytest.mark.asyncio
async def test_webhook_manager_deliver_failure_retry(mock_db):
    wm = WebhookManager()
    delivery = MagicMock(spec=WebhookDelivery)
    delivery.delivery_id = "d1"
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.retry_count = 5
    delivery.payload = {"a": 1}
    delivery.webhook_url = "https://ok.com/hook"
    delivery.resolved_ip = "1.2.3.4"
    delivery.retry_delays = [1]

    mock_db.query.return_value.filter.return_value.first.return_value = delivery

    with (
        patch("app.services.webhook_manager.settings") as mock_settings,
        patch("aiohttp.ClientSession.post") as mock_post,
    ):

        mock_settings.webhook_secret_key = "secret"

        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_post.return_value.__aenter__.return_value = mock_resp

        success = await wm.deliver_webhook(mock_db, "d1")
        assert success is False
        assert delivery.status == "retry"


@pytest.mark.asyncio
async def test_webhook_manager_deliver_dead_letter(mock_db):
    wm = WebhookManager()
    delivery = MagicMock(spec=WebhookDelivery)
    delivery.delivery_id = "d1"
    delivery.status = "pending"
    delivery.attempts = 5
    delivery.retry_count = 5

    mock_db.query.return_value.filter.return_value.first.return_value = delivery

    with patch(
        "app.services.webhook_manager.alert_manager.trigger_custom_alert", new_callable=AsyncMock
    ) as mock_alert:
        success = await wm.deliver_webhook(mock_db, "d1")
        assert success is False
        assert delivery.status == "dead_letter"
        assert mock_alert.called


@pytest.mark.asyncio
async def test_webhook_manager_process_pending(mock_db):
    wm = WebhookManager()
    delivery = MagicMock()
    delivery.delivery_id = "d1"
    mock_db.query.return_value.filter.return_value.all.return_value = [delivery]

    with patch.object(wm, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
        count = await wm.process_pending_deliveries(mock_db)
        assert count == 1
        assert mock_deliver.called


@pytest.mark.asyncio
async def test_webhook_manager_context_manager():
    async with WebhookManager() as wm:
        assert wm is not None


@pytest.mark.asyncio
async def test_webhook_manager_validate_url_failures():
    with pytest.raises(ValueError) as exc_info:
        WebhookManager._validate_webhook_url("not-a-url")
    assert "Invalid webhook URL" in str(exc_info.value)
    assert "Invalid URL format" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        WebhookManager._validate_webhook_url("ftp://server.com")
    assert "Invalid webhook URL" in str(exc_info.value)
    assert "Only HTTP and HTTPS URLs are allowed" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        WebhookManager._validate_webhook_url("http:///path")
    assert "Invalid webhook URL" in str(exc_info.value)
    assert "Invalid URL format" in str(exc_info.value)

    with patch("socket.getaddrinfo", side_effect=Exception("DNS Fail")):
        with pytest.raises(ValueError) as exc_info:
            WebhookManager._validate_webhook_url("http://invalid.host")
        assert "Invalid webhook URL" in str(exc_info.value)
        assert "DNS Fail" in str(exc_info.value)


@pytest.mark.asyncio
async def test_webhook_manager_create_delivery_error(mock_db):
    wm = WebhookManager()
    mock_db.commit.side_effect = Exception("DB Fail")
    with patch.object(wm, "_validate_webhook_url", return_value="1.2.3.4"):
        with pytest.raises(Exception, match="DB Fail"):
            await wm.create_webhook_delivery(mock_db, "t1", "http://ok.com", {})
        assert mock_db.rollback.called


@pytest.mark.asyncio
async def test_webhook_manager_deliver_not_found(mock_db):
    wm = WebhookManager()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    assert await wm.deliver_webhook(mock_db, "missing") is False


@pytest.mark.asyncio
async def test_webhook_manager_deliver_no_secret(mock_db):
    wm = WebhookManager()
    delivery = MagicMock(spec=WebhookDelivery)
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.retry_count = 5
    mock_db.query.return_value.filter.return_value.first.return_value = delivery

    with patch("app.services.webhook_manager.settings") as mock_settings:
        mock_settings.webhook_secret_key = None
        await wm.deliver_webhook(mock_db, "d1")
        assert delivery.status == "retry"


@pytest.mark.asyncio
async def test_webhook_manager_deliver_truncation(mock_db):
    wm = WebhookManager()
    delivery = MagicMock(spec=WebhookDelivery)
    delivery.delivery_id = "d1"
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.retry_count = 5
    delivery.payload = {"a": 1}
    delivery.webhook_url = "http://ok.com/hook"
    delivery.resolved_ip = "1.2.3.4"
    mock_db.query.return_value.filter.return_value.first.return_value = delivery

    with (
        patch("app.services.webhook_manager.settings") as mock_settings,
        patch("aiohttp.ClientSession.post") as mock_post,
    ):
        mock_settings.webhook_secret_key = "secret"
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text.return_value = "X" * (wm.MAX_RESPONSE_SIZE + 10)
        mock_post.return_value.__aenter__.return_value = mock_resp

        await wm.deliver_webhook(mock_db, "d1")
        assert "truncated" in delivery.response_body
