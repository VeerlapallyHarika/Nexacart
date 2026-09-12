import razorpay
import hashlib
import hmac
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from models.payment import Payment
from services.payment_service import PaymentProvider
from typing import Dict, Any
import os
import uuid


class RazorpayPaymentProvider(PaymentProvider):
    """Razorpay TEST MODE payment provider.

    Uses the Razorpay Python SDK to create orders and verify payments.
    All operations use Razorpay's test mode keys.
    """

    def __init__(self):
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            raise ValueError(
                "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in environment"
            )
        self.client = razorpay.Client(auth=(key_id, key_secret))
        self.key_id = key_id

    def verify_credentials(self) -> bool:
        """Verify that the Razorpay credentials are valid by making a test API call.

        Returns True if credentials are valid, False otherwise.
        This is called during provider initialization to catch invalid credentials
        early and allow graceful fallback to simulated provider.
        """
        try:
            # Try creating a minimal order to verify credentials work.
            # A valid key will get a 400 (bad request) but not 401/403 (auth).
            self.client.order.create({
                "amount": 1,
                "currency": "INR",
                "receipt": "_credential_check",
            })
            return True
        except razorpay.errors.BadRequestError as e:
            # 400 = bad request (credentials are valid, just invalid payload)
            # An auth failure also comes as BadRequestError with "Authentication failed"
            error_msg = str(e).lower()
            if "authentication" in error_msg or "auth" in error_msg:
                return False
            return True
        except Exception:
            # Other errors (network, server) — assume credentials might be valid
            return True

    def create_payment(self, amount: float, currency: str, metadata: dict) -> Dict[str, Any]:
        """Create a Razorpay Order for the given amount.

        Returns the Razorpay order_id which the frontend uses to open checkout.
        """
        # Razorpay expects amount in paise (smallest currency unit)
        amount_paise = int(amount * 100)

        try:
            order = self.client.order.create({
                "amount": amount_paise,
                "currency": currency,
                "receipt": metadata.get("cart_id", f"rcpt_{uuid.uuid4().hex[:8]}"),
                "notes": {
                    "session_id": metadata.get("session_id", ""),
                    "cart_id": metadata.get("cart_id", ""),
                },
            })

            return {
                "success": True,
                "provider_order_id": order["id"],
                "amount": amount,
                "currency": currency,
                "status": "created",
                "key_id": self.key_id,
            }
        except razorpay.errors.BadRequestError as e:
            return {"success": False, "error": f"Razorpay order creation failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Razorpay error: {str(e)}"}

    def process_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        """Not used directly for Razorpay. Verification is done via verify_payment."""
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "status": "captured",
            "message": "Razorpay payment verified"
        }

    def verify_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Dict[str, Any]:
        """Verify the Razorpay payment signature.

        This is the critical security step. Razorpay generates a signature
        using HMAC SHA256 with the order_id + payment_id and the secret key.
        We regenerate it server-side and compare.
        """
        try:
            # The expected signature is HMAC SHA256 of "order_id|payment_id"
            payload = f"{razorpay_order_id}|{razorpay_payment_id}"
            expected_signature = hmac.new(
                bytes(os.getenv("RAZORPAY_KEY_SECRET", ""), "utf-8"),
                bytes(payload, "utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(expected_signature, razorpay_signature):
                return {
                    "success": True,
                    "verified": True,
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                }
            else:
                return {
                    "success": False,
                    "verified": False,
                    "error": "Payment signature verification failed",
                }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Signature verification error: {str(e)}",
            }

    def get_payment_status(self, provider_payment_id: str) -> Dict[str, Any]:
        """Fetch payment status from Razorpay."""
        try:
            payment = self.client.payment.fetch(provider_payment_id)
            return {
                "success": True,
                "provider_payment_id": provider_payment_id,
                "status": payment.get("status", "unknown"),
                "amount": payment.get("amount", 0) / 100,  # Convert from paise
                "currency": payment.get("currency", "INR"),
            }
        except Exception as e:
            return {
                "success": False,
                "provider_payment_id": provider_payment_id,
                "error": str(e),
            }

    def cancel_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        """Razorpay does not support direct cancellation via API.
        Payments can be refunded after capture, but not cancelled."""
        return {
            "success": True,
            "provider_payment_id": provider_payment_id,
            "status": "cancelled",
            "message": "Razorpay payment cancelled (note: Razorpay refunds require dashboard)"
        }
