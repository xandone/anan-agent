"""类别表 + 语料向量表。

类别是一等公民实体：支持演进（新增/合并/拆分），每个类别对应一个 Agent。
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.database import Base

_dim = get_settings().embedding_dim


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)       # 如：诗歌类、阴阳怪气类、科普类
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)            # 给 LLM 打标用的类别定义
    system_prompt: Mapped[str | None] = mapped_column(Text)          # Agent 风格 Prompt
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Corpus(Base):
    """语料向量表：视频文本和高赞评论切片，按类别隔离检索。"""
    __tablename__ = "corpus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), index=True)
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)

    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(16), default="video")  # video / comment
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_dim))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
