from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class DecisionLabConstraint(BaseModel):
    key: str
    value: Any = None
    operator: str = "eq"


class SimulateRequest(BaseModel):
    session_id: str
    label: Optional[str] = None
    category: Optional[str] = None
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    brand: Optional[str] = None
    constraints: Optional[List[DecisionLabConstraint]] = None


class CompareRequest(BaseModel):
    product_a_id: str
    product_b_id: str


class ApplyRequest(BaseModel):
    session_id: str
    product_id: Optional[str] = None
