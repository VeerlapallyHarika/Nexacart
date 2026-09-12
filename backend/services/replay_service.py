from sqlalchemy.orm import Session
from models.event import AuditEvent
from services.event_service import EventService
from services.product_service import ProductService
from services.contract_service import ContractService
from services.order_service import OrderService
from services.decision_trace_service import DecisionTraceService
from typing import Dict, Any, List, Optional

# Constants for replay step types
STEP_INTENT = "INTENT"
STEP_DISCOVERY = "DISCOVERY"
STEP_CONTRACT_CREATED = "CONTRACT_CREATED"
STEP_CONTRACT_CHECK = "CONTRACT_CHECK"
STEP_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
STEP_COMPARISON = "COMPARISON"
STEP_DECISION = "DECISION"
STEP_CART_ADD = "CART_ADD"
STEP_CART_UPDATE = "CART_UPDATE"
STEP_CART_VERIFIED = "CART_VERIFIED"
STEP_CHECKOUT_APPROVAL = "CHECKOUT_APPROVAL"
STEP_PAYMENT_INITIATED = "PAYMENT_INITIATED"
STEP_PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
STEP_ORDER_CONFIRMED = "ORDER_CONFIRMED"
STEP_PURCHASE_COMPLETE = "PURCHASE_COMPLETE"

# AI Buyer Agent orchestration steps (extend the replay without replacing it).
# These render the agent's decisions that a purely human chat flow never emits.
STEP_AGENT_GOAL = "AGENT_GOAL"
STEP_AGENT_RECOMMENDATION = "AGENT_RECOMMENDATION"

# Replay statuses
REPLAY_IN_PROGRESS = "IN_PROGRESS"
REPLAY_COMPLETED = "COMPLETED"
REPLAY_BLOCKED = "BLOCKED"
REPLAY_CANCELLED = "CANCELLED"

# Event types we turn into replay steps
_EVENT_SEARCH = "TOOL_EXECUTED"
_EVENT_COMPARE = "TOOL_EXECUTED"
_EVENT_CONTRACT_CHECK = "CONTRACT_CHECK"
_EVENT_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
_EVENT_CONTRACT_ACTION_BLOCKED = "CONTRACT_ACTION_BLOCKED"
_EVENT_PRODUCT_ADDED = "PRODUCT_ADDED_TO_CART"
_EVENT_CART_UPDATED = "CART_ITEM_UPDATED"
_EVENT_CART_VERIFIED = "CART_VERIFIED"
_EVENT_APPROVAL_REQUESTED = "CHECKOUT_APPROVAL_REQUESTED"
_EVENT_APPROVED = "USER_APPROVED_CHECKOUT"
_EVENT_PAYMENT_CREATED = "PAYMENT_CREATED"
_EVENT_PAYMENT_INITIATED = "PAYMENT_INITIATED"
_EVENT_PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
_EVENT_ORDER_CREATED = "ORDER_CREATED"
_EVENT_ORDER_CONFIRMED = "ORDER_CONFIRMED"

# AI Buyer Agent orchestration events (new; ignored for old data that predates
# them, so backward compatibility is preserved).
_EVENT_BUYER_GOAL = "BUYER_GOAL_UNDERSTOOD"
_EVENT_PRODUCT_RECOMMENDED = "PRODUCT_RECOMMENDED"
_EVENT_PRODUCT_REJECTED = "PRODUCT_REJECTED_BY_CONTRACT"


