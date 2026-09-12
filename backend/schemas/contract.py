from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ContractPayload(BaseModel):
    goal: Optional[str] = None
    max_budget: Optional[float] = None
    currency: Optional[str] = None
    required_categories: Optional[List[str]] = None
    required_attributes: Optional[Dict[str, Any]] = None
    minimum_battery_hours: Optional[int] = None
    battery_hours_min: Optional[int] = None
    excluded_conditions: Optional[List[str]] = None
    allowed_actions: Optional[List[str]] = None
    status: Optional[str] = None
    activate: Optional[bool] = False


class ContractCheckRequest(BaseModel):
    action: str
    product_id: Optional[str] = None
    max_price: Optional[float] = None
    category: Optional[str] = None
