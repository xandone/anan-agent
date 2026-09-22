"""视频主表：贯穿整条流水线的状态机载体。"""
import enum
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VideoStatus(str, enum.Enum):
    PENDING = "pending"          # 已登记，待下载
    DOWNLOADED = "downloaded"    # 已下载
    OCR_DONE = "ocr_done"        # 画面文字已提取（历史遗留状态，当前 OCR 为手动兜底）
    ASR_DONE = "asr_done"        # 语音已转写
    CLASSIFIED = "classified"    # 已分类
    INDEXED = "indexed"          # 已入向量库
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {"comment": "视频主表：采集到的抖音视频，承载流水线状态机"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键")
    aweme_id: Mapped[str] = mapped_column(String(64), unique=True, index=True,
                                          comment="抖音作品 ID")
    url: Mapped[str | None] = mapped_column(String(512), comment="作品链接")
    title: Mapped[str | None] = mapped_column(Text, comment="视频标题/文案")
    hashtags: Mapped[list | None] = mapped_column(JSON, comment="话题标签（JSON 数组）")
    author_id: Mapped[str | None] = mapped_column(String(64), index=True,
                                                  comment="作者 ID（sec_uid）")
    author_name: Mapped[str | None] = mapped_column(String(128), comment="作者昵称")

    digg_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="点赞数")
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="评论数")
    share_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="分享数")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, comment="发布时间")

    # 来源任务：hot（热榜）/ account（达人）/ like（用户点赞）/ search（关键词）/ manual（手动）
    source: Mapped[str] = mapped_column(String(32), default="manual",
                                        comment="采集来源：hot热榜/account达人/like用户点赞/search搜索/manual手动")

    local_path: Mapped[str | None] = mapped_column(String(512), comment="本地视频文件路径")
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), default=VideoStatus.PENDING, index=True,
        comment="流水线状态：pending/downloaded/asr_done/classified/indexed/failed")
    error: Mapped[str | None] = mapped_column(Text, comment="失败原因（含失败步骤前缀）")

    # 提取结果
    ocr_text: Mapped[str | None] = mapped_column(Text, comment="OCR 提取的画面文字（手动兜底）")
    asr_text: Mapped[str | None] = mapped_column(Text, comment="ASR 语音转写文本（字幕主来源）")

    # 分类结果
    category_id: Mapped[int | None] = mapped_column(Integer, index=True,
                                                    comment="分类 ID（关联 categories.id，NULL=未分类）")
    classify_confidence: Mapped[float | None] = mapped_column(Float, comment="分类置信度 0~1")
    classify_source: Mapped[str | None] = mapped_column(String(16),
                                                        comment="分类来源：llm自动/human人工")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow, comment="更新时间")

    comments: Mapped[list["Comment"]] = relationship(back_populates="video",
                                                     cascade="all, delete-orphan")

    @property
    def full_text(self) -> str:
        """拼接用于分类和入库的完整文本。"""
        parts = [self.title or "", " ".join(self.hashtags or []),
                 self.ocr_text or "", self.asr_text or ""]
        return "\n".join(p for p in parts if p)
