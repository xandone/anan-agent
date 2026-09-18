"""评论表：高赞评论既是分类语料，也是 Agent 的风格语料库。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = {"comment": "评论表：视频的高赞评论，用于分类参考和风格语料"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True,
                                            comment="抖音评论 ID")
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True,
                                          comment="所属视频（关联 videos.id）")

    text: Mapped[str] = mapped_column(Text, comment="评论内容")
    digg_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="点赞数")
    reply_to: Mapped[str | None] = mapped_column(String(64), comment="父评论 ID（楼中楼回复）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="采集时间")

    video: Mapped["Video"] = relationship(back_populates="comments")
