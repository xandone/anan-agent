"""流水线编排：状态机驱动，每步独立可重试。

pending -> downloaded -> asr_done -> classified -> indexed
OCR 不在自动流程里：字幕统一走 ASR，ASR 失败（无语音/识别失败）的
视频进入 failed，由用户在视频库手动触发 OCR 兜底（单条或批量）。
任何一步失败置为 failed 并记录 error，可单独重跑。
"""
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from app.clients import asr, douyin, ocr
from app.core.config import get_settings
from app.models import Comment, Video, VideoStatus
from app.pipeline.classifier import classify_video
from app.pipeline.indexer import index_video


def register_video(db: Session, aweme_id: str, meta: dict, source: str) -> Video:
    """登记视频元数据（幂等：已存在则直接返回）。"""
    existing = db.query(Video).filter_by(aweme_id=aweme_id).first()
    if existing:
        return existing
    video = Video(
        aweme_id=aweme_id,
        url=meta.get("url"),
        title=meta.get("title") or meta.get("desc"),
        hashtags=meta.get("hashtags") or [],
        author_id=meta.get("author_id"),
        author_name=meta.get("author_name"),
        digg_count=meta.get("digg_count") or 0,
        comment_count=meta.get("comment_count") or 0,
        share_count=meta.get("share_count") or 0,
        source=source,
        status=VideoStatus.PENDING,
    )
    db.add(video)
    db.commit()
    return video


def step_download(db: Session, video: Video) -> None:
    save_dir = str(get_settings().data_path / "videos")
    path = douyin.download_video(video.aweme_id, save_dir)
    if not path or not Path(path).exists():
        raise RuntimeError("下载失败或文件不存在")
    video.local_path = path
    video.status = VideoStatus.DOWNLOADED
    db.commit()

    # 同步抓评论入库
    raw = douyin.fetch_comments(video.aweme_id, count=100)
    comments = sorted(raw, key=lambda c: c.get("digg_count", 0), reverse=True)
    for item in comments[: get_settings().top_comments]:
        cid = str(item.get("comment_id") or item.get("cid") or "")
        if not cid or db.query(Comment).filter_by(comment_id=cid).first():
            continue
        db.add(Comment(comment_id=cid, video_id=video.id,
                       text=item.get("text", ""),
                       digg_count=item.get("digg_count", 0)))
    db.commit()


def step_asr(db: Session, video: Video) -> None:
    text = asr.transcribe(video.local_path)
    if not text.strip():
        # 无语音/识别为空：视为字幕采集失败，交给 OCR 手动兜底
        raise RuntimeError("ASR 未识别到语音内容")
    video.asr_text = text
    video.status = VideoStatus.ASR_DONE
    db.commit()


def step_classify(db: Session, video: Video) -> None:
    db.refresh(video)
    classify_video(db, video)
    db.commit()


def step_index(db: Session, video: Video) -> None:
    db.refresh(video)
    index_video(db, video)
    db.commit()


# 状态 -> 下一步骤（OCR 不在其中，见 run_ocr）
STEPS = {
    VideoStatus.PENDING: step_download,
    VideoStatus.DOWNLOADED: step_asr,
    VideoStatus.ASR_DONE: step_classify,
    VideoStatus.CLASSIFIED: step_index,
}


def run_video(video_id: int) -> None:
    """从当前状态开始跑完剩余流水线。供后台任务调用。"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        video = db.get(Video, video_id)
        while video and video.status in STEPS:
            step = STEPS[video.status]
            try:
                logger.info(f"[{video.aweme_id}] {video.status} -> {step.__name__}")
                step(db, video)
            except Exception as e:
                logger.exception(f"[{video.aweme_id}] {step.__name__} 失败")
                video.status = VideoStatus.FAILED
                video.error = f"{step.__name__}: {e}"
                db.commit()
                return
    finally:
        db.close()


def run_ocr(video_id: int) -> bool:
    """手动 OCR 兜底：提取画面文字。

    如果视频是因 ASR 失败而进入 failed 的，OCR 成功（识别到文字）后
    把状态拨回 asr_done 并自动接力后续流程（分类→入库）。
    返回是否识别到文字。
    """
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        video = db.get(Video, video_id)
        if not video or not video.local_path:
            logger.warning(f"OCR 跳过 video={video_id}：无本地文件")
            return False
        asr_failed = video.status == VideoStatus.FAILED and "step_asr" in (video.error or "")
        video.ocr_text = ocr.ocr_video(video.local_path)
        if asr_failed and video.ocr_text.strip():
            video.status = VideoStatus.ASR_DONE  # 字幕以 OCR 方式补齐
            video.error = None
        db.commit()
        has_text = bool(video.ocr_text.strip())
    finally:
        db.close()
    if has_text:
        run_video(video_id)  # 状态到位时自动接力分类/入库
    return has_text


def collect_hot(db: Session, board: str = "热榜", limit: int = 50) -> list[int]:
    """热榜采集入口：登记视频并入队。"""
    items = douyin.fetch_hot_board(board)
    ids = []
    for item in items[:limit]:
        aweme_id = str(item.get("aweme_id") or item.get("id") or "")
        if not aweme_id:
            continue
        video = register_video(db, aweme_id, item, source="hot")
        ids.append(video.id)
    return ids


def collect_account(db: Session, sec_uid: str, count: int = 50,
                    min_digg: int = 0) -> list[int]:
    """达人采集入口，支持点赞数过滤。"""
    items = douyin.fetch_account_posts(sec_uid, count=count)
    ids = []
    for item in items:
        if (item.get("digg_count") or 0) < min_digg:
            continue
        aweme_id = str(item.get("aweme_id") or item.get("id") or "")
        if not aweme_id:
            continue
        video = register_video(db, aweme_id, item, source="account")
        ids.append(video.id)
    return ids
