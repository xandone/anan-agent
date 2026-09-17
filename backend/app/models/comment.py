"""评论表：高赞评论既是分类语料，也是 Agent 的风格语料库。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)

    text: Mapped[str] = mapped_column(Text)
    digg_count: Mapped[int] = mapped_column(BigInteger, default=0)
    reply_to: Mapped[str | None] = mapped_column(String(64))  # 父评论 ID（楼中楼）

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    video: Mapped["Video"] = relationship(back_populates="comments")
