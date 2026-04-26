"""
Webhook Celery Tasks

Background tasks for managing webhook deliveries.
"""

import asyncio
import logging

from celery import shared_task

from app.database.connection import SessionLocal
from app.services.webhook_manager import WebhookManager

logger = logging.getLogger(__name__)


async def _process_webhooks() -> int:
    db = SessionLocal()
    try:
        manager = WebhookManager()
        processed = await manager.process_pending_deliveries(db)
        logger.info(f"Processed {processed} pending webhooks")
        return processed
    except Exception as e:
        logger.error(f"Error processing webhooks: {e}")
        raise
    finally:
        db.close()


@shared_task(name="process_pending_webhooks")  # type: ignore[untyped-decorator]
def process_pending_webhooks() -> int:
    """Celery task to process pending webhook deliveries."""
    return asyncio.run(_process_webhooks())
