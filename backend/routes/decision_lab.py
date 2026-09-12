from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.user import User
from dependencies import get_current_user_optional
from services.decision_lab_service import DecisionLabService
from services.decision_trace_service import DecisionTraceService
from schemas.decision_lab import SimulateRequest, CompareRequest, ApplyRequest
from services.product_service import SearchConstraint

router = APIRouter()


def _validate_decision_access(
    db: Session, decision_id: str, user: Optional[User]
) -> None:
    """Ensure the decision trace exists and belongs to the authenticated user."""
    trace = DecisionTraceService.get_trace(db, decision_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    if user and trace.user_id and trace.user_id != user.id:
        raise HTTPException(status_code=404, detail="Decision trace not found")


@router.get("/api/decision-lab/{decision_id}/explain")
def explain_recommendation(
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    _validate_decision_access(db, decision_id, current_user)
    result = DecisionLabService.explain_recommendation(db, decision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Decision trace or recommendation not found")
    return result


@router.get("/api/decision-lab/{decision_id}/alternatives")
def get_alternatives(
    decision_id: str,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    _validate_decision_access(db, decision_id, current_user)
    result = DecisionLabService.get_alternatives(db, decision_id, limit=limit)
    if not result:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    return result


@router.post("/api/decision-lab/compare")
def compare_products(payload: CompareRequest, db: Session = Depends(get_db)):
    result = DecisionLabService.compare_products(
        db, payload.product_a_id, payload.product_b_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="One or both products not found")
    return result


@router.post("/api/decision-lab/{decision_id}/simulate")
def run_simulation(
    decision_id: str,
    payload: SimulateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    _validate_decision_access(db, decision_id, current_user)
    constraints = []
    if payload.constraints:
        for c in payload.constraints:
            constraints.append(
                SearchConstraint(
                    key=c.key,
                    value=c.value,
                    operator=c.operator,
                )
            )
    result = DecisionLabService.run_simulation(
        db=db,
        session_id=payload.session_id,
        decision_id=decision_id,
        label=payload.label,
        modified_category=payload.category,
        modified_max_price=payload.max_price,
        modified_min_price=payload.min_price,
        modified_brand=payload.brand,
        modified_constraints=constraints or None,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/decision-lab/simulations/{simulation_id}/apply")
def apply_simulation(
    simulation_id: str,
    payload: ApplyRequest,
    db: Session = Depends(get_db),
):
    result = DecisionLabService.apply_simulation(
        db, simulation_id, payload.session_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if "error" in result:
        raise HTTPException(
            status_code=400 if result["error"] == "contract_violation" else 404,
            detail=result.get("message") or result["error"],
        )
    return result


@router.get("/api/decision-lab/{decision_id}/simulations")
def get_simulations(
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    _validate_decision_access(db, decision_id, current_user)
    return DecisionLabService.get_simulations(db, decision_id)
