from sqlalchemy import Column, String, Text, Integer, JSON
from sqlalchemy.sql import func
from database import Base


class BuyerAgentRun(Base):
    """Structured, per-step action log for the autonomous Buyer Agent.

    Each row is one autonomous action (search_products, add_to_cart, etc.),
    mirroring the step/action/input/output/timestamp shape requested. Rows are
    grouped by ``run_id`` so a single goal execution can be replayed from the
    audit trail.
    """

    __tablename__ = "buyer_agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    goal = Column(Text)
    step = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    input = Column(JSON, default=dict)
    output = Column(JSON, default=dict)
    timestamp = Column(String(50), server_default=func.now())
