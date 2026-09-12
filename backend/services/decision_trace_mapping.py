from typing import Dict, Any, Optional

# ─────────────────────────────────────────────────────────────────────────
# Decision Trace event mapping.
#
# Every audit event that is relevant to a commerce decision is mapped to a
# small, human-readable presentation: the actor (AI / user / system), a status
# (success / pending / warning / error), a short title, a readable summary and,
# where useful, a structured "explanation" such as a recommendation rationale.
#
# The mapping is DATA-DRIVEN and EXTENSIBLE: unknown or future event types fall
# back to a safe generic presentation instead of breaking the trace. Add new
# canonical event types here (or rely on the fallback) for future agents,
# categories, rules, providers or event types.
# ─────────────────────────────────────────────────────────────────────────

# Actor buckets
ACTOR_AI = "ai"
ACTOR_USER = "user"
ACTOR_SYSTEM = "system"


def _summary(data: Dict[str, Any], keys, fallback: str = "") -> str:
    for k in keys:
        v = data.get(k)
        if v:
            return str(v)
    return fallback


def _money(value) -> str:
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return ""


# Canonical canonical_event_type -> presentation.
# Each entry:
#   actor, status, title, summary_fn(data, summary), explanation_fn(data)
# summary_fn returns a human-readable one-liner; explanation_fn returns either
# None or a small structured dict shown under "Technical Details".
def _rec_summary(data):
    name = data.get("product_name")
    if name:
        return f"**{name}** was recommended as the best match for your goal."
    return "The AI recommended the best match for your goal."


def _rec_explanation(data):
    within_goal = data.get("within_goal_budget")
    within_contract = data.get("within_contract_budget")
    many = []
    tradeoffs = []
    if within_goal is True:
        many.append("Within your stated budget")
    if within_goal is False:
        tradeoffs.append("Exceeds your stated budget")
    if within_contract is True:
        many.append("Within your AI Commerce Contract budget")
    if within_contract is False:
        tradeoffs.append("Exceeds your AI Commerce Contract budget")
    if data.get("contract_active") and not within_goal and not within_contract:
        many.append("Evaluated under your active Commerce Contract")
    if not many and not tradeoffs:
        many.append("Ranked as the top query-relevance match")
    explanation = {
        "type": "recommendation",
        "product_id": data.get("product_id"),
        "product_name": data.get("product_name"),
        "product_price": data.get("product_price"),
        "strong_matches": many,
        "trade_offs": tradeoffs,
    }
    return explanation


def _contract_pass_explanation(data):
    return {
        "type": "contract_check",
        "passed": True,
        "violations": [],
        "checked_fields": ["budget", "category", "attributes"],
    }


def _buyer_agent_goal_summary(data):
    parts = ["The AI Buyer Agent understood your goal."]
    cat = data.get("category")
    if cat:
        parts.append(f"Category: {cat}.")
    maxp = data.get("max_price")
    if maxp is not None:
        parts.append(f"Budget: up to {_money(maxp)}.")
    if data.get("active_contract"):
        parts.append("An active Commerce Contract is in effect.")
    return " ".join(parts)


def _buyer_goal_explanation(data):
    return {
        "type": "agent_goal",
        "category": data.get("category"),
        "max_price": data.get("max_price"),
        "min_price": data.get("min_price"),
        "constraints": data.get("constraints") or [],
        "active_contract": bool(data.get("active_contract")),
    }


def _discovery_summary(data):
    count = data.get("result_count") or data.get("results_count") or data.get("products_count")
    if count is not None:
        return f"NexaCart discovered {count} matching product(s)."
    return "NexaCart searched the catalog for matching products."


def _discovery_explanation(data):
    return {
        "type": "discovery",
        "product_count": data.get("result_count") or data.get("results_count") or data.get("products_count"),
        "matched_constraints": data.get("matched_constraints") or [],
        "unmatched_constraints": data.get("unmatched_constraints") or [],
        "product_ids": (data.get("product_ids") or [])[:10],
    }


