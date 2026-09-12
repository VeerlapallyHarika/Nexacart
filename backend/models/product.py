from sqlalchemy import Column, String, Text, Float, Integer, JSON
from sqlalchemy.sql import func
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    category = Column(String(100), nullable=False)
    attributes = Column(JSON, default=dict)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(String(50), server_default=func.now())
    updated_at = Column(String(50), server_default=func.now(), onupdate=func.now())
