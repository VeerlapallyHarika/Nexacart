from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(50), primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    cart_id = Column(String(50), nullable=False, index=True)
    payment_id = Column(String(50), nullable=False, index=True)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(String(30), default="CREATED")
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    @staticmethod
    def generate_id():
        return f"ord_{uuid.uuid4().hex[:12]}"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(50), primary_key=True)
    order_id = Column(String(50), ForeignKey("orders.id"), nullable=False)
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(200), nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")

    @staticmethod
    def generate_id():
        return f"oi_{uuid.uuid4().hex[:12]}"
