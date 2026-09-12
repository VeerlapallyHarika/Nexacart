from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.user import User
from dependencies import get_current_user_optional
from services.decision_trace_service import DecisionTraceService
from services.event_service import EventService

router = APIRouter()


@router.get("/api/decision-traces/{decision_id}")
def get_decision_trace(
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user_id = str(current_user.id) if current_user else None
    trace = DecisionTraceService.compose_trace(db=db, decision_id=decision_id, user_id=user_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    return trace


@router.get("/api/decision-traces/session/{session_id}")
def get_session_decision_trace(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Return the current (most recent) decision trace for a session.

    This lets the frontend fetch the live trace for the active session without
    knowing the Decision ID up front.
    """
    user_id = str(current_user.id) if current_user else None
    trace = DecisionTraceService.compose_by_session(db=db, session_id=session_id, user_id=user_id)
    if not trace:
        raise HTTPException(status_code=404, detail="No decision trace found for this session")
    return trace


@router.get("/api/decision-traces/order/{order_id}")
def get_order_decision_trace(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user_id = str(current_user.id) if current_user else None
    trace = DecisionTraceService.compose_by_order(db=db, order_id=order_id, user_id=user_id)
    if not trace:
        raise HTTPException(status_code=404, detail="No decision trace found for this order")
    return trace
