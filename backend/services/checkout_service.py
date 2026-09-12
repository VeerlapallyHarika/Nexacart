from sqlalchemy.orm import Session
from models.cart import Cart, CartItem
from models.product import Product
from services.cart_service import CartService
from typing import Dict, Any, List


class CheckoutService:
    @staticmethod
    def verify_price(db: Session, product_id: str) -> Dict[str, Any]:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found", "verified": False}

        return {
            "verified": True,
            "product_id": product.id,
            "product_name": product.name,
            "current_price": product.price,
            "currency": product.currency
        }

    @staticmethod
    def verify_inventory(
        db: Session,
        product_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found", "verified": False}

        available = product.stock_quantity >= quantity

        return {
            "verified": available,
            "product_id": product.id,
            "product_name": product.name,
            "requested_quantity": quantity,
            "available_quantity": product.stock_quantity,
            "in_stock": available
        }

    @staticmethod
    def verify_cart(db: Session, session_id: str) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found", "verified": False}

        if not cart.items:
            return {"error": "Cart is empty", "verified": False}

        verification_results = []
        all_verified = True
        total = 0

        for item in cart.items:
            product = item.product
            if not product:
                verification_results.append({
                    "product_id": item.product_id,
                    "product_name": "Unknown Product",
                    "verified": False,
                    "error": "Product not found"
                })
                all_verified = False
                continue

            price_ok = True
            inventory_ok = product.stock_quantity >= item.quantity

            item_total = product.price * item.quantity
            total += item_total

            verification_results.append({
                "product_id": product.id,
                "product_name": product.name,
                "price": product.price,
                "quantity": item.quantity,
                "subtotal": item_total,
                "price_verified": price_ok,
                "inventory_verified": inventory_ok,
                "current_stock": product.stock_quantity,
                "verified": price_ok and inventory_ok
            })

            if not price_ok or not inventory_ok:
                all_verified = False

        if all_verified:
            CartService.update_cart_status(db, session_id, "VERIFIED")

        return {
            "verified": all_verified,
            "cart_id": cart.id,
            "status": cart.status if not all_verified else "VERIFIED",
            "items": verification_results,
            "total": total,
            "currency": "INR",
            "item_count": sum(item.quantity for item in cart.items)
        }

    @staticmethod
    def request_approval(db: Session, session_id: str) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        if cart.status not in ["VERIFIED", "ACTIVE"]:
            return {"error": f"Cart cannot be approved. Current status: {cart.status}"}

        verification = CheckoutService.verify_cart(db, session_id)
        if not verification.get("verified"):
            return {
                "error": "Cart verification failed. Please resolve issues before requesting approval.",
                "verification": verification
            }

        CartService.update_cart_status(db, session_id, "AWAITING_APPROVAL")

        return {
            "success": True,
            "status": "AWAITING_APPROVAL",
            "message": "Cart is ready for approval. Please confirm to proceed to payment.",
            "verification": verification
        }

    @staticmethod
    def approve_checkout(db: Session, session_id: str) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        if cart.status != "AWAITING_APPROVAL":
            return {
                "error": f"Cart cannot be approved. Current status: {cart.status}",
                "required_status": "AWAITING_APPROVAL"
            }

        verification = CheckoutService.verify_cart(db, session_id)
        if not verification.get("verified"):
            return {
                "error": "Cart verification failed during approval. Prices or inventory may have changed.",
                "verification": verification
            }

        CartService.update_cart_status(db, session_id, "APPROVED_FOR_PAYMENT")

        return {
            "success": True,
            "status": "APPROVED_FOR_PAYMENT",
            "message": "Your order has been verified and approved for payment. The next step is secure payment checkout.",
            "verification": verification
        }

    @staticmethod
    def get_checkout_summary(db: Session, session_id: str) -> Dict[str, Any]:
        verification = CheckoutService.verify_cart(db, session_id)
        if not verification.get("verified") and "error" in verification:
            return {"error": verification["error"]}

        return {
            "summary": {
                "items": verification.get("items", []),
                "total": verification.get("total", 0),
                "currency": verification.get("currency", "INR"),
                "item_count": verification.get("item_count", 0),
                "all_prices_verified": all(
                    item.get("price_verified", False)
                    for item in verification.get("items", [])
                ),
                "all_inventory_available": all(
                    item.get("inventory_verified", False)
                    for item in verification.get("items", [])
                ),
                "ready_for_payment": verification.get("verified", False)
            }
        }
