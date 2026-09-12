from sqlalchemy import Column, String, Text, Integer, JSON
from sqlalchemy.sql import func
from database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    # Optional linkage of this audit event to a persistent commerce decision
    # trace (see DecisionTrace). Nullable so legacy/unchanged rows are untouched.
    decision_id = Column(String(50), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(50), default="user")
    summary = Column(Text)
    data = Column(JSON, default=dict)
    created_at = Column(String(50), server_default=func.now())
