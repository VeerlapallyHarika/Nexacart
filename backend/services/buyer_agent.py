"""Autonomous Buyer Agent.

A separate, non-interactive agent from the chat-based ``CartAgent``. It accepts a
single natural-language goal and runs a closed autonomous loop that reuses the
*exact same* tool implementations as the human chat flow (search_products,
get_product_details, compare_products, add_to_cart, view_cart, verify_cart),
while enforcing the active CommerceContract via the existing
``ContractValidator``.

It deliberately NEVER calls ``request_checkout_approval`` or any payment tool —
when the cart is verified and ready for approval it stops and waits, exactly
like the human-in-the-loop flow.

Every action is written to:
  * the ``buyer_agent_runs`` table (structured per-step log), and
  * the shared audit trail (``audit_events``) tagged with ``source: buyer_agent``.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from agents.cart_agent import CartAgent
from services.intent_service import IntentService
from services.event_service import EventService
from services.contract_validator import ContractValidator
from services.product_service import ProductService
from services.cart_service import CartService
from services.contract_constants import CONTRACT_VIOLATION
from models.buyer_agent_run import BuyerAgentRun
from services.decision_trace_service import DecisionTraceService
import uuid


ACTION_SEARCH = "search_products"
ACTION_DETAILS = "get_product_details"
ACTION_COMPARE = "compare_products"
ACTION_ADD = "add_to_cart"
ACTION_VIEW = "view_cart"
ACTION_VERIFY = "verify_cart"

# ── Orchestration journey events ──────────────────────────────────────
# First-class journey events written to the shared `audit_events` table so the
# AI Buyer Agent's decisions become part of the same purchase narrative that
# Purchase Replay reconstructs.
EVENT_BUYER_GOAL_UNDERSTOOD = "BUYER_GOAL_UNDERSTOOD"
EVENT_PRODUCT_RECOMMENDED = "PRODUCT_RECOMMENDED"
EVENT_PRODUCT_REJECTED = "PRODUCT_REJECTED_BY_CONTRACT"


def _truncate(value: Any, max_len: int = 4000) -> Any:
    """Keep audit-event payloads from growing unbounded."""
    import json as _json

    try:
        text = _json.dumps(value)
        if len(text) <= max_len:
            return value
        return f"[truncated payload > {max_len} chars]"
    except Exception:
        return "[unserializable payload]"


class BuyerAgent:
    # Final states returned by the endpoint.
    RECOMMENDATION_READY = "recommendation_ready"
    READY_FOR_APPROVAL = "ready_for_approval"
    BLOCKED_BY_CONTRACT = "blocked_by_contract"
    MAX_STEPS_REACHED = "max_steps_reached"
    NO_MATCHING_PRODUCTS = "no_matching_products"
    ERROR = "error"

    DEFAULT_MAX_STEPS = 8

    def __init__(self):
        # CartAgent's tool methods (_search_products, _add_to_cart, ...) do not
        # touch the OpenAI client, so we can reuse them without an API key.
        self.cart_agent = CartAgent()

    # ── Public API ──────────────────────────────────────────────────

    def run(
        self,
        db: Session,
        goal: str,
        session_id: str,
        user_id: Optional[str] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        auto_approve: bool = False,
        approve_product_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_id = run_id or f"buyer_{uuid.uuid4().hex[:12]}"
        actions: List[Dict[str, Any]] = []

        trace = DecisionTraceService.get_trace_by_session(db, session_id) if approve_product_id else None
        if not trace:
            trace = DecisionTraceService.create_new_trace(
                db=db, session_id=session_id, goal=goal, user_id=user_id
            )

        def record(action: str, args: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, Any]:
            step_no = len(actions) + 1
            ts = datetime.now(timezone.utc).isoformat()
            row = BuyerAgentRun(
                run_id=run_id,
                session_id=session_id,
                goal=goal,
                step=step_no,
                action=action,
                input=args,
                output=output,
                timestamp=ts,
            )
            db.add(row)
            db.commit()
            db.refresh(row)

            # Mirror into the shared human-chat audit trail, tagged as buyer_agent.
            EventService.log_event(
                db=db,
                session_id=session_id,
                event_type="BUYER_AGENT_STEP",
                actor="buyer_agent",
                summary=f"[buyer_agent] {action} (step {step_no})",
                data={
                    "source": "buyer_agent",
                    "run_id": run_id,
                    "step": step_no,
                    "action": action,
                    "input": args,
                    "output": _truncate(output),
                    "user_id": user_id,
                    "decision_id": trace.decision_id,
                },
            )

            entry = {
                "step": step_no,
                "action": action,
                "input": args,
                "output": output,
                "timestamp": ts,
            }
            actions.append(entry)
            return entry

        try:
            return self._run_impl(
                db, run_id, session_id, goal, trace.decision_id, user_id, max_steps, record, actions,
                auto_approve=auto_approve, approve_product_id=approve_product_id
            )
        except Exception as exc:
            db.rollback()
            try:
                EventService.log_event(
                    db=db,
                    session_id=session_id,
                    event_type="BUYER_AGENT_ERROR",
                    actor="buyer_agent",
                    summary=f"[buyer_agent] run failed at step {len(actions) + 1}",
                    data={
                        "source": "buyer_agent",
                        "run_id": run_id,
                        "final_state": self.ERROR,
                        "error": str(exc),
                        "user_id": user_id,
                        "decision_id": trace.decision_id,
                    },
                )
            except Exception:
                pass
            return self._finalize(
                run_id, session_id, trace.decision_id, goal, self.ERROR,
                f"Internal error during autonomous run: {exc}", None, actions,
            )

    def _run_impl(
        self,
        db: Session,
        run_id: str,
        session_id: str,
        goal: str,
        decision_id: str,
        user_id: Optional[str],
        max_steps: int,
        record,
        actions: List[Dict[str, Any]],
        auto_approve: bool = False,
        approve_product_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        final_state: Optional[str] = None
        reason: Optional[str] = None
        added_product_id: Optional[str] = None

        intent = IntentService.extract_intent(goal, db=db)
        category = intent.get("category")
        max_price = intent.get("max_price")
        min_price = intent.get("min_price")
        constraints = intent.get("constraints", []) or []

        # Only clear cart on initial evaluation, not during explicit purchase approval
        if not approve_product_id:
            CartService.clear_cart(db, session_id)

        attributes: Dict[str, Any] = {c.key: c.value for c in constraints}

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=EVENT_BUYER_GOAL_UNDERSTOOD,
            actor="buyer_agent",
            summary=f"[buyer_agent] understood goal: {goal}",
            data={
                "source": "buyer_agent",
                "run_id": run_id,
                "goal": goal,
                "category": category,
                "max_price": max_price,
                "min_price": min_price,
                "constraints": [
                    {"key": c.key, "value": c.value, "op": c.operator}
                    for c in constraints
                ] if constraints else [],
                "active_contract": self._active_contract_summary(db, session_id),
            },
        )

        # ── Step 1: search ──────────────────────────────────────────
        search_args = {
            "category": category,
            "max_price": max_price,
            "min_price": min_price,
            "attributes": attributes,
            "query": goal,
        }
        search_out = self.cart_agent._search_products(search_args, db, session_id)
        record(ACTION_SEARCH, search_args, search_out)

        if self._is_contract_blocked(search_out):
            final_state = self.BLOCKED_BY_CONTRACT
            reason = "search blocked by active Commerce Contract"
            self._log_contract_violation(db, session_id, run_id, len(actions), ACTION_SEARCH, search_out)
            return self._finalize(run_id, session_id, decision_id, goal, final_state, reason, added_product_id, actions)

        if len(actions) >= max_steps:
            return self._finalize(
                run_id, session_id, decision_id, goal, self.MAX_STEPS_REACHED,
                "max step count reached", added_product_id, actions,
            )

        target_result = ProductService.generic_search(
            db,
            category=category,
            max_price=max_price,
            min_price=min_price,
            constraints=None,
            query=goal,
            limit=5,
        )
        target_objs = target_result.products
        query_ranked = ProductService._filter_by_query(target_objs, goal)
        target_pool = query_ranked if query_ranked else target_objs
        target_products = [
            {"id": p.id, "name": p.name, "price": p.price, "category": p.category}
            for p in target_pool
        ]

        products = search_out.get("products", []) if isinstance(search_out, dict) else []
        if not products:
            active_contract = ContractValidator.get_active_contract(db, session_id)
            if active_contract and target_products:
                products = target_products
            elif active_contract:
                self._log_contract_violation(
                    db, session_id, run_id, len(actions), ACTION_SEARCH,
                    {"blocked": True, "reason": "contract_violation",
                     "message": "no products satisfy the active Commerce Contract",
                     "violations": []},
                )
                final_state = self.BLOCKED_BY_CONTRACT
                reason = "no products satisfy the active Commerce Contract"
                return self._finalize(run_id, session_id, decision_id, goal, final_state, reason, added_product_id, actions)
            else:
                label = category or "products"
                budget = f" under ₹{max_price:,.0f}" if max_price else ""
                return self._finalize(
                    run_id, session_id, decision_id, goal, self.NO_MATCHING_PRODUCTS,
                    f"No {label}{budget} were found in the catalog",
                    added_product_id, actions,
                )

        # ── Step 2: compare top candidates ──────────────────────────
        top_pool = target_products if target_products else products
        goal_compliant = [
            p for p in top_pool
            if self._within_goal_budget(p, max_price, min_price)
        ]
        top = goal_compliant[:3]
        if not top:
            label = category or "products"
            budget = f" under ₹{max_price:,.0f}" if max_price else ""
            return self._finalize(
                run_id, session_id, decision_id, goal, self.NO_MATCHING_PRODUCTS,
                f"No {label}{budget} were found in the catalog",
                added_product_id, actions,
            )

        if len(top) >= 2 and len(actions) < max_steps:
            compare_args = {"product_ids": [p["id"] for p in top]}
            compare_out = self.cart_agent._compare_products(compare_args, db, session_id)
            record(ACTION_COMPARE, compare_args, compare_out)
            if len(actions) >= max_steps:
                return self._finalize(
                    run_id, session_id, decision_id, goal, self.MAX_STEPS_REACHED,
                    "max step count reached", added_product_id, actions,
                )

        # ── Step 3: get details for best candidate ─────────────────
        best = self._select_best(top)
        if approve_product_id:
            from models.product import Product
            approved_obj = db.query(Product).filter(Product.id == approve_product_id).first()
            if approved_obj:
                best = {"id": approved_obj.id, "name": approved_obj.name, "price": approved_obj.price, "category": approved_obj.category}

        self._log_recommendation(
            db, session_id, run_id, best,
            max_price=max_price, min_price=min_price, goal=goal,
        )
        details_args = {"product_id": best["id"]}
        details_out = self.cart_agent._get_product_details(details_args, db, session_id)
        record(ACTION_DETAILS, details_args, details_out)
        if len(actions) >= max_steps:
            return self._finalize(
                run_id, session_id, decision_id, goal, self.MAX_STEPS_REACHED,
                "max step count reached", added_product_id, actions,
                recommended_product_id=best["id"],
            )

        # ── AI Native Decision Stop ────────────────────────────────
        # Stop at recommendation_ready so the human can review the choice and
        # explicitly click "Approve Purchase". Do NOT add to cart yet.
        if not auto_approve and not approve_product_id:
            return self._finalize(
                run_id,
                session_id,
                decision_id,
                goal,
                self.RECOMMENDATION_READY,
                "AI recommendation generated. Awaiting human approval before cart insertion.",
                None,
                actions,
                recommended_product_id=best["id"],
            )

        # ── Step 4: add to cart (contract-enforced by tool) ────────
        if not self._within_goal_budget(best, max_price, min_price):
            label = category or "product"
            budget = f" within ₹{min_price:,.0f}-₹{max_price:,.0f}" if (min_price and max_price) else (f" under ₹{max_price:,.0f}" if max_price else "")
            return self._finalize(
                run_id, session_id, decision_id, goal, self.NO_MATCHING_PRODUCTS,
                f"No {label} {budget.strip()} was found in the catalog",
                added_product_id, actions,
                recommended_product_id=best["id"],
            )
        add_args = {"product_id": best["id"], "quantity": 1}
        add_out = self.cart_agent._add_to_cart(add_args, db, session_id)
        record(ACTION_ADD, add_args, add_out)

        if len(actions) >= max_steps:
            return self._finalize(
                run_id, session_id, decision_id, goal, self.MAX_STEPS_REACHED,
                "max step count reached", added_product_id, actions,
                recommended_product_id=best["id"],
            )

        if self._is_contract_blocked(add_out):
            self._log_contract_violation(db, session_id, run_id, len(actions), ACTION_ADD, add_out)
            EventService.log_event(
                db=db,
                session_id=session_id,
                event_type=EVENT_PRODUCT_REJECTED,
                actor="buyer_agent",
                summary=f"[buyer_agent] rejected {best.get('name')} due to active Commerce Contract",
                data={
                    "source": "buyer_agent",
                    "run_id": run_id,
                    "product_id": best.get("id"),
                    "product_name": best.get("name"),
                    "product_price": best.get("price"),
                    "reason": add_out.get("message") or "violates active Commerce Contract",
                    "violations": (add_out.get("violations") or []) if isinstance(add_out, dict) else [],
                },
            )
            final_state = self.BLOCKED_BY_CONTRACT
            reason = add_out.get("message") or "add_to_cart blocked by active Commerce Contract"
            return self._finalize(
                run_id, session_id, decision_id, goal, final_state, reason, added_product_id, actions, recommended_product_id=best["id"]
            )

        added_product_id = best["id"]

        # ── Step 5: view cart ───────────────────────────────────────
        view_out = self.cart_agent._view_cart({}, db, session_id)
        record(ACTION_VIEW, {}, view_out)

        # ── Step 6: verify cart ─────────────────────────────────────
        verify_out = self.cart_agent._verify_cart({}, db, session_id)
        record(ACTION_VERIFY, {}, verify_out)

        if isinstance(verify_out, dict) and verify_out.get("verified"):
            final_state = self.READY_FOR_APPROVAL
        else:
            final_state = self.MAX_STEPS_REACHED
            reason = "cart could not be verified (prices/inventory changed or empty)"

        if final_state is None:
            final_state = self.MAX_STEPS_REACHED

        return self._finalize(
            run_id, session_id, decision_id, goal, final_state, reason, added_product_id, actions, recommended_product_id=best["id"]
        )

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _is_contract_blocked(output: Any) -> bool:
        """A contract block returns a payload with ``blocked: True``."""
        if not isinstance(output, dict):
            return False
        return bool(output.get("blocked")) or (
            isinstance(output.get("reason"), str)
            and output.get("reason") == "contract_violation"
        )

    @staticmethod
    def _active_contract_summary(db: Session, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a small, safe, human-readable snapshot of the active contract."""
        contract = ContractValidator.get_active_contract(db, session_id)
        if not contract:
            return None
        return {
            "id": contract.id,
            "status": contract.status,
            "max_budget": contract.max_budget,
            "currency": contract.currency or "INR",
            "required_categories": contract.required_categories or [],
            "required_attributes": contract.required_attributes or {},
            "minimum_battery_hours": contract.minimum_battery_hours,
            "excluded_conditions": contract.excluded_conditions or [],
        }

    def _log_recommendation(
        self,
        db: Session,
        session_id: str,
        run_id: str,
        product: Dict[str, Any],
        max_price: Optional[float],
        min_price: Optional[float],
        goal: str,
    ) -> None:
        """Record a first-class `PRODUCT_RECOMMENDED` journey event explaining the
        agent's selection and whether it was constrained by the active contract."""
        contract = ContractValidator.get_active_contract(db, session_id)
        price = product.get("price")
        within_contract = True
        contract_note = None
        if contract and price is not None and contract.max_budget is not None:
            within_contract = price <= contract.max_budget
            contract_note = (
                f"within your ₹{contract.max_budget:,.0f} contract budget"
                if within_contract
                else f"exceeds your ₹{contract.max_budget:,.0f} contract budget"
            )

        within_goal = self._within_goal_budget(product, max_price, min_price)
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=EVENT_PRODUCT_RECOMMENDED,
            actor="buyer_agent",
            summary=f"[buyer_agent] recommended {product.get('name')}",
            data={
                "source": "buyer_agent",
                "run_id": run_id,
                "goal": goal,
                "product_id": product.get("id"),
                "product_name": product.get("name"),
                "product_price": price,
                "category": product.get("category"),
                "within_goal_budget": within_goal,
                "within_contract_budget": within_contract,
                "contract_note": contract_note,
                "contract_active": contract is not None,
            },
        )

    @staticmethod
    def _select_best(products: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not products:
            raise ValueError("No products to select from")
        return products[0]

    @staticmethod
    def _within_goal_budget(
        product: Dict[str, Any],
        max_price: Optional[float],
        min_price: Optional[float],
    ) -> bool:
        price = product.get("price")
        if price is None:
            return True
        if max_price is not None and price > max_price:
            return False
        if min_price is not None and price < min_price:
            return False
        return True

    @staticmethod
    def _log_contract_violation(
        db: Session,
        session_id: str,
        run_id: str,
        step: int,
        action: str,
        blocked_output: Dict[str, Any],
    ) -> None:
        """Mirror a contract block into the shared audit trail tagged buyer_agent."""
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type=CONTRACT_VIOLATION,
            actor="buyer_agent",
            summary=f"[buyer_agent] {action} blocked by Commerce Contract (step {step})",
            data={
                "source": "buyer_agent",
                "run_id": run_id,
                "step": step,
                "action": action,
                "violations": blocked_output.get("violations", []) if isinstance(blocked_output, dict) else [],
                "message": blocked_output.get("message") if isinstance(blocked_output, dict) else None,
            },
        )

    @staticmethod
    def _finalize(
        run_id: str,
        session_id: str,
        decision_id: str,
        goal: str,
        final_state: str,
        reason: Optional[str],
        added_product_id: Optional[str],
        actions: List[Dict[str, Any]],
        recommended_product_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "session_id": session_id,
            "decision_id": decision_id,
            "goal": goal,
            "final_state": final_state,
            "reason": reason,
            "added_product_id": added_product_id,
            "recommended_product_id": recommended_product_id,
            "actions": actions,
        }

    @staticmethod
    def get_run_log(db: Session, run_id: str) -> List[Dict[str, Any]]:
        """Read back the persisted per-step log for a run (from buyer_agent_runs)."""
        rows = (
            db.query(BuyerAgentRun)
            .filter(BuyerAgentRun.run_id == run_id)
            .order_by(BuyerAgentRun.step)
            .all()
        )
        return [
            {
                "step": r.step,
                "action": r.action,
                "input": r.input or {},
                "output": r.output or {},
                "timestamp": r.timestamp,
            }
            for r in rows
        ]
