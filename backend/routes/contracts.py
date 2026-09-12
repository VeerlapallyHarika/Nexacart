from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.contract_service import ContractService
from services.contract_validator import ContractValidator
from services.product_service import ProductService
from schemas.contract import ContractPayload, ContractCheckRequest
from pydantic import BaseModel

router = APIRouter()


class MessagePayload(BaseModel):
    message: str


@router.get("/api/contracts/{session_id}")
def get_contract(session_id: str, db: Session = Depends(get_db)):
    contract = ContractService.get_contract(db, session_id)
    if not contract:
        return {
            "id": None,
            "session_id": session_id,
            "status": "DRAFT",
            "goal": None,
            "max_budget": None,
            "currency": "INR",
            "required_categories": [],
            "required_attributes": {},
            "minimum_battery_hours": None,
            "excluded_conditions": [],
            "allowed_actions": [],
        }
    return ContractService.serialize(contract)


@router.post("/api/contracts/{session_id}")
def create_contract(
    session_id: str,
    payload: ContractPayload,
    db: Session = Depends(get_db),
):
    try:
        return ContractService.upsert_contract_from_payload(
            db, session_id, payload.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/contracts/{session_id}")
def update_contract(
    session_id: str,
    payload: ContractPayload,
    db: Session = Depends(get_db),
):
    try:
        return ContractService.upsert_contract_from_payload(
            db, session_id, payload.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/contracts/{session_id}/activate")
def activate_contract(session_id: str, db: Session = Depends(get_db)):
    try:
        result = ContractService.activate(db, session_id)
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/contracts/{session_id}/cancel")
def cancel_contract(session_id: str, db: Session = Depends(get_db)):
    result = ContractService.cancel(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/contracts/{session_id}/complete")
def complete_contract(session_id: str, db: Session = Depends(get_db)):
    result = ContractService.complete(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/contracts/{session_id}/from-message")
def update_from_message(
    session_id: str,
    payload: MessagePayload,
    db: Session = Depends(get_db),
):
    return ContractService.update_from_natural_language(
        db, session_id, payload.message
    )


@router.post("/api/contracts/{session_id}/check")
def check_action(
    session_id: str,
    payload: ContractCheckRequest,
    db: Session = Depends(get_db),
):
    product = None
    if payload.product_id:
        product = ProductService.get_product(db, payload.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

    result = ContractValidator.check_action(
        db=db,
        session_id=session_id,
        action=payload.action,
        product=product,
        max_price=payload.max_price,
        category=payload.category,
    )
    return result
