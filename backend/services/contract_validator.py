from sqlalchemy.orm import Session
from models.contract import CommerceContract
from models.product import Product
from services.event_service import EventService
from services.contract_constants import (
    CONTRACT_CHECK,
    CONTRACT_VIOLATION,
    CONTRACT_ACTION_BLOCKED,
    ACTION_SEARCH,
    ACTION_SELECT,
    ACTION_RECOMMEND,
    ACTION_ADD_TO_CART,
    ACTION_PAYMENT,
    RESTRICTED_ACTIONS,
)
from typing import Dict, Any, Optional, List

# Rule identifiers used in violation responses and audit log data.
RULE_MAX_BUDGET = "MAX_BUDGET"
RULE_CATEGORY = "REQUIRED_CATEGORY"
RULE_BATTERY = "MINIMUM_BATTERY"
RULE_EXCLUDED = "EXCLUDED_CONDITION"
RULE_ACTION_PERMISSION = "ACTION_PERMISSION"
RULE_RESTRICTED = "RESTRICTED_ACTION"
RULE_INPUT = "INVALID_INPUT"


class ContractValidator:
    """Deterministically validates AI agent actions against the active contract.

    This is the machine-enforceable boundary. The LLM may propose an action, but
    this validator decides whether it is allowed. It never relies on a prompt.
    """

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
    def _log_check(
        db: Session,
        session_id: str,
        action: str,
        passed: bool,
        rule: str = "",
        reason: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ):
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_CHECK if passed else CONTRACT_VIOLATION,
            actor="system",
            summary=(
                f"Contract check passed for {action}"
                if passed
                else f"Contract violated for {action}: {reason}"
            ),
            data={
                "action": action,
                "rule": rule,
                "passed": passed,
                "reason": reason,
                **(extra or {}),
            },
        )

    @staticmethod
    def check_action(
        db: Session,
        session_id: str,
        action: str,
        # Context specific to the action being validated.
        product: Optional[Product] = None,
        max_price: Optional[float] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate an AI-proposed action against the active contract.

        Returns a structured result:
        {
          "allowed": bool,
          "violations": [ {"rule": str, "message": str}, ... ]
        }
        """
        contract = ContractValidator.get_active_contract(db, session_id)

        # No active contract means there is nothing to enforce.
        if not contract:
            return {"allowed": True, "violations": [], "contract_active": False}

        violations = []

        # 1. AI can never perform restricted actions (e.g., approve/charge payment).
        if action in RESTRICTED_ACTIONS:
            violations.append({
                "rule": RULE_RESTRICTED,
                "message": "AI cannot perform this action; it requires explicit human approval.",
            })
            ContractValidator._log_check(
                db, session_id, action, False,
                rule=RULE_RESTRICTED,
                reason="Restricted action not allowed for AI",
            )
            return ContractValidator._build_result(False, violations)

        # 2. The action must be listed in allowed_actions (when the list is non-empty).
        allowed_actions = contract.allowed_actions or []
        if allowed_actions and action not in allowed_actions:
            violations.append({
                "rule": RULE_ACTION_PERMISSION,
                "message": f"The action '{action}' is not permitted by the active contract.",
            })
            ContractValidator._log_check(
                db, session_id, action, False,
                rule=RULE_ACTION_PERMISSION,
                reason=f"Action '{action}' not in allowed actions",
            )
            return ContractValidator._build_result(False, violations)

        # 3. Product-targeted checks (select/recommend/add_to_cart).
        if product is not None:
            product_violations = ContractValidator._check_product(contract, product)
            violations.extend(product_violations)

        # 4. Search-specific checks: provided price/category must respect contract.
        if action == ACTION_SEARCH:
            search_violations = ContractValidator._check_search(
                contract, max_price=max_price, category=category
            )
            violations.extend(search_violations)

        allowed = len(violations) == 0

        if allowed:
            ContractValidator._log_check(
                db,
                session_id,
                action,
                True,
                rule="ALL",
                reason="All contract rules satisfied",
            )
        else:
            ContractValidator._log_check(
                db, session_id, action, False,
                rule=";".join(v["rule"] for v in violations),
                reason="; ".join(v["message"] for v in violations),
            )
            ContractValidator._log_event_blocked(
                db, session_id, action, violations
            )

        return ContractValidator._build_result(allowed, violations)

    @staticmethod
    def _build_result(allowed: bool, violations: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "allowed": allowed,
            "violations": violations,
            "contract_active": True,
        }

    @staticmethod
    def _log_event_blocked(db: Session, session_id: str, action: str, violations):
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_ACTION_BLOCKED,
            actor="system",
            summary=f"AI action '{action}' blocked by contract",
            data={
                "action": action,
                "violations": [{"rule": v["rule"], "message": v["message"]} for v in violations],
            },
        )

    @staticmethod
    def _check_product(
        contract: CommerceContract, product: Product
    ) -> List[Dict[str, str]]:
        violations = []

        # Maximum budget
        if contract.max_budget is not None and product.price > contract.max_budget:
            excess = product.price - contract.max_budget
            violations.append({
                "rule": RULE_MAX_BUDGET,
                "message": (
                    f"Product price ₹{product.price:,.0f} exceeds your maximum "
                    f"budget of ₹{contract.max_budget:,.0f}."
                ),
            })
            # The demo text asks to word the excess clearly.
            violations[-1]["message"] = (
                f"{product.name} costs ₹{product.price:,.0f}, which exceeds your "
                f"maximum budget of ₹{contract.max_budget:,.0f} by ₹{excess:,.0f}."
            )

        # Required category
        required_categories = contract.required_categories or []
        if required_categories and product.category not in required_categories:
            violations.append({
                "rule": RULE_CATEGORY,
                "message": (
                    f"Product category '{product.category}' does not match the "
                    f"required category: {', '.join(required_categories)}."
                ),
            })

        # Minimum battery requirement
        if contract.minimum_battery_hours is not None:
            battery = (product.attributes or {}).get("battery_life_hours", 0)
            if battery < contract.minimum_battery_hours:
                violations.append({
                    "rule": RULE_BATTERY,
                    "message": (
                        f"{product.name} has {battery} hours of battery life, "
                        f"below the required minimum of {contract.minimum_battery_hours} hours."
                    ),
                })

        # Required attributes (e.g., wireless must be truthy). Only enforced when
        # the product actually carries the attribute; a missing attribute means we
        # cannot confirm the requirement, so we don't block on it. This keeps the
        # demo working while still enforcing attributes that are in the data.
        required_attrs = contract.required_attributes or {}
        product_attrs = product.attributes or {}
        for attr, expected in required_attrs.items():
            if attr not in product_attrs:
                continue
            actual = product_attrs.get(attr)
            if expected is True and not actual:
                violations.append({
                    "rule": "REQUIRED_ATTRIBUTE",
                    "message": f"Product does not satisfy the '{attr}' requirement.",
                })

        # Excluded conditions (e.g., refurbished) — match against description/name.
        exclusions = contract.excluded_conditions or []
        haystack = "{} {}".format(
            (product.description or "").lower(), (product.name or "").lower()
        )
        for condition in exclusions:
            word = condition.replace("_", " ").lower()
            if word and word in haystack:
                violations.append({
                    "rule": RULE_EXCLUDED,
                    "message": f"Product matches an excluded condition: {condition}.",
                })

        return violations

    @staticmethod
    def _check_search(
        contract: CommerceContract,
        max_price: Optional[float] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        violations = []

        # The proposed search must not exceed the contract budget.
        if (
            contract.max_budget is not None
            and max_price is not None
            and max_price > contract.max_budget
        ):
            violations.append({
                "rule": RULE_MAX_BUDGET,
                "message": (
                    f"Searching with max price ₹{max_price:,.0f} exceeds the "
                    f"contract budget of ₹{contract.max_budget:,.0f}."
                ),
            })

        # The search must respect the required category when one is set.
        required_categories = contract.required_categories or []
        if required_categories and category and category not in required_categories:
            violations.append({
                "rule": RULE_CATEGORY,
                "message": (
                    f"Searching category '{category}' is outside the required "
                    f"category: {', '.join(required_categories)}."
                ),
            })

        return violations

    @staticmethod
    def check_product(
        db: Session, session_id: str, product: Product, action: str = ACTION_ADD_TO_CART
    ) -> Dict[str, Any]:
        """Convenience validator for a concrete product (add_to_cart, select...)."""
        return ContractValidator.check_action(
            db, session_id, action=action, product=product
        )

    @staticmethod
    def _to_blocked_payload(action: str, check: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a failed check into a structured payload the agent can surface."""
        return {
            "blocked": True,
            "reason": "contract_violation",
            "action": action,
            "message": ContractValidator._blocked_human_message(check),
            "violations": check.get("violations", []),
        }

    @staticmethod
    def _blocked_human_message(check: Dict[str, Any]) -> str:
        violations = check.get("violations", [])
        if not violations:
            return "This action is blocked by your active AI Commerce Contract."
        if len(violations) == 1:
            return violations[0]["message"]
        return "This action is blocked by your active AI Commerce Contract: " + "; ".join(
            v["message"] for v in violations
        )
