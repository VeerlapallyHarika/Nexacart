import openai
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from agents.tools import TOOL_DEFINITIONS
from services.product_service import ProductService, SearchConstraint
from services.cart_service import CartService
from services.checkout_service import CheckoutService
from services.payment_service import PaymentService
from services.order_service import OrderService
from services.event_service import EventService
from services.conversation_service import ConversationService
from services.contract_validator import ContractValidator
from services.contract_constants import ACTION_SEARCH, ACTION_ADD_TO_CART, ACTION_PAYMENT
import os

SYSTEM_PROMPT = """You are NexaCart's AI shopping assistant. You help users find products, compare them, manage their shopping cart, and complete payments.

Your capabilities:
1. Search the product catalog based on user preferences
2. Get detailed product information
3. Compare multiple products side by side
4. Add products to the shopping cart
5. View the cart contents
6. Remove items from the cart
7. Verify cart items for checkout (price and inventory check)
8. Request checkout approval before payment
9. Initiate payment for approved carts
10. Check payment status
11. Get order details

Guidelines:
- Understand what the user wants and extract their preferences
- Use tools to retrieve real product data from the database
- Present products clearly with key details (name, price, battery life, features)
- Help users make decisions by comparing products
- When adding to cart, confirm the product and quantity
- Always verify cart before requesting checkout approval
- Never approve payment without explicit user confirmation
- Initiate payment only when the user explicitly asks to pay
- Be concise and helpful
- Always use real data from the database
- Never invent product information, prices, or specifications
- If you don't have enough information, ask the user or use tools to find out

Important:
- Always use tools to get product information
- Never make up product details
- Keep responses focused and helpful
- Always verify prices and inventory before checkout
- Never silently approve payment - always ask the user first
- Payment must be explicitly confirmed by the user"""


