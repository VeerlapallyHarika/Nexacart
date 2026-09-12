from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.sql import func
from database import Base


class DecisionTrace(Base):
    """Persistent header for a single commerce decision journey.

    A decision trace groups all of the real audit events for a shopping journey
    (user request -> intent -> discovery -> buyer agent -> recommendation ->
    user decision -> contract -> cart -> payment -> order) under one stable,
    human-readable Decision ID. It is deliberately light: the actual event data
    stays in the existing ``audit_events`` table (the single source of truth),
    and this row only tracks the trace's identity, status and the most relevant
    linked entities (cart / payment / order / product).
    """

    __tablename__ = "decision_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(50), unique=True, nullable=False, index=True)
    session_id = Column(String(100), unique=False, nullable=False, index=True)
    status = Column(String(30), default="IN_PROGRESS")
    # Human-readable overall goal / user request that opened the journey.
    goal = Column(Text, nullable=True)
    # Most-relevant links, updated as the journey progresses.
    product_id = Column(String(50), nullable=True, index=True)
    cart_id = Column(String(50), nullable=True, index=True)
    payment_id = Column(String(50), nullable=True, index=True)
    order_id = Column(String(50), nullable=True, index=True)
    user_id = Column(String(50), nullable=True, index=True)
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())
