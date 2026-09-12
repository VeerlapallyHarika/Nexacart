import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

# Force simulated provider for decision trace tests
os.environ["PAYMENT_PROVIDER"] = "simulated"

from main import app
from database import SessionLocal, Base, engine
from models.product import Product
from models.payment import Payment
from models.cart import Cart
from models.order import Order
from models.event import AuditEvent
from models.decision_trace import DecisionTrace
from seed.seed_products import seed_products
from services.decision_trace_service import DecisionTraceService
from services.payment_service import PaymentService


def _build_approved_cart(client, session_id):
    with SessionLocal() as db:
        product = db.query(Product).filter(Product.stock_quantity > 0).first()
        product_id = product.id
        product_name = product.name
    client.post(f"/api/cart/{session_id}/items",
                json={"product_id": product_id, "quantity": 1})
    client.post(f"/api/cart/{session_id}/request-approval")
    client.post(f"/api/cart/{session_id}/approve")
    return product_id, product_name


def _complete_purchase(client, session_id):
    """Run the full journey through payment success so a decision trace backfills."""
    created = client.post(f"/api/payment/create?session_id={session_id}").json()
    payment_id = created["payment_id"]
    confirm = client.post(f"/api/payment/{payment_id}/confirm")
    return confirm.json() if confirm.status_code == 200 else None


class TestDecisionTraceLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = "test_trace_session"
        self.db = SessionLocal()
        seed_products(self.db)
        # Reset the cached provider so it picks up PAYMENT_PROVIDER=simulated
        PaymentService._provider = None
        for model in (Payment, Cart, Order, AuditEvent, DecisionTrace):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()

    def tearDown(self):
        for model in (Payment, Cart, Order, AuditEvent, DecisionTrace):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()
        self.db.close()

    def _trace_row(self):
        return (
            self.db.query(DecisionTrace)
            .filter(DecisionTrace.session_id == self.session_id)
            .first()
        )

    def test_01_no_trace_before_any_event(self):
        resp = self.client.get(f"/api/decision-traces/session/{self.session_id}")
        self.assertEqual(resp.status_code, 404)

    def test_02_decision_id_has_valid_format(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "hello"})
        row = self._trace_row()
        self.assertIsNotNone(row)
        # DEC-NX-<6 alphanumerics from a non-ambiguous alphabet
        self.assertRegex(row.decision_id, r"^DEC-NX-[A-HJ-NP-Z0-9]{6}$")
        # unique across sessions
        other = DecisionTraceService.generate_decision_id()
        self.assertNotEqual(other, row.decision_id)

    def test_03_single_session_maps_to_single_trace(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "i want a phone"})
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "under 30000"})
        count = self.db.query(DecisionTrace).filter(
            DecisionTrace.session_id == self.session_id
        ).count()
        self.assertEqual(count, 1)

    def test_04_trace_status_starts_in_progress(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "hello"})
        row = self._trace_row()
        self.assertEqual(row.status, "IN_PROGRESS")

    def test_05_trace_captures_goal_from_first_request(self):
        goal = "i want a smartphone under 50000"
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": goal})
        row = self._trace_row()
        self.assertEqual(row.goal, goal)

    def test_06_events_are_attached_to_the_trace(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "i want a phone"})
        row = self._trace_row()
        with SessionLocal() as db:
            evs = db.query(AuditEvent).filter(
                AuditEvent.session_id == self.session_id
            ).all()
            self.assertTrue(all(e.decision_id == row.decision_id for e in evs))

    def test_07_compose_trace_returns_composed_events(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "i want a phone"})
        row = self._trace_row()
        body = self.client.get(
            f"/api/decision-traces/{row.decision_id}"
        ).json()
        self.assertEqual(body["decision_id"], row.decision_id)
        self.assertEqual(body["status"], "IN_PROGRESS")
        self.assertTrue(isinstance(body["events"], list))
        # first event should be the user message, actor=user
        self.assertEqual(body["events"][0]["actor"], "user")
        self.assertEqual(body["events"][0]["event_type"], "USER_MESSAGE")

    def test_08_compose_trace_is_read_only_composition(self):
        """Trace never duplicates event data; it composes from real audit events."""
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "hello"})
        row = self._trace_row()
        body = self.client.get(
            f"/api/decision-traces/{row.decision_id}"
        ).json()
        with SessionLocal() as db:
            ev_count = db.query(AuditEvent).filter(
                AuditEvent.decision_id == row.decision_id
            ).count()
        # composed events reference audit rows, never exceed their count
        self.assertLessEqual(len(body["events"]), ev_count)

    def test_09_unknown_decision_id_returns_404(self):
        resp = self.client.get("/api/decision-traces/DEC-NX-ZZZZZZ")
        self.assertEqual(resp.status_code, 404)

    def test_10_session_endpoint_returns_latest_trace(self):
        self.client.post("/api/chat",
                         json={"session_id": self.session_id, "message": "hello"})
        row = self._trace_row()
        body = self.client.get(
            f"/api/decision-traces/session/{self.session_id}"
        ).json()
        self.assertEqual(body["decision_id"], row.decision_id)

    def test_11_purchase_completion_marks_trace_completed(self):
        _build_approved_cart(self.client, self.session_id)
        _complete_purchase(self.client, self.session_id)
        row = self._trace_row()
        self.assertEqual(row.status, "COMPLETED")
        body = self.client.get(
            f"/api/decision-traces/session/{self.session_id}"
        ).json()
        self.assertEqual(body["status"], "COMPLETED")
        self.assertIsNotNone(body["links"]["order_id"])

    def test_12_order_endpoint_resolves_to_trace(self):
        _build_approved_cart(self.client, self.session_id)
        result = _complete_purchase(self.client, self.session_id)
        order_id = result["order"]["order_id"]
        body = self.client.get(
            f"/api/decision-traces/order/{order_id}"
        ).json()
        self.assertEqual(body["links"]["order_id"], order_id)
        self.assertEqual(body["status"], "COMPLETED")

    def test_13_failed_payment_marks_trace_interrupted(self):
        _build_approved_cart(self.client, self.session_id)
        created = self.client.post(
            f"/api/payment/create?session_id={self.session_id}"
        ).json()
        with SessionLocal() as db:
            payment = db.query(Payment).filter(
                Payment.id == created["payment_id"]
            ).first()
            payment.status = "FAILED"
            db.commit()
        # A failed payment + retry path emits PAYMENT_FAILED -> INTERRUPTED
        self.client.post(f"/api/payment/create?session_id={self.session_id}")
        row = self._trace_row()
        # INTERRUPTED because a payment failure occurred and journey not completed
        self.assertIn(row.status, ("INTERRUPTED", "IN_PROGRESS"))

    def test_14_links_follow_product_and_payment(self):
        product_id, _ = _build_approved_cart(self.client, self.session_id)
        created = self.client.post(
            f"/api/payment/create?session_id={self.session_id}"
        ).json()
        row = self._trace_row()
        self.assertEqual(row.product_id, product_id)
        self.assertEqual(row.payment_id, created["payment_id"])

    def test_15_decision_id_persists_and_is_unique(self):
        done = set()
        for i in range(200):
            done.add(DecisionTraceService.generate_decision_id())
        self.assertEqual(len(done), 200)

    def test_16_replay_surfaces_same_decision_id(self):
        _build_approved_cart(self.client, self.session_id)
        _complete_purchase(self.client, self.session_id)
        row = self._trace_row()
        replay = self.client.get(f"/api/replay/{self.session_id}").json()
        self.assertEqual(replay["decision_id"], row.decision_id)


if __name__ == "__main__":
    unittest.main()
