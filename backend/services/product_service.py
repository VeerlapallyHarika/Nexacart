from sqlalchemy.orm import Session
from models.product import Product
from typing import List, Optional, Dict, Any, Tuple
import re
import math
from services.category_matcher import match_category


class SearchConstraint:
    """A single attribute constraint extracted from user intent."""

    def __init__(
        self,
        key: str,
        value: Any = None,
        operator: str = "eq",
        raw_text: str = "",
    ):
        self.key = key
        self.value = value
        self.operator = operator  # eq, gte, lte, contains, approx
        self.raw_text = raw_text

    def __repr__(self):
        return f"Constraint({self.key} {self.operator} {self.value})"


class SearchResult:
    """Structured search result with explanation."""

    def __init__(
        self,
        products: List[Product],
        match_type: str = "exact",
        matched_constraints: List[str] = None,
        unmatched_constraints: List[str] = None,
        explanation: str = "",
        total_scanned: int = 0,
    ):
        self.products = products
        self.match_type = match_type
        self.matched_constraints = matched_constraints or []
        self.unmatched_constraints = unmatched_constraints or []
        self.explanation = explanation
        self.total_scanned = total_scanned


# ── Generic Attribute Aliases ──────────────────────────────────────────
# Maps common user phrasing to actual attribute keys in the product JSON.
# This is NOT category-specific — it maps generic concepts to attribute keys.
ATTRIBUTE_ALIASES = {
    # Numeric attributes — map aliases to (attribute_key, default_operator)
    "ram": ("ram_gb", "gte"),
    "ram_gb": ("ram_gb", "gte"),
    "storage": ("storage_gb", "gte"),
    "storage_gb": ("storage_gb", "gte"),
    "battery": ("battery_life_hours", "gte"),
    "battery_life": ("battery_life_hours", "gte"),
    "battery_life_hours": ("battery_life_hours", "gte"),
    "battery_mah": ("battery_mah", "gte"),
    "camera": ("camera_mp", "gte"),
    "camera_mp": ("camera_mp", "gte"),
    "mp": ("camera_mp", "gte"),
    "dpi": ("dpi", "gte"),
    "screen": ("screen_size_inches", "approx"),
    "screen_size": ("screen_size_inches", "approx"),
    "screen_size_inches": ("screen_size_inches", "approx"),
    "display": ("display_size_inches", "approx"),
    "display_size": ("display_size_inches", "approx"),
    "display_size_inches": ("display_size_inches", "approx"),
    "weight": ("weight_grams", "lte"),
    "weight_grams": ("weight_grams", "lte"),
    "weight_kg": ("weight_kg", "lte"),
    "bluetooth": ("bluetooth_version", "gte"),
    "bluetooth_version": ("bluetooth_version", "gte"),
    "refresh_rate": ("refresh_rate_hz", "gte"),
    "refresh_rate_hz": ("refresh_rate_hz", "gte"),
    "screen_size_inches_tv": ("screen_size_inches", "approx"),
    "resolution": ("resolution", "eq"),
    "processor": ("processor", "contains"),
    "gpu": ("gpu", "contains"),
    "switch_type": ("switch_type", "eq"),
    "sensor": ("sensor_type", "eq"),
    "sensor_mp": ("sensor_mp", "gte"),
    "iso_range": ("iso_range", "gte"),
    "autofocus_points": ("autofocus_points", "gte"),
    "weight_capacity_kg": ("weight_capacity_kg", "gte"),
    "power_output_watts": ("power_output_watts", "gte"),
    "hdmi_ports": ("hdmi_ports", "gte"),
    "buttons": ("buttons", "gte"),
    "battery_life_months": ("battery_life_months", "gte"),
    "battery_life_days": ("battery_life_days", "gte"),
}

