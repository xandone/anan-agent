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
    __table_args__ = {"comment": "类别表：内容分类，每个类别对应一个 AI 智能体人格"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), unique=True,
                                      comment="类别名称，如：诗歌类、阴阳怪气类、科普类")
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True,
                                      comment="类别标识（对话路由、API 引用用）")
    description: Mapped[str | None] = mapped_column(Text,
                                                    comment="类别定义（供 LLM 打标时判断）")
    system_prompt: Mapped[str | None] = mapped_column(Text,
                                                      comment="智能体人格 Prompt（system prompt）")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="创建时间")


class Corpus(Base):
    """语料向量表：视频文本和高赞评论切片，按类别隔离检索。"""
    __tablename__ = "corpus"
    __table_args__ = {"comment": "语料向量表：按类别隔离的 RAG 检索语料"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), index=True,
                                                 comment="来源视频（关联 videos.id）")
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"), index=True,
                                                   comment="来源评论（关联 comments.id，视频语料为 NULL）")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True,
                                             comment="所属类别（检索时按此隔离）")

    content: Mapped[str] = mapped_column(Text, comment="语料文本")
    content_type: Mapped[str] = mapped_column(String(16), default="video",
                                              comment="语料类型：video视频文本/comment评论")
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_dim), comment=f"文本向量（{_dim} 维，BGE-M3）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="入库时间")
