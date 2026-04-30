"""
Extended coverage tests for app/middleware/alerting.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.alerting import (
    Alert,
    AlertEscalationPolicy,
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertTemplate,
    PagerDutyNotificationChannel,
    SlackNotificationChannel,
    TeamsNotificationChannel,
    WebhookNotificationChannel,
)


@pytest.mark.asyncio
async def test_webhook_channel_success():
    """Test WebhookNotificationChannel success path."""
    channel = WebhookNotificationChannel(webhook_url="http://example.com/webhook")
    alert = Alert(title="Test", message="Msg", severity=AlertSeverity.INFO)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        assert await channel.send_alert(alert) is True


@pytest.mark.asyncio
async def test_slack_channel_with_metadata():
    """Test SlackNotificationChannel with metadata escalation."""
    channel = SlackNotificationChannel(webhook_url="http://example.com/slack", channel="#alerts")
    alert = Alert(
        title="Test", message="Msg", severity=AlertSeverity.ERROR, metadata={"key": "val"}
    )

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        assert await channel.send_alert(alert) is True
        # Check that metadata was included in payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert any(f["title"] == "key" for f in payload["attachments"][0]["fields"])


@pytest.mark.asyncio
async def test_pagerduty_channel():
    """Test PagerDutyNotificationChannel."""
    channel = PagerDutyNotificationChannel(integration_key="key")
    alert = Alert(title="Test", message="Msg", severity=AlertSeverity.CRITICAL)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=202)
        mock_post.return_value.json = AsyncMock(return_value={"dedup_key": "123"})
        assert await channel.send_alert(alert) is True


@pytest.mark.asyncio
async def test_teams_channel():
    """Test TeamsNotificationChannel."""
    channel = TeamsNotificationChannel(webhook_url="http://example.com/teams")
    alert = Alert(
        title="Test", message="Msg", severity=AlertSeverity.WARNING, metadata={"key": "val"}
    )

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        assert await channel.send_alert(alert) is True


@pytest.mark.asyncio
async def test_alert_rule_cooldown():
    """Test AlertRule cooldown logic."""
    template = AlertTemplate(name="test", title_template="T", message_template="M")
    rule = AlertRule(
        name="rule", condition=AsyncMock(return_value=True), template=template, cooldown_seconds=60
    )

    # First trigger
    alert1 = await rule.should_trigger()
    assert alert1 is not None

    # Second trigger immediately (should be blocked by cooldown)
    alert2 = await rule.should_trigger()
    assert alert2 is None


@pytest.mark.asyncio
async def test_alert_manager_escalation():
    """Test AlertManager escalation logic."""
    manager = AlertManager()
    channel = MagicMock(spec=WebhookNotificationChannel)
    channel.send_alert = AsyncMock(return_value=True)
    manager.add_channel(channel)

    policy = AlertEscalationPolicy(
        initial_severity=AlertSeverity.INFO,
        escalation_rules=[{"after_seconds": 0, "severity": AlertSeverity.CRITICAL}],
    )

    alert = Alert(title="Test", message="Msg", severity=AlertSeverity.INFO)
    alert.escalation_policy = policy
    manager.active_alerts["test"] = alert

    # Force escalation check
    await manager.escalate_alerts()

    assert alert.severity == AlertSeverity.CRITICAL
    assert channel.send_alert.call_count >= 1
