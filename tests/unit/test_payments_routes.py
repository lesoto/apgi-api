"""
Unit tests for payment routes.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.routes.payments import (
    create_payment_intent,
    stripe_webhook,
    _handle_payment_succeeded,
    _handle_payment_failed,
    _handle_dispute_created,
    _handle_dispute_closed,
    _handle_refund,
    _handle_subscription_event,
    PaymentIntentCreateRequest,
)


class TestPaymentRoutes:
    """Test payment route handlers."""

    @pytest.fixture
    def mock_stripe(self):
        """Mock Stripe client."""
        with patch("app.routes.payments.stripe") as mock:
            mock.PaymentIntent.create.return_value = Mock(client_secret="test_secret")
            mock.Webhook.construct_event.return_value = {
                "type": "test_event",
                "data": {"object": {"id": "test_id"}},
            }
            yield mock

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for webhook configuration."""
        with patch("app.routes.payments.settings") as mock:
            mock.stripe_webhook_secret = "whsec_test_secret"
            yield mock

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        return db

    @pytest.mark.asyncio
    async def test_create_payment_intent_success(self, mock_stripe):
        """Test successful payment intent creation."""
        request = PaymentIntentCreateRequest(items=[{"id": "cognitive-engine-v2"}], currency="usd")

        result = await create_payment_intent(request)

        assert result.clientSecret == "test_secret"

    @pytest.mark.asyncio
    async def test_create_payment_intent_missing_item_id(self, mock_stripe):
        """Test payment intent creation with missing item ID."""
        request = PaymentIntentCreateRequest(items=[{}], currency="usd")

        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_payment_intent_unknown_product(self, mock_stripe):
        """Test payment intent creation with unknown product."""
        request = PaymentIntentCreateRequest(items=[{"id": "unknown"}], currency="usd")

        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_payment_intent_no_valid_items(self, mock_stripe):
        """Test payment intent creation with no valid items."""
        request = PaymentIntentCreateRequest(items=[], currency="usd")

        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_payment_intent_stripe_error(self, mock_stripe):
        """Test payment intent creation with Stripe error."""
        mock_stripe.PaymentIntent.create.side_effect = Exception("Stripe error")
        request = PaymentIntentCreateRequest(items=[{"id": "cognitive-engine-v2"}], currency="usd")

        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_stripe_webhook_missing_signature(self, mock_db):
        """Test webhook without signature header."""
        request = Mock(headers={}, body=AsyncMock(return_value=b"test_payload"))

        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_webhook_invalid_payload(self, mock_db, mock_settings):
        """Test webhook with invalid payload."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.Webhook.construct_event.side_effect = ValueError("Invalid payload")
            request = Mock(
                headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
            )

            with pytest.raises(HTTPException) as exc:
                await stripe_webhook(request)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_webhook_invalid_signature(self, mock_settings):
        """Test webhook with invalid signature."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = Exception
            mock_stripe.Webhook.construct_event.side_effect = Exception("Invalid sig")
            request = Mock(
                headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
            )

            with pytest.raises(HTTPException) as exc:
                await stripe_webhook(request)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_webhook_payment_succeeded(self, mock_settings):
        """Test webhook payment succeeded event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch("app.routes.payments._handle_payment_succeeded") as mock_handler:
                mock_stripe.Webhook.construct_event.return_value = {
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_test", "amount": 9900}},
                }
                request = Mock(
                    headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
                )

                result = await stripe_webhook(request)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhook_payment_failed(self, mock_settings):
        """Test webhook payment failed event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch("app.routes.payments._handle_payment_failed") as mock_handler:
                mock_stripe.Webhook.construct_event.return_value = {
                    "type": "payment_intent.payment_failed",
                    "data": {"object": {"id": "pi_test"}},
                }
                request = Mock(
                    headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
                )

                result = await stripe_webhook(request)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhook_dispute_created(self, mock_db, mock_settings):
        """Test webhook dispute created event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "charge.dispute.created",
                "data": {
                    "object": {
                        "id": "dp_test",
                        "charge": "ch_test",
                        "amount": 9900,
                        "currency": "usd",
                        "reason": "product_not_received",
                    }
                },
            }
            request = Mock(
                headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
            )

            result = await stripe_webhook(request)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhook_dispute_closed(self, mock_settings):
        """Test webhook dispute closed event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch("app.routes.payments._handle_dispute_closed") as mock_handler:
                mock_stripe.Webhook.construct_event.return_value = {
                    "type": "charge.dispute.closed",
                    "data": {"object": {"id": "dp_test", "status": "lost"}},
                }
                request = Mock(
                    headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
                )

                result = await stripe_webhook(request)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhook_refund(self, mock_settings):
        """Test webhook refund event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch("app.routes.payments._handle_refund") as mock_handler:
                mock_stripe.Webhook.construct_event.return_value = {
                    "type": "charge.refunded",
                    "data": {"object": {"id": "ch_test", "refunds": {"data": [{"amount": 9900}]}}},
                }
                request = Mock(
                    headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
                )

                result = await stripe_webhook(request)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhook_subscription_created(self, mock_settings):
        """Test webhook subscription created event."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch("app.routes.payments._handle_subscription_event") as mock_handler:
                mock_stripe.Webhook.construct_event.return_value = {
                    "type": "customer.subscription.created",
                    "data": {"object": {"id": "sub_test"}},
                }
                request = Mock(
                    headers={"stripe-signature": "test_sig"}, body=AsyncMock(return_value=b"test")
                )

                result = await stripe_webhook(request)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded(self, mock_db):
        """Test payment success handler."""
        payment_intent = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }

        await _handle_payment_succeeded(mock_db, payment_intent)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_payment_failed(self, mock_db):
        """Test payment failure handler."""
        payment_intent = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "user123", "order_id": "order123"},
            "last_payment_error": {"message": "Card declined", "type": "card_error"},
        }

        await _handle_payment_failed(mock_db, payment_intent)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_dispute_created(self, mock_db):
        """Test dispute creation handler."""
        dispute = {
            "id": "dp_test",
            "charge": "ch_test",
            "amount": 9900,
            "currency": "usd",
            "reason": "product_not_received",
        }

        await _handle_dispute_created(mock_db, dispute)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_dispute_closed(self, mock_db):
        """Test dispute closure handler."""
        dispute = {"id": "dp_test", "status": "lost", "charge": "ch_test"}

        await _handle_dispute_closed(mock_db, dispute)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_refund(self, mock_db):
        """Test refund handler."""
        charge = {
            "id": "ch_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }

        await _handle_refund(mock_db, charge, 9900)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_created(self, mock_db):
        """Test subscription created event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "active"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.created", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_updated(self, mock_db):
        """Test subscription updated event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "active"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.updated", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_deleted(self, mock_db):
        """Test subscription deleted event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "canceled"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.deleted", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_paused(self, mock_db):
        """Test subscription paused event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "paused"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.paused", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_resumed(self, mock_db):
        """Test subscription resumed event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "active"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.resumed", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_payment_failed(self, mock_db):
        """Test subscription payment failed event handler."""
        subscription = {"id": "sub_test", "customer": "cus_test", "status": "past_due"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.payment_failed", subscription
        )  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded_error(self, mock_db):
        """Test payment success handler with error."""
        payment_intent = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123"},
        }

        await _handle_payment_succeeded(mock_db, payment_intent)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_payment_failed_error(self, mock_db):
        """Test payment failure handler with error."""
        payment_intent = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "user123"},
            "last_payment_error": {"message": "Card declined"},
        }

        await _handle_payment_failed(mock_db, payment_intent)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_dispute_created_error(self, mock_db):
        """Test dispute creation handler with error."""
        dispute = {"id": "dp_test", "charge": "ch_test", "amount": 9900}

        await _handle_dispute_created(mock_db, dispute)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_dispute_closed_error(self, mock_db):
        """Test dispute closure handler with error."""
        dispute = {"id": "dp_test", "status": "lost"}

        await _handle_dispute_closed(mock_db, dispute)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_refund_error(self, mock_db):
        """Test refund handler with error."""
        charge = {"id": "ch_test", "amount": 9900}

        await _handle_refund(mock_db, charge, 9900)  # Should not raise

    @pytest.mark.asyncio
    async def test_handle_subscription_event_error(self, mock_db):
        """Test subscription event handler with error."""
        subscription = {"id": "sub_test", "customer": "cus_test"}

        await _handle_subscription_event(
            mock_db, "customer.subscription.created", subscription
        )  # Should not raise
