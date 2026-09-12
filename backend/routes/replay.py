from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.replay_service import ReplayService
from services.event_service import EventService

router = APIRouter()


@router.get("/api/replay/{session_id}")
def get_replay(session_id: str, db: Session = Depends(get_db)):
    replay = ReplayService.get_purchase_replay(db=db, session_id=session_id)

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="REPLAY_VIEWED",
        actor="user",
        summary=f"User viewed purchase replay ({replay['total_steps']} steps)",
        data={"total_steps": replay["total_steps"], "status": replay["status"]},
    )

    return replay


@router.get("/api/replay/order/{order_id}")
def get_order_replay(order_id: str, db: Session = Depends(get_db)):
    replay = ReplayService.get_order_replay(db=db, order_id=order_id)
    if not replay:
        raise HTTPException(status_code=404, detail="Order not found")

    EventService.log_event(
        db=db,
        session_id=replay["session_id"],
        event_type="REPLAY_VIEWED",
        actor="user",
        summary=f"User viewed order replay for {order_id}",
        data={"order_id": order_id, "total_steps": replay["total_steps"]},
    )

    return replay
