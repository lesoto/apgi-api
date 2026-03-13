"""
Stripe Payment Routes

API endpoints for creating Stripe PaymentIntents.
"""

import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from app.config import settings
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
    dependencies=[Depends(require_permission(Permission.SYSTEM_ADMIN))],
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

            amount += int(PRODUCT_CATALOGUE[item_id]["price_cents"])

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
async def stripe_webhook(request: Request):
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
        # In production, this should be configured per webhook endpoint
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
            # Invalid payload
            logger.warning(f"Invalid Stripe webhook payload: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
        except stripe.SignatureVerificationError as e:
            # Invalid signature
            logger.warning(f"Invalid Stripe webhook signature: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

        # Process the event
        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook event: {event_type}")

        # Handle different event types
        if event_type == "payment_intent.succeeded":
            # Payment succeeded - update order status and send confirmation
            payment_intent = event_data
            logger.info(f"Payment succeeded: {payment_intent['id']}")
            await _handle_payment_succeeded(payment_intent)

        elif event_type == "payment_intent.payment_failed":
            # Payment failed - notify user and update order
            payment_intent = event_data
            logger.warning(f"Payment failed: {payment_intent['id']}")
            await _handle_payment_failed(payment_intent)

        elif event_type == "charge.dispute.created":
            # Dispute created - notify admin and mark order
            dispute = event_data
            logger.warning(f"Dispute created: {dispute['id']} for charge {dispute['charge']}")
            await _handle_dispute_created(dispute)

        elif event_type == "charge.dispute.closed":
            # Dispute resolved - update based on outcome
            dispute = event_data
            logger.info(f"Dispute closed: {dispute['id']}, status: {dispute['status']}")
            await _handle_dispute_closed(dispute)

        elif event_type == "charge.refunded":
            # Refund processed - update order and notify
            charge = event_data
            refund_amount = sum(
                refund["amount"] for refund in charge.get("refunds", {}).get("data", [])
            )
            logger.info(f"Refund processed: charge {charge['id']}, amount: {refund_amount}")
            await _handle_refund(charge, refund_amount)

        elif event_type.startswith("customer.subscription."):
            # Subscription events - handle lifecycle
            subscription = event_data
            logger.info(f"Subscription event {event_type}: {subscription['id']}")
            await _handle_subscription_event(event_type, subscription)

        else:
            # Unhandled event type
            logger.info(f"Unhandled Stripe event type: {event_type}")

        # Return success response
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )


async def _handle_payment_succeeded(payment_intent: dict) -> None:
    """Handle successful payment intent."""
    try:
        payment_intent_id = payment_intent.get("id")
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        order_id = metadata.get("order_id")

        logger.info(f"Processing payment success: {payment_intent_id} for user {user_id}")

        # TODO: Update order status to 'paid' in database
        # TODO: Send confirmation email to user
        # TODO: Trigger order fulfillment process
        # TODO: Update user subscription status if applicable

        logger.info(f"Payment {payment_intent_id} processed successfully")

    except Exception as e:
        logger.error(f"Failed to handle payment success: {e}", exc_info=True)
        # Don't raise - webhook should acknowledge receipt


async def _handle_payment_failed(payment_intent: dict) -> None:
    """Handle failed payment intent."""
    try:
        payment_intent_id = payment_intent.get("id")
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        order_id = metadata.get("order_id")
        last_payment_error = payment_intent.get("last_payment_error", {})

        logger.warning(f"Processing payment failure: {payment_intent_id} for user {user_id}")

        # TODO: Update order status to 'payment_failed'
        # TODO: Send failure notification to user with reason
        # TODO: Log payment failure reason for analytics

        error_message = last_payment_error.get("message", "Unknown error")
        logger.warning(f"Payment {payment_intent_id} failed: {error_message}")

    except Exception as e:
        logger.error(f"Failed to handle payment failure: {e}", exc_info=True)


async def _handle_dispute_created(dispute: dict) -> None:
    """Handle charge dispute creation."""
    try:
        dispute_id = dispute.get("id")
        charge_id = dispute.get("charge")
        amount = dispute.get("amount", 0)
        currency = dispute.get("currency", "usd")

        logger.warning(f"Processing dispute creation: {dispute_id} for charge {charge_id}")

        # TODO: Mark order as 'disputed' in database
        # TODO: Send alert to admin team
        # TODO: Create dispute record for tracking
        # TODO: Notify user about dispute

        logger.warning(f"Dispute {dispute_id} created for ${amount / 100:.2f} {currency}")

    except Exception as e:
        logger.error(f"Failed to handle dispute creation: {e}", exc_info=True)


async def _handle_dispute_closed(dispute: dict) -> None:
    """Handle charge dispute resolution."""
    try:
        dispute_id = dispute.get("id")
        status = dispute.get("status")
        charge_id = dispute.get("charge")

        logger.info(f"Processing dispute closure: {dispute_id} with status {status}")

        # TODO: Update order status based on dispute outcome
        # TODO: If won (status='won'), restore order to normal state
        # TODO: If lost (status='lost'), mark order as 'dispute_lost'
        # TODO: Send notification to admin and user

        logger.info(f"Dispute {dispute_id} closed with status: {status}")

    except Exception as e:
        logger.error(f"Failed to handle dispute closure: {e}", exc_info=True)


async def _handle_refund(charge: dict, refund_amount: int) -> None:
    """Handle charge refund."""
    try:
        charge_id = charge.get("id")
        metadata = charge.get("metadata", {})
        user_id = metadata.get("user_id")
        order_id = metadata.get("order_id")

        logger.info(f"Processing refund: {charge_id} for ${refund_amount / 100:.2f}")

        # TODO: Update order status to 'refunded'
        # TODO: Send refund confirmation to user
        # TODO: Log refund for accounting
        # TODO: Update subscription status if applicable

        logger.info(f"Refund processed for charge {charge_id}")

    except Exception as e:
        logger.error(f"Failed to handle refund: {e}", exc_info=True)


async def _handle_subscription_event(event_type: str, subscription: dict) -> None:
    """Handle subscription lifecycle events."""
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")

        logger.info(f"Processing subscription event: {event_type} for {subscription_id}")

        # Handle specific subscription events
        if event_type == "customer.subscription.created":
            logger.info(f"Subscription created: {subscription_id}")
            # TODO: Create subscription record in database
            # TODO: Link subscription to user account
            # TODO: Send welcome email

        elif event_type == "customer.subscription.updated":
            logger.info(f"Subscription updated: {subscription_id}")
            # TODO: Update subscription details in database
            # TODO: Handle plan changes

        elif event_type == "customer.subscription.deleted":
            logger.info(f"Subscription cancelled: {subscription_id}")
            # TODO: Mark subscription as cancelled
            # TODO: Send cancellation confirmation
            # TODO: Revoke access if applicable

        elif event_type == "customer.subscription.paused":
            logger.info(f"Subscription paused: {subscription_id}")
            # TODO: Pause subscription benefits

        elif event_type == "customer.subscription.resumed":
            logger.info(f"Subscription resumed: {subscription_id}")
            # TODO: Resume subscription benefits

        elif event_type in ["customer.subscription.payment_failed", "invoice.payment_failed"]:
            logger.warning(f"Subscription payment failed: {subscription_id}")
            # TODO: Handle payment failure (retry logic, dunning)
            # TODO: Notify user of payment issue
            # TODO: Update subscription status

        logger.info(f"Subscription event {event_type} processed for {subscription_id}")

    except Exception as e:
        logger.error(f"Failed to handle subscription event: {e}", exc_info=True)
