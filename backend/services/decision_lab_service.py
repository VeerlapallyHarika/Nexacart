from sqlalchemy.orm import Session
from models.decision_trace import DecisionTrace
from models.decision_simulation import DecisionSimulation
from models.event import AuditEvent
from models.product import Product
from services.product_service import ProductService, SearchConstraint
from services.event_service import EventService
from services.contract_validator import ContractValidator
from services.intent_service import IntentService
from typing import Dict, Any, Optional, List, Tuple
import uuid
import secrets


_SIM_PREFIX = "SIM"


def _random_segment(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _money(value) -> str:
    try:
        return f"\u20b9{float(value):,.0f}"
    except (TypeError, ValueError):
        return ""


class DecisionLabService:
    # ── Simulation ID generation ─────────────────────────────────────
    @staticmethod
    def generate_simulation_id() -> str:
        return f"{_SIM_PREFIX}-NX-{_random_segment()}"

    # ── Retrieve original constraints from the trace ────────────────
    @staticmethod
    def _get_original_constraints(
        db: Session, session_id: str, decision_id: str
    ) -> Dict[str, Any]:
        """Extract the original search constraints from the trace's audit events.

        First looks for BUYER_GOAL_UNDERSTOOD (which has structured data),
        then falls back to extracting from the trace goal via IntentService.
        """
        goal_event = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.session_id == session_id,
                AuditEvent.decision_id == decision_id,
                AuditEvent.event_type == "BUYER_GOAL_UNDERSTOOD",
            )
            .order_by(AuditEvent.id)
            .first()
        )
        if goal_event and goal_event.data:
            d = goal_event.data
            raw_constraints = d.get("constraints") or []
            constraints = []
            for c in raw_constraints:
                if isinstance(c, dict):
                    constraints.append(
                        SearchConstraint(
                            key=c.get("key", ""),
                            value=c.get("value"),
                            operator=c.get("operator", "eq"),
                        )
                    )
            return {
                "category": d.get("category"),
                "max_price": d.get("max_price"),
                "min_price": d.get("min_price"),
                "brand": d.get("brand"),
                "constraints": constraints,
            }

        trace = DecisionTraceService.get_trace(db, decision_id)
        goal = trace.goal if trace else None
        if not goal:
            return {
                "category": None,
                "max_price": None,
                "min_price": None,
                "brand": None,
                "constraints": [],
            }
        intent = IntentService.extract_intent(goal, db=db)
        return {
            "category": intent.get("category"),
            "max_price": intent.get("max_price"),
            "min_price": intent.get("min_price"),
            "brand": intent.get("brand"),
            "constraints": intent.get("constraints") or [],
        }

    # ── Get the recommended product from the trace ───────────────────
    @staticmethod
    def _get_recommended_product(
        db: Session, session_id: str, decision_id: str
    ) -> Optional[Dict[str, Any]]:
        rec_event = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.session_id == session_id,
                AuditEvent.decision_id == decision_id,
                AuditEvent.event_type == "PRODUCT_RECOMMENDED",
            )
            .order_by(AuditEvent.id.desc())
            .first()
        )
        if rec_event and rec_event.data:
            pid = rec_event.data.get("product_id")
            if pid:
                product = ProductService.get_product(db, pid)
                if product:
                    return {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "currency": product.currency,
                        "category": product.category,
                        "attributes": product.attributes or {},
                        "stock_quantity": product.stock_quantity,
                    }
        return None

    # ── Explanation: WHY this recommendation? ────────────────────────
    @staticmethod
    def explain_recommendation(
        db: Session, decision_id: str
    ) -> Optional[Dict[str, Any]]:
        trace = DecisionTraceService.get_trace(db, decision_id)
        if not trace:
            return None
        session_id = trace.session_id
        orig = DecisionLabService._get_original_constraints(
            db, session_id, decision_id
        )
        rec = DecisionLabService._get_recommended_product(db, session_id, decision_id)
        if not rec:
            return None

        product_obj = db.query(Product).filter(Product.id == rec["id"]).first()
        if not product_obj:
            return None

        raw_score, breakdown, match_pct = ProductService.compute_score(
            product_obj, orig["max_price"], orig["constraints"]
        )

        # Count total candidates considered
        result = ProductService.generic_search(
            db,
            category=orig["category"],
            max_price=orig["max_price"],
            min_price=orig["min_price"],
            brand=orig["brand"],
            constraints=orig["constraints"],
            limit=100,
        )
        total_scanned = result.total_scanned
        total_candidates = len(result.products)

        strong_matches = []
        trade_offs = []

        # Budget analysis
        max_price = orig["max_price"]
        if max_price:
            price_ratio = rec["price"] / max_price if max_price > 0 else 0
            if rec["price"] <= max_price:
                strong_matches.append(
                    f"Within your {_money(max_price)} budget"
                    + (
                        f" ({_money(rec['price'])}, leaving {_money(max_price - rec['price'])} headroom)"
                        if price_ratio < 0.85
                        else ""
                    )
                )
            else:
                trade_offs.append(
                    f"Exceeds your {_money(max_price)} budget by {_money(rec['price'] - max_price)}"
                )

        # Constraint analysis
        for detail in breakdown.get("constraint_details", []):
            key = detail["key"]
            actual = detail.get("actual")
            target = detail.get("target")
            if detail["satisfied"]:
                label = key.replace("_", " ").replace("gb", " GB").replace("mah", " mAh").replace("hours", " hr").strip()
                strong_matches.append(f"Matches {label} preference ({actual})")
            else:
                label = key.replace("_", " ").strip()
                if actual is not None:
                    trade_offs.append(
                        f"{label} is {actual} vs requested {target}"
                    )
                else:
                    trade_offs.append(f"Does not have {label} attribute")

        # Contract check
        contract = ContractValidator.get_active_contract(db, session_id)
        contract_info = None
        if contract:
            check = ContractValidator.check_product(db, session_id, product_obj)
            if not check.get("allowed"):
                for v in check.get("violations", []):
                    trade_offs.append(v.get("message", ""))
            contract_info = {
                "active": True,
                "max_budget": contract.max_budget,
                "passed": check.get("allowed", True),
            }

        return {
            "decision_id": decision_id,
            "product": rec,
            "match_percentage": match_pct,
            "raw_score": round(raw_score, 3),
            "breakdown": breakdown,
            "strong_matches": strong_matches,
            "trade_offs": trade_offs,
            "total_candidates_scanned": total_scanned,
            "total_candidates_ranked": total_candidates,
            "contract": contract_info,
        }

    # ── Alternatives: real candidates from the search pipeline ───────
    @staticmethod
    def get_alternatives(
        db: Session, decision_id: str, limit: int = 5
    ) -> Optional[Dict[str, Any]]:
        trace = DecisionTraceService.get_trace(db, decision_id)
        if not trace:
            return None
        session_id = trace.session_id
        orig = DecisionLabService._get_original_constraints(
            db, session_id, decision_id
        )
        rec = DecisionLabService._get_recommended_product(db, session_id, decision_id)
        rec_id = rec["id"] if rec else None

        result = ProductService.generic_search(
            db,
            category=orig["category"],
            max_price=orig["max_price"],
            min_price=orig["min_price"],
            brand=orig["brand"],
            constraints=orig["constraints"],
            limit=max(limit + 5, 20),
        )
        alternatives = []
        for p in result.products:
            if p.id == rec_id:
                continue
            raw_score, breakdown, match_pct = ProductService.compute_score(
                p, orig["max_price"], orig["constraints"]
            )
            alternatives.append({
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "currency": p.currency,
                "category": p.category,
                "attributes": p.attributes or {},
                "stock_quantity": p.stock_quantity,
                "match_percentage": match_pct,
                "score": round(raw_score, 3),
            })
            if len(alternatives) >= limit:
                break

        return {
            "decision_id": decision_id,
            "original_product": rec,
            "alternatives": alternatives,
            "total_candidates": len(result.products),
            "match_type": result.match_type,
        }

    # ── Generic product comparison ───────────────────────────────────
    @staticmethod
    def compare_products(
        db: Session, product_a_id: str, product_b_id: str
    ) -> Optional[Dict[str, Any]]:
        pa = db.query(Product).filter(Product.id == product_a_id).first()
        pb = db.query(Product).filter(Product.id == product_b_id).first()
        if not pa or not pb:
            return None

        a_attrs = pa.attributes or {}
        b_attrs = pb.attributes or {}
        all_keys = list(dict.fromkeys(list(a_attrs.keys()) + list(b_attrs.keys())))

        product_a = {
            "id": pa.id, "name": pa.name, "price": pa.price,
            "currency": pa.currency, "category": pa.category,
            "attributes": a_attrs,
        }
        product_b = {
            "id": pb.id, "name": pb.name, "price": pb.price,
            "currency": pb.currency, "category": pb.category,
            "attributes": b_attrs,
        }

        comparisons = []

        # Price comparison (special: lower is better for buyer)
        pa_price = pa.price
        pb_price = pb.price
        price_diff = pb_price - pa_price
        if abs(price_diff) < 1:
            verdict_price = "similar"
        elif pb_price < pa_price:
            verdict_price = "b_better"
        else:
            verdict_price = "a_better"
        comparisons.append({
            "attribute": "price",
            "label": "Price",
            "a_value": pa_price,
            "b_value": pb_price,
            "a_display": _money(pa_price),
            "b_display": _money(pb_price),
            "verdict": verdict_price,
            "summary": (
                f"{pb.name} is {_money(abs(price_diff))} cheaper"
                if pb_price < pa_price
                else (f"{pa.name} is {_money(abs(price_diff))} cheaper" if pa_price < pb_price else "Same price")
            ),
        })

        for key in all_keys:
            a_val = a_attrs.get(key)
            b_val = b_attrs.get(key)
            if a_val is None and b_val is None:
                continue

            label = key.replace("_", " ").title()
            verdict = "similar"
            summary = ""

            try:
                a_num = float(a_val) if a_val is not None else None
                b_num = float(b_val) if b_val is not None else None
                if a_num is not None and b_num is not None:
                    diff = b_num - a_num
                    if abs(diff) < 0.01:
                        verdict = "similar"
                        summary = f"Both have {a_val}"
                    elif diff > 0:
                        verdict = "b_better"
                        summary = f"{pb.name} has higher {label}"
                    else:
                        verdict = "a_better"
                        summary = f"{pa.name} has higher {label}"
                else:
                    verdict = "similar" if str(a_val) == str(b_val) else "tradeoff"
                    summary = f"{pa.name}: {a_val} vs {pb.name}: {b_val}"
            except (ValueError, TypeError):
                if isinstance(a_val, bool) and isinstance(b_val, bool):
                    if a_val == b_val:
                        verdict = "similar"
                        summary = f"Both {'have' if a_val else 'lack'} {label}"
                    else:
                        verdict = "tradeoff"
                        summary = f"{pa.name}: {'yes' if a_val else 'no'} vs {pb.name}: {'yes' if b_val else 'no'}"
                elif str(a_val).lower() == str(b_val).lower():
                    verdict = "similar"
                    summary = f"Both: {a_val}"
                else:
                    verdict = "tradeoff"
                    summary = f"{pa.name}: {a_val} vs {pb.name}: {b_val}"

            comparisons.append({
                "attribute": key,
                "label": label,
                "a_value": a_val,
                "b_value": b_val,
                "a_display": str(a_val) if a_val is not None else "N/A",
                "b_display": str(b_val) if b_val is not None else "N/A",
                "verdict": verdict,
                "summary": summary,
            })

        a_score, _, a_pct = ProductService.compute_score(pa, None, [])
        b_score, _, b_pct = ProductService.compute_score(pb, None, [])

        return {
            "product_a": product_a,
            "product_b": product_b,
            "comparisons": comparisons,
            "overall_a_match": a_pct,
            "overall_b_match": b_pct,
        }

    # ── Run simulation ───────────────────────────────────────────────
    @staticmethod
    def run_simulation(
        db: Session,
        session_id: str,
        decision_id: str,
        label: Optional[str],
        modified_category: Optional[str],
        modified_max_price: Optional[float],
        modified_min_price: Optional[float],
        modified_brand: Optional[str],
        modified_constraints: Optional[List[SearchConstraint]],
    ) -> Optional[Dict[str, Any]]:
        trace = DecisionTraceService.get_trace(db, decision_id)
        if not trace:
            return None

        orig = DecisionLabService._get_original_constraints(
            db, session_id, decision_id
        )
        rec = DecisionLabService._get_recommended_product(db, session_id, decision_id)

        sim_constraints = modified_constraints or []
        sim_category = modified_category if modified_category is not None else orig["category"]
        sim_max_price = modified_max_price if modified_max_price is not None else orig["max_price"]
        sim_min_price = modified_min_price if modified_min_price is not None else orig["min_price"]
        sim_brand = modified_brand if modified_brand is not None else orig["brand"]

        result = ProductService.generic_search(
            db,
            category=sim_category,
            max_price=sim_max_price,
            min_price=sim_min_price,
            brand=sim_brand,
            constraints=sim_constraints,
            limit=20,
        )

        new_candidates = []
        for p in result.products:
            raw_score, breakdown, match_pct = ProductService.compute_score(
                p, sim_max_price, sim_constraints
            )
            new_candidates.append({
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "currency": p.currency,
                "category": p.category,
                "attributes": p.attributes or {},
                "stock_quantity": p.stock_quantity,
                "match_percentage": match_pct,
                "score": round(raw_score, 3),
            })

        sim_product = new_candidates[0] if new_candidates else None

        # Contract check for the simulation search
        contract_warnings = []
        contract = ContractValidator.get_active_contract(db, session_id)
        contract_info = {"active": contract is not None}
        if contract:
            if contract.max_budget and sim_max_price and sim_max_price > contract.max_budget:
                contract_warnings.append(
                    f"Your simulation searches up to {_money(sim_max_price)}, "
                    f"but your Commerce Contract limits purchases to {_money(contract.max_budget)}."
                )
            if sim_product:
                prod_obj = db.query(Product).filter(Product.id == sim_product["id"]).first()
                if prod_obj:
                    check = ContractValidator.check_product(db, session_id, prod_obj)
                    if not check.get("allowed"):
                        for v in check.get("violations", []):
                            contract_warnings.append(v.get("message", ""))
                        contract_info["recommendation_blocked"] = True
                    else:
                        contract_info["recommendation_blocked"] = False

        # Compute changes
        changes = []
        if rec and sim_product:
            if sim_product["id"] != rec["id"]:
                changes.append(f"New recommendation: {sim_product['name']} instead of {rec['name']}")
            price_diff = sim_product["price"] - rec["price"]
            if abs(price_diff) > 0.5:
                direction = "more" if price_diff > 0 else "less"
                changes.append(
                    f"Price {_money(abs(price_diff))} {direction} "
                    f"({_money(rec['price'])} \u2192 {_money(sim_product['price'])})"
                )
            if sim_product.get("match_percentage", 0) != rec.get("match_percentage", 0) if isinstance(rec, dict) else True:
                changes.append(
                    f"Match score changed ({sim_product.get('match_percentage', 0)}%)"
                )
            if sim_product["category"] != rec["category"]:
                changes.append(
                    f"Category changed ({rec['category']} \u2192 {sim_product['category']})"
                )
        elif sim_product and not rec:
            changes.append(f"Found recommendation: {sim_product['name']}")
        elif not sim_product:
            changes.append("No matching products found under modified constraints")

        # Extra products now eligible
        extra_count = len(new_candidates) - (1 if rec else 0)
        if extra_count > 0 and len(new_candidates) > 1:
            changes.append(f"{extra_count} product(s) available in the modified search")

        # Build label if not provided
        if not label:
            parts = []
            if modified_max_price is not None and modified_max_price != orig.get("max_price"):
                parts.append(f"Budget \u2192 {_money(modified_max_price)}")
            if modified_category is not None and modified_category != orig.get("category"):
                parts.append(f"Category \u2192 {modified_category}")
            if modified_constraints:
                for c in modified_constraints:
                    parts.append(f"{c.key} \u2192 {c.value}")
            label = " + ".join(parts) if parts else "Modified constraints"

        # Number this simulation
        existing = db.query(DecisionSimulation).filter(
            DecisionSimulation.decision_id == decision_id
        ).count()

        sim_id = DecisionLabService.generate_simulation_id()
        simulation = DecisionSimulation(
            simulation_id=sim_id,
            decision_id=decision_id,
            session_id=session_id,
            simulation_number=existing + 1,
            label=label,
            original_constraints={
                "category": orig.get("category"),
                "max_price": orig.get("max_price"),
                "min_price": orig.get("min_price"),
                "brand": orig.get("brand"),
                "constraints": [
                    {"key": c.key, "value": c.value, "operator": c.operator}
                    for c in (orig.get("constraints") or [])
                ],
            },
            modified_constraints={
                "category": sim_category,
                "max_price": sim_max_price,
                "min_price": sim_min_price,
                "brand": sim_brand,
                "constraints": [
                    {"key": c.key, "value": c.value, "operator": c.operator}
                    for c in sim_constraints
                ],
            },
            result={
                "original_product": rec,
                "simulated_product": sim_product,
                "alternatives": new_candidates[1:6],
                "changes": changes,
                "total_candidates": len(result.products),
                "match_type": result.match_type,
            },
            contract_warnings=contract_warnings,
            status="COMPLETED",
        )
        db.add(simulation)
        db.commit()
        db.refresh(simulation)

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="SIMULATION_COMPLETED",
            actor="ai",
            summary=f"What-if simulation completed: {label}",
            data={
                "simulation_id": sim_id,
                "decision_id": decision_id,
                "label": label,
                "original_product_id": rec["id"] if rec else None,
                "simulated_product_id": sim_product["id"] if sim_product else None,
                "changes": changes,
                "contract_warnings": contract_warnings,
            },
        )

        return {
            "simulation_id": sim_id,
            "decision_id": decision_id,
            "simulation_number": existing + 1,
            "label": label,
            "original_constraints": simulation.original_constraints,
            "modified_constraints": simulation.modified_constraints,
            "result": simulation.result,
            "contract_warnings": contract_warnings,
            "contract": contract_info,
            "status": "COMPLETED",
            "created_at": simulation.created_at,
        }

    # ── Apply simulation ─────────────────────────────────────────────
    @staticmethod
    def apply_simulation(
        db: Session, simulation_id: str, session_id: str
    ) -> Optional[Dict[str, Any]]:
        from services.cart_service import CartService

        sim = (
            db.query(DecisionSimulation)
            .filter(DecisionSimulation.simulation_id == simulation_id)
            .first()
        )
        if not sim:
            return None

        result = sim.result or {}
        sim_product = result.get("simulated_product")
        if not sim_product:
            return {"error": "No simulated product to apply"}

        prod_obj = db.query(Product).filter(Product.id == sim_product["id"]).first()
        if not prod_obj:
            return {"error": "Product not found in catalog"}

        contract = ContractValidator.get_active_contract(db, session_id)
        if contract:
            check = ContractValidator.check_product(db, session_id, prod_obj)
            if not check.get("allowed"):
                return {
                    "error": "contract_violation",
                    "violations": check.get("violations", []),
                    "message": "; ".join(
                        v.get("message", "") for v in check.get("violations", [])
                    ),
                }

        trace = DecisionTraceService.get_trace(db, sim.decision_id)

        goal = trace.goal if trace else None
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="PRODUCT_RECOMMENDED",
            actor="ai",
            summary=f"Applied simulation recommendation: {prod_obj.name}",
            data={
                "source": "decision_lab_simulation",
                "simulation_id": simulation_id,
                "decision_id": sim.decision_id,
                "goal": goal,
                "product_id": prod_obj.id,
                "product_name": prod_obj.name,
                "product_price": prod_obj.price,
                "category": prod_obj.category,
                "within_goal_budget": True,
                "within_contract_budget": True,
                "contract_note": None,
                "contract_active": contract is not None,
            },
        )

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="SIMULATION_APPLIED",
            actor="user",
            summary=f"Applied simulation: {sim.label}",
            data={
                "simulation_id": simulation_id,
                "decision_id": sim.decision_id,
                "product_id": prod_obj.id,
                "product_name": prod_obj.name,
                "product_price": prod_obj.price,
            },
        )

        if trace:
            trace.product_id = prod_obj.id
            db.commit()

        CartService.clear_cart(db, session_id)
        CartService.add_to_cart(db, session_id, prod_obj.id, 1)

        sim.status = "APPLIED"
        db.commit()

        return {
            "success": True,
            "simulation_id": simulation_id,
            "product": {
                "id": prod_obj.id,
                "name": prod_obj.name,
                "price": prod_obj.price,
                "currency": prod_obj.currency,
                "category": prod_obj.category,
                "attributes": prod_obj.attributes or {},
            },
            "message": (
                f"Applied: {prod_obj.name} at {_money(prod_obj.price)}. "
                f"This is now your active recommendation and has been added to your cart."
            ),
        }

    # ── List simulations for a trace ─────────────────────────────────
    @staticmethod
    def get_simulations(
        db: Session, decision_id: str
    ) -> List[Dict[str, Any]]:
        sims = (
            db.query(DecisionSimulation)
            .filter(DecisionSimulation.decision_id == decision_id)
            .order_by(DecisionSimulation.simulation_number)
            .all()
        )
        out = []
        for s in sims:
            out.append({
                "simulation_id": s.simulation_id,
                "simulation_number": s.simulation_number,
                "label": s.label,
                "status": s.status,
                "result_summary": {
                    "original_product": (s.result or {}).get("original_product"),
                    "simulated_product": (s.result or {}).get("simulated_product"),
                    "changes": (s.result or {}).get("changes", []),
                },
                "contract_warnings": s.contract_warnings or [],
                "created_at": s.created_at,
            })
        return out

    # ── Get a single simulation ──────────────────────────────────────
    @staticmethod
    def get_simulation(
        db: Session, simulation_id: str
    ) -> Optional[Dict[str, Any]]:
        sim = (
            db.query(DecisionSimulation)
            .filter(DecisionSimulation.simulation_id == simulation_id)
            .first()
        )
        if not sim:
            return None
        return {
            "simulation_id": sim.simulation_id,
            "decision_id": sim.decision_id,
            "session_id": sim.session_id,
            "simulation_number": sim.simulation_number,
            "label": sim.label,
            "original_constraints": sim.original_constraints,
            "modified_constraints": sim.modified_constraints,
            "result": sim.result,
            "contract_warnings": sim.contract_warnings or [],
            "status": sim.status,
            "created_at": sim.created_at,
        }


from services.decision_trace_service import DecisionTraceService
