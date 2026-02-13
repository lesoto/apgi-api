"""
Alerting System

Monitors critical errors and triggers alerts through configured notification channels.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import httpx

from app.middleware.logging import StructuredLogger

logger = StructuredLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """
    Represents an alert to be sent.
    """

    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert alert to dictionary."""
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat() + "Z",
            "metadata": self.metadata,
        }


class NotificationChannel(ABC):
    """
    Abstract base class for notification channels.
    """

    @abstractmethod
    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert through this channel.

        Args:
            alert: Alert to send

        Returns:
            True if alert was sent successfully
        """
        pass


class WebhookNotificationChannel(NotificationChannel):
    """
    Sends alerts via HTTP webhook.
    """

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        """
        Initialize webhook notification channel.

        Args:
            webhook_url: URL to POST alerts to
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert via webhook POST request.

        Args:
            alert: Alert to send

        Returns:
            True if webhook call succeeded
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url, json=alert.to_dict(), timeout=self.timeout
                )

                if response.status_code < 300:
                    logger.info(
                        "Alert sent via webhook",
                        webhook_url=self.webhook_url,
                        alert_title=alert.title,
                        severity=alert.severity.value,
                    )
                    return True
                else:
                    logger.warning(
                        "Webhook returned non-success status",
                        webhook_url=self.webhook_url,
                        status_code=response.status_code,
                        alert_title=alert.title,
                    )
                    return False

        except Exception as e:
            logger.error(
                "Failed to send alert via webhook",
                webhook_url=self.webhook_url,
                alert_title=alert.title,
                error=str(e),
            )
            return False


class LogNotificationChannel(NotificationChannel):
    """
    Sends alerts to log output (useful for development/testing).
    """

    async def send_alert(self, alert: Alert) -> bool:
        """
        Log alert at appropriate level.

        Args:
            alert: Alert to log

        Returns:
            Always True (logging doesn't fail)
        """
        log_data = {
            "alert_title": alert.title,
            "alert_message": alert.message,
            "severity": alert.severity.value,
            **alert.metadata,
        }

        if alert.severity == AlertSeverity.CRITICAL:
            logger.error("CRITICAL ALERT", **log_data)
        elif alert.severity == AlertSeverity.ERROR:
            logger.error("ERROR ALERT", **log_data)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning("WARNING ALERT", **log_data)
        else:
            logger.info("INFO ALERT", **log_data)

        return True


class AlertManager:
    """
    Manages alert triggers and notification channels.

    Monitors error rates and triggers alerts when thresholds are exceeded.
    """

    def __init__(self):
        """Initialize alert manager."""
        self.channels: List[NotificationChannel] = []
        self.error_counts: Dict[str, List[datetime]] = {}
        self.alert_cooldowns: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

        # Alert thresholds
        self.error_rate_threshold = 10  # errors per minute
        self.error_rate_window = timedelta(minutes=1)
        self.alert_cooldown = timedelta(minutes=5)  # Don't spam alerts

    def add_channel(self, channel: NotificationChannel):
        """
        Add a notification channel.

        Args:
            channel: Notification channel to add
        """
        self.channels.append(channel)
        logger.info(
            "Notification channel added",
            channel_type=type(channel).__name__,
            total_channels=len(self.channels),
        )

    async def record_error(
        self, error_type: str, error_message: str, metadata: Optional[Dict] = None
    ):
        """
        Record an error and check if alert should be triggered.

        Args:
            error_type: Type of error
            error_message: Error message
            metadata: Additional error metadata
        """
        async with self._lock:
            now = datetime.utcnow()

            # Initialize error tracking for this type
            if error_type not in self.error_counts:
                self.error_counts[error_type] = []

            # Add error timestamp
            self.error_counts[error_type].append(now)

            # Clean up old errors outside the window
            cutoff = now - self.error_rate_window
            self.error_counts[error_type] = [
                ts for ts in self.error_counts[error_type] if ts > cutoff
            ]

            # Check if we should trigger an alert
            error_count = len(self.error_counts[error_type])

            if error_count >= self.error_rate_threshold:
                await self._trigger_high_error_rate_alert(
                    error_type, error_count, error_message, metadata
                )

    async def _trigger_high_error_rate_alert(
        self, error_type: str, error_count: int, error_message: str, metadata: Optional[Dict]
    ):
        """
        Trigger alert for high error rate.

        Args:
            error_type: Type of error
            error_count: Number of errors in window
            error_message: Recent error message
            metadata: Additional metadata
        """
        # Check cooldown to avoid alert spam
        alert_key = f"high_error_rate_{error_type}"
        now = datetime.utcnow()

        if alert_key in self.alert_cooldowns:
            if now < self.alert_cooldowns[alert_key]:
                # Still in cooldown period
                return

        # Set cooldown
        self.alert_cooldowns[alert_key] = now + self.alert_cooldown

        # Create alert
        alert = Alert(
            title=f"High Error Rate: {error_type}",
            message=f"Detected {error_count} errors of type '{error_type}' in the last minute. Recent error: {error_message}",
            severity=AlertSeverity.CRITICAL,
            metadata={
                "error_type": error_type,
                "error_count": error_count,
                "window_minutes": self.error_rate_window.total_seconds() / 60,
                "recent_error": error_message,
                **(metadata or {}),
            },
        )

        # Send alert through all channels
        await self._send_alert(alert)

    async def trigger_custom_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.ERROR,
        metadata: Optional[Dict] = None,
    ):
        """
        Trigger a custom alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            metadata: Additional metadata
        """
        alert = Alert(title=title, message=message, severity=severity, metadata=metadata or {})

        await self._send_alert(alert)

    async def _send_alert(self, alert: Alert):
        """
        Send alert through all configured channels.

        Args:
            alert: Alert to send
        """
        if not self.channels:
            logger.warning("No notification channels configured", alert_title=alert.title)
            return

        # Send to all channels concurrently
        tasks = [channel.send_alert(alert) for channel in self.channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        success_count = sum(1 for r in results if r is True)
        logger.info(
            "Alert sent to channels",
            alert_title=alert.title,
            severity=alert.severity.value,
            channels_total=len(self.channels),
            channels_success=success_count,
        )


# Global alert manager instance
alert_manager = AlertManager()


def configure_alerting(
    webhook_urls: Optional[List[str]] = None,
    enable_log_channel: bool = True,
    error_rate_threshold: int = 10,
    error_rate_window_minutes: int = 1,
    alert_cooldown_minutes: int = 5,
):
    """
    Configure the alerting system.

    Args:
        webhook_urls: List of webhook URLs to send alerts to
        enable_log_channel: Whether to enable log-based alerts
        error_rate_threshold: Number of errors to trigger alert
        error_rate_window_minutes: Time window for error rate calculation
        alert_cooldown_minutes: Cooldown period between alerts
    """
    # Configure thresholds
    alert_manager.error_rate_threshold = error_rate_threshold
    alert_manager.error_rate_window = timedelta(minutes=error_rate_window_minutes)
    alert_manager.alert_cooldown = timedelta(minutes=alert_cooldown_minutes)

    # Add webhook channels
    if webhook_urls:
        for url in webhook_urls:
            alert_manager.add_channel(WebhookNotificationChannel(url))

    # Add log channel
    if enable_log_channel:
        alert_manager.add_channel(LogNotificationChannel())

    logger.info(
        "Alerting system configured",
        error_rate_threshold=error_rate_threshold,
        error_rate_window_minutes=error_rate_window_minutes,
        alert_cooldown_minutes=alert_cooldown_minutes,
        channels=len(alert_manager.channels),
    )
