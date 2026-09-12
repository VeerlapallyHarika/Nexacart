from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(String(50), primary_key=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(30), default="ACTIVE")
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())

    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    def calculate_total(self):
        total = 0
        for item in self.items:
            if item.product:
                total += item.product.price * item.quantity
        return total


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(String(50), primary_key=True)
    cart_id = Column(String(50), ForeignKey("carts.id"), nullable=False)
    product_id = Column(String(50), ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    created_at = Column(String(50), server_default=func.now())

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
