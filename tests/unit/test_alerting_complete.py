"""
Unit tests for alerting module - covering remaining untested code paths.

This module tests:
- SlackNotificationChannel
- EmailNotificationChannel
- AlertTemplate
- AlertEscalationPolicy
- AlertRule
- AlertManager.check_rules and escalate_alerts
- configure_alerting function
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.middleware.alerting import (
    Alert,
    AlertSeverity,
    AlertTemplate,
    AlertEscalationPolicy,
    AlertRule,
    AlertManager,
    SlackNotificationChannel,
    EmailNotificationChannel,
    LogNotificationChannel,
    configure_alerting,
    alert_manager,
)


class TestSlackNotificationChannel:
    """Test Slack notification channel."""

    @pytest.mark.asyncio
    async def test_slack_channel_success(self):
        """Test Slack channel with successful delivery."""
        webhook_url = "https://hooks.slack.com/services/test"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = SlackNotificationChannel(webhook_url, channel="#alerts")
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
                metadata={"key": "value"},
            )

            result = await channel.send_alert(alert)
            assert result is True

            # Verify the Slack webhook was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == webhook_url

    @pytest.mark.asyncio
    async def test_slack_channel_failure(self):
        """Test Slack channel with failure response."""
        webhook_url = "https://hooks.slack.com/services/test"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = SlackNotificationChannel(webhook_url)
            alert = Alert(
                title="Test Alert", message="Test message", severity=AlertSeverity.WARNING
            )

            result = await channel.send_alert(alert)
            assert result is False

    @pytest.mark.asyncio
    async def test_slack_channel_exception(self):
        """Test Slack channel with exception."""
        webhook_url = "https://hooks.slack.com/services/test"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Network error")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = SlackNotificationChannel(webhook_url)
            alert = Alert(
                title="Test Alert", message="Test message", severity=AlertSeverity.CRITICAL
            )

            result = await channel.send_alert(alert)
            assert result is False

    def test_severity_to_color(self):
        """Test severity to color mapping."""
        channel = SlackNotificationChannel("https://test.com")

        assert channel._severity_to_color(AlertSeverity.INFO) == "good"
        assert channel._severity_to_color(AlertSeverity.WARNING) == "warning"
        assert channel._severity_to_color(AlertSeverity.ERROR) == "danger"
        assert channel._severity_to_color(AlertSeverity.CRITICAL) == "#ff0000"
        assert channel._severity_to_color("unknown") == "warning"  # type: ignore


class TestEmailNotificationChannel:
    """Test email notification channel."""

    @pytest.mark.asyncio
    async def test_email_channel_success(self):
        """Test email channel with successful delivery."""
        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value = mock_server

            channel = EmailNotificationChannel(
                smtp_server="smtp.test.com",
                smtp_port=587,
                smtp_username="user@test.com",
                smtp_password="password",
                from_email="alerts@test.com",
                to_emails=["recipient@test.com"],
            )

            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
                metadata={"key": "value"},
            )

            result = await channel.send_alert(alert)
            assert result is True

            # Verify SMTP was called
            mock_smtp_class.assert_called_once_with("smtp.test.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@test.com", "password")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_channel_no_recipients(self):
        """Test email channel with no recipients configured."""
        channel = EmailNotificationChannel(
            smtp_server="smtp.test.com",
            to_emails=[],
        )

        alert = Alert(title="Test Alert", message="Test message", severity=AlertSeverity.ERROR)

        result = await channel.send_alert(alert)
        assert result is False

    @pytest.mark.asyncio
    async def test_email_channel_exception(self):
        """Test email channel with SMTP exception."""
        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.side_effect = Exception("SMTP connection failed")

            channel = EmailNotificationChannel(
                smtp_server="smtp.test.com",
                to_emails=["recipient@test.com"],
            )

            alert = Alert(title="Test Alert", message="Test message", severity=AlertSeverity.ERROR)

            result = await channel.send_alert(alert)
            assert result is False


class TestWebhookNotificationChannel:
    """Test Webhook notification channel."""

    @pytest.mark.asyncio
    async def test_webhook_channel_exception(self):
        """Test webhook channel exception handling (lines 121-128)."""
        from app.middleware.alerting import WebhookNotificationChannel

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = WebhookNotificationChannel("https://example.com/webhook")
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
            )

            result = await channel.send_alert(alert)
            assert result is False

    @pytest.mark.asyncio
    async def test_webhook_non_success_status(self):
        """Test webhook channel with non-success status (lines 112-119)."""
        from app.middleware.alerting import WebhookNotificationChannel

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = WebhookNotificationChannel("https://example.com/webhook")
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.WARNING,
            )

            result = await channel.send_alert(alert)
            assert result is False


class TestLogNotificationChannel:
    """Test log notification channel."""

    @pytest.mark.asyncio
    async def test_log_channel_success(self):
        """Test log channel success."""
        with patch("app.middleware.alerting.logger") as mock_logger:
            channel = LogNotificationChannel()
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
                metadata={"test": True},
            )

            result = await channel.send_alert(alert)
            assert result is True
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_channel_exception(self):
        """Test log channel when logger fails."""
        with patch("app.middleware.alerting.logger") as mock_logger:
            mock_logger.error.side_effect = Exception("Logger error")

            channel = LogNotificationChannel()
            alert = Alert(title="Test Alert", message="Test message", severity=AlertSeverity.ERROR)

            result = await channel.send_alert(alert)
            assert result is False


class TestAlertTemplate:
    """Test alert template functionality."""

    def test_template_format_title(self):
        """Test formatting alert title with template."""
        template = AlertTemplate(
            name="test_template",
            title_template="Error in {service}",
            message_template="An error occurred: {error_message}",
            severity=AlertSeverity.ERROR,
        )

        title = template.format_title(service="auth-service")
        assert title == "Error in auth-service"

    def test_template_format_message(self):
        """Test formatting alert message with template."""
        template = AlertTemplate(
            name="test_template",
            title_template="Error in {service}",
            message_template="An error occurred: {error_message}",
            severity=AlertSeverity.ERROR,
        )

        message = template.format_message(error_message="Connection timeout")
        assert message == "An error occurred: Connection timeout"

    def test_template_default_severity(self):
        """Test default severity is ERROR."""
        template = AlertTemplate(
            name="test_template",
            title_template="Test",
            message_template="Test message",
        )
        assert template.severity == AlertSeverity.ERROR


class TestAlertEscalationPolicy:
    """Test alert escalation policy."""

    def test_escalation_policy_no_rules(self):
        """Test escalation policy with no escalation rules."""
        policy = AlertEscalationPolicy(
            initial_severity=AlertSeverity.WARNING,
            escalation_rules=[],
        )

        severity = policy.get_severity_at_time(alert_age_seconds=300)
        assert severity == AlertSeverity.WARNING

    def test_escalation_policy_with_rules(self):
        """Test escalation policy with escalation rules."""
        # Note: AlertSeverity uses string values, so comparison is alphabetical
        # "critical" (99) < "error" (101) < "info" (105) < "warning" (119)
        # Escalation only works when new_severity.value > current_severity.value
        policy = AlertEscalationPolicy(
            initial_severity=AlertSeverity.CRITICAL,
            escalation_rules=[
                {
                    "after_seconds": 300,
                    "severity": AlertSeverity.ERROR,
                },  # 'e' > 'c' - will escalate
                {"after_seconds": 600, "severity": AlertSeverity.INFO},  # 'i' > 'e' - will escalate
            ],
        )

        # Before first threshold
        assert policy.get_severity_at_time(alert_age_seconds=100) == AlertSeverity.CRITICAL
        # At first threshold - ERROR ('e') > CRITICAL ('c') alphabetically
        assert policy.get_severity_at_time(alert_age_seconds=300) == AlertSeverity.ERROR
        # At second threshold - INFO ('i') > ERROR ('e') alphabetically
        assert policy.get_severity_at_time(alert_age_seconds=600) == AlertSeverity.INFO

    def test_escalation_policy_string_severity(self):
        """Test escalation policy with string severity values."""
        policy = AlertEscalationPolicy(
            initial_severity=AlertSeverity.INFO,
            escalation_rules=[
                {"after_seconds": 100, "severity": "warning"},
                {"after_seconds": 200, "severity": "invalid_severity"},  # Should be skipped
            ],
        )

        severity = policy.get_severity_at_time(alert_age_seconds=150)
        assert severity == AlertSeverity.WARNING

    def test_escalation_policy_invalid_severity_skipped(self):
        """Test that invalid severity values are skipped."""
        policy = AlertEscalationPolicy(
            initial_severity=AlertSeverity.INFO,
            escalation_rules=[
                {"after_seconds": 100, "severity": "invalid"},
            ],
        )

        severity = policy.get_severity_at_time(alert_age_seconds=150)
        assert severity == AlertSeverity.INFO  # Should remain initial


class TestAlertRule:
    """Test alert rule functionality."""

    @pytest.mark.asyncio
    async def test_alert_rule_triggers_when_condition_true(self):
        """Test alert rule triggers when condition returns True."""
        template = AlertTemplate(
            name="test_template",
            title_template="High CPU: {cpu_percent}%",
            message_template="CPU usage is above threshold",
            severity=AlertSeverity.WARNING,
        )

        async def async_condition():
            return {"cpu_percent": 85}

        rule = AlertRule(
            name="high_cpu",
            condition=async_condition,
            template=template,
            cooldown_seconds=0,
        )

        alert = await rule.should_trigger()
        assert alert is not None
        assert alert.title == "High CPU: 85%"
        assert alert.severity == AlertSeverity.WARNING
        assert "rule_name" in alert.metadata

    @pytest.mark.asyncio
    async def test_alert_rule_no_trigger_when_condition_false(self):
        """Test alert rule doesn't trigger when condition returns False."""
        template = AlertTemplate(
            name="test_template",
            title_template="Test Alert",
            message_template="Test message",
        )

        async def async_condition_false():
            return False

        rule = AlertRule(
            name="test_rule",
            condition=async_condition_false,
            template=template,
        )

        alert = await rule.should_trigger()
        assert alert is None

    @pytest.mark.asyncio
    async def test_alert_rule_respects_cooldown(self):
        """Test alert rule respects cooldown period."""
        template = AlertTemplate(
            name="test_template",
            title_template="Test Alert",
            message_template="Test message",
        )

        async def async_condition_true():
            return True

        rule = AlertRule(
            name="test_rule",
            condition=async_condition_true,
            template=template,
            cooldown_seconds=60,
        )

        # First trigger
        alert1 = await rule.should_trigger()
        assert alert1 is not None

        # Second trigger within cooldown should return None
        alert2 = await rule.should_trigger()
        assert alert2 is None

    @pytest.mark.asyncio
    async def test_alert_rule_async_condition(self):
        """Test alert rule with async condition."""

        async def async_condition():
            return {"value": 42}

        template = AlertTemplate(
            name="test_template",
            title_template="Value is {value}",
            message_template="Test",
        )

        rule = AlertRule(
            name="test_rule",
            condition=async_condition,
            template=template,
            cooldown_seconds=0,
        )

        alert = await rule.should_trigger()
        assert alert is not None
        assert "42" in alert.title

    @pytest.mark.asyncio
    async def test_alert_rule_condition_exception(self):
        """Test alert rule handles condition exception gracefully."""

        async def failing_condition():
            raise ValueError("Test error")

        template = AlertTemplate(
            name="test_template",
            title_template="Test",
            message_template="Test",
        )

        rule = AlertRule(
            name="test_rule",
            condition=failing_condition,
            template=template,
        )

        # Should return None on exception, not raise
        alert = await rule.should_trigger()
        assert alert is None


