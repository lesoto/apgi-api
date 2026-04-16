"""
Unit tests for payment routes — targeting ≥90% coverage of app/routes/payments.py.

Validates: Requirements 3.1, 3.15
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.testclient import TestClient
from typing import Generator, Any, Type

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

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> Mock:
    """Mock database session."""
    db = Mock(spec=Session)
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.delete = Mock()
    return db


@pytest.fixture
def mock_settings() -> Generator[Mock, None, None]:
    """Mock settings with stripe_webhook_secret configured."""
    with patch("app.routes.payments.settings") as mock:
        mock.stripe_webhook_secret = "whsec_test_secret"
        mock.stripe_secret_key = "sk_test_key"
        yield mock


@pytest.fixture
def client(mock_db: Mock) -> Generator[tuple[TestClient, Mock], None, None]:
    """TestClient with DB dependency overridden and test_mode=True."""
    from app.main import create_app
    from app.database.connection import get_db

    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, mock_db


# ---------------------------------------------------------------------------
# Direct async handler tests — create_payment_intent
# ---------------------------------------------------------------------------


class TestCreatePaymentIntent:
    """Tests for create_payment_intent handler."""

    @pytest.fixture
    def mock_stripe(self) -> Generator[Mock, None, None]:
        with patch("app.routes.payments.stripe") as mock:
            mock.PaymentIntent.create.return_value = Mock(client_secret="test_secret")
            yield mock

    @pytest.mark.asyncio
    async def test_success(self, mock_stripe: Mock) -> None:
        request = PaymentIntentCreateRequest(items=[{"id": "cognitive-engine-v2"}], currency="usd")
        result = await create_payment_intent(request)
        assert result.clientSecret == "test_secret"

    @pytest.mark.asyncio
    async def test_missing_item_id(self, mock_stripe: Mock) -> None:
        request = PaymentIntentCreateRequest(items=[{}], currency="usd")
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_unknown_product(self, mock_stripe: Mock) -> None:
        request = PaymentIntentCreateRequest(items=[{"id": "unknown-product"}], currency="usd")
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_items(self, mock_stripe: Mock) -> None:
        request = PaymentIntentCreateRequest(items=[], currency="usd")
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_error(self, mock_stripe: Mock) -> None:
        """Card-declined / generic Stripe error → 500."""
        mock_stripe.PaymentIntent.create.side_effect = Exception("card declined")
        request = PaymentIntentCreateRequest(items=[{"id": "cognitive-engine-v2"}], currency="usd")
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_stripe_specific_error(self, mock_stripe: Mock) -> None:
        """Stripe StripeError subclass → 500."""
        StripeError = type("StripeError", (Exception,), {})
        mock_stripe.PaymentIntent.create.side_effect = StripeError("Your card was declined")
        request = PaymentIntentCreateRequest(items=[{"id": "cognitive-engine-v2"}], currency="usd")
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)
        assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# Direct async handler tests — stripe_webhook
# ---------------------------------------------------------------------------


class TestStripeWebhook:
    """Tests for stripe_webhook handler."""

    def _make_request(self, sig_header: str | None = None, body: bytes = b"test_payload") -> Mock:
        req = Mock()
        req.headers = {"stripe-signature": sig_header} if sig_header else {}
        req.body = AsyncMock(return_value=body)
        return req

    @pytest.mark.asyncio
    async def test_missing_signature(self, mock_db: Mock) -> None:
        req = self._make_request(sig_header=None)
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req, mock_db)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_webhook_secret_configured(self, mock_db: Mock) -> None:
        """When stripe_webhook_secret is None → 500."""
        with patch("app.routes.payments.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = None
            req = self._make_request(sig_header="sig_test")
            with pytest.raises(HTTPException) as exc:
                await stripe_webhook(req, mock_db)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_invalid_payload_value_error(self, mock_db: Mock, mock_settings: Mock) -> None:
        """ValueError from construct_event → 400."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.Webhook.construct_event.side_effect = ValueError("bad payload")
            mock_stripe.SignatureVerificationError = type(
                "SignatureVerificationError", (Exception,), {}
            )
            req = self._make_request(sig_header="sig_test")
            with pytest.raises(HTTPException) as exc:
                await stripe_webhook(req, mock_db)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_signature_verification_error(
        self, mock_db: Mock, mock_settings: Mock
    ) -> None:
        """Webhook-signature-failure path → 400."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            SigVerError = type("SignatureVerificationError", (Exception,), {})
            mock_stripe.SignatureVerificationError = SigVerError
            mock_stripe.Webhook.construct_event.side_effect = SigVerError("bad sig")
            req = self._make_request(sig_header="sig_test")
            with pytest.raises(HTTPException) as exc:
                await stripe_webhook(req, mock_db)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_already_processed_idempotency(self, mock_db: Mock, mock_settings: Mock) -> None:
        """Event already in DB → returns already_processed."""
        from app.database.models import ProcessedWebhookEvent

        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = type(
                "SignatureVerificationError", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "id": "evt_already",
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_test"}},
            }
            # Simulate existing event in DB
            existing = Mock(spec=ProcessedWebhookEvent)
            mock_db.query.return_value.filter.return_value.first.return_value = existing
            req = self._make_request(sig_header="sig_test")
            result = await stripe_webhook(req, mock_db)
            assert result["detail"] == "already_processed"

    @pytest.mark.asyncio
    async def test_unhandled_event_type(self, mock_db: Mock, mock_settings: Mock) -> None:
        """Unknown event type → success=True, event recorded."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = type(
                "SignatureVerificationError", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "id": "evt_unknown",
                "type": "some.unknown.event",
                "data": {"object": {}},
            }
            mock_db.query.return_value.filter.return_value.first.return_value = None
            req = self._make_request(sig_header="sig_test")
            result = await stripe_webhook(req, mock_db)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_payment_succeeded_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_payment_succeeded",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_pi_success",
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_test", "amount": 9900}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_payment_failed_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_payment_failed",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_pi_failed",
                    "type": "payment_intent.payment_failed",
                    "data": {"object": {"id": "pi_test"}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_dispute_created_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_dispute_created",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_dispute_created",
                    "type": "charge.dispute.created",
                    "data": {"object": {"id": "dp_test", "charge": "ch_test", "amount": 9900}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_dispute_closed_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_dispute_closed",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_dispute_closed",
                    "type": "charge.dispute.closed",
                    "data": {"object": {"id": "dp_test", "status": "lost"}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_charge_refunded_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_refund", new_callable=AsyncMock, return_value=True
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_refund",
                    "type": "charge.refunded",
                    "data": {"object": {"id": "ch_test", "refunds": {"data": [{"amount": 9900}]}}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_subscription_event(self, mock_db: Mock, mock_settings: Mock) -> None:
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_subscription_event",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_sub_created",
                    "type": "customer.subscription.created",
                    "data": {"object": {"id": "sub_test"}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_handler_returns_false_logs_error(
        self, mock_db: Mock, mock_settings: Mock
    ) -> None:
        """When handler returns False, error is logged but response is still success."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_payment_succeeded",
                new_callable=AsyncMock,
                return_value=False,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_fail_handler",
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_test"}},
                }
                mock_db.query.return_value.filter.return_value.first.return_value = None
                req = self._make_request(sig_header="sig_test")
                result = await stripe_webhook(req, mock_db)
                assert result["status"] == "success"


# ---------------------------------------------------------------------------
# _handle_payment_succeeded
# ---------------------------------------------------------------------------


class TestHandlePaymentSucceeded:

    @pytest.mark.asyncio
    async def test_no_user_id_no_order_id(self, mock_db: Mock) -> None:
        """No metadata → returns True (nothing to update)."""
        pi = {"id": "pi_test", "amount": 9900, "currency": "usd", "metadata": {}}
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_user_id(self, mock_db: Mock) -> None:
        """user_id not in DB → returns False."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "bad_user"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_user_order_found_success(self, mock_db: Mock) -> None:
        """Valid user + matching order → order.status = succeeded."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)
        mock_order = Mock(spec=Order)
        mock_order.user_id = "user123"
        mock_order.amount_cents = 9900

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = mock_order
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is True
        assert mock_order.status == "succeeded"

    @pytest.mark.asyncio
    async def test_user_id_mismatch_on_order(self, mock_db: Mock) -> None:
        """Order user_id doesn't match metadata user_id → returns False."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)
        mock_order = Mock(spec=Order)
        mock_order.user_id = "different_user"
        mock_order.amount_cents = 9900

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = mock_order
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is False

    @pytest.mark.asyncio
    async def test_amount_mismatch_on_order(self, mock_db: Mock) -> None:
        """Order amount doesn't match payment amount → returns False."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)
        mock_order = Mock(spec=Order)
        mock_order.user_id = "user123"
        mock_order.amount_cents = 5000  # different from 9900

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = mock_order
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is False

    @pytest.mark.asyncio
    async def test_order_not_found(self, mock_db: Mock) -> None:
        """Order ID in metadata but order not in DB → returns False."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "missing_order"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, mock_db: Mock) -> None:
        mock_db.query.side_effect = Exception("db error")
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "currency": "usd",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_payment_succeeded(mock_db, pi)
        assert result is False


# ---------------------------------------------------------------------------
# _handle_payment_failed
# ---------------------------------------------------------------------------


class TestHandlePaymentFailed:

    @pytest.mark.asyncio
    async def test_no_metadata(self, mock_db: Mock) -> None:
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {},
            "last_payment_error": {"message": "Card declined", "type": "card_error"},
        }
        result = await _handle_payment_failed(mock_db, pi)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_user_id(self, mock_db: Mock) -> None:
        """user_id not in DB → returns False."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "bad_user"},
            "last_payment_error": {"message": "Card declined"},
        }
        result = await _handle_payment_failed(mock_db, pi)
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_user_with_order(self, mock_db: Mock) -> None:
        """Card-declined path with valid user and order → order.status = failed."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)
        mock_order = Mock(spec=Order)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = mock_order
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "user123", "order_id": "order123"},
            "last_payment_error": {"message": "Your card was declined", "type": "card_error"},
        }
        result = await _handle_payment_failed(mock_db, pi)
        assert result is True
        assert mock_order.status == "failed"

    @pytest.mark.asyncio
    async def test_order_not_found(self, mock_db: Mock) -> None:
        """Order ID in metadata but order not in DB → still returns True."""
        from app.database.models import User, Order

        mock_user = Mock(spec=User)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "user123", "order_id": "missing_order"},
            "last_payment_error": {},
        }
        result = await _handle_payment_failed(mock_db, pi)
        assert result is True

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, mock_db: Mock) -> None:
        mock_db.query.side_effect = Exception("db error")
        pi = {
            "id": "pi_test",
            "amount": 9900,
            "metadata": {"user_id": "user123"},
            "last_payment_error": {},
        }
        result = await _handle_payment_failed(mock_db, pi)
        assert result is False