class CartAgent:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = openai.OpenAI(api_key=api_key)
            else:
                raise ValueError("OPENAI_API_KEY not set")
        return self._client

    @property
    def model(self):
        return os.getenv("OPENAI_MODEL", "gpt-4")

    @property
    def is_available(self):
        return os.getenv("OPENAI_API_KEY") is not None

    def handle_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="AGENT_STARTED",
            actor="agent",
            summary="CartAgent started processing user request",
            data={"message": user_message}
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        all_tool_results = []

        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            if assistant_message.tool_calls:
                messages.append(assistant_message)

                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    EventService.log_event(
                        db=db,
                        session_id=session_id,
                        event_type="TOOL_SELECTED",
                        actor="agent",
                        summary=f"CartAgent selected {function_name} tool",
                        data={"tool": function_name, "args": function_args}
                    )

                    tool_result = self._execute_tool(
                        function_name, function_args, db, session_id
                    )
                    all_tool_results.append({
                        "tool": function_name,
                        "input": function_args,
                        "output": tool_result
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })
            else:
                return {
                    "message": assistant_message.content,
                    "tools_used": all_tool_results
                }

    def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        if tool_name == "search_products":
            return self._search_products(args, db, session_id)
        elif tool_name == "get_product_details":
            return self._get_product_details(args, db, session_id)
        elif tool_name == "compare_products":
            return self._compare_products(args, db, session_id)
        elif tool_name == "add_to_cart":
            return self._add_to_cart(args, db, session_id)
        elif tool_name == "view_cart":
            return self._view_cart(args, db, session_id)
        elif tool_name == "remove_from_cart":
            return self._remove_from_cart(args, db, session_id)
        elif tool_name == "verify_cart":
            return self._verify_cart(args, db, session_id)
        elif tool_name == "request_checkout_approval":
            return self._request_checkout_approval(args, db, session_id)
        elif tool_name == "initiate_payment":
            return self._initiate_payment(args, db, session_id)
        elif tool_name == "get_payment_status":
            return self._get_payment_status(args, db, session_id)
        elif tool_name == "get_order_details":
            return self._get_order_details(args, db, session_id)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _search_products(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        # Validate the proposed search filters against the active contract.
        contract_check = ContractValidator.check_action(
            db=db,
            session_id=session_id,
            action=ACTION_SEARCH,
            max_price=args.get("max_price"),
            category=args.get("category"),
        )
        if not contract_check.get("allowed"):
            return ContractValidator._to_blocked_payload(
                "search_products", contract_check
            )

        # Build generic constraints from the tool call arguments
        constraints = []
        raw_attrs = args.get("attributes", {})
        for attr_key, attr_value in raw_attrs.items():
            if isinstance(attr_value, bool):
                constraints.append(
                    SearchConstraint(attr_key, attr_value, "eq", f"{attr_key}={attr_value}")
                )
            elif isinstance(attr_value, (int, float)):
                constraints.append(
                    SearchConstraint(attr_key, attr_value, "gte", f"{attr_key}>={attr_value}")
                )
            elif isinstance(attr_value, str):
                constraints.append(
                    SearchConstraint(attr_key, attr_value, "contains", f"{attr_key} contains {attr_value}")
                )

        # Apply contract defaults if no category specified
        effective_category = args.get("category")
        effective_max_price = args.get("max_price")
        active = ContractValidator.get_active_contract(db, session_id)
        if active:
            cats = active.required_categories or []
            if effective_category is None and cats:
                effective_category = cats[0]
            if effective_max_price is None and active.max_budget is not None:
                effective_max_price = active.max_budget

        # Use the generic search
        search_result = ProductService.generic_search(
            db=db,
            category=effective_category,
            max_price=effective_max_price,
            min_price=args.get("min_price"),
            brand=args.get("brand"),
            constraints=constraints,
            query=args.get("query"),
            limit=5,
        )

        # Enforce the contract on each returned product
        allowed_products = [
            p for p in search_result.products
            if ContractValidator.check_product(db, session_id, p, ACTION_ADD_TO_CART).get("allowed")
        ]

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Product search completed - found {len(allowed_products)} matching products",
            data={
                "tool": "search_products",
                "filters": {
                    "category": effective_category,
                    "max_price": effective_max_price,
                    "brand": args.get("brand"),
                    "query": args.get("query"),
                },
                "result_count": len(allowed_products),
                "product_ids": [p.id for p in allowed_products],
                "match_type": search_result.match_type,
            }
        )

        return {
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": p.price,
                    "currency": p.currency,
                    "category": p.category,
                    "attributes": p.attributes or {},
                    "stock_quantity": p.stock_quantity
                }
                for p in allowed_products
            ],
            "match_type": search_result.match_type,
            "explanation": search_result.explanation,
        }

    def _get_product_details(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        product = ProductService.get_product(db, args["product_id"])
        if not product:
            return {"error": "Product not found"}

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Retrieved details for {product.name}",
            data={
                "tool": "get_product_details",
                "product_id": product.id,
                "product_name": product.name
            }
        )

        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "currency": product.currency,
            "category": product.category,
            "attributes": product.attributes or {},
            "stock_quantity": product.stock_quantity
        }

    def _compare_products(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        product_ids = args.get("product_ids", [])
        if len(product_ids) < 2:
            return {"error": "At least 2 product IDs are required for comparison"}

        products = []
        for pid in product_ids:
            product = ProductService.get_product(db, pid)
            if product:
                products.append(product)

        if len(products) < 2:
            return {"error": "Could not find enough products for comparison"}

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Compared {len(products)} products: {', '.join(p.name for p in products)}",
            data={
                "tool": "compare_products",
                "product_ids": [p.id for p in products],
                "product_names": [p.name for p in products]
            }
        )

        comparison = {
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": p.price,
                    "currency": p.currency,
                    "category": p.category,
                    "attributes": p.attributes or {},
                    "stock_quantity": p.stock_quantity
                }
                for p in products
            ],
            "comparison_highlights": self._generate_comparison_highlights(products)
        }

        return comparison

    def _generate_comparison_highlights(self, products: list) -> Dict[str, Any]:
        highlights = {
            "price_comparison": [],
            "features": [],
            "recommendation": ""
        }

        for p in products:
            highlights["price_comparison"].append({
                "product_id": p.id,
                "name": p.name,
                "price": p.price
            })

        all_attrs = set()
        for p in products:
            if p.attributes:
                all_attrs.update(p.attributes.keys())

        for attr in all_attrs:
            values = []
            for p in products:
                val = (p.attributes or {}).get(attr)
                if val is not None:
                    values.append({
                        "product_id": p.id,
                        "name": p.name,
                        "value": val
                    })
            if values:
                highlights["features"].append({
                    "feature": attr,
                    "values": values
                })

        cheapest = min(products, key=lambda p: p.price)
        highlights["recommendation"] = f"Best value: {cheapest.name} at ₹{cheapest.price}"

        return highlights

    def _add_to_cart(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        product_id = args.get("product_id")
        quantity = args.get("quantity", 1)

        product = ProductService.get_product(db, product_id)
        if not product:
            return {"error": "Product not found"}

        # Contract enforcement: the actual product must satisfy the contract.
        contract_check = ContractValidator.check_product(
            db, session_id, product, ACTION_ADD_TO_CART
        )
        if not contract_check.get("allowed"):
            EventService.log_event(
                db=db,
                session_id=session_id,
                event_type="CONTRACT_VIOLATION",
                actor="agent",
                summary=f"Blocked adding {product.name} - violates contract",
                data={
                    "tool": "add_to_cart",
                    "product_id": product_id,
                    "violations": contract_check["violations"],
                },
            )
            return ContractValidator._to_blocked_payload("add_to_cart", contract_check)

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Adding {product.name} to cart",
            data={
                "tool": "add_to_cart",
                "product_id": product_id,
                "product_name": product.name,
                "quantity": quantity,
                "price": product.price
            }
        )

        result = CartService.add_to_cart(db, session_id, product_id, quantity)

        if "error" in result:
            return result

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="PRODUCT_ADDED_TO_CART",
            actor="agent",
            summary=f"Successfully added {product.name} to cart",
            data={
                "product_id": product_id,
                "product_name": product.name,
                "quantity": quantity,
                "price": product.price,
                "cart_total": result.get("cart_total"),
                "cart_item_count": result.get("cart_item_count")
            }
        )

        return {
            "success": True,
            "message": f"Added {quantity}x {product.name} to your cart",
            "product": {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "currency": product.currency
            },
            "quantity": quantity,
            "cart_total": result.get("cart_total"),
            "cart_item_count": result.get("cart_item_count")
        }

    def _view_cart(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary="Viewing cart contents",
            data={"tool": "view_cart"}
        )

        cart = CartService.get_cart_details(db, session_id)

        if not cart:
            return {
                "cart_empty": True,
                "message": "Your cart is empty"
            }

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="CART_VIEWED",
            actor="agent",
            summary=f"Cart has {cart['item_count']} items, total: ₹{cart['total']}",
            data={
                "item_count": cart["item_count"],
                "total": cart["total"],
                "status": cart["status"]
            }
        )

        return {
            "cart_empty": cart["item_count"] == 0,
            "cart_id": cart["cart_id"],
            "status": cart["status"],
            "items": cart["items"],
            "total": cart["total"],
            "item_count": cart["item_count"],
            "currency": "INR"
        }

    def _remove_from_cart(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        item_id = args.get("item_id")

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Removing item {item_id} from cart",
            data={"tool": "remove_from_cart", "item_id": item_id}
        )

        result = CartService.remove_cart_item(db, session_id, item_id)

        if "error" in result:
            return result

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="CART_ITEM_REMOVED",
            actor="agent",
            summary="Item removed from cart",
            data={"item_id": item_id}
        )

        return {
            "success": True,
            "message": "Item removed from your cart"
        }

    def _verify_cart(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary="Verifying cart for checkout",
            data={"tool": "verify_cart"}
        )

        verification = CheckoutService.verify_cart(db, session_id)

        if "error" in verification:
            return verification

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="CART_VERIFIED" if verification.get("verified") else "CART_VERIFICATION_FAILED",
            actor="agent",
            summary=f"Cart verification {'passed' if verification.get('verified') else 'failed'}",
            data={
                "verified": verification.get("verified"),
                "total": verification.get("total"),
                "item_count": verification.get("item_count")
            }
        )

        return verification

    def _request_checkout_approval(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary="Requesting checkout approval",
            data={"tool": "request_checkout_approval"}
        )

        result = CheckoutService.request_approval(db, session_id)

        if "error" in result:
            return result

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="CHECKOUT_APPROVAL_REQUESTED",
            actor="agent",
            summary="Checkout approval requested from user",
            data={"status": "AWAITING_APPROVAL"}
        )

        return {
            "success": True,
            "status": "AWAITING_APPROVAL",
            "message": "Your cart is ready for checkout. Please review the order summary and confirm to proceed to payment.",
            "verification": result.get("verification")
        }

    def _initiate_payment(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        # The AI is never allowed to charge the user directly. Payment must be
        # initiated only after explicit human approval through the UI flow.
        contract_check = ContractValidator.check_action(
            db=db, session_id=session_id, action=ACTION_PAYMENT
        )
        if not contract_check.get("allowed"):
            return ContractValidator._to_blocked_payload(
                "initiate_payment", contract_check
            )

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary="Initiating payment for approved cart",
            data={"tool": "initiate_payment"}
        )

        result = PaymentService.create_payment_intent(db, session_id)

        if "error" in result:
            return result

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="PAYMENT_INITIATED",
            actor="agent",
            summary=f"Payment initiated: {result['payment_id']} for ₹{result['amount']}",
            data={
                "payment_id": result["payment_id"],
                "amount": result["amount"],
                "currency": result["currency"]
            }
        )

        return {
            "success": True,
            "payment_id": result["payment_id"],
            "amount": result["amount"],
            "currency": result["currency"],
            "status": result["status"],
            "message": f"Payment initiated for ₹{result['amount']}. Please confirm to complete the payment."
        }

    def _get_payment_status(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        payment_id = args.get("payment_id")

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Checking payment status for {payment_id}",
            data={"tool": "get_payment_status", "payment_id": payment_id}
        )

        payment = PaymentService.get_payment(db, payment_id)

        if not payment:
            return {"error": "Payment not found"}

        return {
            "payment_id": payment["payment_id"],
            "amount": payment["amount"],
            "currency": payment["currency"],
            "status": payment["status"],
            "payment_method": payment["payment_method"],
            "created_at": payment["created_at"]
        }

    def _get_order_details(
        self,
        args: Dict[str, Any],
        db: Session,
        session_id: str
    ) -> Dict[str, Any]:
        order_id = args.get("order_id")

        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="TOOL_EXECUTED",
            actor="agent",
            summary=f"Getting order details for {order_id}",
            data={"tool": "get_order_details", "order_id": order_id}
        )

        order = OrderService.get_order(db, order_id)

        if not order:
            return {"error": "Order not found"}

        return {
            "order_id": order["order_id"],
            "total_amount": order["total_amount"],
            "currency": order["currency"],
            "status": order["status"],
            "payment_status": order["payment_status"],
            "items": order["items"],
            "created_at": order["created_at"]
        }
