"""对话会话与消息：支持多轮对话和历史记录。"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"comment": "对话会话表：用户与某智能体的一轮完整对话"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    category_slug: Mapped[str] = mapped_column(String(64), index=True,
                                               comment="对话的智能体 slug（关联 categories.slug）")
    title: Mapped[str] = mapped_column(String(120), comment="会话标题（取首个问题前 30 字）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow,
                                                 comment="最后活跃时间（历史列表按此排序）")

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="ChatMessage.id")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"comment": "对话消息表：用户提问和助手回答（含生成统计）"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True,
                                                 comment="所属会话（关联 conversations.id）")

    role: Mapped[str] = mapped_column(String(16), comment="角色：user用户/assistant助手")
    content: Mapped[str] = mapped_column(Text, comment="消息内容（助手为 Markdown）")

    # 助手消息的统计信息
    context_count: Mapped[int | None] = mapped_column(Integer, comment="RAG 检索到的语料条数")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, comment="输入 token 数")
    completion_tokens: Mapped[int | None] = mapped_column(Integer, comment="输出 token 数")
    duration_ms: Mapped[int | None] = mapped_column(Integer, comment="生成耗时（毫秒）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="发送时间")

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
