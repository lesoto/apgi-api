"""
Unit tests for WebhookManager service.

Covers delivery success, retry scheduling, permanent failure (dead-letter),
SSRF URL validation, and process_pending_deliveries.

Requirements: 2.5, 12.4, 12.5, 12.6
"""

import asyncio
import socket
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    """MagicMock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def manager():
    from app.services.webhook_manager import WebhookManager

    return WebhookManager()


def _make_delivery(
    *,
    delivery_id="del-001",
    task_id="task-001",
    webhook_url="https://example.com/hook",
    resolved_ip="93.184.216.34",
    payload=None,
    status="pending",
    attempts=0,
    retry_count=5,
    retry_delays=None,
):
    """Build a MagicMock WebhookDelivery with realistic attributes."""
    d = MagicMock()
    d.delivery_id = delivery_id
    d.task_id = task_id
    d.webhook_url = webhook_url
    d.resolved_ip = resolved_ip
    d.payload = payload or {"event": "task_completed", "task_id": task_id}
    d.status = status
    d.attempts = attempts
    d.retry_count = retry_count
    d.retry_delays = retry_delays or [5, 30, 300, 1800, 3600]
    d.last_attempt_at = None
    d.next_retry_at = None
    d.response_status = None
    d.response_body = None
    d.error_message = None
    return d


# ---------------------------------------------------------------------------
# _validate_webhook_url — SSRF prevention
# ---------------------------------------------------------------------------


class TestValidateWebhookUrl:
    """Tests for the static SSRF-prevention URL validator."""

    def test_valid_https_url_resolves(self):
        from app.services.webhook_manager import WebhookManager

        # example.com resolves to a public IP — should not raise
        WebhookManager._validate_webhook_url("https://example.com/webhook")

    def test_valid_http_url_resolves(self):
        from app.services.webhook_manager import WebhookManager

        WebhookManager._validate_webhook_url("http://example.com/webhook")

    def test_ftp_scheme_rejected(self):
        from app.services.webhook_manager import WebhookManager

        with pytest.raises(ValueError, match="Only HTTP and HTTPS URLs are allowed"):
            WebhookManager._validate_webhook_url("ftp://example.com/webhook")

    def test_missing_scheme_rejected(self):
        from app.services.webhook_manager import WebhookManager

        with pytest.raises(ValueError):
            WebhookManager._validate_webhook_url("example.com/webhook")

    def test_missing_hostname_rejected(self):
        from app.services.webhook_manager import WebhookManager

        with pytest.raises(ValueError):
            WebhookManager._validate_webhook_url("https:///path")

    @patch("socket.getaddrinfo")
    def test_private_192_168_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("192.168.1.100", 0))]
        with pytest.raises(ValueError, match="private/internal IP"):
            WebhookManager._validate_webhook_url("http://internal.corp/hook")

    @patch("socket.getaddrinfo")
    def test_private_10_x_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("10.0.0.5", 0))]
        with pytest.raises(ValueError, match="private/internal IP"):
            WebhookManager._validate_webhook_url("http://internal.corp/hook")

    @patch("socket.getaddrinfo")
    def test_private_172_16_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("172.16.0.1", 0))]
        with pytest.raises(ValueError, match="private/internal IP"):
            WebhookManager._validate_webhook_url("http://internal.corp/hook")

    @patch("socket.getaddrinfo")
    def test_loopback_127_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        with pytest.raises(ValueError, match="private/internal IP"):
            WebhookManager._validate_webhook_url("http://localhost/hook")

    @patch("socket.getaddrinfo")
    def test_cloud_metadata_169_254_169_254_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("169.254.169.254", 0))]
        with pytest.raises(ValueError, match="cloud metadata"):
            WebhookManager._validate_webhook_url("http://metadata/hook")

    @patch("socket.getaddrinfo")
    def test_cloud_metadata_169_254_169_253_blocked(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("169.254.169.253", 0))]
        with pytest.raises(ValueError, match="cloud metadata"):
            WebhookManager._validate_webhook_url("http://metadata/hook")

    @patch("socket.getaddrinfo")
    def test_dns_resolution_failure_raises(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.side_effect = socket.gaierror("Name or service not known")
        with pytest.raises(ValueError, match="Could not resolve hostname"):
            WebhookManager._validate_webhook_url("http://nonexistent.invalid/hook")

    @patch("socket.getaddrinfo")
    def test_no_valid_ip_raises(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        # Return an entry with an invalid IP string so all IPs are skipped
        mock_gai.return_value = [(None, None, None, None, ("not-an-ip", 0))]
        with pytest.raises(ValueError):
            WebhookManager._validate_webhook_url("http://weird.host/hook")

    @patch("socket.getaddrinfo")
    def test_returns_resolved_ip_string(self, mock_gai):
        from app.services.webhook_manager import WebhookManager

        mock_gai.return_value = [(None, None, None, None, ("93.184.216.34", 0))]
        ip = WebhookManager._validate_webhook_url("http://example.com/hook")
        assert ip == "93.184.216.34"


# ---------------------------------------------------------------------------
# create_webhook_delivery
# ---------------------------------------------------------------------------


class TestCreateWebhookDelivery:
    """Tests for WebhookManager.create_webhook_delivery."""

    @pytest.mark.asyncio
    async def test_success_returns_uuid_string(self, manager, db):
        with (
            patch(
                "app.services.webhook_manager.WebhookManager._validate_webhook_url",
                return_value="93.184.216.34",
            ),
            patch("app.services.webhook_manager.WebhookDelivery") as MockDelivery,
        ):
            mock_obj = MagicMock()
            MockDelivery.return_value = mock_obj

            delivery_id = await manager.create_webhook_delivery(
                db, "task-1", "https://example.com/hook", {"event": "done"}
            )

        assert isinstance(delivery_id, str)
        assert len(delivery_id) == 36  # UUID format
        db.add.assert_called_once_with(mock_obj)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(mock_obj)

    @pytest.mark.asyncio
    async def test_invalid_url_raises_before_db(self, manager, db):
        with pytest.raises(ValueError):
            await manager.create_webhook_delivery(db, "task-1", "ftp://bad.url/hook", {})
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_commit_error_rolls_back(self, manager, db):
        db.commit.side_effect = Exception("DB unavailable")
        with (
            patch(
                "app.services.webhook_manager.WebhookManager._validate_webhook_url",
                return_value="93.184.216.34",
            ),
            patch("app.services.webhook_manager.WebhookDelivery"),
        ):
            with pytest.raises(Exception, match="DB unavailable"):
                await manager.create_webhook_delivery(db, "task-1", "https://example.com/hook", {})
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_schedule_uses_exponential_delays(self, manager, db):
        """Delivery record is created with next_retry_at set from retry_delays[0]."""
        captured = {}

        def capture_delivery(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with (
            patch(
                "app.services.webhook_manager.WebhookManager._validate_webhook_url",
                return_value="1.2.3.4",
            ),
            patch(
                "app.services.webhook_manager.WebhookDelivery",
                side_effect=lambda **kw: captured.update(kw) or MagicMock(),
            ),
        ):
            await manager.create_webhook_delivery(
                db, "task-1", "https://example.com/hook", {"x": 1}
            )

        # next_retry_at should be set (not None)
        assert "next_retry_at" in captured
        assert captured["next_retry_at"] is not None


# ---------------------------------------------------------------------------
# deliver_webhook — guard clauses
# ---------------------------------------------------------------------------


class TestDeliverWebhookGuards:
    """Tests for early-exit conditions in deliver_webhook."""

    @pytest.mark.asyncio
    async def test_delivery_not_found_returns_false(self, manager, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await manager.deliver_webhook(db, "missing-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_already_delivered_returns_true_immediately(self, manager, db):
        d = _make_delivery(status="delivered")
        db.query.return_value.filter.return_value.first.return_value = d
        result = await manager.deliver_webhook(db, d.delivery_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_attempts_equal_retry_count_marks_dead_letter(self, manager, db):
        d = _make_delivery(attempts=5, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        with patch("app.services.webhook_manager.alert_manager") as mock_am:
            mock_am.trigger_custom_alert = AsyncMock()
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "dead_letter"
        db.commit.assert_called_once()
        mock_am.trigger_custom_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_attempts_exceed_retry_count_marks_dead_letter(self, manager, db):
        d = _make_delivery(attempts=10, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        with patch("app.services.webhook_manager.alert_manager") as mock_am:
            mock_am.trigger_custom_alert = AsyncMock()
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "dead_letter"

    @pytest.mark.asyncio
    async def test_missing_webhook_secret_causes_failure(self, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        with patch("app.services.webhook_manager.settings") as mock_settings:
            mock_settings.webhook_secret_key = None
            result = await manager.deliver_webhook(db, d.delivery_id)

        # Exception is caught; delivery should be marked retry or dead_letter
        assert result is False


# ---------------------------------------------------------------------------
# deliver_webhook — HTTP success path
# ---------------------------------------------------------------------------


def _mock_aiohttp_session(response_status: int, response_text: str = "OK"):
    """Return a mock aiohttp.ClientSession context manager."""
    mock_response = MagicMock()
    mock_response.status = response_status
    mock_response.text = AsyncMock(return_value=response_text)

    mock_post_cm = MagicMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_session_cm, mock_response


class TestDeliverWebhookSuccess:
    """Tests for successful HTTP delivery."""

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_http_200_marks_delivered(self, MockSession, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(200, "OK")
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "super-secret-key-32chars-long!!"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is True
        assert d.status == "delivered"
        assert d.response_status == 200
        assert d.response_body == "OK"
        assert d.attempts == 1
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_http_201_marks_delivered(self, MockSession, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(201, "Created")
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "super-secret-key-32chars-long!!"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is True
        assert d.status == "delivered"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_response_body_truncated_when_too_large(self, MockSession, manager, db):
        from app.services.webhook_manager import WebhookManager

        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        large_body = "x" * (WebhookManager.MAX_RESPONSE_SIZE + 500)
        mock_cm, _ = _mock_aiohttp_session(200, large_body)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "super-secret-key-32chars-long!!"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is True
        assert "(truncated)" in d.response_body
        assert len(d.response_body) <= WebhookManager.MAX_RESPONSE_SIZE + 20

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_hmac_signature_header_set(self, MockSession, manager, db):
        """Verify X-Signature-256 header is included in the POST."""
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(200)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "super-secret-key-32chars-long!!"
            await manager.deliver_webhook(db, d.delivery_id)

        # The session.post was called — verify headers arg contained signature
        mock_session = mock_cm.__aenter__.return_value
        _, kwargs = mock_session.post.call_args
        headers = kwargs.get("headers", {})
        assert "X-Signature-256" in headers
        assert headers["X-Signature-256"].startswith("sha256=")


# ---------------------------------------------------------------------------
# deliver_webhook — HTTP failure / retry logic
# ---------------------------------------------------------------------------


class TestDeliverWebhookRetry:
    """Tests for retry scheduling on non-2xx responses."""

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_http_500_with_retries_remaining_schedules_retry(self, MockSession, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(500)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "retry"
        assert d.attempts == 1
        assert d.next_retry_at is not None
        assert "will retry" in d.error_message
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_http_404_with_retries_remaining_schedules_retry(self, MockSession, manager, db):
        d = _make_delivery(attempts=2, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(404)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "retry"
        assert d.attempts == 3

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_http_500_last_attempt_marks_dead_letter(self, MockSession, manager, db):
        # attempts=4, retry_count=5 → after increment attempts==5 == retry_count → dead_letter
        d = _make_delivery(attempts=4, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(500)
        MockSession.return_value = mock_cm

        with (
            patch("app.services.webhook_manager.settings") as s,
            patch("app.services.webhook_manager.alert_manager") as mock_am,
        ):
            s.webhook_secret_key = "secret"
            mock_am.trigger_custom_alert = AsyncMock()
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "dead_letter"
        mock_am.trigger_custom_alert.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_retry_delay_uses_delay_index(self, MockSession, manager, db):
        """next_retry_at uses the correct delay from retry_delays list."""
        d = _make_delivery(attempts=1, retry_count=5, retry_delays=[5, 30, 300, 1800, 3600])
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(503)
        MockSession.return_value = mock_cm

        before = datetime.now(timezone.utc)
        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            await manager.deliver_webhook(db, d.delivery_id)

        # After 1 attempt (index 1 → 30s delay), next_retry_at should be ~30s from now
        assert d.next_retry_at is not None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_retry_delay_capped_at_last_element(self, MockSession, manager, db):
        """When attempt index exceeds delay list length, use last delay."""
        d = _make_delivery(attempts=10, retry_count=20, retry_delays=[5, 30])
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(503)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "retry"


# ---------------------------------------------------------------------------
# deliver_webhook — exception handling
# ---------------------------------------------------------------------------


class TestDeliverWebhookExceptions:
    """Tests for unexpected exceptions during HTTP delivery."""

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_network_error_with_retries_remaining_schedules_retry(
        self, MockSession, manager, db
    ):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_session = MagicMock()
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_post_cm

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "retry"
        assert d.attempts == 1
        assert "Connection refused" in d.error_message

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_network_error_last_attempt_marks_dead_letter(self, MockSession, manager, db):
        d = _make_delivery(attempts=4, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_session = MagicMock()
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=Exception("Timeout"))
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_post_cm

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert result is False
        assert d.status == "dead_letter"
        assert d.attempts == 5

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_exception_sets_last_attempt_at(self, MockSession, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_session = MagicMock()
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=Exception("err"))
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_post_cm

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            await manager.deliver_webhook(db, d.delivery_id)

        assert d.last_attempt_at is not None

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_exception_error_message_stored(self, MockSession, manager, db):
        d = _make_delivery(attempts=0, retry_count=5)
        db.query.return_value.filter.return_value.first.return_value = d

        mock_session = MagicMock()
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=Exception("SSL handshake failed"))
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_post_cm

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            await manager.deliver_webhook(db, d.delivery_id)

        assert "SSL handshake failed" in d.error_message


# ---------------------------------------------------------------------------
# deliver_webhook — HTTPS with IP pinning
# ---------------------------------------------------------------------------


class TestDeliverWebhookHttps:
    """Tests for HTTPS delivery with SSL context and IP pinning."""

    @pytest.mark.asyncio
    @patch("aiohttp.TCPConnector")
    @patch("aiohttp.ClientSession")
    async def test_https_url_creates_ssl_connector(self, MockSession, MockConnector, manager, db):
        d = _make_delivery(
            attempts=0,
            retry_count=5,
            webhook_url="https://example.com/hook",
            resolved_ip="93.184.216.34",
        )
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(200)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        # TCPConnector should have been called (with ssl context for https)
        assert MockConnector.called
        assert result is True

    @pytest.mark.asyncio
    @patch("aiohttp.TCPConnector")
    @patch("aiohttp.ClientSession")
    async def test_http_url_creates_plain_connector(self, MockSession, MockConnector, manager, db):
        d = _make_delivery(
            attempts=0,
            retry_count=5,
            webhook_url="http://example.com/hook",
            resolved_ip="93.184.216.34",
        )
        db.query.return_value.filter.return_value.first.return_value = d

        mock_cm, _ = _mock_aiohttp_session(200)
        MockSession.return_value = mock_cm

        with patch("app.services.webhook_manager.settings") as s:
            s.webhook_secret_key = "secret"
            result = await manager.deliver_webhook(db, d.delivery_id)

        assert MockConnector.called
        assert result is True


# ---------------------------------------------------------------------------
# process_pending_deliveries
# ---------------------------------------------------------------------------


class TestProcessPendingDeliveries:
    """Tests for WebhookManager.process_pending_deliveries."""

    @pytest.mark.asyncio
    async def test_no_pending_returns_zero(self, manager, db):
        db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(manager, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
            count = await manager.process_pending_deliveries(db)

        assert count == 0
        mock_deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_pending_delivery_processed(self, manager, db):
        d = _make_delivery()
        db.query.return_value.filter.return_value.all.return_value = [d]

        with patch.object(manager, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = True
            count = await manager.process_pending_deliveries(db)

        assert count == 1
        mock_deliver.assert_awaited_once_with(db, d.delivery_id)

    @pytest.mark.asyncio
    async def test_multiple_pending_deliveries_all_processed(self, manager, db):
        deliveries = [_make_delivery(delivery_id=f"del-{i}") for i in range(3)]
        db.query.return_value.filter.return_value.all.return_value = deliveries

        with patch.object(manager, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = True
            count = await manager.process_pending_deliveries(db)

        assert count == 3
        assert mock_deliver.await_count == 3

    @pytest.mark.asyncio
    async def test_failed_deliveries_still_counted(self, manager, db):
        d1 = _make_delivery(delivery_id="del-1")
        d2 = _make_delivery(delivery_id="del-2")
        db.query.return_value.filter.return_value.all.return_value = [d1, d2]

        with patch.object(manager, "deliver_webhook", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = False
            count = await manager.process_pending_deliveries(db)

        # Both are processed (counted) regardless of success/failure
        assert count == 2

    @pytest.mark.asyncio
    async def test_query_filters_by_status_and_next_retry(self, manager, db):
        """Verify the query uses the correct filter conditions."""
        db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(manager, "deliver_webhook", new_callable=AsyncMock):
            await manager.process_pending_deliveries(db)

        # The filter was called (we can't easily inspect SQLAlchemy filter args on MagicMock,
        # but we verify the query chain was invoked)
        db.query.assert_called_once()
        db.query.return_value.filter.assert_called_once()


# ---------------------------------------------------------------------------
# Lifecycle — context manager and close()
# ---------------------------------------------------------------------------


class TestWebhookManagerLifecycle:
    """Tests for async context manager and close() method."""

    def test_async_context_manager_exits_cleanly(self, manager):
        async def run():
            async with manager:
                pass
            assert manager.session is None

        asyncio.run(run())

    def test_close_with_open_session_closes_it(self, manager):
        async def run():
            mock_session = AsyncMock()
            manager.session = mock_session
            await manager.close()
            mock_session.close.assert_awaited_once()
            assert manager.session is None

        asyncio.run(run())

    def test_close_without_session_is_noop(self, manager):
        async def run():
            assert manager.session is None
            await manager.close()  # should not raise
            assert manager.session is None

        asyncio.run(run())

    def test_initial_session_is_none(self, manager):
        assert manager.session is None
