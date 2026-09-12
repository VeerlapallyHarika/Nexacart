import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from main import app
from database import SessionLocal, Base, engine
from models.product import Product
from models.buyer_agent_run import BuyerAgentRun
from models.event import AuditEvent
from seed.seed_products import seed_products
from services.contract_service import ContractService


class TestBuyerAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = "test_buyer_session"
        self.db = SessionLocal()
        seed_products(self.db)
        # Clean any prior contract / runs for this session so each test is isolated.
        self.db.query(BuyerAgentRun).filter(
            BuyerAgentRun.session_id == self.session_id
        ).delete()
        from models.contract import CommerceContract

        self.db.query(CommerceContract).filter(
            CommerceContract.session_id == self.session_id
        ).delete()
        self.db.query(AuditEvent).filter(
            AuditEvent.session_id == self.session_id
        ).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(BuyerAgentRun).filter(
            BuyerAgentRun.session_id == self.session_id
        ).delete()
        self.db.commit()
        self.db.close()

    def _activate_contract(self, max_budget=None, **extra):
        payload = {"goal": "test", "status": "ACTIVE", **extra}
        if max_budget is not None:
            payload["max_budget"] = max_budget
        ContractService.upsert_contract_from_payload(
            self.db, self.session_id, payload
        )

    def test_ready_for_approval(self):
        """A compliant goal stops at recommendation_ready, and explicit approval completes to ready_for_approval."""
        # Step 1: Initial evaluation run (recommendation only, cart untouched)
        resp1 = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy wireless earbuds under Rs 5000 with noise cancellation",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        rec_data = resp1.json()
        self.assertEqual(rec_data["final_state"], "recommendation_ready")
        self.assertIsNotNone(rec_data["recommended_product_id"])
        self.assertIsNone(rec_data["added_product_id"])

        # Step 2: Explicit human approval executes contract check & cart addition
        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy wireless earbuds under Rs 5000 with noise cancellation",
                "session_id": self.session_id,
                "approve_product_id": rec_data["recommended_product_id"],
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_state"], "ready_for_approval")
        self.assertIsNotNone(data["added_product_id"])
        self.assertGreater(len(data["actions"]), 0)

        for a in data["actions"]:
            self.assertIn("step", a)
            self.assertIn("action", a)
            self.assertIn("input", a)
            self.assertIn("output", a)
            self.assertIn("timestamp", a)

    def test_replay_shows_connected_agent_journey(self):
        """The purchase replay surfaces the AI Buyer Agent's orchestration."""
        from services.replay_service import ReplayService

        resp1 = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy wireless earbuds under Rs 5000 with noise cancellation",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        rec_data = resp1.json()

        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy wireless earbuds under Rs 5000 with noise cancellation",
                "session_id": self.session_id,
                "approve_product_id": rec_data["recommended_product_id"],
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)

        self.db.expire_all()
        replay = ReplayService.get_purchase_replay(self.db, self.session_id)
        step_types = [s["type"] for s in replay["steps"]]

        self.assertIn("AGENT_GOAL", step_types)
        self.assertIn("AGENT_RECOMMENDATION", step_types)
        self.assertLess(step_types.index("AGENT_GOAL"), step_types.index("AGENT_RECOMMENDATION"))

        goal_step = next(s for s in replay["steps"] if s["type"] == "AGENT_GOAL")
        self.assertEqual(goal_step["status"], "SUCCESS")
        self.assertIn("earbuds", goal_step["description"].lower())
        rec_step = next(s for s in replay["steps"] if s["type"] == "AGENT_RECOMMENDATION")
        self.assertIn("recommended", rec_step["description"].lower())

        self.assertIn("CART_ADD", step_types)
        self.assertLess(
            step_types.index("AGENT_RECOMMENDATION"), step_types.index("CART_ADD")
        )

    def test_replay_is_not_duplicated_for_agent_runs(self):
        """The agent run writes into the SAME audit_events backbone as human chat."""
        from services.replay_service import ReplayService

        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "I want smartphone under 50000",
                "session_id": self.session_id,
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.db.expire_all()
        replay = ReplayService.get_purchase_replay(self.db, self.session_id)
        types = [s["type"] for s in replay["steps"]]
        steps_n = [s["step"] for s in replay["steps"]]
        self.assertEqual(steps_n, list(range(1, len(steps_n) + 1)))

    def test_blocked_by_contract(self):
        """max_budget=8000 must block add_to_cart of a >budget product upon approval."""
        self._activate_contract(max_budget=8000)
        resp1 = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy the Sony WH-1000XM4 headphones",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        rec_data = resp1.json()
        self.assertEqual(rec_data["final_state"], "recommendation_ready")
        self.assertIsNone(rec_data["added_product_id"])

        # Upon user approval, ContractValidator runs and rejects the product
        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy the Sony WH-1000XM4 headphones",
                "session_id": self.session_id,
                "approve_product_id": rec_data["recommended_product_id"],
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_state"], "blocked_by_contract")
        self.assertIsNone(data["added_product_id"])

        add_action = next(a for a in data["actions"] if a["action"] == "add_to_cart")
        violations = add_action["output"].get("violations", [])
        rules = [v["rule"] for v in violations]
        self.assertIn("MAX_BUDGET", rules)

        violation_events = [
            e
            for e in self.db.query(AuditEvent).filter(
                AuditEvent.session_id == self.session_id
            ).all()
            if e.event_type == "CONTRACT_VIOLATION"
            and (e.data or {}).get("source") == "buyer_agent"
            and (e.data or {}).get("run_id") == data["run_id"]
        ]
        self.assertEqual(len(violation_events), 1)
        self.assertEqual(violation_events[0].data.get("action"), "add_to_cart")

        rejected = [
            e
            for e in self.db.query(AuditEvent).filter(
                AuditEvent.session_id == self.session_id
            ).all()
            if e.event_type == "PRODUCT_REJECTED_BY_CONTRACT"
            and (e.data or {}).get("run_id") == data["run_id"]
        ]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].data.get("product_name"), "Sony WH-1000XM4")

        self.assertIsNotNone(data["reason"])
        self.assertIn("budget", data["reason"].lower())

    def test_max_steps_reached(self):
        """A tiny step cap stops the loop with max_steps_reached."""
        from services.buyer_agent import BuyerAgent

        result = BuyerAgent().run(
            self.db, "Buy wireless earbuds under Rs 5000", self.session_id, max_steps=1, auto_approve=True
        )
        self.assertEqual(result["final_state"], "max_steps_reached")
        self.assertEqual(len(result["actions"]), 1)

    def test_never_requests_approval_or_payment(self):
        """The buyer agent must never call request_checkout_approval/payment itself."""
        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "Buy wireless earbuds under Rs 5000 with noise cancellation",
                "session_id": self.session_id,
                "auto_approve": True,
            },
        )
        data = resp.json()
        actions = {a["action"] for a in data["actions"]}
        self.assertNotIn("request_checkout_approval", actions)
        self.assertNotIn("initiate_payment", actions)

    def test_smartphone_goal_succeeds(self):
        """The demo goal 'I want smartphone under 50000' succeeds after approval."""
        resp1 = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "I want smartphone under 50000",
                "session_id": self.session_id,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        rec_data = resp1.json()

        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "I want smartphone under 50000",
                "session_id": self.session_id,
                "approve_product_id": rec_data["recommended_product_id"],
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_state"], "ready_for_approval")
        self.assertIsNotNone(data["added_product_id"])

        product = self.db.query(Product).filter(
            Product.id == data["added_product_id"]
        ).first()
        self.assertIsNotNone(product)
        self.assertEqual(product.category, "smartphones")
        self.assertLessEqual(product.price, 50000)

    def test_budget_constraint_enforced_on_add(self):
        """The natural-language goal's budget must be a hard code-level check."""
        from services.cart_service import CartService

        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "buy phones under 10000",
                "session_id": self.session_id,
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_state"], "ready_for_approval")
        self.assertIsNotNone(data["added_product_id"])

        added = self.db.query(Product).filter(
            Product.id == data["added_product_id"]
        ).first()
        self.assertIsNotNone(added)
        self.assertLessEqual(added.price, 10000)
        self.assertEqual(added.category, "smartphones")

        cart = CartService.get_cart(self.db, self.session_id)
        self.assertIsNotNone(cart)
        for item in cart.items:
            self.assertLessEqual(item.product.price, 10000)

    def test_cart_reset_between_runs(self):
        """A new Buyer Agent run must start from a clean, isolated cart."""
        from services.cart_service import CartService

        CartService.clear_cart(self.db, self.session_id)
        CartService.add_to_cart(self.db, self.session_id, "sony-wh-1000xm4", 1)

        resp = self.client.post(
            "/buyer-agent/run",
            json={
                "goal": "I want smartphone under 50000",
                "session_id": self.session_id,
                "auto_approve": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["final_state"], "ready_for_approval")

        self.db.expire_all()
        cart = CartService.get_cart(self.db, self.session_id)
        self.assertIsNotNone(cart)
        cart_ids = [i.product_id for i in cart.items]
        self.assertNotIn("sony-wh-1000xm4", cart_ids)
        self.assertIn(data["added_product_id"], cart_ids)
        self.assertEqual(len(cart_ids), 1)

    def test_no_matching_products_when_search_empty(self):
        """When search_products returns zero results, the run must terminate with no_matching_products."""
        from unittest import mock
        from services.buyer_agent import BuyerAgent

        with mock.patch(
            "agents.cart_agent.CartAgent._search_products",
            return_value={"products": [], "match_type": "no_results", "explanation": "none"},
        ):
            result = BuyerAgent().run(
                self.db, "smartphone under 50000", self.session_id, auto_approve=True
            )
        self.assertEqual(result["final_state"], "no_matching_products")
        self.assertIsNone(result.get("added_product_id"))
        self.assertIn("No smartphones", result["reason"])
        actions = [a["action"] for a in result["actions"]]
        self.assertNotIn("add_to_cart", actions)

    def test_unexpected_exception_returns_error_state(self):
        """An unexpected exception inside the run loop returns a clean error state."""
        from unittest import mock
        from services.buyer_agent import BuyerAgent

        def boom(*args, **kwargs):
            raise RuntimeError("kaboom")

        with mock.patch(
            "agents.cart_agent.CartAgent._search_products", side_effect=boom
        ):
            result = BuyerAgent().run(
                self.db, "I want smartphone under 50000", self.session_id
            )
        self.assertEqual(result["final_state"], "error")
        self.assertIn("kaboom", result["reason"])


if __name__ == "__main__":
    unittest.main()
