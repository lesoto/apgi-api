"""
Webhook Manager Service

Handles webhook delivery and management for task completions.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import uuid
import socket
import ipaddress
import json
import hmac
import hashlib

import aiohttp

from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import WebhookDelivery
from app.middleware.alerting import alert_manager, AlertSeverity

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manager for webhook deliveries."""

    MAX_RESPONSE_SIZE = 1024 * 1024  # 1MB limit for response bodies

    # Private IP ranges to block
    PRIVATE_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
        ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
        ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    @staticmethod
    def _validate_webhook_url(url: str) -> None:
        """
        Validate webhook URL to prevent SSRF attacks.

        Args:
            url: Webhook URL to validate

        Raises:
            ValueError: If URL is invalid or points to private/internal network
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Only HTTP and HTTPS URLs are allowed")

            hostname = parsed.hostname
            if not hostname:
                raise ValueError("Invalid URL: no hostname")

            # Block cloud metadata endpoints
            blocked_hostnames = [
                "metadata.google.internal",
                "169.254.169.254",
                "metadata",
                "ec2metadata",
                "instance-data",
                "linklocal.amazonaws.com",
            ]

            if hostname.lower() in blocked_hostnames:
                raise ValueError(f"Access to cloud metadata endpoint {hostname} is blocked")

            # Resolve hostname to IP addresses
            try:
                addrinfo = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
                ip_addresses = [info[4][0] for info in addrinfo]
            except socket.gaierror as e:
                raise ValueError(f"Could not resolve hostname {hostname}: {e}")

            # Check each IP address against private networks and metadata IPs
            for ip_str in ip_addresses:
                try:
                    ip = ipaddress.ip_address(ip_str)

                    # Block cloud metadata IP ranges
                    if ip_str in ["169.254.169.254", "169.254.169.253", "169.254.169.252"]:
                        raise ValueError(f"Access to cloud metadata IP {ip_str} is blocked")

                    for private_net in WebhookManager.PRIVATE_NETWORKS:
                        if ip in private_net:
                            raise ValueError(f"URL points to private/internal IP address: {ip_str}")
                except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                    # Invalid IP format, skip
                    continue

        except Exception as e:
            raise ValueError(f"Invalid webhook URL: {e}")

    def __init__(self):
        """Initialize webhook manager."""
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the webhook manager."""
        if self.session:
            await self.session.close()
            self.session = None

    async def create_webhook_delivery(
        self, db: Session, task_id: str, webhook_url: str, payload: Dict[str, Any]
    ) -> str:
        """
        Create a webhook delivery record.

        Args:
            db: Database session
            task_id: Associated task ID
            webhook_url: Target webhook URL
            payload: Webhook payload data

        Returns:
            Delivery ID

        Raises:
            ValueError: If webhook URL is invalid or insecure
        """
        # Validate webhook URL to prevent SSRF
        self._validate_webhook_url(webhook_url)

        delivery_id = str(uuid.uuid4())

        # Calculate retry schedule (exponential backoff)
        now = datetime.now(timezone.utc)
        retry_delays = [5, 30, 300, 1800, 3600]  # 5s, 30s, 5min, 30min, 1h

        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            task_id=task_id,
            webhook_url=webhook_url,
            payload=payload,
            status="pending",
            attempts=0,
            next_retry_at=now + timedelta(seconds=retry_delays[0]),
        )

        try:
            db.add(delivery)
            db.commit()
            db.refresh(delivery)
            return delivery_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create webhook delivery for task {task_id}: {e}")
            raise

    async def deliver_webhook(self, db: Session, delivery_id: str) -> bool:
        """
        Attempt to deliver a webhook.

        Args:
            db: Database session
            delivery_id: Delivery ID

        Returns:
            True if delivery successful, False otherwise
        """
        # Get delivery record
        delivery = (
            db.query(WebhookDelivery).filter(WebhookDelivery.delivery_id == delivery_id).first()
        )

        if not delivery:
            logger.warning(f"Webhook delivery {delivery_id} not found")
            return False

        # Skip if already delivered
        if delivery.status == "delivered":
            return True

        # Check retry attempts
        retry_count = delivery.retry_count
        if delivery.attempts >= retry_count:
            delivery.status = "dead_letter"  # type: ignore[assignment]
            delivery.error_message = "Maximum retry attempts exceeded, moved to dead-letter queue"  # type: ignore[assignment]
            db.commit()
            # Alert about dead-letter webhook
            await alert_manager.trigger_custom_alert(
                title="Webhook Dead-Letter",
                message=f"Webhook delivery {delivery_id} for task {delivery.task_id} moved to dead-letter queue after {delivery.attempts} attempts",
                severity=AlertSeverity.WARNING,
                metadata={
                    "delivery_id": delivery_id,
                    "task_id": delivery.task_id,
                    "webhook_url": delivery.webhook_url,
                    "attempts": delivery.attempts,
                    "error_message": delivery.error_message,
                },
            )
            return False

        try:
            # Prepare headers with HMAC signature
            headers = {"Content-Type": "application/json"}
            if settings.webhook_secret_key:
                payload_str = json.dumps(delivery.payload, sort_keys=True, separators=(",", ":"))
                signature = hmac.new(
                    settings.webhook_secret_key.encode(), payload_str.encode(), hashlib.sha256
                ).hexdigest()
                headers["X-Signature-256"] = f"sha256={signature}"
            else:
                logger.warning("WEBHOOK_SECRET_KEY not configured, webhook sent without signature")

            # Attempt delivery
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    delivery.webhook_url,  # type: ignore[arg-type]
                    json=delivery.payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    delivery.attempts += 1  # type: ignore[assignment]
                    delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]

                    if response.status >= 200 and response.status < 300:
                        delivery.status = "delivered"  # type: ignore[assignment]
                        delivery.response_status = response.status  # type: ignore[assignment]
                        text = await response.text()
                        if len(text) > self.MAX_RESPONSE_SIZE:
                            text = text[: self.MAX_RESPONSE_SIZE] + "... (truncated)"
                        delivery.response_body = text  # type: ignore[assignment]
                        logger.info(f"Webhook delivery {delivery_id} successful")
                        db.commit()
                        return True
                    else:
                        # Schedule next retry
                        retry_delays = delivery.retry_delays
                        if delivery.attempts < len(retry_delays):  # type: ignore[arg-type]
                            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                                seconds=retry_delays[delivery.attempts]  # type: ignore[arg-type]
                            )
                        else:
                            delivery.status = "dead_letter"  # type: ignore[assignment]
                            delivery.error_message = f"HTTP {response.status}"  # type: ignore[assignment]

                        delivery.response_status = response.status  # type: ignore[assignment]
                        text = await response.text()
                        if len(text) > self.MAX_RESPONSE_SIZE:
                            text = text[: self.MAX_RESPONSE_SIZE] + "... (truncated)"
                        delivery.response_body = text  # type: ignore[assignment]
                        db.commit()
                        return False

        except asyncio.TimeoutError:
            delivery.attempts += 1  # type: ignore[assignment]
            delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            delivery.error_message = "Timeout"  # type: ignore[assignment]
            # Schedule next retry
            retry_delays = delivery.retry_delays
            if delivery.attempts < len(retry_delays):  # type: ignore[arg-type]
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                    seconds=retry_delays[delivery.attempts]  # type: ignore[arg-type]
                )
            else:
                delivery.status = "dead_letter"  # type: ignore[assignment]
            db.commit()
            return False

        except Exception as e:
            delivery.attempts += 1  # type: ignore[assignment]
            delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            delivery.error_message = str(e)  # type: ignore[assignment]
            # Schedule next retry
            retry_delays = delivery.retry_delays
            if delivery.attempts < len(retry_delays):  # type: ignore[arg-type]
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                    seconds=retry_delays[delivery.attempts]  # type: ignore[arg-type]
                )
            else:
                delivery.status = "dead_letter"  # type: ignore[assignment]
            db.commit()
            return False

    async def process_pending_deliveries(self, db: Session) -> int:
        """
        Process all pending webhook deliveries that are due for retry.

        Args:
            db: Database session

        Returns:
            Number of deliveries processed
        """
        now = datetime.now(timezone.utc)
        pending_deliveries = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.status.in_(["pending", "retry"]),
                WebhookDelivery.next_retry_at <= now,
                WebhookDelivery.attempts < 5,
            )
            .all()
        )

        processed = 0
        for delivery in pending_deliveries:
            await self.deliver_webhook(db, delivery.delivery_id)  # type: ignore[arg-type]
            processed += 1

        return processed
