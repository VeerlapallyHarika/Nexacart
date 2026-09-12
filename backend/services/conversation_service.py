from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from models.conversation import Conversation, ConversationMessage
from services.context_resolver import ContextResolver
import uuid
import json


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(self, session_id: str) -> Conversation:
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .first()
        )
        if not conversation:
            conversation = Conversation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                context_json=self._empty_context(),
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata,
        )
        self.db.add(message)
        self.db.commit()
        return message

    def get_recent_messages(
        self, conversation_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        messages.reverse()
        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

    def get_context(self, conversation_id: str) -> Dict[str, Any]:
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conversation and conversation.context_json:
            return conversation.context_json
        return self._empty_context()

    def update_context(self, conversation_id: str, updates: Dict[str, Any]) -> None:
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if not conversation:
            return
        current = conversation.context_json or self._empty_context()
        for key, value in updates.items():
            if key in current:
                current[key] = value
        conversation.context_json = current
        self.db.commit()

    def clear_conversation(self, session_id: str) -> bool:
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .first()
        )
        if not conversation:
            return False
        self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation.id
        ).delete()
        conversation.context_json = self._empty_context()
        self.db.commit()
        return True

    def build_context_string(self, conversation_id: str, cart_summary: Optional[str] = None) -> str:
        context = self.get_context(conversation_id)
        parts = []

        recent_ids = context.get("recent_product_ids", [])
        if recent_ids:
            names = context.get("product_names", {})
            displayed = [f"{names.get(pid, pid)} ({pid})" for pid in recent_ids[:5]]
            parts.append(f"Products from recent results: {', '.join(displayed)}")

        selected_id = context.get("selected_product_id")
        if selected_id:
            name = context.get("product_names", {}).get(selected_id, selected_id)
            parts.append(f"User's selected product: {name} ({selected_id})")

        compared_ids = context.get("compared_product_ids", [])
        if compared_ids:
            names = context.get("product_names", {})
            compared = [f"{names.get(pid, pid)} ({pid})" for pid in compared_ids]
            parts.append(f"Recently compared products: {', '.join(compared)}")

        search_query = context.get("last_search_query")
        if search_query:
            parts.append(f"Last search query: \"{search_query}\"")

        if cart_summary:
            parts.append(f"Current cart: {cart_summary}")

        if not parts:
            return "No prior context. This is the start of the conversation."

        return "Conversation context:\n" + "\n".join(parts)

    def update_context_from_products(
        self, conversation_id: str, products: List[Dict[str, Any]], search_query: Optional[str] = None
    ) -> None:
        updates: Dict[str, Any] = {}
        product_ids = [p["id"] for p in products]
        product_names = {p["id"]: p["name"] for p in products}

        if product_ids:
            updates["recent_product_ids"] = product_ids
            existing_names = self.get_context(conversation_id).get("product_names", {})
            existing_names.update(product_names)
            updates["product_names"] = existing_names

        if search_query:
            updates["last_search_query"] = search_query

        if updates:
            self.update_context(conversation_id, updates)

    def update_context_from_comparison(
        self, conversation_id: str, products: List[Dict[str, Any]]
    ) -> None:
        product_ids = [p["id"] for p in products]
        product_names = {p["id"]: p["name"] for p in products}

        context = self.get_context(conversation_id)
        existing_names = context.get("product_names", {})
        existing_names.update(product_names)

        self.update_context(conversation_id, {
            "compared_product_ids": product_ids,
            "product_names": existing_names,
        })

    def update_selected_product(self, conversation_id: str, product_id: str, product_name: str) -> None:
        context = self.get_context(conversation_id)
        existing_names = context.get("product_names", {})
        existing_names[product_id] = product_name
        self.update_context(conversation_id, {
            "selected_product_id": product_id,
            "product_names": existing_names,
        })

    def resolve_reference(self, conversation_id: str, message: str) -> Optional[str]:
        context = self.get_context(conversation_id)
        product_names = context.get("product_names", {})
        recent_ids = context.get("recent_product_ids", [])
        selected_id = context.get("selected_product_id")
        compared_ids = context.get("compared_product_ids", [])

        products_for_resolution = []
        target_ids = list(set(recent_ids + compared_ids))
        if selected_id and selected_id not in target_ids:
            target_ids.append(selected_id)

        for pid in target_ids:
            products_for_resolution.append({
                "id": pid,
                "name": product_names.get(pid, pid),
                "attributes": {},
            })

        if not products_for_resolution:
            return None

        resolver = ContextResolver(
            products_for_resolution,
            selected_product_id=selected_id,
        )
        return resolver.resolve(message)

    @staticmethod
    def _empty_context() -> Dict[str, Any]:
        return {
            "recent_product_ids": [],
            "selected_product_id": None,
            "compared_product_ids": [],
            "last_search_query": None,
            "product_names": {},
        }
