from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.cart_service import CartService
from services.checkout_service import CheckoutService
from services.event_service import EventService
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1


class UpdateCartItemRequest(BaseModel):
    quantity: int


@router.get("/api/cart/{session_id}")
def get_cart(session_id: str, db: Session = Depends(get_db)):
    cart = CartService.get_cart_details(db, session_id)
    if not cart:
        return {
            "cart_id": None,
            "session_id": session_id,
            "status": "ACTIVE",
            "items": [],
            "total": 0,
            "item_count": 0
        }

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_VIEWED",
        actor="user",
        summary="User viewed cart",
        data={"item_count": cart["item_count"], "total": cart["total"]}
    )

    return cart


@router.post("/api/cart/{session_id}/items")
def add_to_cart(
    session_id: str,
    request: AddToCartRequest,
    db: Session = Depends(get_db)
):
    result = CartService.add_to_cart(
        db=db,
        session_id=session_id,
        product_id=request.product_id,
        quantity=request.quantity
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="PRODUCT_ADDED_TO_CART",
        actor="user",
        summary=f"Added {result['item']['product_name']} to cart",
        data={
            "product_id": request.product_id,
            "product_name": result["item"]["product_name"],
            "quantity": request.quantity,
            "price": result["item"]["price"],
            "cart_total": result["cart_total"]
        }
    )

    return result


@router.patch("/api/cart/{session_id}/items/{item_id}")
def update_cart_item(
    session_id: str,
    item_id: str,
    request: UpdateCartItemRequest,
    db: Session = Depends(get_db)
):
    result = CartService.update_cart_item(
        db=db,
        session_id=session_id,
        item_id=item_id,
        quantity=request.quantity
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_ITEM_UPDATED",
        actor="user",
        summary=f"Updated cart item quantity to {request.quantity}",
        data={"item_id": item_id, "new_quantity": request.quantity}
    )

    return result


@router.delete("/api/cart/{session_id}/items/{item_id}")
def remove_cart_item(
    session_id: str,
    item_id: str,
    db: Session = Depends(get_db)
):
    result = CartService.remove_cart_item(
        db=db,
        session_id=session_id,
        item_id=item_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_ITEM_REMOVED",
        actor="user",
        summary="Removed item from cart",
        data={"item_id": item_id}
    )

    return result


@router.delete("/api/cart/{session_id}")
def clear_cart(session_id: str, db: Session = Depends(get_db)):
    result = CartService.clear_cart(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_CLEARED",
        actor="user",
        summary="Cart cleared",
        data={}
    )

    return result


@router.post("/api/cart/{session_id}/verify")
def verify_cart(session_id: str, db: Session = Depends(get_db)):
    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_VERIFICATION_STARTED",
        actor="user",
        summary="Cart verification requested",
        data={}
    )

    result = CheckoutService.verify_cart(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_VERIFIED" if result.get("verified") else "CART_VERIFICATION_FAILED",
        actor="agent",
        summary=f"Cart verification {'passed' if result.get('verified') else 'failed'}",
        data={
            "verified": result.get("verified"),
            "total": result.get("total"),
            "item_count": result.get("item_count")
        }
    )

    return result


@router.post("/api/cart/{session_id}/request-approval")
def request_checkout_approval(session_id: str, db: Session = Depends(get_db)):
    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CHECKOUT_APPROVAL_REQUESTED",
        actor="user",
        summary="Checkout approval requested",
        data={}
    )

    result = CheckoutService.request_approval(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/api/cart/{session_id}/approve")
def approve_checkout(session_id: str, db: Session = Depends(get_db)):
    result = CheckoutService.approve_checkout(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="USER_APPROVED_CHECKOUT",
        actor="user",
        summary="User approved checkout for payment",
        data={
            "total": result.get("verification", {}).get("total"),
            "status": result.get("status")
        }
    )

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CART_APPROVED_FOR_PAYMENT",
        actor="system",
        summary="Cart approved for payment",
        data={"status": "APPROVED_FOR_PAYMENT"}
    )

    return result


@router.get("/api/cart/{session_id}/checkout-summary")
def get_checkout_summary(session_id: str, db: Session = Depends(get_db)):
    result = CheckoutService.get_checkout_summary(db=db, session_id=session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
