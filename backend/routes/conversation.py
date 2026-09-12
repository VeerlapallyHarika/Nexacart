from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


@router.get("/{session_id}")
def get_conversation_history(session_id: str, db: Session = Depends(get_db)):
    service = ConversationService(db)
    conversation = service.get_or_create_conversation(session_id)
    messages = service.get_recent_messages(conversation.id, limit=50)
    context = service.get_context(conversation.id)
    return {
        "session_id": session_id,
        "conversation_id": conversation.id,
        "messages": messages,
        "context": context,
    }


@router.delete("/{session_id}")
def clear_conversation(session_id: str, db: Session = Depends(get_db)):
    service = ConversationService(db)
    cleared = service.clear_conversation(session_id)
    return {"success": cleared, "session_id": session_id}