class ReplayService:
    """Builds a safe, step-by-step visual replay of a purchase journey.

    The replay is derived purely from structured audit events recorded by the
    system. It never exposes AI internal reasoning, prompts, or raw debug data.
    """

    @staticmethod
    def _format_ts(raw: Optional[str]) -> str:
        """Normalize the SQLite timestamp into a stable ISO-like string."""
        if not raw:
            return ""
        return raw.replace(" ", "T")

    @staticmethod
    def _step_number(index: int) -> int:
        return index + 1

    @staticmethod
    def get_purchase_replay(db: Session, session_id: str) -> Dict[str, Any]:
        events = EventService.get_events_by_session(db, session_id)
        steps: List[Dict[str, Any]] = []

        contract = ContractService.get_contract(db, session_id)
        contract_snapshot = (
            ContractService.serialize(contract) if contract else None
        )

        # Track the last user intent and the latest discovered products so we
        # can render richer, still-safe descriptions for later steps.
        last_user_message = ""
        last_discovery_count = 0
        last_discovery_names: List[str] = []
        last_compared_products: List[str] = []
        blocked = False
        completed = False
        cancelled = False

        def _last_step_type() -> Optional[str]:
            return steps[-1]["type"] if steps else None

        def _last_step_status() -> Optional[str]:
            return steps[-1]["status"] if steps else None

        for event in events:
            et = event.event_type
            data = event.data or {}
            summary = event.summary or ""

            if et == "USER_MESSAGE":
                last_user_message = data.get("message", summary)
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_INTENT,
                    "title": "Your Shopping Intent",
                    "description": (
                        f"You said: \"{last_user_message}\""
                        if last_user_message else "You shared what you were looking for."
                    ),
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_BUYER_GOAL:
                # The AI Buyer Agent parsed the user's goal into structured intent.
                goal = data.get("goal") or summary
                parts = ["The AI Buyer Agent understood your goal."]
                category = data.get("category")
                max_price = data.get("max_price")
                if category:
                    parts.append(f"Looking in category: {category}.")
                if max_price is not None:
                    parts.append(f"Targeting a budget of up to ₹{max_price:,.0f}.")
                contract = data.get("active_contract")
                if contract and contract.get("max_budget") is not None:
                    parts.append(
                        f"An active Commerce Contract limits spending to ₹{contract['max_budget']:,.0f}."
                    )
                description = " ".join(parts)
                if goal and goal != data.get("raw_message"):
                    description = f"Goal: \"{goal}\". " + description
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_AGENT_GOAL,
                    "title": "AI Buyer Agent Understood Your Goal",
                    "description": description,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_SEARCH and data.get("tool") == "search_products":
                last_discovery_count = data.get("result_count", 0)
                last_discovery_names = ReplayService._resolve_names(
                    db, data.get("product_ids", [])
                )
                description = f"NexaCart found {last_discovery_count} matching product(s)."
                if last_discovery_names:
                    description += " " + ", ".join(last_discovery_names) + "."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_DISCOVERY,
                    "title": "Products Discovered",
                    "description": "NexaCart searched the catalog for products matching your request. " + description,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_COMPARE and data.get("tool") == "compare_products":
                last_compared_products = data.get("product_names", [])
                description = "You compared the following products side by side: "
                description += ", ".join(last_compared_products) + "." if last_compared_products else "NexaCart compared the selected products."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_COMPARISON,
                    "title": "Products Compared",
                    "description": description,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_PRODUCT_RECOMMENDED:
                # The AI Buyer Agent explicitly recommends a product and explains why.
                name = data.get("product_name") or "a product"
                price = data.get("product_price")
                desc = f"The AI Buyer Agent recommended **{name}**" + (f" at ₹{price:,.0f}" if price is not None else "") + " as the top match for your goal."
                contract_note = data.get("contract_note")
                if contract_note:
                    desc += f"\nContract: {contract_note}."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_AGENT_RECOMMENDATION,
                    "title": "AI Buyer Agent Recommendation",
                    "description": desc,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_PRODUCT_REJECTED:
                # The agent could not add the goal product because the active
                # contract blocked it — reuse the CONTRACT_VIOLATION step type so
                # the UI needs no new variant while the agent's decision is shown.
                name = data.get("product_name") or "a product"
                reason = data.get("reason") or "violates the active AI Commerce Contract"
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CONTRACT_VIOLATION,
                    "title": "Product Rejected by Contract",
                    "description": f"The AI Buyer Agent could not add **{name}** because of your active AI Commerce Contract.\n✗ {reason}",
                    "status": "BLOCKED",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et in ("CONTRACT_CREATED", "CONTRACT_UPDATED", "CONTRACT_ACTIVATED"):
                # Avoid repeating the same contract snapshot across create/update
                # events that happened close together.
                if _last_step_type() == STEP_CONTRACT_CREATED:
                    continue
                description = ReplayService._describe_contract(contract_snapshot)
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CONTRACT_CREATED,
                    "title": "Your AI Commerce Contract",
                    "description": "These shopping rules were set before purchase to keep the AI within bounds.\n" + description,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_CONTRACT_CHECK and data.get("passed", True) is True:
                # Collapse repeated identical pass checks into a single step.
                if _last_step_type() == STEP_CONTRACT_CHECK and _last_step_status() == "SUCCESS":
                    continue
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CONTRACT_CHECK,
                    "title": "Contract Check Passed",
                    "description": ReplayService._contract_pass_lines(db, session_id),
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_CONTRACT_VIOLATION:
                reason = data.get("reason") or ReplayService._violation_message(data)
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CONTRACT_VIOLATION,
                    "title": "Contract Check Failed",
                    "description": f"A product was checked against your AI Commerce Contract and did not pass.\n✗ {reason}",
                    "status": "BLOCKED",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_CONTRACT_ACTION_BLOCKED:
                blocked = True
                reason = ReplayService._violation_message(data)
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CONTRACT_VIOLATION,
                    "title": "Action Blocked",
                    "description": f"The AI was prevented from performing this action to stay within your contract.\n🔒 {reason}",
                    "status": "BLOCKED",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_PRODUCT_ADDED:
                product_name = data.get("product_name", "")
                price = data.get("price")
                qty = data.get("quantity", 1)
                cart_total = data.get("cart_total")
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_DECISION,
                    "title": "Your Choice",
                    "description": f"You selected {product_name}." if product_name else "You selected a product.",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
                cart_desc = f"Added {qty}x {product_name}" if product_name else "Added an item"
                if price is not None:
                    cart_desc += f" at ₹{price:,.0f}"
                cart_desc += " to your cart."
                if cart_total is not None:
                    cart_desc += f" Cart total: ₹{cart_total:,.0f}."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CART_ADD,
                    "title": "Added to Cart",
                    "description": cart_desc,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_CART_UPDATED:
                qty = data.get("new_quantity")
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CART_UPDATE,
                    "title": "Cart Updated",
                    "description": f"Cart item quantity updated to {qty}." if qty else "Cart item updated.",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_CART_VERIFIED:
                total = data.get("total")
                item_count = data.get("item_count")
                desc = "NexaCart verified your cart: prices and inventory are correct."
                if item_count is not None:
                    desc += f" {item_count} item(s) checked."
                if total is not None:
                    desc += f" Total: ₹{total:,.0f}."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CART_VERIFIED,
                    "title": "Cart Verified",
                    "description": desc,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_APPROVAL_REQUESTED:
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CHECKOUT_APPROVAL,
                    "title": "Checkout Approval Requested",
                    "description": "NexaCart asked you to review the order and approve checkout before any payment.",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_APPROVED:
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_CHECKOUT_APPROVAL,
                    "title": "Approved by You",
                    "description": "You approved the checkout. This explicit human approval is required before payment.",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et in (_EVENT_PAYMENT_CREATED, _EVENT_PAYMENT_INITIATED):
                amount = data.get("amount")
                desc = "Payment was initiated for your approved cart."
                if amount is not None:
                    desc += f" Amount: ₹{amount:,.0f}."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_PAYMENT_INITIATED,
                    "title": "Payment Initiated",
                    "description": desc,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_PAYMENT_SUCCESS:
                completed = True
                amount = data.get("amount")
                desc = "Your payment was processed successfully."
                if amount is not None:
                    desc += f" Paid: ₹{amount:,.0f}."
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_PAYMENT_CONFIRMED,
                    "title": "Payment Successful",
                    "description": desc,
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_ORDER_CREATED:
                order_id = data.get("order_id", "")
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_ORDER_CONFIRMED,
                    "title": "Order Created",
                    "description": f"Your order {order_id} was created from the successful payment." if order_id else "Your order was created.",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })
            elif et == _EVENT_ORDER_CONFIRMED:
                steps.append({
                    "step": ReplayService._step_number(len(steps)),
                    "type": STEP_PURCHASE_COMPLETE,
                    "title": "Purchase Complete",
                    "description": "Your order was confirmed. Thank you for shopping with NexaCart!",
                    "status": "SUCCESS",
                    "timestamp": ReplayService._format_ts(event.created_at),
                })

        # Determine replay status from the journey that actually happened.
        status = ReplayService._determine_status(blocked, completed, cancelled, events)

        trace = DecisionTraceService.get_trace_by_session(db, session_id)

        return {
            "session_id": session_id,
            "decision_id": trace.decision_id if trace else None,
            "status": status,
            "total_steps": len(steps),
            "steps": steps,
        }

    @staticmethod
    def get_order_replay(db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        order = OrderService.get_order(db, order_id)
        if not order:
            return None
        replay = ReplayService.get_purchase_replay(db, order["session_id"])
        replay["order_id"] = order_id
        return replay

    @staticmethod
    def _resolve_names(db: Session, product_ids: List[str]) -> List[str]:
        names = []
        for pid in product_ids:
            product = ProductService.get_product(db, pid)
            if product:
                names.append(product.name)
        return names

    @staticmethod
    def _describe_contract(contract: Optional[Dict[str, Any]]) -> str:
        if not contract:
            return "No contract rules were set for this session."
        lines = []
        if contract.get("max_budget") is not None:
            lines.append(f"• Maximum budget: ₹{contract['max_budget']:,.0f}")
        cats = contract.get("required_categories") or []
        if cats:
            lines.append(f"• Required category: {', '.join(cats)}")
        if contract.get("minimum_battery_hours") is not None:
            lines.append(f"• Minimum battery: {contract['minimum_battery_hours']} hours")
        exclusions = contract.get("excluded_conditions") or []
        if exclusions:
            lines.append(f"• Excluded: {', '.join(exclusions)}")
        return "\n".join(lines) if lines else "No specific rules were configured."

    @staticmethod
    def _contract_pass_lines(db: Session, session_id: str) -> str:
        contract = ContractService.get_contract(db, session_id)
        lines = []
        if contract and contract.max_budget is not None:
            lines.append(f"✓ Price is within your ₹{contract.max_budget:,.0f} budget.")
        if contract and (contract.required_categories or []):
            lines.append(f"✓ Product matches the required category ({', '.join(contract.required_categories)}).")
        if contract and contract.minimum_battery_hours is not None:
            lines.append(f"✓ Battery life meets your minimum of {contract.minimum_battery_hours} hours.")
        if not lines:
            lines.append("✓ All active contract rules were satisfied.")
        return "\n".join(lines)

    @staticmethod
    def _violation_message(data: Dict[str, Any]) -> str:
        violations = data.get("violations") or []
        if violations:
            if len(violations) == 1:
                return violations[0].get("message", "")
            return "; ".join(v.get("message", "") for v in violations)
        reason = data.get("reason", "")
        return reason or "The action did not satisfy the contract rules."

    @staticmethod
    def _determine_status(
        blocked: bool, completed: bool, cancelled: bool, events: List[AuditEvent]
    ) -> str:
        if completed:
            return REPLAY_COMPLETED
        if blocked:
            return REPLAY_BLOCKED
        for e in events:
            if e.event_type == "CONTRACT_CANCELLED":
                return REPLAY_CANCELLED
        if not events:
            return REPLAY_IN_PROGRESS
        return REPLAY_IN_PROGRESS
