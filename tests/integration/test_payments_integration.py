"""
Integration tests for payments routes.
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from fastapi import HTTPException, status
from datetime import datetime, timezone


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.execute = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = Mock()
    user.user_id = "user123"
    user.email = "test@example.com"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_order():
    """Mock order."""
    order = MagicMock()
    order.order_id = "order123"
    order.user_id = "user123"
    order.status = "pending"
    order.amount_cents = 9900
    order.currency = "usd"
    order.items = [{"product_id": "cognitive-engine-v2", "quantity": 1}]
    order.created_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)
    return order


@pytest.fixture
def mock_subscription():
    """Mock subscription."""
    subscription = MagicMock()
    subscription.subscription_id = "sub123"
    subscription.user_id = "user123"
    subscription.status = "active"
    subscription.product_id = "cognitive-engine-v2"
    subscription.amount_cents = 9900
    subscription.currency = "usd"
    subscription.created_at = datetime.now(timezone.utc)
    subscription.updated_at = datetime.now(timezone.utc)
    return subscription


class TestPaymentsIntegration:
    """Test payment integration endpoints."""

    @patch("app.routes.payments.stripe")
    async def test_create_payment_intent_success(
        self,
        mock_stripe,
    ):
        """Test successful payment intent creation."""
        # Mock Stripe response
        mock_payment_intent = MagicMock()
        mock_payment_intent.client_secret = "secret123"
        mock_payment_intent.amount = 9900
        mock_payment_intent.currency = "usd"
        mock_stripe.PaymentIntent.create.return_value = mock_payment_intent

        from app.routes.payments import (
            create_payment_intent,
            PaymentIntentCreateRequest,
        )

        request_data = PaymentIntentCreateRequest(
            items=[{"id": "cognitive-engine-v2"}],
            currency="usd",
        )

        result = await create_payment_intent(request_data)

        assert result.clientSecret == "secret123"
        mock_stripe.PaymentIntent.create.assert_called_once()

    @patch("app.routes.payments.stripe")
    async def test_create_payment_intent_invalid_product(
        self,
        mock_stripe,
    ):
        """Test payment intent creation with invalid product."""
        from app.routes.payments import (
            create_payment_intent,
            PaymentIntentCreateRequest,
        )

        request_data = PaymentIntentCreateRequest(
            items=[{"id": "invalid-product"}],
            currency="usd",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_payment_intent(request_data)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown product" in str(exc_info.value.detail)

    @patch("app.routes.payments.stripe")
    async def test_create_payment_intent_stripe_error(
        self,
        mock_stripe,
    ):
        """Test payment intent creation with Stripe error."""
        mock_stripe.PaymentIntent.create.side_effect = Exception("Stripe API error")

        from app.routes.payments import (
            create_payment_intent,
            PaymentIntentCreateRequest,
        )

        request_data = PaymentIntentCreateRequest(
            items=[{"id": "cognitive-engine-v2"}],
            currency="usd",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_payment_intent(request_data)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("app.routes.payments.stripe")
    @patch("app.routes.payments.get_db")
    @patch("app.config.settings")
    async def test_webhook_payment_success(
        self,
        mock_settings,
        mock_get_db,
        mock_stripe,
        mock_db,
        mock_order,
    ):
        """Test successful payment webhook handling."""
        mock_settings.stripe_webhook_secret = "test_secret"
        mock_get_db.return_value = mock_db

        # Mock Stripe event
        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
        mock_event["type"] = "payment_intent.succeeded"
        mock_event["data"] = {
            "object": {
                "id": "pi_123",
                "amount": 9900,
                "currency": "usd",
                "metadata": {"order_id": "order123"},
            }
        }

        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_order

        from app.routes.payments import stripe_webhook
        from fastapi import Request

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"stripe-signature": "test_signature"}
        mock_request.body = AsyncMock(return_value=b'{"data": {"object": {"id": "pi_123"}}}')

        with patch("app.routes.payments.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = mock_event
            result = await stripe_webhook(mock_request, mock_db)

        assert result["status"] == "success"

    @patch("app.routes.payments.stripe")
    @patch("app.routes.payments.get_db")
    @patch("app.config.settings")
    async def test_webhook_payment_failed(
        self,
        mock_settings,
        mock_get_db,
        mock_stripe,
        mock_db,
        mock_order,
    ):
        """Test failed payment webhook handling."""
        mock_settings.stripe_webhook_secret = "test_secret"
        mock_get_db.return_value = mock_db

        # Mock Stripe event
        mock_event = MagicMock()
        mock_event.type = "payment_intent.payment_failed"
        mock_event["type"] = "payment_intent.payment_failed"
        mock_event["data"] = {"object": {"id": "pi_123", "metadata": {"order_id": "order123"}}}

        # Mock database query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_order

        from app.routes.payments import stripe_webhook
        from fastapi import Request

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"stripe-signature": "test_signature"}
        mock_request.body = AsyncMock(return_value=b'{"data": {"object": {"id": "pi_123"}}}')

        with patch("app.routes.payments.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = mock_event
            result = await stripe_webhook(mock_request, mock_db)

        assert result["status"] == "success"

    @patch("app.routes.payments.stripe")
    @patch("app.routes.payments.get_db")
    @patch("app.config.settings")
    async def test_webhook_invalid_signature(
        self,
        mock_settings,
        mock_get_db,
        mock_stripe,
    ):
        """Test webhook with invalid signature."""
        mock_settings.stripe_webhook_secret = "test_secret"
        mock_stripe.Webhook.construct_event.side_effect = ValueError("Invalid signature")

        from app.routes.payments import stripe_webhook
        from fastapi import Request

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"stripe-signature": "invalid_signature"}

        # Make body property return bytes directly
        mock_request.body = b'{"data": {"object": {"id": "pi_123"}}}'

        with pytest.raises(HTTPException) as exc_info:
            await stripe_webhook(mock_request, mock_get_db.return_value)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
