"""
Webhook Manager Service

Handles webhook delivery and management for task completions.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import uuid

import aiohttp

from sqlalchemy.orm import Session

from app.database.models import WebhookDelivery

logger = logging.getLogger(__name__)


class WebhookManager:
    """Manager for webhook deliveries."""

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
        """
        delivery_id = str(uuid.uuid4())

        # Calculate retry schedule (exponential backoff)
        now = datetime.now(timezone.utc)
        retry_delays = [5, 30, 300, 1800, 3600]  # 5min, 30min, 5h, 30min, 1h

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
        if delivery.attempts >= 5:
            delivery.status = "failed"  # type: ignore[assignment]
            delivery.error_message = "Maximum retry attempts exceeded"  # type: ignore[assignment]
            db.commit()
            return False

        try:
            # Attempt delivery
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    delivery.webhook_url,  # type: ignore[arg-type]
                    json=delivery.payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    delivery.attempts += 1  # type: ignore[assignment]
                    delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]

                    if response.status >= 200 and response.status < 300:
                        delivery.status = "delivered"  # type: ignore[assignment]
                        delivery.response_status = response.status  # type: ignore[assignment]
                        delivery.response_body = await response.text()  # type: ignore[assignment]
                        logger.info(f"Webhook delivery {delivery_id} successful")
                        db.commit()
                        return True
                    else:
                        # Schedule next retry
                        retry_delays = [5, 30, 300, 1800, 3600]
                        if delivery.attempts < len(retry_delays):
                            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                                seconds=retry_delays[delivery.attempts]
                            )
                        else:
                            delivery.status = "failed"  # type: ignore[assignment]
                            delivery.error_message = f"HTTP {response.status}"  # type: ignore[assignment]

                        delivery.response_status = response.status  # type: ignore[assignment]
                        delivery.response_body = await response.text()  # type: ignore[assignment]
                        db.commit()
                        return False

        except asyncio.TimeoutError:
            delivery.attempts += 1  # type: ignore[assignment]
            delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            delivery.error_message = "Timeout"  # type: ignore[assignment]
            # Schedule next retry
            retry_delays = [5, 30, 300, 1800, 3600]
            if delivery.attempts < len(retry_delays):
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                    seconds=retry_delays[delivery.attempts]
                )
            else:
                delivery.status = "failed"  # type: ignore[assignment]
            db.commit()
            return False

        except Exception as e:
            delivery.attempts += 1  # type: ignore[assignment]
            delivery.last_attempt_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            delivery.error_message = str(e)  # type: ignore[assignment]
            # Schedule next retry
            retry_delays = [5, 30, 300, 1800, 3600]
            if delivery.attempts < len(retry_delays):
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(  # type: ignore[assignment]
                    seconds=retry_delays[delivery.attempts]
                )
            else:
                delivery.status = "failed"  # type: ignore[assignment]
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
