from sqlalchemy import Column, String, Text, Float, Integer, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base
import uuid


class CommerceContract(Base):
    """A machine-enforceable boundary around the AI agent's commerce actions.

    The contract defines explicit rules (budget, requirements, restrictions)
    that the ContractValidator enforces deterministically on the backend,
    independent of the LLM. One ACTIVE contract is allowed per session.
    """

    __tablename__ = "commerce_contracts"

    STATUSES = ["DRAFT", "ACTIVE", "COMPLETED", "CANCELLED"]

    id = Column(String(50), primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(30), default="DRAFT")
    goal = Column(Text)
    max_budget = Column(Float, nullable=True)
    currency = Column(String(3), default="INR")
    required_categories = Column(JSON, default=list)
    required_attributes = Column(JSON, default=dict)
    minimum_battery_hours = Column(Integer, nullable=True)
    excluded_conditions = Column(JSON, default=list)
    allowed_actions = Column(JSON, default=list)
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())

    @staticmethod
    def generate_id():
        return f"contract_{uuid.uuid4().hex[:12]}"
