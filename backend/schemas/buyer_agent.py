from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class BuyerAgentRequest(BaseModel):
    goal: str
    session_id: str
    auto_approve: bool = False
    approve_product_id: Optional[str] = None
    run_id: Optional[str] = None


class BuyerAgentAction(BaseModel):
    step: int
    action: str
    input: Dict[str, Any] = {}
    output: Dict[str, Any] = {}
    timestamp: Optional[str] = None


class BuyerAgentResponse(BaseModel):
    run_id: str
    session_id: str
    decision_id: Optional[str] = None
    goal: str
    final_state: str  # recommendation_ready | ready_for_approval | blocked_by_contract | max_steps_reached
    reason: Optional[str] = None
    added_product_id: Optional[str] = None
    recommended_product_id: Optional[str] = None
    actions: List[BuyerAgentAction] = []
