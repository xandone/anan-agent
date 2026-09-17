"""视频库路由：列表、详情、人工改标、OCR 兜底。"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Category, Video, VideoStatus
from app.pipeline.orchestrator import run_ocr

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("")
def list_videos(
    status: VideoStatus | None = None,
    category_id: int | None = None,
    source: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Video)
    if status:
        q = q.filter(Video.status == status)
    if category_id:
        q = q.filter(Video.category_id == category_id)
    if source:
        q = q.filter(Video.source == source)
    total = q.count()
    items = (q.order_by(Video.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return {
        "total": total,
        "items": [{
            "id": v.id, "aweme_id": v.aweme_id, "title": v.title,
            "author_name": v.author_name, "digg_count": v.digg_count,
            "status": v.status.value, "category_id": v.category_id,
            "confidence": v.classify_confidence, "source": v.source,
            "error": v.error,
        } for v in items],
    }


@router.get("/{video_id}")
def video_detail(video_id: int, db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404)
    return {
        "id": v.id, "aweme_id": v.aweme_id, "title": v.title,
        "hashtags": v.hashtags, "author_name": v.author_name,
        "digg_count": v.digg_count, "status": v.status.value,
        "category_id": v.category_id, "confidence": v.classify_confidence,
        "ocr_text": v.ocr_text, "asr_text": v.asr_text, "error": v.error,
        "comments": [{"text": c.text, "digg_count": c.digg_count}
                     for c in sorted(v.comments, key=lambda x: x.digg_count, reverse=True)],
    }


@router.post("/{video_id}/ocr")
def ocr_video(video_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """单条 OCR 兜底：提取画面文字。ASR 失败的任务 OCR 成功后会自动接力分类。"""
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404)
    if not v.local_path:
        raise HTTPException(400, "视频尚未下载，无法 OCR")
    bg.add_task(run_ocr, video_id)
    return {"ok": True, "video_id": video_id}


class OcrBatchReq(BaseModel):
    video_ids: list[int] | None = None  # 指定 ID 列表
    only_failed: bool = True            # 未指定时：只处理 ASR 失败的


@router.post("/ocr-batch")
def ocr_batch(req: OcrBatchReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """批量 OCR 兜底。默认处理所有因 ASR 失败而卡住的任务。"""
    q = db.query(Video).filter(Video.local_path.isnot(None))
    if req.video_ids:
        q = q.filter(Video.id.in_(req.video_ids))
    elif req.only_failed:
        q = q.filter(Video.status == VideoStatus.FAILED,
                     Video.error.like("step_asr%"))
    ids = [v.id for v in q.all()]
    for vid in ids:
        bg.add_task(run_ocr, vid)
    return {"queued": len(ids), "video_ids": ids}


class RelabelReq(BaseModel):
    category_id: int | None


@router.post("/{video_id}/relabel")
def relabel(video_id: int, req: RelabelReq, db: Session = Depends(get_db)):
    """人工改标：修正 LLM 分类结果。"""
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404)
    if req.category_id and not db.get(Category, req.category_id):
        raise HTTPException(400, "类别不存在")
    v.category_id = req.category_id
    v.classify_source = "human"
    v.classify_confidence = 1.0
    db.commit()
    return {"ok": True}