# Boolean attribute aliases — map user phrasing to attribute key
BOOLEAN_ALIASES = {
    "wireless": "wireless",
    "noise_cancellation": "noise_cancellation",
    "anc": "noise_cancellation",
    "noise cancelling": "noise_cancellation",
    "active noise": "noise_cancellation",
    "noise canceling": "noise_cancellation",
    "smart_tv": "smart_tv",
    "smart tv": "smart_tv",
    "hdr": "hdr",
    "rgb": "rgb",
    "backlit": "rgb",
    "backlight": "rgb",
    "gaming": "gaming",
    "ergonomic": "ergonomic",
    "hot_swappable": "hot_swappable",
    "hot swappable": "hot_swappable",
    "water_resistant": "water_resistant",
    "waterproof": "water_resistant",
    "water resistant": "water_resistant",
    "gps": "gps",
    "nfc": "nfc",
    "heart_rate_monitor": "heart_rate_monitor",
    "heart rate": "heart_rate_monitor",
    "blood_oxygen_monitor": "blood_oxygen_monitor",
    "stylus_support": "stylus_support",
    "stylus": "stylus_support",
    "wifi": "wifi",
    "image_stabilization": "image_stabilization",
    "image stabilization": "image_stabilization",
    "microphone": "microphone",
    "5g": "5g",
}

# String attribute aliases
STRING_ALIASES = {
    "brand": "brand",
    "operating_system": "operating_system",
    "os": "operating_system",
    "type": "type",
    "connector": "connector",
    "display_type": "display_type",
}