# ---------------------------------------------------------------------------
# _handle_dispute_created / _handle_dispute_closed
# ---------------------------------------------------------------------------


class TestHandleDispute:

    @pytest.mark.asyncio
    async def test_dispute_created_success(self, mock_db: Mock) -> None:
        dispute = {
            "id": "dp_test",
            "charge": "ch_test",
            "amount": 9900,
            "currency": "usd",
            "reason": "product_not_received",
        }
        result = await _handle_dispute_created(mock_db, dispute)
        assert result is True

    @pytest.mark.asyncio
    async def test_dispute_created_exception(self, mock_db: Mock) -> None:
        # Force an exception by making dispute.get raise
        dispute = Mock()
        dispute.get.side_effect = Exception("unexpected")
        result = await _handle_dispute_created(mock_db, dispute)
        assert result is False

    @pytest.mark.asyncio
    async def test_dispute_closed_success(self, mock_db: Mock) -> None:
        dispute = {"id": "dp_test", "status": "lost", "charge": "ch_test"}
        result = await _handle_dispute_closed(mock_db, dispute)
        assert result is True

    @pytest.mark.asyncio
    async def test_dispute_closed_exception(self, mock_db: Mock) -> None:
        dispute = Mock()
        dispute.get.side_effect = Exception("unexpected")
        result = await _handle_dispute_closed(mock_db, dispute)
        assert result is False


