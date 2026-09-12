from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base
import uuid


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(50), primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    cart_id = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    payment_method = Column(String(50), default="simulated")
    status = Column(String(30), default="PENDING")
    provider = Column(String(50), default="simulated")
    provider_payment_id = Column(String(200), nullable=True)
    provider_order_id = Column(String(200), nullable=True)
    payment_signature = Column(String(500), nullable=True)
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())

    @staticmethod
    def generate_id():
        return f"pay_{uuid.uuid4().hex[:12]}"
