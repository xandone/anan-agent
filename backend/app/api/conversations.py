"""历史会话路由：列表 / 详情 / 删除。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Conversation

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    convs = (db.query(Conversation)
             .order_by(Conversation.updated_at.desc())
             .limit(100).all())
    return [{
        "id": c.id, "title": c.title, "category_slug": c.category_slug,
        "updated_at": c.updated_at.isoformat(),
        "message_count": len(c.messages),
    } for c in convs]


@router.get("/{conv_id}")
def conversation_detail(conv_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversation, conv_id)
    if not c:
        raise HTTPException(404)
    return {
        "id": c.id, "title": c.title, "category_slug": c.category_slug,
        "messages": [{
            "id": m.id, "role": m.role, "content": m.content,
            "context_count": m.context_count,
            "prompt_tokens": m.prompt_tokens,
            "completion_tokens": m.completion_tokens,
            "duration_ms": m.duration_ms,
        } for m in c.messages],
    }


@router.delete("/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversation, conv_id)
    if not c:
        raise HTTPException(404)
    db.delete(c)
    db.commit()
    return {"ok": True}
