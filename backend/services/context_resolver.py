import re
from typing import Optional, Dict, List, Any


class ContextResolver:
    """Resolves product references like 'it', 'cheaper one', 'better battery'."""

    def __init__(self, products: List[Dict[str, Any]], selected_product_id: Optional[str] = None):
        self.products = {p["id"]: p for p in products}
        self.selected_product_id = selected_product_id

    def resolve(self, message: str) -> Optional[str]:
        msg = message.lower().strip()

        if re.match(r'^(add|buy|get|put|cart)\s+(it|that|this|one|them)\b', msg):
            return self.selected_product_id

        if re.match(r'^(show|view|details?|more)\s+(info|details?|about)?\s*(of|for|on)?\s*(it|that|this|one)\b', msg):
            return self.selected_product_id

        if 'cheaper' in msg or 'less expensive' in msg or 'lower price' in msg:
            return self._pick_cheapest()

        if 'expensive' in msg or 'pricier' in msg or 'premium' in msg:
            return self._pick_most_expensive()

        if 'better battery' in msg or 'longer battery' in msg or 'best battery' in msg:
            return self._pick_best_battery()

        if 'lighter' in msg or 'lightest' in msg:
            return self._pick_lightest()

        if 'first one' in msg or '1st one' in msg or 'first option' in msg:
            return self._pick_by_position(0)

        if 'second one' in msg or '2nd one' in msg or 'second option' in msg:
            return self._pick_by_position(1)

        if 'third one' in msg or '3rd one' in msg or 'third option' in msg:
            return self._pick_by_position(2)

        return None

    def _pick_cheapest(self) -> Optional[str]:
        if not self.products:
            return None
        cheapest = min(self.products.values(), key=lambda p: p.get("price", float("inf")))
        return cheapest["id"]

    def _pick_most_expensive(self) -> Optional[str]:
        if not self.products:
            return None
        expensive = max(self.products.values(), key=lambda p: p.get("price", 0))
        return expensive["id"]

    def _pick_best_battery(self) -> Optional[str]:
        best_id = None
        best_battery = -1
        for p in self.products.values():
            attrs = p.get("attributes", {})
            battery = attrs.get("battery_life", 0) or 0
            if battery > best_battery:
                best_battery = battery
                best_id = p["id"]
        return best_id

    def _pick_lightest(self) -> Optional[str]:
        if not self.products:
            return None
        lightest = min(self.products.values(), key=lambda p: p.get("attributes", {}).get("weight", float("inf")))
        return lightest["id"]

    def _pick_by_position(self, index: int) -> Optional[str]:
        ids = list(self.products.keys())
        if index < len(ids):
            return ids[index]
        return None

    def resolve_product_name(self, message: str) -> Optional[str]:
        """Return the product name of a resolved reference, for display."""
        product_id = self.resolve(message)
        if product_id and product_id in self.products:
            return self.products[product_id]["name"]
        return None