class ProductService:
    @staticmethod
    def get_products(db: Session) -> List[Product]:
        return db.query(Product).all()

    @staticmethod
    def get_product(db: Session, product_id: str) -> Optional[Product]:
        return db.query(Product).filter(Product.id == product_id).first()

    @staticmethod
    def get_all_categories(db: Session) -> List[str]:
        """Return all distinct category values in the database."""
        rows = db.query(Product.category).distinct().all()
        return sorted([r[0] for r in rows])

    @staticmethod
    def get_category_sample_products(db: Session, category: str, limit: int = 3) -> List[Product]:
        """Return a few products from a category for context."""
        return (
            db.query(Product)
            .filter(Product.category == category)
            .limit(limit)
            .all()
        )

    @staticmethod
    def search_products(
        db: Session,
        query: Optional[str] = None,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
    ) -> List[Product]:
        stmt = db.query(Product)
        if query:
            stmt = stmt.filter(Product.name.ilike(f"%{query}%"))
        if category:
            stmt = stmt.filter(Product.category == category)
        if max_price:
            stmt = stmt.filter(Product.price <= max_price)
        return stmt.all()

    @staticmethod
    def search_with_intent(
        db: Session,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        min_battery_life: Optional[int] = None,
        noise_cancellation: Optional[bool] = None,
        limit: int = 3,
    ) -> List[Product]:
        """Legacy interface — kept for backward compatibility."""
        result = ProductService.generic_search(
            db=db,
            category=category,
            max_price=max_price,
            constraints=[
                SearchConstraint("battery_life_hours", min_battery_life, "gte")
                if min_battery_life
                else None,
                SearchConstraint("noise_cancellation", True, "eq")
                if noise_cancellation
                else None,
            ],
            limit=limit,
        )
        return result.products

    @staticmethod
    def generic_search(
        db: Session,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        brand: Optional[str] = None,
        constraints: Optional[List[SearchConstraint]] = None,
        query: Optional[str] = None,
        limit: int = 5,
    ) -> SearchResult:
        """Generic product discovery search with layered fallback.

        Layer 1: Exact match (all constraints satisfied)
        Layer 2: Partial match (relax lower-priority constraints)
        Layer 3: Category + budget only
        Layer 4: Closest category products
        Layer 5: No results with explanation
        """
        constraints = constraints or []
        all_products = db.query(Product).all()
        total_scanned = len(all_products)

        # ── Normalize category ──────────────────────────────────────
        normalized_category = ProductService._normalize_category(db, category)

        # ── Derive price bounds from free-text query ───────────────
        # Callers (notably the LLM agent) sometimes express a price floor or
        # ceiling inside the free-text `query` (e.g. "laptops above 70000")
        # instead of using the dedicated min_price/max_price arguments. If a
        # directional price phrase is present, fold it into the numeric bounds
        # so it is honoured as a real comparison rather than being dropped.
        min_price, max_price = ProductService._reconcile_price_bounds(
            query, min_price, max_price
        )
        clean_query = ProductService._strip_price_tokens(query)

        # ── Layer 1: Full match ─────────────────────────────────────
        candidates = all_products
        if normalized_category:
            candidates = [p for p in candidates if p.category == normalized_category]

        # Price floors/ceilings are hard constraints and must always apply.
        if min_price is not None:
            candidates = [p for p in candidates if p.price >= min_price]

        if max_price is not None:
            candidates = [p for p in candidates if p.price <= max_price]

        if brand:
            candidates = ProductService._filter_by_brand(candidates, brand)

        # Free-text query is a *soft* preference: it narrows results only when
        # it actually matches something. Otherwise we must not discard the
        # category/price-filtered candidates (which would wrongly fall through
        # to the "closest options" fallback).
        if clean_query:
            queried = ProductService._filter_by_query(candidates, clean_query)
            if queried:
                candidates = queried

        if constraints:
            matched, unmatched = ProductService._apply_constraints(candidates, constraints)
        else:
            matched = candidates
            unmatched = []

        if matched:
            ranked = ProductService._rank_products(matched, max_price, constraints)
            explanation = ProductService._build_explanation(
                normalized_category, max_price, constraints, matched, unmatched, "exact"
            )
            return SearchResult(
                products=ranked[:limit],
                match_type="exact",
                matched_constraints=[c.key for c in constraints if c not in unmatched],
                unmatched_constraints=[c.key for c in unmatched],
                explanation=explanation,
                total_scanned=total_scanned,
            )

        # ── Layer 2: Relax constraints, keep category + budget ──────
        if constraints and candidates:
            relaxed = ProductService._rank_products(candidates, max_price, [])
            if relaxed:
                explanation = ProductService._build_explanation(
                    normalized_category, max_price, constraints, [], constraints, "partial"
                )
                return SearchResult(
                    products=relaxed[:limit],
                    match_type="partial",
                    matched_constraints=[],
                    unmatched_constraints=[c.key for c in constraints],
                    explanation=explanation,
                    total_scanned=total_scanned,
                )

        # ── Layer 3: Category only, closest to budget ───────────────
        if normalized_category:
            cat_products = [p for p in all_products if p.category == normalized_category]
            if cat_products:
                ranked = ProductService._rank_products(cat_products, max_price, [])
                explanation = ProductService._build_explanation(
                    normalized_category, max_price, constraints, [], constraints, "budget_fallback"
                )
                return SearchResult(
                    products=ranked[:limit],
                    match_type="budget_fallback",
                    matched_constraints=["category"],
                    unmatched_constraints=[c.key for c in constraints]
                    + (["budget"] if max_price else []),
                    explanation=explanation,
                    total_scanned=total_scanned,
                )

        # ── Layer 4: No category match at all ───────────────────────
        if (max_price is not None or min_price is not None) and not normalized_category:
            budget_products = [
                p
                for p in all_products
                if (max_price is None or p.price <= max_price)
                and (min_price is None or p.price >= min_price)
            ]
            if budget_products:
                ranked = ProductService._rank_products(budget_products, max_price, [])
                explanation = (
                    f"I couldn't find a category matching "
                    f"{'\"' + category + '\"' if category else 'your request'} "
                    f"but here are products within your budget."
                )
                return SearchResult(
                    products=ranked[:limit],
                    match_type="category_fallback",
                    matched_constraints=[],
                    unmatched_constraints=["category"],
                    explanation=explanation,
                    total_scanned=total_scanned,
                )

        # ── Layer 5: Nothing found ──────────────────────────────────
        explanation = ProductService._build_no_results_explanation(
            category, max_price, constraints
        )
        return SearchResult(
            products=[],
            match_type="no_results",
            matched_constraints=[],
            unmatched_constraints=["category"]
            + (["budget"] if max_price else [])
            + [c.key for c in constraints],
            explanation=explanation,
            total_scanned=total_scanned,
        )

    # ── Internal helpers ────────────────────────────────────────────

    _PRICE_FLOOR_PATTERNS = [
        r"above\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"over\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"more\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"at\s+least\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"minimum\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"min(?:imum)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"starting\s+(?:from|at)\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
    ]
    _PRICE_CEIL_PATTERNS = [
        r"under\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"below\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"less\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"upto\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"up\s+to\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"max(?:imum)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"budget\s*(?:of|is|:)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
    ]

    @staticmethod
    def _reconcile_price_bounds(
        query: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """Extract directional price phrases from a free-text query and fold
        them into min_price/max_price, without overwriting explicit arguments.

        This guards against a caller (e.g. the LLM agent) expressing an upward
        price bound as free text — "laptops above 70000" — which must be treated
        as a floor, not silently ignored or mapped to an upper bound.
        """
        if not query:
            return min_price, max_price

        q = query.lower()
        if min_price is None:
            for pattern in ProductService._PRICE_FLOOR_PATTERNS:
                m = re.search(pattern, q)
                if m:
                    min_price = ProductService._parse_price_with_unit(m.group(1), q, m.end(1))
                    break
        if max_price is None:
            for pattern in ProductService._PRICE_CEIL_PATTERNS:
                m = re.search(pattern, q)
                if m:
                    max_price = ProductService._parse_price_with_unit(m.group(1), q, m.end(1))
                    break
        # "between X and Y" → both bounds
        between = re.search(
            r"between\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:to|-|and)\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
            q,
        )
        if between:
            lo = ProductService._parse_price_with_unit(between.group(1), q, between.end(1))
            hi = ProductService._parse_price_with_unit(between.group(2), q, between.end(2))
            if min_price is None:
                min_price = lo
            if max_price is None:
                max_price = hi
        return min_price, max_price

    @staticmethod
    def _parse_price_with_unit(number_str: str, text: str, end: int) -> float:
        """Parse a price number, honouring Indian units 'lakh'/'lac'/'crore'
        that may follow the number (e.g. '1 lakh' → 100000)."""
        value = float(number_str.replace(",", ""))
        tail = text[end:].strip()
        if tail.startswith("crore") or tail.startswith("cr"):
            return value * 10_000_000
        if tail.startswith("lakh") or tail.startswith("lac") or tail.startswith("lk"):
            return value * 100_000
        return value

    @staticmethod
    def _strip_price_tokens(query: Optional[str]) -> str:
        """Remove price-related phrases from a free-text query so they don't
        interfere with substring matching against product names/descriptions.
        """
        if not query:
            return ""
        q = query.lower()
        for pattern in (
            ProductService._PRICE_FLOOR_PATTERNS
            + ProductService._PRICE_CEIL_PATTERNS
            + [
                r"between\s*₹?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:to|-|and)\s*₹?\s*\d+(?:,\d{3})*(?:\.\d+)?",
                r"₹\s*\d+(?:,\d{3})*(?:\.\d+)?",
                r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:rupees|inr)",
                r"\d+(?:,\d{3})*(?:\.\d+)?\s*k\b",
            ]
        ):
            q = re.sub(pattern, " ", q)
        # Drop bare numbers left behind
        q = re.sub(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", " ", q)
        return q.strip()

    @staticmethod
    def _normalize_category(db: Session, category: Optional[str]) -> Optional[str]:
        """Match a user-provided category string against actual DB categories.

        Delegates to the shared category_matcher module.
        """
        db_categories = ProductService.get_all_categories(db)
        if not db_categories:
            return None

        return match_category(category, db_categories)

    @staticmethod
    def _filter_by_query(products: List[Product], query: str) -> List[Product]:
        """Filter products by free-text query against name and description."""
        query_lower = query.lower()
        tokens = set(re.split(r"\s+", query_lower))
        tokens -= {"a", "an", "the", "with", "and", "or", "under", "below", "for", "in", "of", "the"}

        scored = []
        for p in products:
            text = f"{p.name} {p.description or ''}".lower()
            if not tokens:
                scored.append((p, 0))
                continue
            matches = sum(1 for t in tokens if t in text)
            if matches > 0:
                scored.append((p, matches / len(tokens)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    @staticmethod
    def _filter_by_brand(products: List[Product], brand: str) -> List[Product]:
        """Filter products by brand (matches name or attributes.brand)."""
        brand_lower = brand.lower()
        return [
            p
            for p in products
            if brand_lower in (p.name or "").lower()
            or brand_lower in str((p.attributes or {}).get("brand", "")).lower()
        ]

    @staticmethod
    def _apply_constraints(
        products: List[Product], constraints: List[SearchConstraint]
    ) -> Tuple[List[Product], List[SearchConstraint]]:
        """Apply constraints, returning (matched_products, unmatched_constraints).

        A product must satisfy ALL constraints to be in the matched set.
        Unmatched constraints are those where NO product satisfied them.
        """
        if not constraints:
            return products, []

        matched = []
        unmatched = []

        for p in products:
            all_pass = True
            for c in constraints:
                if not ProductService._check_constraint(p, c):
                    all_pass = False
                    break
            if all_pass:
                matched.append(p)

        # If no products matched all constraints, identify which constraints were hardest
        if not matched:
            for c in constraints:
                any_match = any(ProductService._check_constraint(p, c) for p in products)
                if not any_match:
                    unmatched.append(c)

        return matched, unmatched

    @staticmethod
    def _check_constraint(product: Product, constraint: SearchConstraint) -> bool:
        """Check if a single product satisfies a single constraint."""
        attrs = product.attributes or {}
        val = attrs.get(constraint.key)

        if val is None:
            return False

        try:
            if constraint.operator == "eq":
                if isinstance(constraint.value, bool):
                    return bool(val) == constraint.value
                if isinstance(val, str):
                    return val.lower() == str(constraint.value).lower()
                return val == constraint.value

            elif constraint.operator == "gte":
                return float(val) >= float(constraint.value)

            elif constraint.operator == "lte":
                return float(val) <= float(constraint.value)

            elif constraint.operator == "contains":
                return str(constraint.value).lower() in str(val).lower()

            elif constraint.operator == "approx":
                # Within 20% of target value
                target = float(constraint.value)
                actual = float(val)
                if target == 0:
                    return actual == 0
                ratio = abs(actual - target) / target
                return ratio <= 0.2

        except (ValueError, TypeError):
            return False

        return False

    @staticmethod
    def _rank_products(
        products: List[Product],
        max_price: Optional[float],
        constraints: List[SearchConstraint],
    ) -> List[Product]:
        """Rank products by generic relevance score.

        Scoring factors:
        - Within budget (higher score for better value)
        - Number of matched constraint attributes
        - Stock availability
        - Price competitiveness
        """
        scored = []
        for p in products:
            score = 0.0
            attrs = p.attributes or {}

            # Budget score: prefer products that leave headroom
            if max_price and max_price > 0:
                price_ratio = p.price / max_price
                if price_ratio <= 0.5:
                    score += 4.0
                elif price_ratio <= 0.7:
                    score += 3.0
                elif price_ratio <= 0.85:
                    score += 2.0
                elif price_ratio <= 1.0:
                    score += 1.0
                else:
                    score -= 1.0  # Over budget penalty

            # Constraint match score
            for c in constraints:
                if ProductService._check_constraint(p, c):
                    score += 2.0
                    # Bonus for numeric closeness
                    val = attrs.get(c.key)
                    if val is not None and c.operator in ("gte", "lte") and c.value:
                        try:
                            actual = float(val)
                            target = float(c.value)
                            if target > 0:
                                closeness = 1.0 - min(abs(actual - target) / target, 1.0)
                                score += closeness
                        except (ValueError, TypeError):
                            pass

            # Stock bonus
            stock = p.stock_quantity or 0
            if stock > 50:
                score += 1.5
            elif stock > 20:
                score += 1.0
            elif stock > 5:
                score += 0.5

            # Value score: prefer mid-range over extremes
            if max_price and max_price > 0:
                price_ratio = p.price / max_price
                if 0.3 <= price_ratio <= 0.7:
                    score += 1.0  # Sweet spot bonus

            scored.append((p, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    @staticmethod
    def compute_score(
        product: "Product",
        max_price: Optional[float],
        constraints: List["SearchConstraint"],
    ) -> Tuple[float, Dict[str, Any], int]:
        """Public scoring helper that mirrors _rank_products logic exactly.

        Returns (raw_score, breakdown_dict, match_percentage). The breakdown
        dict provides per-factor details for explanation/comparison UIs.
        """
        score = 0.0
        attrs = product.attributes or {}
        breakdown: Dict[str, Any] = {}

        # Budget score
        budget_score = 0.0
        if max_price and max_price > 0:
            price_ratio = product.price / max_price
            if price_ratio <= 0.5:
                budget_score = 4.0
            elif price_ratio <= 0.7:
                budget_score = 3.0
            elif price_ratio <= 0.85:
                budget_score = 2.0
            elif price_ratio <= 1.0:
                budget_score = 1.0
            else:
                budget_score = -1.0
            breakdown["budget_ratio"] = round(price_ratio, 3)
        breakdown["budget_score"] = budget_score
        score += budget_score

        # Constraint match score
        matched_constraints = []
        unmatched_constraints = []
        for c in constraints:
            if ProductService._check_constraint(product, c):
                matched_constraints.append(c.key)
                score += 2.0
                val = attrs.get(c.key)
                closeness = 0.0
                if val is not None and c.operator in ("gte", "lte") and c.value:
                    try:
                        actual_f = float(val)
                        target_f = float(c.value)
                        if target_f > 0:
                            closeness = 1.0 - min(abs(actual_f - target_f) / target_f, 1.0)
                            score += closeness
                    except (ValueError, TypeError):
                        pass
                breakdown.setdefault("constraint_details", []).append({
                    "key": c.key, "satisfied": True,
                    "actual": val, "target": c.value, "closeness": round(closeness, 3),
                })
            else:
                unmatched_constraints.append(c.key)
                breakdown.setdefault("constraint_details", []).append({
                    "key": c.key, "satisfied": False,
                    "actual": attrs.get(c.key), "target": c.value,
                })
        breakdown["matched_constraints"] = matched_constraints
        breakdown["unmatched_constraints"] = unmatched_constraints

        # Stock bonus
        stock = product.stock_quantity or 0
        stock_score = 0.0
        if stock > 50:
            stock_score = 1.5
        elif stock > 20:
            stock_score = 1.0
        elif stock > 5:
            stock_score = 0.5
        breakdown["stock_score"] = stock_score
        breakdown["stock"] = stock
        score += stock_score

        # Value sweet spot
        value_score = 0.0
        if max_price and max_price > 0:
            price_ratio = product.price / max_price
            if 0.3 <= price_ratio <= 0.7:
                value_score = 1.0
        breakdown["value_score"] = value_score
        score += value_score

        # Compute 0-100 match percentage
        budget_max = 4.0
        constraint_max = max(len(constraints) * 3.0, 1.0)
        total_max = budget_max + constraint_max + 1.5 + 1.0
        match_pct = int(min(round(max(score, 0) / total_max * 100), 100))

        return score, breakdown, match_pct

    @staticmethod
    def _build_explanation(
        category: Optional[str],
        max_price: Optional[float],
        constraints: List[SearchConstraint],
        matched: List[Product],
        unmatched: List[SearchConstraint],
        match_type: str,
    ) -> str:
        """Build a human-readable explanation of search results."""
        cat_text = category or "products"
        budget_text = f" under ₹{max_price:,.0f}" if max_price else ""

        if match_type == "exact":
            constraint_texts = []
            for c in unmatched:
                constraint_texts.append(c.raw_text or c.key)
            if matched:
                msg = f"I found {len(matched)} {cat_text}{budget_text}"
                if constraint_texts:
                    msg += f", but none matched your preference for {', '.join(constraint_texts)}"
                msg += "."
                return msg

        elif match_type == "partial":
            if matched:
                return (
                    f"I found {len(matched)} {cat_text}{budget_text} "
                    f"but couldn't match all your preferences. "
                    f"Here are the closest alternatives."
                )

        elif match_type == "budget_fallback":
            return (
                f"No {cat_text}{budget_text} are currently available in our catalog. "
                f"Here are the closest available options in this category instead."
            )

        elif match_type == "category_fallback":
            return (
                f"I couldn't find a category matching your request "
                f"but here are products within your budget."
            )

        return f"I found {len(matched)} options."

    @staticmethod
    def _build_no_results_explanation(
        category: Optional[str],
        max_price: Optional[float],
        constraints: List[SearchConstraint],
    ) -> str:
        """Build explanation when no results are found."""
        if category:
            budget_text = f" under ₹{max_price:,.0f}" if max_price else ""
            return f"I couldn't find any {category}{budget_text} in our catalog."

        return "I couldn't find any products matching your request. Try broadening your search."
