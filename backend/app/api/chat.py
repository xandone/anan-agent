"""Agent 对话路由：非流式 + SSE 流式（多轮、带统计）。"""
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.graph import (build_messages, chat_with_category, get_category,
                              retrieve_contexts)
from app.clients import llm
from app.core.database import SessionLocal, get_db
from app.models import ChatMessage, Conversation

router = APIRouter(prefix="/api/chat", tags=["chat"])

HISTORY_LIMIT = 20  # 带入上下文的历史轮数上限


class ChatReq(BaseModel):
    category_slug: str
    question: str


@router.post("")
def chat(req: ChatReq, db: Session = Depends(get_db)):
    """非流式接口（保留，供简单调用/测试用）。"""
    return chat_with_category(db, req.category_slug, req.question)


class ChatStreamReq(BaseModel):
    category_slug: str
    question: str
    conversation_id: int | None = None  # 为空则新建会话


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
def chat_stream(req: ChatStreamReq, db: Session = Depends(get_db)):
    """SSE 流式对话。事件类型：meta / delta / done / error。"""
    category = get_category(db, req.category_slug)
    if not category:
        raise HTTPException(404, "该类别不存在或未启用")

    # 会话：续聊或新建（标题取首问前 30 字）
    if req.conversation_id:
        conv = db.get(Conversation, req.conversation_id)
        if not conv:
            raise HTTPException(404, "会话不存在")
    else:
        conv = Conversation(category_slug=req.category_slug,
                            title=req.question[:30])
        db.add(conv)
        db.commit()

    conv_id = conv.id
    history = (db.query(ChatMessage)
               .filter_by(conversation_id=conv_id)
               .order_by(ChatMessage.id.desc())
               .limit(HISTORY_LIMIT).all())[::-1]
    db.add(ChatMessage(conversation_id=conv_id, role="user", content=req.question))
    db.commit()

    contexts = retrieve_contexts(db, category["id"], req.question)
    messages = build_messages(category, contexts, history, req.question)
    context_count = len(contexts)

    def event_stream():
        t0 = time.perf_counter()
        full_text = ""
        usage = None
        yield _sse({"type": "meta", "conversation_id": conv_id,
                    "context_count": context_count})
        try:
            for kind, payload in llm.chat_stream(messages):
                if kind == "delta":
                    full_text += payload
                    yield _sse({"type": "delta", "text": payload})
                else:
                    usage = payload
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
            return
        duration_ms = int((time.perf_counter() - t0) * 1000)

        # 落库（请求级 session 此时已不可靠，开新会话）
        sdb = SessionLocal()
        try:
            msg = ChatMessage(
                conversation_id=conv_id, role="assistant", content=full_text,
                context_count=context_count, duration_ms=duration_ms,
                prompt_tokens=(usage or {}).get("prompt_tokens"),
                completion_tokens=(usage or {}).get("completion_tokens"),
            )
            sdb.add(msg)
            conv2 = sdb.get(Conversation, conv_id)
            conv2.updated_at = datetime.utcnow()
            sdb.commit()
            msg_id = msg.id
        finally:
            sdb.close()

        yield _sse({"type": "done", "message_id": msg_id,
                    "duration_ms": duration_ms, "usage": usage})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
