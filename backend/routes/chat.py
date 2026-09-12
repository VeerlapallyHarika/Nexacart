from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from schemas.chat import ChatRequest, ChatResponse, ProductResponse
from services.event_service import EventService
from services.intent_service import IntentService
from services.product_service import ProductService, SearchConstraint
from agents.cart_agent import CartAgent
from models.product import Product
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter()

agent = CartAgent()

# ── Deterministic intent helpers ──────────────────────────────────────────
# Phrases that unambiguously mean "show me my cart" — routed to the view_cart
# tool instead of falling through to a broad catalog search.
_VIEW_CART_QUERIES = re.compile(
    r"\b(view|show|see)(\s+me)?(\s+(my|the))?\s+cart\b"
    r"|\bwhat('s|\s+(is|are))\s+in\s+(my|the)?\s+cart\b"
    r"|\bmy\s+cart\b",
    re.IGNORECASE,
)

# Words that indicate a product-to-product comparison request.
_COMPARE_KEYWORDS = re.compile(r"\b(compare|comparing|comparison)\b", re.IGNORECASE)
_VS_SEPARATOR = re.compile(r"\b(vs|versus|v\.)\b", re.IGNORECASE)

# Filler words stripped out of a named product phrase before matching.
_FILLER_WORDS = {
    "a", "an", "the", "and", "or", "with", "for", "in", "of", "on", "to",
    "please", "product", "products", "between", "me", "show", "compare",
    "what", "is", "my", "cart", "i", "want", "buy", "bought",
}


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    session_id = request.session_id or EventService.generate_session_id()

    EventService.log_event(
        db=db,
        session_id=session_id,
        actor="user",
        event_type="USER_MESSAGE",
        summary="User sent message",
        data={"message": request.message}
    )

    message = request.message

    # Explicit, deterministic intent routing for user actions that must NOT fall
    # through to a broad catalog search:
    #   1. "view cart" / "show my cart" / "what's in my cart" → view_cart tool
    #   2. "compare X and Y" (2+ named products) → compare_products tool
    if _VIEW_CART_QUERIES.search(message):
        return _handle_view_cart(db, session_id)

    compare_response = _try_handle_compare(message, db, session_id)
    if compare_response is not None:
        return compare_response

    if agent.is_available:
        try:
            return _handle_with_agent(request, db, session_id)
        except Exception as e:
            logger.warning("AI agent failed, falling back to rule-based search: %s", e)

    return _handle_with_rules(request, db, session_id)


def _handle_view_cart(db: Session, session_id: str) -> ChatResponse:
    """Deterministically route an explicit 'view my cart' request to the
    view_cart tool and surface the actual cart contents."""
    result = agent._view_cart({}, db, session_id)

    if result.get("cart_empty"):
        EventService.log_event(
            db=db,
            session_id=session_id,
            event_type="AGENT_RESPONSE",
            actor="agent",
            summary="Responded: cart is empty",
            data={"message": result.get("message", "Your cart is empty")},
        )
        return ChatResponse(
            message=result.get("message", "Your cart is empty."),
            session_id=session_id,
            products=[],
        )

    items = result.get("items", [])
    lines = [f"{i['quantity']}x {i['product_name']} — ₹{i['subtotal']:,}" for i in items]
    message = (
        "Your cart:\n" + "\n".join(lines)
        + f"\n\nTotal: ₹{result['total']:,} ({result['item_count']} items)"
    )

    products = [
        ProductResponse(
            id=i["product_id"],
            name=i["product_name"],
            description=i.get("description") or "",
            price=i["price"],
            currency=i.get("currency", "INR"),
            category="",
            attributes=i.get("attributes", {}),
            stock_quantity=i.get("stock_quantity", 0),
        )
        for i in items
    ]

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="AGENT_RESPONSE",
        actor="agent",
        summary=f"Responded with cart contents ({result.get('item_count')} items)",
        data={"message": message, "products_count": len(products)},
    )

    return ChatResponse(message=message, session_id=session_id, products=products)


def _try_handle_compare(message: str, db: Session, session_id: str):
    """Detect a request to compare 2+ specifically-named products and route it
    to the compare_products tool. Returns a ChatResponse, or None if the message
    is not a resolvable multi-product comparison (caller should search instead)."""
    is_compare = bool(_COMPARE_KEYWORDS.search(message)) or bool(_VS_SEPARATOR.search(message))
    if not is_compare:
        return None

    phrases = _extract_named_products(message)
    if len(phrases) < 2:
        return None

    product_ids = _resolve_product_ids(db, phrases)
    if len(product_ids) < 2:
        return None

    result = agent._compare_products({"product_ids": product_ids}, db, session_id)
    if "error" in result:
        logger.warning("compare_products failed for %s: %s", message, result["error"])
        return None

    compared = result["products"]
    lines = [
        f"• {p['name']} — ₹{p['price']:,} ({p.get('category', '')})"
        for p in compared
    ]
    highlights = result.get("comparison_highlights", {})
    message_out = (
        "Here is a comparison:\n" + "\n".join(lines)
        + "\n\n" + (highlights.get("recommendation", "") or "")
    )

    products = [
        ProductResponse(
            id=p["id"],
            name=p["name"],
            description=p.get("description") or "",
            price=p["price"],
            currency=p.get("currency", "INR"),
            category=p.get("category", ""),
            attributes=p.get("attributes", {}),
            stock_quantity=p.get("stock_quantity", 0),
        )
        for p in compared
    ]

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="AGENT_RESPONSE",
        actor="agent",
        summary=f"Compared {len(compared)} products",
        data={"message": message_out, "products_count": len(products)},
    )

    return ChatResponse(message=message_out, session_id=session_id, products=products)


