"""Agent 对话路由：非流式 + SSE 流式（多轮、带统计）。"""
import asyncio
import json
import threading
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

    async def event_stream():
        """异步生成器：上游 LLM 流在后台线程读取，经队列转发。

        客户端断开（用户点停止）时，await 处立刻收到 CancelledError，
        finally 里通知上游线程停止并把已生成的部分内容落库。
        """
        t0 = time.perf_counter()
        full_text = ""
        usage = None
        normal_end = False
        saved_msg_id: int | None = None

        def save_answer():
            """把（可能只生成了一半的）回答落库，幂等 + 防重复。

            防重复：客户端断开未必能被服务端感知（上游会继续读完），
            前端停止时也会调 /save 兜底；若会话最后一条已是助手消息则跳过。
            """
            nonlocal saved_msg_id
            if saved_msg_id is not None or not full_text.strip():
                return
            sdb = SessionLocal()
            try:
                last = (sdb.query(ChatMessage)
                        .filter_by(conversation_id=conv_id)
                        .order_by(ChatMessage.id.desc()).first())
                if last and last.role == "assistant":
                    saved_msg_id = last.id
                    return
                msg = ChatMessage(
                    conversation_id=conv_id, role="assistant", content=full_text,
                    context_count=context_count,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    prompt_tokens=(usage or {}).get("prompt_tokens"),
                    completion_tokens=(usage or {}).get("completion_tokens"),
                )
                sdb.add(msg)
                conv2 = sdb.get(Conversation, conv_id)
                conv2.updated_at = datetime.utcnow()
                sdb.commit()
                saved_msg_id = msg.id
            finally:
                sdb.close()

        # 后台线程读上游 LLM 流，经 asyncio 队列转发给协程
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop_flag = threading.Event()

        def upstream_worker():
            try:
                for chunk in llm.create_stream(messages):
                    if stop_flag.is_set():
                        break
                    item = llm.parse_chunk(chunk)
                    if item:
                        loop.call_soon_threadsafe(queue.put_nowait, item)
                loop.call_soon_threadsafe(queue.put_nowait, ("end", None))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("err", str(e)))

        try:
            threading.Thread(target=upstream_worker, daemon=True).start()
            yield _sse({"type": "meta", "conversation_id": conv_id,
                        "context_count": context_count})
            while True:
                kind, payload = await queue.get()
                if kind == "end":
                    normal_end = True
                    break
                if kind == "err":
                    raise RuntimeError(payload)
                if kind == "delta":
                    full_text += payload
                    yield _sse({"type": "delta", "text": payload})
                elif kind == "reasoning":
                    # 思考过程：只转发给前端展示，不入库不进正文
                    yield _sse({"type": "reasoning", "text": payload})
                elif kind == "usage":
                    usage = payload
        except (asyncio.CancelledError, GeneratorExit):
            # 客户端断开（用户点了停止）：走 finally 保存半成品
            raise
        except Exception as e:
            try:
                yield _sse({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            stop_flag.set()   # 让上游线程尽快停止，避免白烧 token
            save_answer()     # 正常结束、出错、被停止都会保存已生成内容

        if normal_end:
            yield _sse({"type": "done", "message_id": saved_msg_id,
                        "duration_ms": int((time.perf_counter() - t0) * 1000),
                        "usage": usage})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class SavePartialReq(BaseModel):
    conversation_id: int
    content: str
    duration_ms: int | None = None


@router.post("/save")
def save_partial(req: SavePartialReq, db: Session = Depends(get_db)):
    """前端在「停止生成」时兜底保存半成品回答。

    （服务端未必能及时感知客户端断开，此接口是可靠落库的主路径。）
    """
    conv = db.get(Conversation, req.conversation_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    if not req.content.strip():
        return {"ok": True, "skipped": True}
    last = (db.query(ChatMessage)
            .filter_by(conversation_id=conv.id)
            .order_by(ChatMessage.id.desc()).first())
    if last and last.role == "assistant":
        return {"ok": True, "skipped": True}  # 服务端已保存
    msg = ChatMessage(conversation_id=conv.id, role="assistant",
                      content=req.content, duration_ms=req.duration_ms)
    db.add(msg)
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message_id": msg.id}
