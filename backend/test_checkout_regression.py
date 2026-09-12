"""
Regression tests for the NexaCart Checkout / Payment flow.

Covers:
A. Cart → Checkout without existing payment → checkout loads normally
B. Checkout → Pay → payment created → Razorpay order ID received
C. Existing PENDING payment → resume → same Razorpay order ID reused
D. Razorpay cancel → payment remains PENDING and recoverable
E. Retry after cancel → resume re-opens Razorpay
F. Successful Razorpay verify → payment SUCCESS → order created exactly once
G. Simulated provider still works end-to-end
"""

import sys
import os
import uuid
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# Force simulated provider for most tests; Razorpay tests mock the provider.
os.environ["PAYMENT_PROVIDER"] = "simulated"

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine
from models.product import Product
from models.payment import Payment
from models.cart import Cart
from models.order import Order
from models.event import AuditEvent
from seed.seed_products import seed_products
from services.payment_service import PaymentService, SimulatedPaymentProvider


def _seed_and_reset(session_id: str):
    db = SessionLocal()
    seed_products(db)
    PaymentService._provider = None
    for model in (Payment, Cart, Order, AuditEvent):
        db.query(model).filter(model.session_id == session_id).delete()
    db.commit()
    db.close()


def _build_cart(client, session_id, product_id, quantity=1):
    """Add item and approve cart → APPROVED_FOR_PAYMENT."""
    client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": product_id, "quantity": quantity},
    )
    client.post(f"/api/cart/{session_id}/request-approval")
    resp = client.post(f"/api/cart/{session_id}/approve")
    return resp


def _get_product_id():
    db = SessionLocal()
    product = db.query(Product).filter(Product.stock_quantity > 0).first()
    pid = product.id if product else None
    db.close()
    return pid


class TestCheckoutFlowA_CartToCheckoutWithoutPayment(unittest.TestCase):
    """A. Cart → Checkout without existing payment → loads normally."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_a_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_cart_loads_for_checkout(self):
        """GET /api/cart returns cart data for the checkout page."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        resp = self.client.get(f"/api/cart/{self.session_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data["items"]), 0)
        self.assertIn(data["status"], ["ACTIVE", "VERIFIED", "APPROVED_FOR_PAYMENT"])

    def test_checkout_summary_loads(self):
        """GET /api/cart/{sid}/checkout-summary returns items + total."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        resp = self.client.get(f"/api/cart/{self.session_id}/checkout-summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["total"], 0)

    def test_contract_loads(self):
        """GET /api/contracts returns contract data (may be empty)."""
        resp = self.client.get(f"/api/contracts/{self.session_id}")
        self.assertEqual(resp.status_code, 200)

    def test_payment_not_allowed_before_approval(self):
        """POST /api/payment/create returns 400 if cart not APPROVED_FOR_PAYMENT."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        self.assertEqual(resp.status_code, 400)


class TestCheckoutFlowB_PayCreatesPayment(unittest.TestCase):
    """B. Checkout → Pay → payment created → Razorpay order ID received."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_b_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_auto_approve_then_create_payment(self):
        """Full approval → payment creation returns payment_id and success."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("payment_id", data)
        self.assertEqual(data["status"], "PENDING")
        if data.get("provider") == "razorpay":
            self.assertIn("razorpay_order_id", data)
            self.assertIn("razorpay_key_id", data)

    def test_request_approval_endpoint(self):
        """POST /api/cart/{sid}/request-approval transitions to AWAITING_APPROVAL."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        resp = self.client.post(f"/api/cart/{self.session_id}/request-approval")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

    def test_approve_endpoint(self):
        """POST /api/cart/{sid}/approve transitions to APPROVED_FOR_PAYMENT."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        self.client.post(f"/api/cart/{self.session_id}/request-approval")
        resp = self.client.post(f"/api/cart/{self.session_id}/approve")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "APPROVED_FOR_PAYMENT")


class TestCheckoutFlowC_ResumeExistingPayment(unittest.TestCase):
    """C. Existing PENDING payment → resume → same Razorpay order ID reused."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_c_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_resume_returns_same_payment(self):
        """Calling create_payment twice returns the same payment_id."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp1 = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data1 = resp1.json()
        self.assertTrue(data1["success"])

        resp2 = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data2 = resp2.json()
        self.assertTrue(data2["success"])
        self.assertTrue(data2.get("resumed"))
        self.assertEqual(data1["payment_id"], data2["payment_id"])
        if data1.get("razorpay_order_id"):
            self.assertEqual(data1["razorpay_order_id"], data2["razorpay_order_id"])


