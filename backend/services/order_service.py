from sqlalchemy.orm import Session
from models.order import Order, OrderItem
from models.payment import Payment
from models.cart import Cart, CartItem
from typing import Dict, Any, Optional, List


class OrderService:
    @staticmethod
    def create_order_from_cart(
        db: Session,
        session_id: str,
        payment_id: str
    ) -> Dict[str, Any]:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}

        if payment.status != "SUCCESS":
            return {"error": f"Cannot create order. Payment status is {payment.status}. Required: SUCCESS"}

        cart = db.query(Cart).filter(Cart.id == payment.cart_id).first()
        if not cart:
            return {"error": "Cart not found"}

        existing_order = db.query(Order).filter(
            Order.cart_id == cart.id,
            Order.status.in_(["CREATED", "CONFIRMED"])
        ).first()

        if existing_order:
            # Idempotent: this cart has already been turned into an order by a
            # successful payment. Return the existing order instead of creating a
            # duplicate (protects against double orders on re-verification).
            return OrderService._serialize_order(existing_order, db)

        user_id = getattr(payment, "user_id", None) or getattr(cart, "user_id", None)

        order = Order(
            id=Order.generate_id(),
            session_id=session_id,
            user_id=user_id,
            cart_id=cart.id,
            payment_id=payment.id,
            total_amount=payment.amount,
            currency=payment.currency,
            status="CREATED"
        )

        db.add(order)
        db.flush()

        for cart_item in cart.items:
            product = cart_item.product
            if product:
                order_item = OrderItem(
                    id=OrderItem.generate_id(),
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    price_at_purchase=product.price,
                    quantity=cart_item.quantity,
                    subtotal=product.price * cart_item.quantity
                )
                db.add(order_item)

        order.status = "CONFIRMED"
        cart.status = "PAID"

        db.commit()
        db.refresh(order)

        items = []
        for item in order.items:
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "price_at_purchase": item.price_at_purchase,
                "quantity": item.quantity,
                "subtotal": item.subtotal
            })

        return {
            "success": True,
            "order_id": order.id,
            "session_id": order.session_id,
            "user_id": order.user_id,
            "cart_id": order.cart_id,
            "payment_id": order.payment_id,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "status": order.status,
            "items": items,
            "created_at": order.created_at
        }

    @staticmethod
    def _serialize_order(order: Order, db: Session) -> Dict[str, Any]:
        """Serialize an Order row into the same shape as a fresh order result."""
        items = []
        for item in order.items:
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "price_at_purchase": item.price_at_purchase,
                "quantity": item.quantity,
                "subtotal": item.subtotal,
            })

        return {
            "success": True,
            "order_id": order.id,
            "session_id": order.session_id,
            "user_id": order.user_id,
            "cart_id": order.cart_id,
            "payment_id": order.payment_id,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "status": order.status,
            "items": items,
            "created_at": order.created_at,
        }

    @staticmethod
    def get_order(db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None

        items = []
        for item in order.items:
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "price_at_purchase": item.price_at_purchase,
                "quantity": item.quantity,
                "subtotal": item.subtotal
            })

        payment = db.query(Payment).filter(Payment.id == order.payment_id).first()

        return {
            "order_id": order.id,
            "session_id": order.session_id,
            "user_id": order.user_id,
            "cart_id": order.cart_id,
            "payment_id": order.payment_id,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "status": order.status,
            "items": items,
            "payment_status": payment.status if payment else None,
            "created_at": order.created_at,
            "updated_at": order.updated_at
        }

    @staticmethod
    def get_orders_by_session(db: Session, session_id: str) -> List[Dict[str, Any]]:
        orders = db.query(Order).filter(
            Order.session_id == session_id
        ).order_by(Order.created_at.desc()).all()

        result = []
        for order in orders:
            items = []
            for item in order.items:
                items.append({
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "price_at_purchase": item.price_at_purchase,
                    "quantity": item.quantity,
                    "subtotal": item.subtotal
                })

            payment = db.query(Payment).filter(Payment.id == order.payment_id).first()

            result.append({
                "order_id": order.id,
                "session_id": order.session_id,
                "user_id": order.user_id,
                "cart_id": order.cart_id,
                "payment_id": order.payment_id,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "status": order.status,
                "items": items,
                "payment_status": payment.status if payment else None,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            })

        return result

    @staticmethod
    def get_orders_by_user(db: Session, user_id: str) -> List[Dict[str, Any]]:
        orders = db.query(Order).filter(
            Order.user_id == user_id
        ).order_by(Order.created_at.desc()).all()

        result = []
        for order in orders:
            items = []
            for item in order.items:
                items.append({
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "price_at_purchase": item.price_at_purchase,
                    "quantity": item.quantity,
                    "subtotal": item.subtotal
                })

            payment = db.query(Payment).filter(Payment.id == order.payment_id).first()

            result.append({
                "order_id": order.id,
                "session_id": order.session_id,
                "user_id": order.user_id,
                "cart_id": order.cart_id,
                "payment_id": order.payment_id,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "status": order.status,
                "items": items,
                "payment_status": payment.status if payment else None,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            })

        return result

