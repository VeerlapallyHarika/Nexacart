from pydantic import BaseModel
from typing import Optional, Dict, Any


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    currency: str = "INR"
    category: str
    attributes: Dict[str, Any] = {}
    stock_quantity: int = 0


class ProductCreate(ProductBase):
    id: str


class ProductResponse(ProductBase):
    id: str

    class Config:
        from_attributes = True
