import sys
import os
import uuid
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

# Force simulated provider for payment lifecycle tests (these tests exercise
# the confirm endpoint, not the Razorpay verify endpoint).
os.environ["PAYMENT_PROVIDER"] = "simulated"

from main import app
from database import SessionLocal, Base, engine
from models.product import Product
from models.payment import Payment
from models.cart import Cart
from models.order import Order
from models.event import AuditEvent
from seed.seed_products import seed_products
from services.payment_service import PaymentService


def _run_payment_flow(client, session_id):
    """Build an APPROVED_FOR_PAYMENT cart and return the created payment."""
    with SessionLocal() as db:
        product = db.query(Product).filter(Product.stock_quantity > 0).first()
        product_id = product.id

    client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": product_id, "quantity": 1},
    )
    client.post(f"/api/cart/{session_id}/request-approval")
    client.post(f"/api/cart/{session_id}/approve")

    resp = client.post(f"/api/payment/create?session_id={session_id}")
    assert resp.status_code == 200
    return resp.json()


class TestPaymentLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = "test_pay_session"
        self.db = SessionLocal()
        seed_products(self.db)
        # Reset the cached provider so it picks up PAYMENT_PROVIDER=simulated
        PaymentService._provider = None
        for model in (Payment, Cart, Order, AuditEvent):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()

    def tearDown(self):
        for model in (Payment, Cart, Order, AuditEvent):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()
        self.db.close()

    def test_first_creation_then_resume(self):
        """A PENDING payment is created once; re-requesting resumes the same one."""
        first = _run_payment_flow(self.client, self.session_id)
        self.assertTrue(first["success"])
        self.assertNotIn("resumed", first)
        self.assertNotIn("already_completed", first)
        self.assertEqual(first["status"], "PENDING")

        again = self.client.post(
            f"/api/payment/create?session_id={self.session_id}"
        ).json()
        self.assertTrue(again["success"])
        self.assertTrue(again["resumed"])
        self.assertEqual(again["payment_id"], first["payment_id"])

        # Only one active payment row for the cart.
        with SessionLocal() as db:
            carts = db.query(Cart).filter(Cart.session_id == self.session_id).all()
            cart = carts[0]
            count = (
                db.query(Payment)
                .filter(Payment.cart_id == cart.id)
                .count()
            )
        self.assertEqual(count, 1)

    def test_completed_payment_never_charges_again(self):
        """After success + order, create returns already_completed with the order."""
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        confirm = self.client.post(f"/api/payment/{payment_id}/confirm")
        self.assertEqual(confirm.status_code, 200)
        body = confirm.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status"], "SUCCESS")
        self.assertIn("order", body)

        # Paying again must not create a new charge/order.
        again = self.client.post(
            f"/api/payment/create?session_id={self.session_id}"
        ).json()
        self.assertTrue(again["success"])
        self.assertTrue(again["already_completed"])
        self.assertEqual(again["payment_id"], payment_id)
        self.assertEqual(again["order_id"], body["order"]["order_id"])

        # Exactly one order and exactly one payment row.
        with SessionLocal() as db:
            order_count = (
                db.query(Order)
                .filter(Order.session_id == self.session_id)
                .count()
            )
            carts = db.query(Cart).filter(Cart.session_id == self.session_id).all()
            cart = carts[0]
            pay_count = (
                db.query(Payment).filter(Payment.cart_id == cart.id).count()
            )
        self.assertEqual(order_count, 1)
        self.assertEqual(pay_count, 1)

    def test_failed_payment_is_retried_with_new_attempt(self):
        """A FAILED payment triggers a fresh attempt while preserving history."""
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        with SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            payment.status = "FAILED"
            db.commit()

        retry = self.client.post(
            f"/api/payment/create?session_id={self.session_id}"
        ).json()
        self.assertTrue(retry["success"])
        self.assertNotIn("resumed", retry)
        self.assertNotIn("already_completed", retry)
        self.assertNotEqual(retry["payment_id"], payment_id)
        self.assertEqual(retry["status"], "PENDING")

        with SessionLocal() as db:
            carts = db.query(Cart).filter(Cart.session_id == self.session_id).all()
            cart = carts[0]
            rows = (
                db.query(Payment).filter(Payment.cart_id == cart.id).all()
            )
        # One FAILED (history) + one new PENDING (active).
        self.assertEqual(len(rows), 2)
        statuses = sorted(p.status for p in rows)
        self.assertEqual(statuses, ["FAILED", "PENDING"])

    def test_concurrent_create_generates_single_attempt(self):
        """Two rapid create calls for the same cart yield exactly one active payment."""
        _run_payment_flow(self.client, self.session_id)

        import threading
        results = []
        errors = []

        def call():
            try:
                r = self.client.post(
                    f"/api/payment/create?session_id={self.session_id}"
                )
                results.append((r.status_code, r.json()))
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        ids = set(r[1]["payment_id"] for r in results if r[0] == 200)
        self.assertEqual(len(ids), 1, f"Expected one active payment, got {ids}")

        with SessionLocal() as db:
            carts = db.query(Cart).filter(Cart.session_id == self.session_id).all()
            cart = carts[0]
            count = (
                db.query(Payment)
                .filter(Payment.cart_id == cart.id)
                .count()
            )
        self.assertEqual(count, 1)

    def test_confirm_twice_does_not_duplicate_order(self):
        """Confirming an already-successful payment must not create a second order."""
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        first = self.client.post(f"/api/payment/{payment_id}/confirm")
        self.assertEqual(first.status_code, 200)

        second = self.client.post(f"/api/payment/{payment_id}/confirm")
        # status SUCCESS -> cannot process again -> 400
        self.assertEqual(second.status_code, 400)

        with SessionLocal() as db:
            order_count = (
                db.query(Order)
                .filter(Order.session_id == self.session_id)
                .count()
            )
        self.assertEqual(order_count, 1)

    def test_razorpay_invalid_credentials_falls_back_to_simulated(self):
        """When Razorpay credentials are invalid, provider falls back to simulated."""
        import os
        from services.payment_service import PaymentService, _get_provider, SimulatedPaymentProvider

        # Force Razorpay provider (with invalid credentials)
        os.environ["PAYMENT_PROVIDER"] = "razorpay"
        os.environ["RAZORPAY_KEY_ID"] = "rzp_test_INVALID_KEY"
        os.environ["RAZORPAY_KEY_SECRET"] = "INVALID_SECRET_FOR_TESTING"
        PaymentService._provider = None

        provider = _get_provider()
        self.assertIsInstance(provider, SimulatedPaymentProvider)

        # Restore
        os.environ["PAYMENT_PROVIDER"] = "simulated"
        PaymentService._provider = None

    def test_razorpay_credentials_error_includes_detail(self):
        """Provider failure error message includes the actual provider error."""
        import os
        from services.razorpay_payment_provider import RazorpayPaymentProvider

        os.environ["RAZORPAY_KEY_ID"] = "rzp_test_INVALID_KEY"
        os.environ["RAZORPAY_KEY_SECRET"] = "INVALID_SECRET_FOR_TESTING"

        provider = RazorpayPaymentProvider()
        result = provider.create_payment(
            amount=100.0, currency="INR",
            metadata={"cart_id": "test", "session_id": "test"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Authentication failed", result["error"])

        # Restore
        os.environ["RAZORPAY_KEY_ID"] = "rzp_test_Kt1mXNnMSjMFSx"
        os.environ["RAZORPAY_KEY_SECRET"] = "O6pjfC6FBhNvJoGm7gRNvJRL"

    def test_simulated_provider_works_independently(self):
        """Simulated provider works when PAYMENT_PROVIDER=simulated."""
        import os
        from services.payment_service import PaymentService, SimulatedPaymentProvider

        os.environ["PAYMENT_PROVIDER"] = "simulated"
        PaymentService._provider = None

        provider = PaymentService._get_provider()
        self.assertIsInstance(provider, SimulatedPaymentProvider)

        result = provider.create_payment(
            amount=500.0, currency="INR",
            metadata={"cart_id": "test", "session_id": "test"}
        )
        self.assertTrue(result["success"])
        self.assertIn("sim_", result["provider_payment_id"])

        # Restore
        PaymentService._provider = None

    def test_razorpay_confirm_endpoint_rejects_razorpay(self):
        """The /confirm endpoint rejects Razorpay payments with a 400."""
        from services.payment_service import PaymentService

        # Create a payment using simulated provider
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        # Manually set the provider to razorpay so the confirm guard triggers
        with SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            payment.provider = "razorpay"
            db.commit()

        resp = self.client.post(f"/api/payment/{payment_id}/confirm")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("verify", resp.json()["detail"].lower())

    def test_razorpay_verify_endpoint_rejects_simulated(self):
        """The /verify endpoint requires valid Razorpay signature data."""
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        resp = self.client.post(
            f"/api/payment/{payment_id}/verify",
            json={
                "razorpay_order_id": "order_fake",
                "razorpay_payment_id": "pay_fake",
                "razorpay_signature": "sig_fake",
            },
        )
        # Signature verification fails with simulated provider
        self.assertEqual(resp.status_code, 400)

    def test_razorpay_verify_duplicate_protection(self):
        """Verifying an already-successful payment returns error, no duplicate order."""
        import hashlib, hmac
        from services.payment_service import PaymentService
        from services.razorpay_payment_provider import RazorpayPaymentProvider

        # Use a mock Razorpay provider that always returns success for verify
        class MockRazorpayProvider(RazorpayPaymentProvider):
            def __init__(self):
                self.key_id = "rzp_test_mock"
                self.key_secret = "mock_secret"
                # Skip parent __init__ which requires real Razorpay client

            def create_payment(self, amount, currency, metadata):
                return {
                    "success": True,
                    "provider_payment_id": f"rzp_mock_{uuid.uuid4().hex[:8]}",
                    "provider_order_id": f"order_mock_{uuid.uuid4().hex[:8]}",
                    "amount": amount,
                    "currency": currency,
                    "status": "created",
                    "key_id": self.key_id,
                }

            def verify_payment(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
                return {
                    "success": True,
                    "verified": True,
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                }

        PaymentService.set_provider(MockRazorpayProvider())

        # Create payment with simulated provider, then switch to mock Razorpay
        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        # Manually set provider to razorpay for the verify flow
        with SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            payment.provider = "razorpay"
            payment.provider_order_id = "order_mock_test"
            db.commit()

        # Build a signature
        secret = "mock_secret"
        payload_str = f"order_mock_test|pay_test_success"
        valid_sig = hmac.new(
            bytes(secret, "utf-8"),
            bytes(payload_str, "utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # First verify succeeds
        resp1 = self.client.post(
            f"/api/payment/{payment_id}/verify",
            json={
                "razorpay_order_id": "order_mock_test",
                "razorpay_payment_id": "pay_test_success",
                "razorpay_signature": valid_sig,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["success"])

        # Second verify is rejected (already SUCCESS)
        resp2 = self.client.post(
            f"/api/payment/{payment_id}/verify",
            json={
                "razorpay_order_id": "order_mock_test",
                "razorpay_payment_id": "pay_test_success",
                "razorpay_signature": valid_sig,
            },
        )
        self.assertEqual(resp2.status_code, 400)

        # Only one order created
        with SessionLocal() as db:
            order_count = (
                db.query(Order)
                .filter(Order.session_id == self.session_id)
                .count()
            )
        self.assertEqual(order_count, 1)

        # Restore
        PaymentService._provider = None

    def test_razorpay_verify_invalid_signature_fails(self):
        """Invalid Razorpay signature is rejected, payment remains recoverable."""
        from services.payment_service import PaymentService
        from services.razorpay_payment_provider import RazorpayPaymentProvider

        # Use a mock Razorpay provider that fails verification
        class MockRazorpayProvider(RazorpayPaymentProvider):
            def __init__(self):
                self.key_id = "rzp_test_mock"
                self.key_secret = "mock_secret"
                # Skip parent __init__ which requires real Razorpay client

            def create_payment(self, amount, currency, metadata):
                return {
                    "success": True,
                    "provider_payment_id": f"rzp_mock_{uuid.uuid4().hex[:8]}",
                    "provider_order_id": f"order_mock_{uuid.uuid4().hex[:8]}",
                    "amount": amount,
                    "currency": currency,
                    "status": "created",
                    "key_id": self.key_id,
                }

            def verify_payment(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
                return {
                    "success": False,
                    "verified": False,
                    "error": "Payment signature verification failed",
                }

        PaymentService.set_provider(MockRazorpayProvider())

        created = _run_payment_flow(self.client, self.session_id)
        payment_id = created["payment_id"]

        # Manually set provider to razorpay
        with SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            payment.provider = "razorpay"
            payment.provider_order_id = "order_mock_test"
            db.commit()

        resp = self.client.post(
            f"/api/payment/{payment_id}/verify",
            json={
                "razorpay_order_id": "order_mock_test",
                "razorpay_payment_id": "pay_fake_invalid",
                "razorpay_signature": "invalid_signature_abc123",
            },
        )
        self.assertEqual(resp.status_code, 400)

        # Payment is still in a recoverable state (not stuck)
        resp_get = self.client.get(f"/api/payment/{payment_id}")
        self.assertEqual(resp_get.status_code, 200)
        status = resp_get.json()["status"]
        self.assertIn(status, ["FAILED", "PROCESSING", "PENDING"])

        # Restore
        PaymentService._provider = None


if __name__ == "__main__":
    unittest.main()
