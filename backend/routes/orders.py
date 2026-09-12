from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.order import Order
from services.order_service import OrderService
from services.event_service import EventService
from dependencies import get_current_user_optional, get_current_user
from typing import Optional

router = APIRouter()


@router.get("/api/orders")
def get_orders(
    session_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Fetch orders for a session or authenticated user with authorization checks."""
    if current_user:
        # If user is logged in, fetch all orders belonging to this user
        user_orders = OrderService.get_orders_by_user(db=db, user_id=current_user.id)
        
        # If session_id provided, also check if there are anonymous orders in that session to associate
        if session_id:
            session_orders = db.query(Order).filter(Order.session_id == session_id).all()
            for so in session_orders:
                if so.user_id is None:
                    # Migrate anonymous order to current user
                    so.user_id = current_user.id
                    db.commit()
            # Refresh user orders
            user_orders = OrderService.get_orders_by_user(db=db, user_id=current_user.id)
            
        EventService.log_event(
            db=db,
            session_id=session_id or f"user_{current_user.id}",
            event_type="ORDERS_VIEWED",
            actor="user",
            summary=f"User {current_user.email} viewed {len(user_orders)} orders",
            data={"order_count": len(user_orders), "user_id": current_user.id}
        )
        return {"orders": user_orders, "count": len(user_orders)}

    # Unauthenticated flow: require session_id
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication or session_id required to view orders"
        )

    orders = OrderService.get_orders_by_session(db=db, session_id=session_id)
    
    # Check if any of these orders belong to a registered user
    for o in orders:
        if o.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="These orders belong to a registered user. Please log in to view them."
            )

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="ORDERS_VIEWED",
        actor="user",
        summary=f"Anonymous user viewed {len(orders)} orders",
        data={"order_count": len(orders)}
    )

    return {"orders": orders, "count": len(orders)}


@router.get("/api/orders/{order_id}")
def get_order(
    order_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get single order with ownership validation."""
    order = OrderService.get_order(db=db, order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # If the order is owned by a user, enforce authorization
    if order.get("user_id"):
        if not current_user or current_user.id != order["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this order"
            )

    EventService.log_event(
        db=db,
        session_id=order["session_id"],
        event_type="ORDER_VIEWED",
        actor="user",
        summary=f"User viewed order {order_id}",
        data={"order_id": order_id, "status": order["status"]}
    )

    return order