# ---------------------------------------------------------------------------
# _handle_refund
# ---------------------------------------------------------------------------


class TestHandleRefund:

    @pytest.mark.asyncio
    async def test_no_metadata(self, mock_db: Mock) -> None:
        charge = {"id": "ch_test", "currency": "usd", "metadata": {}}
        result = await _handle_refund(mock_db, charge, 9900)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_user_id(self, mock_db: Mock) -> None:
        mock_db.query.return_value.filter.return_value.first.return_value = None
        charge = {"id": "ch_test", "currency": "usd", "metadata": {"user_id": "bad_user"}}
        result = await _handle_refund(mock_db, charge, 9900)
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_user_with_order(self, mock_db: Mock) -> None:
        from app.database.models import User, Order

        mock_user = Mock(spec=User)
        mock_order = Mock(spec=Order)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = mock_order
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        charge = {
            "id": "ch_test",
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "order123"},
        }
        result = await _handle_refund(mock_db, charge, 9900)
        assert result is True
        assert mock_order.status == "refunded"

    @pytest.mark.asyncio
    async def test_order_not_found(self, mock_db: Mock) -> None:
        from app.database.models import User, Order

        mock_user = Mock(spec=User)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Order:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        charge = {
            "id": "ch_test",
            "currency": "usd",
            "metadata": {"user_id": "user123", "order_id": "missing_order"},
        }
        result = await _handle_refund(mock_db, charge, 9900)
        assert result is True

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, mock_db: Mock) -> None:
        mock_db.query.side_effect = Exception("db error")
        charge = {"id": "ch_test", "currency": "usd", "metadata": {"user_id": "user123"}}
        result = await _handle_refund(mock_db, charge, 9900)
        assert result is False


# ---------------------------------------------------------------------------
# _handle_subscription_event
# ---------------------------------------------------------------------------


