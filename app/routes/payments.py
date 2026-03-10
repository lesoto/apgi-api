"""
Stripe Payment Routes

API endpoints for creating Stripe PaymentIntents.
"""

import logging
import stripe
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel

from app.config import settings
from app.models.schemas import ErrorResponse

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
)
async def create_payment_intent(request: PaymentIntentCreateRequest):
    """
    Generate a Stripe PaymentIntent for the frontend.
    """
    try:
        # Calculate amount from product catalogue based on item IDs
        amount = 0
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

            amount += PRODUCT_CATALOGUE[item_id]["price_cents"]

        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No valid items provided"
            )

        if settings.environment != "production":
            # Mock successful intent creation for non-production environments
            return PaymentIntentCreateResponse(
                clientSecret="pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_a1b2c3d4e5f6g7h8i9j0"
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
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            logger.warning(f"Invalid Stripe webhook signature: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

        # Process the event
        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook event: {event_type}")

        # Handle different event types
        if event_type == "payment_intent.succeeded":
            # Payment succeeded
            payment_intent = event_data
            logger.info(f"Payment succeeded: {payment_intent['id']}")
            # TODO: Update order status, send confirmation email, etc.

        elif event_type == "payment_intent.payment_failed":
            # Payment failed
            payment_intent = event_data
            logger.warning(f"Payment failed: {payment_intent['id']}")
            # TODO: Handle failed payment, notify user, etc.

        elif event_type == "charge.dispute.created":
            # Dispute created
            dispute = event_data
            logger.warning(f"Dispute created: {dispute['id']} for charge {dispute['charge']}")
            # TODO: Handle dispute, notify admin, etc.

        elif event_type == "charge.dispute.closed":
            # Dispute resolved
            dispute = event_data
            logger.info(f"Dispute closed: {dispute['id']}, status: {dispute['status']}")
            # TODO: Handle dispute resolution

        elif event_type == "charge.refunded":
            # Refund processed
            charge = event_data
            refund_amount = sum(
                refund["amount"] for refund in charge.get("refunds", {}).get("data", [])
            )
            logger.info(f"Refund processed: charge {charge['id']}, amount: {refund_amount}")
            # TODO: Handle refund, update order status, etc.

        elif event_type.startswith("customer.subscription."):
            # Subscription events
            subscription = event_data
            logger.info(f"Subscription event {event_type}: {subscription['id']}")
            # TODO: Handle subscription lifecycle events

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
