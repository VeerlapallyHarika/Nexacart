from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from models.payment import Payment
from models.cart import Cart
from models.order import Order
from typing import Dict, Any, Optional
from services.cart_service import CartService
import uuid
import os
import threading


_locks_guard = threading.Lock()
_cart_locks: Dict[str, threading.Lock] = {}


def _cart_lock(cart_id: str) -> threading.Lock:
    """Return a per-cart lock so concurrent payload/verify/finalize calls for the
    same cart are serialized within this process. This is the first line of
    defence against double-click / simultaneous payment requests; the database
    order guard remains the ultimate back-stop for double order creation."""
    with _locks_guard:
        lock = _cart_locks.get(cart_id)
        if lock is None:
            lock = threading.Lock()
            _cart_locks[cart_id] = lock
        return lock


class PaymentProvider(ABC):
    @abstractmethod
    def create_payment(self, amount: float, currency: str, metadata: dict) -> Dict[str, Any]:
        pass

    @abstractmethod
    def process_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_payment_status(self, provider_payment_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def cancel_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        pass


class SimulatedPaymentProvider(PaymentProvider):
    def create_payment(self, amount: float, currency: str, metadata: dict) -> Dict[str, Any]:
        provider_payment_id = f"sim_{uuid.uuid4().hex[:16]}"
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "amount": amount,
            "currency": currency,
            "status": "created"
        }

    def process_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "status": "captured",
            "message": "Simulated payment processed successfully"
        }

    def get_payment_status(self, provider_payment_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "status": "captured"
        }

    def cancel_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "status": "cancelled",
            "message": "Simulated payment cancelled"
        }


def _get_provider() -> PaymentProvider:
    """Get the configured payment provider based on PAYMENT_PROVIDER env var.

    If PAYMENT_PROVIDER is set to 'razorpay' but the credentials are invalid,
    falls back to SimulatedPaymentProvider and logs a warning.
    """
    provider_name = os.getenv("PAYMENT_PROVIDER", "simulated").lower()
    if provider_name == "razorpay":
        try:
            from services.razorpay_payment_provider import RazorpayPaymentProvider
            provider = RazorpayPaymentProvider()
            if not provider.verify_credentials():
                print(
                    "[WARNING] RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are invalid. "
                    "Falling back to simulated payment provider. "
                    "Set valid Razorpay test mode credentials in .env to enable Razorpay.",
                    flush=True,
                )
                return SimulatedPaymentProvider()
            return provider
        except (ValueError, Exception) as e:
            print(
                f"[WARNING] Failed to initialize Razorpay provider: {e}. "
                "Falling back to simulated payment provider.",
                flush=True,
            )
            return SimulatedPaymentProvider()
    return SimulatedPaymentProvider()


