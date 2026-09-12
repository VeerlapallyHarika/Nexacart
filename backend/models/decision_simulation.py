from sqlalchemy import Column, String, Text, Integer, JSON
from sqlalchemy.sql import func
from database import Base


class DecisionSimulation(Base):
    """A what-if simulation branch off an existing Decision Trace.

    Each simulation stores:
    - which trace it branches from (decision_id)
    - a snapshot of the original constraints
    - the modified constraints
    - the full simulation result (new recommendation, alternatives, explanation, contract warnings)
    - its lifecycle status

    The original Decision Trace is never modified.
    """

    __tablename__ = "decision_simulations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String(50), unique=True, nullable=False, index=True)
    decision_id = Column(String(50), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    simulation_number = Column(Integer, default=1)
    label = Column(Text, nullable=True)
    original_constraints = Column(JSON, default=dict)
    modified_constraints = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    contract_warnings = Column(JSON, default=list)
    status = Column(String(30), default="COMPLETED")
    created_at = Column(String(50), server_default=func.now())
