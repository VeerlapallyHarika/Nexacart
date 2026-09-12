from sqlalchemy.orm import Session
from models.contract import CommerceContract
from services.event_service import EventService
from services.intent_service import IntentService
from services.contract_constants import (
    CONTRACT_CREATED,
    CONTRACT_UPDATED,
    CONTRACT_ACTIVATED,
    CONTRACT_CANCELLED,
    CONTRACT_COMPLETED,
    ACTION_SEARCH,
    ACTION_ADD_TO_CART,
)
from typing import Dict, Any, Optional, List
import re

# Action names we understand. These map to the agent tools that the contract
# allows or forbids.
KNOWN_ACTIONS = [
    "search_products",
    "get_product_details",
    "compare_products",
    "recommend_product",
    "add_to_cart",
    "view_cart",
]


class ContractService:
    @staticmethod
    def get_contract(db: Session, session_id: str) -> Optional[CommerceContract]:
        return (
            db.query(CommerceContract)
            .filter(CommerceContract.session_id == session_id)
            .order_by(CommerceContract.updated_at.desc())
            .first()
        )

    @staticmethod
    def get_active_contract(db: Session, session_id: str) -> Optional[CommerceContract]:
        return (
            db.query(CommerceContract)
            .filter(
                CommerceContract.session_id == session_id,
                CommerceContract.status == "ACTIVE",
            )
            .first()
        )

    @staticmethod
    def get_or_create_contract(db: Session, session_id: str) -> CommerceContract:
        """Return the latest contract, creating a DRAFT one if none exists."""
        contract = ContractService.get_contract(db, session_id)
        if not contract:
            contract = CommerceContract(
                id=CommerceContract.generate_id(),
                session_id=session_id,
                status="DRAFT",
                allowed_actions=list(KNOWN_ACTIONS),
            )
            db.add(contract)
            db.commit()
            db.refresh(contract)
        return contract

    @staticmethod
    def _pick_action(action: Optional[str]) -> str:
        """Normalize a user-supplied action name to one of our known names."""
        if not action:
            return ""
        normalized = action.strip().lower()
        for known in KNOWN_ACTIONS:
            if normalized == known:
                return known
        # Allow a few friendly aliases
        aliases = {
            "search": "search_products",
            "view": "view_cart",
            "cart": "add_to_cart",
            "recommend": "recommend_product",
            "compare": "compare_products",
            "details": "get_product_details",
        }
        return aliases.get(normalized, "")

    @staticmethod
    def upsert_contract_from_payload(
        db: Session, session_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create or update a contract from structured payload fields."""
        contract = ContractService.get_contract(db, session_id)
        is_new = contract is None
        if not contract:
            contract = CommerceContract(
                id=CommerceContract.generate_id(),
                session_id=session_id,
                status=payload.get("status", "DRAFT"),
            )
            db.add(contract)
            exists = False
        else:
            exists = True

        # Validate battery hours if provided
        battery = payload.get("minimum_battery_hours")
        if battery is None:
            battery = payload.get("battery_hours_min")
        if battery is not None:
            if battery < 0:
                raise ValueError("Battery life must be 0 or greater")
            payload["minimum_battery_hours"] = battery

        # Only update fields that were explicitly provided in the payload.
        fields = [
            "goal",
            "max_budget",
            "currency",
            "required_categories",
            "required_attributes",
            "minimum_battery_hours",
            "excluded_conditions",
            "allowed_actions",
        ]
        for field in fields:
            if field in payload and payload[field] is not None:
                setattr(contract, field, payload[field])

        # Ensure stored battery life is not negative
        if contract.minimum_battery_hours is not None and contract.minimum_battery_hours < 0:
            raise ValueError("Battery life must be 0 or greater")

        # A contract that leaves DRAFT can be activated immediately.
        if payload.get("activate", False) and contract.status != "ACTIVE":
            contract.status = "ACTIVE"

        db.commit()
        db.refresh(contract)

        event_type = CONTRACT_CREATED if is_new else CONTRACT_UPDATED
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=event_type,
            actor="user",
            summary="Contract created" if is_new else "Contract updated",
            data={"contract_id": contract.id, "status": contract.status},
        )

        return ContractService.serialize(contract)

    @staticmethod
    def update_from_natural_language(
        db: Session, session_id: str, message: str
    ) -> Dict[str, Any]:
        """Convert simple instructions into structured contract fields.

        Uses the existing intent extractor plus lightweight regex parsing. This
        is intentionally simple — not a full NLP parser.
        """
        contract = ContractService.get_or_create_contract(db, session_id)
        message_lower = message.lower()

        intent = IntentService.extract_intent(message)
        changed = False

        # "above X"/"don't show above X" -> max budget X (a ceiling).
        ceiling = ContractService._extract_ceiling(message)
        if intent.get("max_price") is not None or ceiling is not None:
            contract.max_budget = intent.get("max_price") if intent.get("max_price") is not None else ceiling
            changed = True

        if intent.get("min_battery_life") is not None:
            contract.minimum_battery_hours = intent["min_battery_life"]
            changed = True

        if intent.get("category") is not None:
            categories = contract.required_categories or []
            if intent["category"] not in categories:
                categories.append(intent["category"])
            contract.required_categories = categories
            changed = True

        # Heuristic: words like "wireless", "refurbished", "used" become
        # attributes or exclusions.
        requirements = contract.required_attributes or {}
        if "wireless" in message_lower and "wireless" not in requirements:
            requirements["wireless"] = True
            contract.required_attributes = requirements
            changed = True

        exclusions = list(contract.excluded_conditions or [])
        for condition, word in [("refurbished", "refurbished"), ("used", "used"), ("open_box", "open box")]:
            if word in message_lower and condition not in exclusions:
                exclusions.append(condition)
                changed = True
        if exclusions:
            contract.excluded_conditions = exclusions

        # Don't activate contract on a plain instruction for the demo unless we
        # can't tell the difference; the frontend/endpoints control activation.
        if changed:
            db.commit()
            db.refresh(contract)
            EventService.log_event(
                db=db,
                session_id=session_id,
                event_type=CONTRACT_UPDATED,
                actor="agent",
                summary="Contract updated from natural language",
                data={
                    "contract_id": contract.id,
                    "max_budget": contract.max_budget,
                    "minimum_battery_hours": contract.minimum_battery_hours,
                    "required_categories": contract.required_categories,
                },
            )

        return ContractService.serialize(contract)

    @staticmethod
    def activate(db: Session, session_id: str) -> Dict[str, Any]:
        contract = ContractService.get_or_create_contract(db, session_id)

        if contract.minimum_battery_hours is not None and contract.minimum_battery_hours < 0:
            raise ValueError("Battery life must be 0 or greater")

        # Only one ACTIVE contract allowed per session.
        active = (
            db.query(CommerceContract)
            .filter(
                CommerceContract.session_id == session_id,
                CommerceContract.id != contract.id,
                CommerceContract.status == "ACTIVE",
            )
            .all()
        )
        for other in active:
            other.status = "CANCELLED"

        contract.status = "ACTIVE"
        db.commit()
        db.refresh(contract)

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_ACTIVATED,
            actor="user",
            summary="Contract activated",
            data={"contract_id": contract.id},
        )
        return ContractService.serialize(contract)

    @staticmethod
    def cancel(db: Session, session_id: str) -> Dict[str, Any]:
        contract = ContractService.get_contract(db, session_id)
        if not contract:
            return {"error": "No contract found for this session"}

        if contract.status in ["COMPLETED"]:
            return {"error": f"Cannot cancel a {contract.status} contract"}

        contract.status = "CANCELLED"
        db.commit()
        db.refresh(contract)

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_CANCELLED,
            actor="user",
            summary="Contract cancelled",
            data={"contract_id": contract.id},
        )
        return ContractService.serialize(contract)

    @staticmethod
    def complete(db: Session, session_id: str) -> Dict[str, Any]:
        contract = ContractService.get_contract(db, session_id)
        if not contract:
            return {"error": "No contract found for this session"}

        contract.status = "COMPLETED"
        db.commit()
        db.refresh(contract)

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_COMPLETED,
            actor="system",
            summary="Contract completed",
            data={"contract_id": contract.id},
        )
        return ContractService.serialize(contract)

    @staticmethod
    def _extract_ceiling(message_lower: str) -> Optional[float]:
        """Extract a max budget from phrases like 'don't show above 3000'."""
        match = re.search(r"above\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", message_lower)
        if match:
            return float(match.group(1).replace(",", ""))
        return None

    @staticmethod
    def serialize(contract: CommerceContract) -> Dict[str, Any]:
        return {
            "id": contract.id,
            "session_id": contract.session_id,
            "status": contract.status,
            "goal": contract.goal,
            "max_budget": contract.max_budget,
            "currency": contract.currency,
            "required_categories": contract.required_categories or [],
            "required_attributes": contract.required_attributes or {},
            "minimum_battery_hours": contract.minimum_battery_hours,
            "excluded_conditions": contract.excluded_conditions or [],
            "allowed_actions": contract.allowed_actions or [],
            "created_at": contract.created_at,
            "updated_at": contract.updated_at,
        }
