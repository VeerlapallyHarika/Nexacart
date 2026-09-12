from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: float
    currency: str = "INR"
    category: str
    attributes: Dict[str, Any] = {}
    stock_quantity: int = 0


class ChatResponse(BaseModel):
    message: str
    session_id: str
    intent: Optional[Dict[str, Any]] = None
    products: Optional[List[ProductResponse]] = None
