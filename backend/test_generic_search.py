"""Comprehensive tests for the generic product discovery engine.

Tests 16 categories of search scenarios using the actual expanded catalog.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
from models.product import Product
from seed.seed_products import seed_products
from services.product_service import ProductService, SearchConstraint, SearchResult
from services.intent_service import IntentService


def setup_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_products(db)
    return db


def test_category(db, query, expected_category=None, expected_min_products=1, label=""):
    """Run a category test and report results."""
    intent = IntentService.extract_intent(query, db=db)
    cat = intent["category"]
    result = ProductService.generic_search(
        db=db, category=cat, max_price=intent["max_price"],
        min_price=intent.get("min_price"), brand=intent.get("brand"),
        constraints=intent.get("constraints", []), limit=5,
    )
    ok = len(result.products) >= expected_min_products
    if expected_category:
        ok = ok and cat == expected_category
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label or query}")
    if not ok:
        print(f"         category={cat} expected={expected_category} products={len(result.products)}")
        print(f"         match_type={result.match_type} explanation={result.explanation}")
    return ok


def test_search(db, category, max_price, constraints, expected_min=1, label=""):
    """Run a search test."""
    result = ProductService.generic_search(
        db=db, category=category, max_price=max_price,
        constraints=constraints, limit=5,
    )
    ok = len(result.products) >= expected_min
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")
    if not ok:
        print(f"         products={len(result.products)} match_type={result.match_type}")
        print(f"         explanation={result.explanation}")
    return ok


def run_all_tests():
    db = setup_database()
    total = 0
    passed = 0

    print("=" * 60)
    print("GENERIC PRODUCT DISCOVERY ENGINE — TEST SUITE")
    print("=" * 60)

    # ── 1. Singular category search ──────────────────────────────
    print("\n--- 1. Singular category search ---")
    total += 1; passed += test_category(db, "show me a laptop", "laptops", 1, "singular: laptop")
    total += 1; passed += test_category(db, "i need a headphone", "headphones", 1, "singular: headphone")
    total += 1; passed += test_category(db, "show me a phone", "smartphones", 1, "singular: phone")

    # ── 2. Plural category search ────────────────────────────────
    print("\n--- 2. Plural category search ---")
    total += 1; passed += test_category(db, "show me laptops", "laptops", 1, "plural: laptops")
    total += 1; passed += test_category(db, "headphones please", "headphones", 1, "plural: headphones")
    total += 1; passed += test_category(db, "smartphones under 30000", "smartphones", 1, "plural: smartphones")

    # ── 3. Case-insensitive search ───────────────────────────────
    print("\n--- 3. Case-insensitive search ---")
    total += 1; passed += test_category(db, "show me LAPTOPS", "laptops", 1, "uppercase: LAPTOPS")
    total += 1; passed += test_category(db, "Headphones under 5000", "headphones", 1, "mixed case: Headphones")

    # ── 4. Category + budget ─────────────────────────────────────
    print("\n--- 4. Category + budget ---")
    total += 1; passed += test_search(db, "laptops", 50000, [], 1, "laptops under 50000")
    total += 1; passed += test_search(db, "smartphones", 20000, [], 1, "smartphones under 20000")
    total += 1; passed += test_search(db, "headphones", 5000, [], 1, "headphones under 5000")

    # ── 5. Category + numeric attribute ──────────────────────────
    print("\n--- 5. Category + numeric attribute ---")
    total += 1; passed += test_search(
        db, "laptops", 80000,
        [SearchConstraint("ram_gb", 16, "gte", "16GB RAM")],
        1, "laptops with 16GB RAM under 80000"
    )
    total += 1; passed += test_search(
        db, "smartphones", 40000,
        [SearchConstraint("camera_mp", 50, "gte", "50MP camera")],
        1, "smartphones with 50MP camera under 40000"
    )
    total += 1; passed += test_search(
        db, "earbuds", 10000,
        [SearchConstraint("battery_life_hours", 30, "gte", "30hr battery")],
        1, "earbuds with 30hr battery under 10000"
    )

    # ── 6. Category + boolean attribute ──────────────────────────
    print("\n--- 6. Category + boolean attribute ---")
    total += 1; passed += test_search(
        db, "headphones", None,
        [SearchConstraint("noise_cancellation", True, "eq", "noise cancellation")],
        1, "headphones with noise cancellation"
    )
    total += 1; passed += test_search(
        db, "earbuds", None,
        [SearchConstraint("wireless", True, "eq", "wireless")],
        1, "wireless earbuds"
    )
    total += 1; passed += test_search(
        db, "keyboards", None,
        [SearchConstraint("rgb", True, "eq", "RGB")],
        1, "keyboards with RGB"
    )

    # ── 7. Category + string attribute ───────────────────────────
    print("\n--- 7. Category + string attribute ---")
    total += 1; passed += test_search(
        db, "laptops", None,
        [SearchConstraint("operating_system", "macOS", "contains", "macOS")],
        1, "laptops with macOS"
    )
    total += 1; passed += test_search(
        db, "laptops", None,
        [SearchConstraint("processor", "Ryzen", "contains", "Ryzen processor")],
        1, "laptops with Ryzen processor"
    )

    # ── 8. Multiple attribute requirements ───────────────────────
    print("\n--- 8. Multiple attribute requirements ---")
    total += 1; passed += test_search(
        db, "laptops", 100000,
        [
            SearchConstraint("ram_gb", 16, "gte", "16GB RAM"),
            SearchConstraint("storage_gb", 512, "gte", "512GB storage"),
        ],
        1, "laptops: 16GB RAM + 512GB under 100000"
    )
    total += 1; passed += test_search(
        db, "smartphones", 30000,
        [
            SearchConstraint("camera_mp", 50, "gte", "50MP camera"),
            SearchConstraint("5g", True, "eq", "5G"),
        ],
        1, "smartphones: 50MP + 5G under 30000"
    )

    # ── 9. Exact match ───────────────────────────────────────────
    print("\n--- 9. Exact match ---")
    result = ProductService.generic_search(
        db, "headphones", 25000,
        constraints=[SearchConstraint("noise_cancellation", True, "eq", "ANC")], limit=5,
    )
    total += 1
    if result.match_type == "exact" and len(result.products) > 0:
        passed += 1; print("  [PASS] exact match: ANC headphones under 25000")
    else:
        print(f"  [FAIL] exact match: type={result.match_type} count={len(result.products)}")

    # ── 10. Partial match ────────────────────────────────────────
    print("\n--- 10. Partial match (relax constraints) ---")
    result = ProductService.generic_search(
        db, "headphones", 5000,
        constraints=[SearchConstraint("noise_cancellation", True, "eq", "ANC")], limit=5,
    )
    total += 1
    if len(result.products) > 0 and result.match_type in ("partial", "budget_fallback"):
        passed += 1; print(f"  [PASS] partial match: {result.match_type}, {len(result.products)} products")
    else:
        print(f"  [FAIL] partial match: type={result.match_type} count={len(result.products)}")

    # ── 11. Unavailable preference with alternatives ─────────────
    print("\n--- 11. Unavailable preference with alternatives ---")
    result = ProductService.generic_search(
        db, "smartphones", 15000,
        constraints=[SearchConstraint("camera_mp", 200, "gte", "200MP camera")], limit=5,
    )
    total += 1
    if len(result.products) > 0:
        passed += 1; print(f"  [PASS] alternatives found: {len(result.products)} products")
    else:
        print(f"  [FAIL] no alternatives: {result.explanation}")

    # ── 12. Budget fallback ──────────────────────────────────────
    print("\n--- 12. Budget not available with closest products ---")
    result = ProductService.generic_search(
        db, "laptops", 15000, limit=5,  # No laptop under 15000
    )
    total += 1
    if len(result.products) > 0 and result.match_type in ("budget_fallback", "partial"):
        passed += 1; print(f"  [PASS] budget fallback: {result.match_type}, {len(result.products)} products")
    else:
        print(f"  [FAIL] budget fallback: type={result.match_type} count={len(result.products)}")

    # ── 13. Unknown category ─────────────────────────────────────
    print("\n--- 13. Unknown category ---")
    result = ProductService.generic_search(
        db, "nonexistent_category_xyz", 1, limit=5,  # impossibly low budget
    )
    total += 1
    if result.match_type in ("no_results", "category_fallback"):
        passed += 1; print(f"  [PASS] unknown category: {result.match_type}")
    else:
        print(f"  [FAIL] unknown category: type={result.match_type} count={len(result.products)}")

    # ── 14. New dynamically-added category ───────────────────────
    print("\n--- 14. New category without code changes (gaming-chair) ---")
    # Add a test product directly
    test_product = Product(
        id="test-gaming-chair-001",
        name="Test Gaming Chair Pro",
        description="Test gaming chair with lumbar support and reclining feature",
        price=15999.00,
        currency="INR",
        category="gaming-chairs",
        attributes={
            "brand": "TestBrand",
            "weight_capacity_kg": 120,
            "reclining": True,
            "lumbar_support": True,
            "armrests": True,
        },
        stock_quantity=10,
    )
    existing = db.query(Product).filter(Product.id == "test-gaming-chair-001").first()
    if not existing:
        db.add(test_product)
        db.commit()

    # Search for it using generic pipeline
    result = ProductService.generic_search(
        db, "gaming-chairs", 20000,
        constraints=[SearchConstraint("reclining", True, "eq", "reclining")], limit=5,
    )
    total += 1
    found_chair = any(p.id == "test-gaming-chair-001" for p in result.products)
    if found_chair:
        passed += 1; print("  [PASS] dynamic category: gaming-chair found via generic search")
    else:
        print(f"  [FAIL] dynamic category: products={[p.id for p in result.products]}")

    # Cleanup test product
    db.query(Product).filter(Product.id == "test-gaming-chair-001").delete()
    db.commit()

    # ── 15. AI unavailable / rules fallback ──────────────────────
    print("\n--- 15. Rules fallback (simulated) ---")
    # Test that intent extraction + generic search work together
    intent = IntentService.extract_intent("wireless headphones under 5000 with noise cancellation", db=db)
    result = ProductService.generic_search(
        db=db, category=intent["category"], max_price=intent["max_price"],
        constraints=intent.get("constraints", []), limit=5,
    )
    total += 1
    if len(result.products) > 0 and intent["category"] == "headphones":
        passed += 1; print(f"  [PASS] rules fallback: {len(result.products)} headphones found")
    else:
        print(f"  [FAIL] rules fallback: cat={intent['category']} products={len(result.products)}")

    # ── 16. Existing catalog categories ──────────────────────────
    print("\n--- 16. All existing catalog categories ---")
    categories = [
        ("headphones", "headphones under 10000"),
        ("earbuds", "earbuds under 5000"),
        ("wired-earphones", "wired earphones"),
        ("laptops", "laptops under 70000"),
        ("smartphones", "smartphones under 30000"),
        ("smartwatches", "smartwatches under 10000"),
        ("tablets", "tablets under 30000"),
        ("tvs", "tvs under 50000"),
        ("speakers", "speakers under 5000"),
        ("cameras", "cameras under 50000"),
        ("keyboards", "keyboards under 5000"),
        ("mice", "mice under 5000"),
    ]
    for cat_name, query in categories:
        intent = IntentService.extract_intent(query, db=db)
        result = ProductService.generic_search(
            db=db, category=intent["category"], max_price=intent["max_price"],
            constraints=intent.get("constraints", []), limit=5,
        )
        total += 1
        if len(result.products) > 0 and intent["category"] == cat_name:
            passed += 1; print(f"  [PASS] {cat_name}: {len(result.products)} products")
        else:
            print(f"  [FAIL] {cat_name}: cat={intent['category']} products={len(result.products)}")

    # ── 17. Synonym and linguistic edge cases ───────────────────────
    print("\n--- 17. Synonym and linguistic edge cases ---")
    total += 1; passed += test_category(db, "television", "tvs", 1, "synonym: television -> tvs")
    total += 1; passed += test_category(db, "mouse", "mice", 1, "irregular plural: mouse -> mice")
    total += 1; passed += test_category(db, "watch", "smartwatches", 1, "synonym prefix: watch -> smartwatches")
    total += 1; passed += test_category(db, "phone", "smartphones", 1, "synonym prefix: phone -> smartphones")
    total += 1; passed += test_category(db, "earphone", "wired-earphones", 1, "synonym: earphone -> wired-earphones")

    # ── 18. Price floor expressed as "above"/"over" ──────────────
    print("\n--- 18. Upward price bound ('above'/'over') ---")
    # The phrasing must be honoured as a floor, not dropped or inverted.
    result = ProductService.generic_search(
        db, "laptops", query="laptops above 70000", limit=5,
    )
    total += 1
    above_ok = (
        result.match_type == "exact"
        and len(result.products) > 0
        and all(p.price >= 70000 for p in result.products)
    )
    if above_ok:
        passed += 1
        print(f"  [PASS] 'above 70000' as floor: {len(result.products)} laptops >= 70000")
    else:
        print(f"  [FAIL] 'above 70000': type={result.match_type} count={len(result.products)}")

    result = ProductService.generic_search(
        db, "laptops", query="gaming laptops over 1 lakh", limit=5,
    )
    total += 1
    lakh_ok = (
        result.match_type == "exact"
        and len(result.products) > 0
        and all(p.price >= 100000 for p in result.products)
    )
    if lakh_ok:
        passed += 1
        print(f"  [PASS] 'over 1 lakh' as floor: {len(result.products)} laptops >= 100000")
    else:
        print(f"  [FAIL] 'over 1 lakh': type={result.match_type} count={len(result.products)}")

    db.close()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
