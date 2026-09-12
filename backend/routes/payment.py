from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from services.payment_service import PaymentService
from services.order_service import OrderService
from services.event_service import EventService

router = APIRouter()


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/api/payment/create")
def create_payment(session_id: str, db: Session = Depends(get_db)):
    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="PAYMENT_INTENT_REQUESTED",
        actor="user",
        summary="User requested payment creation",
        data={}
    )

    result = PaymentService.create_payment_intent(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if result.get("already_completed"):
        # CASE 4: this cart was already paid for. Return a clear, non-error
        # response pointing at the completed payment/order so the frontend never
        # tries to charge the user again.
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="PAYMENT_ALREADY_COMPLETED",
            actor="agent",
            summary="Payment already completed for this cart — not charging again",
            data={
                "payment_id": result["payment_id"],
                "order_id": result.get("order_id"),
                "amount": result["amount"],
            }
        )
        return result

    if result.get("resumed"):
        # CASE 2: resume an existing PENDING/PROCESSING payment (reusing its
        # Razorpay order if applicable).
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="PAYMENT_RESUMED",
            actor="agent",
            summary=f"Resumed existing payment {result['payment_id']}",
            data={
                "payment_id": result["payment_id"],
                "amount": result["amount"],
                "provider": result.get("provider", "simulated"),
            }
        )
        if result.get("razorpay_order_id"):
            EventService.log_event(
                db=db,
                session_id=session_id,
                event_type="RAZORPAY_ORDER_REUSED",
                actor="agent",
                summary=f"Reused existing Razorpay order: {result['razorpay_order_id']}",
                data={
                    "payment_id": result["payment_id"],
                    "razorpay_order_id": result["razorpay_order_id"],
                }
            )
        return result

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="PAYMENT_CREATED",
        actor="agent",
        summary=f"Payment created: {result['payment_id']} for ₹{result['amount']}",
        data={
            "payment_id": result["payment_id"],
            "amount": result["amount"],
            "currency": result["currency"],
            "cart_id": result["cart_id"],
            "provider": result.get("provider", "simulated"),
        }
    )

    if result.get("razorpay_order_id"):
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="RAZORPAY_ORDER_CREATED",
            actor="agent",
            summary=f"Razorpay order created: {result['razorpay_order_id']}",
            data={
                "payment_id": result["payment_id"],
                "razorpay_order_id": result["razorpay_order_id"],
            }
        )

    return result


@router.post("/api/payment/{payment_id}/confirm")
def confirm_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = PaymentService.get_payment(db=db, payment_id=payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.get("provider") == "razorpay":
        raise HTTPException(
            status_code=400,
            detail="Razorpay payments must be verified via /api/payment/{id}/verify"
        )

    EventService.log_event(
        db=db,
        session_id=payment["session_id"],
        event_type="PAYMENT_PROCESSING",
        actor="user",
        summary=f"User confirmed payment {payment_id}",
        data={"payment_id": payment_id, "amount": payment["amount"]}
    )

    result = PaymentService.process_simulated_payment(db=db, payment_id=payment_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if result["success"]:
        EventService.log_event(
            db=db,
            session_id=payment["session_id"],
            event_type="PAYMENT_SUCCESS",
            actor="agent",
            summary=f"Payment {payment_id} completed successfully",
            data={
                "payment_id": payment_id,
                "amount": result["amount"],
                "currency": result["currency"],
                "provider_payment_id": result["provider_payment_id"]
            }
        )

        order_result = OrderService.create_order_from_cart(
            db=db,
            session_id=payment["session_id"],
            payment_id=payment_id
        )

        if order_result.get("success"):
            EventService.log_event(
                db=db,
                session_id=payment["session_id"],
                event_type="ORDER_CREATED",
                actor="agent",
                summary=f"Order {order_result['order_id']} created from successful payment",
                data={
                    "order_id": order_result["order_id"],
                    "payment_id": payment_id,
                    "total_amount": order_result["total_amount"]
                }
            )

            EventService.log_event(
                db=db,
                session_id=payment["session_id"],
                event_type="ORDER_CONFIRMED",
                actor="agent",
                summary=f"Order {order_result['order_id']} confirmed",
                data={"order_id": order_result["order_id"], "status": "CONFIRMED"}
            )

            result["order"] = order_result
    else:
        EventService.log_event(
            db=db,
            session_id=payment["session_id"],
            event_type="PAYMENT_FAILED",
            actor="agent",
            summary=f"Payment {payment_id} failed",
            data={"payment_id": payment_id, "error": result.get("error")}
        )

    return result


@router.post("/api/payment/{payment_id}/verify")
def verify_razorpay_payment(
    payment_id: str,
    payload: RazorpayVerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify a Razorpay payment after frontend checkout completes."""
    payment = PaymentService.get_payment(db=db, payment_id=payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    EventService.log_event(
        db=db,
        session_id=payment["session_id"],
        event_type="PAYMENT_VERIFICATION_STARTED",
        actor="user",
        summary=f"User submitted Razorpay verification for payment {payment_id}",
        data={
            "payment_id": payment_id,
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
        }
    )

    result = PaymentService.verify_razorpay_payment(
        db=db,
        payment_id=payment_id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )

    if "error" in result:
        EventService.log_event(
            db=db,
            session_id=payment["session_id"],
            event_type="PAYMENT_FAILED",
            actor="agent",
            summary=f"Payment verification failed for {payment_id}",
            data={"payment_id": payment_id, "error": result["error"]}
        )
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=payment["session_id"],
        event_type="PAYMENT_VERIFIED",
        actor="agent",
        summary=f"Payment {payment_id} verified successfully",
        data={
            "payment_id": payment_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "amount": result["amount"],
        }
    )

    if result["success"]:
        EventService.log_event(
            db=db,
            session_id=payment["session_id"],
            event_type="PAYMENT_SUCCESS",
            actor="agent",
            summary=f"Payment {payment_id} completed after Razorpay verification",
            data={
                "payment_id": payment_id,
                "amount": result["amount"],
                "currency": result["currency"],
                "provider_payment_id": result["provider_payment_id"]
            }
        )

        order_result = OrderService.create_order_from_cart(
            db=db,
            session_id=payment["session_id"],
            payment_id=payment_id
        )

        if order_result.get("success"):
            EventService.log_event(
                db=db,
                session_id=payment["session_id"],
                event_type="ORDER_CREATED",
                actor="agent",
                summary=f"Order {order_result['order_id']} created from verified Razorpay payment",
                data={
                    "order_id": order_result["order_id"],
                    "payment_id": payment_id,
                    "total_amount": order_result["total_amount"]
                }
            )

            EventService.log_event(
                db=db,
                session_id=payment["session_id"],
                event_type="ORDER_CONFIRMED",
                actor="agent",
                summary=f"Order {order_result['order_id']} confirmed",
                data={"order_id": order_result["order_id"], "status": "CONFIRMED"}
            )

            result["order"] = order_result

    return result


@router.post("/api/payment/{payment_id}/cancel")
def cancel_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = PaymentService.get_payment(db=db, payment_id=payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    result = PaymentService.cancel_payment(db=db, payment_id=payment_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=payment["session_id"],
        event_type="PAYMENT_CANCELLED",
        actor="user",
        summary=f"Payment {payment_id} cancelled",
        data={"payment_id": payment_id}
    )

    return result


@router.get("/api/payment/{payment_id}")
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = PaymentService.get_payment(db=db, payment_id=payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
