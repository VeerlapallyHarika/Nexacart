from sqlalchemy.orm import Session
from models.decision_trace import DecisionTrace
from models.event import AuditEvent
from services.event_service import EventService
from services.order_service import OrderService
from services.cart_service import CartService
from typing import Dict, Any, Optional, List
import uuid


# Human-readable prefix for every decision trace id, e.g. DEC-NX-8F2A91
_DECISION_PREFIX = "DEC"


def _random_segment(length: int = 6) -> str:
    """Uppercase alphanumerics (no ambiguity-prone chars) for a readable ID."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    import secrets
    return "".join(secrets.choice(alphabet) for _ in range(length))


class DecisionTraceService:
    # Trace status values
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_INTERRUPTED = "INTERRUPTED"
    STATUS_FAILED = "FAILED"

    # Public status values used on the composed events
    EV_STATUS_SUCCESS = "SUCCESS"
    EV_STATUS_PENDING = "PENDING"
    EV_STATUS_WARNING = "WARNING"
    EV_STATUS_ERROR = "ERROR"

    # ── Decision ID generation ─────────────────────────────────────────
    @staticmethod
    def generate_decision_id() -> str:
        """Return a unique, human-readable, frontend-safe Decision ID.

        Format: ``DEC-<REGION>-<CODE>``, e.g. ``DEC-NX-8F2A91``. The short region
        token disambiguates deployments; the random segment guarantees uniqueness
        while staying readable. Stored on the DecisionTrace row so it persists.
        """
        return f"{_DECISION_PREFIX}-NX-{_random_segment()}"

    # ── Trace lifecycle ────────────────────────────────────────────────
    @staticmethod
    def get_trace(
        db: Session, decision_id: str, user_id: Optional[str] = None
    ) -> Optional[DecisionTrace]:
        query = db.query(DecisionTrace).filter(DecisionTrace.decision_id == decision_id)
        trace = query.first()
        if not trace:
            return None
        # User ownership verification: if trace belongs to a specific user and user_id is provided
        if user_id and trace.user_id and trace.user_id != user_id:
            return None
        return trace

    @staticmethod
    def get_trace_by_session(
        db: Session, session_id: str, user_id: Optional[str] = None
    ) -> Optional[DecisionTrace]:
        query = db.query(DecisionTrace).filter(DecisionTrace.session_id == session_id)
        if user_id:
            query = query.filter((DecisionTrace.user_id == user_id) | (DecisionTrace.user_id.is_(None)))
        return query.order_by(DecisionTrace.id.desc()).first()

    @staticmethod
    def create_new_trace(
        db: Session, session_id: str, goal: Optional[str] = None, user_id: Optional[str] = None
    ) -> DecisionTrace:
        """Explicitly create a new, distinct decision trace for a session / goal."""
        trace = DecisionTrace(
            decision_id=DecisionTraceService.generate_decision_id(),
            session_id=session_id,
            status=DecisionTraceService.STATUS_IN_PROGRESS,
            goal=goal,
            user_id=user_id,
        )
        db.add(trace)
        db.commit()
        db.refresh(trace)
        return trace

    @staticmethod
    def get_or_create_trace(
        db: Session, session_id: str, goal: Optional[str] = None, user_id: Optional[str] = None
    ) -> DecisionTrace:
        """Return the active decision trace for a session, creating one if needed."""
        trace = DecisionTraceService.get_trace_by_session(db, session_id, user_id=user_id)
        if trace:
            if goal and not trace.goal:
                trace.goal = goal
                db.commit()
            if user_id and not trace.user_id:
                trace.user_id = user_id
                db.commit()
            return trace

        return DecisionTraceService.create_new_trace(db, session_id=session_id, goal=goal, user_id=user_id)

    # ── Linking the trace to real entities as the journey progresses ──
    @staticmethod
    def _link(db: Session, trace: DecisionTrace, links: Dict[str, Any]) -> DecisionTrace:
        changed = False
        for key in ("product_id", "cart_id", "payment_id", "order_id", "user_id"):
            val = links.get(key)
            if val and getattr(trace, key) != val:
                setattr(trace, key, val)
                changed = True
        if changed:
            db.commit()
            db.refresh(trace)
        return trace

    # ── Auto-hook used by EventService.log_event ──────────────────────
    @staticmethod
    def record_event(db: Session, session_id: str, event: AuditEvent) -> None:
        """Attach a freshly-created audit event to the session's decision trace
        and advance the trace status/links. Called from EventService.log_event so
        every existing journey event automatically joins the trace."""
        if not session_id:
            return
        try:
            trace = DecisionTraceService.get_or_create_trace(db, session_id)
        except Exception:
            return

        trace_id = trace.decision_id

        links = DecisionTraceService._extract_links(event.event_type, event.data or {})

        # Set the trace's opening goal from the first user request if not yet set.
        if not trace.goal and event.event_type in ("USER_MESSAGE", "BUYER_GOAL_UNDERSTOOD"):
            goal = (event.data or {}).get("message") or (event.data or {}).get("goal")
            if goal:
                trace.goal = goal

        DecisionTraceService._advance_status(trace, event.event_type, event.data or {})

        # Attach the decision_id to the audit row so replay/->trace lookups work.
        if event.decision_id != trace_id:
            event.decision_id = trace_id

        DecisionTraceService._link(db, trace, links)
        # Always persist the decision_id on the audit row.
        db.commit()

    @staticmethod
    def _extract_links(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        links: Dict[str, Any] = {}
        if data.get("product_id"):
            links["product_id"] = data["product_id"]
        if data.get("product_ids") and not links.get("product_id"):
            links["product_id"] = data["product_ids"][0]
        if event_type in ("PRODUCT_ADDED_TO_CART", "CART_ITEM_UPDATED", "CART_VERIFIED"):
            links["cart_id"] = data.get("cart_id")
        if "payment_id" in data:
            links["payment_id"] = data["payment_id"]
        if event_type in ("ORDER_CREATED", "ORDER_CONFIRMED", "PURCHASE_COMPLETED") and data.get("order_id"):
            links["order_id"] = data.get("order_id")
        if event_type == "ORDER_CREATED" and data.get("payment_id"):
            links["payment_id"] = data.get("payment_id")
        if "user_id" in data and data.get("user_id"):
            links["user_id"] = data["user_id"]
        return links

    @staticmethod
    def _advance_status(trace: DecisionTrace, event_type: str, data: Dict[str, Any]) -> None:
        if event_type in ("PAYMENT_SUCCESS", "ORDER_CREATED", "ORDER_CONFIRMED", "PURCHASE_COMPLETED"):
            if event_type == "PAYMENT_SUCCESS":
                trace.payment_id = data.get("payment_id") or trace.payment_id
            if event_type == "ORDER_CREATED" and data.get("order_id"):
                trace.order_id = data.get("order_id")
            trace.status = DecisionTraceService.STATUS_COMPLETED
            return
        if event_type in ("PAYMENT_FAILED", "PAYMENT_CANCELLED", "BUYER_AGENT_ERROR") and trace.status != DecisionTraceService.STATUS_COMPLETED:
            trace.status = DecisionTraceService.STATUS_INTERRUPTED
            return
        if trace.status not in (DecisionTraceService.STATUS_COMPLETED,):
            trace.status = DecisionTraceService.STATUS_IN_PROGRESS

    # ── Composing the human/technical trace view ──────────────────────
    @staticmethod
    def compose_trace(
        db: Session, decision_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        trace = DecisionTraceService.get_trace(db, decision_id, user_id=user_id)
        if not trace:
            return None

        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.decision_id == decision_id)
            .order_by(AuditEvent.created_at, AuditEvent.id)
            .all()
        )

        composed = []
        for ev in events:
            step = DecisionTraceService._map_event(ev.event_type, ev.actor or "user", ev.summary or "", ev.data or {}, ev.id)
            if step is not None:
                composed.append(step)

        # Recompute a safe overall status from the trace + events.
        status = DecisionTraceService._resolve_status(trace, events)

        goal = trace.goal
        return {
            "decision_id": decision_id,
            "session_id": trace.session_id,
            "status": status,
            "goal": goal,
            "summary": DecisionTraceService._overall_summary(db, decision_id, status),
            "links": {
                "product_id": trace.product_id,
                "cart_id": trace.cart_id,
                "payment_id": trace.payment_id,
                "order_id": trace.order_id,
                "user_id": trace.user_id,
            },
            "events": composed,
            "created_at": trace.created_at,
            "updated_at": trace.updated_at,
        }

    @staticmethod
    def _resolve_status(trace: DecisionTrace, events: List[AuditEvent]) -> str:
        if trace.status == DecisionTraceService.STATUS_COMPLETED:
            return DecisionTraceService.STATUS_COMPLETED
        if trace.status == DecisionTraceService.STATUS_INTERRUPTED:
            return DecisionTraceService.STATUS_INTERRUPTED
        # Nothing meaningful -> not yet started; otherwise in progress.
        if not events:
            return DecisionTraceService.STATUS_IN_PROGRESS
        return DecisionTraceService.STATUS_IN_PROGRESS

    @staticmethod
    def _overall_summary(db: Session, decision_id: str, status: str) -> str:
        trace = DecisionTraceService.get_trace(db, decision_id)
        if not trace:
            return ""
        if status == DecisionTraceService.STATUS_COMPLETED:
            return "This purchase journey was completed end-to-end."
        if status == DecisionTraceService.STATUS_INTERRUPTED:
            return "This journey was interrupted before completion. You can resume it at any time."
        return "This journey is in progress."

    # ── Per-event presentation (extensible via decision_trace_mapping) ──
    @staticmethod
    def _map_event(
        event_type: str,
        actor: str,
        summary: str,
        data: Dict[str, Any],
        audit_event_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Turn one audit event into a trace step, or None to omit it.

        Lookup happens in the data-driven mapping module. Nonexistent handlers
        fall back to a safe generic entry so unknown/future event types never
        break the trace.
        """
        from services.decision_trace_mapping import map_event, ACTOR_AI, ACTOR_USER, ACTOR_SYSTEM

        entry = map_event(event_type)
        if entry is None:
            return None

        try:
            summary_text = entry["summary_fn"](data, summary)
        except Exception:
            summary_text = summary or event_type.replace("_", " ").title()

        explanation = None
        expl_fn = entry.get("explanation_fn")
        if expl_fn:
            try:
                explanation = expl_fn(data)
            except Exception:
                explanation = None

        actor_bucket = entry.get("actor", ACTOR_SYSTEM)

        return {
            "event_type": event_type,
            "registry_type": entry.get("registry", "UNKNOWN"),
            "actor": actor_bucket,
            "status": entry.get("status", DecisionTraceService.EV_STATUS_SUCCESS),
            "title": entry.get("title", event_type.replace("_", " ").title()),
            "summary": summary_text,
            "explanation": explanation,
            "ref_audit_event_id": audit_event_id,
        }

    @staticmethod
    def compose_by_session(db: Session, session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        trace = DecisionTraceService.get_trace_by_session(db, session_id, user_id=user_id)
        if not trace:
            return None
        return DecisionTraceService.compose_trace(db, trace.decision_id, user_id=user_id)

    @staticmethod
    def compose_by_order(db: Session, order_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        order = OrderService.get_order(db, order_id)
        if not order:
            return None
        trace = DecisionTraceService.get_trace_by_session(db, order["session_id"], user_id=user_id)
        if not trace:
            return None
        # Ensure the trace links to this order even if the order event predates
        # trace linking.
        if trace.order_id != order_id:
            trace.order_id = order_id
            trace.payment_id = order.get("payment_id") or trace.payment_id
            trace.status = DecisionTraceService.STATUS_COMPLETED
            db.commit()
        return DecisionTraceService.compose_trace(db, trace.decision_id, user_id=user_id)