class PaymentService:
    _provider: Optional[PaymentProvider] = None

    @classmethod
    def _get_provider(cls) -> PaymentProvider:
        if cls._provider is None:
            cls._provider = _get_provider()
        return cls._provider

    @classmethod
    def set_provider(cls, provider: PaymentProvider):
        cls._provider = provider

    @classmethod
    def get_provider_name(cls) -> str:
        return os.getenv("PAYMENT_PROVIDER", "simulated").lower()

    @staticmethod
    def create_payment_intent(db: Session, session_id: str) -> Dict[str, Any]:
        cart = CartService.get_cart(db, session_id)
        if not cart:
            return {"error": "Cart not found"}

        if not cart.items:
            return {"error": "Cart is empty"}

        total = CartService._calculate_cart_total(cart)
        if total <= 0:
            return {"error": "Invalid cart total"}

        # Serialize concurrent create calls for the same cart so two rapid
        # requests cannot both create independent active attempts. Inside the
        # lock we re-check the latest payment so the SUCCESS/resume/resume cases
        # are decided against the current DB state.
        with _cart_lock(cart.id):
            existing_payment = (
                db.query(Payment)
                .filter(Payment.cart_id == cart.id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            if existing_payment and existing_payment.status == "SUCCESS":
                # CASE 4: already successfully paid (cart is "PAID"). Never
                # charge again — this guard runs before the cart-status check so
                # a re-request returns the completed response, not an error.
                return PaymentService._completed_response(db, existing_payment, cart)

            if existing_payment and existing_payment.status in ("PENDING", "PROCESSING"):
                # CASE 2: resume the existing active payment (no new Razorpay order).
                return PaymentService._resume_response(existing_payment, cart)

            if cart.status != "APPROVED_FOR_PAYMENT":
                return {"error": f"Payment not allowed. Cart status is {cart.status}. Cart must be APPROVED_FOR_PAYMENT."}

            # CASE 1 (no payment) and CASE 3 (existing FAILED/CANCELLED payment):
            # create a new payment attempt. FAILED/CANCELLED rows are kept as
            # history; the new row becomes the active attempt.
            provider = PaymentService._get_provider()
            provider_name = PaymentService.get_provider_name()

            provider_result = provider.create_payment(
                amount=total,
                currency="INR",
                metadata={"cart_id": cart.id, "session_id": session_id}
            )

            if not provider_result.get("success"):
                detail = provider_result.get("error", "Unknown provider error")
                return {"error": f"Failed to create payment with provider: {detail}"}

            payment = Payment(
                id=Payment.generate_id(),
                session_id=session_id,
                cart_id=cart.id,
                amount=total,
                currency="INR",
                payment_method=provider_name,
                status="PENDING",
                provider=provider_name,
                provider_payment_id=provider_result.get("provider_payment_id"),
                provider_order_id=provider_result.get("provider_order_id"),
            )

            db.add(payment)
            db.commit()
            db.refresh(payment)

        result = {
            "success": True,
            "payment_id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "payment_method": payment.payment_method,
            "provider": payment.provider,
            "cart_id": cart.id,
            "item_count": sum(item.quantity for item in cart.items),
        }

        if provider_name == "razorpay":
            result["razorpay_order_id"] = provider_result.get("provider_order_id")
            result["razorpay_key_id"] = provider_result.get("key_id")

        return result

    @staticmethod
    def _resume_response(payment: Payment, cart: Cart) -> Dict[str, Any]:
        """Return an existing PENDING/PROCESSING payment so the frontend can
        resume it (reusing the same Razorpay order) instead of throwing an error."""
        result = {
            "success": True,
            "resumed": True,
            "payment_id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "payment_method": payment.payment_method,
            "provider": payment.provider,
            "cart_id": cart.id,
            "item_count": sum(item.quantity for item in cart.items),
        }
        if payment.provider == "razorpay" and payment.provider_order_id:
            result["razorpay_order_id"] = payment.provider_order_id
            result["razorpay_key_id"] = PaymentService._get_razorpay_key_id()
        return result

    @staticmethod
    def _get_razorpay_key_id() -> Optional[str]:
        try:
            from services.razorpay_payment_provider import RazorpayPaymentProvider
            return os.getenv("RAZORPAY_KEY_ID")
        except Exception:
            return None

    @staticmethod
    def _completed_response(db: Session, payment: Payment, cart: Cart) -> Dict[str, Any]:
        """Return the already-completed payment plus its order so the frontend can
        redirect the user to the completed purchase instead of double charging."""
        order = (
            db.query(Order)
            .filter(Order.cart_id == cart.id, Order.status.in_(["CREATED", "CONFIRMED"]))
            .first()
        )
        result = {
            "success": True,
            "already_completed": True,
            "payment_id": payment.id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "cart_id": cart.id,
            "order_id": order.id if order else None,
        }
        return result

    @staticmethod
    def _get_active_payment(db: Session, cart_id: str) -> Optional[Payment]:
        """The most recent active payment for a cart (PENDING/PROCESSING/SUCCESS)."""
        return (
            db.query(Payment)
            .filter(
                Payment.cart_id == cart_id,
                Payment.status.in_(["PENDING", "PROCESSING", "SUCCESS"]),
            )
            .order_by(Payment.created_at.desc())
            .first()
        )

    @staticmethod
    def process_simulated_payment(db: Session, payment_id: str) -> Dict[str, Any]:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}

        if payment.status not in ["PENDING"]:
            return {"error": f"Payment cannot be processed. Current status: {payment.status}"}

        payment.status = "PROCESSING"
        db.commit()

        provider = PaymentService._get_provider()
        provider_result = provider.process_payment(payment.provider_payment_id)

        if provider_result.get("success"):
            payment.status = "SUCCESS"
            db.commit()
            db.refresh(payment)

            return {
                "success": True,
                "payment_id": payment.id,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "provider_payment_id": payment.provider_payment_id,
                "message": "Payment processed successfully"
            }
        else:
            payment.status = "FAILED"
            db.commit()
            db.refresh(payment)

            return {
                "success": False,
                "error": "Payment processing failed",
                "payment_id": payment.id,
                "status": payment.status
            }

    @staticmethod
    def verify_razorpay_payment(
        db: Session,
        payment_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Dict[str, Any]:
        """Verify a Razorpay payment signature and finalize the payment."""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}

        if payment.status == "SUCCESS":
            return {"error": "Payment already completed"}

        if payment.status not in ["PENDING", "PROCESSING"]:
            return {"error": f"Payment cannot be verified. Current status: {payment.status}"}

        payment.status = "PROCESSING"
        payment.provider_payment_id = razorpay_payment_id
        payment.payment_signature = razorpay_signature
        db.commit()

        provider = PaymentService._get_provider()

        if not hasattr(provider, "verify_payment"):
            return {"error": "Provider does not support payment verification"}

        verify_result = provider.verify_payment(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

        if verify_result.get("success") and verify_result.get("verified"):
            payment.status = "SUCCESS"
            db.commit()
            db.refresh(payment)

            return {
                "success": True,
                "payment_id": payment.id,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "provider_payment_id": razorpay_payment_id,
                "message": "Payment verified successfully"
            }
        else:
            payment.status = "FAILED"
            db.commit()
            db.refresh(payment)

            return {
                "success": False,
                "error": verify_result.get("error", "Payment verification failed"),
                "payment_id": payment.id,
                "status": payment.status,
            }

    @staticmethod
    def get_payment(db: Session, payment_id: str) -> Optional[Dict[str, Any]]:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return None

        return {
            "payment_id": payment.id,
            "session_id": payment.session_id,
            "cart_id": payment.cart_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "status": payment.status,
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "provider_order_id": payment.provider_order_id,
            "created_at": payment.created_at,
            "updated_at": payment.updated_at
        }

    @staticmethod
    def cancel_payment(db: Session, payment_id: str) -> Dict[str, Any]:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}

        if payment.status in ["SUCCESS"]:
            return {"error": "Cannot cancel a completed payment"}

        if payment.status in ["CANCELLED"]:
            return {"error": "Payment is already cancelled"}

        if payment.provider_payment_id:
            provider = PaymentService._get_provider()
            provider.cancel_payment(payment.provider_payment_id)

        payment.status = "CANCELLED"
        db.commit()
        db.refresh(payment)

        return {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status,
            "message": "Payment cancelled"
        }

    @staticmethod
    def get_payments_by_session(db: Session, session_id: str):
        return db.query(Payment).filter(
            Payment.session_id == session_id
        ).order_by(Payment.created_at.desc()).all()

    @staticmethod
    def get_payment_by_cart(db: Session, cart_id: str):
        return db.query(Payment).filter(
            Payment.cart_id == cart_id,
            Payment.status.in_(["PENDING", "PROCESSING", "SUCCESS"])
        ).first()
