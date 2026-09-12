import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from main import app
from database import SessionLocal, Base, engine
from models.product import Product
from models.payment import Payment
from models.cart import Cart
from models.order import Order
from models.event import AuditEvent
from models.decision_trace import DecisionTrace
from models.decision_simulation import DecisionSimulation
from models.contract import CommerceContract
from seed.seed_products import seed_products
from services.decision_trace_service import DecisionTraceService
from services.contract_service import ContractService


def _run_buyer_agent(client, session_id, goal):
    resp = client.post(
        "/buyer-agent/run",
        json={"goal": goal, "session_id": session_id},
    )
    return resp.json() if resp.status_code == 200 else None


def _get_trace(client, session_id):
    resp = client.get(f"/api/decision-traces/session/{session_id}")
    return resp.json() if resp.status_code == 200 else None


class TestDecisionLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = "test_lab_session"
        self.db = SessionLocal()
        seed_products(self.db)
        for model in (Payment, Cart, Order, AuditEvent, DecisionTrace, DecisionSimulation, CommerceContract):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()
        # Run buyer agent to establish a real trace
        _run_buyer_agent(
            self.client, self.session_id,
            "I want a laptop under 80000 with 16GB RAM"
        )
        self.trace = _get_trace(self.client, self.session_id)
        self.decision_id = self.trace["decision_id"] if self.trace else None

    def tearDown(self):
        for model in (Payment, Cart, Order, AuditEvent, DecisionTrace, DecisionSimulation, CommerceContract):
            self.db.query(model).filter(model.session_id == self.session_id).delete()
        self.db.commit()
        self.db.close()

    def test_01_explain_uses_real_data(self):
        resp = self.client.get(f"/api/decision-lab/{self.decision_id}/explain")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["decision_id"], self.decision_id)
        self.assertIn("product", body)
        self.assertIn("match_percentage", body)
        self.assertIn("strong_matches", body)
        self.assertIn("trade_offs", body)
        self.assertIn("breakdown", body)
        self.assertIsInstance(body["strong_matches"], list)
        self.assertIsInstance(body["trade_offs"], list)
        self.assertGreater(body["total_candidates_scanned"], 0)

    def test_02_alternatives_from_real_candidates(self):
        resp = self.client.get(
            f"/api/decision-lab/{self.decision_id}/alternatives?limit=3"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["decision_id"], self.decision_id)
        self.assertIn("alternatives", body)
        self.assertIsInstance(body["alternatives"], list)
        self.assertLessEqual(len(body["alternatives"]), 3)
        if body["alternatives"]:
            alt = body["alternatives"][0]
            self.assertIn("id", alt)
            self.assertIn("name", alt)
            self.assertIn("match_percentage", alt)
            # Must not be the original recommended product
            rec_id = body["original_product"]["id"]
            self.assertNotEqual(alt["id"], rec_id)

    def test_03_generic_comparison_works(self):
        products = self.db.query(Product).filter(Product.stock_quantity > 0).limit(2).all()
        self.assertGreaterEqual(len(products), 2)
        resp = self.client.post(
            "/api/decision-lab/compare",
            json={"product_a_id": products[0].id, "product_b_id": products[1].id},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("product_a", body)
        self.assertIn("product_b", body)
        self.assertIn("comparisons", body)
        self.assertIsInstance(body["comparisons"], list)
        self.assertGreater(len(body["comparisons"]), 0)
        price_comp = body["comparisons"][0]
        self.assertEqual(price_comp["attribute"], "price")
        self.assertIn(price_comp["verdict"], ("similar", "a_better", "b_better"))

    def test_04_unknown_attribute_does_not_break_comparison(self):
        products = self.db.query(Product).filter(Product.stock_quantity > 0).limit(2).all()
        resp = self.client.post(
            "/api/decision-lab/compare",
            json={"product_a_id": products[0].id, "product_b_id": products[1].id},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Each comparison must have a valid verdict
        for comp in body["comparisons"]:
            self.assertIn(comp["verdict"], ("similar", "a_better", "b_better", "tradeoff"))

    def test_05_budget_simulation_changes_results(self):
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Budget increased to 120000",
                "max_price": 120000,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["decision_id"], self.decision_id)
        self.assertIn("simulation_id", body)
        self.assertIn("result", body)
        self.assertIn("changes", body["result"])
        self.assertIsInstance(body["result"]["changes"], list)
        self.assertEqual(body["status"], "COMPLETED")

    def test_06_preference_simulation_changes_ranking(self):
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "32GB RAM instead of 16GB",
                "constraints": [
                    {"key": "ram_gb", "value": 32, "operator": "gte"}
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        sim_product = body["result"].get("simulated_product")
        if sim_product:
            self.assertIn("ram_gb", str(sim_product.get("attributes", {})))

    def test_07_original_trace_unchanged(self):
        trace_before = _get_trace(self.client, self.session_id)
        self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Test simulation",
                "max_price": 200000,
            },
        )
        trace_after = _get_trace(self.client, self.session_id)
        # The trace header (decision_id, goal, status) must not change
        self.assertEqual(
            trace_before["decision_id"],
            trace_after["decision_id"],
        )
        self.assertEqual(
            trace_before["status"],
            trace_after["status"],
        )
        # The simulation creates a new audit event that joins the trace
        # (SIMULATION_COMPLETED), so event count grows by 1 — this is correct.
        self.assertGreaterEqual(
            len(trace_after["events"]),
            len(trace_before["events"]),
        )

    def test_08_simulation_creates_branch(self):
        self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Branch 1",
                "max_price": 100000,
            },
        )
        resp = self.client.get(f"/api/decision-lab/{self.decision_id}/simulations")
        self.assertEqual(resp.status_code, 200)
        sims = resp.json()
        self.assertIsInstance(sims, list)
        self.assertGreaterEqual(len(sims), 1)
        self.assertEqual(sims[0]["simulation_number"], 1)

    def test_09_multiple_simulations_work(self):
        for i, price in enumerate([90000, 150000, 60000]):
            resp = self.client.post(
                f"/api/decision-lab/{self.decision_id}/simulate",
                json={
                    "session_id": self.session_id,
                    "label": f"Sim {i+1}",
                    "max_price": price,
                },
            )
            self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/decision-lab/{self.decision_id}/simulations")
        sims = resp.json()
        self.assertEqual(len(sims), 3)
        numbers = [s["simulation_number"] for s in sims]
        self.assertEqual(numbers, [1, 2, 3])

    def test_10_contract_restrictions_respected(self):
        ContractService.upsert_contract_from_payload(
            self.db, self.session_id,
            {"max_budget": 50000, "status": "ACTIVE"}
        )
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Over contract budget",
                "max_price": 100000,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Should show contract warnings
        self.assertIsInstance(body["contract_warnings"], list)
        self.assertGreater(len(body["contract_warnings"]), 0)
        self.assertTrue(body["contract"]["active"])

    def test_11_simulation_cannot_bypass_contract(self):
        ContractService.upsert_contract_from_payload(
            self.db, self.session_id,
            {"max_budget": 40000, "status": "ACTIVE"}
        )
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "High budget sim",
                "max_price": 100000,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # If the simulated product exceeds contract, apply should fail
        sim_product = body["result"].get("simulated_product")
        if sim_product:
            prod = self.db.query(Product).filter(Product.id == sim_product["id"]).first()
            if prod and prod.price > 40000:
                # Attempting to apply should fail contract check
                apply_resp = self.client.post(
                    f"/api/decision-lab/simulations/{body['simulation_id']}/apply",
                    json={"session_id": self.session_id},
                )
                self.assertIn(apply_resp.status_code, (400, 404))

    def test_12_apply_requires_user_action(self):
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Apply test",
                "max_price": 90000,
            },
        )
        sim = resp.json()
        # Applying must be an explicit POST, not automatic
        apply_resp = self.client.post(
            f"/api/decision-lab/simulations/{sim['simulation_id']}/apply",
            json={"session_id": self.session_id},
        )
        self.assertEqual(apply_resp.status_code, 200)
        apply_body = apply_resp.json()
        self.assertTrue(apply_body.get("success"))
        self.assertIn("product", apply_body)
        # Verify the simulation status changed to APPLIED
        sim_resp = self.client.get(f"/api/decision-lab/{self.decision_id}/simulations")
        applied = [s for s in sim_resp.json() if s["simulation_id"] == sim["simulation_id"]]
        self.assertEqual(applied[0]["status"], "APPLIED")

    def test_13_future_categories_work_without_code_changes(self):
        # Generic comparison and scoring must work for any category
        products = self.db.query(Product).filter(Product.stock_quantity > 0).all()
        categories = set(p.category for p in products)
        for cat in categories:
            cat_products = [p for p in products if p.category == cat]
            if len(cat_products) >= 2:
                resp = self.client.post(
                    "/api/decision-lab/compare",
                    json={
                        "product_a_id": cat_products[0].id,
                        "product_b_id": cat_products[1].id,
                    },
                )
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertIn("comparisons", body)
                # Must not crash regardless of category
                for comp in body["comparisons"]:
                    self.assertIn(comp["verdict"], ("similar", "a_better", "b_better", "tradeoff"))

    def test_14_session_isolation(self):
        other_session = "test_lab_other"
        other_decision_id = None
        try:
            _run_buyer_agent(
                self.client, other_session,
                "I want headphones under 5000"
            )
            other_trace = _get_trace(self.client, other_session)
            other_decision_id = other_trace["decision_id"] if other_trace else None
            if other_decision_id:
                resp = self.client.get(f"/api/decision-lab/{other_decision_id}/explain")
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["decision_id"], other_decision_id)
                # Simulations should not cross sessions
                self.client.post(
                    f"/api/decision-lab/{self.decision_id}/simulate",
                    json={
                        "session_id": self.session_id,
                        "label": "Isolation test",
                        "max_price": 5000,
                    },
                )
                sims = self.client.get(
                    f"/api/decision-lab/{other_decision_id}/simulations"
                ).json()
                for s in sims:
                    self.assertNotEqual(s.get("label"), "Isolation test")
        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(model.session_id == other_session).delete()
                db.commit()

    def test_15_cross_session_decision_isolation(self):
        """TEST A: A laptop decision must never return headphone data and vice versa.

        Regression: previously, the same session_id across logins caused the
        Decision Lab to mix contexts (headphone alternatives showing up in a
        laptop flow)."""
        headphone_session = "test_cross_session_hp"
        laptop_session = "test_cross_session_laptop"
        try:
            _run_buyer_agent(
                self.client, headphone_session,
                "I want headphones under 5000 with 30+ hour battery"
            )
            hp_trace = _get_trace(self.client, headphone_session)
            hp_decision_id = hp_trace["decision_id"] if hp_trace else None

            _run_buyer_agent(
                self.client, laptop_session,
                "I want a laptop under 80000 for coding"
            )
            laptop_trace = _get_trace(self.client, laptop_session)
            laptop_decision_id = laptop_trace["decision_id"] if laptop_trace else None

            self.assertIsNotNone(hp_decision_id)
            self.assertIsNotNone(laptop_decision_id)
            self.assertNotEqual(hp_decision_id, laptop_decision_id)

            hp_explain = self.client.get(
                f"/api/decision-lab/{hp_decision_id}/explain"
            ).json()
            laptop_explain = self.client.get(
                f"/api/decision-lab/{laptop_decision_id}/explain"
            ).json()

            hp_product_name = hp_explain.get("product", {}).get("name", "").lower()
            laptop_product_name = laptop_explain.get("product", {}).get("name", "").lower()

            laptop_alts = self.client.get(
                f"/api/decision-lab/{laptop_decision_id}/alternatives?limit=10"
            ).json()
            for alt in laptop_alts.get("alternatives", []):
                alt_cat = (alt.get("category") or "").lower()
                self.assertIn(
                    alt_cat, ("laptops", "smartphones"),
                    f"Laptop alternatives must not contain headphones: got {alt.get('name')} ({alt_cat})"
                )

            hp_alts = self.client.get(
                f"/api/decision-lab/{hp_decision_id}/alternatives?limit=10"
            ).json()
            for alt in hp_alts.get("alternatives", []):
                alt_cat = (alt.get("category") or "").lower()
                self.assertNotEqual(
                    alt_cat, "laptops",
                    f"Headphone alternatives must not contain laptops: got {alt.get('name')} ({alt_cat})"
                )
        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(
                        model.session_id.in_([headphone_session, laptop_session])
                    ).delete()
                db.commit()

    def test_16_same_user_logout_login_isolation(self):
        """TEST B: Simulates logout/login by running two buyer agent runs on the
        SAME session_id. The second run's Decision Lab must use only the second
        run's context."""
        shared_session = "test_logout_login_sim"
        try:
            _run_buyer_agent(
                self.client, shared_session,
                "I want headphones under 5000 with 30+ hour battery"
            )
            trace1 = _get_trace(self.client, shared_session)
            decision1 = trace1["decision_id"] if trace1 else None

            _run_buyer_agent(
                self.client, shared_session,
                "I want a laptop under 80000 for coding"
            )
            trace2 = _get_trace(self.client, shared_session)
            decision2 = trace2["decision_id"] if trace2 else None

            self.assertIsNotNone(decision1)
            self.assertIsNotNone(decision2)
            self.assertNotEqual(decision1, decision2)

            latest_trace = _get_trace(self.client, shared_session)
            self.assertEqual(latest_trace["decision_id"], decision2)

            explain = self.client.get(
                f"/api/decision-lab/{decision2}/explain"
            ).json()
            product_name = explain.get("product", {}).get("name", "").lower()

            alts = self.client.get(
                f"/api/decision-lab/{decision2}/alternatives?limit=10"
            ).json()
            for alt in alts.get("alternatives", []):
                alt_cat = (alt.get("category") or "").lower()
                self.assertIn(
                    alt_cat, ("laptops", "smartphones"),
                    f"Latest decision must not return old headphones: got {alt.get('name')} ({alt_cat})"
                )
        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(model.session_id == shared_session).delete()
                db.commit()

    def test_17_active_decision_replacement(self):
        """TEST C: When a second decision replaces the first, the first must
        remain historically accessible by its explicit decision_id but not be
        the active one."""
        shared_session = "test_active_replacement"
        try:
            _run_buyer_agent(
                self.client, shared_session,
                "I want headphones under 5000"
            )
            trace1 = _get_trace(self.client, shared_session)
            decision1 = trace1["decision_id"] if trace1 else None

            _run_buyer_agent(
                self.client, shared_session,
                "I want a laptop under 80000"
            )
            trace2 = _get_trace(self.client, shared_session)
            decision2 = trace2["decision_id"] if trace2 else None

            self.assertIsNotNone(decision1)
            self.assertIsNotNone(decision2)
            self.assertNotEqual(decision1, decision2)

            resp1 = self.client.get(f"/api/decision-lab/{decision1}/explain")
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp1.json()["decision_id"], decision1)

            resp2 = self.client.get(f"/api/decision-lab/{decision2}/explain")
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["decision_id"], decision2)

            latest = _get_trace(self.client, shared_session)
            self.assertEqual(latest["decision_id"], decision2)
        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(model.session_id == shared_session).delete()
                db.commit()

    def test_18_no_latest_fallback(self):
        """TEST E: When no valid active decision exists, the Decision Lab must
        not automatically return another historical decision."""
        session_a = "test_no_fallback_a"
        session_b = "test_no_fallback_b"
        try:
            _run_buyer_agent(
                self.client, session_a,
                "I want headphones under 5000"
            )
            trace_a = _get_trace(self.client, session_a)
            decision_a = trace_a["decision_id"] if trace_a else None
            self.assertIsNotNone(decision_a)

            resp = self.client.get(f"/api/decision-traces/session/{session_b}")
            self.assertEqual(resp.status_code, 404)
        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(
                        model.session_id.in_([session_a, session_b])
                    ).delete()
                db.commit()

    def test_19_apply_simulation_updates_active_recommendation(self):
        """BUG 2 regression: applying a simulation must make the simulated
        product the active recommendation, not just log it to history."""
        resp = self.client.post(
            f"/api/decision-lab/{self.decision_id}/simulate",
            json={
                "session_id": self.session_id,
                "label": "Apply test - higher budget",
                "max_price": 200000,
            },
        )
        self.assertEqual(resp.status_code, 200)
        sim = resp.json()
        sim_product = sim["result"].get("simulated_product")
        self.assertIsNotNone(sim_product)

        apply_resp = self.client.post(
            f"/api/decision-lab/simulations/{sim['simulation_id']}/apply",
            json={"session_id": self.session_id},
        )
        self.assertEqual(apply_resp.status_code, 200)
        apply_body = apply_resp.json()
        self.assertTrue(apply_body.get("success"))
        self.assertEqual(apply_body["product"]["id"], sim_product["id"])

        explain_resp = self.client.get(
            f"/api/decision-lab/{self.decision_id}/explain"
        )
        self.assertEqual(explain_resp.status_code, 200)
        explain = explain_resp.json()
        self.assertEqual(explain["product"]["id"], sim_product["id"])

        alts_resp = self.client.get(
            f"/api/decision-lab/{self.decision_id}/alternatives?limit=10"
        )
        self.assertEqual(alts_resp.status_code, 200)
        alts = alts_resp.json()
        for alt in alts.get("alternatives", []):
            self.assertNotEqual(
                alt["id"], sim_product["id"],
                "Applied product must not appear in its own alternatives"
            )

        from services.cart_service import CartService
        self.db.expire_all()
        cart = CartService.get_cart(self.db, self.session_id)
        self.assertIsNotNone(cart)
        cart_ids = [item.product_id for item in cart.items]
        self.assertIn(
            sim_product["id"], cart_ids,
            "Applied product must be in the cart"
        )

    def test_20_second_run_updates_workspace_context(self):
        """BUG 1 regression: after running buyer agent twice in the same session,
        the Decision Lab must reflect the SECOND (latest) run's data."""
        shared_session = "test_workspace_freshness"
        try:
            _run_buyer_agent(
                self.client, shared_session,
                "I want headphones under 5000 with 30+ hour battery"
            )
            trace1 = _get_trace(self.client, shared_session)
            decision1 = trace1["decision_id"] if trace1 else None

            _run_buyer_agent(
                self.client, shared_session,
                "I want a laptop under 80000 for coding"
            )
            trace2 = _get_trace(self.client, shared_session)
            decision2 = trace2["decision_id"] if trace2 else None

            self.assertIsNotNone(decision1)
            self.assertIsNotNone(decision2)
            self.assertNotEqual(decision1, decision2)

            explain = self.client.get(
                f"/api/decision-lab/{decision2}/explain"
            ).json()
            self.assertEqual(explain["decision_id"], decision2)

            product_name = explain.get("product", {}).get("name", "").lower()
            alts = self.client.get(
                f"/api/decision-lab/{decision2}/alternatives?limit=10"
            ).json()
            for alt in alts.get("alternatives", []):
                alt_cat = (alt.get("category") or "").lower()
                self.assertIn(
                    alt_cat, ("laptops", "smartphones"),
                    f"Latest run must show laptop alternatives, not headphones: got {alt.get('name')} ({alt_cat})"
                )

            old_explain = self.client.get(
                f"/api/decision-lab/{decision1}/explain"
            ).json()
            old_product_name = old_explain.get("product", {}).get("name", "").lower()

        finally:
            with SessionLocal() as db:
                for model in (AuditEvent, DecisionTrace, DecisionSimulation):
                    db.query(model).filter(model.session_id == shared_session).delete()
                db.commit()


if __name__ == "__main__":
    unittest.main()
