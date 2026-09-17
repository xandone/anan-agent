"""视频主表：贯穿整条流水线的状态机载体。"""
import enum
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VideoStatus(str, enum.Enum):
    PENDING = "pending"          # 已登记，待下载
    DOWNLOADED = "downloaded"    # 已下载
    OCR_DONE = "ocr_done"        # 画面文字已提取
    ASR_DONE = "asr_done"        # 语音已转写
    CLASSIFIED = "classified"    # 已分类
    INDEXED = "indexed"          # 已入向量库
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aweme_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 抖音作品 ID
    url: Mapped[str | None] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(Text)          # 视频文案/标题
    hashtags: Mapped[list | None] = mapped_column(JSON)      # 话题标签
    author_id: Mapped[str | None] = mapped_column(String(64), index=True)
    author_name: Mapped[str | None] = mapped_column(String(128))

    digg_count: Mapped[int] = mapped_column(BigInteger, default=0)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0)
    share_count: Mapped[int] = mapped_column(BigInteger, default=0)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime)

    # 来源任务：hot（热榜）/ account（达人）/ search（关键词）/ manual
    source: Mapped[str] = mapped_column(String(32), default="manual")

    local_path: Mapped[str | None] = mapped_column(String(512))   # 视频文件路径
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.PENDING, index=True)
    error: Mapped[str | None] = mapped_column(Text)

    # 提取结果
    ocr_text: Mapped[str | None] = mapped_column(Text)
    asr_text: Mapped[str | None] = mapped_column(Text)

    # 分类结果
    category_id: Mapped[int | None] = mapped_column(Integer, index=True)
    classify_confidence: Mapped[float | None] = mapped_column(Float)
    classify_source: Mapped[str | None] = mapped_column(String(16))  # llm / human

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    comments: Mapped[list["Comment"]] = relationship(back_populates="video", cascade="all, delete-orphan")

    @property
    def full_text(self) -> str:
        """拼接用于分类和入库的完整文本。"""
        parts = [self.title or "", " ".join(self.hashtags or []),
                 self.ocr_text or "", self.asr_text or ""]
        return "\n".join(p for p in parts if p)