def _extract_named_products(message: str) -> List[str]:
    """Split a comparison message into the individual named product phrases."""
    text = _COMPARE_KEYWORDS.sub(" ", message)
    text = _VS_SEPARATOR.sub(",", text)

    segments = re.split(r",|\band\b|\bwith\b", text)
    phrases = []
    for seg in segments:
        phrase = re.sub(r"\s+", " ", seg).strip(" ,")
        phrase = re.sub(r"^\s*(the|product|products|a|an)\b", "", phrase).strip()
        if len(phrase) >= 2:
            phrases.append(phrase)
    return phrases


def _resolve_product_ids(db: Session, phrases: List[str]) -> List[str]:
    """Resolve each named product phrase to the best-matching catalog product id."""
    products = db.query(Product).all()
    ids = []
    for phrase in phrases:
        tokens = set(re.findall(r"[a-z0-9]+", phrase.lower())) - _FILLER_WORDS
        if not tokens:
            continue
        best_id = None
        best_score = 0
        for p in products:
            name_tokens = set(re.findall(r"[a-z0-9]+", (p.name or "").lower()))
            score = len(tokens & name_tokens)
            if score > best_score:
                best_score = score
                best_id = p.id
        if best_id is not None and best_score > 0:
            ids.append(best_id)
    return ids


def _handle_with_agent(
    request: ChatRequest,
    db: Session,
    session_id: str
) -> ChatResponse:
    conversation_history = []

    agent_result = agent.handle_message(
        user_message=request.message,
        conversation_history=conversation_history,
        db=db,
        session_id=session_id
    )

    response_message = agent_result["message"]
    products = []

    for tool_use in agent_result.get("tools_used", []):
        if tool_use["tool"] == "search_products" and "products" in tool_use["output"]:
            for p in tool_use["output"]["products"]:
                products.append(ProductResponse(
                    id=p["id"],
                    name=p["name"],
                    description=p.get("description", ""),
                    price=p["price"],
                    currency=p.get("currency", "INR"),
                    category=p.get("category", ""),
                    attributes=p.get("attributes", {}),
                    stock_quantity=p.get("stock_quantity", 0)
                ))

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="AGENT_RESPONSE",
        actor="agent",
        summary="CartAgent returned response",
        data={
            "message": response_message,
            "products_count": len(products),
            "tools_used": [t["tool"] for t in agent_result.get("tools_used", [])]
        }
    )

    return ChatResponse(
        message=response_message,
        session_id=session_id,
        products=products
    )


def _handle_with_rules(
    request: ChatRequest,
    db: Session,
    session_id: str
) -> ChatResponse:
    intent = IntentService.extract_intent(request.message, db=db)

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="INTENT_EXTRACTED",
        actor="agent",
        summary="Extracted product preferences",
        data={
            "category": intent.get("category"),
            "max_price": intent.get("max_price"),
            "brand": intent.get("brand"),
            "constraints_count": len(intent.get("constraints", [])),
        }
    )

    # Build constraint list from extracted intent
    constraints = intent.get("constraints", [])

    search_result = ProductService.generic_search(
        db=db,
        category=intent.get("category"),
        max_price=intent.get("max_price"),
        min_price=intent.get("min_price"),
        brand=intent.get("brand"),
        constraints=constraints,
        limit=5,
    )

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="CATALOG_SEARCHED",
        actor="agent",
        summary=f"Searched catalog and found {len(search_result.products)} matching products",
        data={
            "category": intent.get("category"),
            "max_price": intent.get("max_price"),
            "match_type": search_result.match_type,
            "results_count": len(search_result.products),
            "matched_constraints": search_result.matched_constraints,
            "unmatched_constraints": search_result.unmatched_constraints,
        }
    )

    product_responses = [
        ProductResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            price=p.price,
            currency=p.currency,
            category=p.category,
            attributes=p.attributes or {},
            stock_quantity=p.stock_quantity,
        )
        for p in search_result.products
    ]

    response_message = search_result.explanation

    EventService.log_event(
        db=db,
        session_id=session_id,
        event_type="AGENT_RESPONSE",
        actor="agent",
        summary="Responded with product recommendations",
        data={
            "message": response_message,
            "products_count": len(product_responses),
            "match_type": search_result.match_type,
        }
    )

    return ChatResponse(
        message=response_message,
        session_id=session_id,
        products=product_responses
    )