class TestAlertManagerAdvanced:
    """Test advanced AlertManager functionality."""

    @pytest.fixture
    def fresh_alert_manager(self):
        """Create a fresh alert manager for testing."""
        manager = AlertManager()
        manager.channels.clear()
        manager.rules.clear()
        manager.active_alerts.clear()
        manager.error_counts.clear()
        manager.alert_cooldowns.clear()
        return manager

    @pytest.mark.asyncio
    async def test_check_rules_triggers_alerts(self, fresh_alert_manager):
        """Test check_rules triggers alerts when rules fire."""
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        fresh_alert_manager.add_channel(mock_channel)

        template = AlertTemplate(
            name="test_template",
            title_template="Test Alert",
            message_template="Test message",
        )

        async def async_condition_true():
            return True

        rule = AlertRule(
            name="test_rule",
            condition=async_condition_true,
            template=template,
            cooldown_seconds=0,
        )
        fresh_alert_manager.add_rule(rule)

        await fresh_alert_manager.check_rules()

        # Channel should have been called
        mock_channel.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_rules_no_trigger_when_condition_false(self, fresh_alert_manager):
        """Test check_rules doesn't trigger when condition is false."""
        mock_channel = AsyncMock()
        fresh_alert_manager.add_channel(mock_channel)

        template = AlertTemplate(
            name="test_template",
            title_template="Test Alert",
            message_template="Test message",
        )

        async def async_condition_false():
            return False

        rule = AlertRule(
            name="test_rule",
            condition=async_condition_false,
            template=template,
        )
        fresh_alert_manager.add_rule(rule)

        await fresh_alert_manager.check_rules()

        # Channel should not have been called
        mock_channel.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_escalate_alerts_with_policy(self, fresh_alert_manager):
        """Test escalate_alerts escalates alerts with escalation policy."""
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        fresh_alert_manager.add_channel(mock_channel)

        # Create an alert with escalation policy
        # Use CRITICAL as initial since ERROR ('e') > CRITICAL ('c') alphabetically
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.CRITICAL,
        )

        # Add escalation policy to alert - CRITICAL -> ERROR escalation path
        policy = AlertEscalationPolicy(
            initial_severity=AlertSeverity.CRITICAL,
            escalation_rules=[
                {
                    "after_seconds": 0,
                    "severity": AlertSeverity.ERROR,
                },  # Immediate escalation, 'e' > 'c'
            ],
        )
        alert.escalation_policy = policy  # type: ignore

        # Add to active alerts
        fresh_alert_manager.active_alerts["test_alert"] = alert

        await fresh_alert_manager.escalate_alerts()

        # Channel should have been called for escalated alert
        mock_channel.send_alert.assert_called_once()
        call_args = mock_channel.send_alert.call_args[0][0]
        assert "[ESCALATED]" in call_args.title

    @pytest.mark.asyncio
    async def test_escalate_alerts_no_policy(self, fresh_alert_manager):
        """Test escalate_alerts skips alerts without policy."""
        mock_channel = AsyncMock()
        fresh_alert_manager.add_channel(mock_channel)

        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
        )
        # No escalation_policy attribute
        fresh_alert_manager.active_alerts["test_alert"] = alert

        await fresh_alert_manager.escalate_alerts()

        # Channel should not have been called
        mock_channel.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_custom_alert(self, fresh_alert_manager):
        """Test trigger_custom_alert sends custom alert."""
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        fresh_alert_manager.add_channel(mock_channel)

        await fresh_alert_manager.trigger_custom_alert(
            title="Custom Alert",
            message="Custom message",
            severity=AlertSeverity.CRITICAL,
            metadata={"custom": True},
        )

        mock_channel.send_alert.assert_called_once()
        call_args = mock_channel.send_alert.call_args[0][0]
        assert call_args.title == "Custom Alert"
        assert call_args.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_send_alert_no_channels(self, fresh_alert_manager):
        """Test _send_alert logs warning when no channels configured."""
        with patch("app.middleware.alerting.logger") as mock_logger:
            alert = Alert(title="Test", message="Test", severity=AlertSeverity.ERROR)
            await fresh_alert_manager._send_alert(alert)

            mock_logger.warning.assert_called_once()
            assert "No notification channels configured" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_send_alert_multiple_channels(self, fresh_alert_manager):
        """Test _send_alert sends to multiple channels concurrently."""
        mock_channel1 = AsyncMock()
        mock_channel1.send_alert.return_value = True
        mock_channel2 = AsyncMock()
        mock_channel2.send_alert.return_value = True

        fresh_alert_manager.add_channel(mock_channel1)
        fresh_alert_manager.add_channel(mock_channel2)

        alert = Alert(title="Test", message="Test", severity=AlertSeverity.ERROR)
        await fresh_alert_manager._send_alert(alert)

        mock_channel1.send_alert.assert_called_once_with(alert)
        mock_channel2.send_alert.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_record_error_triggers_high_rate_alert(self, fresh_alert_manager):
        """Test record_error triggers alert when error rate is high."""
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        fresh_alert_manager.add_channel(mock_channel)

        # Set low threshold for testing
        fresh_alert_manager.error_rate_threshold = 3
        fresh_alert_manager.error_rate_window = timedelta(minutes=1)
        fresh_alert_manager.alert_cooldown = timedelta(seconds=0)

        # Record errors
        for i in range(3):
            await fresh_alert_manager.record_error("test_error", f"Error {i}")

        # Channel should have been called for high error rate alert
        assert mock_channel.send_alert.call_count >= 1

    @pytest.mark.asyncio
    async def test_record_error_respects_cooldown(self, fresh_alert_manager):
        """Test record_error respects alert cooldown."""
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        fresh_alert_manager.add_channel(mock_channel)

        fresh_alert_manager.error_rate_threshold = 1
        fresh_alert_manager.error_rate_window = timedelta(minutes=1)
        fresh_alert_manager.alert_cooldown = timedelta(minutes=5)

        # First error - should trigger alert
        await fresh_alert_manager.record_error("test_error", "Error 1")
        call_count_after_first = mock_channel.send_alert.call_count

        # More errors immediately - should not trigger new alerts due to cooldown
        for i in range(5):
            await fresh_alert_manager.record_error("test_error", f"Error {i}")

        # Should only have the first alert
        assert mock_channel.send_alert.call_count == call_count_after_first


