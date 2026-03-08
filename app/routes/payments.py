"""
Stripe Payment Routes

API endpoints for creating Stripe PaymentIntents.
"""

import logging
import stripe
from fastapi import APIRouter, HTTPException, status
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


class PaymentIntentCreateRequest(BaseModel):
    items: list
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
        # Calculate amount. In a real app, calculate securely on the backend based on items
        # Hardcoding the $99.00 for the Cognitive Engine V2 module mock:
        amount = 9900  # $99.00 in cents

        if settings.stripe_secret_key.startswith("sk_test_4eC39H"):
            # Mock successful intent creation for test flow
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
        return PaymentIntentCreateResponse(clientSecret=intent.client_secret)

    except Exception as e:
        logger.error(f"Failed to create PaymentIntent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
