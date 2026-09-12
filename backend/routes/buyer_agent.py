from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.user import User
from dependencies import get_current_user_optional
from schemas.buyer_agent import BuyerAgentRequest, BuyerAgentResponse
from services.buyer_agent import BuyerAgent

router = APIRouter()


@router.post("/buyer-agent/run", response_model=BuyerAgentResponse)
def run_buyer_agent(
    request: BuyerAgentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    agent = BuyerAgent()
    user_id = current_user.id if current_user else None
    result = agent.run(
        db,
        request.goal,
        request.session_id,
        user_id=user_id,
        auto_approve=request.auto_approve,
        approve_product_id=request.approve_product_id,
        run_id=request.run_id,
    )

    # Read the persisted structured log back from the buyer_agent_runs table
    # so the response reflects what was actually audited.
    actions = agent.get_run_log(db, result["run_id"])

    return BuyerAgentResponse(
        run_id=result["run_id"],
        session_id=result["session_id"],
        decision_id=result.get("decision_id"),
        goal=result["goal"],
        final_state=result["final_state"],
        reason=result.get("reason"),
        added_product_id=result.get("added_product_id"),
        recommended_product_id=result.get("recommended_product_id"),
        actions=actions,
    )
