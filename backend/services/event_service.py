from sqlalchemy.orm import Session
from models.event import AuditEvent
from typing import List, Dict, Any, Optional
import uuid


class EventService:
    @staticmethod
    def log_event(
        db: Session,
        session_id: str,
        event_type: str,
        actor: str,
        summary: str,
        data: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        event = AuditEvent(
            session_id=session_id,
            event_type=event_type,
            actor=actor,
            summary=summary,
            data=data or {}
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Attach this real event to the session's persistent Decision Trace so
        # every system (chat, discovery, buyer agent, contract, cart, payment,
        # orders) joins one connected, explainable journey. This is additive and
        # never alters the event's own data.
        try:
            from services.decision_trace_service import DecisionTraceService
            DecisionTraceService.record_event(db, session_id, event)
        except Exception:
            db.rollback()

        return event

    @staticmethod
    def get_events_by_session(db: Session, session_id: str) -> List[AuditEvent]:
        return db.query(AuditEvent).filter(
            AuditEvent.session_id == session_id
        ).order_by(AuditEvent.created_at).all()

    @staticmethod
    def generate_session_id() -> str:
        return f"session_{uuid.uuid4().hex[:12]}"
