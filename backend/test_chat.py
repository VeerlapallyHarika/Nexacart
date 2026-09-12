import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine
from seed.seed_products import seed_products
from services.cart_service import CartService


class ChatIntentRoutingTest(unittest.TestCase):
    """Regression tests for deterministic chat intent routing.

    Covers two routing bugs:
      1. "compare <X> and <Y>" with 2+ named products must call compare_products
         with matches for each named product (not a single keyword search).
      2. "view cart" phrasing must call view_cart and show actual cart contents
         instead of falling through to a broad catalog search.

    The agent LLM path is stubbed out so the deterministic rule-based path is
    always exercised, independent of (and without hitting the rate limit of) an
    external LLM.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        # Force the deterministic path: make the LLM agent handler always throw,
        # so the chat route falls back to the rule-based handlers (which now
        # include deterministic view-cart / compare routing).
        cls._agent_patch = mock.patch(
            "routes.chat._handle_with_agent",
            side_effect=RuntimeError("LLM stubbed out for deterministic test"),
        )
        cls._agent_patch.start()
        cls.addClassCleanup(cls._agent_patch.stop)

    def setUp(self):
        self.db = SessionLocal()
        seed_products(self.db)
        self.session_id = "test_chat_routing"

    def tearDown(self):
        CartService.clear_cart(self.db, self.session_id)
        self.db.close()

    def _chat(self, message, session_id=None):
        return self.client.post(
            "/api/chat",
            json={
                "message": message,
                "session_id": session_id or self.session_id,
            },
        )

    # ── Bug 1: compare X and Y ─────────────────────────────────────────

    def test_compare_two_named_products(self):
        """'compare Dell Inspiron 15 and hp pavilion 15' must return a comparison
        of BOTH named products, not a single-product keyword search."""
        resp = self._chat("compare Dell Inspiron 15 and hp pavilion 15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        names = [p["name"] for p in (data["products"] or [])]
        self.assertEqual(
            sorted(names),
            sorted(["Dell Inspiron 15", "HP Pavilion 15"]),
        )
        self.assertIn("Dell Inspiron 15", data["message"])
        self.assertIn("HP Pavilion 15", data["message"])

        # The catalog has many products; if this were a generic search it would
        # return lots of results. A comparison returns exactly the two named items.
        self.assertEqual(len(data["products"]), 2)

    def test_compare_with_vs_separator(self):
        """'vs' separator must route to compare_products too."""
        resp = self._chat("compare Dell Inspiron 15 vs hp pavilion 15")
        data = resp.json()
        names = {p["name"] for p in (data["products"] or [])}
        self.assertIn("Dell Inspiron 15", names)
        self.assertIn("HP Pavilion 15", names)

    def test_compare_three_named_products(self):
        """Three named products requested -> all three compared."""
        resp = self._chat(
            "compare Dell Inspiron 15, hp pavilion 15 and macbook air m2"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = {p["name"] for p in (data["products"] or [])}
        self.assertIn("Dell Inspiron 15", names)
        self.assertIn("HP Pavilion 15", names)
        self.assertTrue(
            any("MacBook Air" in name for name in names),
            f"expected a MacBook Air in comparison, got {names}",
        )
        self.assertEqual(len(data["products"]), 3)

    def test_compare_not_triggered_for_single_named_product(self):
        """A single named product (no comparison) must NOT be routed to compare."""
        resp = self._chat("show me the Dell Inspiron 15")
        data = resp.json()
        self.assertEqual(resp.status_code, 200)
        # A search-based reply, not a comparison.
        self.assertNotIn("Here is a comparison", data["message"])
        self.assertNotIn("Best value:", data["message"])

    # ── Bug 2: view cart ───────────────────────────────────────────────

    def test_view_cart_empty(self):
        """'view cart' with an empty cart returns the empty-cart message, NOT a
        catalog search like 'I found N products'."""
        resp = self._chat("view cart")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("empty", data["message"].lower())
        self.assertNotIn("found", data["message"].lower())
        self.assertEqual(data["products"] or [], [])

    def test_view_cart_shows_actual_contents(self):
        """'view cart' with items in the cart shows the actual cart contents."""
        CartService.clear_cart(self.db, self.session_id)
        CartService.add_to_cart(self.db, self.session_id, "dell-inspiron-15", 1)
        CartService.add_to_cart(self.db, self.session_id, "redmi-9a", 2)

        resp = self._chat("view cart")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("Dell Inspiron 15", data["message"])
        self.assertIn("Redmi 9A", data["message"])
        self.assertIn("Total", data["message"])

        ids = [p["id"] for p in (data["products"] or [])]
        self.assertIn("dell-inspiron-15", ids)
        self.assertIn("redmi-9a", ids)

    def test_view_cart_phrasing_variants(self):
        """Several wordings of the cart intent must all route to view_cart."""
        for msg in ["view cart", "show my cart", "see my cart", "what's in my cart"]:
            resp = self._chat(msg)
            data = resp.json()
            self.assertIn("empty", data["message"].lower())
            self.assertNotIn("found", data["message"].lower())


if __name__ == "__main__":
    unittest.main()