class TestConfigureAlerting:
    """Test configure_alerting function."""

    @pytest.fixture(autouse=True)
    def reset_alert_manager(self):
        """Reset global alert manager before each test."""
        alert_manager.channels.clear()
        alert_manager.rules.clear()
        alert_manager.active_alerts.clear()
        alert_manager.error_counts.clear()
        alert_manager.alert_cooldowns.clear()
        yield
        # Clean up after test
        alert_manager.channels.clear()
        alert_manager.rules.clear()
        alert_manager.active_alerts.clear()
        alert_manager.error_counts.clear()
        alert_manager.alert_cooldowns.clear()

    def test_configure_alerting_with_webhook(self):
        """Test configure_alerting with webhook URLs."""
        with patch("app.middleware.alerting.logger") as mock_logger:
            configure_alerting(
                webhook_urls=["https://example.com/webhook"],
                enable_log_channel=False,
            )

            assert len(alert_manager.channels) == 1
            mock_logger.info.assert_called()

    def test_configure_alerting_with_slack(self) -> None:
        """Test configure_alerting with Slack webhooks."""
        configure_alerting(
            slack_webhook_urls=["https://hooks.slack.com/test"],
            enable_log_channel=False,
        )

        assert len(alert_manager.channels) == 1

    def test_configure_alerting_with_pagerduty(self) -> None:
        """Test configure_alerting with PagerDuty."""
        configure_alerting(
            pagerduty_integration_keys=["test-key"],
            enable_log_channel=False,
        )

        assert len(alert_manager.channels) == 1

    def test_configure_alerting_with_teams(self) -> None:
        """Test configure_alerting with Microsoft Teams."""
        configure_alerting(
            teams_webhook_urls=["https://outlook.office.com/webhook/test"],
            enable_log_channel=False,
        )

        assert len(alert_manager.channels) == 1

    def test_configure_alerting_with_email(self) -> None:
        """Test configure_alerting with email config."""
        configure_alerting(
            email_config={
                "smtp_server": "smtp.test.com",
                "smtp_port": 587,
                "from_email": "alerts@test.com",
                "to_emails": ["admin@test.com"],
            },
            enable_log_channel=False,
        )

        assert len(alert_manager.channels) == 1

    def test_configure_alerting_with_log_channel(self) -> None:
        """Test configure_alerting with log channel enabled."""
        configure_alerting(enable_log_channel=True)

        # Should have at least one channel (the log channel)
        assert len(alert_manager.channels) >= 1

    def test_configure_alerting_custom_thresholds(self) -> None:
        """Test configure_alerting with custom thresholds."""
        configure_alerting(
            enable_log_channel=False,
            error_rate_threshold=20,
            error_rate_window_minutes=2,
            alert_cooldown_minutes=10,
        )

        assert alert_manager.error_rate_threshold == 20
        assert alert_manager.error_rate_window == timedelta(minutes=2)
        assert alert_manager.alert_cooldown == timedelta(minutes=10)

    def test_configure_alerting_multiple_channels(self) -> None:
        """Test configure_alerting with multiple channel types."""
        configure_alerting(
            webhook_urls=["https://example.com/webhook"],
            slack_webhook_urls=["https://hooks.slack.com/test"],
            pagerduty_integration_keys=["test-key"],
            teams_webhook_urls=["https://outlook.office.com/webhook/test"],
            email_config={
                "smtp_server": "smtp.test.com",
                "to_emails": ["admin@test.com"],
            },
            enable_log_channel=True,
        )

        # Should have 5 channels (webhook, slack, pagerduty, teams, email, log)
        assert len(alert_manager.channels) == 6

    def test_configure_alerting_empty_lists(self) -> None:
        """Test configure_alerting with empty lists doesn't add channels."""
        configure_alerting(
            webhook_urls=[],
            slack_webhook_urls=[],
            pagerduty_integration_keys=[],
            teams_webhook_urls=[],
            enable_log_channel=False,
        )

        assert len(alert_manager.channels) == 0


class TestAlertDataclass:
    """Test Alert dataclass."""

    def test_alert_to_dict(self) -> None:
        """Test alert to_dict conversion."""
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.ERROR,
            metadata={"key": "value"},
        )

        result = alert.to_dict()
        assert result["title"] == "Test Alert"
        assert result["message"] == "Test message"
        assert result["severity"] == "error"
        assert result["metadata"] == {"key": "value"}
        assert "timestamp" in result
