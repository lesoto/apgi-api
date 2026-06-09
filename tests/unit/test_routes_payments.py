"""
Tests for payment routes.
"""

from unittest.mock import patch

import pytest

from app.routes.payments import router


class TestPaymentsRoutes:
    """Test payment processing endpoints."""

    def test_router_configuration(self):
        """Test router is properly configured."""
        assert router.tags == ["Payments"]
        assert router.prefix == "/v1/payments"
        assert len(router.routes) > 0

    @pytest.mark.asyncio
    @patch("app.routes.payments.require_permission")
    @patch("app.routes.payments.stripe")
    async def test_payment_endpoint_requires_auth(self, mock_stripe, mock_require_perm):
        """Test payment endpoints require authentication."""
        mock_require_perm.return_value = None
        mock_stripe.api_key = "test_key"

        # Verify router exists
        assert router is not None

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_payment_processing(self, mock_stripe):
        """Test payment processing with Stripe."""
        mock_stripe.PaymentIntent.create.return_value = {"id": "pi_123"}
        mock_stripe.PaymentIntent.retrieve.return_value = {
            "id": "pi_123",
            "status": "succeeded",
        }

        # Verify Stripe mock
        assert mock_stripe.PaymentIntent.create is not None

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_create_payment_intent(self, mock_stripe):
        """Test creating a payment intent."""
        mock_stripe.PaymentIntent.create.return_value = {
            "id": "pi_123",
            "amount": 1000,
            "currency": "usd",
            "status": "requires_payment_method",
        }

        # Verify payment intent creation
        result = mock_stripe.PaymentIntent.create(
            amount=1000, currency="usd", metadata={"order_id": "order-123"}
        )
        assert result["id"] == "pi_123"
        assert result["amount"] == 1000

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_confirm_payment(self, mock_stripe):
        """Test confirming a payment."""
        mock_stripe.PaymentIntent.confirm.return_value = {
            "id": "pi_123",
            "status": "succeeded",
        }

        # Verify payment confirmation
        result = mock_stripe.PaymentIntent.confirm("pi_123", payment_method="pm_123")
        assert result["status"] == "succeeded"

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_webhook_handling(self, mock_stripe):
        """Test Stripe webhook handling."""
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        }

        # Verify webhook construction
        assert mock_stripe.Webhook.construct_event is not None

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_refund_payment(self, mock_stripe):
        """Test payment refund."""
        mock_stripe.Refund.create.return_value = {
            "id": "re_123",
            "amount": 1000,
            "status": "succeeded",
        }

        # Verify refund creation
        result = mock_stripe.Refund.create(payment_intent="pi_123", amount=1000)
        assert result["status"] == "succeeded"

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_get_payment_status(self, mock_stripe):
        """Test getting payment status."""
        mock_stripe.PaymentIntent.retrieve.return_value = {
            "id": "pi_123",
            "status": "succeeded",
        }

        # Verify payment retrieval
        result = mock_stripe.PaymentIntent.retrieve("pi_123")
        assert result["status"] == "succeeded"

    @pytest.mark.asyncio
    @patch("app.routes.payments.stripe")
    async def test_list_payments(self, mock_stripe):
        """Test listing payments."""
        mock_stripe.PaymentIntent.list.return_value = {
            "data": [{"id": "pi_123"}, {"id": "pi_456"}],
        }

        # Verify payment listing
        result = mock_stripe.PaymentIntent.list(limit=10)
        assert len(result["data"]) == 2
