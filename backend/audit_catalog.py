"""Audit the product catalog.

Queries every category in the catalog and prints, for each:
  * the number of products
  * the minimum price
  * the maximum price
  * the min->max range multiplier (max / min)

Flags any category where either:
  * there are fewer than 4 products, or
  * the price range spans less than 3x from min to max.

These are the categories whose spread needs widening (e.g. by adding budget or
premium stock). Categories that already pass are left untouched.

Usage:
    python audit_catalog.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import func

from database import SessionLocal
from models.product import Product
from seed.seed_products import seed_products

MIN_COUNT = 4
MIN_RANGE_MULTIPLIER = 3.0


def audit_catalog():
    db = SessionLocal()
    try:
        # Apply the seed definitions on disk (idempotent - only adds new ids)
        # so the audit reflects the current catalog source.
        seed_products(db)

        rows = (
            db.query(
                Product.category,
                func.count(Product.id),
                func.min(Product.price),
                func.max(Product.price),
            )
            .group_by(Product.category)
            .order_by(Product.category)
            .all()
        )
    finally:
        db.close()

    print(f"{'Category':<18} {'#':>3} {'Min (INR)':>12} {'Max (INR)':>12} {'Range':>7}  Flag")
    print("-" * 66)

    flagged = []
    for category, count, min_price, max_price in rows:
        range_multiplier = (max_price / min_price) if min_price else 0.0
        low_count = count < MIN_COUNT
        narrow_range = range_multiplier < MIN_RANGE_MULTIPLIER
        flag = low_count or narrow_range

        reasons = []
        if low_count:
            reasons.append("count < 4")
        if narrow_range:
            reasons.append(f"range {range_multiplier:.1f}x < {MIN_RANGE_MULTIPLIER:.0f}x")

        flag_text = ",".join(reasons) if flag else ""
        print(
            f"{category:<18} {count:>3} {min_price:>12,.0f} {max_price:>12,.0f} "
            f"{range_multiplier:>6.1f}x  {flag_text}"
        )
        if flag:
            flagged.append(category)

    print("-" * 66)
    if flagged:
        print(f"FLAGGED ({len(flagged)}): {', '.join(flagged)}")
    else:
        print("All categories pass.")


if __name__ == "__main__":
    audit_catalog()