class TestHandleSubscriptionEvent:

    @pytest.mark.asyncio
    async def test_created_no_user_id(self, mock_db: Mock) -> None:
        """Subscription created without user_id → no DB insert, returns True."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        sub = {"id": "sub_test", "customer": "cus_test", "status": "active", "metadata": {}}
        result = await _handle_subscription_event(mock_db, "customer.subscription.created", sub)
        assert result is True

    @pytest.mark.asyncio
    async def test_created_invalid_user_id(self, mock_db: Mock) -> None:
        """Invalid user_id → returns False."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "bad_user"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.created", sub)
        assert result is False

    @pytest.mark.asyncio
    async def test_created_with_valid_user_new_subscription(self, mock_db: Mock) -> None:
        """Valid user, no existing subscription → creates new Subscription record."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)

        call_count = [0]

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                # First call: no existing sub
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
            "plan": {"id": "plan_basic"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.created", sub)
        assert result is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_created_existing_subscription(self, mock_db: Mock) -> None:
        """Valid user, existing subscription → no new insert."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)
        mock_sub = Mock(spec=Subscription)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = mock_sub
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.created", sub)
        assert result is True
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_updated_existing_subscription(self, mock_db: Mock) -> None:
        """Subscription updated → updates existing record."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)
        mock_sub = Mock(spec=Subscription)
        mock_sub.plan_id = "plan_old"

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = mock_sub
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": True,
            "plan": {"id": "plan_new"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.updated", sub)
        assert result is True
        assert mock_sub.status == "active"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_updated_no_existing_subscription(self, mock_db: Mock) -> None:
        """Subscription updated but not found in DB → still returns True."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.deleted", sub)
        assert result is True

    @pytest.mark.asyncio
    async def test_paused_event(self, mock_db: Mock) -> None:
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)
        mock_sub = Mock(spec=Subscription)
        mock_sub.plan_id = "plan_basic"

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = mock_sub
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "paused",
            "metadata": {"user_id": "user123"},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.paused", sub)
        assert result is True

    @pytest.mark.asyncio
    async def test_resumed_event(self, mock_db: Mock) -> None:
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)
        mock_sub = Mock(spec=Subscription)
        mock_sub.plan_id = "plan_basic"

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = mock_sub
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.resumed", sub)
        assert result is True

    @pytest.mark.asyncio
    async def test_payment_failed_event_updates_past_due(self, mock_db: Mock) -> None:
        """Subscription payment_failed → status set to past_due."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)
        mock_sub = Mock(spec=Subscription)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = mock_sub
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "past_due",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_subscription_event(
            mock_db, "customer.subscription.payment_failed", sub
        )
        assert result is True
        assert mock_sub.status == "past_due"

    @pytest.mark.asyncio
    async def test_payment_failed_no_subscription(self, mock_db: Mock) -> None:
        """Subscription payment_failed but sub not in DB → still True."""
        from app.database.models import User, Subscription

        mock_user = Mock(spec=User)

        def query_side_effect(model: Type[Any]) -> Any:
            q = Mock()
            if model is User:
                q.filter.return_value.first.return_value = mock_user
            elif model is Subscription:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "past_due",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_subscription_event(
            mock_db, "customer.subscription.payment_failed", sub
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, mock_db: Mock) -> None:
        mock_db.query.side_effect = Exception("db error")
        sub = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user123"},
        }
        result = await _handle_subscription_event(mock_db, "customer.subscription.created", sub)
        assert result is False


# ---------------------------------------------------------------------------
# Webhook outer exception path (500)
# ---------------------------------------------------------------------------


class TestStripeWebhookOuterException:

    @pytest.mark.asyncio
    async def test_outer_exception_raises_500(self, mock_db: Mock, mock_settings: Mock) -> None:
        """db.commit() raising after success → outer except catches it → 500."""
        with patch("app.routes.payments.stripe") as mock_stripe:
            with patch(
                "app.routes.payments._handle_payment_succeeded",
                new_callable=AsyncMock,
                return_value=True,
            ):
                mock_stripe.SignatureVerificationError = type(
                    "SignatureVerificationError", (Exception,), {}
                )
                mock_stripe.Webhook.construct_event.return_value = {
                    "id": "evt_boom",
                    "type": "payment_intent.succeeded",
                    "data": {"object": {"id": "pi_test"}},
                }
                # Idempotency check returns None (not yet processed)
                mock_db.query.return_value.filter.return_value.first.return_value = None
                # db.commit() raises unexpectedly
                mock_db.commit.side_effect = Exception("db commit boom")
                req = Mock()
                req.headers = {"stripe-signature": "sig_test"}
                req.body = AsyncMock(return_value=b"test_payload")
                with pytest.raises(HTTPException) as exc:
                    await stripe_webhook(req, mock_db)
                assert exc.value.status_code == 500