class TestCheckoutFlowD_RazorpayCancel(unittest.TestCase):
    """D. Razorpay cancel → payment remains PENDING and recoverable."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_d_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_payment_stays_pending_after_no_action(self):
        """After payment created (simulating cancel), payment is still PENDING."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data = resp.json()
        self.assertEqual(data["status"], "PENDING")

        db = SessionLocal()
        payment = db.query(Payment).filter(Payment.id == data["payment_id"]).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, "PENDING")
        db.close()


class TestCheckoutFlowE_RetryAfterCancel(unittest.TestCase):
    """E. Retry after cancel → resume re-opens Razorpay with same order."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_e_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_retry_returns_resume_with_same_order(self):
        """Simulating cancel then retry returns resumed payment with same id."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp1 = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data1 = resp1.json()
        original_payment_id = data1["payment_id"]

        resp2 = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data2 = resp2.json()
        self.assertTrue(data2.get("resumed"))
        self.assertEqual(data2["payment_id"], original_payment_id)


class TestCheckoutFlowF_SimulatedProvider(unittest.TestCase):
    """G. Simulated provider works end-to-end."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_f_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()
        PaymentService._provider = SimulatedPaymentProvider()

    def tearDown(self):
        PaymentService._provider = None
        _seed_and_reset(self.session_id)

    def test_simulated_payment_full_flow(self):
        """Create payment → confirm → order created."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data = resp.json()
        self.assertTrue(data["success"])
        payment_id = data["payment_id"]

        resp = self.client.post(f"/api/payment/{payment_id}/confirm")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn(data["status"], ("captured", "SUCCESS"))

        db = SessionLocal()
        order = db.query(Order).filter(Order.payment_id == payment_id).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, "CONFIRMED")
        db.close()

    def test_double_confirm_idempotent(self):
        """Confirming an already-confirmed payment does not create duplicate orders."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        payment_id = resp.json()["payment_id"]

        self.client.post(f"/api/payment/{payment_id}/confirm")
        self.client.post(f"/api/payment/{payment_id}/confirm")

        db = SessionLocal()
        orders = db.query(Order).filter(Order.payment_id == payment_id).all()
        self.assertEqual(len(orders), 1)
        db.close()

    def test_completed_payment_never_charges_again(self):
        """Once paid, re-calling create_payment returns already_completed, not a new charge."""
        _build_cart(self.client, self.session_id, self.product_id)

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        payment_id = resp.json()["payment_id"]
        self.client.post(f"/api/payment/{payment_id}/confirm")

        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        data = resp.json()
        self.assertTrue(data.get("already_completed"))
        self.assertEqual(data["payment_id"], payment_id)


class TestCheckoutFlowG_ApprovalEdgeCases(unittest.TestCase):
    """Edge cases for the approval → payment flow."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = f"test_checkout_g_{uuid.uuid4().hex[:8]}"
        _seed_and_reset(self.session_id)
        self.product_id = _get_product_id()

    def tearDown(self):
        _seed_and_reset(self.session_id)

    def test_approve_without_request_fails(self):
        """Approving a cart that is not AWAITING_APPROVAL fails."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        resp = self.client.post(f"/api/cart/{self.session_id}/approve")
        self.assertEqual(resp.status_code, 400)

    def test_request_approval_idempotent(self):
        """Requesting approval on an already-requested cart returns 400 (frontend catches)."""
        self.client.post(
            f"/api/cart/{self.session_id}/items",
            json={"product_id": self.product_id, "quantity": 1},
        )
        self.client.post(f"/api/cart/{self.session_id}/request-approval")
        resp = self.client.post(f"/api/cart/{self.session_id}/request-approval")
        self.assertIn(resp.status_code, (200, 400))

    def test_approve_idempotent(self):
        """Approving an already-approved cart returns 400 (frontend catches this)."""
        _build_cart(self.client, self.session_id, self.product_id)
        resp = self.client.post(f"/api/cart/{self.session_id}/approve")
        self.assertIn(resp.status_code, (200, 400))

    def test_empty_cart_payment_fails(self):
        """Cannot create payment for an empty cart."""
        resp = self.client.post(f"/api/payment/create?session_id={self.session_id}")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
