"""
Stripe Payment Routes

API endpoints for creating Stripe PaymentIntents.
"""

import logging
import stripe
from datetime import timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.database.models import Order, Subscription, ProcessedWebhookEvent, User
from app.models.schemas import ErrorResponse
from app.services.authorization import Permission, require_permission

logger = logging.getLogger(__name__)

# Configure Stripe key
stripe.api_key = settings.stripe_secret_key

router = APIRouter(
    prefix="/v1/payments",
    tags=["Payments"],
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# Product catalogue - prices in cents
PRODUCT_CATALOGUE = {
    "cognitive-engine-v2": {
        "name": "Cognitive Engine V2",
        "price_cents": 9900,  # $99.00
        "currency": "usd",
    },
    # Add more products as needed
}


class PaymentIntentCreateRequest(BaseModel):
    items: list[dict]
    currency: str = "usd"


class PaymentIntentCreateResponse(BaseModel):
    clientSecret: str


@router.post(
    "/create-intent",
    response_model=PaymentIntentCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a Stripe PaymentIntent",
    description="Creates a PaymentIntent for the APGI Subscription checkout flow.",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def create_payment_intent(request: PaymentIntentCreateRequest):
    """
    Generate a Stripe PaymentIntent for the frontend.
    """
    try:
        # Calculate amount from product catalogue based on item IDs
        amount: int = 0
        for item in request.items:
            item_id = item.get("id")
            if not item_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each item must have an 'id' field",
                )

            if item_id not in PRODUCT_CATALOGUE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown product: {item_id}"
                )

            amount += int(PRODUCT_CATALOGUE[item_id]["price_cents"])  # type: ignore[call-overload]

        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No valid items provided"
            )

        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=request.currency,
            # In the latest version of the API, specifying the automatic_payment_methods
            # parameter is optional because Stripe enables its functionality by default.
            automatic_payment_methods={
                "enabled": True,
            },
        )
        return PaymentIntentCreateResponse(clientSecret=intent.client_secret)  # type: ignore

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Stripe PaymentIntent creation failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment service temporarily unavailable",
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Handle Stripe webhooks",
    description="Processes Stripe webhook events including refunds, disputes, and subscriptions.",
)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events.

    Validates the Stripe-Signature header and processes various event types.
    """
    try:
        # Get the raw request body
        payload = await request.body()

        # Get the signature from headers
        sig_header = request.headers.get("stripe-signature")
        if not sig_header:
            logger.warning("Stripe webhook received without signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header"
            )

        # Get webhook endpoint secret from config
        endpoint_secret = getattr(settings, "stripe_webhook_secret", None)
        if not endpoint_secret:
            logger.warning("Stripe webhook secret not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook configuration error",
            )

        # Verify the webhook signature
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            logger.warning(f"Invalid Stripe webhook payload: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
        except stripe.SignatureVerificationError as e:
            logger.warning(f"Invalid Stripe webhook signature: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

        # Check for idempotency
        event_id = event["id"]
        existing_event = (
            db.query(ProcessedWebhookEvent)
            .filter(ProcessedWebhookEvent.event_id == event_id)
            .first()
        )
        if existing_event:
            logger.info(f"Stripe event {event_id} already processed, skipping.")
            return {"status": "success", "detail": "already_processed"}

        # Process the event
        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook event: {event_type} ({event_id})")

        # Handle different event types
        success = False
        processing_error = None
        if event_type == "payment_intent.succeeded":
            success = await _handle_payment_succeeded(db, event_data)
        elif event_type == "payment_intent.payment_failed":
            success = await _handle_payment_failed(db, event_data)
        elif event_type == "charge.dispute.created":
            success = await _handle_dispute_created(db, event_data)
        elif event_type == "charge.dispute.closed":
            success = await _handle_dispute_closed(db, event_data)
        elif event_type == "charge.refunded":
            charge = event_data
            refund_amount = sum(
                refund["amount"] for refund in charge.get("refunds", {}).get("data", [])
            )
            success = await _handle_refund(db, charge, refund_amount)
        elif event_type.startswith("customer.subscription."):
            success = await _handle_subscription_event(db, event_type, event_data)
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")
            success = True  # Mark as "processed" even if unhandled to avoid retries

        # Log processing failures with full context for debugging
        if not success:
            logger.error(
                f"Webhook processing failed: event_type={event_type}, event_id={event_id}, "
                f"event_data={event_data}"
            )

        # Record processed event for idempotency if successful
        if success:
            processed_event = ProcessedWebhookEvent(event_id=event_id, event_type=event_type)
            db.add(processed_event)
            db.commit()

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )


async def _handle_payment_succeeded(db: Session, payment_intent: dict) -> bool:
    """Handle successful payment intent."""
    try:
        payment_intent_id = payment_intent.get("id")
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")

        # Security validation: verify user_id exists in database
        if user_id:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            if not existing_user:
                logger.error(
                    f"Payment success handler: Invalid user_id {user_id} for payment {payment_intent_id}"
                )
                return False
        order_id = metadata.get("order_id")
        amount = payment_intent.get("amount", 0)
        currency = payment_intent.get("currency", "usd")

        logger.info(
            f"Processing payment success: {payment_intent_id} for user {user_id}, "
            f"amount: ${amount / 100:.2f} {currency}"
        )

        if order_id:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if order:
                # Security Validation: Verify user_id and amount match
                if user_id and order.user_id != user_id:
                    logger.error(
                        f"CRITICAL: Metadata user_id mismatch for order {order_id}: "
                        f"order owner={order.user_id}, webhook user_id={user_id}, "
                        f"payment_intent={payment_intent_id}"
                    )
                    return False

                if order.amount_cents != amount:
                    logger.error(
                        f"CRITICAL: Payment amount mismatch for order {order_id}: "
                        f"order amount={order.amount_cents}, webhook amount={amount}, "
                        f"payment_intent={payment_intent_id}"
                    )
                    return False

                order.status = "succeeded"  # type: ignore[assignment]
                db.commit()
                logger.info(
                    f"Payment {payment_intent_id} processed successfully - "
                    f"User: {user_id}, Order: {order_id}"
                )
                return True
            else:
                logger.warning(
                    f"Order {order_id} not found for successful payment {payment_intent_id}. "
                    f"Metadata may be stale or order was deleted."
                )
                return False
        return True  # No order_id, nothing to update but still successful receipt

    except Exception as e:
        logger.error(f"Failed to handle payment success: {e}", exc_info=True)
        return False


async def _handle_payment_failed(db: Session, payment_intent: dict) -> bool:
    """Handle failed payment intent."""
    try:
        payment_intent_id = payment_intent.get("id")
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")

        # Security validation: verify user_id exists in database
        if user_id:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            if not existing_user:
                logger.error(
                    f"Payment success handler: Invalid user_id {user_id} for payment {payment_intent_id}"
                )
                return False
        order_id = metadata.get("order_id")
        last_payment_error = payment_intent.get("last_payment_error", {})
        amount = payment_intent.get("amount", 0)

        error_message = last_payment_error.get("message", "Unknown error")
        error_type = last_payment_error.get("type", "unknown")

        logger.warning(
            f"Processing payment failure: {payment_intent_id} for user {user_id}, "
            f"error: {error_type} - {error_message}"
        )

        # Log payment failure for analytics and manual follow-up
        if order_id:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if order:
                order.status = "failed"  # type: ignore[assignment]
                db.commit()

        logger.warning(
            f"Payment {payment_intent_id} failed - User: {user_id}, "
            f"Order: {order_id}, Amount: ${amount / 100:.2f}, Error: {error_message}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to handle payment failure: {e}", exc_info=True)
        return False


async def _handle_dispute_created(db: Session, dispute: dict) -> bool:
    """Handle charge dispute creation."""
    try:
        dispute_id = dispute.get("id")
        charge_id = dispute.get("charge")
        amount = dispute.get("amount", 0)
        currency = dispute.get("currency", "usd")
        reason = dispute.get("reason", "unknown")

        logger.warning(
            f"Processing dispute creation: {dispute_id} for charge {charge_id}, "
            f"amount: ${amount / 100:.2f} {currency}, reason: {reason}"
        )

        # Log dispute for admin follow-up
        logger.warning(
            f"Dispute {dispute_id} created - Charge: {charge_id}, "
            f"Amount: ${amount / 100:.2f} {currency}, Reason: {reason}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to handle dispute creation: {e}", exc_info=True)
        return False


async def _handle_dispute_closed(db: Session, dispute: dict) -> bool:
    """Handle charge dispute resolution."""
    try:
        dispute_id = dispute.get("id")
        status = dispute.get("status")
        charge_id = dispute.get("charge")

        logger.info(
            f"Processing dispute closure: {dispute_id} with status {status}, "
            f"charge: {charge_id}"
        )

        # Log dispute resolution for record keeping
        logger.info(f"Dispute {dispute_id} closed - Status: {status}, Charge: {charge_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to handle dispute closure: {e}", exc_info=True)
        return False


async def _handle_refund(db: Session, charge: dict, refund_amount: int) -> bool:
    """Handle charge refund."""
    try:
        charge_id = charge.get("id")
        metadata = charge.get("metadata", {})
        user_id = metadata.get("user_id")

        # Security validation: verify user_id exists in database
        if user_id:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            if not existing_user:
                logger.error(
                    f"Payment success handler: Invalid user_id {user_id} for payment {charge_id}"
                )
                return False
        order_id = metadata.get("order_id")
        currency = charge.get("currency", "usd")

        logger.info(
            f"Processing refund: {charge_id} for ${refund_amount / 100:.2f} {currency}, "
            f"user: {user_id}"
        )

        if order_id:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if order:
                order.status = "refunded"  # type: ignore[assignment]
                db.commit()

        # Log refund for accounting and record keeping
        logger.info(
            f"Refund processed - Charge: {charge_id}, Amount: ${refund_amount / 100:.2f} {currency}, "
            f"User: {user_id}, Order: {order_id}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to handle refund: {e}", exc_info=True)
        return False


async def _handle_subscription_event(db: Session, event_type: str, subscription: dict) -> bool:
    """Handle subscription lifecycle events."""
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        metadata = subscription.get("metadata", {})
        user_id = metadata.get("user_id")

        # Security validation: verify user_id exists in database
        if user_id:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            if not existing_user:
                logger.error(
                    f"Payment success handler: Invalid user_id {user_id} for payment {subscription_id}"
                )
                return False

        logger.info(
            f"Processing subscription event: {event_type} for {subscription_id}, "
            f"status: {status}"
        )

        # Handle specific subscription events
        if event_type == "customer.subscription.created":
            logger.info(
                f"Subscription created: {subscription_id}, Customer: {customer_id}, User: {user_id}"
            )
            # Find existing subscription or create a new one
            sub = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )
            if not sub and user_id:
                from datetime import datetime
                import time

                sub = Subscription(
                    user_id=user_id,
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    plan_id=subscription.get("plan", {}).get("id", "unknown"),
                    status=status,
                    current_period_start=datetime.fromtimestamp(
                        subscription.get("current_period_start", time.time()), timezone.utc
                    ),
                    current_period_end=datetime.fromtimestamp(
                        subscription.get("current_period_end", time.time()), timezone.utc
                    ),
                    cancel_at_period_end=subscription.get("cancel_at_period_end", False),
                )
                db.add(sub)
                db.commit()

        elif event_type in [
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "customer.subscription.paused",
            "customer.subscription.resumed",
        ]:
            logger.info(f"Subscription event: {subscription_id}, Status: {status}")
            sub = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )
            if sub:
                from datetime import datetime
                import time

                sub.status = status  # type: ignore[assignment]
                sub.plan_id = subscription.get("plan", {}).get("id", sub.plan_id)
                sub.current_period_start = datetime.fromtimestamp(  # type: ignore[assignment]
                    subscription.get("current_period_start", time.time()), timezone.utc
                )
                sub.current_period_end = datetime.fromtimestamp(  # type: ignore[assignment]
                    subscription.get("current_period_end", time.time()), timezone.utc
                )
                sub.cancel_at_period_end = subscription.get("cancel_at_period_end", False)
                db.commit()

        elif event_type in ["customer.subscription.payment_failed", "invoice.payment_failed"]:
            logger.warning(f"Subscription payment failed: {subscription_id}, User: {user_id}")
            sub = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )
            if sub:
                sub.status = "past_due"  # type: ignore[assignment]
                db.commit()

        logger.info(f"Subscription event {event_type} processed for {subscription_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to handle subscription event: {e}", exc_info=True)
        return False
