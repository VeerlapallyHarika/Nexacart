from sqlalchemy.orm import Session
from models.cart import Cart, CartItem
from models.product import Product
from typing import Optional, List, Dict, Any
import uuid


class CartService:
    @staticmethod
    def get_or_create_cart(db: Session, session_id: str) -> Cart:
        cart = db.query(Cart).filter(Cart.session_id == session_id).first()
        if not cart:
            cart = Cart(
                id=f"cart_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                status="ACTIVE"
            )
            db.add(cart)
            db.commit()
            db.refresh(cart)
        return cart

    @staticmethod
    def get_cart(db: Session, session_id: str) -> Optional[Cart]:
        return db.query(Cart).filter(Cart.session_id == session_id).first()

    @staticmethod
    def add_to_cart(
        db: Session,
        session_id: str,
        product_id: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}

        if product.stock_quantity < quantity:
            return {"error": "Insufficient stock"}

        cart = CartService.get_or_create_cart(db, session_id)

        existing_item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id
        ).first()

        if existing_item:
            existing_item.quantity += quantity
            db.commit()
            db.refresh(existing_item)
            item = existing_item
        else:
            item = CartItem(
                id=f"item_{uuid.uuid4().hex[:12]}",
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity
            )
            db.add(item)
            db.commit()
            db.refresh(item)

        return {
            "success": True,
            "cart_id": cart.id,
            "item": {
                "id": item.id,
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item.quantity,
                "price": product.price,
                "subtotal": product.price * item.quantity
            },
            "cart_total": CartService._calculate_cart_total(cart),
            "cart_item_count": CartService._count_cart_items(cart)
        }

    @staticmethod
    def get_cart_details(db: Session, session_id: str) -> Optional[Dict[str, Any]]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return None

        items = []
        for item in cart.items:
            product = item.product
            if product:
                items.append({
                    "id": item.id,
                    "product_id": product.id,
                    "product_name": product.name,
                    "description": product.description,
                    "price": product.price,
                    "currency": product.currency,
                    "quantity": item.quantity,
                    "subtotal": product.price * item.quantity,
                    "stock_quantity": product.stock_quantity,
                    "attributes": product.attributes or {}
                })

        return {
            "cart_id": cart.id,
            "session_id": cart.session_id,
            "status": cart.status,
            "items": items,
            "total": CartService._calculate_cart_total(cart),
            "item_count": CartService._count_cart_items(cart),
            "created_at": cart.created_at,
            "updated_at": cart.updated_at
        }

    @staticmethod
    def update_cart_item(
        db: Session,
        session_id: str,
        item_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        item = db.query(CartItem).filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        ).first()

        if not item:
            return {"error": "Cart item not found"}

        product = item.product
        if product and product.stock_quantity < quantity:
            return {"error": "Insufficient stock"}

        if quantity <= 0:
            db.delete(item)
            db.commit()
            return {"success": True, "message": "Item removed"}

        item.quantity = quantity
        db.commit()
        db.refresh(item)

        return {
            "success": True,
            "item": {
                "id": item.id,
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item.quantity,
                "price": product.price,
                "subtotal": product.price * item.quantity
            }
        }

    @staticmethod
    def remove_cart_item(
        db: Session,
        session_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        item = db.query(CartItem).filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        ).first()

        if not item:
            return {"error": "Cart item not found"}

        db.delete(item)
        db.commit()

        return {"success": True, "message": "Item removed from cart"}

    @staticmethod
    def clear_cart(db: Session, session_id: str) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        for item in cart.items:
            db.delete(item)

        cart.status = "ACTIVE"
        db.commit()

        return {"success": True, "message": "Cart cleared"}

    @staticmethod
    def update_cart_status(
        db: Session,
        session_id: str,
        status: str
    ) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        valid_statuses = ["ACTIVE", "VERIFIED", "AWAITING_APPROVAL", "APPROVED_FOR_PAYMENT", "CANCELLED"]
        if status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}

        cart.status = status
        db.commit()
        db.refresh(cart)

        return {"success": True, "status": cart.status}

    @staticmethod
    def _calculate_cart_total(cart: Cart) -> float:
        total = 0
        for item in cart.items:
            product = item.product
            if product:
                total += product.price * item.quantity
        return total

    @staticmethod
    def _count_cart_items(cart: Cart) -> int:
        return sum(item.quantity for item in cart.items)