def _contract_block_explanation(data):
    reasons = []
    for v in data.get("violations") or []:
        if isinstance(v, dict):
            reasons.append(v.get("message") or v.get("rule") or "")
        else:
            reasons.append(str(v))
    if not reasons:
        reasons.append(data.get("reason") or "")
    return {
        "type": "contract_block",
        "violations": [r for r in reasons if r],
    }


def _payment_explanation(data):
    return {
        "type": "payment",
        "amount": data.get("amount"),
        "currency": data.get("currency", "INR"),
        "status": data.get("status"),
        "provider": data.get("provider"),
    }


def _selected_explanation(data):
    return {
        "type": "selection",
        "product_id": data.get("product_id"),
        "product_name": data.get("product_name"),
        "price": data.get("price"),
    }


CANONICAL_MAP = {
    # ── User request / intent ──
    "USER_MESSAGE": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "USER_REQUEST",
        "title": "User Request",
        "summary_fn": lambda d, s: f'"{d.get("message") or ""}"',
    },
    "INTENT_EXTRACTED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "INTENT_EXTRACTED",
        "title": "AI Understanding",
        "summary_fn": lambda d, s: (
            "NexaCart parsed your request into structured preferences."
        ),
        "explanation_fn": lambda d: {
            "type": "intent",
            "category": d.get("category"),
            "max_price": d.get("max_price"),
            "brand": d.get("brand"),
            "constraints_count": d.get("constraints_count"),
        },
    },
    # ── Discovery / search ──
    "CATALOG_SEARCHED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "PRODUCTS_DISCOVERED",
        "title": "Product Discovery",
        "summary_fn": _discovery_summary,
        "explanation_fn": _discovery_explanation,
    },
    "TOOL_EXECUTED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "PRODUCTS_DISCOVERED",
        "title": "Product Discovery",
        "summary_fn": lambda d, s: _discovery_summary(d) if d.get("tool") == "search_products" else s,
        "explanation_fn": _discovery_explanation if False else None,
    },
    # ── Buyer agent ──
    "BUYER_GOAL_UNDERSTOOD": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "BUYER_AGENT_STARTED",
        "title": "AI Buyer Agent Started",
        "summary_fn": _buyer_agent_goal_summary,
        "explanation_fn": _buyer_goal_explanation,
    },
    "BUYER_AGENT_STEP": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "BUYER_AGENT_EVALUATED",
        "title": "AI Buyer Agent Evaluated",
        "summary_fn": lambda d, s: (
            f"The AI Buyer Agent ran step {d.get('step')}: {d.get('action', '').replace('_', ' ')}."
        ),
    },
    "PRODUCT_RECOMMENDED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "BUYER_AGENT_RECOMMENDED",
        "title": "AI Recommendation",
        "summary_fn": _rec_summary,
        "explanation_fn": _rec_explanation,
    },
    "PRODUCT_REJECTED_BY_CONTRACT": {
        "actor": ACTOR_AI, "status": "WARNING", "registry": "CONTRACT_BLOCKED",
        "title": "Product Rejected by Contract",
        "summary_fn": lambda d, s: (
            f"{d.get('product_name') or 'A product'} was not selected because it violates your active AI Commerce Contract."
        ),
        "explanation_fn": _contract_block_explanation,
    },
    "BUYER_AGENT_ERROR": {
        "actor": ACTOR_AI, "status": "ERROR", "registry": "BUYER_AGENT_ERROR",
        "title": "AI Buyer Agent Error",
    },
    # ── User decision ──
    "PRODUCT_ADDED_TO_CART": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "PRODUCT_SELECTED",
        "title": "User Decision",
        "summary_fn": lambda d, s: (
            f"You chose {d.get('product_name') or 'a product'}."
        ),
        "explanation_fn": _selected_explanation,
    },
    # ── Contract ──
    "CONTRACT_CREATED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "CONTRACT_VERIFIED",
        "title": "Commerce Contract",
        "summary_fn": lambda d, s: "Your AI Commerce Contract was set up.",
    },
    "CONTRACT_UPDATED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "CONTRACT_VERIFIED",
        "title": "Commerce Contract Updated",
        "summary_fn": lambda d, s: "Your AI Commerce Contract was updated.",
    },
    "CONTRACT_ACTIVATED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "CONTRACT_VERIFIED",
        "title": "Commerce Contract Active",
        "summary_fn": lambda d, s: "Your AI Commerce Contract is now active.",
    },
    "CONTRACT_CHECK": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "CONTRACT_VERIFIED",
        "title": "Contract Verified",
        "summary_fn": lambda d, s: (
            "The purchase rules were verified before proceeding."
        ),
        "explanation_fn": _contract_pass_explanation if False else None,
    },
    "CONTRACT_VIOLATION": {
        "actor": ACTOR_AI, "status": "WARNING", "registry": "CONTRACT_BLOCKED",
        "title": "Contract Check Blocked",
        "summary_fn": lambda d, s: (
            d.get("message")
            or (d.get("violations")[0].get("message") if d.get("violations") else "")
            or "The action was blocked by your AI Commerce Contract."
        ),
        "explanation_fn": _contract_block_explanation,
    },
    "CONTRACT_ACTION_BLOCKED": {
        "actor": ACTOR_SYSTEM, "status": "WARNING", "registry": "CONTRACT_BLOCKED",
        "title": "Action Blocked by Contract",
        "summary_fn": lambda d, s: (
            d.get("message") or "The AI was prevented from performing this action by your Commerce Contract."
        ),
        "explanation_fn": _contract_block_explanation,
    },
    # ── Cart ──
    "CART_ITEM_UPDATED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "CART_UPDATED",
        "title": "Cart Updated",
        "summary_fn": lambda d, s: "Your cart contents were updated.",
    },
    "CART_VERIFIED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "CART_UPDATED",
        "title": "Cart Verified",
        "summary_fn": lambda d, s: (
            f"Your cart was verified ({d.get('item_count')} item(s), total {_money(d.get('total'))})."
        ),
    },
    "CHECKOUT_APPROVAL_REQUESTED": {
        "actor": ACTOR_SYSTEM, "status": "PENDING", "registry": "USER_APPROVED",
        "title": "Checkout Approval Requested",
        "summary_fn": lambda d, s: "NexaCart asked you to review and approve checkout before any payment.",
    },
    "USER_APPROVED_CHECKOUT": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "USER_APPROVED",
        "title": "User Approved Checkout",
        "summary_fn": lambda d, s: "You approved the checkout. Payment was authorized by you.",
    },
    # ── Payment ──
    "PAYMENT_CREATED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "PAYMENT_CREATED",
        "title": "Payment Created",
        "summary_fn": lambda d, s: (
            f"Payment of {_money(d.get('amount'))} was created."
        ),
        "explanation_fn": _payment_explanation,
    },
    "PAYMENT_RESUMED": {
        "actor": ACTOR_SYSTEM, "status": "PENDING", "registry": "PAYMENT_RESUMED",
        "title": "Payment Resumed",
        "summary_fn": lambda d, s: (
            "Your previous payment was resumed — no new charge."
        ),
    },
    "PAYMENT_PROCESSING": {
        "actor": ACTOR_SYSTEM, "status": "PENDING", "registry": "PAYMENT_CREATED",
        "title": "Payment Processing",
        "summary_fn": lambda d, s: "Your payment is being processed.",
    },
    "PAYMENT_SUCCESS": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "PAYMENT_COMPLETED",
        "title": "Payment Completed",
        "summary_fn": lambda d, s: (
            f"Payment of {_money(d.get('amount'))} was completed safely."
        ),
        "explanation_fn": _payment_explanation,
    },
    "PAYMENT_VERIFIED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "PAYMENT_COMPLETED",
        "title": "Payment Verified",
        "summary_fn": lambda d, s: "The payment was verified securely server-side.",
    },
    "PAYMENT_FAILED": {
        "actor": ACTOR_SYSTEM, "status": "ERROR", "registry": "PAYMENT_FAILED",
        "title": "Payment Failed",
        "summary_fn": lambda d, s: (
            f"Payment failed. You can try again when ready. {d.get('error') or ''}".strip()
        ),
    },
    "PAYMENT_CANCELLED": {
        "actor": ACTOR_USER, "status": "WARNING", "registry": "PAYMENT_FAILED",
        "title": "Payment Cancelled",
        "summary_fn": lambda d, s: "You cancelled/closed the payment. You can try again when ready.",
    },
    # ── Order ──
    "ORDER_CREATED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "ORDER_CREATED",
        "title": "Order Created",
        "summary_fn": lambda d, s: (
            f"Your order {d.get('order_id') or ''} was created from the successful payment.".strip()
        ),
        "explanation_fn": lambda d: {"type": "order", "order_id": d.get("order_id"), "total_amount": d.get("total_amount")},
    },
    "ORDER_CONFIRMED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "ORDER_CREATED",
        "title": "Order Confirmed",
        "summary_fn": lambda d, s: "Your order was confirmed. Purchase complete.",
    },
    "PURCHASE_COMPLETED": {
        "actor": ACTOR_SYSTEM, "status": "SUCCESS", "registry": "ORDER_CREATED",
        "title": "Purchase Complete",
        "summary_fn": lambda d, s: "Your purchase journey was completed end-to-end.",
    },
    # ── Decision Lab: simulations ──
    "SIMULATION_STARTED": {
        "actor": ACTOR_AI, "status": "PENDING", "registry": "SIMULATION_STARTED",
        "title": "What-If Simulation Started",
        "summary_fn": lambda d, s: f"What-if simulation started: {d.get('label') or 'Modified constraints'}.",
    },
    "CONSTRAINT_MODIFIED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "CONSTRAINT_MODIFIED",
        "title": "Constraints Modified",
        "summary_fn": lambda d, s: (
            f"You modified constraints: {d.get('label') or 'custom constraints'}."
        ),
    },
    "ALTERNATIVES_EXPLORED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "ALTERNATIVES_EXPLORED",
        "title": "Alternatives Explored",
        "summary_fn": lambda d, s: (
            f"The AI explored {d.get('alternatives_count', 0)} alternative product(s) "
            f"against your current recommendation."
        ),
    },
    "PRODUCT_COMPARED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "PRODUCT_COMPARED",
        "title": "Products Compared",
        "summary_fn": lambda d, s: (
            f"Compared {d.get('product_a_name', 'Product A')} vs {d.get('product_b_name', 'Product B')}."
        ),
    },
    "SIMULATION_COMPLETED": {
        "actor": ACTOR_AI, "status": "SUCCESS", "registry": "SIMULATION_COMPLETED",
        "title": "What-If Simulation Complete",
        "summary_fn": lambda d, s: (
            f"What-if simulation completed: {d.get('label') or 'Modified constraints'}."
        ),
        "explanation_fn": lambda d: {
            "type": "simulation",
            "simulation_id": d.get("simulation_id"),
            "changes": d.get("changes", []),
            "contract_warnings": d.get("contract_warnings", []),
        },
    },
    "SIMULATION_REJECTED": {
        "actor": ACTOR_USER, "status": "WARNING", "registry": "SIMULATION_REJECTED",
        "title": "Simulation Rejected",
        "summary_fn": lambda d, s: (
            f"You rejected the what-if simulation: {d.get('label') or 'modified constraints'}."
        ),
    },
    "SIMULATION_APPLIED": {
        "actor": ACTOR_USER, "status": "SUCCESS", "registry": "SIMULATION_APPLIED",
        "title": "Simulation Applied",
        "summary_fn": lambda d, s: (
            f"You applied the simulation recommendation: "
            f"{d.get('product_name', 'a product')} at {_money(d.get('product_price'))}."
        ),
    },
}


def map_event(event_type: str) -> Optional[Dict[str, Any]]:
    """Return the mapping entry for an event type, or None to skip it."""
    return CANONICAL_MAP.get(event_type)
